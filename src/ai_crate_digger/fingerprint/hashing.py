"""Pair spectrogram peaks into compact landmark hashes."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import Peaks


@dataclass(frozen=True)
class HashSet:
    """Landmark hashes with their anchor times."""

    hashes: npt.NDArray[np.uint32]
    anchor_t: npt.NDArray[np.int64]  # anchor frame after any time scaling
    source_t: npt.NDArray[np.int64]  # anchor frame before time scaling


def _band(freq_bins: npt.NDArray[np.floating[Any]], band_width: float) -> npt.NDArray[np.int64]:
    """Map FFT bins to log-spaced bands so small pitch shifts rarely change a hash."""
    bands: npt.NDArray[np.int64] = np.floor(np.log1p(freq_bins) / np.log1p(band_width)).astype(
        np.int64
    )
    return bands


def hash_peaks(
    peaks: Peaks,
    params: FingerprintParams,
    *,
    rank_min: int,
    rank_max: int,
    time_scale: float = 1.0,
    freq_scale: float = 1.0,
) -> HashSet:
    """Pair each peak with the peaks ranked ``rank_min..rank_max`` after it in time.

    ``time_scale`` and ``freq_scale`` rescale peak coordinates before hashing, which
    lets a mix be compared to the library under a tempo or pitch hypothesis.
    """
    source_t = peaks.t.astype(np.int64)
    scaled_t = np.rint(peaks.t * time_scale).astype(np.int64)
    bands = _band(peaks.f * freq_scale, params.band_width)
    hash_parts: list[npt.NDArray[np.uint32]] = []
    anchor_parts: list[npt.NDArray[np.int64]] = []
    source_parts: list[npt.NDArray[np.int64]] = []

    for rank in range(rank_min, rank_max + 1):
        if len(scaled_t) <= rank:
            break
        dt = scaled_t[rank:] - scaled_t[:-rank]
        ok = (dt >= params.dt_min) & (dt <= params.dt_max)
        packed = (bands[:-rank][ok] << 15) | (bands[rank:][ok] << 6) | dt[ok]
        hash_parts.append(packed.astype(np.uint32))
        anchor_parts.append(scaled_t[:-rank][ok])
        source_parts.append(source_t[:-rank][ok])

    if not hash_parts:
        return HashSet(
            hashes=np.zeros(0, dtype=np.uint32),
            anchor_t=np.zeros(0, dtype=np.int64),
            source_t=np.zeros(0, dtype=np.int64),
        )
    return HashSet(
        hashes=np.concatenate(hash_parts),
        anchor_t=np.concatenate(anchor_parts),
        source_t=np.concatenate(source_parts),
    )
