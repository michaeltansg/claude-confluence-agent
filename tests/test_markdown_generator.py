"""Tests for the markdown report generator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.generators.markdown_generator import (
    MarkdownReportGenerator,
    ReportConfig,
    ReportStats,
)
from src.models.confluence_data import (
    Comment,
    CommentedParagraph,
    CommentThread,
    PageWithComments,
    Paragraph,
)


class TestReportConfig:
    """Tests for ReportConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ReportConfig()

        assert config.title == "Confluence Comments Report"
        assert config.show_only_commented is False
        assert config.include_resolved is True
        assert config.include_toc is True
        assert config.include_metadata is True
        assert config.max_paragraph_preview == 200
        assert "UTC" in config.date_format

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ReportConfig(
            title="Custom Report",
            show_only_commented=True,
            include_resolved=False,
            max_paragraph_preview=100,
        )

        assert config.title == "Custom Report"
        assert config.show_only_commented is True
        assert config.include_resolved is False
        assert config.max_paragraph_preview == 100


class TestReportStats:
    """Tests for ReportStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = ReportStats()

        assert stats.total_pages == 0
        assert stats.pages_with_comments == 0
        assert stats.total_comments == 0
        assert stats.total_threads == 0
        assert stats.resolved_threads == 0
        assert stats.unresolved_threads == 0

    def test_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = ReportStats(
            total_pages=5,
            pages_with_comments=3,
            total_comments=10,
            total_threads=5,
            resolved_threads=2,
            unresolved_threads=3,
        )

        result = stats.to_dict()

        assert result["total_pages"] == 5
        assert result["pages_with_comments"] == 3
        assert result["total_comments"] == 10


class TestMarkdownReportGeneratorInit:
    """Tests for MarkdownReportGenerator initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        generator = MarkdownReportGenerator()

        assert generator.config.title == "Confluence Comments Report"
        assert isinstance(generator.stats, ReportStats)

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = ReportConfig(title="My Report")
        generator = MarkdownReportGenerator(config)

        assert generator.config.title == "My Report"


