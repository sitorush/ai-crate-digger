"""Benchmark mix identification against a recording with a known tracklist.

Usage:
    uv run python scripts/benchmark_mix.py MIX.mp3 TRUTH.json

TRUTH.json lists the tracks you know were played and roughly when they started:

    [{"path": "~/Music/mp3/Artist - Track.mp3", "start_sec": 0},
     {"path": "~/Music/mp3/Other - Tune.mp3", "start_sec": 215}]

The library must already be fingerprinted (``crate fingerprint``). The report shows
recall, false matches, run time and memory, which is how to judge whether the matcher
is good enough on real mixes and where its thresholds need tuning.
"""

import json
import resource
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ai_crate_digger.core.config import get_settings
from ai_crate_digger.fingerprint.identify import match_params_from_settings
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.matcher import identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.report import BAND_RANK, format_time
from ai_crate_digger.fingerprint.spectral import extract_peaks, load_audio
from ai_crate_digger.scanning import compute_file_hash
from ai_crate_digger.storage import Database

console = Console()


def _peak_memory_gb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / 1e9 if sys.platform == "darwin" else usage / 1e6


@click.command()
@click.argument("mix", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("truth", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--tolerance", default=15.0, show_default=True, help="Seconds allowed for start time")
@click.option(
    "--min-confidence",
    type=click.Choice(["low", "medium", "high"]),
    default="medium",
    show_default=True,
)
def main(mix: Path, truth: Path, tolerance: float, min_confidence: str) -> None:
    """Report recall, false matches, run time and memory for one mix."""
    settings = get_settings()
    params = FingerprintParams()
    expected = [
        (compute_file_hash(Path(entry["path"]).expanduser()), float(entry["start_sec"]), entry)
        for entry in json.loads(truth.read_text())
    ]

    started = time.perf_counter()
    db = Database(settings.db_path)
    db.init()
    try:
        index = get_library_index(db)
    finally:
        db.close()
    load_seconds = time.perf_counter() - started

    started = time.perf_counter()
    peaks = extract_peaks(load_audio(mix, params.sample_rate), params)
    decode_seconds = time.perf_counter() - started

    started = time.perf_counter()
    result = identify_mix(index, peaks, params, match_params_from_settings(settings))
    match_seconds = time.perf_counter() - started

    floor = BAND_RANK[min_confidence]
    segments = [s for s in result.segments if BAND_RANK[s.confidence_band] >= floor]
    expected_hashes = {h for h, _, _ in expected}

    table = Table(title=f"{mix.name} ({format_time(result.duration_sec)})")
    for column in ("Expected", "Start", "Found", "Band", "Tempo"):
        table.add_column(column)
    hits = 0
    for file_hash, start, entry in expected:
        match = next(
            (
                s
                for s in segments
                if s.track_hash == file_hash and abs(s.start_sec - start) <= tolerance
            ),
            None,
        )
        hits += match is not None
        table.add_row(
            Path(entry["path"]).name,
            format_time(start),
            f"{format_time(match.start_sec)}" if match else "[red]missed[/red]",
            match.confidence_band if match else "-",
            f"{match.tempo_shift_pct:+.1f}%" if match else "-",
        )
    console.print(table)

    false_matches = [s for s in segments if s.track_hash not in expected_hashes]
    console.print(f"Recall: [bold]{hits}/{len(expected)}[/bold] tracks found")
    console.print(f"False matches: [bold]{len(false_matches)}[/bold] segments not in the tracklist")
    for seg in false_matches:
        console.print(
            f"  {format_time(seg.start_sec)}-{format_time(seg.end_sec)} "
            f"{seg.track_hash[:8]} {seg.confidence_band} ({seg.confidence:.2f})"
        )
    console.print(
        f"Index: {len(index)} tracks, {len(index.hashes):,} hashes, load {load_seconds:.1f}s"
    )
    console.print(f"Decode + peaks: {decode_seconds:.1f}s, matching: {match_seconds:.1f}s")
    console.print(f"Peak memory: {_peak_memory_gb():.2f} GB")


if __name__ == "__main__":
    main()
