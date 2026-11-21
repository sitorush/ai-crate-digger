"""Deterministic synthetic audio for fingerprint tests (no copyrighted material)."""

import librosa
import numpy as np
import numpy.typing as npt

SR = 11025

Audio = npt.NDArray[np.float32]


def make_track(seed: int, seconds: float) -> Audio:
    """Random decaying notes with harmonics. Different seeds give different 'songs'."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(seconds * SR), dtype=np.float32)
    t = 0.0
    while t < seconds:
        freq = float(np.exp(rng.uniform(np.log(150), np.log(3500))))
        n_note = int(rng.uniform(0.15, 0.5) * SR)
        amp = rng.uniform(0.2, 0.6)
        tt = np.arange(n_note) / SR
        env = np.exp(-tt * rng.uniform(4, 9))
        note = (
            amp
            * env
            * sum(
                weight * np.sin(2 * np.pi * k * freq * tt)
                for k, weight in ((1, 1.0), (2, 0.5), (3, 0.25))
            )
        )
        start = int(t * SR)
        end = min(len(out), start + n_note)
        out[start:end] += note[: end - start].astype(np.float32)
        t += rng.uniform(0.06, 0.2)
    out += rng.normal(0, 0.003, len(out)).astype(np.float32)
    normalised: Audio = (out / np.abs(out).max() * 0.8).astype(np.float32)
    return normalised


def stretch_pitch(audio: Audio, speed: float) -> Audio:
    """Play ``audio`` ``speed`` times faster with pitch following (vinyl style)."""
    positions = np.arange(int(len(audio) / speed)) * speed
    shifted: Audio = np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)
    return shifted


def stretch_keylock(audio: Audio, speed: float) -> Audio:
    """Play ``audio`` ``speed`` times faster keeping pitch (key lock)."""
    return np.asarray(librosa.effects.time_stretch(audio, rate=speed), dtype=np.float32)


def place(audio: Audio, start_sec: float, total_sec: float, fade_sec: float = 3.0) -> Audio:
    """Put ``audio`` into a silent buffer at ``start_sec`` with fade in and out."""
    out = np.zeros(int(total_sec * SR), dtype=np.float32)
    faded = audio.copy()
    k = int(fade_sec * SR)
    faded[:k] *= np.linspace(0, 1, k, dtype=np.float32)
    faded[-k:] *= np.linspace(1, 0, k, dtype=np.float32)
    start = int(start_sec * SR)
    end = min(len(out), start + len(faded))
    out[start:end] += faded[: end - start]
    return out


def add_noise(audio: Audio, level: float, seed: int = 0) -> Audio:
    """Add white noise at ``level`` standard deviation."""
    rng = np.random.default_rng(seed)
    return (audio + rng.normal(0, level, len(audio))).astype(np.float32)
