"""MCP tool definitions for DJ Catalog."""

from collections import Counter
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from dj_catalog.core.config import Settings, get_settings
from dj_catalog.core.models import Track
from dj_catalog.playlist import PlaylistOptions, TrackFilter, export_playlist, generate_playlist
from dj_catalog.playlist.generator import Playlist
from dj_catalog.storage import Database, VectorStore


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
                description="Generate a DJ playlist from criteria",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Playlist name"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Include tracks with tags",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Target duration",
                            "default": 60,
                        },
                        "bpm_min": {"type": "number", "description": "Minimum BPM"},
                        "bpm_max": {"type": "number", "description": "Maximum BPM"},
                        "harmonic_mixing": {
                            "type": "boolean",
                            "description": "Enable harmonic mixing",
                            "default": True,
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
                name="export_playlist",
                description="Export a playlist to file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tracks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file hashes",
                        },
                        "name": {"type": "string", "description": "Playlist name"},
                        "output_path": {"type": "string", "description": "Output file path"},
                        "format": {
                            "type": "string",
                            "enum": ["m3u", "rekordbox"],
                            "default": "m3u",
                        },
                    },
                    "required": ["tracks", "output_path"],
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
            if name == "export_playlist":
                return await _export_playlist(db, arguments)
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


async def _export_playlist(db: Database, args: dict[str, Any]) -> list[TextContent]:
    """Handle export_playlist tool."""
    hashes: list[str] = args["tracks"]
    maybe_tracks = [db.get_track_by_hash(h) for h in hashes]
    tracks: list[Track] = [t for t in maybe_tracks if t is not None]

    playlist = Playlist(
        name=args.get("name", "Exported Playlist"),
        tracks=tracks,
        total_duration=sum(t.duration_seconds or 0 for t in tracks),
    )

    output_path = Path(args["output_path"])
    export_playlist(playlist, output_path, output_format=args.get("format", "m3u"))

    return [TextContent(type="text", text=f"Exported {len(tracks)} tracks to {output_path}")]
