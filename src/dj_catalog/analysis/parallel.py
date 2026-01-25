"""Parallel audio analysis using ProcessPoolExecutor."""

import logging
import multiprocessing
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed

from dj_catalog.analysis.analyzer import analyze_track
from dj_catalog.core.config import get_settings
from dj_catalog.core.models import Track

logger = logging.getLogger(__name__)


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
        """Initialize analyzer.

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
        """Analyze tracks in parallel.

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

        with ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_analyze_single, track): track for track in tracks}

            for future in as_completed(futures):
                try:
                    analyzed = future.result()
                    if on_progress:
                        on_progress(analyzed)
                    yield analyzed
                except Exception as e:
                    original = futures[future]
                    logger.error("Worker failed for %s: %s", original.file_path, e)
                    yield original
