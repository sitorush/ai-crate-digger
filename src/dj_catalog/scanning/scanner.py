"""File scanner for discovering audio files."""

import logging
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp3",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wav",
        ".aiff",
        ".wma",
        ".alac",
    }
)


def scan_directory(directory: Path, recursive: bool = True) -> Iterator[Path]:
    """Scan directory for audio files.

    Args:
        directory: Root directory to scan
        recursive: Whether to scan subdirectories

    Yields:
        Path objects for each audio file found

    Raises:
        ValueError: If path is not a directory
    """
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    pattern = "**/*" if recursive else "*"

    for path in directory.glob(pattern):
        # Skip hidden files and directories
        if any(part.startswith(".") for part in path.parts):
            continue

        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            logger.debug("Found audio file: %s", path)
            yield path
