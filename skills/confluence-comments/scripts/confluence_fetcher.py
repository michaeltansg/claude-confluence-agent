"""Confluence API client for fetching pages with comments."""

from __future__ import annotations

import html
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class CommentReply:
    """A reply to a comment."""

    id: str
    author: str
    created: str
    body: str


@dataclass
class PageComment:
    """A page-level comment."""

    id: str
    author: str
    created: str
    body: str
    replies: list[CommentReply] = field(default_factory=list)


@dataclass
class InlineComment:
    """An inline comment attached to specific content."""

    id: str
    author: str
    created: str
    body: str
    selection: str | None
    paragraph_index: int | None
    paragraph_text: str | None
    replies: list[CommentReply] = field(default_factory=list)


@dataclass
class PageWithComments:
    """A Confluence page with its comments."""

    page_id: str
    title: str
    space_key: str
    content: str
    page_level_comments: list[PageComment] = field(default_factory=list)
    inline_comments: list[InlineComment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "page_id": self.page_id,
            "title": self.title,
            "space_key": self.space_key,
            "content": self.content,
            "comments": {
                "page_level": [
                    {
                        "id": c.id,
                        "author": c.author,
                        "created": c.created,
                        "body": c.body,
                        "replies": [
                            {"id": r.id, "author": r.author, "created": r.created, "body": r.body}
                            for r in c.replies
                        ],
                    }
                    for c in self.page_level_comments
                ],
                "inline": [
                    {
                        "id": c.id,
                        "author": c.author,
                        "created": c.created,
                        "body": c.body,
                        "selection": c.selection,
                        "paragraph_index": c.paragraph_index,
                        "paragraph_text": c.paragraph_text,
                        "replies": [
                            {"id": r.id, "author": r.author, "created": r.created, "body": r.body}
                            for r in c.replies
                        ],
                    }
                    for c in self.inline_comments
                ],
            },
        }


