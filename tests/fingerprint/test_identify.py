"""End-to-end tests: audio files in, identified tracks out."""

from pathlib import Path

import pytest

from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.identify import identify_mix_file
from ai_crate_digger.fingerprint.indexer import index_library
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, make_track, place, stretch_pitch


def test_identifies_a_pitched_track_from_a_wav_file(library: Library) -> None:
    index_library(library.db, workers=1)
    mix = place(stretch_pitch(library.audio["hash2"][: 35 * SR], 1.03), 4, 40)
    path = write_wav(library.root / "mix.wav", mix)

    result = identify_mix_file(path, library.settings)

    assert [s.track_hash for s in result.segments] == ["hash2"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(3.0, abs=1.0)


def test_short_recordings_are_rejected(library: Library) -> None:
    index_library(library.db, workers=1)
    path = write_wav(library.root / "short.wav", make_track(1, 10))
    with pytest.raises(FingerprintError, match="shorter than"):
        identify_mix_file(path, library.settings)


def test_empty_index_asks_for_indexing_first(library: Library) -> None:
    path = write_wav(library.root / "mix.wav", make_track(1, 40))
    with pytest.raises(FingerprintError, match="index_fingerprints"):
        identify_mix_file(path, library.settings)


def test_unreadable_file_is_a_clear_error(library: Library) -> None:
    path = Path(library.root / "broken.mp3")
    path.write_bytes(b"this is not audio")
    with pytest.raises(FingerprintError, match="Could not read audio file"):
        identify_mix_file(path, library.settings)
