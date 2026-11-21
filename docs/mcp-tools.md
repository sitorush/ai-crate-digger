# MCP Tools Reference

## Overview

The ai-crate-digger MCP server provides tools for music library management and playlist generation. Tools are divided into two categories:

1. **Traditional tools** - Direct playlist generation via greedy algorithm
2. **AI-friendly tools** - Enable AI-driven playlist building with creative control

## AI-Friendly Playlist Tools

### get_candidate_pool

Returns filtered tracks in compact JSON format optimised for AI selection decisions.

**Use case:** Fetch a pool of compatible tracks for a specific playlist phase (e.g., "warm-up house tracks", "peak techno section").

**Input Schema:**
```json
{
  "tags": ["House", "Deep House"],
  "bpm_min": 124,
  "bpm_max": 128,
  "energy_min": 0.6,
  "energy_max": 0.9,
  "key": "8A",
  "limit": 20,
  "exclude_hashes": ["abc123"],
  "exclude_stems": true,
  "exclude_unknown": true,
  "sort_by": "energy_desc"
}
```

**Output Format:**
```json
[
  {
    "hash": "d73436cf",
    "artist": "Artist Name",
    "title": "Track Title",
    "bpm": 128.1,
    "key": "8A",
    "energy": 0.85,
    "danceability": 0.72,
    "tags": ["House", "Deep House"],
    "duration_sec": 256
  }
]
```

**Filtering logic:**
- Tags: OR logic (track matches any tag)
- BPM/Energy: Inclusive range
- Key: Harmonic compatibility (distance ≤ 1 on Camelot wheel)
- Stems: Case-insensitive substring match for "ds_", "_percussion_", etc.
- Unknown: Case-insensitive artist match

### validate_playlist_order

Validates ordered track list for common issues.

**Use case:** Check AI-selected track order before export.

**Input Schema:**
```json
{
  "hashes": ["hash001", "hash002", "hash003"]
}
```

**Output Format:**
```json
{
  "valid": false,
  "track_count": 3,
  "total_duration_min": 15.2,
  "issues": [
    {
      "type": "bpm_jump",
      "position": 1,
      "from": {"title": "Track A", "bpm": 128.0, "key": "8A", "tags": ["House"]},
      "to": {"title": "Track B", "bpm": 135.0, "key": "8A", "tags": ["House"]},
      "detail": "BPM change of 7.0 (threshold: 2.0)"
    }
  ],
  "duplicates": [],
  "same_song_duplicates": []
}
```

**Validation checks:**
1. Exact duplicates (same hash)
2. Same-song duplicates (different remixes - strips parens/brackets)
3. BPM jumps (>2.0 BPM change between adjacent tracks)
4. Key clashes (harmonic distance >1)
5. Tag mismatches (zero overlap between adjacent tracks)

### build_playlist

Exports ordered track list to playlist file.

**Use case:** Final step after AI selects and validates track order.

**Input Schema:**
```json
{
  "name": "My Playlist",
  "hashes": ["hash001", "hash002"],
  "output_path": "~/Desktop/playlist.m3u",
  "format": "m3u",
  "validate": true
}
```

**Output Format:**
```json
{
  "success": true,
  "output_path": "/Users/tom/Desktop/playlist.m3u",
  "track_count": 2,
  "total_duration_min": 6.33,
  "validation": {
    "valid": true,
    "track_count": 2,
    "issues": []
  }
}
```

**Path handling:**
- User path provided: Validates and uses it
- No path provided: Uses `CRATE_OUTPUT_PATH` env var or `~/Downloads`
- Cross-OS compatible (`Path.home()`)

**Format detection:**
- `.m3u` extension → M3U format
- `.xml` extension → Rekordbox XML format
- `format` parameter overrides extension

## Mix Identification Tools

Find which library tracks were played in a recorded DJ mix and rebuild the playlist. Matching tolerates tempo changes of up to about 8% (with or without key lock), background noise and overlapping transitions. Only tracks already in your library can be identified.

Typical flow: `index_fingerprints` once, then `identify_mix`, poll `get_job_status`, then `build_playlist_from_mix`. Both indexing and identification run in the background, so each call returns a `job_id` straight away.