class ConfluenceAPIError(Exception):
    """Error from Confluence API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ConfluenceFetcher:
    """Client for fetching Confluence pages with comments."""

    def __init__(
        self,
        domain: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        default_space: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize the Confluence fetcher.

        Args:
            domain: Atlassian domain (e.g., 'company.atlassian.net')
            email: Email for authentication
            api_token: API token from Atlassian
            default_space: Default space key for operations
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        self.email = email or os.getenv("CONFLUENCE_EMAIL")
        self.api_token = api_token or os.getenv("CONFLUENCE_API_TOKEN")
        self.default_space = default_space or os.getenv("CONFLUENCE_DEFAULT_SPACE")
        self.timeout = timeout
        self.max_retries = max_retries

        if not all([self.domain, self.email, self.api_token]):
            raise ValueError(
                "Missing required configuration. Set CONFLUENCE_DOMAIN, "
                "CONFLUENCE_EMAIL, and CONFLUENCE_API_TOKEN environment variables "
                "or pass them to the constructor."
            )

        self.base_url = f"https://{self.domain}/wiki"
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                auth=(self.email, self.api_token),
                timeout=self.timeout,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> ConfluenceFetcher:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an API request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.request(method, endpoint, params=params)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    time.sleep(retry_after * (attempt + 1))
                    continue

                if response.status_code == 404:
                    raise ConfluenceAPIError("Resource not found", status_code=404)

                if response.status_code == 401:
                    raise ConfluenceAPIError(
                        "Authentication failed. Verify CONFLUENCE_EMAIL and "
                        "CONFLUENCE_API_TOKEN are correct.",
                        status_code=401,
                    )

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                time.sleep(2**attempt)
            except httpx.HTTPStatusError as e:
                raise ConfluenceAPIError(
                    f"HTTP error: {e.response.status_code}", status_code=e.response.status_code
                ) from e

        raise ConfluenceAPIError(f"Request failed after {self.max_retries} retries: {last_error}")

    def _get_v1(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the v1 REST API."""
        return self._request("GET", f"/rest/api/{endpoint}", params)

    def _get_v2(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the v2 REST API."""
        return self._request("GET", f"/api/v2/{endpoint}", params)

    def _extract_paragraphs(self, content: str) -> list[str]:
        """Extract paragraphs from Confluence storage format HTML."""
        paragraph_pattern = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
        matches = paragraph_pattern.findall(content)
        paragraphs = []
        for match in matches:
            text = re.sub(r"<[^>]+>", "", match)
            text = html.unescape(text).strip()
            if text:
                paragraphs.append(text)
        return paragraphs

    def _find_paragraph_for_selection(
        self, selection: str, paragraphs: list[str]
    ) -> tuple[int | None, str | None]:
        """Find the paragraph containing a text selection."""
        if not selection:
            return None, None

        selection_lower = selection.lower()
        for idx, para in enumerate(paragraphs):
            if selection_lower in para.lower():
                return idx, para

        return None, None

    def _parse_comment_replies(self, comment_data: dict[str, Any]) -> list[CommentReply]:
        """Parse replies from comment data."""
        replies = []
        children = comment_data.get("children", {}).get("comment", {}).get("results", [])

        for child in children:
            replies.append(
                CommentReply(
                    id=child.get("id", ""),
                    author=child.get("version", {}).get("by", {}).get("email", "unknown"),
                    created=child.get("version", {}).get("when", ""),
                    body=self._extract_comment_body(child),
                )
            )
        return replies

    def _extract_comment_body(self, comment_data: dict[str, Any]) -> str:
        """Extract comment body text from comment data."""
        body = comment_data.get("body", {})
        storage = body.get("storage", {}) or body.get("view", {})
        value = storage.get("value", "")
        text = re.sub(r"<[^>]+>", "", value)
        return html.unescape(text).strip()

    def _fetch_page_comments(
        self, page_id: str, paragraphs: list[str]
    ) -> tuple[list[PageComment], list[InlineComment]]:
        """Fetch all comments for a page."""
        page_comments: list[PageComment] = []
        inline_comments: list[InlineComment] = []

        try:
            params = {"expand": "body.storage,version,children.comment.body.storage,extensions"}
            result = self._get_v1(f"content/{page_id}/child/comment", params)

            for comment in result.get("results", []):
                extensions = comment.get("extensions", {})
                inline_properties = extensions.get("inlineProperties", {})
                is_inline = bool(inline_properties)

                author = comment.get("version", {}).get("by", {}).get("email", "unknown")
                created = comment.get("version", {}).get("when", "")
                body = self._extract_comment_body(comment)
                replies = self._parse_comment_replies(comment)

                if is_inline:
                    selection = inline_properties.get("originalSelection", "")
                    para_idx, para_text = self._find_paragraph_for_selection(selection, paragraphs)

                    inline_comments.append(
                        InlineComment(
                            id=comment.get("id", ""),
                            author=author,
                            created=created,
                            body=body,
                            selection=selection or None,
                            paragraph_index=para_idx,
                            paragraph_text=para_text,
                            replies=[
                                CommentReply(r.id, r.author, r.created, r.body) for r in replies
                            ],
                        )
                    )
                else:
                    page_comments.append(
                        PageComment(
                            id=comment.get("id", ""),
                            author=author,
                            created=created,
                            body=body,
                            replies=[
                                CommentReply(r.id, r.author, r.created, r.body) for r in replies
                            ],
                        )
                    )

        except ConfluenceAPIError:
            pass

        return page_comments, inline_comments

    def fetch_page_by_id(
        self, page_id: str, include_inline_comments: bool = True
    ) -> PageWithComments | None:
        """Fetch a page by its ID with comments.

        Args:
            page_id: The Confluence page ID
            include_inline_comments: Whether to fetch inline comments

        Returns:
            PageWithComments object or None if not found
        """
        try:
            params = {"expand": "body.storage,space,version"}
            data = self._get_v1(f"content/{page_id}", params)
        except ConfluenceAPIError as e:
            if e.status_code == 404:
                return None
            raise

        content = data.get("body", {}).get("storage", {}).get("value", "")
        paragraphs = self._extract_paragraphs(content) if include_inline_comments else []

        page_comments, inline_comments = self._fetch_page_comments(page_id, paragraphs)

        return PageWithComments(
            page_id=page_id,
            title=data.get("title", ""),
            space_key=data.get("space", {}).get("key", ""),
            content=content,
            page_level_comments=page_comments,
            inline_comments=inline_comments if include_inline_comments else [],
        )

    def fetch_page_by_title(
        self, title: str, space_key: str | None = None, include_inline_comments: bool = True
    ) -> PageWithComments | None:
        """Fetch a page by its title.

        Args:
            title: The page title to search for
            space_key: Space key to search in (uses default if not provided)
            include_inline_comments: Whether to fetch inline comments

        Returns:
            PageWithComments object or None if not found
        """
        space = space_key or self.default_space
        if not space:
            raise ValueError("space_key is required when CONFLUENCE_DEFAULT_SPACE is not set")

        params = {"title": title, "spaceKey": space, "expand": "body.storage,space,version"}
        result = self._get_v1("content", params)
        results = result.get("results", [])

        if not results:
            return None

        page_data = results[0]
        page_id = page_data.get("id", "")
        content = page_data.get("body", {}).get("storage", {}).get("value", "")
        paragraphs = self._extract_paragraphs(content) if include_inline_comments else []

        page_comments, inline_comments = self._fetch_page_comments(page_id, paragraphs)

        return PageWithComments(
            page_id=page_id,
            title=page_data.get("title", ""),
            space_key=space,
            content=content,
            page_level_comments=page_comments,
            inline_comments=inline_comments if include_inline_comments else [],
        )

    def fetch_pages_by_label(
        self, label: str, space_key: str | None = None, include_comments: bool = True, limit: int = 50
    ) -> list[PageWithComments]:
        """Fetch all pages with a specific label.

        Args:
            label: The label to filter pages by
            space_key: Optional space key to limit search
            include_comments: Whether to fetch comments for each page
            limit: Maximum number of pages to return

        Returns:
            List of PageWithComments objects
        """
        params: dict[str, Any] = {"cql": f'label="{label}"', "limit": limit}
        if space_key:
            params["cql"] = f'label="{label}" AND space="{space_key}"'

        result = self._get_v1("content/search", params)
        pages: list[PageWithComments] = []

        for page_data in result.get("results", []):
            page_id = page_data.get("id", "")
            if include_comments:
                page = self.fetch_page_by_id(page_id, include_inline_comments=True)
                if page:
                    pages.append(page)
            else:
                pages.append(
                    PageWithComments(
                        page_id=page_id,
                        title=page_data.get("title", ""),
                        space_key=page_data.get("space", {}).get("key", ""),
                        content="",
                        page_level_comments=[],
                        inline_comments=[],
                    )
                )

        return pages

    def fetch_pages_with_comments(
        self, space_key: str | None = None, limit: int = 100
    ) -> list[PageWithComments]:
        """Fetch all pages in a space that have at least one comment.

        Args:
            space_key: Space key to search in (uses default if not provided)
            limit: Maximum number of pages to check

        Returns:
            List of PageWithComments objects that have comments
        """
        space = space_key or self.default_space
        if not space:
            raise ValueError("space_key is required when CONFLUENCE_DEFAULT_SPACE is not set")

        params = {"spaceKey": space, "limit": limit, "expand": "body.storage,space"}
        result = self._get_v1("content", params)
        pages_with_comments: list[PageWithComments] = []

        for page_data in result.get("results", []):
            page_id = page_data.get("id", "")
            content = page_data.get("body", {}).get("storage", {}).get("value", "")
            paragraphs = self._extract_paragraphs(content)

            page_comments, inline_comments = self._fetch_page_comments(page_id, paragraphs)

            if page_comments or inline_comments:
                pages_with_comments.append(
                    PageWithComments(
                        page_id=page_id,
                        title=page_data.get("title", ""),
                        space_key=space,
                        content=content,
                        page_level_comments=page_comments,
                        inline_comments=inline_comments,
                    )
                )

        return pages_with_comments
