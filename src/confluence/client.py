"""Confluence API client wrapping atlassian-python-api."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from atlassian import Confluence
from dotenv import load_dotenv

load_dotenv()


class ConfluenceError(Exception):
    """Base exception for Confluence API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ConfluenceAuthError(ConfluenceError):
    """Authentication error for Confluence API."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class ConfluenceNotFoundError(ConfluenceError):
    """Resource not found error."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


@dataclass
class PageComment:
    """A comment on a Confluence page."""

    id: str
    author: str
    created: str
    body: str
    parent_id: str | None = None


@dataclass
class InlineComment:
    """An inline comment from the v2 API."""

    id: str
    author: str
    created: str
    body: str
    text_selection: str | None = None
    resolved: bool = False
    replies: list[InlineComment] = field(default_factory=list)


@dataclass
class Page:
    """A Confluence page with metadata."""

    id: str
    title: str
    space_key: str
    content: str = ""
    version: int = 1
    url: str = ""


class ConfluenceClient:
    """Client for Confluence API operations using atlassian-python-api."""

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        api_token: str | None = None,
        cloud: bool = True,
    ):
        """Initialize the Confluence client.

        Args:
            url: Confluence base URL (e.g., 'https://company.atlassian.net')
            username: Username (email) for authentication
            api_token: API token for authentication
            cloud: Whether this is a Confluence Cloud instance (default: True)

        Raises:
            ConfluenceAuthError: If credentials are missing
        """
        self._url = url or os.getenv("CONFLUENCE_URL") or self._build_url_from_domain()
        self._username = username or os.getenv("CONFLUENCE_EMAIL")
        self._api_token = api_token or os.getenv("CONFLUENCE_API_TOKEN")
        self._cloud = cloud

        if not self._url:
            raise ConfluenceAuthError(
                "Missing Confluence URL. "
                "Set CONFLUENCE_URL or CONFLUENCE_DOMAIN environment variable."
            )
        if not self._username or not self._api_token:
            raise ConfluenceAuthError(
                "Missing credentials. "
                "Set CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN environment variables."
            )

        self._confluence = Confluence(
            url=self._url,
            username=self._username,
            password=self._api_token,
            cloud=self._cloud,
        )

        self._http_client: httpx.Client | None = None

    def _build_url_from_domain(self) -> str | None:
        """Build URL from CONFLUENCE_DOMAIN if set."""
        domain = os.getenv("CONFLUENCE_DOMAIN")
        if domain:
            if not domain.startswith("http"):
                return f"https://{domain}"
            return domain
        return None

    @property
    def _client(self) -> httpx.Client:
        """Get or create HTTP client for v2 API requests."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=f"{self._url}/wiki",
                auth=(self._username, self._api_token),
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._http_client

    def close(self) -> None:
        """Close any open connections."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def __enter__(self) -> ConfluenceClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _handle_api_error(self, error: Exception) -> None:
        """Convert API errors to appropriate exceptions."""
        error_str = str(error).lower()
        if "401" in error_str or "unauthorized" in error_str:
            raise ConfluenceAuthError("Invalid credentials or insufficient permissions")
        if "404" in error_str or "not found" in error_str:
            raise ConfluenceNotFoundError()
        raise ConfluenceError(str(error))

    def get_page_by_id(self, page_id: str, expand: str | None = None) -> Page:
        """Fetch a page by its ID.

        Args:
            page_id: The Confluence page ID
            expand: Additional fields to expand (comma-separated)

        Returns:
            Page object with metadata

        Raises:
            ConfluenceNotFoundError: If the page doesn't exist
            ConfluenceError: For other API errors
        """
        try:
            expand_fields = expand or "space,version"
            data = self._confluence.get_page_by_id(page_id, expand=expand_fields)

            if not data:
                raise ConfluenceNotFoundError(f"Page {page_id}")

            return Page(
                id=str(data.get("id", "")),
                title=data.get("title", ""),
                space_key=data.get("space", {}).get("key", ""),
                version=data.get("version", {}).get("number", 1),
                url=f"{self._url}/wiki{data.get('_links', {}).get('webui', '')}",
            )
        except Exception as e:
            if isinstance(e, (ConfluenceError, ConfluenceNotFoundError)):
                raise
            self._handle_api_error(e)
            raise  # unreachable, but satisfies type checker

    def get_pages_by_title(
        self, title: str, space_key: str, limit: int = 10
    ) -> list[Page]:
        """Search for pages by title in a space.

        Args:
            title: Page title to search for
            space_key: Space key to search in
            limit: Maximum number of results

        Returns:
            List of matching Page objects
        """
        try:
            results = self._confluence.get_page_by_title(
                space=space_key, title=title, expand="space,version"
            )

            if not results:
                return []

            if isinstance(results, dict):
                results = [results]

            pages = []
            for data in results[:limit]:
                pages.append(
                    Page(
                        id=str(data.get("id", "")),
                        title=data.get("title", ""),
                        space_key=space_key,
                        version=data.get("version", {}).get("number", 1),
                        url=f"{self._url}/wiki{data.get('_links', {}).get('webui', '')}",
                    )
                )
            return pages
        except Exception as e:
            if isinstance(e, ConfluenceError):
                raise
            self._handle_api_error(e)
            return []

    def get_pages_by_label(
        self, label: str, space_key: str | None = None, limit: int = 50
    ) -> list[Page]:
        """Fetch pages with a specific label.

        Args:
            label: Label to filter pages by
            space_key: Optional space key to limit search
            limit: Maximum number of results

        Returns:
            List of Page objects with the label
        """
        try:
            cql = f'label="{label}"'
            if space_key:
                cql = f'label="{label}" AND space="{space_key}"'

            results = self._confluence.cql(cql, limit=limit, expand="space,version")
            pages = []

            for item in results.get("results", []):
                content = item.get("content", item)
                pages.append(
                    Page(
                        id=str(content.get("id", "")),
                        title=content.get("title", ""),
                        space_key=content.get("space", {}).get("key", space_key or ""),
                        version=content.get("version", {}).get("number", 1),
                        url=f"{self._url}/wiki{content.get('_links', {}).get('webui', '')}",
                    )
                )
            return pages
        except Exception as e:
            if isinstance(e, ConfluenceError):
                raise
            self._handle_api_error(e)
            return []

    def get_pages_with_comments(self, space_key: str, limit: int = 100) -> list[Page]:
        """Fetch pages in a space that have comments.

        Args:
            space_key: Space key to search in
            limit: Maximum number of pages to check

        Returns:
            List of Page objects that have at least one comment
        """
        try:
            all_pages = self._confluence.get_all_pages_from_space(
                space=space_key, start=0, limit=limit, expand="space,version"
            )

            pages_with_comments = []
            for page_data in all_pages:
                page_id = str(page_data.get("id", ""))

                comments = self._confluence.get_page_comments(
                    content_id=page_id, expand="body.storage", depth="all"
                )

                if comments.get("results"):
                    pages_with_comments.append(
                        Page(
                            id=page_id,
                            title=page_data.get("title", ""),
                            space_key=space_key,
                            version=page_data.get("version", {}).get("number", 1),
                            url=f"{self._url}/wiki{page_data.get('_links', {}).get('webui', '')}",
                        )
                    )

            return pages_with_comments
        except Exception as e:
            if isinstance(e, ConfluenceError):
                raise
            self._handle_api_error(e)
            return []

    def get_inline_comments(self, page_id: str) -> list[InlineComment]:
        """Fetch inline comments for a page using the v2 API.

        Args:
            page_id: The Confluence page ID

        Returns:
            List of InlineComment objects

        Note:
            Uses /wiki/api/v2/pages/{id}/inline-comments endpoint
        """
        comments: list[InlineComment] = []

        try:
            response = self._client.get(
                f"/api/v2/pages/{page_id}/inline-comments",
                params={"body-format": "storage"},
            )

            if response.status_code == 401:
                raise ConfluenceAuthError()
            if response.status_code == 404:
                raise ConfluenceNotFoundError(f"Page {page_id}")

            response.raise_for_status()
            data = response.json()

            for item in data.get("results", []):
                comment = self._parse_inline_comment(item)
                comments.append(comment)

        except httpx.HTTPStatusError as e:
            raise ConfluenceError(
                f"Failed to fetch inline comments: {e}", status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            raise ConfluenceError(f"Request failed: {e}")

        return comments

    def _parse_inline_comment(self, data: dict[str, Any]) -> InlineComment:
        """Parse inline comment data from v2 API response."""
        body_data = data.get("body", {})
        body_value = body_data.get("storage", {}).get("value", "")

        author_data = data.get("author", {})
        author = author_data.get("email", author_data.get("displayName", "unknown"))

        properties = data.get("properties", {})
        # Properties can be either direct string values or nested dicts with 'value' key
        # inline-original-selection contains the actual highlighted text
        original_selection = properties.get("inline-original-selection")
        if isinstance(original_selection, dict):
            text_selection = original_selection.get("value")
        else:
            text_selection = original_selection

        replies = []
        for reply_data in data.get("children", {}).get("results", []):
            replies.append(self._parse_inline_comment(reply_data))

        return InlineComment(
            id=str(data.get("id", "")),
            author=author,
            created=data.get("createdAt", ""),
            body=body_value,
            text_selection=text_selection,
            resolved=data.get("resolutionStatus", "") == "resolved",
            replies=replies,
        )

    def get_page_content(self, page_id: str, body_format: str = "storage") -> str:
        """Fetch page body content.

        Args:
            page_id: The Confluence page ID
            body_format: Content format - 'storage', 'view', or 'export_view'

        Returns:
            Page content in the requested format

        Raises:
            ConfluenceNotFoundError: If the page doesn't exist
        """
        try:
            data = self._confluence.get_page_by_id(page_id, expand=f"body.{body_format}")

            if not data:
                raise ConfluenceNotFoundError(f"Page {page_id}")

            body = data.get("body", {})
            content_data = body.get(body_format, {})
            return content_data.get("value", "")
        except Exception as e:
            if isinstance(e, (ConfluenceError, ConfluenceNotFoundError)):
                raise
            self._handle_api_error(e)
            return ""

    def get_page_comments(self, page_id: str, depth: str = "all") -> list[PageComment]:
        """Fetch all comments for a page.

        Args:
            page_id: The Confluence page ID
            depth: Comment depth - 'all' or '' for root only

        Returns:
            List of PageComment objects
        """
        try:
            data = self._confluence.get_page_comments(
                content_id=page_id, expand="body.storage,version", depth=depth
            )

            comments = []
            for item in data.get("results", []):
                version = item.get("version", {})
                author_data = version.get("by", {})
                author = author_data.get("email", author_data.get("displayName", "unknown"))

                body_value = item.get("body", {}).get("storage", {}).get("value", "")

                parent_id = None
                ancestors = item.get("ancestors", [])
                if ancestors:
                    parent_id = str(ancestors[-1].get("id", ""))

                comments.append(
                    PageComment(
                        id=str(item.get("id", "")),
                        author=author,
                        created=version.get("when", ""),
                        body=body_value,
                        parent_id=parent_id,
                    )
                )

            return comments
        except Exception as e:
            if isinstance(e, ConfluenceError):
                raise
            self._handle_api_error(e)
            return []
