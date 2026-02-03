"""Tests for the comment mapper module."""

from __future__ import annotations

import pytest

from src.models.confluence_data import (
    Comment,
    CommentedParagraph,
    CommentThread,
    PageWithComments,
    Paragraph,
)
from src.processors.comment_mapper import CommentMapper, InlineCommentLocation


class TestParagraphExtraction:
    """Tests for paragraph extraction from Confluence content."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_extract_paragraphs_basic(self, mapper):
        """Test extracting paragraphs from basic HTML content."""
        content = "<p>First paragraph</p><p>Second paragraph</p>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 2
        assert paragraphs[0].text == "First paragraph"
        assert paragraphs[1].text == "Second paragraph"
        assert paragraphs[0].index == 0
        assert paragraphs[1].index == 1

    def test_extract_paragraphs_with_headers(self, mapper):
        """Test extracting headers as paragraphs."""
        content = "<h1>Title</h1><p>Content</p><h2>Section</h2>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 3
        assert paragraphs[0].text == "Title"
        assert paragraphs[1].text == "Content"
        assert paragraphs[2].text == "Section"

    def test_extract_paragraphs_with_list_items(self, mapper):
        """Test extracting list items as paragraphs."""
        content = "<ul><li>First item</li><li>Second item</li></ul>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 2
        assert paragraphs[0].text == "First item"
        assert paragraphs[1].text == "Second item"

    def test_extract_paragraphs_with_table_cells(self, mapper):
        """Test extracting table cells as paragraphs."""
        content = "<table><tr><th>Header</th></tr><tr><td>Cell</td></tr></table>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 2
        assert paragraphs[0].text == "Header"
        assert paragraphs[1].text == "Cell"

    def test_extract_paragraphs_strips_html_tags(self, mapper):
        """Test that HTML tags are stripped from paragraph text."""
        content = "<p>Text with <strong>bold</strong> and <em>italic</em></p>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 1
        assert paragraphs[0].text == "Text with bold and italic"

    def test_extract_paragraphs_normalizes_whitespace(self, mapper):
        """Test that whitespace is normalized in paragraphs."""
        content = "<p>   Text   with    extra   spaces   </p>"

        paragraphs = mapper.extract_paragraphs(content)

        assert paragraphs[0].text == "Text with extra spaces"

    def test_extract_paragraphs_preserves_html(self, mapper):
        """Test that original HTML is preserved in paragraph object."""
        content = "<p>Simple paragraph</p>"

        paragraphs = mapper.extract_paragraphs(content)

        assert "<p>" in paragraphs[0].html

    def test_extract_paragraphs_with_confluence_markers(self, mapper, confluence_storage_content):
        """Test extraction from Confluence storage format with markers."""
        paragraphs = mapper.extract_paragraphs(confluence_storage_content)

        # Should extract various paragraph-like elements
        assert len(paragraphs) > 0

        # Find the paragraph with the inline marker
        marker_para = next(
            (p for p in paragraphs if "highlighted" in p.text.lower()), None
        )
        assert marker_para is not None
        assert "important highlighted text" in marker_para.text

    def test_extract_paragraphs_skips_empty(self, mapper):
        """Test that empty paragraphs are skipped."""
        content = "<p></p><p>   </p><p>Content</p>"

        paragraphs = mapper.extract_paragraphs(content)

        assert len(paragraphs) == 1
        assert paragraphs[0].text == "Content"

    def test_extract_paragraphs_handles_malformed_html(self, mapper, malformed_confluence_content):
        """Test extraction from malformed HTML content."""
        paragraphs = mapper.extract_paragraphs(malformed_confluence_content)

        # Should still extract what it can
        assert len(paragraphs) > 0

    def test_extract_paragraphs_without_whitespace_normalization(self):
        """Test extraction without whitespace normalization."""
        mapper = CommentMapper(normalize_whitespace=False)
        content = "<p>Text   with   spaces</p>"

        paragraphs = mapper.extract_paragraphs(content)

        # Whitespace preserved (though still stripped at ends)
        assert "   " in paragraphs[0].text or paragraphs[0].text == "Text   with   spaces"


class TestInlineMarkerExtraction:
    """Tests for extracting inline comment markers."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_extract_inline_markers_basic(self, mapper):
        """Test extracting inline markers from content."""
        content = """
        <p>Text with <ac:inline-comment-marker ac:ref="marker-1">highlighted</ac:inline-comment-marker> content.</p>
        """

        markers = mapper.extract_inline_markers(content)

        assert "marker-1" in markers
        assert len(markers["marker-1"]) == 1

    def test_extract_inline_markers_multiple(self, mapper):
        """Test extracting multiple inline markers."""
        content = """
        <p><ac:inline-comment-marker ac:ref="marker-1">First</ac:inline-comment-marker> and
        <ac:inline-comment-marker ac:ref="marker-2">second</ac:inline-comment-marker></p>
        """

        markers = mapper.extract_inline_markers(content)

        assert len(markers) == 2
        assert "marker-1" in markers
        assert "marker-2" in markers

    def test_extract_inline_markers_none(self, mapper):
        """Test extraction when no markers exist."""
        content = "<p>Plain text without markers</p>"

        markers = mapper.extract_inline_markers(content)

        assert markers == {}


