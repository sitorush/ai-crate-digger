# Getting Started

Get your music library cataloged in 5 minutes.

## 1. Install

```bash
# Create environment and install
python3.11 -m venv ~/.local/dj-catalog-venv
source ~/.local/dj-catalog-venv/bin/activate
pip install dj-catalog
```

## 2. Scan Your Music

```bash
dj scan ~/Music
```

This will:
- Find all audio files (MP3, FLAC, WAV, AIFF, M4A, OGG)
- Extract metadata (title, artist, genre tags)
- Analyze audio (BPM, key, energy, danceability)
- Classify untagged tracks by genre (using Essentia ML)

First scan takes ~2-5 seconds per track.

## 3. View Your Library

```bash
# Overall stats
dj stats

# Top genres
dj stats --group-by tags

# Top artists
dj stats --group-by artist
```

## 4. Search Tracks

```bash
# By genre
dj search --tags "tech house"

# By BPM range
dj search --bpm-min 124 --bpm-max 128

# By artist
dj search --artist "Fred Again"

# Natural language (semantic search)
dj search --query "uplifting summer vibes"
```

## 5. Generate Playlists

```bash
# 60-minute tech house set
dj playlist --tags "tech house" --duration 60 --output ~/Desktop/tech-house.m3u

# Energy builder (low to high)
dj playlist --tags house --energy-curve rising --duration 90

# BPM-locked set
dj playlist --tags garage --bpm-min 130 --bpm-max 134 --duration 60
```

## 6. Connect to Claude Desktop (Optional)

See [MCP_SETUP.md](./MCP_SETUP.md) to control your library through AI.

Example prompts:
- "Find me some deep house tracks around 122 BPM"
- "Create a 2-hour afro house playlist and export to my Desktop"
- "What's the most common key in my library?"

## Next Steps

- [CLI Reference](../README.md#cli-reference) - All commands and options
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues
- [MCP Setup](./MCP_SETUP.md) - Claude Desktop integration

## Quick Reference

| Command | Description |
|---------|-------------|
| `dj scan <dir>` | Scan directory for music |
| `dj scan <dir> --force` | Re-analyze all tracks |
| `dj scan <dir> --reset` | Clear DB and scan fresh |
| `dj search --tags X` | Find tracks by tag |
| `dj search --query "..."` | Semantic search |
| `dj playlist --tags X` | Generate playlist |
| `dj stats` | Library statistics |
| `dj clean` | Remove orphaned tracks |
| `dj reset` | Clear entire database |
