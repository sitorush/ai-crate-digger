# Getting Started

Get your music library catalogued in 5 minutes.

## 1. Install

```bash
git clone https://github.com/sitorush/ai-crate-digger.git
cd ai-crate-digger
uv sync
```

> **No uv?** `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 2. Scan Your Music

```bash
crate scan ~/Music
```

This will:
- Find all audio files (MP3, FLAC, WAV, AIFF, M4A, OGG)
- Extract metadata (title, artist, genre tags)
- Analyse audio (BPM, key, energy, danceability)
- Classify untagged tracks by genre (using Essentia ML if installed)

First scan takes ~2-5 seconds per track.

## 3. View Your Library

```bash
# Overall stats
crate stats

# Top genres
crate stats --group-by tags

# Top artists
crate stats --group-by artist
```

## 4. Search Tracks

```bash
# By genre
crate search --tags "tech house"

# By BPM range
crate search --bpm-min 124 --bpm-max 128

# By artist
crate search --artist "Fred Again"

# Natural language (semantic search)
crate search --query "uplifting summer vibes"
```

## 5. Generate Playlists

```bash
# 60-minute tech house set
crate playlist --tags "tech house" --duration 60 --output ~/Desktop/tech-house.m3u

# BPM-locked set
crate playlist --tags garage --bpm-min 130 --bpm-max 134 --duration 60

# Export for Rekordbox
crate playlist --tags techno --output ~/Desktop/set.xml --format rekordbox
```

## 6. Identify Tracks in a Recorded Mix (Optional)

Recorded a set and lost the tracklist? Fingerprint your library once, then match the recording against it:

```bash
# One-off (a few minutes for ~7,000 tracks); afterwards only new tracks are processed
crate fingerprint

# Identify a recording, or the newest one in ~/Music/mixes
crate identify ~/Music/mixes/friday-set.mp3
crate identify
```

A long mix takes several minutes and a few GB of RAM. Add `--min-confidence low` to see weaker matches. Run `crate fingerprint` again after adding new tracks to your library.

## 7. Connect to an LLM (Optional)

Control your library through natural language:

- [Claude Desktop](./MCP_CLAUDE.md)  -- "Find me some deep house around 122 BPM"
- [ChatGPT Desktop](./MCP_CHATGPT.md)  -- same tools, different app
- [Other apps](./MCP_GENERIC.md)  -- Cursor, Cline, Continue, Zed

## Quick Reference

| Command | Description |
|---------|-------------|
| `crate scan <dir>` | Scan directory for music |
| `crate scan <dir> --force` | Re-analyse all tracks |
| `crate scan <dir> --reset` | Clear DB and scan fresh |
| `crate search --tags X` | Find tracks by tag |
| `crate search --query "..."` | Semantic search |
| `crate playlist --tags X` | Generate playlist |
| `crate stats` | Library statistics |
| `crate fingerprint` | Fingerprint tracks for mix identification |
| `crate identify [file]` | Identify tracks in a recorded mix |
| `crate clean` | Remove orphaned tracks |
| `crate reset` | Clear entire database |
| `crate mcp-server` | Start MCP server for LLM apps |
