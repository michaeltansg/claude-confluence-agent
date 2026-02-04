#!/usr/bin/env python3
"""Main Claude agent application for Confluence comment extraction.

This module provides a CLI interface for fetching Confluence page comments
and generating markdown reports using the Claude agent SDK.
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions

from src.config import AgentConfig, load_config
from src.confluence import ConfluenceClient, InlineComment, PageComment
from src.generators import MarkdownReportGenerator, ReportConfig
from src.models import PageWithComments
from src.processors import CommentMapper


def _comments_to_dicts(comments: list[PageComment] | list[InlineComment]) -> list[dict]:
    """Convert comment dataclasses to dictionaries for the mapper."""
    return [asdict(c) for c in comments]


def create_agent(config: AgentConfig) -> "ClaudeAgent":
    """Create and configure the Claude agent.

    Args:
        config: Agent configuration with API keys and settings.

    Returns:
        Configured ClaudeAgent instance.
    """
    try:
        from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions
    except ImportError as e:
        raise ImportError(
            "claude-agent-sdk is required for agent mode. "
            "Install it with: pip install claude-agent-sdk"
        ) from e

    options_kwargs = {
        "api_key": config.api_key,
        "model": config.model,
        "max_tokens": config.max_tokens,
        "setting_sources": [str(config.skills_directory)],
        "allowed_tools": config.allowed_tools,
    }

    # Add base_url for LiteLLM proxy if configured
    if config.base_url:
        options_kwargs["base_url"] = config.base_url

    options = ClaudeAgentOptions(**options_kwargs)

    return ClaudeAgent(options)


def fetch_pages_with_comments(
    client: ConfluenceClient,
    space: Optional[str] = None,
    label: Optional[str] = None,
    page_id: Optional[str] = None,
    page_title: Optional[str] = None,
    all_with_comments: bool = False,
) -> list[PageWithComments]:
    """Fetch pages and their comments based on filter criteria.

    Args:
        client: Confluence API client.
        space: Space key to filter by.
        label: Label to filter by.
        page_id: Specific page ID to fetch.
        page_title: Page title to search for.
        all_with_comments: Fetch all pages with comments in space.

    Returns:
        List of pages with their mapped comments.
    """
    mapper = CommentMapper()
    pages_with_comments: list[PageWithComments] = []

    def _process_page(page):
        """Helper to process a single page and map its comments."""
        content = client.get_page_content(page.id)
        all_comments = client.get_page_comments(page.id)
        inline_comments = client.get_inline_comments(page.id)

        # Build a lookup of comment IDs that are inline comments
        inline_ids = {c.id for c in inline_comments}

        # Merge author/created info from v1 API into inline comments (v2 doesn't return author)
        comment_info = {c.id: (c.author, c.created) for c in all_comments}
        for ic in inline_comments:
            if ic.id in comment_info:
                author, created = comment_info[ic.id]
                if ic.author == "unknown":
                    ic.author = author
                if not ic.created:
                    ic.created = created

        # Filter out inline comments from page-level comments
        # (v1 API returns all comments including inline ones)
        page_only_comments = [c for c in all_comments if c.id not in inline_ids]

        return mapper.map_page_comments(
            page_id=page.id,
            title=page.title,
            space_key=page.space_key,
            content=content,
            page_comments=_comments_to_dicts(page_only_comments),
            inline_comments=_comments_to_dicts(inline_comments),
            url=page.url,
        )

    if page_id:
        page = client.get_page_by_id(page_id)
        if page:
            pages_with_comments.append(_process_page(page))

    elif page_title:
        pages = client.get_pages_by_title(page_title, space_key=space)
        for page in pages:
            pages_with_comments.append(_process_page(page))

    elif label and space:
        pages = client.get_pages_by_label(label, space_key=space)
        for page in pages:
            pages_with_comments.append(_process_page(page))

    elif all_with_comments and space:
        pages = client.get_pages_with_comments(space_key=space)
        for page in pages:
            pages_with_comments.append(_process_page(page))

    return pages_with_comments


def generate_report(
    pages: list[PageWithComments],
    output_path: Optional[Path] = None,
    show_only_commented: bool = False,
    include_resolved: bool = True,
) -> str:
    """Generate a markdown report from pages with comments.

    Args:
        pages: List of pages with mapped comments.
        output_path: Optional path to write the report to.
        show_only_commented: Only show paragraphs with comments.
        include_resolved: Include resolved comment threads.

    Returns:
        Generated markdown report content.
    """
    report_config = ReportConfig(
        show_only_commented=show_only_commented,
        include_resolved=include_resolved,
    )

    generator = MarkdownReportGenerator(config=report_config)
    report = generator.generate(pages)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    return report


def run_pipeline(
    config: AgentConfig,
    space: Optional[str] = None,
    label: Optional[str] = None,
    page_id: Optional[str] = None,
    page_title: Optional[str] = None,
    all_with_comments: bool = False,
    output: Optional[str] = None,
) -> str:
    """Run the full comment extraction pipeline.

    Pipeline: ConfluenceClient → CommentMapper → MarkdownGenerator

    Args:
        config: Agent configuration.
        space: Space key to filter by.
        label: Label to filter by.
        page_id: Specific page ID to fetch.
        page_title: Page title to search for.
        all_with_comments: Fetch all pages with comments.
        output: Output file path.

    Returns:
        Generated markdown report.
    """
    if not config.confluence:
        raise ValueError(
            "Confluence configuration is required. "
            "Set CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN."
        )

    client = ConfluenceClient(
        url=config.confluence.base_url,
        username=config.confluence.username,
        api_token=config.confluence.api_token,
        cloud=config.confluence.cloud,
    )

    pages = fetch_pages_with_comments(
        client=client,
        space=space,
        label=label,
        page_id=page_id,
        page_title=page_title,
        all_with_comments=all_with_comments,
    )

    output_path = Path(output) if output else None
    report = generate_report(pages, output_path=output_path)

    return report


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Optional list of arguments (for testing).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Extract Confluence page comments and generate markdown reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --page-id 123456
  %(prog)s --space MYSPACE --label review
  %(prog)s --space MYSPACE --all-with-comments --output report.md
  %(prog)s --page-title "My Document" --space MYSPACE
        """,
    )

    filter_group = parser.add_argument_group("filter options")
    filter_group.add_argument(
        "--space",
        "-s",
        type=str,
        help="Confluence space key to filter pages",
    )
    filter_group.add_argument(
        "--label",
        "-l",
        type=str,
        help="Label to filter pages by",
    )
    filter_group.add_argument(
        "--page-id",
        "-p",
        type=str,
        help="Specific page ID to fetch",
    )
    filter_group.add_argument(
        "--page-title",
        "-t",
        type=str,
        help="Page title to search for",
    )
    filter_group.add_argument(
        "--all-with-comments",
        "-a",
        action="store_true",
        help="Fetch all pages with comments in space (requires --space)",
    )

    output_group = parser.add_argument_group("output options")
    output_group.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path for the generated report",
    )

    config_group = parser.add_argument_group("configuration")
    config_group.add_argument(
        "--env-file",
        type=str,
        help="Path to .env file (default: .env)",
    )
    config_group.add_argument(
        "--agent-mode",
        action="store_true",
        help="Run in agent mode with skill support",
    )

    return parser.parse_args(args)


