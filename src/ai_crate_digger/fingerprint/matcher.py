"""Identify library tracks inside a DJ mix recording."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt

from ai_crate_digger.fingerprint.hashing import hash_peaks
from ai_crate_digger.fingerprint.index import LibraryIndex
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import Peaks

Band = Literal["high", "medium", "low"]
Mode = Literal["pitch", "keylock"]


@dataclass(frozen=True)
class MatchParams:
    """Tunable matching behaviour (query time only, no reindex needed)."""

    speed_range: float = 0.08
    speed_step: float = 0.01
    block_sec: float = 5.0
    offset_bin_frames: int = 4
    min_votes: int = 8
    max_tracks_per_block: int = 2
    high_support: float = 0.12
    medium_support: float = 0.05
    low_support: float = 0.02
    merge_tolerance_sec: float = 2.0
    max_gap_blocks: int = 1
    min_gap_sec: float = 10.0


@dataclass(frozen=True)
class MixSegment:
    """One contiguous stretch of the mix identified as a library track."""

    start_sec: float
    end_sec: float
    track_hash: str
    confidence: float
    confidence_band: Band
    tempo_shift_pct: float
    mode: Mode


@dataclass(frozen=True)
class MixResult:
    """Identified segments plus spans nothing matched."""

    duration_sec: float
    segments: list[MixSegment] = field(default_factory=list)
    unmatched: list[tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True)
class _Candidate:
    block: int
    track: int
    votes: int
    support: float
    speed: float
    mode: Mode
    offset_sec: float


def hypotheses(params: MatchParams) -> list[tuple[float, Mode]]:
    """Speed hypotheses: identity, plus each speed under pitch-follows and key-lock modes."""
    steps = int(round(params.speed_range / params.speed_step))
    result: list[tuple[float, Mode]] = [(1.0, "keylock")]
    for i in range(1, steps + 1):
        for sign in (-1, 1):
            speed = round(1.0 + sign * i * params.speed_step, 6)
            result.append((speed, "pitch"))
            result.append((speed, "keylock"))
    return result


def _band(support: float, params: MatchParams) -> Band | None:
    if support >= params.high_support:
        return "high"
    if support >= params.medium_support:
        return "medium"
    if support >= params.low_support:
        return "low"
    return None


def _votes_for_hypothesis(
    index: LibraryIndex,
    mix_peaks: Peaks,
    fp: FingerprintParams,
    params: MatchParams,
    speed: float,
    mode: Mode,
    block_frames: int,
    anchors_per_block: npt.NDArray[np.int64],
) -> list[_Candidate]:
    freq_scale = 1.0 / speed if mode == "pitch" else 1.0
    hs = hash_peaks(
        mix_peaks,
        fp,
        rank_min=1,
        rank_max=fp.query_rank_max,
        time_scale=speed,
        freq_scale=freq_scale,
    )
    if len(hs.hashes) == 0:
        return []
    matches = index.lookup(hs.hashes, fp.max_matches_per_hash)
    if len(matches.query_idx) == 0:
        return []

    offset = hs.anchor_t[matches.query_idx] - matches.track_t.astype(np.int64)
    pad = index.max_track_frames
    bin_width = params.offset_bin_frames
    obin = (offset + pad) // bin_width
    block = hs.source_t[matches.query_idx] // block_frames
    n_obins = int(obin.max()) + 1
    n_tracks = len(index)
    key = (block * n_tracks + matches.track_idx.astype(np.int64)) * n_obins + obin
    uniq, counts = np.unique(key, return_counts=True)
    keep = counts >= params.min_votes
    uniq, counts = uniq[keep], counts[keep]
    if len(uniq) == 0:
        return []

    obin_k = uniq % n_obins
    rest = uniq // n_obins
    track_k = rest % n_tracks
    block_k = rest // n_tracks
    pairs = fp.pairs_per_anchor
    candidates: list[_Candidate] = []
    for b, tr, ob, votes in zip(block_k, track_k, obin_k, counts, strict=True):
        anchors = int(anchors_per_block[b]) if b < len(anchors_per_block) else 0
        support = float(votes) / max(1, anchors * pairs)
        if _band(support, params) is None:
            continue
        offset_frames = ob * bin_width - pad + bin_width / 2
        candidates.append(
            _Candidate(
                block=int(b),
                track=int(tr),
                votes=int(votes),
                support=support,
                speed=speed,
                mode=mode,
                offset_sec=float(offset_frames / fp.frame_rate),
            )
        )
    return candidates


def identify_mix(
    index: LibraryIndex,
    mix_peaks: Peaks,
    fp: FingerprintParams,
    params: MatchParams,
    on_progress: Callable[[float], None] | None = None,
) -> MixResult:
    """Match a mix's spectrogram peaks against the library index."""
    duration = mix_peaks.n_frames / fp.frame_rate
    if len(index) == 0 or len(mix_peaks.t) == 0:
        return MixResult(duration_sec=duration, unmatched=[(0.0, duration)] if duration else [])

    block_frames = int(round(params.block_sec * fp.frame_rate))
    n_blocks = mix_peaks.n_frames // block_frames + 1
    anchors_per_block = np.bincount(mix_peaks.t // block_frames, minlength=n_blocks)

    best: dict[tuple[int, int], _Candidate] = {}
    plan = hypotheses(params)
    for i, (speed, mode) in enumerate(plan):
        for cand in _votes_for_hypothesis(
            index, mix_peaks, fp, params, speed, mode, block_frames, anchors_per_block
        ):
            key = (cand.block, cand.track)
            if key not in best or cand.votes > best[key].votes:
                best[key] = cand
        if on_progress:
            on_progress((i + 1) / len(plan))

    per_block: dict[int, list[_Candidate]] = {}
    for cand in best.values():
        per_block.setdefault(cand.block, []).append(cand)
    chosen: list[_Candidate] = []
    for cands in per_block.values():
        cands.sort(key=lambda c: c.votes, reverse=True)
        chosen.extend(cands[: params.max_tracks_per_block])

    segments = _merge(chosen, index, params, fp, duration)
    return MixResult(
        duration_sec=duration, segments=segments, unmatched=_gaps(segments, duration, params)
    )


def _merge(
    chosen: list[_Candidate],
    index: LibraryIndex,
    params: MatchParams,
    fp: FingerprintParams,
    duration: float,
) -> list[MixSegment]:
    by_track: dict[int, list[_Candidate]] = {}
    for cand in chosen:
        by_track.setdefault(cand.track, []).append(cand)

    segments: list[MixSegment] = []
    for track, cands in by_track.items():
        cands.sort(key=lambda c: c.block)
        run: list[_Candidate] = []
        for cand in cands:
            if run and not _continues(run[-1], cand, params):
                _flush(run, track, index, params, duration, segments)
                run = []
            run.append(cand)
        _flush(run, track, index, params, duration, segments)
    segments.sort(key=lambda s: s.start_sec)
    return segments


def _position(cand: _Candidate, params: MatchParams) -> float:
    """Where in the track the mix is, at the start of this candidate's block."""
    return cand.block * params.block_sec * cand.speed - cand.offset_sec


def _continues(prev: _Candidate, cand: _Candidate, params: MatchParams) -> bool:
    gap = cand.block - prev.block
    if gap < 1 or gap > params.max_gap_blocks + 1:
        return False
    expected = _position(prev, params) + gap * params.block_sec * prev.speed
    return abs(_position(cand, params) - expected) <= params.merge_tolerance_sec


def _flush(
    run: list[_Candidate],
    track: int,
    index: LibraryIndex,
    params: MatchParams,
    duration: float,
    out: list[MixSegment],
) -> None:
    if not run:
        return
    support = float(np.mean([c.support for c in run]))
    band = _band(support, params)
    if band is None or (len(run) < 2 and band != "high"):
        return
    speed = float(np.mean([c.speed for c in run]))
    pitch_votes = sum(c.votes for c in run if c.mode == "pitch")
    key_votes = sum(c.votes for c in run if c.mode == "keylock")
    out.append(
        MixSegment(
            start_sec=run[0].block * params.block_sec,
            end_sec=min(duration, (run[-1].block + 1) * params.block_sec),
            track_hash=index.track_hashes[track],
            confidence=round(support, 4),
            confidence_band=band,
            tempo_shift_pct=round((speed - 1.0) * 100.0, 2),
            mode="pitch" if pitch_votes > key_votes else "keylock",
        )
    )


def _gaps(
    segments: list[MixSegment], duration: float, params: MatchParams
) -> list[tuple[float, float]]:
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for seg in sorted(segments, key=lambda s: s.start_sec):
        if seg.start_sec - cursor >= params.min_gap_sec:
            gaps.append((cursor, seg.start_sec))
        cursor = max(cursor, seg.end_sec)
    if duration - cursor >= params.min_gap_sec:
        gaps.append((cursor, duration))
    return gaps
