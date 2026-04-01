# ChatGPT Desktop Integration (MCP)

ai-crate-digger works with the ChatGPT desktop app via the Model Context Protocol (MCP). The same server that powers Claude Desktop works here  -- only the config file location differs.

> **Requires:** ChatGPT desktop app (not the web app). Download from https://openai.com/chatgpt/download/

## Setup

### 1. Install ai-crate-digger

```bash
git clone https://github.com/sitorush/ai-crate-digger.git ~/ai-crate-digger
cd ~/ai-crate-digger
uv sync
```

> **No uv?** Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. Find the crate binary path

```bash
echo "$HOME/ai-crate-digger/.venv/bin/crate"
# e.g. /Users/yourname/ai-crate-digger/.venv/bin/crate
```

### 3. Configure ChatGPT Desktop

Open ChatGPT desktop → Settings → Developer → Edit Config.

The config file is at:

**macOS:** `~/Library/Application Support/OpenAI/ChatGPT/mcp.json`

**Windows:** `%APPDATA%\OpenAI\ChatGPT\mcp.json`

Add the following (create the file if it doesn't exist):

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

**Windows example:**
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

### 4. Restart ChatGPT Desktop

Quit and reopen. The ai-crate-digger tools should appear in the tools menu.

## Example Prompts

- "Search my music library for afro house tracks between 120 and 125 BPM"
- "Create a 90-minute warm-up set starting at 122 BPM and building to 128"
- "How many tracks do I have in each key?"
- "Find tracks similar to Peggy Gou  -- I want that Korean disco feel"
- "Export a tech house playlist to my Desktop in Rekordbox format"

## Differences vs Claude Desktop

| | Claude Desktop | ChatGPT Desktop |
|--|--|--|
| Config file location | `~/Library/Application Support/Claude/` | `~/Library/Application Support/OpenAI/ChatGPT/` |
| MCP server command | same | same |
| Tool names and behaviour | native MCP | native MCP |

The MCP server and all tools are identical  -- only where you put the config differs.

## Troubleshooting

**Tools not appearing**
1. Verify the binary path: `/path/to/.venv/bin/crate --version`
2. Check the JSON is valid (no trailing commas, correct quote style)
3. Restart ChatGPT Desktop after any config change

**"Permission denied" on export**
Use paths on your local machine (`~/Desktop/playlist.m3u`). Avoid paths inside ChatGPT's sandbox.

**Config path not found**
If the Developer settings aren't visible, check for a ChatGPT desktop app update  -- MCP support requires a recent version.