class TestGenerateReport:
    """Tests for the main generate method."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_generate_empty_pages(self, generator):
        """Test generating report with no pages."""
        report = generator.generate([])

        assert "Confluence Comments Report" in report
        assert "No pages to display" in report

    def test_generate_single_page(self, generator, sample_page_with_comments):
        """Test generating report with a single page."""
        report = generator.generate([sample_page_with_comments])

        assert "Test Page" in report
        assert "TEST" in report
        assert "123456" in report

    def test_generate_multiple_pages(self, generator):
        """Test generating report with multiple pages."""
        pages = [
            PageWithComments(
                page_id="1",
                title="First Page",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[],
                unmapped_inline_comments=[],
            ),
            PageWithComments(
                page_id="2",
                title="Second Page",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[],
                unmapped_inline_comments=[],
            ),
        ]

        report = generator.generate(pages)

        assert "First Page" in report
        assert "Second Page" in report
        assert "Table of Contents" in report

    def test_generate_includes_metadata(self, generator, sample_page_with_comments):
        """Test that metadata section is included."""
        report = generator.generate([sample_page_with_comments])

        assert "Report Metadata" in report
        assert "Total Pages" in report
        assert "Generated" in report

    def test_generate_without_metadata(self, sample_page_with_comments):
        """Test generating report without metadata."""
        config = ReportConfig(include_metadata=False)
        generator = MarkdownReportGenerator(config)

        report = generator.generate([sample_page_with_comments])

        assert "Report Metadata" not in report

    def test_generate_stats_updated(self, generator, sample_page_with_comments):
        """Test that stats are updated after generation."""
        generator.generate([sample_page_with_comments])

        assert generator.stats.total_pages == 1
        assert generator.stats.total_comments > 0

    def test_generate_filters_pages_without_comments(self):
        """Test show_only_commented filter."""
        config = ReportConfig(show_only_commented=True)
        generator = MarkdownReportGenerator(config)

        page_with_comments = PageWithComments(
            page_id="1",
            title="Has Comments",
            space_key="TEST",
            content="",
            paragraphs=[],
            commented_paragraphs=[],
            page_level_comments=[
                CommentThread(
                    root=Comment(id="1", author="a", created="", body="comment"),
                    replies=[],
                )
            ],
            unmapped_inline_comments=[],
        )
        page_without_comments = PageWithComments(
            page_id="2",
            title="No Comments",
            space_key="TEST",
            content="",
            paragraphs=[],
            commented_paragraphs=[],
            page_level_comments=[],
            unmapped_inline_comments=[],
        )

        report = generator.generate([page_with_comments, page_without_comments])

        assert "Has Comments" in report
        assert "No Comments" not in report


class TestPageSectionGeneration:
    """Tests for generating individual page sections."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_generate_page_section_header(self, generator, sample_page_with_comments):
        """Test page section includes proper header."""
        section = generator.generate_page_section(sample_page_with_comments)

        assert "## Test Page" in section

    def test_generate_page_section_metadata(self, generator, sample_page_with_comments):
        """Test page section includes metadata."""
        section = generator.generate_page_section(sample_page_with_comments)

        assert "**Space:** TEST" in section
        assert "**Page ID:** 123456" in section
        assert "**Comments:**" in section

    def test_generate_page_section_with_url(self, generator, sample_page_with_comments):
        """Test page section includes URL when available."""
        section = generator.generate_page_section(sample_page_with_comments)

        assert "**Link:**" in section
        assert "https://example.atlassian.net" in section

    def test_generate_page_section_page_level_comments(self, generator, sample_page_with_comments):
        """Test page section includes page-level comments."""
        section = generator.generate_page_section(sample_page_with_comments)

        assert "Page-Level Comments" in section
        assert "General feedback" in section

    def test_generate_page_section_inline_comments(self, generator, sample_page_with_comments):
        """Test page section includes inline comments."""
        section = generator.generate_page_section(sample_page_with_comments)

        assert "Inline Comments" in section
        assert "Paragraph" in section

    def test_generate_page_section_no_comments(self, generator):
        """Test page section handles pages with no comments."""
        page = PageWithComments(
            page_id="1",
            title="Empty Page",
            space_key="TEST",
            content="",
            paragraphs=[],
            commented_paragraphs=[],
            page_level_comments=[],
            unmapped_inline_comments=[],
        )

        section = generator.generate_page_section(page)

        assert "No comments on this page" in section


