"""Scanning module - file discovery and metadata extraction."""

from dj_catalog.scanning.extractor import extract_metadata
from dj_catalog.scanning.hasher import compute_file_hash
from dj_catalog.scanning.scanner import SUPPORTED_EXTENSIONS, scan_directory

__all__ = [
    "scan_directory",
    "SUPPORTED_EXTENSIONS",
    "compute_file_hash",
    "extract_metadata",
]
