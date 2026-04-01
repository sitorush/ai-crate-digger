"""Playlist generation with harmonic mixing."""

import random
from dataclasses import dataclass

from ai_crate_digger.core.models import Track
from ai_crate_digger.playlist.filters import TrackFilter, filter_tracks
from ai_crate_digger.playlist.harmonic import harmonic_distance


@dataclass
class PlaylistOptions:
    """Options for playlist generation."""

    duration_minutes: int = 60
    harmonic_mixing: bool = True
    shuffle_start: bool = True
    avoid_same_artist: bool = True
    max_artist_repeat: int = 3


@dataclass
class Playlist:
    """A generated playlist."""

    name: str
    tracks: list[Track]
    total_duration: float  # seconds

    @property
    def duration_minutes(self) -> float:
        """Duration in minutes."""
        return self.total_duration / 60


def _score_track(
    candidate: Track,
    last_track: Track | None,
    recent_artists: list[str],
    options: PlaylistOptions,
) -> float:
    """Score a candidate track for playlist inclusion.

    Lower score is better.
    """
    score = 0.0

    # Harmonic compatibility (most important)
    if options.harmonic_mixing and last_track and last_track.key_camelot and candidate.key_camelot:
        dist = harmonic_distance(last_track.key_camelot, candidate.key_camelot)
        score += dist * 10  # Weight heavily

    # BPM change penalty
    if last_track and last_track.bpm and candidate.bpm:
        bpm_diff = abs(last_track.bpm - candidate.bpm)
        score += bpm_diff * 0.5

    # Same artist penalty
    if options.avoid_same_artist and candidate.artist:
        artist_lower = candidate.artist.lower()
        artist_count = sum(1 for a in recent_artists if a.lower() == artist_lower)
        if artist_count >= options.max_artist_repeat:
            score += 100  # Heavy penalty
        else:
            score += artist_count * 5

    # Prefer higher rated tracks (slight bonus)
    if candidate.rating:
        score -= candidate.rating * 0.5

    return score


def generate_playlist(
    tracks: list[Track],
    filter_: TrackFilter | None = None,
    options: PlaylistOptions | None = None,
    name: str = "Generated Playlist",
) -> Playlist:
    """Generate a playlist from available tracks.

    Uses greedy algorithm to select tracks based on:
    - Harmonic compatibility (Camelot wheel)
    - BPM similarity
    - Artist variety
    - Track ratings

    Args:
        tracks: Pool of available tracks
        filter_: Optional filter to apply first
        options: Generation options
        name: Playlist name

    Returns:
        Generated playlist
    """
    options = options or PlaylistOptions()

    # Apply filter if provided
    pool = filter_tracks(tracks, filter_) if filter_ else list(tracks)

    if not pool:
        return Playlist(name=name, tracks=[], total_duration=0)

    # Shuffle to randomize starting point
    if options.shuffle_start:
        random.shuffle(pool)

    target_duration = options.duration_minutes * 60  # Convert to seconds
    playlist_tracks: list[Track] = []
    total_duration = 0.0
    recent_artists: list[str] = []
    used_hashes: set[str] = set()

    # Greedy selection
    while pool and total_duration < target_duration:
        last_track = playlist_tracks[-1] if playlist_tracks else None

        # Score all candidates
        scored = []
        for track in pool:
            if track.file_hash in used_hashes:
                continue
            score = _score_track(track, last_track, recent_artists, options)
            scored.append((score, track))

        if not scored:
            break

        # Pick best scoring track
        scored.sort(key=lambda x: x[0])
        _, best_track = scored[0]

        # Add to playlist
        playlist_tracks.append(best_track)
        used_hashes.add(best_track.file_hash)
        total_duration += best_track.duration_seconds or 0

        if best_track.artist:
            recent_artists.append(best_track.artist)
            # Keep only recent artists
            if len(recent_artists) > 10:
                recent_artists.pop(0)

    return Playlist(
        name=name,
        tracks=playlist_tracks,
        total_duration=total_duration,
    )
