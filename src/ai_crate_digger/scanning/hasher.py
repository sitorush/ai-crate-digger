"""Content hashing for deduplication."""

import hashlib
from pathlib import Path


def compute_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of first 1MB of file.

    Using only the first 1MB provides fast hashing while still
    being sufficient to detect duplicates in audio files.

    Args:
        path: Path to file
        chunk_size: Bytes to read per chunk

    Returns:
        64-character hex string (SHA-256)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    hasher = hashlib.sha256()
    bytes_read = 0
    max_bytes = 1024 * 1024  # 1MB

    with open(path, "rb") as f:
        while bytes_read < max_bytes:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_read += len(chunk)

    return hasher.hexdigest()
