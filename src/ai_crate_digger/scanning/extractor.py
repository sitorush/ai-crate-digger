"""Metadata extraction from audio files."""

import logging
import re
from datetime import date
from pathlib import Path

import mutagen

from ai_crate_digger.core.exceptions import ExtractionError
from ai_crate_digger.core.models import Track
from ai_crate_digger.scanning.hasher import compute_file_hash

logger = logging.getLogger(__name__)


def _normalize_tag(tag: str) -> list[str]:
    """Normalize a genre tag into clean separate tags.

    Examples:
        "Garage / Bassline / Grime" → ["Garage", "Bassline", "Grime"]
        "Deep House/Indie Dance/Nu Disco" → ["Deep House", "Indie Dance", "Nu Disco"]
    """
    results = []

    # Split by common delimiters: " / ", "/", " : ", ":"
    parts = re.split(r"\s*/\s*|\s*:\s*", tag)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Remove trailing numbers (like "Bassline 1", "House 2")
        part = re.sub(r"\s+\d+$", "", part)

        # Remove year-like patterns (like "2000", "2023")
        part = re.sub(r"\s+20\d{2}\b", "", part)

        # Remove common noise words at end
        part = re.sub(r"\s+(andre|batz|mp3|folder)$", "", part, flags=re.IGNORECASE)

        part = part.strip()

        # Skip if too short or just numbers
        if len(part) < 2 or part.isdigit():
            continue

        results.append(part)

    return results


def _normalize_tags(tags: list[str]) -> list[str]:
    """Normalize a list of tags, splitting compounds and deduping."""
    all_tags = []
    seen = set()

    for tag in tags:
        for normalized in _normalize_tag(tag):
            key = normalized.lower()
            if key not in seen:
                seen.add(key)
                all_tags.append(normalized)

    return all_tags


def _safe_str(value: str | list[str] | None) -> str | None:
    """Safely convert tag value to string."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value)


def _safe_int(value: str | list[str] | None) -> int | None:
    """Safely convert tag value to int."""
    str_val = _safe_str(value)
    if str_val is None:
        return None
    try:
        # Handle "1/12" track number format
        return int(str(str_val).split("/")[0])
    except (ValueError, TypeError):
        return None


def _safe_date(value: str | list[str] | None) -> date | None:
    """Safely parse date from tag."""
    str_val = _safe_str(value)
    if str_val is None:
        return None
    try:
        # Try full date first (YYYY-MM-DD)
        if len(str_val) >= 10 and "-" in str_val:
            parts = str_val[:10].split("-")
            if len(parts) == 3:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        # Fall back to just year
        year = int(str_val[:4])
        return date(year, 1, 1)
    except (ValueError, TypeError):
        return None


def _parse_remixer(title: str | None, artist: str | None) -> str | None:
    """Try to parse remixer from title."""
    if title is None:
        return None
    # Common patterns: "Song (Artist Remix)", "Song - Artist Remix"
    lower = title.lower()
    for pattern in [" remix)", " remix]", " rmx)", " rmx]", " edit)", " bootleg)"]:
        if pattern in lower:
            # Find the start of remixer name
            idx = lower.rfind("(")
            if idx == -1:
                idx = lower.rfind("[")
            if idx == -1:
                idx = lower.rfind(" - ")
            if idx != -1:
                remixer_part = title[idx:].strip("()[]- ")
                # Remove "Remix" suffix
                for suffix in ["Remix", "remix", "RMX", "rmx", "Edit", "edit", "Bootleg"]:
                    if remixer_part.endswith(suffix):
                        remixer_part = remixer_part[: -len(suffix)].strip()
                if remixer_part and remixer_part != artist:
                    return remixer_part
    return None


def extract_metadata(file_path: Path) -> Track:
    """Extract metadata from an audio file.

    Args:
        file_path: Path to audio file

    Returns:
        Track with extracted metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ExtractionError: If file format not supported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Compute hash first
    file_hash = compute_file_hash(file_path)

    # Load with mutagen
    audio = mutagen.File(file_path, easy=True)  # type: ignore[attr-defined]
    if audio is None:
        raise ExtractionError(f"Unsupported format: {file_path}")

    # Get audio info
    info = audio.info
    duration = info.length if info else None
    sample_rate = getattr(info, "sample_rate", None)
    bitrate = getattr(info, "bitrate", None)
    if bitrate and bitrate > 0:
        bitrate = int(bitrate)

    # Determine codec from file extension
    codec = file_path.suffix.lower().lstrip(".")

    # Extract tags (mutagen easy mode normalizes common tags)
    tags = audio.tags or {}

    title = _safe_str(tags.get("title"))
    artist = _safe_str(tags.get("artist"))
    release_date = _safe_date(tags.get("date"))
    year = _safe_int(tags.get("date"))
    if release_date:
        year = release_date.year

    # Parse remixer from title
    remixer = _parse_remixer(title, artist)

    # Build track
    track = Track(
        file_path=file_path,
        file_hash=file_hash,
        title=title,
        artist=artist,
        album=_safe_str(tags.get("album")),
        album_artist=_safe_str(tags.get("albumartist")),
        track_number=_safe_int(tags.get("tracknumber")),
        duration_seconds=duration,
        label=_safe_str(tags.get("publisher") or tags.get("label")),
        remixer=remixer,
        composer=_safe_str(tags.get("composer")),
        isrc=_safe_str(tags.get("isrc")),
        release_date=release_date,
        year=year,
        comment=_safe_str(tags.get("comment")),
        bitrate=bitrate,
        sample_rate=sample_rate,
        codec=codec,
        # Genre from tag - normalized (split compound tags like "A / B / C")
        tags=_normalize_tags([g for g in [_safe_str(tags.get("genre"))] if g]),
    )

    logger.debug("Extracted metadata for: %s", track.title or file_path.name)
    return track
