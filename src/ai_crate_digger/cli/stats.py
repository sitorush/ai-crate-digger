"""Stats command for library statistics."""

from collections import Counter

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ai_crate_digger.core.config import get_settings
from ai_crate_digger.storage import Database

console = Console()


@click.command()
@click.option(
    "--by",
    "-b",
    "group_by",
    type=click.Choice(["tags", "artist", "label", "key", "year"]),
    default="tags",
)
@click.option("--limit", "-n", type=int, default=20, help="Max items to show")
def stats(group_by: str, limit: int) -> None:
    """Show library statistics.

    Display counts grouped by tags, artist, label, key, or year.
    """
    settings = get_settings()
    db = Database(settings.db_path)
    db.init()

    tracks = db.get_all_tracks()
    db.close()

    if not tracks:
        console.print("[yellow]No tracks in database. Run 'dj scan' first.[/yellow]")
        return

    # Overall stats
    total = len(tracks)
    analyzed = sum(1 for t in tracks if t.analyzed_at)
    with_bpm = sum(1 for t in tracks if t.bpm)
    with_key = sum(1 for t in tracks if t.key)
    total_duration = sum(t.duration_seconds or 0 for t in tracks)
    hours = total_duration / 3600

    console.print(
        Panel(
            f"[bold]Total tracks:[/bold] {total}\n"
            f"[bold]Analyzed:[/bold] {analyzed} ({100 * analyzed // total if total else 0}%)\n"
            f"[bold]With BPM:[/bold] {with_bpm}\n"
            f"[bold]With Key:[/bold] {with_key}\n"
            f"[bold]Total duration:[/bold] {hours:.1f} hours",
            title="Library Overview",
        )
    )

    # Grouped stats
    counter: Counter[str] = Counter()

    if group_by == "tags":
        for track in tracks:
            for tag in track.tags:
                counter[tag] += 1
    elif group_by == "artist":
        for track in tracks:
            if track.artist:
                counter[track.artist] += 1
    elif group_by == "label":
        for track in tracks:
            if track.label:
                counter[track.label] += 1
    elif group_by == "key":
        for track in tracks:
            if track.key_camelot:
                counter[track.key_camelot] += 1
    elif group_by == "year":
        for track in tracks:
            if track.year:
                counter[str(track.year)] += 1

    if counter:
        table = Table(title=f"Top {limit} by {group_by.title()}")
        table.add_column(group_by.title(), style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percent", justify="right")

        for item, count in counter.most_common(limit):
            pct = f"{100 * count / total:.1f}%"
            table.add_row(item[:40], str(count), pct)

        console.print()
        console.print(table)
