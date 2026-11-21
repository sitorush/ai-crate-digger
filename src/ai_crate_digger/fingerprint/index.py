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

# The built index holds 12 bytes per entry, but building it peaks at about 25 bytes
# per entry (the arrays, an int64 sort order and one sorted copy), so this cap keeps
# the peak at roughly 5 GB.
MAX_INDEX_HASHES = 200_000_000


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
        total: int | None = None,
    ) -> LibraryIndex:
        """Build an index from ``(track_hash, hashes, times)`` tuples.

        Passing ``total`` (the number of hashes across all items) lets the arrays be
        allocated once and filled in place, which keeps peak memory down.
        """
        track_hashes: list[str] = []
        if total is None:
            hash_parts: list[npt.NDArray[np.uint32]] = []
            time_parts: list[npt.NDArray[np.int32]] = []
            idx_parts: list[npt.NDArray[np.int32]] = []
            for track_hash, track_h, track_t in items:
                idx_parts.append(np.full(len(track_h), len(track_hashes), dtype=np.int32))
                track_hashes.append(track_hash)
                hash_parts.append(track_h)
                time_parts.append(track_t)
            if not track_hashes:
                return cls._empty()
            hashes = np.concatenate(hash_parts).astype(np.uint32, copy=False)
            del hash_parts
            times = np.concatenate(time_parts).astype(np.int32, copy=False)
            del time_parts
            track_idx = np.concatenate(idx_parts).astype(np.int32, copy=False)
            del idx_parts
        else:
            hashes = np.empty(total, dtype=np.uint32)
            times = np.empty(total, dtype=np.int32)
            track_idx = np.empty(total, dtype=np.int32)
            pos = 0
            for track_hash, track_h, track_t in items:
                end = pos + len(track_h)
                if end > len(hashes):
                    # Fingerprints were added after ``total`` was read: grow in place.
                    size = max(end, len(hashes) + len(hashes) // 8)
                    hashes = np.resize(hashes, size)
                    times = np.resize(times, size)
                    track_idx = np.resize(track_idx, size)
                hashes[pos:end] = track_h
                times[pos:end] = track_t
                track_idx[pos:end] = len(track_hashes)
                track_hashes.append(track_hash)
                pos = end
            if not track_hashes:
                return cls._empty()
            if pos != len(hashes):
                hashes, times, track_idx = hashes[:pos], times[:pos], track_idx[:pos]

        max_track_frames = int(times.max()) if len(times) else 0
        # Apply the sort order one array at a time so only one extra copy exists.
        order = np.argsort(hashes, kind="stable")
        hashes = hashes[order]
        times = times[order]
        track_idx = track_idx[order]
        del order
        return cls(
            hashes=hashes,
            times=times,
            track_idx=track_idx,
            track_hashes=track_hashes,
            max_track_frames=max_track_frames,
        )

    @classmethod
    def _empty(cls) -> LibraryIndex:
        return cls(
            hashes=np.zeros(0, dtype=np.uint32),
            times=np.zeros(0, dtype=np.int32),
            track_idx=np.zeros(0, dtype=np.int32),
            track_hashes=[],
            max_track_frames=0,
        )

    def __len__(self) -> int:
        return len(self.track_hashes)

    def lookup(self, query: npt.NDArray[np.uint32], max_matches: int) -> Matches:
        """Return every index entry whose hash equals a query hash.

        A hash held by more than ``max_matches`` entries is too common to tell tracks
        apart and is ignored entirely. Truncating it instead would keep only the
        lowest track indexes and make results depend on library order.
        """
        lo = np.searchsorted(self.hashes, query, side="left")
        hi = np.searchsorted(self.hashes, query, side="right")
        counts = hi - lo
        counts[counts > max_matches] = 0
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


_cache: dict[str, tuple[tuple[int, int, str | None], LibraryIndex]] = {}


def invalidate_index_cache() -> None:
    """Forget cached indexes. Call after fingerprints are added or replaced."""
    _cache.clear()


def get_library_index(db: Database) -> LibraryIndex:
    """Load the library index for ``db``, reusing the cached copy while it is current."""
    signature = db.fingerprint_signature(FINGERPRINT_VERSION)
    key = str(db.db_path)
    cached = _cache.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    n_hashes = signature[1]
    if n_hashes > MAX_INDEX_HASHES:
        gigabytes = n_hashes * 25 / 1e9
        msg = (
            f"The fingerprint index has {n_hashes:,} hashes and would need about "
            f"{gigabytes:.1f} GB of memory, which is over the safety limit."
        )
        raise FingerprintError(msg)

    _cache.pop(key, None)
    index = LibraryIndex.build(db.iter_fingerprints(FINGERPRINT_VERSION), total=n_hashes)
    _cache[key] = (signature, index)
    return index
