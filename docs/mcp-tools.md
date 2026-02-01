# MCP Tools Reference

## Overview

The DJ Catalog MCP server provides tools for music library management and playlist generation. Tools are divided into two categories:

1. **Traditional tools** - Direct playlist generation via greedy algorithm
2. **AI-friendly tools** - Enable AI-driven playlist building with creative control

## AI-Friendly Playlist Tools

### get_candidate_pool

Returns filtered tracks in compact JSON format optimized for AI selection decisions.

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
- No path provided: Uses `DJ_CATALOG_OUTPUT_PATH` env var or `~/Downloads`
- Cross-OS compatible (`Path.home()`)

**Format detection:**
- `.m3u` extension → M3U format
- `.xml` extension → Rekordbox XML format
- `format` parameter overrides extension

## Traditional Tools

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
export DJ_CATALOG_OUTPUT_PATH=~/Music/Playlists

# Database path
export DJ_CATALOG_DB_PATH=~/.dj-catalog/catalog.db

# Vector store path
export DJ_CATALOG_VECTOR_PATH=~/.dj-catalog/.chroma
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

### Traditional Playlist (1 call)

```
1. generate_playlist(tags=["House"], duration_minutes=60, harmonic_mixing=true)
```
