# ai-crate-digger

AI-powered music library scanner and playlist generator for DJs. Scan your local music files, analyse BPM/key/energy, and generate playlists  -- all from the command line or through an AI assistant.

## What It Does

- **Scans your library**  -- finds all audio files, extracts ID3 metadata, detects duplicates
- **Analyses audio**  -- BPM detection, musical key (+ Camelot wheel), energy, danceability
- **Classifies genres**  -- ML-based genre tagging via Essentia for untagged tracks (optional)
- **Filters and generates playlists**  -- by tag, BPM, key, energy, label, artist
- **Exports**  -- M3U (universal) and Rekordbox XML
- **Connects to AI assistants**  -- MCP server for Claude Desktop, ChatGPT, and any MCP-compatible app

## How It Works

```
Your music files (MP3, FLAC, WAV, AIFF, M4A, OGG)
        │
        ▼
┌─────────────────┐
│   Scanner       │ Discovers audio files, hashes for dedup
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Extractor     │ Reads ID3/FLAC tags (title, artist, genre, label...)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Analyser      │ BPM (Essentia), key + Camelot, energy, danceability
│   (parallel)    │ Genre classification for untagged tracks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Storage       │ SQLite (metadata) + ChromaDB (semantic search vectors)
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌──────────────────────┐
│  CLI  │  │  MCP Server          │
│ crate │  │  Claude / ChatGPT /  │
│       │  │  Cursor / Cline ...  │
└───────┘  └──────────────────────┘
```

Analysis runs in parallel across all CPU cores. A library of 6,000+ tracks takes 45-90 minutes on first scan; subsequent scans are incremental (new files only).

## Requirements

- Python 3.11+
- FFmpeg

## Installation

```bash
git clone https://github.com/sitorush/ai-crate-digger.git
cd ai-crate-digger
uv sync
```

> **No uv?** Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

See [Installation Guide](docs/INSTALLATION.md) for platform-specific instructions and optional Essentia setup.

## Quick Start

```bash
# Scan your library
crate scan ~/Music

# View stats
crate stats --group-by tags

# Search tracks
crate search --tags "tech house" --bpm-min 126 --bpm-max 130

# Generate a playlist
crate playlist --tags techno --duration 60 --output ~/Desktop/set.m3u

# Export for Rekordbox
crate playlist --tags techno --output ~/Desktop/set.xml --format rekordbox
```

## Identify Tracks in a Recorded Mix

Recorded a set and forgot the tracklist? Fingerprint your library once, then match the recording against it.

```bash
# Fingerprint your library (only new tracks after the first run)
crate fingerprint

# Identify what was played in a recording
crate identify ~/Music/mixes/friday-set.mp3

# Or use the newest recording in ~/Music/mixes
crate identify
```

