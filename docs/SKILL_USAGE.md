# Confluence Comments Skill Usage Guide

This document explains how the `confluence-comments` custom skill works within the Claude Agent SDK framework.

## Overview

The `confluence-comments` skill enables Claude agents to fetch Confluence pages along with their comments (both inline and page-level) and map inline comments to the specific paragraphs they reference.

## Skill Location

```
skills/
└── confluence-comments/
    ├── SKILL.md              # Skill metadata and documentation
    ├── __init__.py
    ├── scripts/
    │   └── confluence_fetcher.py  # Core fetcher implementation
    └── references/
        └── API_GUIDE.md      # Atlassian API reference
```

## Skill Metadata

The skill is defined in `SKILL.md` with the following metadata:

```yaml
---
name: confluence-comments
description: Fetch and analyze Confluence pages with their inline and page-level comments
version: 1.0.0
dependencies:
  - atlassian-python-api>=4.0.7
  - httpx>=0.27.0
  - python-dotenv>=1.0.0
env_vars:
  - CONFLUENCE_BASE_URL
  - CONFLUENCE_USERNAME
  - CONFLUENCE_API_TOKEN
---
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONFLUENCE_BASE_URL` | Your Atlassian URL | `https://company.atlassian.net` |
| `CONFLUENCE_USERNAME` | Email for API authentication | `user@example.com` |
| `CONFLUENCE_API_TOKEN` | API token from Atlassian | `AbCdEf123456...` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFLUENCE_CLOUD` | Set to `true` for Atlassian Cloud | `true` |
| `CONFLUENCE_DEFAULT_SPACE` | Default space key | None |

### Claude API Configuration (for agent mode)

Choose ONE of the following options:

**Option 1: Direct Claude API**

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | `sk-ant-...` |

**Option 2: LiteLLM Proxy**

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_BASE_URL` | LiteLLM proxy URL | `http://localhost:4000/anthropic` |
| `ANTHROPIC_AUTH_TOKEN` | Your LiteLLM API key | `your-litellm-api-key` |

### Agent Configuration (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_MODEL` | Claude model to use | `claude-sonnet-4-20250514` |
| `SKILLS_DIRECTORY` | Path to skills directory | `skills` |
| `ALLOWED_TOOLS` | Comma-separated allowed tools | `Skill,Read,Write,Bash` |
| `MAX_TOKENS` | Maximum tokens for responses | `4096` |

## Using the Skill

### Programmatic Usage

```python
from skills.confluence_comments.scripts.confluence_fetcher import ConfluenceFetcher

# Initialize the fetcher
fetcher = ConfluenceFetcher()

# Fetch by page ID
page = fetcher.fetch_page_by_id("123456789", include_inline_comments=True)

# Fetch by page title
page = fetcher.fetch_page_by_title("My Document", space_key="MYSPACE")

# Fetch by label
pages = fetcher.fetch_pages_by_label(
    label="documentation",
    space_key="DOCS",
    include_comments=True,
    limit=50
)

# Fetch all pages with comments in a space
pages = fetcher.fetch_pages_with_comments(space_key="MYSPACE", limit=100)
```

### Agent Mode Usage

When running in agent mode, the skill is automatically available to the Claude agent:

```bash
python -m src.main --page-id 123456 --agent-mode
```

The agent can then use the skill's capabilities to:
1. Fetch Confluence content
2. Analyze comments and feedback
3. Map inline comments to specific content sections
4. Generate reports or summaries

## Output Data Structure

### PageWithComments

The skill returns data in the following structure:

```python
{
    "page_id": "123456789",
    "title": "Page Title",
    "space_key": "MYSPACE",
    "content": "Full page content in HTML or markdown",
    "url": "https://company.atlassian.net/wiki/spaces/MYSPACE/pages/123456789",
    "comments": {
        "page_level": [
            {
                "id": "comment-1",
                "author": "user@example.com",
                "created": "2024-01-15T10:30:00Z",
                "body": "This is a page-level comment",
                "replies": [
                    {
                        "id": "reply-1",
                        "author": "other@example.com",
                        "created": "2024-01-15T11:00:00Z",
                        "body": "Reply to the comment"
                    }
                ]
            }
        ],
        "inline": [
            {
                "id": "inline-1",
                "author": "reviewer@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "This needs clarification",
                "selection": "specific text highlighted",
                "paragraph_index": 3,
                "paragraph_text": "The full paragraph containing the selection...",
                "resolved": false,
                "replies": []
            }
        ]
    }
}
```

## Comment Mapping Process

The skill performs intelligent mapping of inline comments to paragraphs:

### 1. Paragraph Extraction

The content parser extracts paragraph-like elements from Confluence storage format:
- `<p>` - Paragraphs
- `<h1>` through `<h6>` - Headers
- `<li>` - List items
- `<td>` and `<th>` - Table cells

