"""Tests for MCP tools."""

from ai_crate_digger.mcp.server import create_server


class TestMCPServer:
    """Tests for MCP server creation."""

    def test_creates_server(self) -> None:
        """Can create MCP server."""
        server = create_server()
        assert server is not None
        assert server.name == "dj-catalog"
