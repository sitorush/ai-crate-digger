# DJ Catalog

A world-class CLI tool for scanning music libraries, analyzing audio, and generating DJ playlists with harmonic mixing.

## Features

- **Music Library Scanning**: Discover audio files (MP3, FLAC, M4A, WAV, etc.)
- **Metadata Extraction**: Parse ID3 tags, album art, release dates, labels
- **Audio Analysis**: BPM detection, key detection, energy/danceability scoring
- **Incremental Scanning**: Only process new files on re-scan
- **Tag-Based Filtering**: Include/exclude by genre, mood, era
- **Harmonic Mixing**: Generate playlists using the Camelot wheel
- **Multiple Export Formats**: M3U and Rekordbox XML
- **Semantic Search**: Natural language track search via ChromaDB
- **Claude Desktop Integration**: MCP server for AI-assisted playlist curation

## Installation

```bash
# Clone the repository
git clone https://github.com/youruser/dj-catalog.git
cd dj-catalog

# Install with uv
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

## Quick Start

### 1. Scan your music library

```bash
# Scan with audio analysis (BPM, key, energy)
dj scan ~/Music/mp3

# Scan without analysis (faster, metadata only)
dj scan ~/Music/mp3 --no-analyze

# Force re-scan all files
dj scan ~/Music/mp3 --force
```

### 2. Search your library

```bash
# Search by tags
dj search --tags techno --tags dark

# Search by BPM range
dj search --bpm-min 125 --bpm-max 135

# Search by artist
dj search --artist "deadmau5"

# Semantic search (natural language)
dj search "dark industrial techno" --semantic
```

### 3. Generate playlists

```bash
# Generate a 60-minute techno set
dj playlist --tags techno --duration 60

# High-energy house without vocals
dj playlist --tags house --exclude-tags vocal --energy-min 0.7

# Export to M3U
dj playlist --tags techno -o my_set.m3u

# Export to Rekordbox XML
dj playlist --tags techno -o my_set.xml --format rekordbox
```

### 4. View library stats

```bash
# Stats by genre/tag
dj stats --by tags

# Stats by artist
dj stats --by artist

# Stats by key
dj stats --by key
```

## Claude Desktop Integration

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "dj-catalog": {
      "command": "dj",
      "args": ["mcp-server"]
    }
  }
}
```

Then ask Claude to:
- "Search my music library for dark techno tracks around 130 BPM"
- "Generate a 2-hour melodic house playlist"
- "Show me stats about my music collection"

## CLI Reference

| Command | Description |
|---------|-------------|
| `dj scan <dir>` | Scan directory for music files |
| `dj search` | Search tracks by criteria |
| `dj playlist` | Generate and export playlists |
| `dj stats` | Show library statistics |
| `dj mcp-server` | Run MCP server for Claude Desktop |

### Scan Options

- `--analyze/--no-analyze`: Run audio analysis (default: on)
- `--force`: Re-process all files, not just new ones
- `--workers N`: Number of parallel analysis workers

### Search Options

- `--tags/-t`: Filter by tags (can be repeated)
- `--bpm-min/--bpm-max`: BPM range
- `--key/-k`: Musical key (e.g., Am, C)
- `--artist/-a`: Artist name (partial match)
- `--label/-l`: Record label (partial match)
- `--rating-min`: Minimum rating (1-5)
- `--semantic/-s`: Use semantic search

### Playlist Options

- `--name/-n`: Playlist name
- `--duration/-d`: Target duration in minutes
- `--tags/-t`: Include tags
- `--exclude-tags`: Exclude tags
- `--bpm-min/--bpm-max`: BPM range
- `--key/-k`: Starting key
- `--no-harmonic`: Disable harmonic mixing
- `--output/-o`: Export file path
- `--format/-f`: Export format (m3u, rekordbox)

## Development

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=dj_catalog

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

## License

MIT
