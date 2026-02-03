"""Comment mapper for Confluence pages.

Maps inline comments to specific paragraphs based on text selection
or location markers in Confluence storage format content.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from src.models.confluence_data import (
    Comment,
    CommentedParagraph,
    CommentThread,
    PageWithComments,
    Paragraph,
)


@dataclass
class InlineCommentLocation:
    """Location data for an inline comment from Confluence API."""

    comment_id: str
    text_selection: str | None = None
    marker_ref: str | None = None
    original_selection: str | None = None


class CommentMapper:
    """Maps inline comments to paragraphs in Confluence pages.

    Parses Confluence storage format (XML/HTML) to extract paragraphs
    and maps inline comments to their corresponding paragraph locations.
    """

    # Elements that typically contain paragraph-like content
    PARAGRAPH_TAGS = {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}

    # Inline comment marker pattern in Confluence storage format
    MARKER_PATTERN = re.compile(
        r'<ac:inline-comment-marker\s+ac:ref="([^"]+)"[^>]*>(.*?)</ac:inline-comment-marker>',
        re.DOTALL,
    )

    def __init__(self, normalize_whitespace: bool = True):
        """Initialize the comment mapper.

        Args:
            normalize_whitespace: Whether to normalize whitespace in extracted text
        """
        self.normalize_whitespace = normalize_whitespace

    def extract_paragraphs(self, content: str) -> list[Paragraph]:
        """Extract paragraphs from Confluence storage format content.

        Parses the HTML/XML content and extracts text from paragraph-like
        elements, preserving order and position information.

        Args:
            content: Confluence storage format HTML/XML content

        Returns:
            List of Paragraph objects with extracted text
        """
        paragraphs: list[Paragraph] = []

        # First, try to extract with regex for more reliable results
        paragraphs = self._extract_paragraphs_regex(content)

        # If regex extraction failed, try XML parsing
        if not paragraphs:
            paragraphs = self._extract_paragraphs_xml(content)

        return paragraphs

    def _extract_paragraphs_regex(self, content: str) -> list[Paragraph]:
        """Extract paragraphs using regex patterns.

        More reliable for malformed HTML/XML that's common in
        Confluence storage format.
        """
        paragraphs: list[Paragraph] = []

        # Match paragraph-like elements
        pattern = re.compile(
            r"<(p|li|h[1-6]|td|th)[^>]*>(.*?)</\1>",
            re.DOTALL | re.IGNORECASE,
        )

        for match in pattern.finditer(content):
            full_html = match.group(0)
            inner_html = match.group(2)

            # Strip HTML tags to get plain text
            text = self._strip_html_tags(inner_html)
            text = html.unescape(text)

            if self.normalize_whitespace:
                text = self._normalize_whitespace(text)

            if text.strip():
                paragraphs.append(
                    Paragraph(
                        index=len(paragraphs),
                        text=text.strip(),
                        html=full_html,
                        start_offset=match.start(),
                        end_offset=match.end(),
                    )
                )

        return paragraphs

    def _extract_paragraphs_xml(self, content: str) -> list[Paragraph]:
        """Extract paragraphs using XML parsing.

        Falls back to this method when regex extraction produces no results.
        """
        paragraphs: list[Paragraph] = []

        # Wrap content in a root element for parsing
        wrapped = f"<root>{content}</root>"

        try:
            # Register Confluence namespaces to avoid parsing errors
            namespaces = {
                "ac": "http://atlassian.com/content",
                "ri": "http://atlassian.com/resource/identifier",
            }
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)

            root = ET.fromstring(wrapped)
            self._extract_from_element(root, paragraphs)
        except ET.ParseError:
            # If XML parsing fails, return empty list (regex should have worked)
            pass

        return paragraphs

    def _extract_from_element(
        self, element: ET.Element, paragraphs: list[Paragraph]
    ) -> None:
        """Recursively extract paragraphs from an XML element."""
        # Get the tag name without namespace
        tag = element.tag.split("}")[-1].lower() if "}" in element.tag else element.tag.lower()

        if tag in self.PARAGRAPH_TAGS:
            text = self._get_element_text(element)
            if text.strip():
                paragraphs.append(
                    Paragraph(
                        index=len(paragraphs),
                        text=text.strip(),
                        html=ET.tostring(element, encoding="unicode"),
                    )
                )
        else:
            # Recurse into children
            for child in element:
                self._extract_from_element(child, paragraphs)

    def _get_element_text(self, element: ET.Element) -> str:
        """Get all text content from an element, including nested elements."""
        texts = []
        if element.text:
            texts.append(element.text)

        for child in element:
            texts.append(self._get_element_text(child))
            if child.tail:
                texts.append(child.tail)

        text = "".join(texts)
        if self.normalize_whitespace:
            text = self._normalize_whitespace(text)
        return text

    def _strip_html_tags(self, content: str) -> str:
        """Remove HTML tags from content."""
        # Remove inline comment markers but keep their content
        content = self.MARKER_PATTERN.sub(r"\2", content)
        # Remove all remaining HTML tags
        return re.sub(r"<[^>]+>", "", content)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        return re.sub(r"\s+", " ", text).strip()

    def extract_inline_markers(self, content: str) -> dict[str, list[int]]:
        """Extract inline comment marker references and their paragraph locations.

        Finds ac:inline-comment-marker elements in the content and maps
        their ref IDs to paragraph indices.

        Args:
            content: Confluence storage format content

        Returns:
            Dict mapping marker ref IDs to list of paragraph indices
        """
        markers: dict[str, list[int]] = {}
        paragraphs = self.extract_paragraphs(content)

        for match in self.MARKER_PATTERN.finditer(content):
            marker_ref = match.group(1)
            marker_text = self._strip_html_tags(match.group(2))
            marker_start = match.start()

            # Find which paragraph contains this marker
            for para in paragraphs:
                if para.start_offset <= marker_start < para.end_offset:
                    if marker_ref not in markers:
                        markers[marker_ref] = []
                    if para.index not in markers[marker_ref]:
                        markers[marker_ref].append(para.index)
                    break
            else:
                # If marker not in any paragraph, try text matching
                para_idx = self._find_paragraph_by_text(marker_text, paragraphs)
                if para_idx is not None:
                    if marker_ref not in markers:
                        markers[marker_ref] = []
                    if para_idx not in markers[marker_ref]:
                        markers[marker_ref].append(para_idx)

        return markers

    def _find_paragraph_by_text(
        self, text: str, paragraphs: list[Paragraph]
    ) -> int | None:
        """Find the paragraph index containing the given text.

        Uses case-insensitive substring matching with whitespace normalization.
        """
        if not text:
            return None

        normalized_text = self._normalize_whitespace(text.lower())
        if not normalized_text:
            return None

        for para in paragraphs:
            normalized_para = self._normalize_whitespace(para.text.lower())
            if normalized_text in normalized_para:
                return para.index

        return None

    def map_comment_to_paragraph(
        self,
        location: InlineCommentLocation,
        paragraphs: list[Paragraph],
        marker_map: dict[str, list[int]] | None = None,
    ) -> int | None:
        """Map an inline comment to its paragraph index.

        Uses multiple strategies in order of preference:
        1. Marker reference (if marker_map provided)
        2. Text selection matching
        3. Original selection matching

        Args:
            location: The inline comment location data
            paragraphs: List of paragraphs from the page
            marker_map: Optional pre-computed marker ref to paragraph map

        Returns:
            Paragraph index or None if no match found
        """
        # Strategy 1: Use marker reference
        if marker_map and location.marker_ref:
            indices = marker_map.get(location.marker_ref, [])
            if indices:
                return indices[0]

        # Strategy 2: Match text selection
        if location.text_selection:
            idx = self._find_paragraph_by_text(location.text_selection, paragraphs)
            if idx is not None:
                return idx

        # Strategy 3: Match original selection
        if location.original_selection:
            idx = self._find_paragraph_by_text(location.original_selection, paragraphs)
            if idx is not None:
                return idx

        return None

    def build_comment_threads(
        self, comments: list[dict[str, Any]]
    ) -> list[CommentThread]:
        """Build comment threads from a flat list of comment data.

        Groups comments into threads based on parent_id relationships,
        handling nested replies.

        Args:
            comments: List of comment dictionaries from API

        Returns:
            List of CommentThread objects
        """
        # Parse comments into Comment objects
        parsed: dict[str, Comment] = {}
        for data in comments:
            comment = Comment(
                id=str(data.get("id", "")),
                author=data.get("author", "unknown"),
                created=data.get("created", ""),
                body=data.get("body", ""),
                parent_id=data.get("parent_id"),
                text_selection=data.get("text_selection"),
                resolved=data.get("resolved", False),
            )
            parsed[comment.id] = comment

        # Build threads
        threads: list[CommentThread] = []
        processed: set[str] = set()

        for comment in parsed.values():
            if comment.id in processed:
                continue

            # Find root of this comment's thread
            root = comment
            while root.parent_id and root.parent_id in parsed:
                root = parsed[root.parent_id]

            if root.id in processed:
                continue

            # Collect all replies for this root
            replies = self._collect_replies(root.id, parsed, processed)
            processed.add(root.id)

            threads.append(CommentThread(root=root, replies=replies))

        return threads

    def _collect_replies(
        self,
        parent_id: str,
        all_comments: dict[str, Comment],
        processed: set[str],
    ) -> list[Comment]:
        """Recursively collect replies for a parent comment."""
        replies: list[Comment] = []

        for comment in all_comments.values():
            if comment.parent_id == parent_id and comment.id not in processed:
                processed.add(comment.id)
                replies.append(comment)
                # Recursively get nested replies
                nested = self._collect_replies(comment.id, all_comments, processed)
                replies.extend(nested)

        # Sort replies by creation time
        replies.sort(key=lambda c: c.created)
        return replies

    def map_page_comments(
        self,
        page_id: str,
        title: str,
        space_key: str,
        content: str,
        page_comments: list[dict[str, Any]],
        inline_comments: list[dict[str, Any]],
        url: str = "",
    ) -> PageWithComments:
        """Map all comments to paragraphs for a Confluence page.

        Main entry point for comment mapping. Takes raw page and comment
        data and produces a fully mapped PageWithComments object.

        Args:
            page_id: Confluence page ID
            title: Page title
            space_key: Space key
            content: Page content in storage format
            page_comments: List of page-level comment data
            inline_comments: List of inline comment data with location info
            url: Optional page URL

        Returns:
            PageWithComments with comments mapped to paragraphs
        """
        # Extract paragraphs
        paragraphs = self.extract_paragraphs(content)

        # Extract inline markers from content
        marker_map = self.extract_inline_markers(content)

        # Build page-level comment threads
        page_threads = self.build_comment_threads(page_comments)

        # Process inline comments
        inline_threads = self.build_comment_threads(inline_comments)

        # Map inline comments to paragraphs
        paragraph_comments: dict[int, list[CommentThread]] = {}
        unmapped: list[CommentThread] = []

        for thread in inline_threads:
            # Get location info from root comment
            location = InlineCommentLocation(
                comment_id=thread.root.id,
                text_selection=thread.root.text_selection,
                marker_ref=self._get_marker_ref(thread.root.id, marker_map),
                original_selection=thread.root.text_selection,
            )

            para_idx = self.map_comment_to_paragraph(location, paragraphs, marker_map)

            if para_idx is not None:
                if para_idx not in paragraph_comments:
                    paragraph_comments[para_idx] = []
                paragraph_comments[para_idx].append(thread)
            else:
                unmapped.append(thread)

        # Build CommentedParagraph objects
        commented_paragraphs: list[CommentedParagraph] = []
        for para in paragraphs:
            threads = paragraph_comments.get(para.index, [])
            commented_paragraphs.append(
                CommentedParagraph(paragraph=para, comment_threads=threads)
            )

        return PageWithComments(
            page_id=page_id,
            title=title,
            space_key=space_key,
            content=content,
            url=url,
            paragraphs=paragraphs,
            commented_paragraphs=commented_paragraphs,
            page_level_comments=page_threads,
            unmapped_inline_comments=unmapped,
        )

    def _get_marker_ref(
        self, comment_id: str, marker_map: dict[str, list[int]]
    ) -> str | None:
        """Find marker ref for a comment ID if one exists."""
        # In some cases, the marker ref might be the comment ID itself
        if comment_id in marker_map:
            return comment_id
        return None
