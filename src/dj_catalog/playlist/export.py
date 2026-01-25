"""Playlist export to M3U and Rekordbox XML formats."""

from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from dj_catalog.playlist.generator import Playlist


def export_m3u(playlist: Playlist, output_path: Path) -> None:
    """Export playlist to M3U format.

    Args:
        playlist: Playlist to export
        output_path: Path to write M3U file
    """
    lines = ["#EXTM3U", f"#PLAYLIST:{playlist.name}"]

    for track in playlist.tracks:
        duration = int(track.duration_seconds or 0)
        title = track.title or track.file_path.stem
        artist = track.artist or "Unknown"
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(str(track.file_path))

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_rekordbox_xml(playlist: Playlist, output_path: Path) -> None:
    """Export playlist to Rekordbox XML format.

    Args:
        playlist: Playlist to export
        output_path: Path to write XML file
    """
    # Root element
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")

    # Product info
    ET.SubElement(root, "PRODUCT", Name="dj-catalog", Version="0.1.0")

    # Collection of tracks
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(playlist.tracks)))

    for i, track in enumerate(playlist.tracks, 1):
        track_elem = ET.SubElement(collection, "TRACK")
        track_elem.set("TrackID", str(i))
        track_elem.set("Name", track.title or track.file_path.stem)
        track_elem.set("Artist", track.artist or "")
        track_elem.set("Album", track.album or "")
        track_elem.set("Genre", ", ".join(track.tags) if track.tags else "")
        track_elem.set("Kind", track.codec.upper() if track.codec else "MP3")
        track_elem.set("Size", "0")  # Unknown
        track_elem.set("TotalTime", str(int(track.duration_seconds or 0)))
        track_elem.set("BitRate", str(track.bitrate or 0))
        track_elem.set("SampleRate", str(track.sample_rate or 44100))
        track_elem.set("AverageBpm", f"{track.bpm:.2f}" if track.bpm else "0.00")
        track_elem.set("Tonality", track.key or "")
        track_elem.set("Rating", str((track.rating or 0) * 51))  # Rekordbox uses 0-255
        track_elem.set("Location", f"file://localhost{track.file_path}")
        if track.year:
            track_elem.set("Year", str(track.year))
        if track.label:
            track_elem.set("Label", track.label)
        if track.comment:
            track_elem.set("Comments", track.comment)

    # Playlists node
    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", Type="0", Name="ROOT")
    playlist_node = ET.SubElement(
        root_node,
        "NODE",
        Type="1",
        Name=playlist.name,
        Entries=str(len(playlist.tracks)),
    )

    for i in range(1, len(playlist.tracks) + 1):
        ET.SubElement(playlist_node, "TRACK", Key=str(i))

    # Pretty print
    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    # Remove extra blank lines
    lines = [line for line in xml_str.split("\n") if line.strip()]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_playlist(
    playlist: Playlist,
    output_path: Path,
    output_format: str = "m3u",
) -> None:
    """Export playlist to specified format.

    Args:
        playlist: Playlist to export
        output_path: Path to write file
        output_format: Export format ("m3u" or "rekordbox")

    Raises:
        ValueError: If format is unknown
    """
    if output_format == "m3u":
        export_m3u(playlist, output_path)
    elif output_format == "rekordbox":
        export_rekordbox_xml(playlist, output_path)
    else:
        raise ValueError(f"Unknown export format: {output_format}")
