# Mix Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify which library tracks were played in a recorded DJ mix (with timings, tempo shift and confidence), and rebuild the playlist, via the MCP server and the CLI.

**Architecture:** A new `ai_crate_digger.fingerprint` package extracts spectrogram peaks, hashes them into landmark pairs, and stores one packed blob per track in a new `fingerprints` table. A mix is matched by rescaling its peaks under a grid of speed hypotheses (pitch-follows-tempo and key-lock), voting on `(block, track, time offset)`, and merging blocks into segments. Long work (indexing, identification) runs as background jobs polled through `get_job_status`.

**Tech Stack:** Python 3.11, numpy, scipy (peak picking), librosa (decoding, STFT), SQLAlchemy/SQLite, click/rich, MCP. Spec: `docs/superpowers/specs/2026-11-21-mix-identification-design.md`.

---

## Working notes

- **Where:** worktree `~/Sites/dj-catalog/.worktrees/dj-catalog-impl` (package `ai_crate_digger`, CLI `crate`). Run every command from that directory. Do not push; Tom reviews first.
- **Provenance:** every code block below was run before it went into this plan (full suite 259 passed, `mypy src/ scripts/` and `ruff` clean) on a scratch copy of this repo at commit `85e66e1`. The synthetic-audio tests pass on that copy, so a failure when you follow the plan means a transcription slip, not a design problem.
- **Verify commands:** `uv run pytest <path> -q --no-cov` for focused runs. The repo's default `addopts` adds a coverage gate that fails partial runs.
- **Deviations from the spec** (found while prototyping) are listed in the amendments patch in Task 13. The important ones: no `fingerprinted_at` column on `tracks` (a new table is the only migration-free option), `get_job_status` replaces `get_mix_result`, and 5 s blocks replace 10 s windows.
- **Not in scope:** live microphone identification, Beatport/ZipDJ lookups.
- **Commit hook:** Tom's global Claude hook runs `mypy .` (tests included, strict) before every `git commit`. All test code must be fully annotated; the plan's tests are. Commit `3487649` annotated the pre-existing tests so the hook passes. Do not bypass the hook.
- **Progress:** Task 0 done (branch `feat/mix-identification`). Prep commit `3487649` and Task 1 (`21caa66`) are done; Task 1's test patch below was applied with `monkeypatch: pytest.MonkeyPatch` annotations. Start at Task 2.

## File structure

| File | Responsibility |
|---|---|
| `src/ai_crate_digger/fingerprint/params.py` | Fixed fingerprint constants (`FingerprintParams`, `FINGERPRINT_VERSION`) |
| `src/ai_crate_digger/fingerprint/spectral.py` | Decode audio, chunked STFT, local peak picking, per-second peak cap |
| `src/ai_crate_digger/fingerprint/hashing.py` | Pair peaks into 24-bit landmark hashes, with optional time/frequency rescaling |
| `src/ai_crate_digger/fingerprint/index.py` | `LibraryIndex` (sorted arrays, binary-search lookup), cached loader, memory guard |
| `src/ai_crate_digger/fingerprint/matcher.py` | Speed hypotheses, voting, segment merging, confidence, unmatched spans |
| `src/ai_crate_digger/fingerprint/indexer.py` | Fingerprint files and store them (sequential or process pool) |
| `src/ai_crate_digger/fingerprint/inbox.py` | Resolve a mix path or the newest recording in the inbox folder |
| `src/ai_crate_digger/fingerprint/report.py` | Describe results with track names, order tracks for playlists |
| `src/ai_crate_digger/fingerprint/jobs.py` | Background job registry (one worker thread) |
| `src/ai_crate_digger/fingerprint/identify.py` | Decode, guard, match: the function jobs and the CLI call |
| `src/ai_crate_digger/mcp/mix_tools.py` | Four MCP tools and their dispatch |
| `src/ai_crate_digger/cli/mix.py` | `crate fingerprint` and `crate identify` |
| `scripts/benchmark_mix.py` | Recall, false matches, run time and memory on a real mix |
| `tests/fingerprint/` | Unit and synthetic-audio tests (`synth.py`, `library.py` are helpers) |

Modified: `pyproject.toml`, `core/config.py`, `core/exceptions.py`, `storage/database.py`, `mcp/tools.py`, `cli/main.py`, `tests/conftest.py`, `tests/core/test_config.py`, docs, spec.

---

### Task 0: Branch and baseline

**Files:** none

- [ ] **Step 1: Create the feature branch**

```bash
cd ~/Sites/dj-catalog/.worktrees/dj-catalog-impl
git status --short
git switch -c feat/mix-identification
```

Expected: `git status` prints nothing, then `Switched to a new branch 'feat/mix-identification'`.

- [ ] **Step 2: Confirm the baseline is green**

```bash
uv run pytest -q 2>&1 | tail -3 && uv run mypy src/ && uv run ruff check .
```

Expected: `177 passed`, `Success: no issues found`, `All checks passed!`. If anything fails here, stop and tell Tom before changing code.

### Task 1: Dependencies, settings and exception

**Files:**
- Modify: `pyproject.toml`, `uv.lock`
- Modify: `src/ai_crate_digger/core/config.py`
- Modify: `src/ai_crate_digger/core/exceptions.py`
- Test: `tests/core/test_config.py`

- [ ] **Step 1: Write the failing config tests**

Apply to `tests/core/test_config.py`:

```diff
--- a/tests/core/test_config.py
+++ b/tests/core/test_config.py
@@ -39,3 +39,17 @@
         monkeypatch.setenv("CRATE_OUTPUT_PATH", str(tmp_path))
         settings = Settings()
         assert settings.output_path == tmp_path
+
+    def test_mix_identification_defaults(self) -> None:
+        """Mix identification settings have defaults."""
+        settings = Settings()
+        assert settings.inbox_path == Path.home() / "Music" / "mixes"
+        assert settings.mix_min_seconds == 30.0
+        assert settings.mix_speed_range == 0.08
+        assert settings.mix_speed_step == 0.01
+        assert settings.mix_high_support > settings.mix_medium_support > settings.mix_low_support
+
+    def test_inbox_path_from_env(self, monkeypatch) -> None:
+        """The inbox folder can be overridden via environment."""
+        monkeypatch.setenv("CRATE_INBOX_PATH", "/recordings")
+        assert Settings().inbox_path == Path("/recordings")
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/core/test_config.py -q --no-cov
```

Expected: 2 failures, both `AttributeError: 'Settings' object has no attribute 'inbox_path'`.

- [ ] **Step 3: Add the settings and the exception**

`src/ai_crate_digger/core/config.py`:

```diff
--- a/src/ai_crate_digger/core/config.py
+++ b/src/ai_crate_digger/core/config.py
@@ -22,6 +22,11 @@
         description="Default directory for music library scanning",
     )
 
+    inbox_path: Path = Field(
+        default_factory=lambda: Path.home() / "Music" / "mixes",
+        description="Folder where recorded mixes are dropped for identification",
+    )
+
     # Performance
     max_workers: int | None = None  # None = auto-detect (cpu_count - 1)
     batch_size: int = 100  # DB batch write size
@@ -30,6 +35,14 @@
     analyze_by_default: bool = True
     sample_rate: int = 22050  # Hz for librosa
 
+    # Mix identification
+    mix_min_seconds: float = 30.0
+    mix_speed_range: float = 0.08
+    mix_speed_step: float = 0.01
+    mix_high_support: float = 0.12
+    mix_medium_support: float = 0.05
+    mix_low_support: float = 0.02
+
     model_config = {
         "env_prefix": "CRATE_",
         "env_file": ".env",
```

`src/ai_crate_digger/core/exceptions.py`:

```diff
--- a/src/ai_crate_digger/core/exceptions.py
+++ b/src/ai_crate_digger/core/exceptions.py
@@ -35,3 +35,9 @@
     """Error exporting playlist."""
 
     pass
+
+
+class FingerprintError(DJCatalogError):
+    """Error fingerprinting audio or identifying a mix."""
+
+    pass
```

- [ ] **Step 4: Declare numpy and scipy, and let mypy accept scipy's missing stubs**

Both are already installed through librosa, but the new code imports them directly. `pyproject.toml`:

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -19,6 +19,8 @@
     "sqlalchemy>=2.0",
     "mutagen>=1.47",
     "librosa>=0.10,<0.11",
+    "numpy>=1.26",
+    "scipy>=1.11",
     "essentia>=2.1b5",
     "chromadb>=0.4",
     "mcp>=1.0",
@@ -50,7 +52,7 @@
 plugins = ["pydantic.mypy"]
 
 [[tool.mypy.overrides]]
-module = ["essentia.*"]
+module = ["essentia.*", "scipy.*"]
 ignore_missing_imports = true
 
 [tool.ruff]
```

Then refresh the lock file:

```bash
uv lock
```

Expected: `uv.lock` changes only to list `numpy` and `scipy` as direct dependencies of `ai-crate-digger`. Check with `git diff --stat uv.lock`.

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/core/test_config.py -q --no-cov
```

Expected: all pass.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add pyproject.toml \
  uv.lock \
  src/ai_crate_digger/core/config.py \
  src/ai_crate_digger/core/exceptions.py \
  tests/core/test_config.py
git commit -m "feat: add mix identification settings and FingerprintError" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 2: Fingerprint parameters and spectral peaks

**Files:**
- Create: `src/ai_crate_digger/fingerprint/__init__.py` (empty)
- Create: `src/ai_crate_digger/fingerprint/params.py`
- Create: `src/ai_crate_digger/fingerprint/spectral.py`
- Create: `tests/fingerprint/__init__.py` (empty), `tests/fingerprint/synth.py`
- Test: `tests/fingerprint/test_spectral.py`

How it works: audio is decoded to mono 11.025 kHz. A 1024-point STFT (hop 256, about 43 frames per second) is taken in one-minute chunks with a few frames of context either side, so chunk boundaries do not change the result. A point is a peak if it equals the maximum of a 25 bin by 21 frame neighbourhood and is not digital silence. Only the 20 strongest peaks in each one-second block survive, which makes the result independent of overall loudness.

- [ ] **Step 1: Create the empty package files and the synthetic audio helper**

```bash
mkdir -p src/ai_crate_digger/fingerprint tests/fingerprint
touch src/ai_crate_digger/fingerprint/__init__.py tests/fingerprint/__init__.py
```

Create `tests/fingerprint/synth.py`:

```python
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
```

`make_track` builds a deterministic "song" from decaying notes, so tests need no real (copyrighted) audio. `stretch_pitch` plays audio faster with pitch following, like a vinyl pitch fader. `stretch_keylock` changes tempo only.

- [ ] **Step 2: Write the failing tests**

Create `tests/fingerprint/test_spectral.py`:

```python
"""Tests for spectrogram peak extraction."""

import numpy as np

from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks
from tests.fingerprint.synth import SR, make_track

PARAMS = FingerprintParams()


def test_sine_peaks_sit_on_the_tone_bin() -> None:
    t = np.arange(3 * SR) / SR
    audio = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    peaks = extract_peaks(audio, PARAMS)
    expected_bin = round(1000 / (SR / PARAMS.n_fft))
    assert len(peaks.t) > 0
    assert np.all(np.abs(peaks.f - expected_bin) <= 1)


def test_silence_has_no_peaks() -> None:
    peaks = extract_peaks(np.zeros(3 * SR, dtype=np.float32), PARAMS)
    assert len(peaks.t) == 0
    assert peaks.n_frames > 0


def test_audio_shorter_than_one_frame_is_empty() -> None:
    peaks = extract_peaks(np.zeros(100, dtype=np.float32), PARAMS)
    assert len(peaks.t) == 0
    assert peaks.n_frames == 0


def test_peaks_per_block_are_capped() -> None:
    rng = np.random.default_rng(0)
    audio = rng.normal(0, 0.3, 10 * SR).astype(np.float32)
    peaks = extract_peaks(audio, PARAMS)
    counts = np.bincount(peaks.t // PARAMS.block_frames)
    assert counts.max() <= PARAMS.peaks_per_block


def test_peaks_are_sorted_by_time() -> None:
    peaks = extract_peaks(make_track(1, 10), PARAMS)
    assert np.all(np.diff(peaks.t) >= 0)


def test_extraction_is_deterministic() -> None:
    audio = make_track(2, 10)
    a, b = extract_peaks(audio, PARAMS), extract_peaks(audio, PARAMS)
    assert np.array_equal(a.t, b.t)
    assert np.array_equal(a.f, b.f)


def test_chunk_boundaries_do_not_change_peaks() -> None:
    audio = make_track(3, 20)
    whole = extract_peaks(audio, PARAMS)
    chunked = extract_peaks(audio, FingerprintParams(chunk_frames=43 * 5))
    assert np.array_equal(whole.t, chunked.t)
    assert np.array_equal(whole.f, chunked.f)
```

