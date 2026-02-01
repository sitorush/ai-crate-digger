"""MCP tool definitions for DJ Catalog."""

import json  # noqa: F401 - required for future MCP tool usage
import platform
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from dj_catalog.core.config import Settings, get_settings
from dj_catalog.core.models import Track
from dj_catalog.playlist import (
    PlaylistOptions,
    TrackFilter,
    export_playlist,
    generate_playlist,
)
from dj_catalog.playlist.generator import Playlist
from dj_catalog.storage import Database, VectorStore


def _compact_track(track: Track) -> dict[str, Any]:
    """Compact track representation for validation issues."""
    return {"title": track.title, "bpm": track.bpm, "key": track.key_camelot, "tags": track.tags}


def _strip_remix_markers(title: str) -> str:
    """Strip parentheses and brackets, normalize whitespace.

    Examples:
        "Track (Remix)" -> "track"
        "Track [VIP]" -> "track"
        "Track  (Extended)  [2023]" -> "track"
    """
    stripped = re.sub(r"[\(\[].*?[\)\]]", "", title)
    return " ".join(stripped.split()).lower()


def _sort_candidates(tracks: list[Track], sort_by: str) -> list[Track]:
    """Sort candidate tracks by specified criteria."""
    if sort_by == "random":
        shuffled = tracks.copy()
        random.shuffle(shuffled)
        return shuffled
    if sort_by == "bpm_asc":
        return sorted(tracks, key=lambda t: t.bpm or 0)
    if sort_by == "bpm_desc":
        return sorted(tracks, key=lambda t: t.bpm or 0, reverse=True)
    if sort_by == "energy_desc":
        return sorted(tracks, key=lambda t: t.energy or 0, reverse=True)
    if sort_by == "danceability_desc":
        return sorted(tracks, key=lambda t: t.danceability or 0, reverse=True)
    return tracks  # Unknown sort_by, return as-is


def _validate_output_path(path_str: str) -> tuple[Path | None, str | None]:
    """Validate and resolve output path, returning (resolved_path, error_message).

    Checks that path is on the local machine, not inside Claude Desktop's container.
    Returns (Path, None) on success, (None, error_message) on failure.
    """
    home = Path.home()
    system = platform.system()

    # Expand ~ to home directory
    path = Path(path_str).expanduser()

    # Container paths that indicate Claude Desktop sandbox (not local machine)
    # These are Linux paths used by Claude Desktop's container
    container_prefixes = ["/mnt/", "/home/claude", "/tmp/sandbox"]

    if any(path_str.startswith(p) for p in container_prefixes):
        if system == "Windows":
            example = f"{home}\\Desktop\\playlist.m3u"
        else:
            example = f"{home}/Desktop/playlist.m3u"

        return None, (
            "ERROR: Invalid path - use a path on your LOCAL machine, not Claude's container.\n"
            "The MCP server runs on YOUR computer, not inside Claude Desktop.\n\n"
            f"Your system: {system}\n"
            f"Your home: {home}\n\n"
            "Example paths:\n"
            f"  {example}\n"
            "  ~/Desktop/playlist.m3u"
        )

    # On Windows, ensure path has a drive letter or starts with ~ or is relative
    # If it looks like a Unix absolute path on Windows, it's wrong
    if system == "Windows" and path_str.startswith("/") and not path_str.startswith("//"):
        return None, (
            f"ERROR: Unix-style path on Windows. Use Windows paths.\n"
            f"Example: {home}\\Desktop\\playlist.m3u"
        )

    return path, None


def _get_example_path(filename: str = "playlist.m3u") -> str:
    """Get an example path appropriate for the current OS."""
    home = Path.home()
    if platform.system() == "Windows":
        return f"{home}\\Desktop\\{filename}"
    return f"{home}/Desktop/{filename}"


