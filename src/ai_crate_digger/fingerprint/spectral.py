"""Audio decoding and spectrogram peak extraction."""

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import numpy.typing as npt
from scipy import ndimage

from ai_crate_digger.fingerprint.params import FingerprintParams


@dataclass(frozen=True)
class Peaks:
    """Spectrogram peaks sorted by time then frequency."""

    t: npt.NDArray[np.int32]  # frame index
    f: npt.NDArray[np.int32]  # FFT bin
    n_frames: int  # total frames analysed


def load_audio(path: Path, sample_rate: int) -> npt.NDArray[np.float32]:
    """Decode an audio file to mono float32 at the fingerprint sample rate."""
    audio, _ = librosa.load(str(path), sr=sample_rate, mono=True)
    return np.asarray(audio, dtype=np.float32)


def _limit_per_block(
    t: npt.NDArray[np.int32],
    f: npt.NDArray[np.int32],
    amp: npt.NDArray[np.float32],
    block_frames: int,
    keep: int,
) -> tuple[npt.NDArray[np.int32], npt.NDArray[np.int32]]:
    """Keep the strongest ``keep`` peaks in each block, sorted by time then frequency."""
    if len(t) == 0:
        return t, f
    block = t // block_frames
    order = np.lexsort((-amp, block))
    block_sorted = block[order]
    first = np.concatenate(([True], block_sorted[1:] != block_sorted[:-1]))
    positions = np.arange(len(order))
    group_start = np.maximum.accumulate(np.where(first, positions, 0))
    selected = order[(positions - group_start) < keep]
    final = np.lexsort((f[selected], t[selected]))
    selected = selected[final]
    return t[selected], f[selected]


def extract_peaks(audio: npt.NDArray[np.float32], params: FingerprintParams) -> Peaks:
    """Find the strongest local spectrogram peaks in ``audio``."""
    hop, n_fft = params.hop_length, params.n_fft
    if len(audio) < n_fft:
        empty = np.zeros(0, dtype=np.int32)
        return Peaks(t=empty, f=empty, n_frames=0)

    n_frames = 1 + (len(audio) - n_fft) // hop
    context = params.peak_time_size
    all_t: list[npt.NDArray[np.int32]] = []
    all_f: list[npt.NDArray[np.int32]] = []
    all_amp: list[npt.NDArray[np.float32]] = []

    for start in range(0, n_frames, params.chunk_frames):
        stop = min(start + params.chunk_frames, n_frames)
        first = max(0, start - context)
        last = min(n_frames, stop + context)
        segment = audio[first * hop : (last - 1) * hop + n_fft]
        spec = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop, center=False))
        db = 20.0 * np.log10(spec + 1e-6)
        local_max = ndimage.maximum_filter(
            db,
            size=(params.peak_freq_size, params.peak_time_size),
            mode="constant",
            cval=-200.0,
        )
        is_peak = (db == local_max) & (spec >= params.min_magnitude)
        f_idx, t_idx = np.nonzero(is_peak)
        t_abs = t_idx + first
        inside = (t_abs >= start) & (t_abs < stop)
        all_t.append(t_abs[inside].astype(np.int32))
        all_f.append(f_idx[inside].astype(np.int32))
        all_amp.append(db[f_idx[inside], t_idx[inside]].astype(np.float32))

    t = np.concatenate(all_t)
    f = np.concatenate(all_f)
    amp = np.concatenate(all_amp)
    t, f = _limit_per_block(t, f, amp, params.block_frames, params.peaks_per_block)
    return Peaks(t=t, f=f, n_frames=n_frames)
