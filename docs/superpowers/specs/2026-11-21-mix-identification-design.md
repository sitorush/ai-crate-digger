# Mix identification (audio fingerprinting) design

**Date:** 2026-11-21
**Status:** Draft, awaiting review
**Package:** `ai_crate_digger` (worktree `dj-catalog-impl`, branch `main`)

## Problem

DJ mixes get recorded without a tracklist. Given a recording (typically up to
an hour), identify which tracks from the local library were played, when, and
rebuild the playlist, driven from Claude through the existing MCP server.

Out of scope: matching against Beatport, ZipDJ or any online catalogue (no
public fingerprint search exists, and bulk preview downloads breach their
terms). Out of scope: identifying samples reused inside other tracks.

## Goals

- Identify library tracks inside a mix recording and return a timeline with
  start and end times, confidence and estimated tempo shift.
- Tolerate DJ tempo and pitch changes (target range 0.92 to 1.08), noise and
  overlapping transitions.
- Rebuild a playlist from the result using the existing `export_playlist`
  code (Rekordbox export and so on).
- Work from Claude (Desktop or Code) via MCP, and from the CLI without Claude.

## Non-goals

- Passing audio through Claude. MCP tool calls carry text only and Claude
  Desktop voice mode does not forward raw audio, so input is always a file
  path on disk (or an inbox folder).
- Live microphone identification. Deferred as a later add-on that would feed
  the same matcher.
- Guaranteeing recall on heavy loops, acapella-over-instrumental layering or
  different edits of the same song. These may come back partial or unmatched.

## Approach

Own constellation fingerprinting in Python (numpy, scipy, librosa), with the
mix fingerprinted at several speed factors and matched against an index of
the library. Chosen over plain Chromaprint-style matching (fails beyond about
1 to 2% tempo change) and over Olaf or Panako (native or Java dependency,
second index format, hurts easy install for the planned open-source release).
If real mixes defeat the matcher, an external engine can replace it behind the
same interface later.

## Architecture

New package `src/ai_crate_digger/fingerprint/`, laid out like `analysis/`:

| Module | Responsibility |
|---|---|
| `spectral.py` | Decode to mono 11.025 kHz, log-magnitude spectrogram, local peak picking, capped peaks per second |
| `hashing.py` | Pair each anchor peak with later peaks in a target zone, pack `(f1, f2, dt)` into 32-bit hashes with the anchor offset |
| `index.py` | Persist per-track hash blobs, load an in-memory `hash -> (track, offset)` lookup (sorted numpy arrays), incremental indexing |
| `matcher.py` | Speed-factor search, offset voting, windowing, segment merging, confidence scoring |
| `jobs.py` | Background job registry for long identifications (progress, result, errors) |

### Storage

- New `fingerprints` table in `catalog.db`: `track_hash TEXT` (the existing
  file hash, so rescans and `clean_orphans` stay consistent), `hashes BLOB`
  (packed hash and offset arrays), `n_hashes INTEGER`.
- New `fingerprinted_at` column on `tracks` so indexing is incremental.
- Per-track blobs rather than one row per hash. A full library (about 6,400
  tracks) would be hundreds of millions of rows otherwise. At query time the
  blobs load into sorted numpy arrays, an estimated 1 to 2 GB of RAM for the
  full library (to be confirmed by the benchmark).
- `clean_orphans` also deletes fingerprints for removed tracks.

### Matching

1. Fingerprint the mix once per speed factor (0.92 to 1.08, about 1% steps).
2. For each factor, look up every hash and vote on
   `(track, mix_time - track_time)`. A genuine match is a sharp spike at one
   offset.
3. Slide 10 s windows with a 5 s hop. Keep the best `(track, factor)` per
   window when its votes clear a threshold. Merge consecutive windows with the
   same track and a consistent offset into one segment.
4. Confidence is the vote count relative to the noise floor, banded high,
   medium or low. The winning speed factor is reported as the tempo shift
   (for example `+3.2%`).
5. Spans with no segment above threshold are returned as `unmatched`.
   Lower-confidence matches are kept and flagged, never silently dropped.

Result shape:

```python
@dataclass(frozen=True)
class MixSegment:
    start_sec: float
    end_sec: float
    track_hash: str
    artist: str | None
    title: str | None
    confidence: float
    confidence_band: Literal["high", "medium", "low"]
    tempo_shift_pct: float
```

(Pydantic or dataclass per house style; `unmatched` spans are a parallel list
of `(start_sec, end_sec)`.)

## Interfaces

### MCP tools (`mcp/tools.py`)

- `index_fingerprints(force=False)`: fingerprint tracks without an index,
  using the existing parallel analysis pool. Reports progress and counts.
  `scan_library` gains an opt-in flag to fingerprint new files as it scans.
- `identify_mix(path | "latest")`: starts a background job, returns `job_id`
  immediately. `"latest"` resolves to the newest file in the inbox folder.
  Non-blocking because an hour-long mix takes minutes and the Claude Desktop
  tool-call timeout is not known.
- `get_mix_result(job_id, min_confidence="medium")`: progress while running,
  then the timeline JSON.
- `build_playlist_from_mix(job_id, min_confidence, name, format)`: matched
  hashes in mix order into the existing `export_playlist` code.

### CLI

`fingerprint` and `identify` commands alongside `scan` and `search`, sharing
the same code path, results printed as a Rich table.

### Config (`core/config.py`, `Settings`)

`inbox_path` (default `~/Music/mixes`), speed range and step, window and hop
size, confidence thresholds. Same env-var override pattern as existing
settings.

## Error handling

- Unreadable or unsupported file: clear tool error.
- Empty or stale index: prompt the user to run `index_fingerprints` first.
- Mix shorter than 30 s: rejected with an explanation.
- Index load guarded by a size estimate, with a readable error instead of an
  out-of-memory crash.
- Logging through the standard `logging` module, no prints.

## Testing

- Unit: hash determinism, vote-offset maths, segment merging, confidence
  banding.
- Synthetic: build a mix from generated or fixture audio, time-stretch by
  known factors, add noise, overlap transitions. Assert recall, offset error
  and tempo-shift estimate within tolerance. No copyrighted audio in the repo.
- Local benchmark script (not run in CI): a real mix built from the user's own
  library with a known tracklist. Reports recall, false matches, RAM and run
  time. This is the gate for trusting the matcher on real mixes.
- Every commit passes pytest, mypy and ruff. Small, frequent commits.

## Open questions

- Actual RAM and run time for the full library and an hour-long mix (resolved
  by the benchmark).
- Whether peak density and hash fan-out need tuning for low-bitrate MP3s.
- Whether the live-mic tool is worth adding after this ships.
