"""Scan command for discovering and analyzing music files."""

from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ai_crate_digger.analysis import ParallelAnalyzer
from ai_crate_digger.core.config import get_settings
from ai_crate_digger.scanning import compute_file_hash, extract_metadata, scan_directory
from ai_crate_digger.storage import Database, VectorStore

console = Console()


@click.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.option("--analyze/--no-analyze", default=True, help="Run audio analysis")
@click.option("--force", is_flag=True, help="Re-process all files, not just new ones")
@click.option("--reset", is_flag=True, help="Delete database before scanning (fresh start)")
@click.option("--workers", "-w", type=int, default=None, help="Number of parallel workers")
def scan(directory: Path, analyze: bool, force: bool, reset: bool, workers: int | None) -> None:
    """Scan directory for music files.

    Discovers audio files, extracts metadata, and optionally analyzes
    audio properties (BPM, key, energy).
    """
    settings = get_settings()

    # Handle reset flag
    if reset:
        import shutil

        console.print("[yellow]Resetting database...[/yellow]")
        if settings.db_path.exists():
            settings.db_path.unlink()
        if settings.vector_path.exists():
            shutil.rmtree(settings.vector_path)
        console.print("[green]Database cleared.[/green]")
        force = True  # Force re-process since DB is empty

    console.print(f"[bold]Scanning:[/bold] {directory}")

    # Initialize storage
    db = Database(settings.db_path)
    db.init()

    vector_store = VectorStore(settings.vector_path)
    vector_store.init()

    # Get known hashes for incremental scan
    known_hashes = set() if force else db.get_known_hashes()
    if known_hashes:
        console.print(f"[dim]Found {len(known_hashes)} existing tracks in database[/dim]")

    # Discover files
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("Discovering files...", total=None)
        files = list(scan_directory(directory))

    console.print(f"[green]Found {len(files)} audio files[/green]")

    # Filter to new files only
    new_files = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Checking for new files...", total=len(files))
        for file in files:
            file_hash = compute_file_hash(file)
            if file_hash not in known_hashes:
                new_files.append((file, file_hash))
            progress.update(task, advance=1)

    if not new_files:
        console.print("[yellow]No new files to process[/yellow]")
        db.close()
        return

    console.print(f"[cyan]{len(new_files)} new files to process[/cyan]")

    # Extract metadata
    tracks = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Extracting metadata...", total=len(new_files))
        for file, _file_hash in new_files:
            try:
                track = extract_metadata(file)
                tracks.append(track)
            except Exception as e:
                console.print(f"[red]Error extracting {file.name}: {e}[/red]")
            progress.update(task, advance=1)

    # Analyze if requested
    if analyze and tracks:
        console.print(f"[bold]Analyzing {len(tracks)} tracks...[/bold]")
        analyzer = ParallelAnalyzer(max_workers=workers)
        analyzed_tracks = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Analyzing audio...", total=len(tracks))

            for analyzed in analyzer.analyze_batch(tracks):
                analyzed_tracks.append(analyzed)
                progress.update(task, advance=1)

        tracks = analyzed_tracks

    # Save to database and vector store
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Saving to database...", total=len(tracks))
        for track in tracks:
            db.upsert_track(track)
            vector_store.add_track(track)
            progress.update(task, advance=1)

    db.close()

    # Summary
    console.print()
    console.print("[bold green]Scan complete![/bold green]")
    console.print(f"  Processed: {len(tracks)} tracks")
    console.print(f"  Database: {settings.db_path}")
