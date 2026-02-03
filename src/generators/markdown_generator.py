"""Markdown report generator for Confluence pages with comments."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from src.models.confluence_data import (
    CommentedParagraph,
    CommentThread,
    PageWithComments,
)


@dataclass
class ReportConfig:
    """Configuration for markdown report generation.

    Attributes:
        title: Report title displayed at the top.
        show_only_commented: If True, only show pages/paragraphs with comments.
        include_resolved: If True, include resolved comment threads.
        include_toc: If True, generate table of contents for multiple pages.
        include_metadata: If True, include generation metadata section.
        max_paragraph_preview: Maximum characters to show for paragraph text.
        date_format: Format string for timestamps.
    """

    title: str = "Confluence Comments Report"
    show_only_commented: bool = False
    include_resolved: bool = True
    include_toc: bool = True
    include_metadata: bool = True
    max_paragraph_preview: int = 200
    date_format: str = "%Y-%m-%d %H:%M:%S UTC"


@dataclass
class ReportStats:
    """Statistics about the generated report.

    Attributes:
        total_pages: Total number of pages in the report.
        pages_with_comments: Number of pages that have comments.
        total_comments: Total number of comments across all pages.
        total_threads: Total number of comment threads.
        resolved_threads: Number of resolved comment threads.
        unresolved_threads: Number of unresolved comment threads.
    """

    total_pages: int = 0
    pages_with_comments: int = 0
    total_comments: int = 0
    total_threads: int = 0
    resolved_threads: int = 0
    unresolved_threads: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary representation."""
        return {
            "total_pages": self.total_pages,
            "pages_with_comments": self.pages_with_comments,
            "total_comments": self.total_comments,
            "total_threads": self.total_threads,
            "resolved_threads": self.resolved_threads,
            "unresolved_threads": self.unresolved_threads,
        }


