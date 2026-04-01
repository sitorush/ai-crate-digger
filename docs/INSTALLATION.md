# Installation Guide

## Prerequisites

- **Python 3.11+** (required)
- **FFmpeg** (for audio processing)

### macOS
```bash
brew install python@3.11 ffmpeg
```

### Windows
1. Download Python 3.11+ from https://python.org
2. Download FFmpeg from https://ffmpeg.org and add to PATH

### Linux (Ubuntu/Debian)
```bash
sudo apt install python3.11 python3.11-venv ffmpeg
```

## Installation Methods

### Method 1: pip install (Recommended for Users)

```bash
# Create virtual environment
python3.11 -m venv ~/.local/dj-catalog-venv

# Activate it
source ~/.local/dj-catalog-venv/bin/activate  # macOS/Linux
# or
~\.local\dj-catalog-venv\Scripts\activate     # Windows

# Install dj-catalog
pip install dj-catalog
```

### Method 2: Install from Source (For Development)

```bash
# Clone the repo
git clone https://github.com/yourusername/dj-catalog.git
cd dj-catalog

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Verify Installation

```bash
dj --version
# Should output: dj-catalog, version 0.1.0

dj --help
# Shows available commands
```

## First Run

```bash
# Scan your music folder
dj scan ~/Music

# Check stats
dj stats
```

## Data Storage

dj-catalog stores data in `~/.dj-catalog/`:

| File | Purpose |
|------|---------|
| `catalog.db` | SQLite database with track metadata |
| `vectors/` | ChromaDB vector store for semantic search |
| `models/` | Downloaded ML models (Essentia) |

To use a custom location, set environment variables:

```bash
export DJ_CATALOG_DB_PATH=~/my-custom-path/catalog.db
export DJ_CATALOG_VECTOR_PATH=~/my-custom-path/vectors
```

## Claude Desktop Integration

See [MCP_SETUP.md](./MCP_SETUP.md) for Claude Desktop integration.
