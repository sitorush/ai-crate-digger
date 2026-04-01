# Connecting to Any MCP-Compatible App

ai-crate-digger implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io)  -- an open standard for connecting AI assistants to external tools. Any app that supports MCP can connect to your music library.

## What You Need

Two things in every MCP config:

1. **`command`**  -- the `crate` binary in your ai-crate-digger virtual environment
2. **`args`**  -- `["mcp-server"]`

```json
{
  "command": "/path/to/ai-crate-digger/.venv/bin/crate",
  "args": ["mcp-server"]
}
```

After cloning and running `uv sync`, the binary is at `<repo-dir>/.venv/bin/crate` (macOS/Linux) or `<repo-dir>\.venv\Scripts\crate.exe` (Windows).

## App-Specific Config Locations

| App | Config file |
|-----|-------------|
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **ChatGPT Desktop** | `~/Library/Application Support/OpenAI/ChatGPT/mcp.json` |
| **Cursor** | `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` globally |
| **Cline (VS Code)** | VS Code settings → Cline → MCP Servers → Add Server |
| **Continue** | `~/.continue/config.json` under `"mcpServers"` |
| **Zed** | `~/.config/zed/settings.json` under `"context_servers"` |

## Generic Config Block

Most apps use this structure under a key like `mcpServers` or `context_servers`:

```json
{
  "mcpServers": {
    "ai-crate-digger": {
      "command": "/Users/yourname/ai-crate-digger/.venv/bin/crate",
      "args": ["mcp-server"]
    }
  }
}
```

Replace `/Users/yourname/ai-crate-digger` with where you cloned the repo.

**Windows path:**
```json
{
  "mcpServers": {
    "ai-crate-digger": {
      "command": "C:\\Users\\yourname\\ai-crate-digger\\.venv\\Scripts\\crate.exe",
      "args": ["mcp-server"]
    }
  }
}
```

## Verify the Server Works

Test the server manually before configuring any app:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | /path/to/ai-crate-digger/.venv/bin/crate mcp-server
```

You should see a JSON response with `"result"` containing server capabilities. If you see an error, check the Python path and that the package is installed.

## Available Tools

Once connected, any MCP app can call these tools:

| Tool | Description |
|------|-------------|
| `search_tracks` | Search by tags, BPM, artist, key, or natural language |
| `generate_playlist` | Build playlists from filter criteria |
| `get_candidate_pool` | Get filtered tracks in compact JSON for AI selection |
| `validate_playlist_order` | Check for BPM jumps, key clashes, duplicates |
| `build_playlist` | Export ordered track list to M3U or Rekordbox XML |
| `get_stats` | Library statistics grouped by tag, artist, or key |
| `get_track_details` | Full metadata for a specific track |
| `export_playlist` | Export an existing playlist to file |
| `scan_library` | Scan a directory for new tracks |
| `reset_database` | Clear the database (with confirmation) |
| `clean_orphans` | Remove tracks for files that no longer exist |