class TestCommentThreadBuilding:
    """Tests for building comment threads from flat lists."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_build_comment_threads_single(self, mapper):
        """Test building a single comment thread."""
        comments = [
            {
                "id": "1",
                "author": "user@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Root comment",
                "parent_id": None,
            }
        ]

        threads = mapper.build_comment_threads(comments)

        assert len(threads) == 1
        assert threads[0].root.id == "1"
        assert threads[0].reply_count == 0

    def test_build_comment_threads_with_replies(self, mapper):
        """Test building threads with replies."""
        comments = [
            {
                "id": "1",
                "author": "user1@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Root comment",
                "parent_id": None,
            },
            {
                "id": "2",
                "author": "user2@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "First reply",
                "parent_id": "1",
            },
            {
                "id": "3",
                "author": "user1@example.com",
                "created": "2024-01-15T12:00:00Z",
                "body": "Second reply",
                "parent_id": "1",
            },
        ]

        threads = mapper.build_comment_threads(comments)

        assert len(threads) == 1
        assert threads[0].root.id == "1"
        assert threads[0].reply_count == 2
        assert threads[0].replies[0].id == "2"
        assert threads[0].replies[1].id == "3"

    def test_build_comment_threads_multiple_roots(self, mapper):
        """Test building multiple independent threads."""
        comments = [
            {
                "id": "1",
                "author": "user@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "First thread",
                "parent_id": None,
            },
            {
                "id": "2",
                "author": "user@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "Second thread",
                "parent_id": None,
            },
        ]

        threads = mapper.build_comment_threads(comments)

        assert len(threads) == 2

    def test_build_comment_threads_nested_replies(self, mapper):
        """Test building threads with nested replies."""
        comments = [
            {
                "id": "1",
                "author": "user1@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Root",
                "parent_id": None,
            },
            {
                "id": "2",
                "author": "user2@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "Reply to root",
                "parent_id": "1",
            },
            {
                "id": "3",
                "author": "user3@example.com",
                "created": "2024-01-15T12:00:00Z",
                "body": "Reply to reply",
                "parent_id": "2",
            },
        ]

        threads = mapper.build_comment_threads(comments)

        assert len(threads) == 1
        # All nested replies should be flattened into the replies list
        assert len(threads[0].all_comments) == 3

    def test_build_comment_threads_empty(self, mapper):
        """Test building threads from empty list."""
        threads = mapper.build_comment_threads([])

        assert threads == []

    def test_build_comment_threads_preserves_resolved_status(self, mapper):
        """Test that resolved status is preserved in threads."""
        comments = [
            {
                "id": "1",
                "author": "user@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Comment",
                "parent_id": None,
                "resolved": True,
            }
        ]

        threads = mapper.build_comment_threads(comments)

        assert threads[0].is_resolved is True


class TestCommentToParagraphMapping:
    """Tests for mapping comments to paragraphs."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_map_comment_by_marker_ref(self, mapper, sample_paragraphs):
        """Test mapping comment using marker reference."""
        location = InlineCommentLocation(
            comment_id="1",
            marker_ref="marker-123",
        )
        marker_map = {"marker-123": [1]}  # Maps to paragraph index 1

        result = mapper.map_comment_to_paragraph(location, sample_paragraphs, marker_map)

        assert result == 1

    def test_map_comment_by_text_selection(self, mapper, sample_paragraphs):
        """Test mapping comment using text selection."""
        location = InlineCommentLocation(
            comment_id="1",
            text_selection="highlighted text",
        )

        result = mapper.map_comment_to_paragraph(location, sample_paragraphs)

        assert result == 1  # Should match paragraph with "highlighted text"

    def test_map_comment_by_original_selection(self, mapper, sample_paragraphs):
        """Test mapping comment using original selection fallback."""
        location = InlineCommentLocation(
            comment_id="1",
            original_selection="Section Header",
        )

        result = mapper.map_comment_to_paragraph(location, sample_paragraphs)

        assert result == 2  # Should match "Section Header"

    def test_map_comment_no_match(self, mapper, sample_paragraphs):
        """Test that unmatched comment returns None."""
        location = InlineCommentLocation(
            comment_id="1",
            text_selection="nonexistent text",
        )

        result = mapper.map_comment_to_paragraph(location, sample_paragraphs)

        assert result is None

    def test_map_comment_case_insensitive(self, mapper, sample_paragraphs):
        """Test that text matching is case-insensitive."""
        location = InlineCommentLocation(
            comment_id="1",
            text_selection="SECTION HEADER",
        )

        result = mapper.map_comment_to_paragraph(location, sample_paragraphs)

        assert result == 2


