"""Integration tests for the Claude Agent Confluence pipeline."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from src.config import AgentConfig, ConfluenceConfig, load_config
from src.confluence.client import ConfluenceClient, InlineComment, Page, PageComment
from src.generators.markdown_generator import MarkdownReportGenerator, ReportConfig
from src.main import (
    fetch_pages_with_comments,
    generate_report,
    main,
    parse_args,
    run_pipeline,
    validate_args,
)
from src.models.confluence_data import PageWithComments
from src.processors.comment_mapper import CommentMapper


class TestEndToEndPipeline:
    """End-to-end integration tests for the full pipeline."""

    @pytest.fixture
    def mock_confluence_client(self):
        """Create a mocked ConfluenceClient."""
        client = MagicMock(spec=ConfluenceClient)

        # Mock page
        client.get_page_by_id.return_value = Page(
            id="123456",
            title="Integration Test Page",
            space_key="TEST",
            version=1,
            url="https://test.atlassian.net/wiki/spaces/TEST/pages/123456",
        )

        # Mock content with inline marker
        client.get_page_content.return_value = """
<p>This is the introduction to the document.</p>
<p>This paragraph has <ac:inline-comment-marker ac:ref="marker-1">important content</ac:inline-comment-marker> that needs review.</p>
<h2>Section Title</h2>
<p>More detailed information in this section.</p>
        """

        # Mock page comments
        client.get_page_comments.return_value = [
            PageComment(
                id="page-comment-1",
                author="reviewer@example.com",
                created="2024-01-15T10:00:00Z",
                body="Overall this document looks good.",
                parent_id=None,
            ),
        ]

        # Mock inline comments
        client.get_inline_comments.return_value = [
            InlineComment(
                id="inline-1",
                author="editor@example.com",
                created="2024-01-15T11:00:00Z",
                body="Please clarify this section.",
                text_selection="important content",
                resolved=False,
                replies=[
                    InlineComment(
                        id="inline-1-reply",
                        author="author@example.com",
                        created="2024-01-15T12:00:00Z",
                        body="I've added more details.",
                        text_selection=None,
                        resolved=False,
                        replies=[],
                    )
                ],
            ),
        ]

        return client

    def test_full_pipeline_page_by_id(self, mock_confluence_client):
        """Test complete pipeline fetching page by ID."""
        # Execute pipeline
        pages = fetch_pages_with_comments(
            client=mock_confluence_client,
            page_id="123456",
        )

        # Verify results
        assert len(pages) == 1
        page = pages[0]

        assert page.page_id == "123456"
        assert page.title == "Integration Test Page"
        assert page.space_key == "TEST"

        # Should have page-level comment
        assert len(page.page_level_comments) == 1
        assert page.page_level_comments[0].root.author == "reviewer@example.com"

        # Should have mapped inline comment
        assert page.total_comments > 1

    def test_full_pipeline_generates_report(self, mock_confluence_client):
        """Test that pipeline generates valid markdown report."""
        pages = fetch_pages_with_comments(
            client=mock_confluence_client,
            page_id="123456",
        )

        report = generate_report(pages)

        # Verify report structure
        assert "# Confluence Comments Report" in report
        assert "Integration Test Page" in report
        assert "reviewer@example.com" in report
        assert "editor@example.com" in report
        assert "Page-Level Comments" in report

    def test_full_pipeline_writes_to_file(self, mock_confluence_client):
        """Test that pipeline can write report to file."""
        pages = fetch_pages_with_comments(
            client=mock_confluence_client,
            page_id="123456",
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"

            report = generate_report(pages, output_path=output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "Confluence Comments Report" in content
            assert content == report


class TestFetchPagesWithComments:
    """Tests for the fetch_pages_with_comments function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked ConfluenceClient."""
        return MagicMock(spec=ConfluenceClient)

    def test_fetch_by_page_id(self, mock_client):
        """Test fetching by specific page ID."""
        mock_client.get_page_by_id.return_value = Page(
            id="111", title="Page", space_key="TEST", version=1, url=""
        )
        mock_client.get_page_content.return_value = "<p>Content</p>"
        mock_client.get_page_comments.return_value = []
        mock_client.get_inline_comments.return_value = []

        pages = fetch_pages_with_comments(client=mock_client, page_id="111")

        assert len(pages) == 1
        mock_client.get_page_by_id.assert_called_once_with("111")

    def test_fetch_by_page_title(self, mock_client):
        """Test fetching by page title."""
        mock_client.get_pages_by_title.return_value = [
            Page(id="222", title="My Page", space_key="TEST", version=1, url="")
        ]
        mock_client.get_page_content.return_value = "<p>Content</p>"
        mock_client.get_page_comments.return_value = []
        mock_client.get_inline_comments.return_value = []

        pages = fetch_pages_with_comments(
            client=mock_client, page_title="My Page", space="TEST"
        )

        assert len(pages) == 1
        mock_client.get_pages_by_title.assert_called_once_with("My Page", space_key="TEST")

    def test_fetch_by_label(self, mock_client):
        """Test fetching by label."""
        mock_client.get_pages_by_label.return_value = [
            Page(id="333", title="Labeled Page", space_key="TEST", version=1, url=""),
            Page(id="444", title="Another Labeled", space_key="TEST", version=1, url=""),
        ]
        mock_client.get_page_content.return_value = "<p>Content</p>"
        mock_client.get_page_comments.return_value = []
        mock_client.get_inline_comments.return_value = []

        pages = fetch_pages_with_comments(
            client=mock_client, label="review", space="TEST"
        )

        assert len(pages) == 2
        mock_client.get_pages_by_label.assert_called_once_with("review", space_key="TEST")

    def test_fetch_all_with_comments(self, mock_client):
        """Test fetching all pages with comments in space."""
        mock_client.get_pages_with_comments.return_value = [
            Page(id="555", title="Commented Page", space_key="TEST", version=1, url="")
        ]
        mock_client.get_page_content.return_value = "<p>Content</p>"
        mock_client.get_page_comments.return_value = []
        mock_client.get_inline_comments.return_value = []

        pages = fetch_pages_with_comments(
            client=mock_client, all_with_comments=True, space="TEST"
        )

        assert len(pages) == 1
        mock_client.get_pages_with_comments.assert_called_once_with(space_key="TEST")

    def test_fetch_returns_empty_without_filters(self, mock_client):
        """Test that fetch returns empty list without filters."""
        pages = fetch_pages_with_comments(client=mock_client)

        assert pages == []


class TestGenerateReport:
    """Tests for the generate_report function."""

    def test_generate_report_basic(self, sample_page_with_comments):
        """Test basic report generation."""
        report = generate_report([sample_page_with_comments])

        assert isinstance(report, str)
        assert len(report) > 0
        assert "Test Page" in report

    def test_generate_report_with_show_only_commented(self, sample_page_with_comments):
        """Test report with show_only_commented option."""
        empty_page = PageWithComments(
            page_id="2",
            title="Empty",
            space_key="TEST",
            content="",
            paragraphs=[],
            commented_paragraphs=[],
            page_level_comments=[],
            unmapped_inline_comments=[],
        )

        report = generate_report(
            [sample_page_with_comments, empty_page],
            show_only_commented=True,
        )

        assert "Test Page" in report
        # Empty page should be filtered out

    def test_generate_report_with_output_file(self, sample_page_with_comments):
        """Test report generation to file."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "report.md"

            generate_report([sample_page_with_comments], output_path=output_path)

            assert output_path.exists()


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_parse_args_page_id(self):
        """Test parsing --page-id argument."""
        args = parse_args(["--page-id", "123456"])

        assert args.page_id == "123456"
        assert args.space is None

    def test_parse_args_space_and_label(self):
        """Test parsing --space and --label arguments."""
        args = parse_args(["--space", "TEST", "--label", "review"])

        assert args.space == "TEST"
        assert args.label == "review"

    def test_parse_args_all_with_comments(self):
        """Test parsing --all-with-comments argument."""
        args = parse_args(["--space", "TEST", "--all-with-comments"])

        assert args.all_with_comments is True
        assert args.space == "TEST"

    def test_parse_args_output(self):
        """Test parsing --output argument."""
        args = parse_args(["--page-id", "123", "--output", "report.md"])

        assert args.output == "report.md"

    def test_parse_args_short_options(self):
        """Test parsing short option flags."""
        args = parse_args(["-p", "123", "-s", "TEST", "-o", "out.md"])

        assert args.page_id == "123"
        assert args.space == "TEST"
        assert args.output == "out.md"


