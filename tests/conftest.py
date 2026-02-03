"""Pytest fixtures and mock data for Confluence tests."""

from __future__ import annotations

import pytest

from src.confluence.client import InlineComment, Page, PageComment
from src.models.confluence_data import (
    Comment,
    CommentedParagraph,
    CommentThread,
    PageWithComments,
    Paragraph,
)


# ============================================================================
# Mock Confluence API Responses
# ============================================================================


@pytest.fixture
def mock_page_response() -> dict:
    """Mock response from Confluence API for a single page."""
    return {
        "id": "123456",
        "title": "Test Page Title",
        "space": {"key": "TEST"},
        "version": {"number": 5},
        "_links": {"webui": "/spaces/TEST/pages/123456/Test+Page+Title"},
    }


@pytest.fixture
def mock_page_content_response() -> dict:
    """Mock response for page content in storage format."""
    return {
        "id": "123456",
        "body": {
            "storage": {
                "value": """
<p>This is the first paragraph of the document.</p>
<p>This is the second paragraph with <ac:inline-comment-marker ac:ref="comment-1">highlighted text</ac:inline-comment-marker> that has a comment.</p>
<h2>Section Header</h2>
<p>Third paragraph under the section.</p>
<ul>
<li>First list item</li>
<li>Second list item with important content</li>
</ul>
""",
                "representation": "storage",
            }
        },
    }


@pytest.fixture
def mock_page_comments_response() -> dict:
    """Mock response for page-level comments."""
    return {
        "results": [
            {
                "id": "comment-100",
                "version": {
                    "by": {"email": "alice@example.com", "displayName": "Alice"},
                    "when": "2024-01-15T10:30:00.000Z",
                },
                "body": {"storage": {"value": "This is a page-level comment."}},
                "ancestors": [],
            },
            {
                "id": "comment-101",
                "version": {
                    "by": {"email": "bob@example.com", "displayName": "Bob"},
                    "when": "2024-01-15T11:00:00.000Z",
                },
                "body": {"storage": {"value": "This is a reply to the page comment."}},
                "ancestors": [{"id": "comment-100"}],
            },
        ],
        "size": 2,
    }


@pytest.fixture
def mock_inline_comments_response() -> dict:
    """Mock response for inline comments from v2 API."""
    return {
        "results": [
            {
                "id": "inline-1",
                "author": {"email": "charlie@example.com", "displayName": "Charlie"},
                "createdAt": "2024-01-16T09:00:00.000Z",
                "body": {"storage": {"value": "This needs clarification."}},
                "properties": {
                    "inline-marker-ref": {"value": "comment-1"},
                    "inline-original-selection": {"value": "highlighted text"},
                },
                "resolutionStatus": "open",
                "children": {
                    "results": [
                        {
                            "id": "inline-1-reply",
                            "author": {"email": "alice@example.com"},
                            "createdAt": "2024-01-16T09:30:00.000Z",
                            "body": {"storage": {"value": "I've updated this section."}},
                            "properties": {},
                            "resolutionStatus": "open",
                            "children": {"results": []},
                        }
                    ]
                },
            },
            {
                "id": "inline-2",
                "author": {"email": "bob@example.com"},
                "createdAt": "2024-01-17T14:00:00.000Z",
                "body": {"storage": {"value": "Great explanation!"}},
                "properties": {"inline-original-selection": {"value": "important content"}},
                "resolutionStatus": "resolved",
                "children": {"results": []},
            },
        ]
    }


@pytest.fixture
def mock_cql_search_response() -> dict:
    """Mock response for CQL search (label-based)."""
    return {
        "results": [
            {
                "content": {
                    "id": "123456",
                    "title": "Test Page 1",
                    "space": {"key": "TEST"},
                    "version": {"number": 3},
                    "_links": {"webui": "/spaces/TEST/pages/123456"},
                }
            },
            {
                "content": {
                    "id": "789012",
                    "title": "Test Page 2",
                    "space": {"key": "TEST"},
                    "version": {"number": 1},
                    "_links": {"webui": "/spaces/TEST/pages/789012"},
                }
            },
        ],
        "size": 2,
    }


@pytest.fixture
def mock_space_pages_response() -> list[dict]:
    """Mock response for getting all pages in a space."""
    return [
        {
            "id": "123456",
            "title": "Page with Comments",
            "space": {"key": "TEST"},
            "version": {"number": 2},
            "_links": {"webui": "/spaces/TEST/pages/123456"},
        },
        {
            "id": "789012",
            "title": "Page without Comments",
            "space": {"key": "TEST"},
            "version": {"number": 1},
            "_links": {"webui": "/spaces/TEST/pages/789012"},
        },
    ]


# ============================================================================
# Domain Object Fixtures
# ============================================================================


@pytest.fixture
def sample_page() -> Page:
    """Create a sample Page object."""
    return Page(
        id="123456",
        title="Test Page",
        space_key="TEST",
        content="<p>Sample content</p>",
        version=1,
        url="https://example.atlassian.net/wiki/spaces/TEST/pages/123456",
    )