class TestMapPageComments:
    """Tests for the main map_page_comments method."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_map_page_comments_full_pipeline(self, mapper):
        """Test full comment mapping pipeline."""
        content = """
        <p>Introduction paragraph.</p>
        <p>Paragraph with <ac:inline-comment-marker ac:ref="marker-1">important content</ac:inline-comment-marker>.</p>
        """

        page_comments = [
            {
                "id": "page-1",
                "author": "user@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Page-level feedback",
            }
        ]

        inline_comments = [
            {
                "id": "inline-1",
                "author": "reviewer@example.com",
                "created": "2024-01-15T11:00:00Z",
                "body": "Please clarify this",
                "text_selection": "important content",
            }
        ]

        result = mapper.map_page_comments(
            page_id="123",
            title="Test Page",
            space_key="TEST",
            content=content,
            page_comments=page_comments,
            inline_comments=inline_comments,
            url="https://example.com/page/123",
        )

        assert isinstance(result, PageWithComments)
        assert result.page_id == "123"
        assert result.title == "Test Page"
        assert len(result.page_level_comments) == 1
        assert len(result.paragraphs) == 2

        # Check that inline comment was mapped
        paragraphs_with_comments = result.paragraphs_with_comments
        assert len(paragraphs_with_comments) == 1
        assert "important content" in paragraphs_with_comments[0].text

    def test_map_page_comments_with_unmapped(self, mapper):
        """Test that unmapped comments are tracked."""
        content = "<p>Simple paragraph</p>"

        inline_comments = [
            {
                "id": "inline-1",
                "author": "user@example.com",
                "created": "2024-01-15T10:00:00Z",
                "body": "Comment on deleted text",
                "text_selection": "text that no longer exists",
            }
        ]

        result = mapper.map_page_comments(
            page_id="123",
            title="Test",
            space_key="TEST",
            content=content,
            page_comments=[],
            inline_comments=inline_comments,
        )

        assert len(result.unmapped_inline_comments) == 1

    def test_map_page_comments_empty_content(self, mapper):
        """Test mapping with empty page content."""
        result = mapper.map_page_comments(
            page_id="123",
            title="Empty Page",
            space_key="TEST",
            content="",
            page_comments=[],
            inline_comments=[],
        )

        assert result.page_id == "123"
        assert len(result.paragraphs) == 0
        assert result.total_comments == 0


class TestHelperMethods:
    """Tests for helper methods in CommentMapper."""

    @pytest.fixture
    def mapper(self):
        """Create a CommentMapper instance."""
        return CommentMapper()

    def test_strip_html_tags(self, mapper):
        """Test HTML tag stripping."""
        html = "<p>Text with <strong>bold</strong> and <a href='#'>link</a></p>"

        result = mapper._strip_html_tags(html)

        assert "<" not in result
        assert "bold" in result
        assert "link" in result

    def test_strip_html_tags_with_markers(self, mapper):
        """Test that inline markers are removed but content preserved."""
        html = 'Text with <ac:inline-comment-marker ac:ref="1">marked content</ac:inline-comment-marker> here'

        result = mapper._strip_html_tags(html)

        assert "marked content" in result
        assert "ac:inline-comment-marker" not in result

    def test_normalize_whitespace(self, mapper):
        """Test whitespace normalization."""
        text = "  Multiple   spaces   and\n\nnewlines  "

        result = mapper._normalize_whitespace(text)

        assert result == "Multiple spaces and newlines"

    def test_find_paragraph_by_text_exact(self, mapper, sample_paragraphs):
        """Test finding paragraph by exact text."""
        result = mapper._find_paragraph_by_text("Section Header", sample_paragraphs)

        assert result == 2

    def test_find_paragraph_by_text_partial(self, mapper, sample_paragraphs):
        """Test finding paragraph by partial text."""
        result = mapper._find_paragraph_by_text("first paragraph", sample_paragraphs)

        assert result == 0

    def test_find_paragraph_by_text_empty(self, mapper, sample_paragraphs):
        """Test that empty text returns None."""
        result = mapper._find_paragraph_by_text("", sample_paragraphs)

        assert result is None

    def test_find_paragraph_by_text_no_match(self, mapper, sample_paragraphs):
        """Test that non-matching text returns None."""
        result = mapper._find_paragraph_by_text("xyz not found", sample_paragraphs)

        assert result is None
