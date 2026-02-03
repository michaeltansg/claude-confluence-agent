# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Agents is a Python CLI tool for extracting Confluence page comments and generating markdown reports. It integrates with the Claude Agent SDK to provide skill-based automation.

## Commands

```bash
# Install dependencies
pip install -e .
pip install -e ".[dev]"  # includes test/lint tools

# Run the CLI
python -m src.main --page-id 123456
python -m src.main --space MYSPACE --label review
python -m src.main --space MYSPACE --all-with-comments
python -m src.main --page-title "Title" --space MYSPACE

# Run tests
pytest                              # all tests
pytest tests/test_confluence_client.py  # single file
pytest -k "test_name"               # single test by name

# Lint and type check
ruff check .
ruff format .
mypy src/
```

## Architecture

### Three-Stage Pipeline

The application processes data through: **ConfluenceClient → CommentMapper → MarkdownReportGenerator**

1. **ConfluenceClient** (`src/confluence/client.py`): Fetches pages and comments via Atlassian API. Uses `atlassian-python-api` for v1 REST API and `httpx` for v2 API (inline comments).

2. **CommentMapper** (`src/processors/comment_mapper.py`): Parses Confluence storage format (XML/HTML) to extract paragraphs and maps inline comments to them using marker refs or text selection matching.

3. **MarkdownReportGenerator** (`src/generators/markdown_generator.py`): Produces formatted markdown reports with metadata, TOC, and comment threads.

### Data Models (`src/models/confluence_data.py`)

Core hierarchy: `Comment` → `CommentThread` → `CommentedParagraph` → `PageWithComments`

- `Paragraph`: Extracted content segment with position offsets
- `CommentThread`: Root comment plus threaded replies
- `CommentedParagraph`: Links paragraphs to their comment threads
- `PageWithComments`: Complete page with all mapped and unmapped comments

### Configuration (`src/config/agent_config.py`)

Uses dataclasses with `from_env()` methods for loading from environment.

**Confluence (required):** `CONFLUENCE_BASE_URL`, `CONFLUENCE_USERNAME`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_CLOUD` (optional, default `true`)

**Claude API (choose one):**
- Direct: `ANTHROPIC_API_KEY`
- LiteLLM Proxy: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`

**Agent (optional):** `CLAUDE_MODEL`, `SKILLS_DIRECTORY`, `ALLOWED_TOOLS`, `MAX_TOKENS`

### Skills (`skills/confluence-comments/`)

Custom Claude agent skill with `ConfluenceFetcher` class. See `docs/SKILL_USAGE.md` for skill integration details.

## Key Patterns

- Confluence storage format uses `<ac:inline-comment-marker ac:ref="...">` elements for inline comment locations
- Comment mapping uses three strategies in order: marker ref, text selection, original selection
- All API clients support context managers for proper resource cleanup
- Exception hierarchy: `ConfluenceError` → `ConfluenceAuthError`, `ConfluenceNotFoundError`

## Test Structure

- `tests/conftest.py`: Shared fixtures and mock API responses
- Mock data simulates Confluence v1 and v2 API response formats
- Integration tests verify data flows correctly through the full pipeline