### 2. Inline Marker Detection

Confluence uses `<ac:inline-comment-marker>` elements to mark commented text:

```html
<p>This is text with
<ac:inline-comment-marker ac:ref="marker-123">highlighted content</ac:inline-comment-marker>
that has a comment.</p>
```

### 3. Mapping Strategies

Comments are mapped using multiple strategies (in order of preference):

1. **Marker Reference**: Direct match via `ac:ref` attribute
2. **Text Selection**: Match the highlighted text to paragraph content
3. **Original Selection**: Fallback to stored original selection text

### 4. Unmapped Comments

Comments that cannot be mapped (e.g., the referenced text was deleted) are collected separately and marked as "unmapped" in the output.

## Error Handling

### Authentication Failures

```python
# Returns clear error message
ConfluenceAPIError: Authentication failed (401).
Please verify your CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN.
```

### Page Not Found

```python
# Returns None instead of raising
page = fetcher.fetch_page_by_id("nonexistent")  # Returns None
```

### Rate Limiting

The fetcher automatically handles rate limiting:
- Detects 429 responses
- Reads `Retry-After` header
- Implements exponential backoff (configurable, default 3 retries)

```python
fetcher = ConfluenceFetcher(max_retries=5)  # Custom retry count
```

## Best Practices

### 1. Use Context Managers

```python
with ConfluenceFetcher() as fetcher:
    pages = fetcher.fetch_pages_by_label("review", space_key="DOCS")
    # Client is automatically closed when done
```

### 2. Handle Missing Data Gracefully

```python
page = fetcher.fetch_page_by_id("123456")
if page is None:
    print("Page not found")
    return

if not page.comments.inline:
    print("No inline comments on this page")
```

### 3. Limit Large Queries

```python
# Limit pages to avoid overwhelming the API
pages = fetcher.fetch_pages_by_label(
    label="documentation",
    space_key="DOCS",
    limit=25  # Reasonable limit
)
```

### 4. Cache Results When Appropriate

For repeated access to the same data, consider caching:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_page_cached(page_id: str):
    return fetcher.fetch_page_by_id(page_id)
```

## Integration with Claude Agent

### Skill Registration

The skill is automatically registered when the agent is initialized with the skills directory:

```python
from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions

options = ClaudeAgentOptions(
    api_key=api_key,
    setting_sources=["skills/"],  # Skills directory
    allowed_tools=["Skill", "Read", "Write"],
)

agent = ClaudeAgent(options)
```

### Agent Prompting

When using the agent, you can prompt it to use the Confluence skill:

```
Fetch the page "Project Requirements" from the DOCS space and summarize
all the feedback comments, grouping them by topic.
```

The agent will:
1. Use the skill to fetch the page
2. Process the comments
3. Generate the requested summary

### Claude Desktop Usage

To use this skill in Claude Desktop, add the skill directory to your Claude Desktop configuration. Then prompt Claude with natural language requests like:

```
Fetch all Confluence pages with the "review" label from the AIF space
and generate a comments report. Save it to comments.md
```

This is equivalent to running:
```bash
python -m src.main --label review --space AIF --output comments.md
```

Other example prompts:
- "Get comments from the Confluence page with ID 123456 and summarize the feedback"
- "Find all pages in the DOCS space that have comments and create a report"
- "Fetch the page titled 'API Design' from ENGINEERING and list all unresolved comments"

## Extending the Skill

### Adding New Fetch Methods

To add new ways to fetch pages, extend the `ConfluenceFetcher` class:

```python
def fetch_pages_by_author(
    self,
    author: str,
    space_key: str | None = None,
    limit: int = 50
) -> list[PageWithComments]:
    """Fetch pages created by a specific author."""
    cql = f'creator="{author}"'
    if space_key:
        cql += f' AND space="{space_key}"'
    # Implementation...
```

### Custom Report Formats

To generate different report formats, create new generator classes:

```python
class JSONReportGenerator:
    def generate(self, pages: list[PageWithComments]) -> str:
        return json.dumps([p.to_dict() for p in pages], indent=2)
```

## Troubleshooting

### "Connection refused" Errors

1. Verify your Confluence domain is accessible
2. Check for VPN requirements
3. Ensure no firewall blocking

### "Permission denied" for Specific Pages

1. Verify your account has access to the page
2. Check space-level permissions
3. Some pages may have restricted access

### Comments Not Mapping Correctly

1. The commented text may have been edited after commenting
2. Complex formatting may interfere with text matching
3. Check the `unmapped_inline_comments` list for orphaned comments

## API Reference

See `skills/confluence-comments/references/API_GUIDE.md` for detailed Atlassian API documentation including:
- Authentication details
- Endpoint specifications
- CQL query syntax
- Rate limiting behavior
- Response format examples