class TestCLIArgumentValidation:
    """Tests for CLI argument validation."""

    def test_validate_args_requires_filter(self):
        """Test that at least one filter is required."""
        args = argparse.Namespace(
            page_id=None,
            page_title=None,
            label=None,
            all_with_comments=False,
            space=None,
        )

        with pytest.raises(ValueError) as exc_info:
            validate_args(args)

        assert "filter option is required" in str(exc_info.value)

    def test_validate_args_all_with_comments_requires_space(self):
        """Test that --all-with-comments requires --space."""
        args = argparse.Namespace(
            page_id=None,
            page_title=None,
            label=None,
            all_with_comments=True,
            space=None,
        )

        with pytest.raises(ValueError) as exc_info:
            validate_args(args)

        assert "--all-with-comments requires --space" in str(exc_info.value)

    def test_validate_args_label_requires_space(self):
        """Test that --label requires --space."""
        args = argparse.Namespace(
            page_id=None,
            page_title=None,
            label="review",
            all_with_comments=False,
            space=None,
        )

        with pytest.raises(ValueError) as exc_info:
            validate_args(args)

        assert "--label requires --space" in str(exc_info.value)

    def test_validate_args_page_id_standalone(self):
        """Test that --page-id works without --space."""
        args = argparse.Namespace(
            page_id="123456",
            page_title=None,
            label=None,
            all_with_comments=False,
            space=None,
        )

        # Should not raise
        validate_args(args)