- [ ] **Step 3: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_spectral.py -q --no-cov
```

Expected: collection error, `ModuleNotFoundError: No module named 'ai_crate_digger.fingerprint.params'`.

- [ ] **Step 4: Implement**

Create `src/ai_crate_digger/fingerprint/params.py`:

```python
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
```

Create `src/ai_crate_digger/fingerprint/spectral.py`:

```python
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
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/fingerprint/test_spectral.py -q --no-cov
```

Expected: `7 passed`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint \
  tests/fingerprint
git commit -m "feat: add spectrogram peak extraction for fingerprinting" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 3: Landmark hashing

**Files:**
- Create: `src/ai_crate_digger/fingerprint/hashing.py`
- Test: `tests/fingerprint/test_hashing.py`

How it works: each peak (the anchor) is paired with peaks ranked `rank_min..rank_max` after it in time. A hash packs `(band of anchor, band of target, time gap)` into 24 bits (9 + 9 + 6). Frequencies go through log-spaced 2% bands so a small pitch change rarely changes a hash. `time_scale` and `freq_scale` rescale peak coordinates before hashing, which is how a mix is tested against a tempo or pitch hypothesis without re-decoding it. Library tracks use sparse pairing (ranks 3 to 7) and mixes use dense pairing (ranks 1 to 24), so peaks added or dropped by a second track do not break matches.

- [ ] **Step 1: Write the failing tests**

Create `tests/fingerprint/test_hashing.py`:

```python
"""Tests for landmark hashing."""

import numpy as np

from ai_crate_digger.fingerprint.hashing import _band, hash_peaks
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import Peaks

PARAMS = FingerprintParams()


def _peaks(t: list[int], f: list[int]) -> Peaks:
    return Peaks(t=np.array(t, dtype=np.int32), f=np.array(f, dtype=np.int32), n_frames=max(t) + 1)


def test_hash_packs_both_bands_and_the_time_gap() -> None:
    hs = hash_peaks(_peaks([0, 10], [100, 200]), PARAMS, rank_min=1, rank_max=1)
    assert len(hs.hashes) == 1
    value = int(hs.hashes[0])
    assert value & 63 == 10
    assert (value >> 6) & 511 == _band(np.array([200.0]), PARAMS.band_width)[0]
    assert (value >> 15) & 511 == _band(np.array([100.0]), PARAMS.band_width)[0]
    assert hs.anchor_t[0] == 0


def test_pairs_outside_the_time_window_are_dropped() -> None:
    peaks = _peaks([0, 1, 100], [10, 20, 30])  # dt 1 is too small, dt 99 too large
    hs = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=2)
    assert len(hs.hashes) == 0


def test_rank_range_controls_pair_count() -> None:
    peaks = _peaks(list(range(0, 100, 5)), [50] * 20)
    one = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1)
    three = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=3)
    assert len(one.hashes) == 19
    assert len(three.hashes) == 19 + 18 + 17


def test_time_scale_stretches_the_gap() -> None:
    peaks = _peaks([0, 10], [100, 200])
    hs = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1, time_scale=2.0)
    assert int(hs.hashes[0]) & 63 == 20
    assert hs.source_t[0] == 0


def test_freq_scale_moves_the_band() -> None:
    peaks = _peaks([0, 10], [100, 200])
    scaled = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1, freq_scale=1.1)
    shifted = hash_peaks(_peaks([0, 10], [110, 220]), PARAMS, rank_min=1, rank_max=1)
    assert scaled.hashes[0] == shifted.hashes[0]


def test_no_peaks_gives_empty_hash_set() -> None:
    hs = hash_peaks(_peaks([0], [5]), PARAMS, rank_min=1, rank_max=3)
    assert len(hs.hashes) == 0
    assert len(hs.anchor_t) == 0
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_hashing.py -q --no-cov
```

Expected: collection error, `No module named 'ai_crate_digger.fingerprint.hashing'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/fingerprint/hashing.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/fingerprint -q --no-cov
```

Expected: `13 passed`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/hashing.py \
  tests/fingerprint/test_hashing.py
git commit -m "feat: add landmark hashing with tempo and pitch rescaling" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 4: Fingerprint storage

**Files:**
- Modify: `src/ai_crate_digger/storage/database.py`
- Test: `tests/storage/test_fingerprints.py`

Design note: this is a new `fingerprints` table, one packed blob per track (`uint32` hashes followed by `int32` anchor times), keyed by the track's file hash. It deliberately does not add a column to `tracks`: `create_all` cannot alter an existing SQLite table, so a new column would break every existing catalogue. `Database.delete_track` also removes the fingerprint, which keeps `crate clean` and the `clean_orphans` tool consistent.

- [ ] **Step 1: Write the failing tests**

Create `tests/storage/test_fingerprints.py`:

```python
"""Tests for fingerprint storage."""

from pathlib import Path

import numpy as np
import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init()
    return database


def _hashes(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.uint32)


def _times(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.int32)


def test_round_trip(db: Database) -> None:
    db.upsert_fingerprint("h1", _hashes(5, 9, 5), _times(10, 20, 30), version=1)
    [(track_hash, hashes, times)] = list(db.iter_fingerprints(1))
    assert track_hash == "h1"
    assert hashes.tolist() == [5, 9, 5]
    assert times.tolist() == [10, 20, 30]


def test_upsert_replaces_existing_fingerprint(db: Database) -> None:
    db.upsert_fingerprint("h1", _hashes(1, 2), _times(1, 2), version=1)
    db.upsert_fingerprint("h1", _hashes(7), _times(70), version=1)
    [(_, hashes, times)] = list(db.iter_fingerprints(1))
    assert hashes.tolist() == [7]
    assert times.tolist() == [70]
    assert db.count_fingerprints(1) == 1


def test_version_filters_everything(db: Database) -> None:
    db.upsert_fingerprint("old", _hashes(1), _times(1), version=1)
    db.upsert_fingerprint("new", _hashes(1, 2, 3), _times(1, 2, 3), version=2)
    assert db.get_fingerprinted_hashes(2) == {"new"}
    assert db.count_fingerprints(1) == 1
    assert db.sum_fingerprint_hashes(2) == 3
    assert [t for t, _, _ in db.iter_fingerprints(1)] == ["old"]


def test_empty_database_totals_are_zero(db: Database) -> None:
    assert db.count_fingerprints(1) == 0
    assert db.sum_fingerprint_hashes(1) == 0
    assert list(db.iter_fingerprints(1)) == []


def test_deleting_a_track_deletes_its_fingerprint(db: Database) -> None:
    track_id = db.insert_track(Track(file_path=Path("/music/a.mp3"), file_hash="h1"))
    db.upsert_fingerprint("h1", _hashes(1), _times(1), version=1)
    db.upsert_fingerprint("h2", _hashes(2), _times(2), version=1)
    assert db.delete_track(track_id) is True
    assert db.get_fingerprinted_hashes(1) == {"h2"}


def test_deleting_a_track_without_fingerprint_still_works(db: Database) -> None:
    track_id = db.insert_track(Track(file_path=Path("/music/a.mp3"), file_hash="h1"))
    assert db.delete_track(track_id) is True
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/storage/test_fingerprints.py -q --no-cov
```

Expected: 6 failures, `AttributeError: 'Database' object has no attribute 'upsert_fingerprint'`.

- [ ] **Step 3: Implement**

`src/ai_crate_digger/storage/database.py`:

```diff
--- a/src/ai_crate_digger/storage/database.py
+++ b/src/ai_crate_digger/storage/database.py
@@ -4,18 +4,24 @@
 
 import contextlib
 import json
+from collections.abc import Iterator
 from datetime import UTC, date, datetime
 from pathlib import Path
 from typing import TYPE_CHECKING, Any
 
+import numpy as np
+import numpy.typing as npt
 from sqlalchemy import (
     DateTime,
     Float,
     Index,
     Integer,
+    LargeBinary,
     String,
     Text,
     create_engine,
+    delete,
+    func,
     select,
 )
 from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
@@ -93,7 +99,19 @@
         Index("ix_tracks_bpm_key", "bpm", "key"),
         Index("ix_tracks_energy_danceability", "energy", "danceability"),
     )
+
+
+class FingerprintRow(Base):
+    """Packed audio fingerprint for one track (hashes then anchor times)."""
+
+    __tablename__ = "fingerprints"
 
+    track_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
+    version: Mapped[int] = mapped_column(Integer, nullable=False)
+    n_hashes: Mapped[int] = mapped_column(Integer, nullable=False)
+    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
+    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
+
 
 def _row_to_track(row: TrackRow) -> Track:
     """Convert database row to Track model."""
@@ -424,6 +442,69 @@
         row = self.session.execute(stmt).scalar_one_or_none()
         if row is None:
             return False
+        self.session.execute(
+            delete(FingerprintRow).where(FingerprintRow.track_hash == row.file_hash)
+        )
         self.session.delete(row)
         self.session.commit()
         return True
+
+    def upsert_fingerprint(
+        self,
+        track_hash: str,
+        hashes: npt.NDArray[np.uint32],
+        times: npt.NDArray[np.int32],
+        version: int,
+    ) -> None:
+        """Store (or replace) the fingerprint for a track.
+
+        Args:
+            track_hash: File hash of the track
+            hashes: Landmark hashes
+            times: Anchor frame of each hash, same length as ``hashes``
+            version: Fingerprint scheme version the hashes were made with
+        """
+        blob = hashes.astype(np.uint32).tobytes() + times.astype(np.int32).tobytes()
+        self.session.merge(
+            FingerprintRow(
+                track_hash=track_hash,
+                version=version,
+                n_hashes=len(hashes),
+                blob=blob,
+                created_at=datetime.now(tz=UTC),
+            )
+        )
+        self.session.commit()
+
+    def get_fingerprinted_hashes(self, version: int) -> set[str]:
+        """File hashes that already have a fingerprint made with ``version``."""
+        stmt = select(FingerprintRow.track_hash).where(FingerprintRow.version == version)
+        return set(self.session.execute(stmt).scalars().all())
+
+    def count_fingerprints(self, version: int) -> int:
+        """Number of stored fingerprints made with ``version``."""
+        stmt = (
+            select(func.count())
+            .select_from(FingerprintRow)
+            .where(FingerprintRow.version == version)
+        )
+        return int(self.session.execute(stmt).scalar_one())
+
+    def sum_fingerprint_hashes(self, version: int) -> int:
+        """Total number of hashes across fingerprints of ``version``."""
+        stmt = select(func.coalesce(func.sum(FingerprintRow.n_hashes), 0)).where(
+            FingerprintRow.version == version
+        )
+        return int(self.session.execute(stmt).scalar_one())
+
+    def iter_fingerprints(
+        self, version: int
+    ) -> Iterator[tuple[str, npt.NDArray[np.uint32], npt.NDArray[np.int32]]]:
+        """Yield ``(track_hash, hashes, times)`` for every fingerprint of ``version``."""
+        stmt = select(
+            FingerprintRow.track_hash, FingerprintRow.n_hashes, FingerprintRow.blob
+        ).where(FingerprintRow.version == version)
+        for track_hash, n_hashes, blob in self.session.execute(stmt):
+            hashes = np.frombuffer(blob, dtype=np.uint32, count=n_hashes)
+            times = np.frombuffer(blob, dtype=np.int32, count=n_hashes, offset=4 * n_hashes)
+            yield track_hash, hashes, times
```

- [ ] **Step 4: Run the storage tests**

```bash
uv run pytest tests/storage -q --no-cov
```

Expected: all pass, including the existing database tests.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/storage/database.py \
  tests/storage/test_fingerprints.py
git commit -m "feat: store track fingerprints in a new table" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 5: Library index

**Files:**
- Create: `src/ai_crate_digger/fingerprint/index.py`
- Test: `tests/fingerprint/test_index.py`

How it works: `LibraryIndex.build` concatenates every track's hashes and sorts them, so `lookup` can binary-search all query hashes at once and expand the matches with numpy (no Python loop). `max_matches` caps very common hashes. `get_library_index` reloads from the database only when the fingerprint count changes (or after `invalidate_index_cache()`), and refuses to load an index larger than `MAX_INDEX_HASHES` (about 3.6 GB) with a readable error.

- [ ] **Step 1: Write the failing tests**

Create `tests/fingerprint/test_index.py`:

```python
"""Tests for the in-memory library index."""

from pathlib import Path

import numpy as np
import pytest

from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint import index as index_module
from ai_crate_digger.fingerprint.index import (
    LibraryIndex,
    get_library_index,
    invalidate_index_cache,
)
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION
from ai_crate_digger.storage import Database


def _arr(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.uint32)


def _times(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.int32)


def _index() -> LibraryIndex:
    return LibraryIndex.build(
        [
            ("aaa", _arr(5, 9, 5), _times(10, 20, 30)),
            ("bbb", _arr(9, 7), _times(100, 200)),
        ]
    )


def test_lookup_returns_every_track_with_the_hash() -> None:
    matches = _index().lookup(_arr(9), max_matches=10)
    assert sorted(zip(matches.track_idx.tolist(), matches.track_t.tolist(), strict=True)) == [
        (0, 20),
        (1, 100),
    ]
    assert matches.query_idx.tolist() == [0, 0]


def test_lookup_keeps_query_positions() -> None:
    matches = _index().lookup(_arr(7, 5), max_matches=10)
    pairs = sorted(zip(matches.query_idx.tolist(), matches.track_t.tolist(), strict=True))
    assert pairs == [(0, 200), (1, 10), (1, 30)]


