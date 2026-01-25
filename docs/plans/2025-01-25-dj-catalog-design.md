# DJ Catalog - Design Document

> **For Claude:** This is the design specification. Use superpowers:writing-plans to create the implementation plan from this design.

**Goal:** Build a world-class CLI tool that scans local music files, captures comprehensive metadata, analyzes audio properties, and generates DJ playlists with filtering and Rekordbox export. Includes MCP server for Claude Desktop integration.

**Target Library:** ~6,400 tracks (69GB) in `~/Music/mp3`

---

## 1. Track Model

Comprehensive metadata capture with tag-based classification:

```python
class Track(BaseModel):
    # Identity
    file_path: Path
    file_hash: str

    # Core metadata (from ID3)
    title: str | None
    artist: str | None
    album: str | None
    album_artist: str | None
    track_number: int | None
    duration_seconds: float | None

    # Extended metadata
    label: str | None           # Record label / Publisher
    remixer: str | None         # Parsed from title or tag
    composer: str | None        # Writer/producer credits
    original_artist: str | None # For remixes
    isrc: str | None            # Unique identifier
    release_date: date | None   # Full date, not just year
    year: int | None            # Fallback if no full date
    comment: str | None         # Notes, DJ cue info

    # Audio quality
    bitrate: int | None         # kbps
    sample_rate: int | None     # Hz
    codec: str | None           # mp3, flac, aac

    # Analysis results
    bpm: float | None
    bpm_source: str | None      # "analyzed" or "tag"
    key: str | None             # e.g., "Am"
    key_camelot: str | None     # e.g., "8A"
    energy: float | None        # 0-1
    danceability: float | None  # 0-1

    # Tag-based classification (multiple values)
    tags: list[str] = []        # ["techno", "dark", "driving", "peak"]

    # User-defined
    rating: int | None          # 1-5 stars
    color: str | None           # Visual organization (hex)
    play_count: int = 0

    # System
    analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

---

## 2. Modular Architecture

Domain-driven structure:

```
src/dj_catalog/
├── core/                   # Shared foundations
│   ├── models.py          # Track, Playlist, Tag models
│   ├── config.py          # Settings, paths, defaults
│   ├── exceptions.py      # Custom exceptions
│   └── logging.py         # Structured logging setup
│
├── scanning/              # File discovery & metadata
│   ├── scanner.py         # Find audio files
│   ├── extractor.py       # ID3/FLAC tag extraction
│   └── hasher.py          # Content hashing for dedup
│
├── analysis/              # Audio processing
│   ├── analyzer.py        # Orchestrates analysis
│   ├── bpm.py             # Tempo detection
│   ├── key.py             # Key detection + Camelot
│   ├── energy.py          # Energy/danceability
│   └── parallel.py        # ProcessPoolExecutor wrapper
│
├── storage/               # Persistence layer
│   ├── database.py        # SQLite via SQLAlchemy
│   ├── vectors.py         # ChromaDB for semantic search
│   └── migrations.py      # Schema versioning
│
├── playlist/              # Generation & filtering
│   ├── generator.py       # Playlist building logic
│   ├── filters.py         # Tag/field filtering
│   ├── harmonic.py        # Camelot wheel mixing
│   └── export.py          # M3U, Rekordbox XML
│
├── cli/                   # Command-line interface
│   ├── main.py            # Click app entry
│   ├── scan.py            # scan command
│   ├── search.py          # search command
│   ├── playlist.py        # playlist command
│   └── stats.py           # stats command
│
└── mcp/                   # Claude Desktop integration
    ├── server.py          # MCP server setup
    └── tools.py           # Exposed tool definitions
```

---

## 3. Parallel Processing

For ~6,400 tracks, parallel analysis gives ~3-4x speedup:

```python
class ParallelAnalyzer:
    def __init__(self, max_workers: int | None = None):
        # Default: leave 1 core free for system
        self.max_workers = max_workers or (multiprocessing.cpu_count() - 1)

    async def analyze_batch(
        self,
        tracks: list[Track],
        on_progress: Callable[[Track], None] | None = None,
    ) -> list[Track]:
        """Analyze tracks in parallel using process pool."""

        with ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(analyze_single_track, track): track
                for track in tracks
            }

            results = []
            for future in as_completed(futures):
                analyzed = future.result()
                results.append(analyzed)
                if on_progress:
                    on_progress(analyzed)

            return results
