"""In-memory lookup table over every fingerprinted track."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION

if TYPE_CHECKING:
    from ai_crate_digger.storage import Database

# About 12 bytes per entry in memory, so this caps the index at roughly 3.6 GB.
MAX_INDEX_HASHES = 300_000_000


@dataclass(frozen=True)
class Matches:
    """Index entries matched by a batch of query hashes."""

    query_idx: npt.NDArray[np.int64]
    track_idx: npt.NDArray[np.int32]
    track_t: npt.NDArray[np.int32]


@dataclass(frozen=True)
class LibraryIndex:
    """Hashes from all tracks, sorted by hash value for binary search."""

    hashes: npt.NDArray[np.uint32]
    times: npt.NDArray[np.int32]
    track_idx: npt.NDArray[np.int32]
    track_hashes: list[str]
    max_track_frames: int

    @classmethod
    def build(
        cls,
        items: Iterable[tuple[str, npt.NDArray[np.uint32], npt.NDArray[np.int32]]],
    ) -> LibraryIndex:
        """Build an index from ``(track_hash, hashes, times)`` tuples."""
        track_hashes: list[str] = []
        hash_parts: list[npt.NDArray[np.uint32]] = []
        time_parts: list[npt.NDArray[np.int32]] = []
        idx_parts: list[npt.NDArray[np.int32]] = []
        for track_hash, hashes, times in items:
            idx_parts.append(np.full(len(hashes), len(track_hashes), dtype=np.int32))
            track_hashes.append(track_hash)
            hash_parts.append(hashes)
            time_parts.append(times)
        if not track_hashes:
            return cls(
                hashes=np.zeros(0, dtype=np.uint32),
                times=np.zeros(0, dtype=np.int32),
                track_idx=np.zeros(0, dtype=np.int32),
                track_hashes=[],
                max_track_frames=0,
            )
        hashes = np.concatenate(hash_parts)
        times = np.concatenate(time_parts)
        track_idx = np.concatenate(idx_parts)
        order = np.argsort(hashes, kind="stable")
        return cls(
            hashes=hashes[order],
            times=times[order],
            track_idx=track_idx[order],
            track_hashes=track_hashes,
            max_track_frames=int(times.max()) if len(times) else 0,
        )

    def __len__(self) -> int:
        return len(self.track_hashes)

    def lookup(self, query: npt.NDArray[np.uint32], max_matches: int) -> Matches:
        """Return every index entry whose hash equals a query hash."""
        lo = np.searchsorted(self.hashes, query, side="left")
        hi = np.searchsorted(self.hashes, query, side="right")
        counts = np.minimum(hi - lo, max_matches)
        total = int(counts.sum())
        if total == 0:
            return Matches(
                query_idx=np.zeros(0, dtype=np.int64),
                track_idx=np.zeros(0, dtype=np.int32),
                track_t=np.zeros(0, dtype=np.int32),
            )
        query_idx = np.repeat(np.arange(len(query), dtype=np.int64), counts)
        run_start = np.cumsum(counts) - counts
        within = np.arange(total, dtype=np.int64) - np.repeat(run_start, counts)
        pos = np.repeat(lo, counts) + within
        return Matches(query_idx=query_idx, track_idx=self.track_idx[pos], track_t=self.times[pos])


_cache: dict[str, tuple[int, LibraryIndex]] = {}


def invalidate_index_cache() -> None:
    """Forget cached indexes. Call after fingerprints are added or replaced."""
    _cache.clear()


def get_library_index(db: Database) -> LibraryIndex:
    """Load the library index for ``db``, reusing the cached copy while it is current."""
    count = db.count_fingerprints(FINGERPRINT_VERSION)
    key = str(db.db_path)
    cached = _cache.get(key)
    if cached is not None and cached[0] == count:
        return cached[1]

    n_hashes = db.sum_fingerprint_hashes(FINGERPRINT_VERSION)
    if n_hashes > MAX_INDEX_HASHES:
        gigabytes = n_hashes * 12 / 1e9
        msg = (
            f"The fingerprint index has {n_hashes:,} hashes and would need about "
            f"{gigabytes:.1f} GB of memory, which is over the safety limit."
        )
        raise FingerprintError(msg)

    index = LibraryIndex.build(db.iter_fingerprints(FINGERPRINT_VERSION))
    _cache[key] = (count, index)
    return index
