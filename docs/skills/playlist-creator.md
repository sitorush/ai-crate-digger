---
name: playlist-creator
description: Generate DJ playlists from a music library using the crate-digger MCP tools. Use when the user asks to create, generate, or build a playlist, mix, or set for any occasion (gym, party, warm-up, cool-down, etc.). Also triggers for playlist editing, deduplication, track swapping, or exporting playlists to M3U/Rekordbox. Requires the crate-digger MCP server to be connected.
type: skill
---

# Playlist Creator

Generate high-quality DJ playlists using the crate-digger MCP server.

## MCP Server

The MCP server is **ai-crate-digger** (previously referred to as dj-catalog). All tool calls are prefixed `ai-crate-digger:`. Confirm it's connected before starting — if tools fail to load, ask the user to check the server is running.

---

## Workflow Modes

| Mode | When to use |
|---|---|
| **Brainstorm** | User gives a vague or open brief. Start with discovery questions before building. |
| **Direct** | User gives a specific brief with genre, BPM, duration, or vibe details already defined. Skip brainstorming, go straight to building. |

Default to **brainstorm mode** unless the user has clearly provided enough detail to build.

---

## Brainstorm Mode

### Step 1: Quick Discovery

Ask 2–3 focused questions in a single message. Only ask what's missing.

### Step 2: Check Library

Call `get_stats(group_by=tags)` to see what's available.

### Step 3: Propose a Plan

Propose a phase structure and wait for confirmation before building.

### Step 4: Build

Proceed to the building workflow below.

---

## Building Workflow

### Phase-Based Candidate Fetching

For each phase, call `get_candidate_pool` with relevant tags, BPM range, and `exclude_stems=true`, `exclude_unknown=true`. Fetch **15–25 candidates per phase** so you have options for the harmonic chain.

Pass `exclude_hashes` with already-picked hashes to avoid cross-phase duplicates.

### Harmonic Chain Building

Build the track order as a **Camelot key chain**, not just phase-by-phase.

- Adjacent tracks must have **Camelot distance <= 1** (same key, +/-1, or relative major/minor A↔B).
- When bridging between key zones, do a targeted fetch using the `key=` parameter.
- Plan the full key chain before committing to a track order.
- **BPM steps <= 2** within a phase. Intentional wind-down drops up to ~3 BPM are acceptable.

**Example chains:**

```
6A → 6A → 7B → 7B → 8A → 9A → 9B → 10A → 11B → 12A → 1B → 2A → 3B
12A → 1B → 1B → 2A → 2A → 3B → 4A → 4A → 5B → 5B → 6A
```

**Targeted bridge fetch example:**

```
get_candidate_pool(key="9B", tags=["Afro House"], bpm_min=121, bpm_max=124, limit=8)
```

### Track Selection

Pick tracks considering: vibe coherence, BPM progression, key compatibility, era awareness, tag overlap, and no same-song duplicates.

### Duration Targeting

A 90-min set needs ~14–16 tracks averaging 5–6 min each. Targeting 100–110 min of playlist content is fine — transition overlaps eat time in a live mix.

### Validation

Call `validate_playlist_order` with the full hash list. `valid: true` with only warnings is fine to export. Fix any `error` severity issues first. Tag mismatch warnings between stylistically similar genres (e.g. Organic/Afro House) can be ignored.

### Export

Prefer `build_playlist` (validates + exports in one call). If it times out, fall back to `export_playlist` with the same hashes — it's faster and skips the re-validation.

Default output: `~/Desktop/{playlist_name}.m3u`

---

## Presenting Playlists

Table columns: `#`, `Artist`, `Title`, `BPM`, `Key`, `Duration`, `Tags`. Group by phase with headers. Summary line with total duration and BPM range. **Bold** any swapped rows.

---

## Preset Mappings

### Afro House

| Phase | Duration % | Tags | BPM |
|---|---|---|---|
| Intro | 20% | Afro House, Organic House | 119–121 |
| Build | 25% | Afro House | 121–123 |
| Peak | 35% | Afro House | 123–126 |
| Wind down | 20% | Afro House, Organic House | 121–123 |

### Gym / Workout

| Phase | Duration % | Tags | BPM |
|---|---|---|---|
| Warm-up | 10% | Nu Disco, Disco, Funky | 124–126 |
| Build | 15% | House, Classic House, Vocal House | 126–128 |
| Drive | 25% | Tech House | 128–129 |
| Peak | 25% | Melodic House & Techno, Techno | 128–129 |
| Climax | 15% | EDM, Electro House | 128–130 |
| Cool down | 10% | House, Tech House | 126–128 |

### Party / Commercial

| Phase | Duration % | Tags | BPM |
|---|---|---|---|
| Opener | 15% | Nu Disco, Indie Dance, Disco | 122–125 |
| Build | 20% | House, Dance, Vocal House | 125–128 |
| Peak | 40% | House, EDM, Electro House, Tech House | 128–130 |
| Wind down | 25% | Deep House, Melodic House | 124–127 |

### Warm-Up Set

| Phase | Duration % | Tags | BPM |
|---|---|---|---|
| Intro | 25% | Deep House, Organic House | 118–121 |
| Build | 50% | House, Indie Dance, Melodic House | 121–124 |
| Handover | 25% | Tech House, House | 124–126 |

### Cool-Down / Closing

| Phase | Duration % | Tags | BPM |
|---|---|---|---|
| Transition | 20% | Melodic House, House | 124–126 |
| Ease | 50% | Deep House, Organic House, Indie Dance | 120–124 |
| Close | 30% | Organic House, Downtempo | 115–120 |

---

## Quality Rules

- No exact duplicates
- No same-song duplicates (different remixes of the same original)
- No stems/samples (`DS_`, `_percussion_`, `_bass_synth_`, `_drum_top_`, `_fragment`)
- No unknown/unnamed tracks
- BPM flow — no drops > 2 BPM between adjacent tracks (wind-down excepted)
- Harmonic flow — Camelot distance <= 1 between adjacent tracks
- Vibe continuity — shared era context and mood

---

## Tool Reference

| Tool | Use |
|---|---|
| `get_stats` | Library overview, group by tags |
| `get_candidate_pool` | Filtered candidates for AI selection. Supports `tags`, `bpm`, `energy`, `key`, `exclude_hashes` |
| `validate_playlist_order` | Check transitions, duplicates, key clashes |
| `build_playlist` | Validate + export in one call. Can time out — use `export_playlist` as fallback |
| `search_tracks` | One-off track lookups |
| `get_track_details` | Full metadata for a single track |
| `generate_playlist` | Quick auto-generate, no phase/vibe awareness |
| `export_playlist` | Fast file export, no validation. Reliable fallback for `build_playlist` |

**Notes:**

- `output_path` must be a local machine path (`~/Desktop/`), never `/mnt/` or `/home/claude/`
- `get_candidate_pool` with `key=` returns harmonically compatible tracks — use for bridge fetching
- `build_playlist` can time out; `export_playlist` is the reliable fallback
