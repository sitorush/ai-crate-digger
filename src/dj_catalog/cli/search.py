"""Search command for finding tracks."""

import click
from rich.console import Console
from rich.table import Table

from dj_catalog.core.config import get_settings
from dj_catalog.core.models import Track
from dj_catalog.storage import Database, VectorStore

console = Console()


@click.command()
@click.argument("query", required=False)
@click.option("--tags", "-t", multiple=True, help="Include tracks with these tags")
@click.option("--bpm-min", type=float, help="Minimum BPM")
@click.option("--bpm-max", type=float, help="Maximum BPM")
@click.option("--key", "-k", help="Musical key (e.g., Am, C)")
@click.option("--artist", "-a", help="Artist name (partial match)")
@click.option("--label", "-l", help="Record label (partial match)")
@click.option("--rating-min", type=int, help="Minimum rating (1-5)")
@click.option("--limit", "-n", type=int, default=20, help="Max results")
@click.option("--semantic", "-s", is_flag=True, help="Use semantic search")
def search(
    query: str | None,
    tags: tuple[str, ...],
    bpm_min: float | None,
    bpm_max: float | None,
    key: str | None,
    artist: str | None,
    label: str | None,
    rating_min: int | None,
    limit: int,
    semantic: bool,
) -> None:
    """Search for tracks in the catalog.

    Use natural language QUERY for semantic search, or filter flags.
    """
    settings = get_settings()
    db = Database(settings.db_path)
    db.init()

    tracks: list[Track]
    if semantic and query:
        # Semantic search via ChromaDB
        vector_store = VectorStore(settings.vector_path)
        vector_store.init()

        hashes = vector_store.search(query, limit=limit)
        maybe_tracks = [db.get_track_by_hash(h) for h in hashes]
        tracks = [t for t in maybe_tracks if t is not None]
    else:
        # Database search with filters
        tracks = db.search_tracks(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            key=key,
            artist=artist,
            include_tags=list(tags) if tags else None,
            limit=limit,
        )

        # Apply additional filters in Python
        if label:
            tracks = [t for t in tracks if t.label and label.lower() in t.label.lower()]
        if rating_min:
            tracks = [t for t in tracks if t.rating is not None and t.rating >= rating_min]

    db.close()

    if not tracks:
        console.print("[yellow]No tracks found[/yellow]")
        return

    # Display results
    table = Table(title=f"Search Results ({len(tracks)} tracks)")
    table.add_column("Title", style="cyan")
    table.add_column("Artist", style="green")
    table.add_column("BPM", justify="right")
    table.add_column("Key")
    table.add_column("Tags", style="dim")

    for track in tracks:
        table.add_row(
            track.title or track.file_path.stem,
            track.artist or "-",
            f"{track.bpm:.1f}" if track.bpm else "-",
            track.key_camelot or track.key or "-",
            ", ".join(track.tags[:3]) if track.tags else "-",
        )

    console.print(table)