class TestMainFunction:
    """Tests for the main CLI entry point."""

    def test_main_returns_error_without_filter(self):
        """Test main returns error code without filter."""
        result = main([])

        assert result == 1

    @patch("src.main.load_config")
    def test_main_returns_error_invalid_args(self, mock_config):
        """Test main returns error for invalid argument combinations."""
        # Mock config with no default space
        mock_config.return_value = MagicMock(
            confluence=MagicMock(default_space=None),
        )
        result = main(["--label", "test"])  # Missing --space and no default

        assert result == 1

    @patch("src.main.load_config")
    @patch("src.main.run_pipeline")
    def test_main_success(self, mock_pipeline, mock_config):
        """Test main returns success on valid execution."""
        mock_config.return_value = MagicMock(
            confluence=MagicMock(),
            api_key="key",
            base_url=None,
            model="claude-sonnet-4-20250514",
            skills_directory="skills",
            allowed_tools=["Read", "Write"],
            max_tokens=4096,
        )
        mock_pipeline.return_value = "# Report"

        result = main(["--page-id", "123456"])

        assert result == 0
        mock_pipeline.assert_called_once()


class TestRunPipeline:
    """Tests for the run_pipeline function."""

    def test_run_pipeline_requires_confluence_config(self):
        """Test that pipeline requires Confluence configuration."""
        config = MagicMock()
        config.confluence = None

        with pytest.raises(ValueError) as exc_info:
            run_pipeline(config, page_id="123")

        assert "Confluence configuration is required" in str(exc_info.value)


class TestCommentMapperIntegration:
    """Integration tests for CommentMapper with realistic data."""

    def test_mapper_handles_complex_content(self):
        """Test mapper with complex Confluence storage format."""
        mapper = CommentMapper()

        content = """
<ac:layout>
<ac:layout-section ac:type="single">
<ac:layout-cell>
<p>Introduction paragraph with some context.</p>
<p>Second paragraph with <ac:inline-comment-marker ac:ref="abc123">marked content for review</ac:inline-comment-marker>.</p>
<h2>Requirements Section</h2>
<ul>
<li>First requirement item</li>
<li>Second requirement with <strong>emphasis</strong></li>
</ul>
<table>
<tr><th>Feature</th><th>Status</th></tr>
<tr><td>Feature A</td><td>Complete</td></tr>
</table>
</ac:layout-cell>
</ac:layout-section>
</ac:layout>
        """

        page_comments = [
            {"id": "1", "author": "user@test.com", "created": "2024-01-01", "body": "LGTM"},
        ]

        inline_comments = [
            {
                "id": "2",
                "author": "reviewer@test.com",
                "created": "2024-01-02",
                "body": "Need more detail here",
                "text_selection": "marked content for review",
            },
        ]

        result = mapper.map_page_comments(
            page_id="test",
            title="Test Page",
            space_key="TEST",
            content=content,
            page_comments=page_comments,
            inline_comments=inline_comments,
        )

        # Should extract multiple paragraphs
        assert len(result.paragraphs) > 3

        # Should have page-level comment
        assert len(result.page_level_comments) == 1

        # Should map inline comment
        paragraphs_with_comments = result.paragraphs_with_comments
        assert len(paragraphs_with_comments) > 0


