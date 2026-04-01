# Contributing

Pull requests welcome. Here's what you need to know.

## Setup

```bash
git clone https://github.com/sitorush/ai-crate-digger.git
cd ai-crate-digger
uv sync
uv run pre-commit install
```

## Running Tests

```bash
uv run pytest
```

Tests require no external services  -- audio analysis is mocked, the database uses in-memory SQLite.

## Code Style

- **Formatter/linter:** ruff (runs automatically via pre-commit)
- **Type checker:** mypy strict (runs automatically via pre-commit)
- **Python:** 3.11+, type hints on everything, no wildcard imports

Pre-commit runs ruff and mypy on every commit. To run manually:

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

## Project Structure

```
src/ai_crate_digger/
├── core/          # Models, config, exceptions
├── scanning/      # File discovery and metadata extraction
├── analysis/      # BPM, key, energy, genre detection
├── storage/       # SQLite (SQLAlchemy) + ChromaDB
├── playlist/      # Filtering, generation, harmonic mixing, export
├── cli/           # Click commands
└── mcp/           # MCP server and tool definitions
```

## Adding an MCP Tool

1. Add the tool definition to `src/ai_crate_digger/mcp/tools.py` in `list_tools()`
2. Add the handler in `call_tool()`
3. Write tests in `tests/mcp/`

## Submitting a PR

- Keep PRs focused  -- one feature or fix per PR
- Include tests for new behaviour
- Update relevant docs if adding/changing a CLI command or MCP tool
- Run `uv run pytest` before pushing
