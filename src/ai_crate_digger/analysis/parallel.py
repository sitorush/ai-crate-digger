"""Parallel audio analysis using ProcessPoolExecutor."""

import logging
import multiprocessing
import os
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from ai_crate_digger.analysis.analyzer import analyze_track
from ai_crate_digger.core.config import get_settings
from ai_crate_digger.core.models import Track

logger = logging.getLogger(__name__)


def _worker_init() -> None:
    """Limit BLAS/OpenBLAS threads in each worker.

    Must be set before numpy initialises its BLAS backend, which happens on
    first import inside the spawned process.  Without this, numpy's use of
    Accelerate / OpenBLAS / BLAS can segfault on Apple Silicon when multiple
    workers run concurrently.
    """
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")


def _analyze_single(track: Track) -> Track:
    """Wrapper for multiprocessing (must be top-level function)."""
    try:
        return analyze_track(track)
    except Exception as e:
        logger.error("Analysis failed for %s: %s", track.file_path, e)
        # Return original track with error noted
        return track.model_copy(update={"comment": f"Analysis error: {e}"})


class ParallelAnalyzer:
    """Parallel audio analyzer using process pool."""

    def __init__(self, max_workers: int | None = None):
        """Initialise analyzer.

        Args:
            max_workers: Number of worker processes. None = cpu_count - 1
        """
        settings = get_settings()
        self.max_workers = max_workers or settings.max_workers
        if self.max_workers is None:
            self.max_workers = max(1, multiprocessing.cpu_count() - 1)

    def analyze_batch(
        self,
        tracks: list[Track],
        on_progress: Callable[[Track], None] | None = None,
    ) -> Iterator[Track]:
        """Analyze tracks in parallel, falling back to sequential if workers crash.

        Args:
            tracks: List of tracks to analyze
            on_progress: Optional callback for progress updates

        Yields:
            Analyzed tracks as they complete
        """
        if not tracks:
            return

        logger.info(
            "Starting parallel analysis of %d tracks with %d workers",
            len(tracks),
            self.max_workers,
        )

        # spawn is the default on macOS but setting it explicitly ensures
        # worker processes start clean (no inherited numpy/BLAS state).
        mp_context = multiprocessing.get_context("spawn")

        completed_paths: set[Path] = set()
        pool_crashed = False

        try:
            with ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context=mp_context,
                initializer=_worker_init,
                # Restart workers every N tasks to prevent memory/state accumulation.
                # This significantly reduces segfault risk on Apple Silicon.
                max_tasks_per_child=4,
            ) as pool:
                futures = {pool.submit(_analyze_single, track): track for track in tracks}

                for future in as_completed(futures):
                    original = futures[future]
                    try:
                        analyzed = future.result()
                        completed_paths.add(original.file_path)
                        if on_progress:
                            on_progress(analyzed)
                        yield analyzed
                    except BrokenProcessPool:
                        pool_crashed = True
                        break
                    except Exception as e:
                        logger.error("Worker failed for %s: %s", original.file_path, e)
                        completed_paths.add(original.file_path)
                        if on_progress:
                            on_progress(original)
                        yield original

        except Exception:
            pool_crashed = True

        if pool_crashed:
            remaining = [t for t in tracks if t.file_path not in completed_paths]
            logger.warning(
                "Process pool crashed (numpy/BLAS issue, likely Apple Silicon). "
                "Falling back to sequential analysis for %d remaining tracks. "
                "Run with --workers 1 to skip parallel processing entirely.",
                len(remaining),
            )
            yield from self._analyze_sequential(remaining, on_progress)

    def _analyze_sequential(
        self,
        tracks: list[Track],
        on_progress: Callable[[Track], None] | None = None,
    ) -> Iterator[Track]:
        """Fall-back: analyse tracks one at a time in the main process."""
        for track in tracks:
            try:
                analyzed = _analyze_single(track)
            except Exception as e:
                logger.error("Analysis failed for %s: %s", track.file_path, e)
                analyzed = track
            if on_progress:
                on_progress(analyzed)
            yield analyzed