class TestReportGeneratorIntegration:
    """Integration tests for MarkdownReportGenerator."""

    def test_generator_produces_valid_markdown(self, sample_page_with_comments):
        """Test that generated report is valid markdown."""
        generator = MarkdownReportGenerator()

        report = generator.generate([sample_page_with_comments])

        # Check markdown structure
        assert report.startswith("#")  # Starts with header
        assert "##" in report  # Has subheadings
        assert "---" in report  # Has horizontal rules
        assert report.endswith("\n")  # Properly terminated

    def test_generator_with_multiple_pages_has_toc(self):
        """Test that multi-page report has table of contents."""
        pages = [
            PageWithComments(
                page_id=str(i),
                title=f"Page {i}",
                space_key="TEST",
                content="",
                paragraphs=[],
                commented_paragraphs=[],
                page_level_comments=[],
                unmapped_inline_comments=[],
            )
            for i in range(3)
        ]

        generator = MarkdownReportGenerator()
        report = generator.generate(pages)

        assert "Table of Contents" in report
        assert "[Page 0]" in report
        assert "[Page 1]" in report
        assert "[Page 2]" in report


class TestDataFlowIntegration:
    """Tests verifying data flows correctly through the pipeline."""

    def test_comment_author_preserved(self):
        """Test that comment authors are preserved through pipeline."""
        mapper = CommentMapper()

        page_comments = [
            {
                "id": "1",
                "author": "specific.author@company.com",
                "created": "2024-01-01",
                "body": "Comment text",
            }
        ]

        result = mapper.map_page_comments(
            page_id="1",
            title="Test",
            space_key="T",
            content="<p>Text</p>",
            page_comments=page_comments,
            inline_comments=[],
        )

        generator = MarkdownReportGenerator()
        report = generator.generate([result])

        assert "specific.author@company.com" in report

    def test_comment_threading_preserved(self):
        """Test that comment threading is preserved through pipeline."""
        mapper = CommentMapper()

        page_comments = [
            {
                "id": "1",
                "author": "author1@test.com",
                "created": "2024-01-01T10:00:00Z",
                "body": "Original comment",
                "parent_id": None,
            },
            {
                "id": "2",
                "author": "author2@test.com",
                "created": "2024-01-01T11:00:00Z",
                "body": "Reply to original",
                "parent_id": "1",
            },
        ]

        result = mapper.map_page_comments(
            page_id="1",
            title="Test",
            space_key="T",
            content="<p>Content</p>",
            page_comments=page_comments,
            inline_comments=[],
        )

        # Verify threading
        assert len(result.page_level_comments) == 1
        thread = result.page_level_comments[0]
        assert thread.root.body == "Original comment"
        assert len(thread.replies) == 1
        assert thread.replies[0].body == "Reply to original"

    def test_resolved_status_preserved(self):
        """Test that resolved status flows through pipeline."""
        mapper = CommentMapper()

        inline_comments = [
            {
                "id": "1",
                "author": "user@test.com",
                "created": "2024-01-01",
                "body": "Resolved comment",
                "text_selection": "some text",
                "resolved": True,
            }
        ]

        result = mapper.map_page_comments(
            page_id="1",
            title="Test",
            space_key="T",
            content="<p>some text here</p>",
            page_comments=[],
            inline_comments=inline_comments,
        )

        # Find the mapped comment
        has_resolved = False
        for cp in result.commented_paragraphs:
            for thread in cp.comment_threads:
                if thread.is_resolved:
                    has_resolved = True
                    break

        assert has_resolved or len(result.unmapped_inline_comments) > 0
