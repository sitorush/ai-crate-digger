"""Locate mix recordings on disk."""

from pathlib import Path

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".aiff", ".aif"})


def resolve_mix_path(path: str | None, inbox: Path) -> Path:
    """Resolve a mix file from an explicit path, or the newest file in ``inbox``.

    Args:
        path: File path, or None / "latest" to use the newest recording in ``inbox``
        inbox: Folder where recordings are dropped

    Raises:
        FileNotFoundError: If the file, folder or any audio file cannot be found
    """
    if path and path.lower() != "latest":
        resolved = Path(path).expanduser()
        if not resolved.is_file():
            msg = f"Mix file not found: {resolved}"
            raise FileNotFoundError(msg)
        return resolved

    if not inbox.is_dir():
        msg = f"Inbox folder not found: {inbox}"
        raise FileNotFoundError(msg)
    candidates = [
        p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ]
    if not candidates:
        msg = f"No audio files in inbox folder: {inbox}"
        raise FileNotFoundError(msg)
    return max(candidates, key=lambda p: p.stat().st_mtime)