def register_tools(server: Server) -> None:
    """Register all tools with the MCP server."""

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="search_tracks",
                description="Search music library by criteria",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by tags",
                        },
                        "artist": {"type": "string", "description": "Filter by artist"},
                        "bpm_min": {"type": "number", "description": "Minimum BPM"},
                        "bpm_max": {"type": "number", "description": "Maximum BPM"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 20,
                        },
                    },
                },
            ),
            Tool(
                name="generate_playlist",
                description=(
                    "Generate a DJ playlist from criteria. "
                    "Optionally export to M3U or Rekordbox XML."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Playlist name"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Include tracks with tags (e.g. ['Afro House', 'Tech House'])"
                            ),
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Target duration in minutes",
                            "default": 60,
                        },
                        "bpm_min": {"type": "number", "description": "Minimum BPM"},
                        "bpm_max": {"type": "number", "description": "Maximum BPM"},
                        "harmonic_mixing": {
                            "type": "boolean",
                            "description": "Enable harmonic mixing",
                            "default": True,
                        },
                        "output_path": {
                            "type": "string",
                            "description": (
                                "Export path on LOCAL machine "
                                "(e.g. ~/Desktop/playlist.m3u). "
                                "NOT container paths like /mnt/ or /home/claude/. "
                                "Use .m3u for M3U or .xml for Rekordbox."
                            ),
                        },
                    },
                },
            ),
            Tool(
                name="get_stats",
                description="Get library statistics",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "enum": ["tags", "artist", "label", "key"],
                            "default": "tags",
                        },
                    },
                },
            ),
            Tool(
                name="get_track_details",
                description="Get full details for a specific track by title, artist, or hash",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Track title (partial match)"},
                        "artist": {"type": "string", "description": "Artist name (partial match)"},
                        "hash": {
                            "type": "string",
                            "description": "File hash (from search results)",
                        },
                    },
                },
            ),
            Tool(
                name="export_playlist",
                description=(
                    "Export a playlist to file. IMPORTANT: output_path must be on "
                    "the LOCAL machine (e.g. ~/Desktop/), NOT Claude container "
                    "paths like /mnt/ or /home/claude/"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tracks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file hashes (full or partial prefix)",
                        },
                        "name": {"type": "string", "description": "Playlist name"},
                        "output_path": {
                            "type": "string",
                            "description": (
                                "Output path on LOCAL machine (e.g. ~/Desktop/playlist.m3u)"
                            ),
                        },
                        "format": {
                            "type": "string",
                            "enum": ["m3u", "rekordbox"],
                            "default": "m3u",
                        },
                    },
                    "required": ["tracks", "output_path"],
                },
            ),
            Tool(
                name="reset_database",
                description=(
                    "Reset the database - delete all tracks and start fresh. Use with caution!"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true to confirm reset",
                        },
                    },
                    "required": ["confirm"],
                },
            ),
            Tool(
                name="scan_library",
                description="Scan a directory for music files and add them to the library",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path to scan (e.g. /Users/tom/Music)",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Re-analyze all files, not just new ones",
                            "default": False,
                        },
                    },
                    "required": ["directory"],
                },
            ),
            Tool(
                name="clean_orphans",
                description="Remove tracks from database whose files no longer exist",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        settings = get_settings()
        db = Database(settings.db_path)
        db.init()

        try:
            if name == "search_tracks":
                return await _search_tracks(db, settings, arguments)
            if name == "generate_playlist":
                return await _generate_playlist(db, arguments)
            if name == "get_stats":
                return await _get_stats(db, arguments)
            if name == "get_track_details":
                return await _get_track_details(db, arguments)
            if name == "export_playlist":
                return await _export_playlist(db, arguments)
            if name == "reset_database":
                return await _reset_database(settings, arguments)
            if name == "scan_library":
                return await _scan_library(settings, arguments)
            if name == "clean_orphans":
                return await _clean_orphans(db, settings)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        finally:
            db.close()


async def _search_tracks(
    db: Database, settings: Settings, args: dict[str, Any]
) -> list[TextContent]:
    """Handle search_tracks tool."""
    query = args.get("query")
    limit = args.get("limit", 20)

    tracks: list[Track]
    if query:
        # Semantic search
        vector_store = VectorStore(settings.vector_path)
        vector_store.init()
        hashes = vector_store.search(query, limit=limit)
        maybe_tracks = [db.get_track_by_hash(h) for h in hashes]
        tracks = [t for t in maybe_tracks if t is not None]
    else:
        # Database search
        tracks = db.search_tracks(
            bpm_min=args.get("bpm_min"),
            bpm_max=args.get("bpm_max"),
            artist=args.get("artist"),
            include_tags=args.get("tags"),
            limit=limit,
        )

    results = []
    for t in tracks:
        results.append(
            f"- {t.title or t.file_path.stem} by {t.artist or 'Unknown'} "
            f"({t.bpm or '?'} BPM, {t.key_camelot or '?'}) [{t.file_hash[:8]}]"
        )

    return [TextContent(type="text", text=f"Found {len(tracks)} tracks:\n" + "\n".join(results))]


async def _generate_playlist(db: Database, args: dict[str, Any]) -> list[TextContent]:
    """Handle generate_playlist tool."""
    tracks = db.get_all_tracks()

    bpm_min = args.get("bpm_min")
    bpm_max = args.get("bpm_max")
    bpm_range = (bpm_min, bpm_max) if bpm_min and bpm_max else None

    filter_ = TrackFilter(
        include_tags=args.get("tags", []),
        bpm_range=bpm_range,
    )

    options = PlaylistOptions(
        duration_minutes=args.get("duration_minutes", 60),
        harmonic_mixing=args.get("harmonic_mixing", True),
    )

    playlist = generate_playlist(
        tracks,
        filter_=filter_,
        options=options,
        name=args.get("name", "Generated Playlist"),
    )

    results = [
        f"Generated playlist: {playlist.name}",
        f"Duration: {playlist.duration_minutes:.1f} minutes",
        f"Tracks ({len(playlist.tracks)}):",
    ]
    for i, t in enumerate(playlist.tracks, 1):
        results.append(
            f"  {i}. {t.title or t.file_path.stem} - {t.artist or 'Unknown'} "
            f"({t.bpm or '?'} BPM, {t.key_camelot or '?'})"
        )

    # Auto-export if output_path provided
    output_path_str = args.get("output_path")
    if output_path_str:
        # Validate and resolve path
        output_path, error = _validate_output_path(output_path_str)
        if error or output_path is None:
            results.append("")
            results.append(error or "Invalid path")
            return [TextContent(type="text", text="\n".join(results))]

        # Determine format from extension
        output_format = "rekordbox" if output_path.suffix.lower() == ".xml" else "m3u"

        try:
            export_playlist(playlist, output_path, output_format=output_format)
            results.append("")
            results.append(f"Exported to: {output_path}")
            results.append(f"Format: {output_format}")
        except PermissionError:
            safe_name = playlist.name.replace(" ", "_").replace("/", "-").replace("\\", "-")
            results.append("")
            results.append(f"ERROR: Permission denied writing to {output_path}")
            results.append(f"Try: {_get_example_path(safe_name + '.m3u')}")
        except OSError as e:
            safe_name = playlist.name.replace(" ", "_").replace("/", "-").replace("\\", "-")
            results.append("")
            results.append(f"ERROR: Failed to write file: {e}")
            results.append(
                "Make sure the path exists on the local machine (not inside Claude Desktop)."
            )
            results.append(f"Try: {_get_example_path(safe_name + '.m3u')}")

    return [TextContent(type="text", text="\n".join(results))]


async def _get_stats(db: Database, args: dict[str, Any]) -> list[TextContent]:
    """Handle get_stats tool."""
    tracks = db.get_all_tracks()
    total = len(tracks)

    if not tracks:
        return [TextContent(type="text", text="No tracks in database")]

    group_by = args.get("group_by", "tags")
    counter: Counter[str] = Counter()

    if group_by == "tags":
        for t in tracks:
            for tag in t.tags:
                counter[tag] += 1
    elif group_by == "artist":
        for t in tracks:
            if t.artist:
                counter[t.artist] += 1
    elif group_by == "label":
        for t in tracks:
            if t.label:
                counter[t.label] += 1
    elif group_by == "key":
        for t in tracks:
            if t.key_camelot:
                counter[t.key_camelot] += 1

    results = [f"Library: {total} tracks", f"Top 10 by {group_by}:"]
    for item, count in counter.most_common(10):
        results.append(f"  {item}: {count} ({100 * count // total}%)")

    return [TextContent(type="text", text="\n".join(results))]


async def _get_track_details(db: Database, args: dict[str, Any]) -> list[TextContent]:
    """Handle get_track_details tool."""
    hash_prefix = args.get("hash")
    title = args.get("title")
    artist = args.get("artist")

    track: Track | None = None

    # Search by hash first (most specific)
    if hash_prefix:
        all_tracks = db.get_all_tracks()
        for t in all_tracks:
            if t.file_hash and t.file_hash.startswith(hash_prefix):
                track = t
                break

    # Search by title/artist
    if not track and (title or artist):
        # search_tracks doesn't support title, so we filter manually
        all_tracks = db.get_all_tracks()
        for t in all_tracks:
            title_match = not title or (t.title and title.lower() in t.title.lower())
            artist_match = not artist or (t.artist and artist.lower() in t.artist.lower())
            if title_match and artist_match:
                track = t
                break

    if not track:
        return [TextContent(type="text", text="Track not found")]

    # Format all available properties
    details = [
        f"=== {track.title or 'Unknown Title'} ===",
        "",
        "FILE INFO:",
        f"  Path: {track.file_path}",
        f"  Hash: {track.file_hash}",
        f"  Codec: {track.codec or 'unknown'}",
        f"  Bitrate: {track.bitrate or '?'} kbps",
        f"  Sample Rate: {track.sample_rate or '?'} Hz",
        (
            f"  Duration: {track.duration_seconds:.1f}s "
            f"({track.duration_seconds // 60:.0f}m {track.duration_seconds % 60:.0f}s)"
            if track.duration_seconds
            else "  Duration: unknown"
        ),
        "",
        "METADATA:",
        f"  Title: {track.title or 'unknown'}",
        f"  Artist: {track.artist or 'unknown'}",
        f"  Album: {track.album or 'unknown'}",
        f"  Album Artist: {track.album_artist or 'unknown'}",
        f"  Track #: {track.track_number or 'unknown'}",
        f"  Label: {track.label or 'unknown'}",
        f"  Year: {track.year or 'unknown'}",
        f"  Comment: {track.comment or 'none'}",
        "",
        "AUDIO ANALYSIS:",
        f"  BPM: {track.bpm:.1f}" if track.bpm else "  BPM: not analyzed",
        f"  Key: {track.key or 'unknown'} ({track.key_camelot or '?'})",
        f"  Energy: {track.energy:.2f}" if track.energy else "  Energy: not analyzed",
        f"  Danceability: {track.danceability:.2f}"
        if track.danceability
        else "  Danceability: not analyzed",
        "",
        "CLASSIFICATION:",
        f"  Tags: {', '.join(track.tags) if track.tags else 'none'}",
        f"  Rating: {'★' * (track.rating or 0)}{'☆' * (5 - (track.rating or 0))}",
    ]

    return [TextContent(type="text", text="\n".join(details))]


async def _export_playlist(db: Database, args: dict[str, Any]) -> list[TextContent]:
    """Handle export_playlist tool."""
    output_path_str = args["output_path"]

    # Validate and resolve path
    output_path, error = _validate_output_path(output_path_str)
    if error or output_path is None:
        return [TextContent(type="text", text=error or "Invalid path")]

    hashes: list[str] = args["tracks"]

    # Look up tracks by hash (with partial match support)
    all_tracks = db.get_all_tracks()
    tracks: list[Track] = []
    not_found: list[str] = []

    for h in hashes:
        found = False
        for t in all_tracks:
            if t.file_hash and t.file_hash.startswith(h):
                tracks.append(t)
                found = True
                break
        if not found:
            not_found.append(h)

    if not tracks:
        return [TextContent(type="text", text=f"No tracks found for hashes: {hashes}")]

    playlist = Playlist(
        name=args.get("name", "Exported Playlist"),
        tracks=tracks,
        total_duration=sum(t.duration_seconds or 0 for t in tracks),
    )

    try:
        export_playlist(playlist, output_path, output_format=args.get("format", "m3u"))
        result = f"Exported {len(tracks)} tracks to {output_path}"
        if not_found:
            result += f"\n\nWarning: {len(not_found)} hashes not found: {not_found[:5]}"
        return [TextContent(type="text", text=result)]
    except PermissionError:
        return [
            TextContent(
                type="text",
                text=(
                    f"ERROR: Permission denied writing to {output_path}\nTry: {_get_example_path()}"
                ),
            )
        ]
    except OSError as e:
        return [
            TextContent(
                type="text",
                text=(
                    f"ERROR: Failed to write file: {e}\n"
                    "Make sure the path is on your local machine.\n"
                    f"Try: {_get_example_path()}"
                ),
            )
        ]


async def _reset_database(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    """Handle reset_database tool."""
    import shutil

    if not args.get("confirm"):
        return [TextContent(type="text", text="Reset cancelled. Set confirm=true to proceed.")]

    deleted = []

    if settings.db_path.exists():
        settings.db_path.unlink()
        deleted.append(f"Database: {settings.db_path}")

    if settings.vector_path.exists():
        shutil.rmtree(settings.vector_path)
        deleted.append(f"Vectors: {settings.vector_path}")

    if deleted:
        return [
            TextContent(
                type="text",
                text="Database reset complete!\nDeleted:\n"
                + "\n".join(f"  - {d}" for d in deleted),
            )
        ]
    return [TextContent(type="text", text="No database files found to delete.")]


async def _scan_library(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    """Handle scan_library tool."""
    from dj_catalog.analysis import ParallelAnalyzer
    from dj_catalog.scanning import compute_file_hash, extract_metadata, scan_directory

    directory = Path(args["directory"])
    force = args.get("force", False)

    if not directory.exists():
        return [TextContent(type="text", text=f"Directory not found: {directory}")]

    db = Database(settings.db_path)
    db.init()

    vector_store = VectorStore(settings.vector_path)
    vector_store.init()

    # Get known hashes
    known_hashes = set() if force else db.get_known_hashes()

    # Discover files
    files = list(scan_directory(directory))

    # Filter to new files
    new_files = []
    for file in files:
        file_hash = compute_file_hash(file)
        if file_hash not in known_hashes:
            new_files.append((file, file_hash))

    if not new_files:
        db.close()
        return [
            TextContent(type="text", text=f"Found {len(files)} files, all already in database.")
        ]

    # Extract and analyze
    tracks = []
    errors = []
    for file, _hash in new_files:
        try:
            track = extract_metadata(file)
            tracks.append(track)
        except Exception as e:
            errors.append(f"{file.name}: {e}")

    # Analyze
    if tracks:
        analyzer = ParallelAnalyzer()
        tracks = list(analyzer.analyze_batch(tracks))

    # Save
    for track in tracks:
        db.upsert_track(track)
        vector_store.add_track(track)

    db.close()

    result = [
        "Scan complete!",
        f"  Directory: {directory}",
        f"  Files found: {len(files)}",
        f"  New tracks processed: {len(tracks)}",
    ]
    if errors:
        result.append(f"  Errors: {len(errors)}")

    return [TextContent(type="text", text="\n".join(result))]


async def _clean_orphans(db: Database, settings: Settings) -> list[TextContent]:
    """Handle clean_orphans tool."""
    from sqlalchemy import select

    from dj_catalog.storage.database import TrackRow

    vector_store = VectorStore(settings.vector_path)
    vector_store.init()

    tracks = db.get_all_tracks()
    orphaned = []

    for track in tracks:
        if not Path(track.file_path).exists():
            orphaned.append(track)

    if not orphaned:
        return [TextContent(type="text", text="No orphaned tracks found.")]

    # Delete orphans
    for track in orphaned:
        stmt = select(TrackRow).where(TrackRow.file_hash == track.file_hash)
        row = db.session.execute(stmt).scalar_one_or_none()
        if row:
            db.delete_track(row.id)
            vector_store.delete_track(track.file_hash)

    return [TextContent(type="text", text=f"Cleaned {len(orphaned)} orphaned tracks.")]