def test_unknown_hash_matches_nothing() -> None:
    matches = _index().lookup(_arr(12345), max_matches=10)
    assert len(matches.query_idx) == 0


def test_max_matches_caps_popular_hashes() -> None:
    matches = _index().lookup(_arr(9), max_matches=1)
    assert len(matches.query_idx) == 1


def test_track_hashes_and_max_frames() -> None:
    index = _index()
    assert index.track_hashes == ["aaa", "bbb"]
    assert len(index) == 2
    assert index.max_track_frames == 200


def test_empty_index_is_empty_and_lookup_safe() -> None:
    index = LibraryIndex.build([])
    assert len(index) == 0
    assert len(index.lookup(_arr(1), max_matches=5).query_idx) == 0


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init()
    invalidate_index_cache()
    return database


def test_library_index_is_loaded_from_the_database(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5, 9), _times(10, 20), FINGERPRINT_VERSION)
    index = get_library_index(db)
    assert index.track_hashes == ["aaa"]
    assert index.lookup(_arr(9), max_matches=5).track_t.tolist() == [20]


def test_library_index_is_cached_until_the_fingerprint_count_changes(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5), _times(10), FINGERPRINT_VERSION)
    first = get_library_index(db)
    assert get_library_index(db) is first

    db.upsert_fingerprint("bbb", _arr(6), _times(10), FINGERPRINT_VERSION)
    second = get_library_index(db)
    assert second is not first
    assert len(second) == 2


def test_invalidate_forces_a_reload(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5), _times(10), FINGERPRINT_VERSION)
    first = get_library_index(db)
    invalidate_index_cache()
    assert get_library_index(db) is not first