It tolerates tempo changes of up to about 8%, noise and overlapping transitions, and lists spans it could not match (usually tracks that are not in your library). From an AI assistant, ask it to identify your latest recording and build a playlist from it. See [MCP tools](docs/mcp-tools.md#mix-identification-tools).

**What to expect.** One measured example: fingerprinting a library of about 7,000 tracks (550 hours of audio) took roughly 5 minutes on a 14-core Mac and added about 1.4 GB to the database. Identifying a 99-minute stereo mix took about 7 minutes and peaked at around 7.5 GB of RAM, so close other heavy apps for long mixes. Your numbers will vary with CPU, library size and mix length.

**Things to know.**
- Only tracks in your library can be identified. Anything else shows up as an unmatched span.
- `crate identify` prints every matched stretch, so one track often appears several times in a row. The assistant tools return the same data.
- Very short samples (one-shots, stems), heavy loops, and a different edit of the same song (extended versus radio) may match partly or not at all.
- Confidence is shown as high, medium or low. Low matches are hidden by default; use `--min-confidence low` to see them.
- The index lives in memory while matching and is capped at about 200 million hashes, roughly 600 hours of audio. See [Troubleshooting](docs/TROUBLESHOOTING.md#mix-identification).

## Connect to an AI Assistant

Ask your AI assistant to manage your music library.

### Claude Desktop

```json
{
  "mcpServers": {
    "ai-crate-digger": {
      "command": "/Users/yourname/ai-crate-digger/.venv/bin/crate",
      "args": ["mcp-server"]
    }
  }
}
```

Replace `/Users/yourname/ai-crate-digger` with the path where you cloned the repo.

Config file: `~/Library/Application Support/Claude/claude_desktop_config.json`

Full guide: [docs/MCP_CLAUDE.md](docs/MCP_CLAUDE.md)

### ChatGPT Desktop

Same config, different file: `~/Library/Application Support/OpenAI/ChatGPT/mcp.json`

Full guide: [docs/MCP_CHATGPT.md](docs/MCP_CHATGPT.md)

### Other Apps (Cursor, Cline, Continue, Zed)

Generic guide: [docs/MCP_GENERIC.md](docs/MCP_GENERIC.md)

### Example AI Prompts

- "Search my music library for dark techno around 130 BPM"
- "Make me a 2-hour gym playlist that builds from 124 to 132 BPM"
- "What are my top 5 genres by track count?"
- "Find tracks similar to Amelie Lens  -- hypnotic, industrial feel"
- "Export a peak-time techno set to my Desktop in Rekordbox format"
- "Identify the tracks in my latest recording and build a playlist from them"

## CLI Reference

| Command | Description |
|---------|-------------|
| `crate scan <dir>` | Scan directory for music files |
| `crate scan <dir> --force` | Re-analyse all tracks |
| `crate scan <dir> --reset` | Clear database and scan fresh |
| `crate search --tags X` | Find tracks by tag |
| `crate search --query "..."` | Semantic (natural language) search |
| `crate playlist --tags X` | Generate playlist |
| `crate stats` | Library statistics |
| `crate fingerprint` | Fingerprint tracks so mixes can be identified (new tracks only) |
| `crate fingerprint --force` | Re-fingerprint every track |
| `crate identify [file]` | Identify tracks in a recorded mix (newest recording in the inbox if no file) |
| `crate clean` | Remove tracks for deleted files |
| `crate reset` | Clear entire database |
| `crate mcp-server` | Start MCP server for AI apps |

### Scan

```bash
crate scan ~/Music                    # Scan with audio analysis (default)
crate scan ~/Music --no-analyze       # Metadata only (faster)
crate scan ~/Music --force            # Re-analyse all files
crate scan ~/Music --workers 4        # Limit parallel workers
crate scan ~/Music --workers 1        # Sequential -- stable on Apple Silicon if crashes occur
```

### Search

```bash
crate search --tags techno --tags dark
crate search --bpm-min 128 --bpm-max 134
crate search --artist "deadmau5"
crate search --key Am
crate search --query "hypnotic driving techno"
```

### Playlist

```bash
crate playlist --tags house --duration 60
crate playlist --tags techno --bpm-min 130 --bpm-max 136
crate playlist --tags house --exclude-tags vocal --energy-min 0.7
crate playlist --tags techno --output ~/Desktop/set.m3u
crate playlist --tags techno --output ~/Desktop/set.xml --format rekordbox
```

### Fingerprint and identify

```bash
crate fingerprint                               # new tracks only
crate fingerprint --force                       # redo every track
crate fingerprint --workers 4                   # limit parallel workers
crate identify ~/Music/mixes/set.mp3            # identify a recording
crate identify                                  # newest file in the inbox folder
crate identify set.mp3 --min-confidence low     # include weaker matches
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRATE_DB_PATH` | `~/.ai-crate-digger/catalog.db` | SQLite database path |
| `CRATE_VECTOR_PATH` | `~/.ai-crate-digger/.chroma` | ChromaDB vector store path |
| `CRATE_OUTPUT_PATH` | `~/Downloads` | Default playlist export directory |
| `CRATE_INBOX_PATH` | `~/Music/mixes` | Folder `crate identify` and `identify_mix` use for the newest recording |
| `CRATE_MIX_MIN_SECONDS` | `30` | Recordings shorter than this are rejected |
| `CRATE_MIX_SPEED_RANGE` | `0.08` | Tempo change searched in either direction (0.08 is 8%) |
| `CRATE_MIX_SPEED_STEP` | `0.01` | Tempo search step. Smaller finds more but is slower |
| `CRATE_MIX_HIGH_SUPPORT` | `0.12` | Match strength for a high confidence band |
| `CRATE_MIX_MEDIUM_SUPPORT` | `0.05` | Match strength for a medium confidence band |
| `CRATE_MIX_LOW_SUPPORT` | `0.02` | Minimum match strength to report at all |

The `CRATE_MIX_*` strengths were tuned on synthetic audio. If real mixes show false matches, raise `CRATE_MIX_MEDIUM_SUPPORT`; if known tracks are missed, lower the low and medium values and use `--min-confidence low`.

## Development

```bash
uv run pytest           # Run tests
uv run mypy src/        # Type check
uv run ruff check src/  # Lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT
