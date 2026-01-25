"""Playlist command for generating and exporting playlists."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from dj_catalog.core.config import get_settings
from dj_catalog.playlist import (
    PlaylistOptions,
    TrackFilter,
    export_playlist,
    generate_playlist,
)
from dj_catalog.storage import Database

console = Console()


@click.command()
@click.option("--name", "-n", default="DJ Set", help="Playlist name")
@click.option("--duration", "-d", type=int, default=60, help="Target duration in minutes")
@click.option("--tags", "-t", multiple=True, help="Include tracks with these tags")
@click.option("--exclude-tags", multiple=True, help="Exclude tracks with these tags")
@click.option("--bpm-min", type=float, help="Minimum BPM")
@click.option("--bpm-max", type=float, help="Maximum BPM")
@click.option("--key", "-k", help="Starting key")
@click.option("--rating-min", type=int, help="Minimum rating (1-5)")
@click.option("--energy-min", type=float, help="Minimum energy (0-1)")
@click.option("--no-harmonic", is_flag=True, help="Disable harmonic mixing")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Export file path")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["m3u", "rekordbox"]),
    default="m3u",
)
def playlist(
    name: str,
    duration: int,
    tags: tuple[str, ...],
    exclude_tags: tuple[str, ...],
    bpm_min: float | None,
    bpm_max: float | None,
    key: str | None,
    rating_min: int | None,
    energy_min: float | None,
    no_harmonic: bool,
    output: Path | None,
    output_format: str,
) -> None:
    """Generate a playlist from the catalog.

    Selects tracks based on filters and arranges them using harmonic mixing.
    """
    settings = get_settings()
    db = Database(settings.db_path)
    db.init()

    # Build filter
    bpm_range = None
    if bpm_min is not None and bpm_max is not None:
        bpm_range = (bpm_min, bpm_max)

    energy_range = None
    if energy_min is not None:
        energy_range = (energy_min, 1.0)

    track_filter = TrackFilter(
        include_tags=list(tags) if tags else [],
        exclude_tags=list(exclude_tags) if exclude_tags else [],
        bpm_range=bpm_range,
        key=key,
        rating_min=rating_min,
        energy_range=energy_range,
    )

    # Get all tracks
    all_tracks = db.get_all_tracks()
    db.close()

    if not all_tracks:
        console.print("[yellow]No tracks in database. Run 'dj scan' first.[/yellow]")
        return

    # Generate playlist
    options = PlaylistOptions(
        duration_minutes=duration,
        harmonic_mixing=not no_harmonic,
    )

    generated = generate_playlist(
        all_tracks,
        filter_=track_filter,
        options=options,
        name=name,
    )

    if not generated.tracks:
        console.print("[yellow]No tracks match the criteria[/yellow]")
        return

    # Display playlist
    console.print(f"\n[bold]{generated.name}[/bold]")
    console.print(f"Duration: {generated.duration_minutes:.1f} minutes\n")

    table = Table()
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Artist", style="green")
    table.add_column("BPM", justify="right")
    table.add_column("Key")

    for i, track in enumerate(generated.tracks, 1):
        table.add_row(
            str(i),
            track.title or track.file_path.stem,
            track.artist or "-",
            f"{track.bpm:.1f}" if track.bpm else "-",
            track.key_camelot or "-",
        )

    console.print(table)

    # Export if requested
    if output:
        export_playlist(generated, output, output_format=output_format)
        console.print(f"\n[green]Exported to {output}[/green]")
