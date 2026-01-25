"""CLI entry point."""

import click
from rich.console import Console

from dj_catalog.cli.playlist import playlist
from dj_catalog.cli.scan import scan
from dj_catalog.cli.search import search

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="dj-catalog")
def main() -> None:
    """DJ Catalog - Music library scanner and playlist generator."""
    pass


main.add_command(scan)
main.add_command(search)
main.add_command(playlist)


if __name__ == "__main__":
    main()
