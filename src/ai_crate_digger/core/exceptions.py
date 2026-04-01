"""Custom exceptions for DJ Catalog."""


class DJCatalogError(Exception):
    """Base exception for DJ Catalog."""

    pass


class ScanError(DJCatalogError):
    """Error during file scanning."""

    pass


class ExtractionError(DJCatalogError):
    """Error extracting metadata from file."""

    pass


class AnalysisError(DJCatalogError):
    """Error during audio analysis."""

    pass


class DatabaseError(DJCatalogError):
    """Database operation error."""

    pass


class ExportError(DJCatalogError):
    """Error exporting playlist."""

    pass