def validate_args(args: argparse.Namespace, default_space: Optional[str] = None) -> None:
    """Validate command line arguments.

    Args:
        args: Parsed arguments.
        default_space: Default space from configuration.

    Raises:
        ValueError: If arguments are invalid.
    """
    has_filter = any([args.page_id, args.page_title, args.label, args.all_with_comments])

    if not has_filter:
        raise ValueError(
            "At least one filter option is required: "
            "--page-id, --page-title, --label, or --all-with-comments"
        )

    effective_space = args.space or default_space

    if args.all_with_comments and not effective_space:
        raise ValueError("--all-with-comments requires --space to be specified")

    if args.label and not effective_space:
        raise ValueError("--label requires --space to be specified")


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI application.

    Args:
        args: Optional list of arguments (for testing).

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parsed_args = parse_args(args)

    try:
        config = load_config(parsed_args.env_file)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    # Get default space from config
    default_space = config.confluence.default_space if config.confluence else None

    try:
        validate_args(parsed_args, default_space=default_space)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if parsed_args.agent_mode:
        agent = create_agent(config)
        print(f"Agent initialized with skills from: {config.skills_directory}")
        print(f"Allowed tools: {', '.join(config.allowed_tools)}")

    # Use default space if not provided via CLI
    effective_space = parsed_args.space or default_space

    try:
        report = run_pipeline(
            config=config,
            space=effective_space,
            label=parsed_args.label,
            page_id=parsed_args.page_id,
            page_title=parsed_args.page_title,
            all_with_comments=parsed_args.all_with_comments,
            output=parsed_args.output,
        )

        if not parsed_args.output:
            print(report)
        else:
            print(f"Report written to: {parsed_args.output}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cli() -> None:
    """CLI entry point for the console script."""
    sys.exit(main())


if __name__ == "__main__":
    cli()
