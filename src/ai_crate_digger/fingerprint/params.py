"""Fixed fingerprinting parameters.

Changing any value here invalidates stored fingerprints, so bump
``FINGERPRINT_VERSION`` alongside it.
"""

from dataclasses import dataclass

FINGERPRINT_VERSION = 1


@dataclass(frozen=True)
class FingerprintParams:
    """Parameters controlling spectrogram peaks and hash generation."""

    sample_rate: int = 11025
    n_fft: int = 1024
    hop_length: int = 256
    peak_freq_size: int = 25  # local-maximum neighbourhood in FFT bins
    peak_time_size: int = 21  # local-maximum neighbourhood in frames
    block_frames: int = 43  # about one second
    peaks_per_block: int = 20  # strongest peaks kept per block
    min_magnitude: float = 1e-2  # ignore digital silence
    chunk_frames: int = 43 * 60  # STFT processed in ~1 minute chunks
    band_width: float = 0.02  # log-frequency band width (2%)
    dt_min: int = 2  # frames
    dt_max: int = 63  # frames (6 bits)
    index_rank_min: int = 3  # tracks pair each anchor with peaks ranked 3..7 after it
    index_rank_max: int = 7
    query_rank_max: int = 24  # mixes pair with peaks ranked 1..24 (superset of the index)
    max_matches_per_hash: int = 200

    @property
    def frame_rate(self) -> float:
        """Spectrogram frames per second."""
        return self.sample_rate / self.hop_length

    @property
    def pairs_per_anchor(self) -> int:
        """Maximum index hashes generated per anchor peak."""
        return self.index_rank_max - self.index_rank_min + 1