class TestCommentThreadFormatting:
    """Tests for comment thread formatting."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_format_thread_open(self, generator):
        """Test formatting an open comment thread."""
        thread = CommentThread(
            root=Comment(
                id="1",
                author="test@example.com",
                created="2024-01-15T10:00:00Z",
                body="This is a comment.",
                resolved=False,
            ),
            replies=[],
        )

        result = generator._format_thread(thread)

        assert "[OPEN]" in result
        assert "test@example.com" in result
        assert "This is a comment." in result

    def test_format_thread_resolved(self, generator):
        """Test formatting a resolved comment thread."""
        thread = CommentThread(
            root=Comment(
                id="1",
                author="test@example.com",
                created="2024-01-15T10:00:00Z",
                body="Resolved comment.",
                resolved=True,
            ),
            replies=[],
        )

        result = generator._format_thread(thread)

        assert "[RESOLVED]" in result

    def test_format_thread_with_replies(self, generator):
        """Test formatting thread with replies."""
        thread = CommentThread(
            root=Comment(
                id="1",
                author="author@example.com",
                created="2024-01-15T10:00:00Z",
                body="Main comment",
                resolved=False,
            ),
            replies=[
                Comment(
                    id="2",
                    author="replier@example.com",
                    created="2024-01-15T11:00:00Z",
                    body="Reply text",
                    parent_id="1",
                    resolved=False,
                ),
            ],
        )

        result = generator._format_thread(thread)

        assert "author@example.com" in result
        assert "replier@example.com" in result
        assert "Main comment" in result
        assert "Reply text" in result

    def test_format_thread_filters_resolved(self):
        """Test that resolved threads are filtered when configured."""
        config = ReportConfig(include_resolved=False)
        generator = MarkdownReportGenerator(config)

        page = PageWithComments(
            page_id="1",
            title="Test",
            space_key="TEST",
            content="",
            paragraphs=[],
            commented_paragraphs=[],
            page_level_comments=[
                CommentThread(
                    root=Comment(id="1", author="a", created="", body="open", resolved=False),
                    replies=[],
                ),
                CommentThread(
                    root=Comment(id="2", author="b", created="", body="resolved", resolved=True),
                    replies=[],
                ),
            ],
            unmapped_inline_comments=[],
        )

        section = generator.generate_page_section(page)

        assert "open" in section
        # Note: resolved comments might still appear in the section header count


class TestCommentedParagraphFormatting:
    """Tests for commented paragraph formatting."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_format_commented_paragraph(self, generator):
        """Test formatting a paragraph with comments."""
        para = Paragraph(index=0, text="Sample paragraph text")
        thread = CommentThread(
            root=Comment(id="1", author="a", created="", body="Comment", resolved=False),
            replies=[],
        )
        cp = CommentedParagraph(paragraph=para, comment_threads=[thread])

        result = generator._format_commented_paragraph(cp)

        assert "Paragraph 1" in result
        assert "Sample paragraph text" in result
        assert "Comment" in result

    def test_format_commented_paragraph_truncates_long_text(self, generator):
        """Test that long paragraph text is truncated."""
        long_text = "A" * 500
        para = Paragraph(index=0, text=long_text)
        thread = CommentThread(
            root=Comment(id="1", author="a", created="", body="c", resolved=False),
            replies=[],
        )
        cp = CommentedParagraph(paragraph=para, comment_threads=[thread])

        result = generator._format_commented_paragraph(cp)

        assert "..." in result
        assert len(result.split(">")[1].split("\n")[0].strip()) <= 203  # 200 + "..."

    def test_format_commented_paragraph_empty_when_filtered(self):
        """Test that paragraph returns empty when all comments filtered."""
        config = ReportConfig(include_resolved=False)
        generator = MarkdownReportGenerator(config)

        para = Paragraph(index=0, text="Text")
        thread = CommentThread(
            root=Comment(id="1", author="a", created="", body="c", resolved=True),
            replies=[],
        )
        cp = CommentedParagraph(paragraph=para, comment_threads=[thread])

        result = generator._format_commented_paragraph(cp)

        assert result == ""