```

**Scan workflow:**
1. Discover files (fast, single-threaded)
2. Hash & check against DB (skip known)
3. Extract metadata (parallel, I/O bound)
4. Analyze audio (parallel, CPU bound)
5. Store results (batched DB writes)

**Performance target:** ~45-90 minutes for full library scan with analysis.

---

## 4. Tag-Based Filtering

Flexible filtering with include/exclude logic:

```python
@dataclass
class TrackFilter:
    """Filter criteria for track selection."""

    # Tag filters (AND logic within, OR between calls)
    include_tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)

    # Field filters
    bpm_range: tuple[float, float] | None = None
    key: str | None = None
    keys: list[str] | None = None
    genre: str | None = None
    label: str | None = None
    artist: str | None = None

    # Exclude filters
    exclude_artists: list[str] = field(default_factory=list)
    exclude_labels: list[str] = field(default_factory=list)

    # Quality filters
    rating_min: int | None = None
    energy_range: tuple[float, float] | None = None
    year_range: tuple[int, int] | None = None
    min_bitrate: int | None = None

    def matches(self, track: Track) -> bool:
        """Check if track passes all filters."""
        ...
```

**CLI examples:**
```bash
# Techno, 128-132 BPM, exclude vocal tracks
dj playlist --tags techno --bpm 128-132 --exclude-tags vocal

# High-energy house, exclude specific labels
dj playlist --tags house --energy-min 0.7 --exclude-labels "Spinnin,Revealed"

# Peak time set from favorite tracks
dj playlist --tags "techno,peak" --rating-min 4 --bpm 130-138

# Only high-quality files
dj playlist --min-bitrate 320 --tags techno
```

---

## 5. MCP Server (Claude Desktop)

Full-access MCP server exposing all operations:

```python
@server.tool()
async def search_tracks(
    query: str | None = None,
    tags: list[str] | None = None,
    artist: str | None = None,
    label: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search music library by criteria."""

@server.tool()
async def generate_playlist(
    description: str,
    tags: list[str] | None = None,
    bpm_range: tuple[float, float] | None = None,
    duration_minutes: int = 60,
    harmonic_mixing: bool = True,
) -> dict:
    """Generate playlist from criteria or natural description."""

@server.tool()
async def get_stats(
    group_by: str = "genre",
) -> dict:
    """Get library statistics."""

@server.tool()
async def scan_directory(
    path: str,
    analyze: bool = True,
) -> dict:
    """Scan directory for new music files."""

@server.tool()
async def export_playlist(
    playlist_id: str,
    format: str = "rekordbox",
    output_path: str | None = None,
) -> dict:
    """Export playlist to file."""
```

**Claude Desktop config:**
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

---

## 6. Quality Standards

**Tools:**
- **Type checking:** mypy strict mode
- **Linting:** ruff (format + lint)
- **Testing:** pytest + pytest-cov (80% minimum)
- **Hooks:** pre-commit framework
- **Docs:** Docstrings + mkdocs-material

**pyproject.toml:**
```toml
[tool.mypy]
strict = true
python_version = "3.11"

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "PT", "RET", "SIM"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--cov=dj_catalog --cov-report=term-missing --cov-fail-under=80"
```

**Pre-commit hooks:**
- ruff format
- ruff lint --fix
- mypy strict

---

## 7. Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI | Click + Rich |
| Audio Analysis | librosa |
| Metadata | mutagen |
| Database | SQLite + SQLAlchemy |
| Vectors | ChromaDB |
| MCP | mcp-python |
| Testing | pytest + pytest-cov |
| Types | mypy strict |
| Linting | ruff |

---

## 8. Export Formats

**M3U (standard):**
```
#EXTM3U
#EXTINF:240,Artist - Title
/path/to/track.mp3
```

**Rekordbox XML:**
```xml
<DJ_PLAYLISTS Version="1.0.0">
  <COLLECTION Entries="N">
    <TRACK TrackID="1" Name="..." Artist="..." AverageBpm="128.00" Tonality="Am" />
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT">
      <NODE Type="1" Name="Playlist Name" Entries="N">
        <TRACK Key="1" />
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
```

---

## 9. Future Enhancements (Post-POC)

- Genre auto-classification ML model
- Mood detection from audio
- Web UI dashboard
- Spotify/Apple Music import
- RAG chat interface
- Waveform visualization
- Cue point detection
