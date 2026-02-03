# Atlassian Confluence API Guide

This guide documents the Confluence REST API endpoints used by the confluence-comments skill.

## Authentication

Confluence Cloud uses Basic Authentication with an API token:

```
Authorization: Basic base64(email:api_token)
```

### Generating an API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a descriptive label
4. Copy the token (it won't be shown again)

## Base URLs

| API Version | Base URL |
|-------------|----------|
| REST API v1 | `https://{domain}/wiki/rest/api/` |
| REST API v2 | `https://{domain}/wiki/api/v2/` |

## Endpoints Used

### Get Page by ID

Retrieves a single page with its content.

**Endpoint:** `GET /rest/api/content/{pageId}`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `expand` | string | Comma-separated list of properties to expand |

**Common expand values:**
- `body.storage` - Page content in storage format (HTML)
- `body.view` - Page content in view format
- `space` - Space information
- `version` - Version information
- `children.comment` - Child comments

**Example Request:**
```bash
curl -u email@example.com:API_TOKEN \
  "https://domain.atlassian.net/wiki/rest/api/content/123456?expand=body.storage,space,version"
```

**Example Response:**
```json
{
  "id": "123456",
  "type": "page",
  "status": "current",
  "title": "Page Title",
  "space": {
    "key": "MYSPACE",
    "name": "My Space"
  },
  "body": {
    "storage": {
      "value": "<p>Page content in HTML...</p>",
      "representation": "storage"
    }
  },
  "version": {
    "number": 5,
    "when": "2024-01-15T10:30:00.000Z",
    "by": {
      "email": "author@example.com"
    }
  }
}
```

### Search Content

Search for pages using CQL (Confluence Query Language).

**Endpoint:** `GET /rest/api/content/search`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `cql` | string | CQL query string |
| `limit` | integer | Maximum results to return (default: 25, max: 100) |
| `start` | integer | Starting index for pagination |

**CQL Examples:**
```
label="documentation"                    # Pages with specific label
space="MYSPACE" AND type=page           # Pages in a space
title~"API"                             # Title contains "API"
label="docs" AND space="ENG"            # Combined conditions
```

**Example Request:**
```bash
curl -u email@example.com:API_TOKEN \
  "https://domain.atlassian.net/wiki/rest/api/content/search?cql=label%3D%22documentation%22&limit=50"
```

### Get Content by Title

Find pages by title within a space.

**Endpoint:** `GET /rest/api/content`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | string | Exact page title |
| `spaceKey` | string | Space key to search in |
| `expand` | string | Properties to expand |

**Example Request:**
```bash
curl -u email@example.com:API_TOKEN \
  "https://domain.atlassian.net/wiki/rest/api/content?title=My%20Page&spaceKey=MYSPACE&expand=body.storage"
```

### Get Page Comments

Retrieves comments attached to a page.

**Endpoint:** `GET /rest/api/content/{pageId}/child/comment`

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `expand` | string | Properties to expand |
| `depth` | string | Comment depth: `all` or `root` |
| `limit` | integer | Maximum results |
| `start` | integer | Starting index |

**Recommended expand values:**
```
body.storage,version,children.comment.body.storage,extensions
```

**Example Request:**
```bash
curl -u email@example.com:API_TOKEN \
  "https://domain.atlassian.net/wiki/rest/api/content/123456/child/comment?expand=body.storage,version,extensions"
```

**Example Response:**
```json
{
  "results": [
    {
      "id": "789",
      "type": "comment",
      "body": {
        "storage": {
          "value": "<p>This is a comment</p>"
        }
      },
      "version": {
        "when": "2024-01-15T11:00:00.000Z",
        "by": {
          "email": "commenter@example.com"
        }
      },
      "extensions": {
        "inlineProperties": {
          "originalSelection": "highlighted text"
        }
      },
      "children": {
        "comment": {
          "results": []
        }
      }
    }
  ],
  "size": 1,
  "_links": {
    "next": "/rest/api/content/123456/child/comment?start=25"
  }
}
```

## Inline Comments

Inline comments have additional properties in the `extensions.inlineProperties` field:

| Property | Description |
|----------|-------------|
| `originalSelection` | The text that was highlighted when the comment was created |
| `markerRef` | Reference ID for the inline marker in the content |

### Identifying Inline vs Page Comments

```python
extensions = comment.get("extensions", {})
inline_props = extensions.get("inlineProperties", {})
is_inline = bool(inline_props)
```

## Storage Format

Confluence stores page content in a custom HTML-like format called "storage format."

### Common Elements

| Element | Description |
|---------|-------------|
| `<p>` | Paragraph |
| `<h1>` - `<h6>` | Headings |
| `<ac:structured-macro>` | Macros (code blocks, panels, etc.) |
| `<ac:inline-comment-marker>` | Inline comment anchor |
| `<ri:page>` | Page reference |
| `<ri:attachment>` | Attachment reference |

### Inline Comment Markers

When a user creates an inline comment, Confluence wraps the selected text:

```html
<p>Some text with
  <ac:inline-comment-marker ac:ref="abc123">
    highlighted text
  </ac:inline-comment-marker>
  and more content.
</p>
```

## Rate Limiting

Confluence Cloud enforces rate limits:

- **Standard:** 100 requests per minute per user
- **Burst:** Up to 10 requests per second

### Handling Rate Limits

When rate limited, the API returns:
- Status code: `429 Too Many Requests`
- Header: `Retry-After: <seconds>`

Implement exponential backoff:

```python
import time

def request_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        response = func()
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            time.sleep(retry_after * (attempt + 1))
            continue
        return response
    raise Exception("Max retries exceeded")
```

## Pagination

List endpoints return paginated results:

```json
{
  "results": [...],
  "start": 0,
  "limit": 25,
  "size": 25,
  "_links": {
    "next": "/rest/api/content?start=25&limit=25",
    "self": "/rest/api/content?start=0&limit=25"
  }
}
```

### Iterating All Results

```python
def get_all_pages(space_key):
    all_results = []
    start = 0
    limit = 100

    while True:
        response = get_content(space_key, start=start, limit=limit)
        results = response.get("results", [])
        all_results.extend(results)

        if len(results) < limit:
            break
        start += limit

    return all_results
```

## Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Bad request (invalid parameters) |
| 401 | Authentication required or failed |
| 403 | Permission denied |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

**Error Response Format:**
```json
{
  "statusCode": 404,
  "message": "No content found with id: 123456"
}
```

## API Version Differences

### v1 API (Legacy)
- More mature and complete
- Uses `/rest/api/` prefix
- Supports all comment operations

### v2 API (Modern)
- Cleaner response format
- Uses `/api/v2/` prefix
- Still adding feature parity with v1

This skill primarily uses v1 API for full comment support.

## Additional Resources

- [Confluence REST API Documentation](https://developer.atlassian.com/cloud/confluence/rest/v1/intro/)
- [Confluence Query Language (CQL)](https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/)
- [Storage Format Reference](https://developer.atlassian.com/cloud/confluence/confluence-storage-format/)
- [API Token Management](https://id.atlassian.com/manage-profile/security/api-tokens)
