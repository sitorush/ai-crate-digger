"""Commands for fingerprinting the library and identifying tracks in a mix."""

from typing import Literal, cast

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
from rich.table import Table

from ai_crate_digger.core.config import get_settings
from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.inbox import resolve_mix_path
from ai_crate_digger.fingerprint.indexer import index_library
from ai_crate_digger.fingerprint.report import describe_result
from ai_crate_digger.storage import Database

console = Console()


@click.command()
@click.option("--force", is_flag=True, help="Re-fingerprint every track, not just new ones")
@click.option("--workers", "-w", type=int, default=None, help="Number of parallel workers")
def fingerprint(force: bool, workers: int | None) -> None:
    """Fingerprint library tracks so mixes can be matched against them."""
    settings = get_settings()
    db = Database(settings.db_path)
    db.init()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Fingerprinting...", total=None)

            def on_progress(done: int, total: int) -> None:
                progress.update(task, completed=done, total=total)

            report = index_library(
                db,
                force=force,
                workers=workers or settings.max_workers,
                on_progress=on_progress,
            )
    finally:
        db.close()

    console.print(
        f"[bold green]Indexed {report.indexed}[/bold green] tracks, "
        f"{report.skipped} already up to date."
    )
    for path, error in report.failed[:10]:
        console.print(f"[red]Failed:[/red] {path} ({error})")
    if len(report.failed) > 10:
        console.print(f"[red]...and {len(report.failed) - 10} more failures[/red]")


@click.command()
@click.argument("path", required=False)
@click.option(
    "--min-confidence",
    type=click.Choice(["low", "medium", "high"]),
    default="medium",
    show_default=True,
    help="Hide matches below this confidence",
)
def identify(path: str | None, min_confidence: str) -> None:
    """Identify which library tracks were played in a recorded mix.

    PATH is the recording. Omit it to use the newest file in the inbox folder.
    """
    settings = get_settings()
    try:
        mix_path = resolve_mix_path(path, settings.inbox_path)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"[bold]Identifying:[/bold] {mix_path}")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Matching...", total=1.0)
        try:
            result = identify_mix_file(
                mix_path, settings, lambda f: progress.update(task, completed=f)
            )
        except FingerprintError as exc:
            raise click.ClickException(str(exc)) from exc

    db = Database(settings.db_path)
    db.init()
    try:
        band = cast("Literal['low', 'medium', 'high']", min_confidence)
        summary = describe_result(result, db, band)
    finally:
        db.close()

    table = Table(title=f"Mix timeline ({summary['duration']})")
    for column in ("Start", "End", "Artist", "Title", "Confidence", "Tempo"):
        table.add_column(column)
    for seg in summary["segments"]:
        table.add_row(
            seg["start"],
            seg["end"],
            seg["artist"] or "Unknown",
            seg["title"] or seg["hash"][:8],
            f"{seg['confidence_band']} ({seg['confidence']:.2f})",
            f"{seg['tempo_shift_pct']:+.1f}%",
        )
    console.print(table)
    for gap in summary["unmatched"]:
        console.print(f"[yellow]Unmatched:[/yellow] {gap['start']} to {gap['end']}")
    if summary["hidden_below_min_confidence"]:
        console.print(
            f"[dim]{summary['hidden_below_min_confidence']} weaker matches hidden "
            f"(use --min-confidence low)[/dim]"
        )
