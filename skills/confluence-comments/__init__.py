"""Confluence comments skill for fetching pages with inline and page-level comments."""

from .scripts.confluence_fetcher import (
    ConfluenceAPIError,
    ConfluenceFetcher,
    InlineComment,
    PageComment,
    PageWithComments,
)

__all__ = [
    "ConfluenceFetcher",
    "ConfluenceAPIError",
    "PageWithComments",
    "PageComment",
    "InlineComment",
]
