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

## Installation

```bash
git clone https://github.com/sitorush/ai-crate-digger.git
cd ai-crate-digger
uv sync
```

> **No uv?** Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Development install (with pre-commit hooks)

```bash
git clone https://github.com/sitorush/ai-crate-digger.git
cd ai-crate-digger
uv sync
uv run pre-commit install
```

## Verify Installation

```bash
crate --version
# Should output: ai-crate-digger, version 0.1.0

crate --help
# Shows available commands
```

## First Run

```bash
# Scan your music folder
crate scan ~/Music

# Check stats
crate stats
```

## Data Storage

ai-crate-digger stores data in `~/.ai-crate-digger/`:

| File | Purpose |
|------|---------|
| `catalog.db` | SQLite database with track metadata |
| `.chroma/` | ChromaDB vector store for semantic search |
| `models/` | Downloaded ML models (Essentia, optional) |

To use a custom location, set environment variables:

```bash
export CRATE_DB_PATH=~/my-custom-path/catalog.db
export CRATE_VECTOR_PATH=~/my-custom-path/vectors
```

## Optional: Essentia (ML Genre Classification)

Essentia provides ML-based genre classification for tracks without genre tags. It's a large dependency (~500MB) and optional.

```bash
# Requires TensorFlow — install TF first if you don't have it
pip install tensorflow
pip install essentia-tensorflow
```

If you don't want TensorFlow, there's a lighter CPU-only build:

```bash
pip install essentia
```

Without Essentia, genre classification falls back to folder name hints and existing ID3 tags.

## Connect to Claude Desktop or ChatGPT

- [Claude Desktop Setup](./MCP_CLAUDE.md)
- [ChatGPT Desktop Setup](./MCP_CHATGPT.md)
- [Other LLM Apps](./MCP_GENERIC.md)