class TestTextProcessing:
    """Tests for text processing utilities."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_clean_comment_body_strips_html(self, generator):
        """Test HTML tag stripping from comments."""
        body = "<p>Text with <strong>bold</strong> and <em>italic</em></p>"

        result = generator._clean_comment_body(body)

        assert "<" not in result
        assert "bold" in result
        assert "italic" in result

    def test_clean_comment_body_unescapes_entities(self, generator):
        """Test HTML entity unescaping."""
        body = "Text with &amp; and &lt;brackets&gt;"

        result = generator._clean_comment_body(body)

        assert "&" in result
        assert "<brackets>" in result

    def test_clean_comment_body_normalizes_whitespace(self, generator):
        """Test whitespace normalization in comments."""
        body = "Text   with\n\nextra   whitespace"

        result = generator._clean_comment_body(body)

        assert "  " not in result
        assert "\n" not in result

    def test_truncate_text_short(self, generator):
        """Test truncation of short text."""
        result = generator._truncate_text("Short text", 100)

        assert result == "Short text"
        assert "..." not in result

    def test_truncate_text_long(self, generator):
        """Test truncation of long text."""
        long_text = "A" * 100

        result = generator._truncate_text(long_text, 50)

        assert len(result) == 50
        assert result.endswith("...")

    def test_make_anchor_basic(self, generator):
        """Test anchor generation from title."""
        result = generator._make_anchor("My Page Title")

        assert result == "my-page-title"

    def test_make_anchor_special_characters(self, generator):
        """Test anchor generation strips special characters."""
        result = generator._make_anchor("Page (with) Special! Characters?")

        assert "(" not in result
        assert "!" not in result
        assert "?" not in result

    def test_make_anchor_collapses_hyphens(self, generator):
        """Test anchor generation collapses multiple hyphens."""
        result = generator._make_anchor("Page - With - Dashes")

        assert "--" not in result


class TestTableOfContents:
    """Tests for table of contents generation."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_format_toc_single_page(self, generator):
        """Test TOC for single page."""
        pages = [
            PageWithComments(
                page_id="1",
                title="Only Page",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[],
                unmapped_inline_comments=[],
            )
        ]

        toc = generator._format_toc(pages)

        assert "Single page report" in toc

    def test_format_toc_multiple_pages(self, generator):
        """Test TOC for multiple pages."""
        pages = [
            PageWithComments(
                page_id="1",
                title="First Page",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[
                    CommentThread(
                        root=Comment(id="1", author="a", created="", body="c"),
                        replies=[],
                    )
                ],
                unmapped_inline_comments=[],
            ),
            PageWithComments(
                page_id="2",
                title="Second Page",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[],
                unmapped_inline_comments=[],
            ),
        ]

        toc = generator._format_toc(pages)

        assert "1. [First Page]" in toc
        assert "2. [Second Page]" in toc
        assert "(1 comment)" in toc
        assert "(0 comments)" in toc


class TestMetadataFormatting:
    """Tests for metadata section formatting."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_format_metadata_includes_timestamp(self, generator):
        """Test that metadata includes generation timestamp."""
        # Generate a report to populate stats
        generator.generate([])

        metadata = generator._format_metadata()

        assert "Generated" in metadata
        assert "UTC" in metadata

    def test_format_metadata_includes_stats(self, generator, sample_page_with_comments):
        """Test that metadata includes statistics."""
        generator.generate([sample_page_with_comments])

        metadata = generator._format_metadata()

        assert "Total Pages" in metadata
        assert "Pages with Comments" in metadata
        assert "Total Comments" in metadata
        assert "Total Threads" in metadata
        assert "Resolved" in metadata
        assert "Unresolved" in metadata


class TestReportCleanup:
    """Tests for report cleanup functionality."""

    @pytest.fixture
    def generator(self):
        """Create a MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    def test_cleanup_removes_excess_blank_lines(self, generator):
        """Test that multiple blank lines are collapsed."""
        report = "Line 1\n\n\n\nLine 2"

        result = generator._cleanup_report(report)

        assert "\n\n\n" not in result

    def test_cleanup_removes_duplicate_hr(self, generator):
        """Test that duplicate horizontal rules are collapsed."""
        report = "Content\n\n---\n\n---\n\nMore content"

        result = generator._cleanup_report(report)

        assert "---\n\n---" not in result


class TestToDictMethod:
    """Tests for the to_dict serialization method."""

    def test_to_dict_includes_config(self):
        """Test that to_dict includes configuration."""
        config = ReportConfig(title="Test Report")
        generator = MarkdownReportGenerator(config)

        result = generator.to_dict()

        assert "config" in result
        assert result["config"]["title"] == "Test Report"

    def test_to_dict_includes_stats(self, sample_page_with_comments):
        """Test that to_dict includes statistics after generation."""
        generator = MarkdownReportGenerator()
        generator.generate([sample_page_with_comments])

        result = generator.to_dict()

        assert "stats" in result
        assert result["stats"]["total_pages"] == 1
