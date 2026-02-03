"""Agent configuration module for Claude agent settings and API keys."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class ConfluenceConfig:
    """Configuration for Confluence API access."""

    base_url: str
    username: str
    api_token: str
    cloud: bool = True
    default_space: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ConfluenceConfig":
        """Load Confluence configuration from environment variables.

        Supports both naming conventions:
        - New: CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME
        - Legacy: CONFLUENCE_DOMAIN, CONFLUENCE_EMAIL
        """
        # Support both new and legacy variable names
        base_url = os.getenv("CONFLUENCE_BASE_URL") or os.getenv("CONFLUENCE_DOMAIN", "")
        username = os.getenv("CONFLUENCE_USERNAME") or os.getenv("CONFLUENCE_EMAIL", "")
        api_token = os.getenv("CONFLUENCE_API_TOKEN", "")
        cloud = os.getenv("CONFLUENCE_CLOUD", "true").lower() == "true"
        default_space = os.getenv("CONFLUENCE_DEFAULT_SPACE") or None

        if not base_url:
            raise ValueError(
                "CONFLUENCE_BASE_URL (or CONFLUENCE_DOMAIN) environment variable is required"
            )
        if not username:
            raise ValueError(
                "CONFLUENCE_USERNAME (or CONFLUENCE_EMAIL) environment variable is required"
            )
        if not api_token:
            raise ValueError("CONFLUENCE_API_TOKEN environment variable is required")

        return cls(
            base_url=base_url,
            username=username,
            api_token=api_token,
            cloud=cloud,
            default_space=default_space,
        )


@dataclass
class AgentConfig:
    """Configuration for the Claude agent."""

    api_key: str
    base_url: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    skills_directory: Path = field(default_factory=lambda: Path("skills"))
    allowed_tools: list[str] = field(
        default_factory=lambda: ["Skill", "Read", "Write", "Bash"]
    )
    max_tokens: int = 4096
    confluence: Optional[ConfluenceConfig] = None

    @property
    def uses_proxy(self) -> bool:
        """Check if configuration uses LiteLLM proxy."""
        return self.base_url is not None

    @classmethod
    def from_env(cls, load_confluence: bool = True) -> "AgentConfig":
        """Load agent configuration from environment variables.

        Supports two authentication modes:
        - Direct Claude API: Set ANTHROPIC_API_KEY
        - LiteLLM Proxy: Set ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN

        Args:
            load_confluence: Whether to load Confluence configuration.
        """
        # Check for direct API key first
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        base_url: Optional[str] = None

        # If no direct API key, check for LiteLLM proxy configuration
        if not api_key:
            proxy_base_url = os.getenv("ANTHROPIC_BASE_URL", "")
            auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", "")

            if proxy_base_url and auth_token:
                api_key = auth_token
                base_url = proxy_base_url
            elif proxy_base_url or auth_token:
                raise ValueError(
                    "LiteLLM proxy requires both ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN"
                )

        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        skills_dir = Path(os.getenv("SKILLS_DIRECTORY", "skills"))
        max_tokens = int(os.getenv("MAX_TOKENS", "4096"))

        allowed_tools_str = os.getenv("ALLOWED_TOOLS", "Skill,Read,Write,Bash")
        allowed_tools = [t.strip() for t in allowed_tools_str.split(",")]

        confluence = None
        if load_confluence:
            try:
                confluence = ConfluenceConfig.from_env()
            except ValueError:
                pass

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            skills_directory=skills_dir,
            allowed_tools=allowed_tools,
            max_tokens=max_tokens,
            confluence=confluence,
        )


def load_config(env_file: Optional[str] = None) -> AgentConfig:
    """Load configuration from environment file and variables.

    Args:
        env_file: Path to .env file. Defaults to .env in current directory.

    Returns:
        Loaded AgentConfig instance.
    """
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    return AgentConfig.from_env()
