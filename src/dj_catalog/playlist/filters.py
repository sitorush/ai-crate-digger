"""Track filtering for playlist generation."""

from dataclasses import dataclass, field

from dj_catalog.core.models import Track


@dataclass
class TrackFilter:
    """Filter criteria for track selection."""

    # Tag filters (AND logic within, OR between calls)
    include_tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)

    # Field filters
    bpm_range: tuple[float, float] | None = None
    key: str | None = None
    keys: list[str] | None = None
    genre: str | None = None
    label: str | None = None
    artist: str | None = None

    # Exclude filters
    exclude_artists: list[str] = field(default_factory=list)
    exclude_labels: list[str] = field(default_factory=list)

    # Quality filters
    rating_min: int | None = None
    energy_range: tuple[float, float] | None = None
    year_range: tuple[int, int] | None = None
    min_bitrate: int | None = None

    def matches(self, track: Track) -> bool:
        """Check if track passes all filters.

        Args:
            track: Track to check

        Returns:
            True if track matches all criteria
        """
        # Include tags (any match)
        if self.include_tags and not any(tag in track.tags for tag in self.include_tags):
            return False

        # Exclude tags (no match allowed)
        if self.exclude_tags and any(tag in track.tags for tag in self.exclude_tags):
            return False

        # BPM range
        if (
            self.bpm_range
            and track.bpm
            and not (self.bpm_range[0] <= track.bpm <= self.bpm_range[1])
        ):
            return False

        # Key (single)
        if self.key and track.key != self.key:
            return False

        # Keys (multiple allowed)
        if self.keys and track.key not in self.keys:
            return False

        # Label (partial match)
        if self.label and track.label:
            if self.label.lower() not in track.label.lower():
                return False
        elif self.label and not track.label:
            return False

        # Artist (partial match)
        if self.artist and track.artist:
            if self.artist.lower() not in track.artist.lower():
                return False
        elif self.artist and not track.artist:
            return False

        # Exclude artists
        if (
            self.exclude_artists
            and track.artist
            and any(a.lower() in track.artist.lower() for a in self.exclude_artists)
        ):
            return False

        # Exclude labels
        if (
            self.exclude_labels
            and track.label
            and any(lbl.lower() in track.label.lower() for lbl in self.exclude_labels)
        ):
            return False

        # Rating minimum
        if self.rating_min and (track.rating is None or track.rating < self.rating_min):
            return False

        # Energy range
        if (
            self.energy_range
            and track.energy
            and not (self.energy_range[0] <= track.energy <= self.energy_range[1])
        ):
            return False

        # Year range
        if (
            self.year_range
            and track.year
            and not (self.year_range[0] <= track.year <= self.year_range[1])
        ):
            return False

        # Minimum bitrate
        return not (
            self.min_bitrate and (track.bitrate is None or track.bitrate < self.min_bitrate)
        )


def filter_tracks(tracks: list[Track], filter_: TrackFilter) -> list[Track]:
    """Apply filter to list of tracks.

    Args:
        tracks: Tracks to filter
        filter_: Filter criteria

    Returns:
        Filtered tracks
    """
    return [t for t in tracks if filter_.matches(t)]
