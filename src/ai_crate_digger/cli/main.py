"""CLI entry point."""

import click
from rich.console import Console

from ai_crate_digger.cli.playlist import playlist
from ai_crate_digger.cli.scan import scan
from ai_crate_digger.cli.search import search
from ai_crate_digger.cli.stats import stats
from ai_crate_digger.core.config import get_settings

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="ai-crate-digger")
def main() -> None:
    """ai-crate-digger - AI-powered music library scanner and playlist generator."""
    pass


main.add_command(scan)
main.add_command(search)
main.add_command(playlist)
main.add_command(stats)


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def reset(yes: bool) -> None:
    """Reset database - delete all tracks and start fresh."""
    settings = get_settings()

    if not yes:
        console.print("[yellow]This will delete ALL tracks from the database.[/yellow]")
        console.print(f"  Database: {settings.db_path}")
        console.print(f"  Vectors: {settings.vector_path}")
        if not click.confirm("Are you sure?"):
            console.print("[dim]Cancelled[/dim]")
            return

    # Delete database file
    if settings.db_path.exists():
        settings.db_path.unlink()
        console.print(f"[green]Deleted:[/green] {settings.db_path}")

    # Delete vector store directory
    if settings.vector_path.exists():
        import shutil

        shutil.rmtree(settings.vector_path)
        console.print(f"[green]Deleted:[/green] {settings.vector_path}")

    console.print("[bold green]Database reset complete![/bold green]")
    console.print("Run 'crate scan <directory>' to rebuild.")


main.add_command(reset)


@click.command()
def clean() -> None:
    """Remove orphaned tracks (files that no longer exist)."""
    from pathlib import Path

    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    from ai_crate_digger.storage import Database, VectorStore

    settings = get_settings()

    db = Database(settings.db_path)
    db.init()

    vector_store = VectorStore(settings.vector_path)
    vector_store.init()

    tracks = db.get_all_tracks()
    console.print(f"[bold]Checking {len(tracks)} tracks...[/bold]")

    orphaned = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Checking files...", total=len(tracks))
        for track in tracks:
            if not Path(track.file_path).exists():
                orphaned.append(track)
            progress.update(task, advance=1)

    if not orphaned:
        console.print("[green]No orphaned tracks found.[/green]")
        db.close()
        return

    console.print(f"[yellow]Found {len(orphaned)} orphaned tracks[/yellow]")

    # Get track IDs for deletion
    for track in orphaned:
        # Find by hash and delete
        db_track = db.get_track_by_hash(track.file_hash)
        if db_track:
            # Need to get the ID - fetch from database directly
            from sqlalchemy import select

            from ai_crate_digger.storage.database import TrackRow

            stmt = select(TrackRow).where(TrackRow.file_hash == track.file_hash)
            row = db.session.execute(stmt).scalar_one_or_none()
            if row:
                db.delete_track(row.id)
                vector_store.delete_track(track.file_hash)
                console.print(f"[dim]Removed: {track.file_path}[/dim]")

    db.close()
    console.print(f"[bold green]Cleaned {len(orphaned)} orphaned tracks![/bold green]")


main.add_command(clean)


@click.command("mcp-server")
def mcp_server() -> None:
    """Run MCP server for Claude Desktop and other LLM apps."""
    from ai_crate_digger.mcp.server import main as mcp_main

    mcp_main()


main.add_command(mcp_server)


if __name__ == "__main__":
    main()
