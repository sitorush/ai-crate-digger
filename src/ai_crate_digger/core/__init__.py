"""Core module - shared foundations."""

from ai_crate_digger.core.config import Settings, get_settings
from ai_crate_digger.core.exceptions import (
    AnalysisError,
    DatabaseError,
    DJCatalogError,
    ExportError,
    ExtractionError,
    ScanError,
)
from ai_crate_digger.core.models import Track

__all__ = [
    "Track",
    "Settings",
    "get_settings",
    "DJCatalogError",
    "ScanError",
    "ExtractionError",
    "AnalysisError",
    "DatabaseError",
    "ExportError",
]