def test_oversized_index_is_refused(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    db.upsert_fingerprint("aaa", _arr(1, 2, 3), _times(1, 2, 3), FINGERPRINT_VERSION)
    monkeypatch.setattr(index_module, "MAX_INDEX_HASHES", 2)
    with pytest.raises(FingerprintError, match="safety limit"):
        get_library_index(db)
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_index.py -q --no-cov
```

Expected: collection error, `No module named 'ai_crate_digger.fingerprint.index'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/fingerprint/index.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/fingerprint/test_index.py -q --no-cov
```

Expected: `10 passed`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/index.py \
  tests/fingerprint/test_index.py
git commit -m "feat: add in-memory library fingerprint index" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 6: Matcher

**Files:**
- Create: `src/ai_crate_digger/fingerprint/matcher.py`
- Test: `tests/fingerprint/test_matcher.py`

How it works:

1. `hypotheses()` lists `(speed, mode)` pairs: identity, plus each 1% step up to 8% in both `pitch` mode (frequencies scale with tempo) and `keylock` mode (frequencies unchanged).
2. For each hypothesis the mix's peaks are rescaled, hashed densely, and looked up. Each hit votes for `(5 s block, track, offset)` where offset is mix time minus track time in 4-frame bins. A genuine match is a spike at one offset.
3. "Support" is votes divided by the pairs that could have voted (anchors in the block times pairs per anchor). It is independent of block length and fan-out, and it drives the confidence band (high 0.12, medium 0.05, low 0.02, thresholds tunable via settings).
4. The best hypothesis per `(block, track)` wins; at most two tracks per block are kept so transitions show both. Consecutive blocks of the same track merge when the implied position inside the track advances at the matched speed. A one-block segment is kept only if its band is high. Spans of 10 s or more with no segment are reported as `unmatched`.

- [ ] **Step 1: Write the failing tests**

Create `tests/fingerprint/test_matcher.py`:

```python
"""Tests for mix identification using synthetic audio."""

import numpy as np
import pytest

from ai_crate_digger.fingerprint.hashing import hash_peaks
from ai_crate_digger.fingerprint.index import LibraryIndex
from ai_crate_digger.fingerprint.matcher import MatchParams, MixResult, hypotheses, identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks
from tests.fingerprint.synth import (
    SR,
    Audio,
    add_noise,
    make_track,
    place,
    stretch_keylock,
    stretch_pitch,
)

FP = FingerprintParams()
MP = MatchParams()
TRACK_SECONDS = 45


@pytest.fixture(scope="module")
def tracks() -> dict[str, Audio]:
    return {f"t{i}": make_track(i, TRACK_SECONDS) for i in range(6)}


@pytest.fixture(scope="module")
def index(tracks: dict[str, Audio]) -> LibraryIndex:
    items = []
    for name, audio in tracks.items():
        hs = hash_peaks(
            extract_peaks(audio, FP),
            FP,
            rank_min=FP.index_rank_min,
            rank_max=FP.index_rank_max,
        )
        items.append((name, hs.hashes, hs.anchor_t.astype(np.int32)))
    return LibraryIndex.build(items)


def _identify(index: LibraryIndex, mix: Audio) -> MixResult:
    return identify_mix(index, extract_peaks(mix, FP), FP, MP)


def test_hypotheses_cover_identity_and_both_modes() -> None:
    plan = hypotheses(MatchParams(speed_range=0.02, speed_step=0.01))
    assert (1.0, "keylock") in plan
    assert (1.02, "pitch") in plan
    assert (0.98, "keylock") in plan
    assert len(plan) == 1 + 2 * 2 * 2


def test_identifies_unshifted_track(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(tracks["t2"][: 30 * SR], 5, 45)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t2"]
    seg = result.segments[0]
    assert seg.confidence_band == "high"
    assert abs(seg.start_sec - 5) <= 5
    assert abs(seg.tempo_shift_pct) < 1.0


def test_identifies_pitch_shifted_track(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(stretch_pitch(tracks["t1"][: 40 * SR], 1.04), 0, 40)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t1"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(4.0, abs=1.0)
    assert result.segments[0].mode == "pitch"


def test_identifies_key_locked_tempo_change(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(stretch_keylock(tracks["t3"][: 40 * SR], 0.96), 0, 42)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t3"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(-4.0, abs=1.5)
    assert result.segments[0].mode == "keylock"


def test_survives_background_noise(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = add_noise(place(tracks["t4"][: 30 * SR], 0, 30), 0.05)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t4"]


def test_overlapping_transition_finds_both_tracks(
    index: LibraryIndex, tracks: dict[str, Audio]
) -> None:
    mix = place(tracks["t0"][: 30 * SR], 0, 60) + place(tracks["t5"][: 30 * SR], 25, 60)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t0", "t5"]
    assert result.segments[0].end_sec > result.segments[1].start_sec - 1


def test_unknown_audio_is_reported_as_unmatched(index: LibraryIndex) -> None:
    mix = make_track(9999, 40)
    result = _identify(index, mix)
    assert result.segments == []
    assert result.unmatched == [(0.0, pytest.approx(result.duration_sec))]


def test_gap_between_known_tracks_is_unmatched(
    index: LibraryIndex, tracks: dict[str, Audio]
) -> None:
    mix = (
        place(tracks["t0"][: 30 * SR], 0, 100)
        + place(make_track(9999, 30), 30, 100)
        + place(tracks["t1"][: 30 * SR], 60, 100)
    )
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t0", "t1"]
    assert any(a < 40 and b > 55 for a, b in result.unmatched)


def test_empty_index_marks_everything_unmatched() -> None:
    mix = make_track(1, 20)
    result = identify_mix(LibraryIndex.build([]), extract_peaks(mix, FP), FP, MP)
    assert result.segments == []
    assert len(result.unmatched) == 1


def test_progress_reaches_one(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    seen: list[float] = []
    mix = place(tracks["t2"][: 20 * SR], 0, 20)
    identify_mix(index, extract_peaks(mix, FP), FP, MP, on_progress=seen.append)
    assert seen == sorted(seen)
    assert seen[-1] == pytest.approx(1.0)
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_matcher.py -q --no-cov
```

Expected: collection error, `No module named 'ai_crate_digger.fingerprint.matcher'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/fingerprint/matcher.py`:

```python
"""Identify library tracks inside a DJ mix recording."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt

from ai_crate_digger.fingerprint.hashing import hash_peaks
from ai_crate_digger.fingerprint.index import LibraryIndex
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import Peaks

Band = Literal["high", "medium", "low"]
Mode = Literal["pitch", "keylock"]


@dataclass(frozen=True)
class MatchParams:
    """Tunable matching behaviour (query time only, no reindex needed)."""

    speed_range: float = 0.08
    speed_step: float = 0.01
    block_sec: float = 5.0
    offset_bin_frames: int = 4
    min_votes: int = 8
    max_tracks_per_block: int = 2
    high_support: float = 0.12
    medium_support: float = 0.05
    low_support: float = 0.02
    merge_tolerance_sec: float = 2.0
    max_gap_blocks: int = 1
    min_gap_sec: float = 10.0


@dataclass(frozen=True)
class MixSegment:
    """One contiguous stretch of the mix identified as a library track."""

    start_sec: float
    end_sec: float
    track_hash: str
    confidence: float
    confidence_band: Band
    tempo_shift_pct: float
    mode: Mode


@dataclass(frozen=True)
class MixResult:
    """Identified segments plus spans nothing matched."""

    duration_sec: float
    segments: list[MixSegment] = field(default_factory=list)
    unmatched: list[tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True)
class _Candidate:
    block: int
    track: int
    votes: int
    support: float
    speed: float
    mode: Mode
    offset_sec: float


def hypotheses(params: MatchParams) -> list[tuple[float, Mode]]:
    """Speed hypotheses: identity, plus each speed under pitch-follows and key-lock modes."""
    steps = int(round(params.speed_range / params.speed_step))
    result: list[tuple[float, Mode]] = [(1.0, "keylock")]
    for i in range(1, steps + 1):
        for sign in (-1, 1):
            speed = round(1.0 + sign * i * params.speed_step, 6)
            result.append((speed, "pitch"))
            result.append((speed, "keylock"))
    return result


def _band(support: float, params: MatchParams) -> Band | None:
    if support >= params.high_support:
        return "high"
    if support >= params.medium_support:
        return "medium"
    if support >= params.low_support:
        return "low"
    return None


def _votes_for_hypothesis(
    index: LibraryIndex,
    mix_peaks: Peaks,
    fp: FingerprintParams,
    params: MatchParams,
    speed: float,
    mode: Mode,
    block_frames: int,
    anchors_per_block: npt.NDArray[np.int64],
) -> list[_Candidate]:
    freq_scale = 1.0 / speed if mode == "pitch" else 1.0
    hs = hash_peaks(
        mix_peaks,
        fp,
        rank_min=1,
        rank_max=fp.query_rank_max,
        time_scale=speed,
        freq_scale=freq_scale,
    )
    if len(hs.hashes) == 0:
        return []
    matches = index.lookup(hs.hashes, fp.max_matches_per_hash)
    if len(matches.query_idx) == 0:
        return []

    offset = hs.anchor_t[matches.query_idx] - matches.track_t.astype(np.int64)
    pad = index.max_track_frames
    bin_width = params.offset_bin_frames
    obin = (offset + pad) // bin_width
    block = hs.source_t[matches.query_idx] // block_frames
    n_obins = int(obin.max()) + 1
    n_tracks = len(index)
    key = (block * n_tracks + matches.track_idx.astype(np.int64)) * n_obins + obin
    uniq, counts = np.unique(key, return_counts=True)
    keep = counts >= params.min_votes
    uniq, counts = uniq[keep], counts[keep]
    if len(uniq) == 0:
        return []

    obin_k = uniq % n_obins
    rest = uniq // n_obins
    track_k = rest % n_tracks
    block_k = rest // n_tracks
    pairs = fp.pairs_per_anchor
    candidates: list[_Candidate] = []
    for b, tr, ob, votes in zip(block_k, track_k, obin_k, counts, strict=True):
        anchors = int(anchors_per_block[b]) if b < len(anchors_per_block) else 0
        support = float(votes) / max(1, anchors * pairs)
        if _band(support, params) is None:
            continue
        offset_frames = ob * bin_width - pad + bin_width / 2
        candidates.append(
            _Candidate(
                block=int(b),
                track=int(tr),
                votes=int(votes),
                support=support,
                speed=speed,
                mode=mode,
                offset_sec=float(offset_frames / fp.frame_rate),
            )
        )
    return candidates


def identify_mix(
    index: LibraryIndex,
    mix_peaks: Peaks,
    fp: FingerprintParams,
    params: MatchParams,
    on_progress: Callable[[float], None] | None = None,
) -> MixResult:
    """Match a mix's spectrogram peaks against the library index."""
    duration = mix_peaks.n_frames / fp.frame_rate
    if len(index) == 0 or len(mix_peaks.t) == 0:
        return MixResult(duration_sec=duration, unmatched=[(0.0, duration)] if duration else [])

    block_frames = int(round(params.block_sec * fp.frame_rate))
    n_blocks = mix_peaks.n_frames // block_frames + 1
    anchors_per_block = np.bincount(mix_peaks.t // block_frames, minlength=n_blocks)

    best: dict[tuple[int, int], _Candidate] = {}
    plan = hypotheses(params)
    for i, (speed, mode) in enumerate(plan):
        for cand in _votes_for_hypothesis(
            index, mix_peaks, fp, params, speed, mode, block_frames, anchors_per_block
        ):
            key = (cand.block, cand.track)
            if key not in best or cand.votes > best[key].votes:
                best[key] = cand
        if on_progress:
            on_progress((i + 1) / len(plan))

    per_block: dict[int, list[_Candidate]] = {}
    for cand in best.values():
        per_block.setdefault(cand.block, []).append(cand)
    chosen: list[_Candidate] = []
    for cands in per_block.values():
        cands.sort(key=lambda c: c.votes, reverse=True)
        chosen.extend(cands[: params.max_tracks_per_block])

    segments = _merge(chosen, index, params, fp, duration)
    return MixResult(
        duration_sec=duration, segments=segments, unmatched=_gaps(segments, duration, params)
    )


def _merge(
    chosen: list[_Candidate],
    index: LibraryIndex,
    params: MatchParams,
    fp: FingerprintParams,
    duration: float,
) -> list[MixSegment]:
    by_track: dict[int, list[_Candidate]] = {}
    for cand in chosen:
        by_track.setdefault(cand.track, []).append(cand)

    segments: list[MixSegment] = []
    for track, cands in by_track.items():
        cands.sort(key=lambda c: c.block)
        run: list[_Candidate] = []
        for cand in cands:
            if run and not _continues(run[-1], cand, params):
                _flush(run, track, index, params, duration, segments)
                run = []
            run.append(cand)
        _flush(run, track, index, params, duration, segments)
    segments.sort(key=lambda s: s.start_sec)
    return segments


def _position(cand: _Candidate, params: MatchParams) -> float:
    """Where in the track the mix is, at the start of this candidate's block."""
    return cand.block * params.block_sec * cand.speed - cand.offset_sec


def _continues(prev: _Candidate, cand: _Candidate, params: MatchParams) -> bool:
    gap = cand.block - prev.block
    if gap < 1 or gap > params.max_gap_blocks + 1:
        return False
    expected = _position(prev, params) + gap * params.block_sec * prev.speed
    return abs(_position(cand, params) - expected) <= params.merge_tolerance_sec


def _flush(
    run: list[_Candidate],
    track: int,
    index: LibraryIndex,
    params: MatchParams,
    duration: float,
    out: list[MixSegment],
) -> None:
    if not run:
        return
    support = float(np.mean([c.support for c in run]))
    band = _band(support, params)
    if band is None or (len(run) < 2 and band != "high"):
        return
    speed = float(np.mean([c.speed for c in run]))
    pitch_votes = sum(c.votes for c in run if c.mode == "pitch")
    key_votes = sum(c.votes for c in run if c.mode == "keylock")
    out.append(
        MixSegment(
            start_sec=run[0].block * params.block_sec,
            end_sec=min(duration, (run[-1].block + 1) * params.block_sec),
            track_hash=index.track_hashes[track],
            confidence=round(support, 4),
            confidence_band=band,
            tempo_shift_pct=round((speed - 1.0) * 100.0, 2),
            mode="pitch" if pitch_votes > key_votes else "keylock",
        )
    )


def _gaps(
    segments: list[MixSegment], duration: float, params: MatchParams
) -> list[tuple[float, float]]:
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for seg in sorted(segments, key=lambda s: s.start_sec):
        if seg.start_sec - cursor >= params.min_gap_sec:
            gaps.append((cursor, seg.start_sec))
        cursor = max(cursor, seg.end_sec)
    if duration - cursor >= params.min_gap_sec:
        gaps.append((cursor, duration))
    return gaps
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/fingerprint -q --no-cov
```

Expected: `33 passed` in a few seconds.

If one of the synthetic tests is flaky or fails for you, do not loosen the assertion first. Print the segments (`result.segments`) and compare with the expectation; the usual cause is a transcription slip in `matcher.py`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/matcher.py \
  tests/fingerprint/test_matcher.py
git commit -m "feat: add DJ mix matcher with tempo and key-lock hypotheses" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 7: Library indexer

**Files:**
- Create: `src/ai_crate_digger/fingerprint/indexer.py`
- Create: `tests/fingerprint/library.py` (test helper)
- Modify: `tests/conftest.py` (adds the `library` fixture)
- Test: `tests/fingerprint/test_indexer.py`

How it works: `index_library` fingerprints every track without a current-version fingerprint. `workers=1` runs in-process (tests, small libraries); otherwise a spawn-context `ProcessPoolExecutor` is used with the same BLAS-thread initialiser as the analysis pool (it avoids a segfault on Apple Silicon). A track that cannot be decoded is recorded in the report and does not stop the run; a crashed pool stops the run, reports the unfinished tracks as failed, and a re-run resumes because finished tracks are skipped.

- [ ] **Step 1: Add the shared test helpers**

Create `tests/fingerprint/library.py`:

```python
"""Helpers for tests that need a small library of synthetic tracks on disk."""

from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from ai_crate_digger.core.config import Settings
from ai_crate_digger.core.models import Track
from ai_crate_digger.storage import Database
from tests.fingerprint.synth import SR, Audio, make_track


@dataclass
class Library:
    """A catalogue database plus the audio behind each track."""

    db: Database
    settings: Settings
    audio: dict[str, Audio]  # file_hash -> audio
    root: Path


def write_wav(path: Path, audio: Audio) -> Path:
    """Write ``audio`` as a mono WAV at the fingerprint sample rate."""
    sf.write(str(path), audio, SR)
    return path


def build_library(root: Path, n_tracks: int = 4, seconds: float = 40) -> Library:
    """Create ``n_tracks`` WAV files and a catalogue database describing them."""
    db_path = root / "catalog.db"
    db = Database(db_path)
    db.init()
    music = root / "music"
    music.mkdir()
    audio: dict[str, Audio] = {}
    for i in range(n_tracks):
        samples = make_track(i, seconds)
        path = write_wav(music / f"track{i}.wav", samples)
        db.upsert_track(
            Track(file_path=path, file_hash=f"hash{i}", title=f"Title{i}", artist=f"Artist{i}")
        )
        audio[f"hash{i}"] = samples
    settings = Settings(db_path=db_path, inbox_path=root / "inbox", max_workers=1)
    return Library(db=db, settings=settings, audio=audio, root=root)
```

`tests/conftest.py`:

```diff
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -9,6 +9,7 @@
 import pytest
 
 from ai_crate_digger.core.models import Track
+from tests.fingerprint.library import Library, build_library
 
 
 @pytest.fixture
@@ -55,3 +56,11 @@
         energy=0.8,
         danceability=0.7,
     )
+
+
+@pytest.fixture
+def library(tmp_path: Path) -> Iterator[Library]:
+    """Small library of synthetic WAV tracks with a catalogue database."""
+    lib = build_library(tmp_path)
+    yield lib
+    lib.db.close()
```

- [ ] **Step 2: Write the failing tests**

Create `tests/fingerprint/test_indexer.py`:

```python
"""Tests for library fingerprinting."""

from pathlib import Path

import numpy as np

from ai_crate_digger.core.models import Track
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.indexer import fingerprint_audio, index_library
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION
from tests.fingerprint.library import Library
from tests.fingerprint.synth import make_track


def test_fingerprint_audio_returns_parallel_arrays() -> None:
    hashes, times = fingerprint_audio(make_track(1, 20))
    assert len(hashes) == len(times) > 0
    assert hashes.dtype == np.uint32
    assert times.dtype == np.int32


def test_indexes_every_track_then_skips_them(library: Library) -> None:
    first = index_library(library.db, workers=1)
    assert (first.indexed, first.skipped, first.failed) == (4, 0, [])
    assert library.db.count_fingerprints(FINGERPRINT_VERSION) == 4

    second = index_library(library.db, workers=1)
    assert (second.indexed, second.skipped) == (0, 4)


def test_force_reindexes_everything(library: Library) -> None:
    index_library(library.db, workers=1)
    report = index_library(library.db, workers=1, force=True)
    assert report.indexed == 4
    assert report.skipped == 0


def test_reports_progress(library: Library) -> None:
    seen: list[tuple[int, int]] = []
    index_library(library.db, workers=1, on_progress=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_unreadable_track_is_reported_and_others_continue(library: Library) -> None:
    library.db.upsert_track(Track(file_path=Path("/nope/missing.mp3"), file_hash="ghost"))
    report = index_library(library.db, workers=1)
    assert report.indexed == 4
    assert [path for path, _ in report.failed] == ["/nope/missing.mp3"]


def test_worker_pool_indexes_tracks(library: Library) -> None:
    report = index_library(library.db, workers=2)
    assert report.indexed == 4
    assert library.db.count_fingerprints(FINGERPRINT_VERSION) == 4


def test_reindexing_invalidates_the_cached_library_index(library: Library) -> None:
    index_library(library.db, workers=1)
    first = get_library_index(library.db)
    assert len(first) == 4

    index_library(library.db, workers=1, force=True)
    assert get_library_index(library.db) is not first
```

- [ ] **Step 3: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_indexer.py -q --no-cov
```

Expected: collection error, `No module named 'ai_crate_digger.fingerprint.indexer'`.

- [ ] **Step 4: Implement**

Create `src/ai_crate_digger/fingerprint/indexer.py`:

```python
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
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/fingerprint/test_indexer.py -q --no-cov
```

Expected: `7 passed`. The worker-pool test spawns processes and takes a few seconds.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/indexer.py \
  tests/fingerprint/library.py \
  tests/fingerprint/test_indexer.py \
  tests/conftest.py
git commit -m "feat: fingerprint library tracks with an optional process pool" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 8: Inbox lookup and result reporting

**Files:**
- Create: `src/ai_crate_digger/fingerprint/inbox.py`
- Create: `src/ai_crate_digger/fingerprint/report.py`
- Test: `tests/fingerprint/test_inbox.py`, `tests/fingerprint/test_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/fingerprint/test_inbox.py`:

```python
"""Tests for locating mix recordings."""

import os
from pathlib import Path

import pytest

from ai_crate_digger.fingerprint.inbox import resolve_mix_path


def _touch(path: Path, mtime: int) -> Path:
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return path


def test_explicit_path_is_used(tmp_path: Path) -> None:
    mix = _touch(tmp_path / "set.mp3", 100)
    assert resolve_mix_path(str(mix), tmp_path / "inbox") == mix


def test_missing_explicit_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Mix file not found"):
        resolve_mix_path(str(tmp_path / "nope.mp3"), tmp_path)


@pytest.mark.parametrize("value", [None, "latest", "LATEST"])
def test_latest_picks_the_newest_audio_file(tmp_path: Path, value: str | None) -> None:
    _touch(tmp_path / "old.mp3", 100)
    newest = _touch(tmp_path / "new.WAV", 300)
    _touch(tmp_path / "notes.txt", 500)
    assert resolve_mix_path(value, tmp_path) == newest


def test_latest_needs_an_inbox_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Inbox folder not found"):
        resolve_mix_path("latest", tmp_path / "missing")


def test_latest_needs_at_least_one_audio_file(tmp_path: Path) -> None:
    _touch(tmp_path / "notes.txt", 100)
    with pytest.raises(FileNotFoundError, match="No audio files"):
        resolve_mix_path(None, tmp_path)
```

Create `tests/fingerprint/test_report.py`:

```python
"""Tests for result summaries and playlist ordering."""

from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.fingerprint.matcher import Band, MixResult, MixSegment
from ai_crate_digger.fingerprint.report import describe_result, format_time, playlist_hashes
from ai_crate_digger.storage import Database


def _segment(start: float, end: float, track: str, band: Band) -> MixSegment:
    return MixSegment(
        start_sec=start,
        end_sec=end,
        track_hash=track,
        confidence=0.2,
        confidence_band=band,
        tempo_shift_pct=1.5,
        mode="pitch",
    )


RESULT = MixResult(
    duration_sec=3700.0,
    segments=[
        _segment(300, 500, "b", "low"),
        _segment(0, 200, "a", "high"),
        _segment(600, 800, "a", "medium"),
    ],
    unmatched=[(200.0, 300.0)],
)


@pytest.mark.parametrize(
    ("seconds", "expected"), [(0, "0:00"), (65, "1:05"), (3599, "59:59"), (3725, "1:02:05")]
)
def test_format_time(seconds: float, expected: str) -> None:
    assert format_time(seconds) == expected


def test_playlist_hashes_follow_mix_order_and_dedupe() -> None:
    assert playlist_hashes(RESULT, "low") == ["a", "b"]
    assert playlist_hashes(RESULT, "low", dedupe=False) == ["a", "b", "a"]


def test_playlist_hashes_respect_confidence_floor() -> None:
    assert playlist_hashes(RESULT, "medium") == ["a"]
    assert playlist_hashes(RESULT, "high") == ["a"]


def test_describe_result_names_tracks_and_hides_weak_matches(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    db.init()
    db.upsert_track(
        Track(file_path=Path("/m/a.mp3"), file_hash="a", artist="Artist A", title="Title A")
    )
    summary = describe_result(RESULT, db, "medium")
    db.close()

    assert summary["duration"] == "1:01:40"
    assert summary["hidden_below_min_confidence"] == 1
    first = summary["segments"][0]
    assert (first["start"], first["end"]) == ("0:00", "3:20")
    assert (first["artist"], first["title"]) == ("Artist A", "Title A")
    assert summary["unmatched"] == [
        {"start": "3:20", "end": "5:00", "start_sec": 200.0, "end_sec": 300.0}
    ]
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_inbox.py tests/fingerprint/test_report.py -q --no-cov
```

Expected: two collection errors, `No module named 'ai_crate_digger.fingerprint.inbox'` and `...report'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/fingerprint/inbox.py`:

```python
"""Locate mix recordings on disk."""

from pathlib import Path

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".aiff", ".aif"})


def resolve_mix_path(path: str | None, inbox: Path) -> Path:
    """Resolve a mix file from an explicit path, or the newest file in ``inbox``.

    Args:
        path: File path, or None / "latest" to use the newest recording in ``inbox``
        inbox: Folder where recordings are dropped

    Raises:
        FileNotFoundError: If the file, folder or any audio file cannot be found
    """
    if path and path.lower() != "latest":
        resolved = Path(path).expanduser()
        if not resolved.is_file():
            msg = f"Mix file not found: {resolved}"
            raise FileNotFoundError(msg)
        return resolved

    if not inbox.is_dir():
        msg = f"Inbox folder not found: {inbox}"
        raise FileNotFoundError(msg)
    candidates = [
        p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ]
    if not candidates:
        msg = f"No audio files in inbox folder: {inbox}"
        raise FileNotFoundError(msg)
    return max(candidates, key=lambda p: p.stat().st_mtime)
```

Create `src/ai_crate_digger/fingerprint/report.py`:

```python
"""Turn match results into JSON-friendly summaries and playlist orderings."""

from typing import Any

from ai_crate_digger.fingerprint.matcher import Band, MixResult
from ai_crate_digger.storage import Database

BAND_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def format_time(seconds: float) -> str:
    """Format seconds as ``m:ss`` or ``h:mm:ss``."""
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def describe_result(result: MixResult, db: Database, min_confidence: Band) -> dict[str, Any]:
    """Describe a mix result with track names, hiding matches below ``min_confidence``."""
    floor = BAND_RANK[min_confidence]
    shown: list[dict[str, Any]] = []
    for seg in result.segments:
        if BAND_RANK[seg.confidence_band] < floor:
            continue
        track = db.get_track_by_hash(seg.track_hash)
        shown.append(
            {
                "start": format_time(seg.start_sec),
                "end": format_time(seg.end_sec),
                "start_sec": seg.start_sec,
                "end_sec": seg.end_sec,
                "hash": seg.track_hash,
                "artist": track.artist if track else None,
                "title": track.title if track else None,
                "confidence": seg.confidence,
                "confidence_band": seg.confidence_band,
                "tempo_shift_pct": seg.tempo_shift_pct,
                "mode": seg.mode,
            }
        )
    return {
        "duration": format_time(result.duration_sec),
        "duration_sec": result.duration_sec,
        "segments": shown,
        "hidden_below_min_confidence": len(result.segments) - len(shown),
        "unmatched": [
            {
                "start": format_time(a),
                "end": format_time(b),
                "start_sec": a,
                "end_sec": b,
            }
            for a, b in result.unmatched
        ],
    }


def playlist_hashes(result: MixResult, min_confidence: Band, *, dedupe: bool = True) -> list[str]:
    """Track hashes in mix order at or above ``min_confidence``."""
    floor = BAND_RANK[min_confidence]
    hashes: list[str] = []
    for seg in sorted(result.segments, key=lambda s: s.start_sec):
        if BAND_RANK[seg.confidence_band] < floor:
            continue
        if dedupe and seg.track_hash in hashes:
            continue
        hashes.append(seg.track_hash)
    return hashes
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/fingerprint/test_inbox.py tests/fingerprint/test_report.py -q --no-cov
```

Expected: `14 passed`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/inbox.py \
  src/ai_crate_digger/fingerprint/report.py \
  tests/fingerprint/test_inbox.py \
  tests/fingerprint/test_report.py
git commit -m "feat: resolve mix recordings and describe match results" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 9: Background jobs and file identification

**Files:**
- Create: `src/ai_crate_digger/fingerprint/jobs.py`
- Create: `src/ai_crate_digger/fingerprint/identify.py`
- Test: `tests/fingerprint/test_jobs.py`, `tests/fingerprint/test_identify.py`

Why jobs: an hour-long mix takes minutes and the MCP client's tool-call timeout is unknown, so `identify_mix` and `index_fingerprints` return a `job_id` immediately and the work runs on one worker thread. The registry is in-memory: a restart of the MCP server forgets jobs (acceptable, they can be re-run).

`identify_mix_file` is the one entry point shared by jobs, the CLI and the benchmark. It turns every failure the user can fix (unreadable file, recording under 30 s, empty index) into a `FingerprintError` with an actionable message.

- [ ] **Step 1: Write the failing tests**

Create `tests/fingerprint/test_jobs.py`:

```python
"""Tests for the background job registry."""

import time

import pytest

from ai_crate_digger.fingerprint.jobs import Job, JobRegistry, ProgressFn
from ai_crate_digger.fingerprint.matcher import MixResult


def _wait(registry: JobRegistry, job_id: str) -> Job:
    deadline = time.time() + 10
    while time.time() < deadline:
        job = registry.get(job_id)
        assert job is not None
        if job.status in ("done", "failed"):
            return job
        time.sleep(0.01)
    pytest.fail("job did not finish")


def test_successful_job_stores_result_and_full_progress() -> None:
    registry = JobRegistry()
    result = MixResult(duration_sec=1.0)

    def work(progress: ProgressFn) -> MixResult:
        progress(0.5)
        return result

    job = registry.submit("mix", "set.mp3", work)
    finished = _wait(registry, job.job_id)
    assert finished.status == "done"
    assert finished.result is result
    assert finished.progress == 1.0
    assert finished.label == "set.mp3"


def test_failing_job_records_the_error() -> None:
    registry = JobRegistry()

    def work(progress: ProgressFn) -> MixResult:
        msg = "boom"
        raise RuntimeError(msg)

    finished = _wait(registry, registry.submit("index", "library", work).job_id)
    assert finished.status == "failed"
    assert finished.error == "boom"
    assert finished.result is None


def test_progress_is_clamped() -> None:
    registry = JobRegistry()
    reporters: list[ProgressFn] = []

    def work(progress: ProgressFn) -> MixResult:
        reporters.append(progress)
        return MixResult(duration_sec=0.0)

    job = _wait(registry, registry.submit("mix", "x", work).job_id)
    reporters[0](7.0)
    assert job.progress == 1.0
    reporters[0](-3.0)
    assert job.progress == 0.0


def test_unknown_job_is_none() -> None:
    assert JobRegistry().get("nope") is None
```

Create `tests/fingerprint/test_identify.py`:

```python
"""End-to-end tests: audio files in, identified tracks out."""

from pathlib import Path

import pytest

from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.indexer import index_library
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, make_track, place, stretch_pitch


def test_identifies_a_pitched_track_from_a_wav_file(library: Library) -> None:
    index_library(library.db, workers=1)
    mix = place(stretch_pitch(library.audio["hash2"][: 35 * SR], 1.03), 4, 40)
    path = write_wav(library.root / "mix.wav", mix)

    result = identify_mix_file(path, library.settings)

    assert [s.track_hash for s in result.segments] == ["hash2"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(3.0, abs=1.0)


def test_short_recordings_are_rejected(library: Library) -> None:
    index_library(library.db, workers=1)
    path = write_wav(library.root / "short.wav", make_track(1, 10))
    with pytest.raises(FingerprintError, match="shorter than"):
        identify_mix_file(path, library.settings)


def test_empty_index_asks_for_indexing_first(library: Library) -> None:
    path = write_wav(library.root / "mix.wav", make_track(1, 40))
    with pytest.raises(FingerprintError, match="index_fingerprints"):
        identify_mix_file(path, library.settings)


def test_unreadable_file_is_a_clear_error(library: Library) -> None:
    path = Path(library.root / "broken.mp3")
    path.write_bytes(b"this is not audio")
    with pytest.raises(FingerprintError, match="Could not read audio file"):
        identify_mix_file(path, library.settings)
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/fingerprint/test_jobs.py tests/fingerprint/test_identify.py -q --no-cov
```

Expected: two collection errors, `No module named 'ai_crate_digger.fingerprint.jobs'` and `...identify'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/fingerprint/jobs.py`:

```python
"""Background jobs for work that outlasts a single MCP tool call."""

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal

from ai_crate_digger.fingerprint.indexer import IndexReport
from ai_crate_digger.fingerprint.matcher import MixResult

logger = logging.getLogger(__name__)

JobKind = Literal["index", "mix"]
JobStatus = Literal["queued", "running", "done", "failed"]
ProgressFn = Callable[[float], None]
Work = Callable[[ProgressFn], MixResult | IndexReport]


@dataclass
class Job:
    """State of one background job."""

    job_id: str
    kind: JobKind
    label: str
    status: JobStatus = "queued"
    progress: float = 0.0
    result: MixResult | IndexReport | None = None
    error: str | None = None


class JobRegistry:
    """Runs jobs one at a time on a worker thread and remembers their state."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crate-job")

    def submit(self, kind: JobKind, label: str, work: Work) -> Job:
        """Queue ``work`` and return its job immediately."""
        job = Job(job_id=uuid.uuid4().hex[:8], kind=kind, label=label)
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> Job | None:
        """Look up a job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job: Job, work: Work) -> None:
        job.status = "running"

        def progress(fraction: float) -> None:
            job.progress = max(0.0, min(1.0, fraction))

        try:
            job.result = work(progress)
        except Exception as exc:
            logger.exception("Job %s failed", job.job_id)
            job.error = str(exc)
            job.status = "failed"
        else:
            job.progress = 1.0
            job.status = "done"


_registry = JobRegistry()


def get_job_registry() -> JobRegistry:
    """The process-wide job registry."""
    return _registry
```

Create `src/ai_crate_digger/fingerprint/identify.py`:

```python
"""Identify tracks in a mix recording against the library index."""

import logging
from collections.abc import Callable
from pathlib import Path

from ai_crate_digger.core.config import Settings
from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.matcher import MatchParams, MixResult, identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks, load_audio
from ai_crate_digger.storage import Database

logger = logging.getLogger(__name__)


def match_params_from_settings(settings: Settings) -> MatchParams:
    """Build matcher parameters from application settings."""
    return MatchParams(
        speed_range=settings.mix_speed_range,
        speed_step=settings.mix_speed_step,
        high_support=settings.mix_high_support,
        medium_support=settings.mix_medium_support,
        low_support=settings.mix_low_support,
    )


def identify_mix_file(
    path: Path,
    settings: Settings,
    on_progress: Callable[[float], None] | None = None,
) -> MixResult:
    """Decode a mix recording and match it against the library.

    Raises:
        FingerprintError: If the file cannot be read, is too short, or the index is empty
    """
    params = FingerprintParams()
    try:
        audio = load_audio(path, params.sample_rate)
    except Exception as exc:
        msg = f"Could not read audio file {path}: {exc}"
        raise FingerprintError(msg) from exc

    seconds = len(audio) / params.sample_rate
    if seconds < settings.mix_min_seconds:
        msg = (
            f"Recording is {seconds:.0f}s long. Mixes shorter than "
            f"{settings.mix_min_seconds:.0f}s are not supported."
        )
        raise FingerprintError(msg)

    peaks = extract_peaks(audio, params)
    del audio

    db = Database(settings.db_path)
    db.init()
    try:
        index = get_library_index(db)
    finally:
        db.close()
    if len(index) == 0:
        msg = "The fingerprint index is empty. Run index_fingerprints first."
        raise FingerprintError(msg)

    logger.info("Matching %s (%.0fs) against %d tracks", path.name, seconds, len(index))
    return identify_mix(index, peaks, params, match_params_from_settings(settings), on_progress)
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/fingerprint -q --no-cov
```

Expected: `62 passed`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/fingerprint/jobs.py \
  src/ai_crate_digger/fingerprint/identify.py \
  tests/fingerprint/test_jobs.py \
  tests/fingerprint/test_identify.py
git commit -m "feat: add background jobs and mix file identification" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 10: MCP tools

**Files:**
- Create: `src/ai_crate_digger/mcp/mix_tools.py`
- Modify: `src/ai_crate_digger/mcp/tools.py`
- Test: `tests/mcp/test_mix_tools.py`

The four tools live in their own module because `tools.py` is already over 1,200 lines. `tools.py` only appends the definitions and dispatches by name; `_build_playlist` is passed in as a callable to avoid a circular import and so playlist export reuses the existing code (Rekordbox XML and M3U) unchanged.

- [ ] **Step 1: Write the failing tests**

Create `tests/mcp/test_mix_tools.py`:

```python
"""Tests for the mix identification MCP tools."""

import json
import time
from typing import Any

import pytest

from ai_crate_digger.mcp.mix_tools import MIX_TOOL_NAMES, call_mix_tool, mix_tool_definitions
from ai_crate_digger.mcp.tools import _build_playlist
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, make_track, place, stretch_pitch


async def _call(library: Library, name: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await call_mix_tool(name, library.db, library.settings, args, _build_playlist)
    payload: dict[str, Any] = json.loads(result[0].text)
    return payload


async def _wait_done(library: Library, job_id: str) -> dict[str, Any]:
    deadline = time.time() + 60
    while time.time() < deadline:
        status = await _call(library, "get_job_status", {"job_id": job_id})
        if status["status"] in ("done", "failed"):
            return status
        time.sleep(0.05)
    pytest.fail("job did not finish")


def test_tool_definitions_match_dispatch_names() -> None:
    assert {tool.name for tool in mix_tool_definitions()} == set(MIX_TOOL_NAMES)


async def test_full_flow_from_indexing_to_playlist(library: Library) -> None:
    started = await _call(library, "index_fingerprints", {})
    indexed = await _wait_done(library, started["job_id"])
    assert indexed["report"]["indexed"] == 4

    mix = place(library.audio["hash1"][: 30 * SR], 0, 70) + place(
        stretch_pitch(library.audio["hash3"][: 30 * SR], 1.02), 35, 70
    )
    mix_path = write_wav(library.root / "friday.wav", mix)
    started = await _call(library, "identify_mix", {"path": str(mix_path)})
    assert started["success"] is True

    status = await _wait_done(library, started["job_id"])
    assert status["status"] == "done"
    assert [(s["hash"], s["artist"]) for s in status["segments"]] == [
        ("hash1", "Artist1"),
        ("hash3", "Artist3"),
    ]
    assert status["unmatched"] == []

    output = library.root / "friday.m3u"
    built = await call_mix_tool(
        "build_playlist_from_mix",
        library.db,
        library.settings,
        {"job_id": started["job_id"], "name": "Friday", "output_path": str(output)},
        _build_playlist,
    )
    assert json.loads(built[0].text)["success"] is True
    text = output.read_text()
    assert text.index("track1.wav") < text.index("track3.wav")


async def test_identify_latest_uses_the_inbox(library: Library) -> None:
    await _wait_done(library, (await _call(library, "index_fingerprints", {}))["job_id"])
    inbox = library.settings.inbox_path
    inbox.mkdir()
    write_wav(inbox / "recording.wav", place(library.audio["hash0"][: 30 * SR], 0, 32))

    started = await _call(library, "identify_mix", {"path": "latest"})
    assert started["path"].endswith("recording.wav")
    status = await _wait_done(library, started["job_id"])
    assert [s["hash"] for s in status["segments"]] == ["hash0"]


async def test_failed_job_reports_its_error(library: Library) -> None:
    path = write_wav(library.root / "mix.wav", make_track(1, 40))
    started = await _call(library, "identify_mix", {"path": str(path)})
    status = await _wait_done(library, started["job_id"])
    assert status["status"] == "failed"
    assert "index_fingerprints" in status["error"]


async def test_missing_file_is_an_immediate_error(library: Library) -> None:
    result = await _call(library, "identify_mix", {"path": str(library.root / "nope.mp3")})
    assert result["success"] is False
    assert "not found" in result["error"]


async def test_unknown_job_and_bad_confidence_are_errors(library: Library) -> None:
    unknown = await _call(library, "get_job_status", {"job_id": "nope"})
    assert unknown["success"] is False

    started = await _call(library, "index_fingerprints", {})
    bad = await _call(
        library, "get_job_status", {"job_id": started["job_id"], "min_confidence": "great"}
    )
    assert bad["success"] is False
    await _wait_done(library, started["job_id"])


async def test_build_playlist_needs_a_finished_mix_job(library: Library) -> None:
    started = await _call(library, "index_fingerprints", {})
    result = await _call(
        library, "build_playlist_from_mix", {"job_id": started["job_id"], "name": "x"}
    )
    assert result["success"] is False
    await _wait_done(library, started["job_id"])


async def test_server_lists_and_routes_the_mix_tools(
    library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp import types
    from mcp.server import Server

    from ai_crate_digger.core.config import get_settings
    from ai_crate_digger.mcp.tools import register_tools

    monkeypatch.setenv("CRATE_DB_PATH", str(library.settings.db_path))
    monkeypatch.setenv("CRATE_MAX_WORKERS", "1")
    get_settings.cache_clear()
    try:
        server = Server("test")
        register_tools(server)

        listed = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        assert isinstance(listed.root, types.ListToolsResult)
        names = {tool.name for tool in listed.root.tools}
        assert names >= MIX_TOOL_NAMES

        called = await server.request_handlers[types.CallToolRequest](
            types.CallToolRequest(
                method="tools/call",
                params=types.CallToolRequestParams(
                    name="get_job_status", arguments={"job_id": "nope"}
                ),
            )
        )
        assert isinstance(called.root, types.CallToolResult)
        content = called.root.content[0]
        assert isinstance(content, types.TextContent)
        assert "Unknown job_id" in content.text
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/mcp/test_mix_tools.py -q --no-cov
```

Expected: collection error, `No module named 'ai_crate_digger.mcp.mix_tools'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/mcp/mix_tools.py`:

```python
"""MCP tools for identifying tracks in recorded DJ mixes."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent, Tool

from ai_crate_digger.core.config import Settings
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.inbox import resolve_mix_path
from ai_crate_digger.fingerprint.indexer import IndexReport, index_library
from ai_crate_digger.fingerprint.jobs import ProgressFn, get_job_registry
from ai_crate_digger.fingerprint.matcher import MixResult
from ai_crate_digger.fingerprint.report import BAND_RANK, describe_result, playlist_hashes
from ai_crate_digger.storage import Database

MIX_TOOL_NAMES = frozenset(
    {"index_fingerprints", "identify_mix", "get_job_status", "build_playlist_from_mix"}
)

BuildPlaylist = Callable[[Database, dict[str, Any]], Awaitable[list[TextContent]]]

_CONFIDENCE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["low", "medium", "high"],
    "default": "medium",
    "description": "Hide matches below this confidence",
}


def mix_tool_definitions() -> list[Tool]:
    """Tool definitions for mix identification."""
    return [
        Tool(
            name="index_fingerprints",
            description=(
                "Fingerprint library tracks so mixes can be matched against them. Only "
                "tracks without a fingerprint are processed unless force is set. Runs in the "
                "background and returns a job_id; poll get_job_status for progress."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Re-fingerprint every track, not just new ones",
                    },
                },
            },
        ),
        Tool(
            name="identify_mix",
            description=(
                "Identify which library tracks were played in a recorded DJ mix and when. "
                "Takes a local file path, or 'latest' for the newest recording in the inbox "
                "folder. Runs in the background and returns a job_id; poll get_job_status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "default": "latest",
                        "description": "Path to the mix recording, or 'latest'",
                    },
                },
            },
        ),
        Tool(
            name="get_job_status",
            description=(
                "Get progress of an index_fingerprints or identify_mix job. When an "
                "identify_mix job is done, returns the timeline of identified tracks "
                "(start, end, artist, title, confidence, tempo shift) and unmatched spans."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "min_confidence": _CONFIDENCE_SCHEMA,
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="build_playlist_from_mix",
            description=(
                "Export the tracks found by a finished identify_mix job as a playlist, in "
                "the order they were played."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "name": {"type": "string", "description": "Playlist name"},
                    "min_confidence": _CONFIDENCE_SCHEMA,
                    "dedupe": {
                        "type": "boolean",
                        "default": True,
                        "description": "List a track once even if it was played twice",
                    },
                    "format": {"type": "string", "enum": ["m3u", "rekordbox"], "default": "m3u"},
                    "output_path": {"type": "string", "description": "Where to write the file"},
                },
                "required": ["job_id", "name"],
            },
        ),
    ]


def _json(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2))]


def _error(message: str) -> list[TextContent]:
    return _json({"success": False, "error": message})


def _index_fingerprints(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    force = bool(args.get("force", False))

    def work(progress: ProgressFn) -> IndexReport:
        db = Database(settings.db_path)
        db.init()
        try:
            return index_library(
                db,
                force=force,
                workers=settings.max_workers,
                on_progress=lambda done, total: progress(done / total if total else 1.0),
            )
        finally:
            db.close()

    job = get_job_registry().submit("index", "library", work)
    return _json(
        {"success": True, "job_id": job.job_id, "status": job.status, "next": "get_job_status"}
    )


def _identify_mix(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    try:
        path = resolve_mix_path(args.get("path"), settings.inbox_path)
    except FileNotFoundError as exc:
        return _error(str(exc))

    def work(progress: ProgressFn) -> MixResult:
        return identify_mix_file(path, settings, progress)

    job = get_job_registry().submit("mix", str(path), work)
    return _json(
        {
            "success": True,
            "job_id": job.job_id,
            "status": job.status,
            "path": str(path),
            "next": "get_job_status",
        }
    )


def _get_job_status(db: Database, args: dict[str, Any]) -> list[TextContent]:
    job = get_job_registry().get(args["job_id"])
    if job is None:
        return _error(f"Unknown job_id: {args['job_id']}")
    min_confidence = args.get("min_confidence", "medium")
    if min_confidence not in BAND_RANK:
        return _error(f"min_confidence must be one of {sorted(BAND_RANK)}")

    payload: dict[str, Any] = {
        "success": True,
        "job_id": job.job_id,
        "kind": job.kind,
        "label": job.label,
        "status": job.status,
        "progress": round(job.progress, 3),
    }
    if job.status == "failed":
        payload["error"] = job.error
    elif isinstance(job.result, MixResult):
        payload.update(describe_result(job.result, db, min_confidence))
    elif isinstance(job.result, IndexReport):
        payload["report"] = {
            "indexed": job.result.indexed,
            "skipped": job.result.skipped,
            "failed": [{"path": p, "error": e} for p, e in job.result.failed[:20]],
            "failed_total": len(job.result.failed),
        }
    return _json(payload)


async def _build_playlist_from_mix(
    db: Database, args: dict[str, Any], build_playlist: BuildPlaylist
) -> list[TextContent]:
    job = get_job_registry().get(args["job_id"])
    if job is None:
        return _error(f"Unknown job_id: {args['job_id']}")
    if not isinstance(job.result, MixResult):
        return _error(f"Job {job.job_id} has no mix result yet (status: {job.status})")
    min_confidence = args.get("min_confidence", "medium")
    if min_confidence not in BAND_RANK:
        return _error(f"min_confidence must be one of {sorted(BAND_RANK)}")

    hashes = playlist_hashes(job.result, min_confidence, dedupe=args.get("dedupe", True))
    if not hashes:
        return _error("No identified tracks at that confidence level")

    build_args: dict[str, Any] = {
        "name": args["name"],
        "hashes": hashes,
        "format": args.get("format", "m3u"),
        "validate": False,  # mix order is what was played, not a harmonic suggestion
    }
    if "output_path" in args:
        build_args["output_path"] = args["output_path"]
    return await build_playlist(db, build_args)


async def call_mix_tool(
    name: str,
    db: Database,
    settings: Settings,
    args: dict[str, Any],
    build_playlist: BuildPlaylist,
) -> list[TextContent]:
    """Dispatch a mix identification tool call."""
    if name == "index_fingerprints":
        return _index_fingerprints(settings, args)
    if name == "identify_mix":
        return _identify_mix(settings, args)
    if name == "get_job_status":
        return _get_job_status(db, args)
    if name == "build_playlist_from_mix":
        return await _build_playlist_from_mix(db, args, build_playlist)
    return _error(f"Unknown tool: {name}")
```

`src/ai_crate_digger/mcp/tools.py`:

```diff
--- a/src/ai_crate_digger/mcp/tools.py
+++ b/src/ai_crate_digger/mcp/tools.py
@@ -13,6 +13,7 @@
 
 from ai_crate_digger.core.config import Settings, get_settings
 from ai_crate_digger.core.models import Track
+from ai_crate_digger.mcp.mix_tools import MIX_TOOL_NAMES, call_mix_tool, mix_tool_definitions
 from ai_crate_digger.playlist import (
     PlaylistOptions,
     TrackFilter,
@@ -773,6 +774,7 @@
                     "required": ["name", "hashes"],
                 },
             ),
+            *mix_tool_definitions(),
         ]
 
     @server.call_tool()  # type: ignore[untyped-decorator]
@@ -821,6 +823,8 @@
                 return await _validate_playlist_order(db, arguments)
             if name == "build_playlist":
                 return await _build_playlist(db, arguments)
+            if name in MIX_TOOL_NAMES:
+                return await call_mix_tool(name, db, settings, arguments, _build_playlist)
             return [TextContent(type="text", text=f"Unknown tool: {name}")]
         finally:
             db.close()
```

- [ ] **Step 4: Run the MCP tests**

```bash
uv run pytest tests/mcp -q --no-cov
```

Expected: all pass, including the existing MCP tests and the 8 new ones.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/mcp/mix_tools.py \
  src/ai_crate_digger/mcp/tools.py \
  tests/mcp/test_mix_tools.py
git commit -m "feat: add mix identification MCP tools" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 11: CLI commands

**Files:**
- Create: `src/ai_crate_digger/cli/mix.py`
- Modify: `src/ai_crate_digger/cli/main.py`
- Test: `tests/cli/test_mix.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_mix.py`:

```python
"""Tests for the fingerprint and identify commands."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_crate_digger.cli.main import main
from ai_crate_digger.core.config import get_settings
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, place


@pytest.fixture
def runner(library: Library, monkeypatch: pytest.MonkeyPatch) -> Iterator[CliRunner]:
    monkeypatch.setenv("CRATE_DB_PATH", str(library.settings.db_path))
    monkeypatch.setenv("CRATE_INBOX_PATH", str(library.settings.inbox_path))
    monkeypatch.setenv("CRATE_MAX_WORKERS", "1")
    get_settings.cache_clear()
    yield CliRunner()
    get_settings.cache_clear()


def test_commands_are_registered(runner: CliRunner) -> None:
    for command in ("fingerprint", "identify"):
        result = runner.invoke(main, [command, "--help"])
        assert result.exit_code == 0


def test_fingerprint_then_identify(runner: CliRunner, library: Library) -> None:
    result = runner.invoke(main, ["fingerprint"])
    assert result.exit_code == 0
    assert "Indexed 4" in result.output

    mix = write_wav(library.root / "set.wav", place(library.audio["hash2"][: 30 * SR], 0, 32))
    result = runner.invoke(main, ["identify", str(mix)])
    assert result.exit_code == 0
    assert "Title2" in result.output


def test_identify_without_an_index_fails_cleanly(runner: CliRunner, library: Library) -> None:
    mix = write_wav(library.root / "set.wav", place(library.audio["hash2"][: 30 * SR], 0, 32))
    result = runner.invoke(main, ["identify", str(mix)])
    assert result.exit_code != 0
    assert "index_fingerprints" in result.output


def test_identify_missing_file_fails_cleanly(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["identify", str(tmp_path / "nope.mp3")])
    assert result.exit_code != 0
    assert "not found" in result.output
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/cli/test_mix.py -q --no-cov
```

Expected: failures, `No such command 'fingerprint'`.

- [ ] **Step 3: Implement**

Create `src/ai_crate_digger/cli/mix.py`:

```python
"""Commands for fingerprinting the library and identifying tracks in a mix."""

from typing import Literal, cast

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from ai_crate_digger.core.config import get_settings
from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.inbox import resolve_mix_path
from ai_crate_digger.fingerprint.indexer import index_library
from ai_crate_digger.fingerprint.report import describe_result
from ai_crate_digger.storage import Database

console = Console()


@click.command()
@click.option("--force", is_flag=True, help="Re-fingerprint every track, not just new ones")
@click.option("--workers", "-w", type=int, default=None, help="Number of parallel workers")
def fingerprint(force: bool, workers: int | None) -> None:
    """Fingerprint library tracks so mixes can be matched against them."""
    settings = get_settings()
    db = Database(settings.db_path)
    db.init()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Fingerprinting...", total=None)

            def on_progress(done: int, total: int) -> None:
                progress.update(task, completed=done, total=total)

            report = index_library(
                db,
                force=force,
                workers=workers or settings.max_workers,
                on_progress=on_progress,
            )
    finally:
        db.close()

    console.print(
        f"[bold green]Indexed {report.indexed}[/bold green] tracks, "
        f"{report.skipped} already up to date."
    )
    for path, error in report.failed[:10]:
        console.print(f"[red]Failed:[/red] {path} ({error})")
    if len(report.failed) > 10:
        console.print(f"[red]...and {len(report.failed) - 10} more failures[/red]")


@click.command()
@click.argument("path", required=False)
@click.option(
    "--min-confidence",
    type=click.Choice(["low", "medium", "high"]),
    default="medium",
    show_default=True,
    help="Hide matches below this confidence",
)
def identify(path: str | None, min_confidence: str) -> None:
    """Identify which library tracks were played in a recorded mix.

    PATH is the recording. Omit it to use the newest file in the inbox folder.
    """
    settings = get_settings()
    try:
        mix_path = resolve_mix_path(path, settings.inbox_path)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"[bold]Identifying:[/bold] {mix_path}")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Matching...", total=1.0)
        try:
            result = identify_mix_file(
                mix_path, settings, lambda f: progress.update(task, completed=f)
            )
        except FingerprintError as exc:
            raise click.ClickException(str(exc)) from exc

    db = Database(settings.db_path)
    db.init()
    try:
        band = cast("Literal['low', 'medium', 'high']", min_confidence)
        summary = describe_result(result, db, band)
    finally:
        db.close()

    table = Table(title=f"Mix timeline ({summary['duration']})")
    for column in ("Start", "End", "Artist", "Title", "Confidence", "Tempo"):
        table.add_column(column)
    for seg in summary["segments"]:
        table.add_row(
            seg["start"],
            seg["end"],
            seg["artist"] or "Unknown",
            seg["title"] or seg["hash"][:8],
            f"{seg['confidence_band']} ({seg['confidence']:.2f})",
            f"{seg['tempo_shift_pct']:+.1f}%",
        )
    console.print(table)
    for gap in summary["unmatched"]:
        console.print(f"[yellow]Unmatched:[/yellow] {gap['start']} to {gap['end']}")
    if summary["hidden_below_min_confidence"]:
        console.print(
            f"[dim]{summary['hidden_below_min_confidence']} weaker matches hidden "
            f"(use --min-confidence low)[/dim]"
        )
```

`src/ai_crate_digger/cli/main.py`:

```diff
--- a/src/ai_crate_digger/cli/main.py
+++ b/src/ai_crate_digger/cli/main.py
@@ -13,6 +13,7 @@
 import click
 from rich.console import Console
 
+from ai_crate_digger.cli.mix import fingerprint, identify
 from ai_crate_digger.cli.playlist import playlist
 from ai_crate_digger.cli.scan import scan
 from ai_crate_digger.cli.search import search
@@ -33,6 +34,8 @@
 main.add_command(search)
 main.add_command(playlist)
 main.add_command(stats)
+main.add_command(fingerprint)
+main.add_command(identify)
 
 
 @click.command()
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/cli -q --no-cov
```

Expected: all pass.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add src/ai_crate_digger/cli/mix.py \
  src/ai_crate_digger/cli/main.py \
  tests/cli/test_mix.py
git commit -m "feat: add crate fingerprint and crate identify commands" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 12: Benchmark script

**Files:**
- Create: `scripts/benchmark_mix.py`

This is the gate for trusting the matcher on real mixes. The synthetic tests prove the algorithm; only a real mix with a known tracklist proves it on real music, real DJ transitions and real MP3s, and gives the real numbers for index RAM and run time that the spec lists as open questions. It is not run in CI.

- [ ] **Step 1: Create the script**

Create `scripts/benchmark_mix.py`:

```python
"""Benchmark mix identification against a recording with a known tracklist.

Usage:
    uv run python scripts/benchmark_mix.py MIX.mp3 TRUTH.json

TRUTH.json lists the tracks you know were played and roughly when they started:

    [{"path": "~/Music/mp3/Artist - Track.mp3", "start_sec": 0},
     {"path": "~/Music/mp3/Other - Tune.mp3", "start_sec": 215}]

The library must already be fingerprinted (``crate fingerprint``). The report shows
recall, false matches, run time and memory, which is how to judge whether the matcher
is good enough on real mixes and where its thresholds need tuning.
"""

import json
import resource
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ai_crate_digger.core.config import get_settings
from ai_crate_digger.fingerprint.identify import match_params_from_settings
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.matcher import identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.report import BAND_RANK, format_time
from ai_crate_digger.fingerprint.spectral import extract_peaks, load_audio
from ai_crate_digger.scanning import compute_file_hash
from ai_crate_digger.storage import Database

console = Console()


def _peak_memory_gb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / 1e9 if sys.platform == "darwin" else usage / 1e6


@click.command()
@click.argument("mix", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("truth", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--tolerance", default=15.0, show_default=True, help="Seconds allowed for start time")
@click.option(
    "--min-confidence",
    type=click.Choice(["low", "medium", "high"]),
    default="medium",
    show_default=True,
)
def main(mix: Path, truth: Path, tolerance: float, min_confidence: str) -> None:
    """Report recall, false matches, run time and memory for one mix."""
    settings = get_settings()
    params = FingerprintParams()
    expected = [
        (compute_file_hash(Path(entry["path"]).expanduser()), float(entry["start_sec"]), entry)
        for entry in json.loads(truth.read_text())
    ]

    started = time.perf_counter()
    db = Database(settings.db_path)
    db.init()
    try:
        index = get_library_index(db)
    finally:
        db.close()
    load_seconds = time.perf_counter() - started

    started = time.perf_counter()
    peaks = extract_peaks(load_audio(mix, params.sample_rate), params)
    decode_seconds = time.perf_counter() - started

    started = time.perf_counter()
    result = identify_mix(index, peaks, params, match_params_from_settings(settings))
    match_seconds = time.perf_counter() - started

    floor = BAND_RANK[min_confidence]
    segments = [s for s in result.segments if BAND_RANK[s.confidence_band] >= floor]
    expected_hashes = {h for h, _, _ in expected}

    table = Table(title=f"{mix.name} ({format_time(result.duration_sec)})")
    for column in ("Expected", "Start", "Found", "Band", "Tempo"):
        table.add_column(column)
    hits = 0
    for file_hash, start, entry in expected:
        match = next(
            (
                s
                for s in segments
                if s.track_hash == file_hash and abs(s.start_sec - start) <= tolerance
            ),
            None,
        )
        hits += match is not None
        table.add_row(
            Path(entry["path"]).name,
            format_time(start),
            f"{format_time(match.start_sec)}" if match else "[red]missed[/red]",
            match.confidence_band if match else "-",
            f"{match.tempo_shift_pct:+.1f}%" if match else "-",
        )
    console.print(table)

    false_matches = [s for s in segments if s.track_hash not in expected_hashes]
    console.print(f"Recall: [bold]{hits}/{len(expected)}[/bold] tracks found")
    console.print(f"False matches: [bold]{len(false_matches)}[/bold] segments not in the tracklist")
    for seg in false_matches:
        console.print(
            f"  {format_time(seg.start_sec)}-{format_time(seg.end_sec)} "
            f"{seg.track_hash[:8]} {seg.confidence_band} ({seg.confidence:.2f})"
        )
    console.print(
        f"Index: {len(index)} tracks, {len(index.hashes):,} hashes, load {load_seconds:.1f}s"
    )
    console.print(f"Decode + peaks: {decode_seconds:.1f}s, matching: {match_seconds:.1f}s")
    console.print(f"Peak memory: {_peak_memory_gb():.2f} GB")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Check it loads**

```bash
uv run python scripts/benchmark_mix.py --help && uv run mypy src/ scripts/ && uv run ruff check .
```

Expected: help text with `MIX TRUTH` arguments, `Success: no issues found`, `All checks passed!`.

- [ ] **Commit**

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/
git add scripts/benchmark_mix.py
git commit -m "feat: add mix identification benchmark script" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

The pre-commit hooks (ruff format, ruff lint, mypy) run on commit. If a hook rewrites a file, `git add` it again and re-run the commit.

### Task 13: Documentation and spec amendments

**Files:**
- Modify: `README.md`, `docs/mcp-tools.md`
- Modify: `docs/superpowers/specs/2026-11-21-mix-identification-design.md`

- [ ] **Step 1: README**

```diff
--- a/README.md
+++ b/README.md
@@ -84,6 +84,23 @@
 crate playlist --tags techno --output ~/Desktop/set.xml --format rekordbox
 ```
 
+## Identify Tracks in a Recorded Mix
+
+Recorded a set and forgot the tracklist? Fingerprint your library once, then match the recording against it.
+
+```bash
+# Fingerprint your library (only new tracks after the first run)
+crate fingerprint
+
+# Identify what was played in a recording
+crate identify ~/Music/mixes/friday-set.mp3
+
+# Or use the newest recording in ~/Music/mixes
+crate identify
+```
+
+It tolerates tempo changes of up to about 8%, noise and overlapping transitions, and lists spans it could not match (usually tracks that are not in your library). From an AI assistant, ask it to identify your latest recording and build a playlist from it. See [MCP tools](docs/mcp-tools.md#mix-identification-tools).
+
 ## Connect to an AI Assistant
 
 Ask your AI assistant to manage your music library.
@@ -177,6 +194,7 @@
 | `CRATE_DB_PATH` | `~/.ai-crate-digger/catalog.db` | SQLite database path |
 | `CRATE_VECTOR_PATH` | `~/.ai-crate-digger/.chroma` | ChromaDB vector store path |
 | `CRATE_OUTPUT_PATH` | `~/Downloads` | Default playlist export directory |
+| `CRATE_INBOX_PATH` | `~/Music/mixes` | Folder `crate identify` and `identify_mix` use for the newest recording |
 
 ## Development
 
```

- [ ] **Step 2: MCP tools reference**

```diff
--- a/docs/mcp-tools.md
+++ b/docs/mcp-tools.md
@@ -138,6 +138,61 @@
 - `.xml` extension → Rekordbox XML format
 - `format` parameter overrides extension
 
+## Mix Identification Tools
+
+Find which library tracks were played in a recorded DJ mix and rebuild the playlist. Matching tolerates tempo changes of up to about 8% (with or without key lock), background noise and overlapping transitions. Only tracks already in your library can be identified.
+
+Typical flow: `index_fingerprints` once, then `identify_mix`, poll `get_job_status`, then `build_playlist_from_mix`. Both indexing and identification run in the background, so each call returns a `job_id` straight away.
+
+### index_fingerprints
+
+Fingerprint library tracks. Only tracks without a current fingerprint are processed unless `force` is true. A full library takes tens of minutes.
+
+```json
+{ "force": false }
+```
+
+### identify_mix
+
+Start identifying a recording. `path` is a local file path, or `"latest"` (the default) for the newest audio file in the inbox folder (`~/Music/mixes`, override with `CRATE_INBOX_PATH`). Recordings under 30 seconds are rejected.
+
+```json
+{ "path": "~/Music/mixes/friday-set.mp3" }
+```
+
+### get_job_status
+
+Progress of an `index_fingerprints` or `identify_mix` job. For a finished mix job it returns the timeline:
+
+```json
+{
+  "status": "done",
+  "duration": "1:01:40",
+  "segments": [
+    {
+      "start": "0:00", "end": "5:20",
+      "hash": "d73436cf", "artist": "Artist", "title": "Title",
+      "confidence": 0.41, "confidence_band": "high",
+      "tempo_shift_pct": 2.0, "mode": "pitch"
+    }
+  ],
+  "hidden_below_min_confidence": 1,
+  "unmatched": [{ "start": "5:20", "end": "9:05" }]
+}
+```
+
+`min_confidence` (`low`, `medium` default, `high`) hides weaker matches. `tempo_shift_pct` is how much faster (positive) or slower the track was played than the original. `unmatched` spans are stretches where no library track was found, typically tracks that are not in the library.
+
+### build_playlist_from_mix
+
+Export the tracks from a finished mix job in the order they were played.
+
+```json
+{ "job_id": "a1b2c3d4", "name": "Friday set", "min_confidence": "medium", "format": "m3u" }
+```
+
+A track played twice is listed once unless `dedupe` is false. Harmonic validation is skipped because the order is what was played.
+
 ## Traditional Tools
 
 ### scan_library
@@ -186,6 +241,9 @@
 
 # Vector store path
 export CRATE_VECTOR_PATH=~/.ai-crate-digger/.chroma
+
+# Folder where recorded mixes are dropped (used by identify_mix "latest")
+export CRATE_INBOX_PATH=~/Music/mixes
 ```
 
 ## Example Workflows
@@ -202,6 +260,15 @@
 5. build_playlist(name="Progressive Set", hashes=[...])
 ```
 
+### Rebuild a Playlist from a Recorded Mix
+
+```
+1. index_fingerprints()                      [once, then only for new tracks]
+2. identify_mix(path="latest")               [returns job_id]
+3. get_job_status(job_id)                    [repeat until status is done]
+4. build_playlist_from_mix(job_id, name="Friday set")
+```
+
 ### Traditional Playlist (1 call)
 
 ```
```

- [ ] **Step 3: Record what prototyping changed in the spec**

```diff
--- a/docs/superpowers/specs/2026-11-21-mix-identification-design.md
+++ b/docs/superpowers/specs/2026-11-21-mix-identification-design.md
@@ -1,7 +1,7 @@
 # Mix identification (audio fingerprinting) design
 
 **Date:** 2026-11-21
-**Status:** Draft, awaiting review
+**Status:** Approved for implementation (amended after prototyping, see Amendments)
 **Package:** `ai_crate_digger` (worktree `dj-catalog-impl`, branch `main`)
 
 ## Problem
@@ -58,28 +58,41 @@
 
 ### Storage
 
-- New `fingerprints` table in `catalog.db`: `track_hash TEXT` (the existing
-  file hash, so rescans and `clean_orphans` stay consistent), `hashes BLOB`
-  (packed hash and offset arrays), `n_hashes INTEGER`.
-- New `fingerprinted_at` column on `tracks` so indexing is incremental.
+- New `fingerprints` table in `catalog.db`: `track_hash TEXT` primary key (the
+  existing file hash, so rescans stay consistent), `version INTEGER` (scheme
+  version, bumped if fingerprint parameters change), `n_hashes INTEGER`,
+  `blob BLOB` (packed hash and anchor-time arrays).
+- No new column on `tracks`. A track counts as fingerprinted when a row with
+  the current version exists. `create_all` cannot add columns to an existing
+  SQLite table and the repo has no migration tooling, so a new table is the
+  only change that is safe for existing catalogues.
 - Per-track blobs rather than one row per hash. A full library (about 6,400
   tracks) would be hundreds of millions of rows otherwise. At query time the
   blobs load into sorted numpy arrays, an estimated 1 to 2 GB of RAM for the
   full library (to be confirmed by the benchmark).
-- `clean_orphans` also deletes fingerprints for removed tracks.
+- `Database.delete_track` also deletes the track's fingerprint, which covers
+  both the `clean_orphans` tool and `crate clean`.
 
 ### Matching
 
-1. Fingerprint the mix once per speed factor (0.92 to 1.08, about 1% steps).
-2. For each factor, look up every hash and vote on
-   `(track, mix_time - track_time)`. A genuine match is a sharp spike at one
-   offset.
-3. Slide 10 s windows with a 5 s hop. Keep the best `(track, factor)` per
-   window when its votes clear a threshold. Merge consecutive windows with the
-   same track and a consistent offset into one segment.
-4. Confidence is the vote count relative to the noise floor, banded high,
-   medium or low. The winning speed factor is reported as the tempo shift
-   (for example `+3.2%`).
+1. Extract spectrogram peaks from the mix once. For each speed hypothesis
+   (0.92 to 1.08 in 1% steps, in two modes: pitch follows tempo like a vinyl
+   pitch fader, or key lock where only tempo changes) rescale the peak
+   coordinates and hash them. No re-decoding or new spectrogram per factor.
+   Library tracks are hashed sparsely (each peak paired with the peaks ranked
+   3 to 7 after it) while the mix is hashed densely (ranks 1 to 24), so peaks
+   added or dropped by a second playing track do not break pairings.
+2. For each hypothesis, look up every hash and vote on
+   `(block, track, mix_time - track_time)`. A genuine match is a sharp spike
+   at one offset.
+3. Split the mix into non-overlapping 5 s blocks. Keep the best
+   `(track, hypothesis)` per block when its votes clear a threshold, and up to
+   two tracks per block so transitions show both. Merge consecutive blocks
+   with the same track and a consistent position in that track into one
+   segment.
+4. Confidence is the share of possible index pairs in the block that voted for
+   the match ("support"), banded high, medium or low. The winning speed factor
+   is reported as the tempo shift (for example `+3.2%`).
 5. Spans with no segment above threshold are returned as `unmatched`.
    Lower-confidence matches are kept and flagged, never silently dropped.
 
@@ -105,22 +118,26 @@
 
 ### MCP tools (`mcp/tools.py`)
 
-- `index_fingerprints(force=False)`: fingerprint tracks without an index,
-  using the existing parallel analysis pool. Reports progress and counts.
-  `scan_library` gains an opt-in flag to fingerprint new files as it scans.
+- `index_fingerprints(force=False)`: fingerprint tracks without a current
+  fingerprint, using a process pool (same spawn and BLAS-thread settings as the
+  analysis pool, which is specific to `Track` objects). Runs as a background
+  job because a full library takes tens of minutes. `scan_library` is
+  unchanged for now.
 - `identify_mix(path | "latest")`: starts a background job, returns `job_id`
   immediately. `"latest"` resolves to the newest file in the inbox folder.
   Non-blocking because an hour-long mix takes minutes and the Claude Desktop
   tool-call timeout is not known.
-- `get_mix_result(job_id, min_confidence="medium")`: progress while running,
-  then the timeline JSON.
+- `get_job_status(job_id, min_confidence="medium")`: progress for either kind
+  of job, and for a finished mix job the timeline JSON from Section 2 (replaces
+  the earlier `get_mix_result`, so indexing can be polled the same way).
 - `build_playlist_from_mix(job_id, min_confidence, name, format)`: matched
   hashes in mix order into the existing `export_playlist` code.
 
 ### CLI
 
 `fingerprint` and `identify` commands alongside `scan` and `search`, sharing
-the same code path, results printed as a Rich table.
+the same code path, results printed as a Rich table. `identify` without a path
+uses the newest file in the inbox folder.
 
 ### Config (`core/config.py`, `Settings`)
 
@@ -149,6 +166,28 @@
   time. This is the gate for trusting the matcher on real mixes.
 - Every commit passes pytest, mypy and ruff. Small, frequent commits.
 
+## Amendments after prototyping
+
+A prototype on synthetic audio (600 tracks; mixes with pitch shifts up to 8%,
+key-lock stretch, noise, overlaps and unknown tracks) identified every track
+with no false matches. Differences from the first draft of this spec:
+
+- 5 s blocks instead of 10 s windows with a 5 s hop (same effect, simpler).
+- Speed search rescales peak coordinates instead of re-fingerprinting audio,
+  and covers both pitch-follows-tempo and key-lock hypotheses.
+- Asymmetric pairing between library (sparse) and mix (dense).
+- Confidence is "support" (share of possible pairs that voted), not a vote
+  count against a noise floor.
+- `MixSegment` carries `mode` (`pitch` or `keylock`) and no artist or title;
+  names are added from the catalogue when results are described.
+- Fingerprint status lives in the new table, not a `tracks` column.
+- `get_job_status` replaces `get_mix_result`.
+- `numpy` and `scipy` become explicit dependencies (already installed via
+  librosa).
+
+Confidence bands (support of 0.12 high, 0.05 medium, 0.02 low) come from
+synthetic audio and must be re-tuned with the benchmark on real mixes.
+
 ## Open questions
 
 - Actual RAM and run time for the full library and an hour-long mix (resolved
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/mcp-tools.md docs/superpowers/specs/2026-11-21-mix-identification-design.md
git commit -m "docs: document mix identification and amend the spec" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

### Task 14: Full verification and a real-library check

**Files:** none

- [ ] **Step 1: Everything green**

```bash
uv run pytest -q 2>&1 | tail -4 && uv run mypy src/ scripts/ && uv run ruff check . && uv run ruff format --check .
```

Expected: about `259 passed` with the coverage gate met, `Success: no issues found`, `All checks passed!`, files already formatted.

- [ ] **Step 2: Smoke test on Tom's real library (manual, needs Tom)**

Do this together with Tom, since it reads his 69 GB library and takes a while:

```bash
uv run crate fingerprint            # first run: tens of minutes. Note the time and any failures.
uv run crate stats                  # sanity check the catalogue is intact
```

Then record or pick a mix whose tracklist Tom knows, write a `truth.json` (format in the script's docstring), and run:

```bash
uv run python scripts/benchmark_mix.py ~/Music/mixes/<mix>.mp3 truth.json
```

Record in the PR description: recall, false matches, index size and RAM, match time for the mix length, and fingerprint time per track.

- [ ] **Step 3: Decide what to tune (only if the benchmark says so)**

| Symptom | First thing to try |
|---|---|
| Known tracks missed, all as `unmatched` | Lower `CRATE_MIX_LOW_SUPPORT` / `CRATE_MIX_MEDIUM_SUPPORT` and re-run with `--min-confidence low` to see what is being hidden |
| False matches at `medium` or `high` | Raise `CRATE_MIX_MEDIUM_SUPPORT` |
| Tracks missed only when tempo was changed a lot | `CRATE_MIX_SPEED_STEP=0.005` (doubles match time) |
| Match time too slow on an hour-long mix | Lower `query_rank_max` in `FingerprintParams` (no reindex needed because it only affects the mix side), or narrow `CRATE_MIX_SPEED_RANGE` |
| Index RAM near the limit | Lower `peaks_per_block` or `index_rank_max` in `FingerprintParams`, **bump `FINGERPRINT_VERSION`**, and re-run `crate fingerprint --force` |

Any change to `FingerprintParams` that affects hashing needs a `FINGERPRINT_VERSION` bump so old fingerprints are ignored and rebuilt.

- [ ] **Step 4: Hand back to Tom**

Do not push. Report the commits on `feat/mix-identification`, the test and lint results, and the benchmark numbers (or that Step 2 is still to do). Tom decides when to push and whether to merge.

---

## Self-review against the spec

| Spec requirement | Task |
|---|---|
| Fingerprint package: spectral, hashing, index, matcher, jobs | 2, 3, 5, 6, 9 |
| `fingerprints` table, incremental indexing, orphan cleanup | 4, 7 |
| Speed search, offset voting, blocks, segments, confidence bands, unmatched spans | 6 |
| `index_fingerprints`, `identify_mix`, `get_job_status`, `build_playlist_from_mix` | 10 |
| Inbox folder and `"latest"` | 8, 10, 11 |
| CLI `fingerprint` and `identify` | 11 |
| Settings and env overrides | 1 |
| Errors: unreadable file, empty index, short mix, oversized index | 5, 9 |
| Tests: unit, synthetic audio, local benchmark | 2 to 12 |
| pytest, mypy, ruff before every commit | every task's commit step |
| Docs | 13 |
| Live microphone | out of scope (spec non-goal) |

Spec items that changed (tools renamed, 5 s blocks, no `tracks` column, own process pool) are recorded in the amendments in Task 13.
