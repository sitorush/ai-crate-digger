"""Parallel audio analysis using ProcessPoolExecutor."""

import logging
import multiprocessing
import os
from pathlib import Path
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

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
    import faulthandler
    import sys

    # Dump Python traceback to stderr on SIGSEGV/SIGFPE/SIGABRT so we can
    # see exactly which library call is crashing rather than just "segfault".
    faulthandler.enable(file=sys.stderr)

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
        """Analyze tracks in parallel with automatic crash recovery.

        Yields each track as soon as its worker finishes so callers see
        real-time progress rather than waiting for the whole batch.

        Workers are initialised with BLAS/OpenBLAS thread counts capped at 1
        to prevent segfaults on Apple Silicon.  On BrokenProcessPool the pool
        is restarted for the remaining tracks; the in-flight tracks that caused
        the crash are skipped so the scan always completes.

        Analysis never runs in the main process, so a SIGSEGV only kills the
        worker, not the scan.

        Args:
            tracks: List of tracks to analyze
            on_progress: Optional callback called for each completed track

        Yields:
            Analyzed tracks as they complete (streaming, not batched)
        """
        if not tracks:
            return

        max_workers: int = self.max_workers or 1

        logger.info(
            "Starting parallel analysis of %d tracks with %d workers",
            len(tracks),
            max_workers,
        )

        remaining = list(tracks)
        restart_count = 0

        while remaining:
            completed_paths: set[Path] = set()
            pool_crashed = False

            mp_context = multiprocessing.get_context("spawn")
            try:
                with ProcessPoolExecutor(
                    max_workers=max_workers,
                    mp_context=mp_context,
                    initializer=_worker_init,
                ) as pool:
                    futures = {pool.submit(_analyze_single, t): t for t in remaining}
                    for future in as_completed(futures):
                        original = futures[future]
                        try:
                            analyzed = future.result()
                        except BrokenProcessPool:
                            pool_crashed = True
                            break
                        except Exception as e:
                            logger.error("Worker failed for %s: %s", original.file_path, e)
                            analyzed = original.model_copy(
                                update={"comment": f"Analysis error: {e}"}
                            )

                        completed_paths.add(original.file_path)
                        if on_progress:
                            on_progress(analyzed)
                        yield analyzed  # stream immediately, not after full batch

            except Exception:
                pass

            still_remaining = [t for t in remaining if t.file_path not in completed_paths]

            if not still_remaining:
                break  # all done

            if not pool_crashed:
                # Shouldn't happen, but avoid infinite loop
                break

            # Pool crashed -- skip in-flight tracks (likely crash cause) and restart
            restart_count += 1
            skipped = still_remaining[:max_workers]
            remaining = still_remaining[max_workers:]

            logger.warning(
                "Pool crashed (restart %d). Skipping %d tracks that were in-flight: %s",
                restart_count,
                len(skipped),
                ", ".join(t.file_path.name for t in skipped),
            )

            for track in skipped:
                analyzed = track.model_copy(
                    update={"comment": "Analysis skipped: worker crash (Apple Silicon BLAS)"}
                )
                if on_progress:
                    on_progress(analyzed)
                yield analyzed
