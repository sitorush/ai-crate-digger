"""Scanning module - file discovery and metadata extraction."""

from ai_crate_digger.scanning.extractor import extract_metadata
from ai_crate_digger.scanning.hasher import compute_file_hash
from ai_crate_digger.scanning.scanner import SUPPORTED_EXTENSIONS, scan_directory

__all__ = [
    "scan_directory",
    "SUPPORTED_EXTENSIONS",
    "compute_file_hash",
    "extract_metadata",
]
