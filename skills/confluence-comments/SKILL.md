---
name: confluence-comments
description: Fetch and analyze Confluence pages with their inline and page-level comments, mapping comments to specific content paragraphs
version: 1.0.0
dependencies:
  - atlassian-python-api>=4.0.7
  - httpx>=0.27.0
  - python-dotenv>=1.0.0
env_vars:
  - CONFLUENCE_DOMAIN
  - CONFLUENCE_EMAIL
  - CONFLUENCE_API_TOKEN
---

# Confluence Comments Skill

Fetch Confluence pages along with their comments (both inline and page-level) and map inline comments to the specific paragraphs they reference.

## Modes of Operation

### 1. Fetch by Label

Retrieve all pages with a specific label that have comments:

```python
from scripts.confluence_fetcher import ConfluenceFetcher

fetcher = ConfluenceFetcher()
pages = fetcher.fetch_pages_by_label("documentation", include_comments=True)
```

### 2. Fetch by Page ID

Retrieve a specific page by its Confluence page ID:

```python
page = fetcher.fetch_page_by_id("123456789", include_inline_comments=True)
```

### 3. Fetch by Page Title

Search for and retrieve a page by its title within a space:

```python
page = fetcher.fetch_page_by_title("My Page Title", space_key="MYSPACE")
```

### 4. Fetch All Pages with Comments

Retrieve all pages in a space that have at least one comment:

```python
pages = fetcher.fetch_pages_with_comments(space_key="MYSPACE")
```

## Comment Mapping

Inline comments are automatically mapped to their corresponding paragraphs in the page content. The skill parses the Confluence storage format and associates each inline comment with:

- The paragraph text it references
- The exact text selection (if available)
- The comment author and timestamp
- Any replies to the comment

### Output Format

```python
{
    "page_id": "123456789",
    "title": "Page Title",
    "space_key": "MYSPACE",
    "content": "Full page content in HTML or markdown",
    "comments": {
        "page_level": [
            {
                "id": "comment-1",
                "author": "user@example.com",
                "created": "2024-01-15T10:30:00Z",
                "body": "This is a page-level comment",
                "replies": []
            }
        ],
        "inline": [
            {
                "id": "inline-1",
                "author": "user@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "This needs clarification",
                "selection": "specific text highlighted",
                "paragraph_index": 3,
                "paragraph_text": "The full paragraph containing the selection...",
                "replies": [
                    {
                        "id": "reply-1",
                        "author": "other@example.com",
                        "created": "2024-01-15T11:30:00Z",
                        "body": "I've updated this section"
                    }
                ]
            }
        ]
    }
}
```

## Configuration

Set the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `CONFLUENCE_DOMAIN` | Your Atlassian domain (e.g., `company.atlassian.net`) | Yes |
| `CONFLUENCE_EMAIL` | Email for API authentication | Yes |
| `CONFLUENCE_API_TOKEN` | API token from Atlassian | Yes |
| `CONFLUENCE_DEFAULT_SPACE` | Default space key for operations | No |

## Error Handling

The skill handles common error scenarios:

- **Authentication failures**: Clear error message with instructions to verify credentials
- **Page not found**: Returns `None` with appropriate logging
- **Rate limiting**: Automatic retry with exponential backoff
- **Network errors**: Configurable timeout and retry behavior

## References

See `references/API_GUIDE.md` for detailed Atlassian API documentation.
