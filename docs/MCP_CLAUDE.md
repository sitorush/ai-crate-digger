# Claude Desktop Integration (MCP)

ai-crate-digger includes an MCP (Model Context Protocol) server that lets you control your music library through Claude Desktop using natural language.

## Setup

### 1. Install ai-crate-digger

```bash
python3.11 -m venv ~/.local/ai-crate-digger-venv
source ~/.local/ai-crate-digger-venv/bin/activate
pip install ai-crate-digger
```

### 2. Find your Python path

```bash
which python
# e.g. /Users/yourname/.local/ai-crate-digger-venv/bin/python
```

### 3. Configure Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
Edit: `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "ai-crate-digger": {
      "command": "/Users/yourname/.local/ai-crate-digger-venv/bin/python",
      "args": ["-m", "ai_crate_digger.mcp.server"]
    }
  }
}
```

**Windows example:**
```json
{
  "mcpServers": {
    "ai-crate-digger": {
      "command": "C:\\Users\\yourname\\.local\\ai-crate-digger-venv\\Scripts\\python.exe",
      "args": ["-m", "ai_crate_digger.mcp.server"]
    }
  }
}
```

### 4. Restart Claude Desktop

Quit and reopen. You should see "ai-crate-digger" in the MCP servers list (hammer icon).

## Available Tools

| Tool | What it does |
|------|-------------|
| `search_tracks` | Search by tags, BPM, artist, or natural language |
| `generate_playlist` | Create playlists with filters and export |
| `get_candidate_pool` | Get filtered tracks for AI-driven playlist building |
| `validate_playlist_order` | Check playlist for BPM jumps, key clashes, duplicates |
| `build_playlist` | Export an ordered track list to M3U or Rekordbox XML |
| `get_stats` | Library statistics |
| `get_track_details` | Full metadata for a specific track |
| `export_playlist` | Export to M3U or Rekordbox XML |
| `scan_library` | Scan a directory for new tracks |
| `reset_database` | Clear all tracks (with confirmation) |
| `clean_orphans` | Remove tracks for deleted files |

## Example Prompts

- "Search my library for dark techno tracks around 130 BPM"
- "Generate a 2-hour melodic house playlist and save it to my Desktop"
- "What's the most common key in my library?"
- "Find me 10 tracks that would mix well after Amelie Lens - Exhale"
- "Make a 90-minute gym playlist that builds from 124 to 132 BPM"

## Important: File Paths

The MCP server runs on **your computer**, not inside Claude. When exporting playlists, use local paths:

```
# Correct
~/Desktop/playlist.m3u
/Users/yourname/Downloads/set.m3u
C:\Users\yourname\Desktop\playlist.m3u

# Wrong (Claude's container — won't work)
/mnt/user-data/outputs/playlist.m3u
/home/claude/playlist.m3u
```

## Troubleshooting

**"Server disconnected" error**
1. Verify the Python path is correct
2. Test it manually: `/path/to/python -c "import ai_crate_digger; print('OK')"`
3. Check Claude Desktop logs: `~/Library/Logs/Claude/` (macOS)

**"Permission denied" on export**
Use paths on your local machine. Avoid paths inside Claude's sandbox.

**Changes not appearing after update**
Restart Claude Desktop after updating ai-crate-digger.
