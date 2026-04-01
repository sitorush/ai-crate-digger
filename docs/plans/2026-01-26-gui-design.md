# DJ Catalog GUI Design

**Date:** 2026-01-26
**Status:** Approved

## Overview

A PySide6 desktop application for browsing, searching, and editing track properties. Launched via `dj gui` command, sharing the same database as the CLI.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Use case | Full library browser | Search, filter, sort, edit properties |
| Platform | Desktop native | User preference |
| Framework | PySide6 | Native look, LGPL license, rich widgets |
| Scope | Minimal MVP | Track list, search, edit properties (no waveforms) |
| Integration | `dj gui` command | Single install, shared database |

## Architecture

```
src/dj_catalog/
├── gui/                    # New module
│   ├── __init__.py
│   ├── app.py             # QApplication setup, entry point
│   ├── main_window.py     # Main window with layout
│   ├── models/
│   │   └── track_model.py # QAbstractTableModel wrapping database
│   └── widgets/
│       ├── track_table.py      # QTableView for track list
│       ├── search_bar.py       # Search/filter controls
│       └── property_editor.py  # Edit panel + tag chips
├── cli/
│   └── main.py            # Add 'dj gui' command
```

**Key principle:** GUI is a thin view layer. All data access through existing `Database` class.

## Main Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Search: [_______________]  Tags: [House ▼]  BPM: [120-130] │
├─────────────────────────────────────────────────────────────┤
│  Title          │ Artist        │ BPM   │ Key │ Tags       │
│─────────────────┼───────────────┼───────┼─────┼────────────│
│  So Lifted      │ Lizzie Curious│ 132.0 │ 8A  │ UK Garage  │
│  If You Let Me  │ Sinead Harnett│ 131.9 │ 5B  │ House      │
│  ► Selected Row │               │       │     │            │
├─────────────────────────────────────────────────────────────┤
│  EDIT TRACK                                                 │
│  Title: [If You Let Me____________]                         │
│  Artist: [Sinead Harnett__________]                         │
│  BPM: [131.9]  Key: [5B ▼]  Energy: [0.72]                 │
│  Tags: [House ×] [Vocal ×] [+ Add]                         │
│  Rating: ★★★★☆                                              │
│                                        [Save] [Revert]      │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **Search Bar** - Text search + tag filter dropdown + BPM range
2. **Track Table** - Sortable columns, single selection
3. **Property Editor** - Edit form for selected track with Save/Revert

## Data Flow

1. **Startup:** `Database.get_all_tracks()` → loads into `QAbstractTableModel`
2. **Search/Filter:** Model applies filters, updates table view
3. **Select track:** Property Editor displays track fields
4. **Edit:** Changes held in memory (dirty state)
5. **Save:** `Database.upsert_track()` → refresh table row
6. **Revert:** Discard in-memory changes

### Dirty State Handling

- Track unsaved changes with `_is_dirty` flag
- Enable/disable Save button based on state
- Prompt on track change: "Save changes?" (Save / Discard / Cancel)

### Tag Editing

- Display as removable chips with × button
- `+ Add` button shows autocomplete with existing library tags

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl+F` | Focus search |
| `Cmd/Ctrl+S` | Save current track |
| `Escape` | Revert changes |
| `Up/Down` | Navigate tracks |

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "PySide6>=6.6.0",
]
```

## CLI Integration

```python
# cli/main.py
@click.command()
def gui() -> None:
    """Launch the desktop GUI."""
    from dj_catalog.gui.app import run_app
    run_app()

main.add_command(gui)
```

## Entry Point

```python
# gui/app.py
def run_app():
    app = QApplication([])
    app.setApplicationName("DJ Catalog")

    settings = get_settings()
    db = Database(settings.db_path)
    db.init()

    window = MainWindow(db)
    window.show()

    app.exec()
    db.close()
```

## Future Enhancements (Not in MVP)

- Waveform display with BPM grid
- Audio preview/playback
- Playlist builder with drag-and-drop
- Bulk editing (select multiple tracks)
- Dark/light theme toggle