class MarkdownReportGenerator:
    """Generates markdown reports from Confluence pages with comments.

    Creates formatted markdown reports containing page information,
    commented paragraphs, and comment threads with author attribution.

    Example:
        generator = MarkdownReportGenerator()
        report = generator.generate(pages)
        print(report)

        # With custom configuration
        config = ReportConfig(
            title="Code Review Comments",
            show_only_commented=True,
            include_resolved=False,
        )
        generator = MarkdownReportGenerator(config)
        report = generator.generate(pages)
    """

    # Template file path relative to this module
    TEMPLATE_PATH = Path(__file__).parent / "templates" / "report_template.md"

    # Regex for stripping HTML tags
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

    def __init__(self, config: ReportConfig | None = None) -> None:
        """Initialize the markdown report generator.

        Args:
            config: Optional configuration for report generation.
                   Uses default ReportConfig if not provided.
        """
        self.config = config or ReportConfig()
        self._template: str | None = None
        self._stats = ReportStats()

    @property
    def stats(self) -> ReportStats:
        """Return statistics from the last generated report."""
        return self._stats

    def generate(self, pages: list[PageWithComments]) -> str:
        """Generate a markdown report from a list of pages.

        Args:
            pages: List of PageWithComments objects to include in the report.

        Returns:
            Formatted markdown string containing the full report.
        """
        self._stats = ReportStats()

        # Filter pages if configured
        filtered_pages = self._filter_pages(pages)

        # Calculate statistics
        self._calculate_stats(pages, filtered_pages)

        # Build report sections
        metadata = self._format_metadata() if self.config.include_metadata else ""
        toc = self._format_toc(filtered_pages) if self.config.include_toc else ""
        content = self._format_pages(filtered_pages)

        # Load and fill template
        template = self._load_template()
        report = template.format(
            title=self.config.title,
            metadata=metadata,
            toc=toc,
            content=content,
        )

        # Clean up empty sections
        report = self._cleanup_report(report)

        return report

    def generate_page_section(self, page: PageWithComments) -> str:
        """Generate markdown for a single page.

        Useful for generating partial reports or streaming output.

        Args:
            page: PageWithComments object to format.

        Returns:
            Formatted markdown string for the page section.
        """
        return self._format_page(page)

    def _filter_pages(self, pages: list[PageWithComments]) -> list[PageWithComments]:
        """Filter pages based on configuration.

        Args:
            pages: List of pages to filter.

        Returns:
            Filtered list of pages.
        """
        if self.config.show_only_commented:
            return [p for p in pages if p.total_comments > 0]
        return pages

    def _calculate_stats(
        self, all_pages: list[PageWithComments], filtered_pages: list[PageWithComments]
    ) -> None:
        """Calculate report statistics.

        Args:
            all_pages: Original list of all pages.
            filtered_pages: Filtered list of pages in the report.
        """
        self._stats.total_pages = len(all_pages)
        self._stats.pages_with_comments = sum(
            1 for p in all_pages if p.total_comments > 0
        )

        for page in filtered_pages:
            self._stats.total_comments += page.total_comments
            self._stats.total_threads += page.total_threads

            # Count resolved/unresolved threads
            for thread in page.page_level_comments:
                if thread.is_resolved:
                    self._stats.resolved_threads += 1
                else:
                    self._stats.unresolved_threads += 1

            for cp in page.commented_paragraphs:
                for thread in cp.comment_threads:
                    if thread.is_resolved:
                        self._stats.resolved_threads += 1
                    else:
                        self._stats.unresolved_threads += 1

            for thread in page.unmapped_inline_comments:
                if thread.is_resolved:
                    self._stats.resolved_threads += 1
                else:
                    self._stats.unresolved_threads += 1

    def _load_template(self) -> str:
        """Load the report template from file.

        Returns:
            Template string with placeholders.
        """
        if self._template is None:
            if self.TEMPLATE_PATH.exists():
                self._template = self.TEMPLATE_PATH.read_text(encoding="utf-8")
            else:
                # Fallback inline template
                self._template = (
                    "# {title}\n\n{metadata}\n\n---\n\n"
                    "## Table of Contents\n\n{toc}\n\n---\n\n"
                    "{content}\n\n---\n\n"
                    "*Generated by Confluence Comment Reporter*\n"
                )
        return self._template

    def _format_metadata(self) -> str:
        """Format the metadata section.

        Returns:
            Formatted metadata markdown.
        """
        now = datetime.now(timezone.utc)
        timestamp = now.strftime(self.config.date_format)

        lines = [
            "**Report Metadata**",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Generated | {timestamp} |",
            f"| Total Pages | {self._stats.total_pages} |",
            f"| Pages with Comments | {self._stats.pages_with_comments} |",
            f"| Total Comments | {self._stats.total_comments} |",
            f"| Total Threads | {self._stats.total_threads} |",
            f"| Resolved | {self._stats.resolved_threads} |",
            f"| Unresolved | {self._stats.unresolved_threads} |",
        ]

        return "\n".join(lines)

    def _format_toc(self, pages: list[PageWithComments]) -> str:
        """Format the table of contents.

        Args:
            pages: List of pages to include in TOC.

        Returns:
            Formatted TOC markdown.
        """
        if len(pages) <= 1:
            return "*Single page report - no table of contents needed*"

        lines = []
        for i, page in enumerate(pages, 1):
            anchor = self._make_anchor(page.title)
            comment_count = page.total_comments
            comment_info = f" ({comment_count} comment{'s' if comment_count != 1 else ''})"
            lines.append(f"{i}. [{page.title}](#{anchor}){comment_info}")

        return "\n".join(lines)

    def _format_pages(self, pages: list[PageWithComments]) -> str:
        """Format all pages.

        Args:
            pages: List of pages to format.

        Returns:
            Formatted pages markdown.
        """
        if not pages:
            return "*No pages to display*"

        sections = [self._format_page(page) for page in pages]
        return "\n\n---\n\n".join(sections)

    def _format_page(self, page: PageWithComments) -> str:
        """Format a single page section.

        Args:
            page: PageWithComments to format.

        Returns:
            Formatted page markdown.
        """
        lines = []

        # Page header
        lines.append(f"## {page.title}")
        lines.append("")

        # Page metadata
        if page.url:
            lines.append(f"**Link:** [{page.url}]({page.url})")
        lines.append(f"**Space:** {page.space_key}")
        lines.append(f"**Page ID:** {page.page_id}")
        lines.append(
            f"**Comments:** {page.total_comments} "
            f"({page.total_threads} thread{'s' if page.total_threads != 1 else ''})"
        )
        lines.append("")

        # Page-level comments
        if page.page_level_comments:
            lines.append("### Page-Level Comments")
            lines.append("")
            for thread in page.page_level_comments:
                if not self.config.include_resolved and thread.is_resolved:
                    continue
                lines.append(self._format_thread(thread))
            lines.append("")

        # Commented paragraphs
        paragraphs_with_comments = page.paragraphs_with_comments
        if paragraphs_with_comments:
            lines.append("### Inline Comments")
            lines.append("")
            for cp in paragraphs_with_comments:
                formatted = self._format_commented_paragraph(cp, page_url=page.url)
                if formatted:
                    lines.append(formatted)
            lines.append("")

        # Unmapped inline comments
        if page.unmapped_inline_comments:
            lines.append("### Unmapped Comments")
            lines.append("")
            lines.append(
                "*These comments could not be mapped to specific paragraphs:*"
            )
            lines.append("")
            for thread in page.unmapped_inline_comments:
                if not self.config.include_resolved and thread.is_resolved:
                    continue
                lines.append(self._format_thread(thread, page_url=page.url))
            lines.append("")

        # Handle pages with no comments
        if page.total_comments == 0:
            lines.append("*No comments on this page*")
            lines.append("")

        return "\n".join(lines)

    def _format_commented_paragraph(
        self, cp: CommentedParagraph, page_url: str = ""
    ) -> str:
        """Format a commented paragraph section.

        Args:
            cp: CommentedParagraph to format.
            page_url: URL of the page for creating text fragment links.

        Returns:
            Formatted paragraph markdown, or empty string if filtered.
        """
        # Filter threads if needed
        threads = cp.comment_threads
        if not self.config.include_resolved:
            threads = [t for t in threads if not t.is_resolved]

        if not threads:
            return ""

        lines = []

        # Format each comment with its highlighted context
        for thread in threads:
            # Paragraph text with highlighted selection and context
            paragraph_text = cp.text
            highlighted_text = self._highlight_with_context(
                paragraph_text, [thread], page_url=page_url
            )
            lines.append(f"> {highlighted_text}")
            lines.append(self._format_thread_with_selection(thread))
            lines.append("")

        return "\n".join(lines).rstrip()

    def _highlight_selections(
        self, paragraph_text: str, threads: list[CommentThread]
    ) -> str:
        """Highlight all text selections within the paragraph.

        Uses HTML <mark> tags to highlight selected text.

        Args:
            paragraph_text: The full paragraph text.
            threads: List of comment threads with text selections.

        Returns:
            Paragraph text with highlighted selections.
        """
        # Collect all selections to highlight
        selections: list[str] = []
        for thread in threads:
            if thread.root.text_selection:
                selections.append(thread.root.text_selection)

        if not selections:
            return self._truncate_text(paragraph_text, self.config.max_paragraph_preview)

        # Sort by length (longest first) to handle overlapping matches correctly
        selections.sort(key=len, reverse=True)

        # Replace each selection with highlighted version
        highlighted = paragraph_text
        for selection in selections:
            if selection in highlighted:
                highlighted = highlighted.replace(
                    selection, f"<mark>{selection}</mark>", 1
                )

        return self._truncate_text(highlighted, self.config.max_paragraph_preview + 100)

    def _format_thread_with_selection(self, thread: CommentThread) -> str:
        """Format a comment thread in compact format.

        Args:
            thread: CommentThread to format.

        Returns:
            Formatted thread markdown (compact, single line for root comment).
        """
        lines = []

        # Status indicator
        status_emoji = "[RESOLVED]" if thread.is_resolved else "[OPEN]"

        # Root comment - all on one line
        root = thread.root
        body = self._clean_comment_body(root.body)
        timestamp = self._format_timestamp(root.created)

        lines.append(f"**{status_emoji}** *{root.author}* · {timestamp}: {body}")

        # Replies (indented)
        for reply in thread.replies:
            reply_body = self._clean_comment_body(reply.body)
            reply_timestamp = self._format_timestamp(reply.created)
            lines.append(f"  ↳ *{reply.author}* · {reply_timestamp}: {reply_body}")

        return "\n".join(lines)

    def _format_thread(self, thread: CommentThread, page_url: str = "") -> str:
        """Format a comment thread in compact format.

        Used for page-level and unmapped comments.

        Args:
            thread: CommentThread to format.
            page_url: Optional page URL for creating text fragment links.

        Returns:
            Formatted thread markdown.
        """
        lines = []

        # Status indicator
        status_emoji = "[RESOLVED]" if thread.is_resolved else "[OPEN]"

        # Root comment
        root = thread.root
        body = self._clean_comment_body(root.body)
        timestamp = self._format_timestamp(root.created)

        # Show the highlighted text if available (for unmapped comments)
        if root.text_selection:
            if page_url:
                fragment_url = self._make_text_fragment_url(page_url, root.text_selection)
                highlight = f"[<mark>{root.text_selection}</mark>]({fragment_url})"
            else:
                highlight = f"<mark>{root.text_selection}</mark>"
            lines.append(f"> ...{highlight}...")
            lines.append(f"**{status_emoji}** *{root.author}* · {timestamp}: {body}")
        else:
            lines.append(f"**{status_emoji}** *{root.author}* · {timestamp}: {body}")

        # Replies (indented)
        for reply in thread.replies:
            reply_body = self._clean_comment_body(reply.body)
            reply_timestamp = self._format_timestamp(reply.created)
            lines.append(f"  ↳ *{reply.author}* · {reply_timestamp}: {reply_body}")

        return "\n".join(lines)

    def _clean_comment_body(self, body: str) -> str:
        """Clean HTML from comment body and format for markdown.

        Args:
            body: Raw comment body potentially containing HTML.

        Returns:
            Cleaned text suitable for markdown.
        """
        # Strip HTML tags first
        text = self.HTML_TAG_PATTERN.sub("", body)

        # Then unescape HTML entities (so &lt; becomes < after tags are removed)
        text = html.unescape(text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length with ellipsis.

        Args:
            text: Text to truncate.
            max_length: Maximum length before truncation.

        Returns:
            Truncated text with ellipsis if needed.
        """
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rstrip() + "..."

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """Format ISO timestamp to human-readable format.

        Args:
            iso_timestamp: ISO format timestamp (e.g., "2026-02-03T16:32:09.675Z")

        Returns:
            Human-readable format (e.g., "Feb 3, 2026")
        """
        if not iso_timestamp:
            return ""
        try:
            # Parse ISO format
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            return dt.strftime("%b %-d, %Y")
        except (ValueError, AttributeError):
            # Return original if parsing fails
            return iso_timestamp

    def _highlight_with_context(
        self,
        paragraph_text: str,
        threads: list[CommentThread],
        context_chars: int = 40,
        page_url: str = "",
    ) -> str:
        """Highlight text selections with surrounding context.

        Shows ellipsis before/after the highlighted portion. If page_url is
        provided, the highlighted text becomes a link using text fragments.

        Args:
            paragraph_text: The full paragraph text.
            threads: List of comment threads with text selections.
            context_chars: Number of characters to show before/after highlight.
            page_url: Optional page URL for creating text fragment links.

        Returns:
            Truncated paragraph with highlighted selections and ellipsis.
        """
        # Collect all selections to highlight
        selections: list[str] = []
        for thread in threads:
            if thread.root.text_selection:
                selections.append(thread.root.text_selection)

        if not selections:
            return self._truncate_text(paragraph_text, self.config.max_paragraph_preview)

        # Find the first selection's position
        first_selection = selections[0]
        pos = paragraph_text.find(first_selection)

        if pos == -1:
            # Selection not found, fall back to simple truncation
            return self._truncate_text(paragraph_text, self.config.max_paragraph_preview)

        # Calculate start and end positions with context
        start = max(0, pos - context_chars)
        end = min(len(paragraph_text), pos + len(first_selection) + context_chars)

        # Extract the portion with context
        portion = paragraph_text[start:end]

        # Add ellipsis
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(paragraph_text) else ""

        # Highlight all selections within this portion
        for selection in selections:
            if selection in portion:
                # Create text fragment link if URL is available
                if page_url:
                    fragment_url = self._make_text_fragment_url(page_url, selection)
                    highlighted = f"[<mark>{selection}</mark>]({fragment_url})"
                else:
                    highlighted = f"<mark>{selection}</mark>"
                portion = portion.replace(selection, highlighted, 1)

        return f"{prefix}{portion}{suffix}"

    def _make_text_fragment_url(self, page_url: str, text: str) -> str:
        """Create a URL with text fragment for direct navigation.

        Args:
            page_url: Base page URL.
            text: Text to highlight via fragment.

        Returns:
            URL with #:~:text= fragment for text highlighting.
        """
        # URL-encode the text for the fragment
        encoded_text = quote(text, safe="")
        return f"{page_url}#:~:text={encoded_text}"

    def _make_anchor(self, title: str) -> str:
        """Create a markdown anchor from a title.

        Args:
            title: Page or section title.

        Returns:
            URL-safe anchor string.
        """
        # Convert to lowercase
        anchor = title.lower()

        # Replace spaces with hyphens
        anchor = anchor.replace(" ", "-")

        # Remove non-alphanumeric characters except hyphens
        anchor = re.sub(r"[^a-z0-9-]", "", anchor)

        # Collapse multiple hyphens
        anchor = re.sub(r"-+", "-", anchor)

        return anchor.strip("-")

    def _cleanup_report(self, report: str) -> str:
        """Clean up the final report.

        Removes empty sections and excessive whitespace.

        Args:
            report: Raw report string.

        Returns:
            Cleaned report string.
        """
        # Remove empty TOC section if no content
        report = re.sub(
            r"## Table of Contents\n\n\*Single page.*?\*\n\n---\n\n",
            "",
            report,
        )

        # Remove multiple consecutive blank lines
        report = re.sub(r"\n{3,}", "\n\n", report)

        # Remove multiple consecutive horizontal rules
        report = re.sub(r"(---\n\n){2,}", "---\n\n", report)

        return report.strip() + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Return generator state as dictionary.

        Returns:
            Dictionary with configuration and last report stats.
        """
        return {
            "config": {
                "title": self.config.title,
                "show_only_commented": self.config.show_only_commented,
                "include_resolved": self.config.include_resolved,
                "include_toc": self.config.include_toc,
                "include_metadata": self.config.include_metadata,
                "max_paragraph_preview": self.config.max_paragraph_preview,
                "date_format": self.config.date_format,
            },
            "stats": self._stats.to_dict(),
        }
