# Claude Desktop Integration (MCP)

dj-catalog includes an MCP (Model Context Protocol) server that lets you control your music library through Claude Desktop or Claude Code.

## Setup

### 1. Find Your Python Path

The MCP server needs to run from your dj-catalog virtual environment.

```bash
# If installed via pip
which python  # Note this path
```

### 2. Configure Claude Desktop

Edit your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the dj-catalog server:

```json
{
  "mcpServers": {
    "dj-catalog": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["-m", "dj_catalog.mcp.server"]
    }
  }
}
```

Replace `/path/to/your/venv/bin/python` with your actual path.

**Example (macOS):**
```json
{
  "mcpServers": {
    "dj-catalog": {
      "command": "/Users/yourname/.local/dj-catalog-venv/bin/python",
      "args": ["-m", "dj_catalog.mcp.server"]
    }
  }
}
```

**Example (Windows):**
```json
{
  "mcpServers": {
    "dj-catalog": {
      "command": "C:\\Users\\yourname\\.local\\dj-catalog-venv\\Scripts\\python.exe",
      "args": ["-m", "dj_catalog.mcp.server"]
    }
  }
}
```

### 3. Restart Claude Desktop

Quit and reopen Claude Desktop. You should see "dj-catalog" in the MCP servers list.

## Available Tools

Once connected, Claude can use these tools:

| Tool | Description |
|------|-------------|
| `search_tracks` | Search by tags, BPM, artist, or natural language |
| `generate_playlist` | Create playlists with filters and export |
| `get_stats` | View library statistics |
| `get_track_details` | Get full info for a specific track |
| `export_playlist` | Export tracks to M3U or Rekordbox XML |
| `scan_library` | Scan a directory for new tracks |
| `reset_database` | Clear all tracks (with confirmation) |
| `clean_orphans` | Remove tracks for deleted files |

## Usage Examples

Ask Claude:
- "Search for tech house tracks around 128 BPM"
- "Create a 60-minute afro house playlist and save it to my Desktop"
- "What are the top genres in my library?"
- "Show me details for that Fred Again track"

## Important: File Paths

**The MCP server runs on YOUR computer, not inside Claude Desktop.**

When exporting playlists, use paths on your local machine:

```
# Correct (your local machine)
~/Desktop/playlist.m3u
/Users/yourname/Downloads/set.m3u
C:\Users\yourname\Desktop\playlist.m3u

# Wrong (Claude's container - won't work!)
/mnt/user-data/outputs/playlist.m3u
/home/claude/playlist.m3u
```

## Troubleshooting

### "Server disconnected" error

1. Check the Python path in your config is correct
2. Verify dj-catalog is installed in that environment:
   ```bash
   /path/to/venv/bin/python -c "import dj_catalog; print('OK')"
   ```
3. Check Claude Desktop logs for errors

### "Permission denied" on export

- Don't use paths inside Claude Desktop's container
- Use paths on your local machine: `~/Desktop/playlist.m3u`

### Changes not appearing

After updating dj-catalog, restart Claude Desktop to reload the MCP server.
