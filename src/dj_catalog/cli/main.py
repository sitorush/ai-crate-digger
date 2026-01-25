"""CLI entry point."""

import click
from rich.console import Console

from dj_catalog.cli.playlist import playlist
from dj_catalog.cli.scan import scan
from dj_catalog.cli.search import search
from dj_catalog.cli.stats import stats

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="dj-catalog")
def main() -> None:
    """DJ Catalog - Music library scanner and playlist generator."""
    pass


main.add_command(scan)
main.add_command(search)
main.add_command(playlist)
main.add_command(stats)


@click.command("mcp-server")
def mcp_server() -> None:
    """Run MCP server for Claude Desktop."""
    from dj_catalog.mcp.server import main as mcp_main

    mcp_main()


main.add_command(mcp_server)


if __name__ == "__main__":
    main()
