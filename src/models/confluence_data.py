"""Data models for Confluence pages, paragraphs, and comments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Comment:
    """A comment on Confluence content.

    Represents both page-level and inline comments. Inline comments
    have additional location information (text_selection, resolved status).
    """

    id: str
    author: str
    created: str
    body: str
    parent_id: str | None = None
    text_selection: str | None = None
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "author": self.author,
            "created": self.created,
            "body": self.body,
            "parent_id": self.parent_id,
            "text_selection": self.text_selection,
            "resolved": self.resolved,
        }


@dataclass
class CommentThread:
    """A thread of comments with a root comment and replies.

    Represents a hierarchical comment structure where the root comment
    may have nested replies.
    """

    root: Comment
    replies: list[Comment] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Return the thread ID (same as root comment ID)."""
        return self.root.id

    @property
    def is_resolved(self) -> bool:
        """Check if the thread is resolved."""
        return self.root.resolved

    @property
    def all_comments(self) -> list[Comment]:
        """Return all comments in the thread (root + replies)."""
        return [self.root] + self.replies

    @property
    def reply_count(self) -> int:
        """Return the number of replies."""
        return len(self.replies)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "root": self.root.to_dict(),
            "replies": [r.to_dict() for r in self.replies],
            "reply_count": self.reply_count,
            "is_resolved": self.is_resolved,
        }


@dataclass
class Paragraph:
    """A paragraph extracted from Confluence page content.

    Stores both the raw HTML and extracted plain text, along with
    position information within the source document.
    """

    index: int
    text: str
    html: str = ""
    start_offset: int = 0
    end_offset: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "index": self.index,
            "text": self.text,
            "html": self.html,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }


@dataclass
class CommentedParagraph:
    """A paragraph with its associated comments.

    Links a paragraph to all comment threads that reference it,
    either through inline markers or text selection matching.
    """

    paragraph: Paragraph
    comment_threads: list[CommentThread] = field(default_factory=list)

    @property
    def index(self) -> int:
        """Return the paragraph index."""
        return self.paragraph.index

    @property
    def text(self) -> str:
        """Return the paragraph text."""
        return self.paragraph.text

    @property
    def comment_count(self) -> int:
        """Return total number of comments (including replies)."""
        return sum(len(thread.all_comments) for thread in self.comment_threads)

    @property
    def thread_count(self) -> int:
        """Return number of comment threads."""
        return len(self.comment_threads)

    @property
    def has_unresolved_comments(self) -> bool:
        """Check if any comment thread is unresolved."""
        return any(not thread.is_resolved for thread in self.comment_threads)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "paragraph": self.paragraph.to_dict(),
            "comment_threads": [t.to_dict() for t in self.comment_threads],
            "comment_count": self.comment_count,
            "thread_count": self.thread_count,
            "has_unresolved_comments": self.has_unresolved_comments,
        }


@dataclass
class PageWithComments:
    """A Confluence page with mapped comments.

    Aggregates page metadata, content, and all comments organized
    by their location (page-level or paragraph-specific).
    """

    page_id: str
    title: str
    space_key: str
    content: str
    url: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)
    commented_paragraphs: list[CommentedParagraph] = field(default_factory=list)
    page_level_comments: list[CommentThread] = field(default_factory=list)
    unmapped_inline_comments: list[CommentThread] = field(default_factory=list)

    @property
    def total_comments(self) -> int:
        """Return total number of comments on the page."""
        page_level = sum(len(t.all_comments) for t in self.page_level_comments)
        inline = sum(cp.comment_count for cp in self.commented_paragraphs)
        unmapped = sum(len(t.all_comments) for t in self.unmapped_inline_comments)
        return page_level + inline + unmapped

    @property
    def total_threads(self) -> int:
        """Return total number of comment threads."""
        return (
            len(self.page_level_comments)
            + sum(cp.thread_count for cp in self.commented_paragraphs)
            + len(self.unmapped_inline_comments)
        )

    @property
    def paragraphs_with_comments(self) -> list[CommentedParagraph]:
        """Return only paragraphs that have comments."""
        return [cp for cp in self.commented_paragraphs if cp.thread_count > 0]

    def get_paragraph(self, index: int) -> Paragraph | None:
        """Get a paragraph by its index."""
        if 0 <= index < len(self.paragraphs):
            return self.paragraphs[index]
        return None

    def get_comments_for_paragraph(self, index: int) -> list[CommentThread]:
        """Get all comment threads for a specific paragraph index."""
        for cp in self.commented_paragraphs:
            if cp.index == index:
                return cp.comment_threads
        return []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "page_id": self.page_id,
            "title": self.title,
            "space_key": self.space_key,
            "url": self.url,
            "content": self.content,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "commented_paragraphs": [cp.to_dict() for cp in self.paragraphs_with_comments],
            "page_level_comments": [t.to_dict() for t in self.page_level_comments],
            "unmapped_inline_comments": [t.to_dict() for t in self.unmapped_inline_comments],
            "stats": {
                "total_paragraphs": len(self.paragraphs),
                "paragraphs_with_comments": len(self.paragraphs_with_comments),
                "total_comments": self.total_comments,
                "total_threads": self.total_threads,
            },
        }
