"""MCP server for Claude Desktop integration."""

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from ai_crate_digger.mcp.tools import register_tools

logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Create and configure MCP server."""
    server = Server("dj-catalog")
    register_tools(server)
    return server


async def run_server() -> None:
    """Run the MCP server."""
    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for MCP server."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
