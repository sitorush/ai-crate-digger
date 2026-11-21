"""Fingerprint library tracks and store the results."""

import logging
import multiprocessing
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from ai_crate_digger.analysis.parallel import _worker_init
from ai_crate_digger.core.config import get_settings
from ai_crate_digger.fingerprint.hashing import hash_peaks
from ai_crate_digger.fingerprint.index import invalidate_index_cache
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION, FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks, load_audio
from ai_crate_digger.storage import Database

logger = logging.getLogger(__name__)

Fingerprint = tuple[npt.NDArray[np.uint32], npt.NDArray[np.int32]]


@dataclass(frozen=True)
class IndexReport:
    """Outcome of an indexing run."""

    indexed: int
    skipped: int
    failed: list[tuple[str, str]] = field(default_factory=list)


def fingerprint_audio(
    audio: npt.NDArray[np.float32], params: FingerprintParams | None = None
) -> Fingerprint:
    """Fingerprint decoded audio as a library track."""
    params = params or FingerprintParams()
    peaks = extract_peaks(audio, params)
    hs = hash_peaks(peaks, params, rank_min=params.index_rank_min, rank_max=params.index_rank_max)
    return hs.hashes, hs.anchor_t.astype(np.int32)


def fingerprint_file(path: str) -> Fingerprint:
    """Fingerprint an audio file. Top-level so worker processes can run it."""
    params = FingerprintParams()
    return fingerprint_audio(load_audio(Path(path), params.sample_rate), params)


def index_library(
    db: Database,
    *,
    force: bool = False,
    workers: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> IndexReport:
    """Fingerprint every track that has no current fingerprint.

    Args:
        db: Initialised catalogue database
        force: Re-fingerprint tracks that already have one
        workers: Worker processes (None picks cpu_count - 1, 1 runs in-process)
        on_progress: Called with ``(done, total)`` after each track
    """
    tracks = db.get_all_tracks()
    done = set() if force else db.get_fingerprinted_hashes(FINGERPRINT_VERSION)
    todo = [(t.file_hash, str(t.file_path)) for t in tracks if t.file_hash not in done]
    skipped = len(tracks) - len(todo)
    failed: list[tuple[str, str]] = []
    finished = 0

    def store(file_hash: str, path: str, result: Fingerprint | Exception) -> None:
        nonlocal finished
        if isinstance(result, Exception):
            logger.warning("Fingerprinting failed for %s: %s", path, result)
            failed.append((path, str(result)))
        else:
            db.upsert_fingerprint(file_hash, result[0], result[1], FINGERPRINT_VERSION)
        finished += 1
        if on_progress:
            on_progress(finished, len(todo))

    if workers is None:
        workers = get_settings().max_workers or max(1, (os.cpu_count() or 2) - 1)

    if workers <= 1 or len(todo) <= 1:
        for file_hash, path in todo:
            try:
                store(file_hash, path, fingerprint_file(path))
            except Exception as exc:
                store(file_hash, path, exc)
    else:
        _run_pool(todo, workers, store, failed)

    invalidate_index_cache()
    return IndexReport(indexed=len(todo) - len(failed), skipped=skipped, failed=failed)


def _run_pool(
    todo: list[tuple[str, str]],
    workers: int,
    store: Callable[[str, str, Fingerprint | Exception], None],
    failed: list[tuple[str, str]],
) -> None:
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=context, initializer=_worker_init
    ) as pool:
        futures = {pool.submit(fingerprint_file, path): (h, path) for h, path in todo}
        try:
            for future in as_completed(futures):
                file_hash, path = futures[future]
                try:
                    result: Fingerprint | Exception = future.result()
                except BrokenProcessPool:
                    raise
                except Exception as exc:
                    result = exc
                store(file_hash, path, result)
        except BrokenProcessPool:
            logger.error("Fingerprint worker pool crashed. Re-run to resume.")
            failed.extend(
                (path, "worker pool crashed")
                for fut, (_, path) in futures.items()
                if not fut.done()
            )
