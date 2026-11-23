"""MCP tools for identifying tracks in recorded DJ mixes."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent, Tool

from ai_crate_digger.core.config import Settings
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.inbox import resolve_mix_path
from ai_crate_digger.fingerprint.indexer import IndexReport, index_library
from ai_crate_digger.fingerprint.jobs import ProgressFn, get_job_registry
from ai_crate_digger.fingerprint.matcher import MixResult
from ai_crate_digger.fingerprint.report import BAND_RANK, describe_result, playlist_hashes
from ai_crate_digger.storage import Database

MIX_TOOL_NAMES = frozenset(
    {"index_fingerprints", "identify_mix", "get_job_status", "build_playlist_from_mix"}
)

BuildPlaylist = Callable[[Database, dict[str, Any]], Awaitable[list[TextContent]]]

_CONFIDENCE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["low", "medium", "high"],
    "default": "medium",
    "description": "Hide matches below this confidence",
}


def mix_tool_definitions() -> list[Tool]:
    """Tool definitions for mix identification."""
    return [
        Tool(
            name="index_fingerprints",
            description=(
                "Fingerprint library tracks so mixes can be matched against them. Only "
                "tracks without a fingerprint are processed unless force is set. Runs in the "
                "background and returns a job_id; poll get_job_status for progress."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Re-fingerprint every track, not just new ones",
                    },
                },
            },
        ),
        Tool(
            name="identify_mix",
            description=(
                "Identify which library tracks were played in a recorded DJ mix and when. "
                "Takes a local file path, or 'latest' for the newest recording in the inbox "
                "folder. Runs in the background and returns a job_id; poll get_job_status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "default": "latest",
                        "description": "Path to the mix recording, or 'latest'",
                    },
                },
            },
        ),
        Tool(
            name="get_job_status",
            description=(
                "Get progress of an index_fingerprints or identify_mix job. When an "
                "identify_mix job is done, returns the timeline of identified tracks "
                "(start, end, artist, title, confidence, tempo shift) and unmatched spans."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "min_confidence": _CONFIDENCE_SCHEMA,
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="build_playlist_from_mix",
            description=(
                "Export the tracks found by a finished identify_mix job as a playlist, in "
                "the order they were played."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "name": {"type": "string", "description": "Playlist name"},
                    "min_confidence": _CONFIDENCE_SCHEMA,
                    "dedupe": {
                        "type": "boolean",
                        "default": True,
                        "description": "List a track once even if it was played twice",
                    },
                    "format": {"type": "string", "enum": ["m3u", "rekordbox"], "default": "m3u"},
                    "output_path": {"type": "string", "description": "Where to write the file"},
                },
                "required": ["job_id", "name"],
            },
        ),
    ]


def _json(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2))]


def _error(message: str) -> list[TextContent]:
    return _json({"success": False, "error": message})


def _index_fingerprints(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    force = bool(args.get("force", False))

    def work(progress: ProgressFn) -> IndexReport:
        db = Database(settings.db_path)
        try:
            db.init()
            return index_library(
                db,
                force=force,
                workers=settings.max_workers,
                on_progress=lambda done, total: progress(done / total if total else 1.0),
            )
        finally:
            db.close()

    job = get_job_registry().submit("index", "library", work)
    return _json(
        {"success": True, "job_id": job.job_id, "status": job.status, "next": "get_job_status"}
    )


def _identify_mix(settings: Settings, args: dict[str, Any]) -> list[TextContent]:
    try:
        path = resolve_mix_path(args.get("path"), settings.inbox_path)
    except FileNotFoundError as exc:
        return _error(str(exc))

    def work(progress: ProgressFn) -> MixResult:
        return identify_mix_file(path, settings, progress)

    job = get_job_registry().submit("mix", str(path), work)
    return _json(
        {
            "success": True,
            "job_id": job.job_id,
            "status": job.status,
            "path": str(path),
            "next": "get_job_status",
        }
    )


def _get_job_status(db: Database, args: dict[str, Any]) -> list[TextContent]:
    job = get_job_registry().get(args["job_id"])
    if job is None:
        return _error(f"Unknown job_id: {args['job_id']}")
    min_confidence = args.get("min_confidence", "medium")
    if min_confidence not in BAND_RANK:
        return _error(f"min_confidence must be one of {sorted(BAND_RANK)}")

    payload: dict[str, Any] = {
        "success": True,
        "job_id": job.job_id,
        "kind": job.kind,
        "label": job.label,
        "status": job.status,
        "progress": round(job.progress, 3),
    }
    if job.status == "failed":
        payload["error"] = job.error
    elif isinstance(job.result, MixResult):
        payload.update(describe_result(job.result, db, min_confidence))
    elif isinstance(job.result, IndexReport):
        payload["report"] = {
            "indexed": job.result.indexed,
            "skipped": job.result.skipped,
            "failed": [{"path": p, "error": e} for p, e in job.result.failed[:20]],
            "failed_total": len(job.result.failed),
        }
    return _json(payload)


async def _build_playlist_from_mix(
    db: Database, args: dict[str, Any], build_playlist: BuildPlaylist
) -> list[TextContent]:
    job = get_job_registry().get(args["job_id"])
    if job is None:
        return _error(f"Unknown job_id: {args['job_id']}")
    if not isinstance(job.result, MixResult):
        return _error(f"Job {job.job_id} has no mix result yet (status: {job.status})")
    min_confidence = args.get("min_confidence", "medium")
    if min_confidence not in BAND_RANK:
        return _error(f"min_confidence must be one of {sorted(BAND_RANK)}")

    hashes = playlist_hashes(job.result, min_confidence, dedupe=args.get("dedupe", True))
    if not hashes:
        return _error("No identified tracks at that confidence level")

    build_args: dict[str, Any] = {
        "name": args["name"],
        "hashes": hashes,
        "format": args.get("format", "m3u"),
        "validate": False,  # mix order is what was played, not a harmonic suggestion
    }
    if "output_path" in args:
        build_args["output_path"] = args["output_path"]
    return await build_playlist(db, build_args)


async def call_mix_tool(
    name: str,
    db: Database,
    settings: Settings,
    args: dict[str, Any],
    build_playlist: BuildPlaylist,
) -> list[TextContent]:
    """Dispatch a mix identification tool call."""
    if name == "index_fingerprints":
        return _index_fingerprints(settings, args)
    if name == "identify_mix":
        return _identify_mix(settings, args)
    if name == "get_job_status":
        return _get_job_status(db, args)
    if name == "build_playlist_from_mix":
        return await _build_playlist_from_mix(db, args, build_playlist)
    return _error(f"Unknown tool: {name}")