### index_fingerprints

Fingerprint library tracks. Only tracks without a current fingerprint are processed unless `force` is true. A full library takes tens of minutes.

```json
{ "force": false }
```

### identify_mix

Start identifying a recording. `path` is a local file path, or `"latest"` (the default) for the newest audio file in the inbox folder (`~/Music/mixes`, override with `CRATE_INBOX_PATH`). Recordings under 30 seconds are rejected.

```json
{ "path": "~/Music/mixes/friday-set.mp3" }
```

### get_job_status

Progress of an `index_fingerprints` or `identify_mix` job. For a finished mix job it returns the timeline:

```json
{
  "status": "done",
  "duration": "1:01:40",
  "segments": [
    {
      "start": "0:00", "end": "5:20",
      "hash": "d73436cf", "artist": "Artist", "title": "Title",
      "confidence": 0.41, "confidence_band": "high",
      "tempo_shift_pct": 2.0, "mode": "pitch"
    }
  ],
  "hidden_below_min_confidence": 1,
  "unmatched": [{ "start": "5:20", "end": "9:05" }]
}
```

`min_confidence` (`low`, `medium` default, `high`) hides weaker matches. `tempo_shift_pct` is how much faster (positive) or slower the track was played than the original. `unmatched` spans are stretches where no library track was found, typically tracks that are not in the library.

### build_playlist_from_mix

Export the tracks from a finished mix job in the order they were played.

```json
{ "job_id": "a1b2c3d4", "name": "Friday set", "min_confidence": "medium", "format": "m3u" }
```

A track played twice is listed once unless `dedupe` is false. Harmonic validation is skipped because the order is what was played.

## Traditional Tools

### scan_library

Scans a directory for new audio files, extracts metadata, and runs audio analysis.

> **Use for new additions only.** This tool runs synchronously inside the MCP server. Scanning a full library of thousands of tracks will time out or hang your AI assistant. For first-time or full library scans, use the CLI:
> ```bash
> crate scan ~/Music
> crate scan ~/Music --force   # re-analyse everything
> ```
> Use `scan_library` via your AI assistant for small folders of new tracks -- e.g. a Downloads folder or a fresh batch of purchases.

**Input Schema:**
```json
{
  "directory": "~/Music/New Arrivals",
  "force": false
}
```

### generate_playlist

Generates playlist using greedy algorithm (existing tool, unchanged).

### search_tracks

Search library by natural language or filters (existing tool, unchanged).

### get_track_details

Get full metadata for specific track (existing tool, unchanged).

### export_playlist

Export tracks to playlist file (existing tool, unchanged).

## Environment Variables

```bash
# Default output directory for playlists
export CRATE_OUTPUT_PATH=~/Music/Playlists

# Database path
export CRATE_DB_PATH=~/.ai-crate-digger/catalog.db

# Vector store path
export CRATE_VECTOR_PATH=~/.ai-crate-digger/.chroma

# Folder where recorded mixes are dropped (used by identify_mix "latest")
export CRATE_INBOX_PATH=~/Music/mixes
```

## Example Workflows

### AI-Driven Playlist (8-9 calls)

```
1. get_candidate_pool(tags=["House"], bpm_min=124, bpm_max=128, limit=10)
2. get_candidate_pool(tags=["Tech House"], bpm_min=127, bpm_max=130, limit=10)
3. get_candidate_pool(tags=["Techno"], bpm_min=128, bpm_max=135, limit=5)
   [AI selects and orders 25 tracks]
4. validate_playlist_order(hashes=[...25 hashes...])
   [AI fixes any issues]
5. build_playlist(name="Progressive Set", hashes=[...])
```

### Rebuild a Playlist from a Recorded Mix

```
1. index_fingerprints()                      [once, then only for new tracks]
2. identify_mix(path="latest")               [returns job_id]
3. get_job_status(job_id)                    [repeat until status is done]
4. build_playlist_from_mix(job_id, name="Friday set")
```

### Traditional Playlist (1 call)

```
1. generate_playlist(tags=["House"], duration_minutes=60, harmonic_mixing=true)
```
