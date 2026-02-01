# DJ Catalog

A world-class CLI tool for scanning music libraries, analyzing audio, and generating DJ playlists with harmonic mixing.

## Features

- **Music Library Scanning**: Discover audio files (MP3, FLAC, M4A, WAV, etc.)
- **Metadata Extraction**: Parse ID3 tags, album art, release dates, labels
- **Audio Analysis**: BPM detection (Essentia), key detection, energy/danceability scoring
- **Automatic Genre Classification**: ML-based genre tagging for untagged tracks
- **Incremental Scanning**: Only process new files on re-scan
- **Tag-Based Filtering**: Include/exclude by genre, mood, era (fuzzy matching)
- **Harmonic Mixing**: Generate playlists using the Camelot wheel
- **Multiple Export Formats**: M3U and Rekordbox XML
- **Semantic Search**: Natural language track search via ChromaDB
- **Claude Desktop Integration**: MCP server for AI-assisted playlist curation

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** - 5-minute quick start
- **[Installation Guide](docs/INSTALLATION.md)** - Detailed setup instructions
- **[Claude Desktop Setup](docs/MCP_SETUP.md)** - MCP server configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and quirks

## Installation

### Quick Install (pip)

```bash
# Create environment
python3.11 -m venv ~/.local/dj-catalog-venv
source ~/.local/dj-catalog-venv/bin/activate

# Install
pip install dj-catalog
```

### From Source (Development)

```bash
git clone https://github.com/youruser/dj-catalog.git
cd dj-catalog

# With uv (recommended)
uv sync
uv run pre-commit install

# Or with pip
pip install -e ".[dev]"
pre-commit install
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

## AI-Friendly Playlist Tools

Three new MCP tools enable AI-driven playlist building with minimal MCP calls:

### get_candidate_pool

Get filtered tracks in compact JSON format optimized for AI selection decisions.

**Parameters:**
- `tags` - Filter by genre tags (OR logic)
- `bpm_min`, `bpm_max` - BPM range filter
- `energy_min`, `energy_max` - Energy range filter (0.0-1.0)
- `key` - Camelot key filter (returns compatible keys only)
- `limit` - Max tracks returned (default: 50)
- `exclude_hashes` - Already-picked track hashes to exclude
- `exclude_stems` - Auto-filter stems/samples (default: true)
- `exclude_unknown` - Auto-filter "Unknown" artists (default: true)
- `sort_by` - Sort criteria: random, bpm_asc, bpm_desc, energy_desc, danceability_desc

**Returns:** JSON array of tracks with compact metadata (hash, artist, title, bpm, key, energy, danceability, tags, duration_sec)

### validate_playlist_order

Validate ordered track list for issues before export.

**Parameters:**
- `hashes` - Ordered track hashes

**Returns:** JSON with validation results:
- Exact duplicates (same hash repeated)
- Same-song duplicates (different remixes)
- BPM jumps (>2.0 BPM change)
- Key clashes (harmonic_distance > 1)
- Tag mismatches (zero overlap)

### build_playlist

Export ordered track list to playlist file with optional validation.

**Parameters:**
- `name` - Playlist name
- `hashes` - Ordered track hashes
- `output_path` - Local path (optional, defaults to ~/Downloads or DJ_CATALOG_OUTPUT_PATH)
- `format` - "m3u" or "rekordbox" (default: m3u)
- `validate` - Run validation before export (default: true)

**Returns:** JSON with success status, output path, track count, duration, and validation results (if enabled)

### Example AI Workflow

```
User: "Make me a 2 hour gym playlist"

# AI fetches candidates per phase
get_candidate_pool(tags=["Nu Disco"], bpm_min=124, bpm_max=127, limit=10)
get_candidate_pool(tags=["House"], bpm_min=126, bpm_max=128, limit=10)
get_candidate_pool(tags=["Tech House"], bpm_min=127, bpm_max=129, limit=10)

# AI selects and orders tracks
validate_playlist_order(hashes=[...])

# AI exports
build_playlist(name="Gym Workout", hashes=[...])

# Total: 5-6 MCP calls instead of 40+
```

### Configuration

Set default output directory via environment variable:

```bash
export DJ_CATALOG_OUTPUT_PATH=~/Music/Playlists
```

Default: `~/Downloads`

## CLI Reference

| Command | Description |
|---------|-------------|
| `dj scan <dir>` | Scan directory for music files |
| `dj search` | Search tracks by criteria |
| `dj playlist` | Generate and export playlists |
| `dj stats` | Show library statistics |
| `dj clean` | Remove tracks for deleted files |
| `dj reset` | Clear entire database |
| `dj mcp-server` | Run MCP server for Claude Desktop |

### Scan Options

- `--analyze/--no-analyze`: Run audio analysis (default: on)
- `--force`: Re-process all files, not just new ones
- `--reset`: Clear database before scanning (fresh start)
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
