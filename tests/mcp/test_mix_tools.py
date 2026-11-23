"""Tests for the mix identification MCP tools."""

import json
import time
from typing import Any

import pytest

from ai_crate_digger.mcp.mix_tools import MIX_TOOL_NAMES, call_mix_tool, mix_tool_definitions
from ai_crate_digger.mcp.tools import _build_playlist
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, make_track, place, stretch_pitch


async def _call(library: Library, name: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await call_mix_tool(name, library.db, library.settings, args, _build_playlist)
    payload: dict[str, Any] = json.loads(result[0].text)
    return payload


async def _wait_done(library: Library, job_id: str) -> dict[str, Any]:
    deadline = time.time() + 60
    while time.time() < deadline:
        status = await _call(library, "get_job_status", {"job_id": job_id})
        if status["status"] in ("done", "failed"):
            return status
        time.sleep(0.05)
    pytest.fail("job did not finish")


def test_tool_definitions_match_dispatch_names() -> None:
    assert {tool.name for tool in mix_tool_definitions()} == set(MIX_TOOL_NAMES)


async def test_full_flow_from_indexing_to_playlist(library: Library) -> None:
    started = await _call(library, "index_fingerprints", {})
    indexed = await _wait_done(library, started["job_id"])
    assert indexed["report"]["indexed"] == 4

    mix = place(library.audio["hash1"][: 30 * SR], 0, 70) + place(
        stretch_pitch(library.audio["hash3"][: 30 * SR], 1.02), 35, 70
    )
    mix_path = write_wav(library.root / "friday.wav", mix)
    started = await _call(library, "identify_mix", {"path": str(mix_path)})
    assert started["success"] is True

    status = await _wait_done(library, started["job_id"])
    assert status["status"] == "done"
    assert [(s["hash"], s["artist"]) for s in status["segments"]] == [
        ("hash1", "Artist1"),
        ("hash3", "Artist3"),
    ]
    assert status["unmatched"] == []

    output = library.root / "friday.m3u"
    built = await call_mix_tool(
        "build_playlist_from_mix",
        library.db,
        library.settings,
        {"job_id": started["job_id"], "name": "Friday", "output_path": str(output)},
        _build_playlist,
    )
    assert json.loads(built[0].text)["success"] is True
    text = output.read_text()
    assert text.index("track1.wav") < text.index("track3.wav")


async def test_identify_latest_uses_the_inbox(library: Library) -> None:
    await _wait_done(library, (await _call(library, "index_fingerprints", {}))["job_id"])
    inbox = library.settings.inbox_path
    inbox.mkdir()
    write_wav(inbox / "recording.wav", place(library.audio["hash0"][: 30 * SR], 0, 32))

    started = await _call(library, "identify_mix", {"path": "latest"})
    assert started["path"].endswith("recording.wav")
    status = await _wait_done(library, started["job_id"])
    assert [s["hash"] for s in status["segments"]] == ["hash0"]


async def test_failed_job_reports_its_error(library: Library) -> None:
    path = write_wav(library.root / "mix.wav", make_track(1, 40))
    started = await _call(library, "identify_mix", {"path": str(path)})
    status = await _wait_done(library, started["job_id"])
    assert status["status"] == "failed"
    assert "index_fingerprints" in status["error"]


async def test_missing_file_is_an_immediate_error(library: Library) -> None:
    result = await _call(library, "identify_mix", {"path": str(library.root / "nope.mp3")})
    assert result["success"] is False
    assert "not found" in result["error"]


async def test_unknown_job_and_bad_confidence_are_errors(library: Library) -> None:
    unknown = await _call(library, "get_job_status", {"job_id": "nope"})
    assert unknown["success"] is False

    started = await _call(library, "index_fingerprints", {})
    bad = await _call(
        library, "get_job_status", {"job_id": started["job_id"], "min_confidence": "great"}
    )
    assert bad["success"] is False
    await _wait_done(library, started["job_id"])


async def test_build_playlist_needs_a_finished_mix_job(library: Library) -> None:
    started = await _call(library, "index_fingerprints", {})
    result = await _call(
        library, "build_playlist_from_mix", {"job_id": started["job_id"], "name": "x"}
    )
    assert result["success"] is False
    await _wait_done(library, started["job_id"])


async def test_server_lists_and_routes_the_mix_tools(
    library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp import types
    from mcp.server import Server

    from ai_crate_digger.core.config import get_settings
    from ai_crate_digger.mcp.tools import register_tools

    monkeypatch.setenv("CRATE_DB_PATH", str(library.settings.db_path))
    monkeypatch.setenv("CRATE_MAX_WORKERS", "1")
    get_settings.cache_clear()
    try:
        server = Server("test")
        register_tools(server)

        listed = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        assert isinstance(listed.root, types.ListToolsResult)
        names = {tool.name for tool in listed.root.tools}
        assert names >= MIX_TOOL_NAMES

        called = await server.request_handlers[types.CallToolRequest](
            types.CallToolRequest(
                method="tools/call",
                params=types.CallToolRequestParams(
                    name="get_job_status", arguments={"job_id": "nope"}
                ),
            )
        )
        assert isinstance(called.root, types.CallToolResult)
        content = called.root.content[0]
        assert isinstance(content, types.TextContent)
        assert "Unknown job_id" in content.text
    finally:
        get_settings.cache_clear()