@pytest.fixture
def sample_page_comments() -> list[PageComment]:
    """Create sample PageComment objects."""
    return [
        PageComment(
            id="comment-100",
            author="alice@example.com",
            created="2024-01-15T10:30:00.000Z",
            body="This is a page-level comment.",
            parent_id=None,
        ),
        PageComment(
            id="comment-101",
            author="bob@example.com",
            created="2024-01-15T11:00:00.000Z",
            body="This is a reply.",
            parent_id="comment-100",
        ),
    ]


@pytest.fixture
def sample_inline_comments() -> list[InlineComment]:
    """Create sample InlineComment objects."""
    return [
        InlineComment(
            id="inline-1",
            author="charlie@example.com",
            created="2024-01-16T09:00:00.000Z",
            body="This needs clarification.",
            text_selection="highlighted text",
            resolved=False,
            replies=[
                InlineComment(
                    id="inline-1-reply",
                    author="alice@example.com",
                    created="2024-01-16T09:30:00.000Z",
                    body="I've updated this.",
                    text_selection=None,
                    resolved=False,
                    replies=[],
                )
            ],
        ),
        InlineComment(
            id="inline-2",
            author="bob@example.com",
            created="2024-01-17T14:00:00.000Z",
            body="Great explanation!",
            text_selection="important content",
            resolved=True,
            replies=[],
        ),
    ]


@pytest.fixture
def sample_paragraphs() -> list[Paragraph]:
    """Create sample Paragraph objects."""
    return [
        Paragraph(
            index=0,
            text="This is the first paragraph of the document.",
            html="<p>This is the first paragraph of the document.</p>",
            start_offset=0,
            end_offset=55,
        ),
        Paragraph(
            index=1,
            text="This is the second paragraph with highlighted text that has a comment.",
            html='<p>This is the second paragraph with <ac:inline-comment-marker ac:ref="comment-1">highlighted text</ac:inline-comment-marker> that has a comment.</p>',
            start_offset=56,
            end_offset=200,
        ),
        Paragraph(
            index=2,
            text="Section Header",
            html="<h2>Section Header</h2>",
            start_offset=201,
            end_offset=230,
        ),
    ]


@pytest.fixture
def sample_comment() -> Comment:
    """Create a sample Comment object."""
    return Comment(
        id="comment-1",
        author="test@example.com",
        created="2024-01-15T10:00:00.000Z",
        body="This is a test comment.",
        parent_id=None,
        text_selection="selected text",
        resolved=False,
    )


@pytest.fixture
def sample_comment_thread(sample_comment: Comment) -> CommentThread:
    """Create a sample CommentThread object."""
    reply = Comment(
        id="comment-2",
        author="reply@example.com",
        created="2024-01-15T11:00:00.000Z",
        body="This is a reply.",
        parent_id="comment-1",
        text_selection=None,
        resolved=False,
    )
    return CommentThread(root=sample_comment, replies=[reply])


@pytest.fixture
def sample_page_with_comments(
    sample_paragraphs: list[Paragraph],
    sample_comment_thread: CommentThread,
) -> PageWithComments:
    """Create a sample PageWithComments object."""
    commented_paragraph = CommentedParagraph(
        paragraph=sample_paragraphs[1],
        comment_threads=[sample_comment_thread],
    )

    page_level_thread = CommentThread(
        root=Comment(
            id="page-comment-1",
            author="page@example.com",
            created="2024-01-14T08:00:00.000Z",
            body="General feedback on the page.",
            resolved=False,
        ),
        replies=[],
    )

    return PageWithComments(
        page_id="123456",
        title="Test Page",
        space_key="TEST",
        content="<p>Test content</p>",
        url="https://example.atlassian.net/wiki/spaces/TEST/pages/123456",
        paragraphs=sample_paragraphs,
        commented_paragraphs=[
            CommentedParagraph(paragraph=sample_paragraphs[0], comment_threads=[]),
            commented_paragraph,
            CommentedParagraph(paragraph=sample_paragraphs[2], comment_threads=[]),
        ],
        page_level_comments=[page_level_thread],
        unmapped_inline_comments=[],
    )


# ============================================================================
# Content Fixtures
# ============================================================================


@pytest.fixture
def confluence_storage_content() -> str:
    """Sample Confluence storage format content."""
    return """
<p>Introduction paragraph with some basic content.</p>
<p>Second paragraph with <ac:inline-comment-marker ac:ref="marker-123">important highlighted text</ac:inline-comment-marker> that needs attention.</p>
<h2>Main Section</h2>
<p>This section describes the main functionality.</p>
<ul>
<li>First bullet point</li>
<li>Second bullet point with <strong>bold text</strong></li>
<li>Third bullet point</li>
</ul>
<h3>Subsection</h3>
<p>Additional details in the subsection.</p>
<table>
<tr><th>Header 1</th><th>Header 2</th></tr>
<tr><td>Cell 1</td><td>Cell 2</td></tr>
</table>
"""


@pytest.fixture
def malformed_confluence_content() -> str:
    """Malformed Confluence content for edge case testing."""
    return """
<p>Unclosed paragraph
<p>Another paragraph</p>
<div><p>Nested paragraph</p></div>
<p>Paragraph with <span>inline elements</span> and <a href="#">links</a></p>
<p>   Paragraph with   extra   whitespace   </p>
"""
