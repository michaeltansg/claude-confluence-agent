# Claude Agents

Claude Agent SDK with Confluence integration for extracting page comments and generating markdown reports.

## Overview

This project provides a command-line tool and library for:
- Fetching Confluence pages with their comments (both page-level and inline)
- Mapping inline comments to specific paragraphs in page content
- Generating professional markdown reports from the collected data

## Setup

### Prerequisites

- Python 3.10+
- Confluence API token
- Anthropic API key (optional, for agent mode)

### Installation

1. Clone the repository and navigate to the project directory.

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

   For development:
   ```bash
   pip install -e ".[dev]"
   ```

4. Copy the environment template and configure credentials:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your credentials:
   - `CONFLUENCE_DOMAIN`: Your Atlassian domain (e.g., `your-domain.atlassian.net`)
   - `CONFLUENCE_EMAIL`: Email associated with your Atlassian account
   - `CONFLUENCE_API_TOKEN`: Generate at https://id.atlassian.com/manage-profile/security/api-tokens
   - `ANTHROPIC_API_KEY`: Your Anthropic API key (optional)

## Usage

The tool supports four modes for fetching Confluence pages:

### 1. Fetch by Page ID

Retrieve a specific page by its Confluence page ID:

```bash
# Basic usage
python -m src.main --page-id 123456789

# With output file
python -m src.main --page-id 123456789 --output report.md

# Short form
python -m src.main -p 123456789 -o report.md
```

### 2. Fetch by Page Title

Search for and retrieve pages by title within a specific space:

```bash
# Basic usage
python -m src.main --page-title "Project Requirements" --space MYSPACE

# With output file
python -m src.main --page-title "Design Document" --space ENG --output design_comments.md

# Short form
python -m src.main -t "API Documentation" -s DOCS -o api_comments.md
```

### 3. Fetch by Label

Retrieve all pages with a specific label in a space:

```bash
# Basic usage
python -m src.main --label review --space MYSPACE

# With output file
python -m src.main --label needs-review --space DOCS --output review_report.md

# Short form
python -m src.main -l documentation -s WIKI -o docs_comments.md
```

### 4. Fetch All Pages with Comments

Retrieve all pages in a space that have at least one comment:

```bash
# Basic usage
python -m src.main --all-with-comments --space MYSPACE

# With output file
python -m src.main --all-with-comments --space ENG --output all_comments.md

# Short form
python -m src.main -a -s TEAM -o team_feedback.md
```

### Additional Options

```bash
# Specify custom .env file location
python -m src.main --page-id 123 --env-file /path/to/.env

# Run in agent mode (enables Claude agent with skills)
python -m src.main --page-id 123 --agent-mode
```

## Output Format

The generated markdown reports include:

- **Report Metadata**: Generation timestamp, statistics (total pages, comments, threads)
- **Table of Contents**: Links to each page section (for multi-page reports)
- **Page Sections**: For each page:
  - Page metadata (title, space, URL, comment count)
  - Page-level comments with author and timestamp
  - Inline comments mapped to specific paragraphs
  - Comment threads with replies
  - Resolution status indicators

Example output structure:

```markdown
# Confluence Comments Report

**Report Metadata**
| Metric | Value |
|--------|-------|
| Generated | 2024-01-15 10:30:00 UTC |
| Total Pages | 3 |
| Pages with Comments | 2 |
| Total Comments | 15 |

---

## My Page Title

**Link:** [https://company.atlassian.net/wiki/spaces/...]
**Space:** MYSPACE
**Page ID:** 123456
**Comments:** 5 (3 threads)

### Page-Level Comments

**[OPEN]** *reviewer@example.com* (2024-01-15T10:00:00Z):
  This document needs more detail in section 2.

### Inline Comments

#### Paragraph 2
> This paragraph contains the key requirements for the feature...

**[RESOLVED]** *editor@example.com* (2024-01-15T11:00:00Z):
  Please clarify the acceptance criteria.

  - *author@example.com* (2024-01-15T12:00:00Z):
    I've updated this section with more details.
```

## Project Structure

```
claude-agents/
├── src/                          # Main source code
│   ├── main.py                   # CLI entry point
│   ├── config/                   # Configuration management
│   │   └── agent_config.py
│   ├── confluence/               # Confluence API client
│   │   └── client.py
│   ├── models/                   # Data models
│   │   └── confluence_data.py
│   ├── processors/               # Comment processing
│   │   └── comment_mapper.py
│   └── generators/               # Report generation
│       ├── markdown_generator.py
│       └── templates/
├── skills/                       # Agent skills
│   └── confluence-comments/      # Confluence skill
├── tests/                        # Test suite
├── docs/                         # Documentation
├── examples/                     # Example outputs
├── pyproject.toml               # Project dependencies
└── README.md
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_confluence_client.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Lint code
ruff check .

# Format code
ruff format .

# Type check
mypy src/
```

### Adding New Features

1. Create tests in the appropriate `tests/test_*.py` file
2. Implement the feature in the corresponding module
3. Update documentation if the feature affects user-facing behavior
4. Run the full test suite before submitting changes

## API Reference

### ConfluenceClient

```python
from src.confluence import ConfluenceClient

# Initialize with explicit credentials
client = ConfluenceClient(
    url="https://company.atlassian.net",
    username="user@example.com",
    api_token="your-api-token",
    cloud=True,
)

# Or use environment variables
client = ConfluenceClient()

# Fetch a page
page = client.get_page_by_id("123456")
content = client.get_page_content("123456")
comments = client.get_page_comments("123456")
inline_comments = client.get_inline_comments("123456")
```

### CommentMapper

```python
from src.processors import CommentMapper

mapper = CommentMapper()

# Map comments to paragraphs
result = mapper.map_page_comments(
    page_id="123456",
    title="Page Title",
    space_key="SPACE",
    content=page_content,
    page_comments=page_comments_list,
    inline_comments=inline_comments_list,
    url="https://...",
)
```

### MarkdownReportGenerator

```python
from src.generators import MarkdownReportGenerator, ReportConfig

# Custom configuration
config = ReportConfig(
    title="My Custom Report",
    show_only_commented=True,
    include_resolved=False,
)

generator = MarkdownReportGenerator(config)
report = generator.generate(pages_with_comments)

# Access statistics
print(generator.stats.total_comments)
```

## Troubleshooting

### Authentication Errors

If you see "Authentication failed" errors:
1. Verify your `CONFLUENCE_EMAIL` is correct
2. Generate a new API token at https://id.atlassian.com/manage-profile/security/api-tokens
3. Ensure the token has appropriate permissions

### Page Not Found

If pages aren't found:
1. Verify the page ID or title is correct
2. Check that your account has access to the page
3. For title search, ensure you're specifying the correct space

### Rate Limiting

The client handles rate limiting automatically with exponential backoff. If you encounter persistent rate limit errors, reduce the number of concurrent requests or add delays between operations.

## License

MIT License - see LICENSE file for details.
