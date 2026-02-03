"""Tests for the Confluence API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.confluence.client import (
    ConfluenceAuthError,
    ConfluenceClient,
    ConfluenceError,
    ConfluenceNotFoundError,
    InlineComment,
    Page,
    PageComment,
)


class TestConfluenceClientInit:
    """Tests for ConfluenceClient initialization."""

    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials."""
        with patch.dict(
            "os.environ",
            {},
            clear=True,
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient(
                    url="https://test.atlassian.net",
                    username="test@example.com",
                    api_token="test-token",
                    cloud=True,
                )

                mock_confluence.assert_called_once_with(
                    url="https://test.atlassian.net",
                    username="test@example.com",
                    password="test-token",
                    cloud=True,
                )

    def test_init_from_environment_variables(self):
        """Test initialization from environment variables."""
        env_vars = {
            "CONFLUENCE_URL": "https://env.atlassian.net",
            "CONFLUENCE_EMAIL": "env@example.com",
            "CONFLUENCE_API_TOKEN": "env-token",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()

                mock_confluence.assert_called_once()
                call_kwargs = mock_confluence.call_args[1]
                assert call_kwargs["url"] == "https://env.atlassian.net"
                assert call_kwargs["username"] == "env@example.com"

    def test_init_from_domain_environment_variable(self):
        """Test URL building from CONFLUENCE_DOMAIN."""
        env_vars = {
            "CONFLUENCE_DOMAIN": "test.atlassian.net",
            "CONFLUENCE_EMAIL": "test@example.com",
            "CONFLUENCE_API_TOKEN": "test-token",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()

                call_kwargs = mock_confluence.call_args[1]
                assert call_kwargs["url"] == "https://test.atlassian.net"

    def test_init_missing_url_raises_error(self):
        """Test that missing URL raises ConfluenceAuthError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfluenceAuthError) as exc_info:
                ConfluenceClient(
                    username="test@example.com",
                    api_token="test-token",
                )

            assert "Missing Confluence URL" in str(exc_info.value)

    def test_init_missing_credentials_raises_error(self):
        """Test that missing credentials raises ConfluenceAuthError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfluenceAuthError) as exc_info:
                ConfluenceClient(url="https://test.atlassian.net")

            assert "Missing credentials" in str(exc_info.value)


class TestConfluenceClientContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_closes_client(self):
        """Test that context manager properly closes HTTP client."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence"):
                with ConfluenceClient() as client:
                    # Access _client to create it
                    mock_http_client = MagicMock()
                    client._http_client = mock_http_client

                mock_http_client.close.assert_called_once()


class TestGetPageById:
    """Tests for get_page_by_id method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_page_by_id_success(self, client, mock_page_response):
        """Test successful page retrieval by ID."""
        client._confluence.get_page_by_id.return_value = mock_page_response

        page = client.get_page_by_id("123456")

        assert isinstance(page, Page)
        assert page.id == "123456"
        assert page.title == "Test Page Title"
        assert page.space_key == "TEST"
        assert page.version == 5

    def test_get_page_by_id_not_found(self, client):
        """Test page not found raises ConfluenceNotFoundError."""
        client._confluence.get_page_by_id.return_value = None

        with pytest.raises(ConfluenceNotFoundError):
            client.get_page_by_id("nonexistent")

    def test_get_page_by_id_with_expand(self, client, mock_page_response):
        """Test page retrieval with custom expand fields."""
        client._confluence.get_page_by_id.return_value = mock_page_response

        client.get_page_by_id("123456", expand="body.storage,space,version")

        client._confluence.get_page_by_id.assert_called_with(
            "123456", expand="body.storage,space,version"
        )


class TestGetPagesByTitle:
    """Tests for get_pages_by_title method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_pages_by_title_single_result(self, client, mock_page_response):
        """Test getting pages by title with a single result."""
        client._confluence.get_page_by_title.return_value = mock_page_response

        pages = client.get_pages_by_title("Test Page Title", "TEST")

        assert len(pages) == 1
        assert pages[0].title == "Test Page Title"

    def test_get_pages_by_title_no_results(self, client):
        """Test getting pages by title with no results."""
        client._confluence.get_page_by_title.return_value = None

        pages = client.get_pages_by_title("Nonexistent", "TEST")

        assert pages == []

    def test_get_pages_by_title_multiple_results(self, client):
        """Test getting pages by title with multiple results."""
        mock_results = [
            {
                "id": "111",
                "title": "Test Page",
                "version": {"number": 1},
                "_links": {"webui": "/pages/111"},
            },
            {
                "id": "222",
                "title": "Test Page Copy",
                "version": {"number": 2},
                "_links": {"webui": "/pages/222"},
            },
        ]
        client._confluence.get_page_by_title.return_value = mock_results

        pages = client.get_pages_by_title("Test", "TEST", limit=2)

        assert len(pages) == 2


class TestGetPagesByLabel:
    """Tests for get_pages_by_label method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_pages_by_label_with_space(self, client, mock_cql_search_response):
        """Test getting pages by label within a space."""
        client._confluence.cql.return_value = mock_cql_search_response

        pages = client.get_pages_by_label("review", space_key="TEST")

        assert len(pages) == 2
        client._confluence.cql.assert_called_once()
        call_args = client._confluence.cql.call_args
        assert 'label="review"' in call_args[0][0]
        assert 'space="TEST"' in call_args[0][0]

    def test_get_pages_by_label_without_space(self, client, mock_cql_search_response):
        """Test getting pages by label across all spaces."""
        client._confluence.cql.return_value = mock_cql_search_response

        pages = client.get_pages_by_label("documentation")

        call_args = client._confluence.cql.call_args
        assert 'label="documentation"' in call_args[0][0]
        assert "space=" not in call_args[0][0]


class TestGetPagesWithComments:
    """Tests for get_pages_with_comments method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_pages_with_comments(self, client, mock_space_pages_response):
        """Test filtering pages that have comments."""
        client._confluence.get_all_pages_from_space.return_value = mock_space_pages_response

        # First page has comments, second doesn't
        client._confluence.get_page_comments.side_effect = [
            {"results": [{"id": "comment-1"}]},  # Has comments
            {"results": []},  # No comments
        ]

        pages = client.get_pages_with_comments("TEST")

        assert len(pages) == 1
        assert pages[0].id == "123456"


class TestGetInlineComments:
    """Tests for get_inline_comments method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence"):
                client = ConfluenceClient()
                client._http_client = MagicMock()
                return client

    def test_get_inline_comments_success(self, client, mock_inline_comments_response):
        """Test successful inline comments retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_inline_comments_response
        client._http_client.get.return_value = mock_response

        comments = client.get_inline_comments("123456")

        assert len(comments) == 2
        assert isinstance(comments[0], InlineComment)
        assert comments[0].id == "inline-1"
        assert comments[0].resolved is False
        assert len(comments[0].replies) == 1
        assert comments[1].resolved is True

    def test_get_inline_comments_auth_error(self, client):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        client._http_client.get.return_value = mock_response

        with pytest.raises(ConfluenceAuthError):
            client.get_inline_comments("123456")

    def test_get_inline_comments_not_found(self, client):
        """Test page not found error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        client._http_client.get.return_value = mock_response

        with pytest.raises(ConfluenceNotFoundError):
            client.get_inline_comments("nonexistent")


class TestGetPageContent:
    """Tests for get_page_content method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_page_content_storage_format(self, client, mock_page_content_response):
        """Test getting page content in storage format."""
        client._confluence.get_page_by_id.return_value = mock_page_content_response

        content = client.get_page_content("123456", body_format="storage")

        assert "<p>This is the first paragraph" in content
        assert "ac:inline-comment-marker" in content

    def test_get_page_content_not_found(self, client):
        """Test page not found raises ConfluenceNotFoundError."""
        client._confluence.get_page_by_id.return_value = None

        with pytest.raises(ConfluenceNotFoundError):
            client.get_page_content("nonexistent")


class TestGetPageComments:
    """Tests for get_page_comments method."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_get_page_comments_success(self, client, mock_page_comments_response):
        """Test successful page comments retrieval."""
        client._confluence.get_page_comments.return_value = mock_page_comments_response

        comments = client.get_page_comments("123456")

        assert len(comments) == 2
        assert isinstance(comments[0], PageComment)
        assert comments[0].id == "comment-100"
        assert comments[0].author == "alice@example.com"
        assert comments[1].parent_id == "comment-100"

    def test_get_page_comments_empty(self, client):
        """Test page with no comments returns empty list."""
        client._confluence.get_page_comments.return_value = {"results": []}

        comments = client.get_page_comments("123456")

        assert comments == []


class TestErrorHandling:
    """Tests for error handling in ConfluenceClient."""

    @pytest.fixture
    def client(self):
        """Create a mocked ConfluenceClient."""
        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_URL": "https://test.atlassian.net",
                "CONFLUENCE_EMAIL": "test@example.com",
                "CONFLUENCE_API_TOKEN": "test-token",
            },
        ):
            with patch("src.confluence.client.Confluence") as mock_confluence:
                client = ConfluenceClient()
                client._confluence = mock_confluence.return_value
                return client

    def test_handle_api_error_401(self, client):
        """Test 401 error is converted to ConfluenceAuthError."""
        client._confluence.get_page_by_id.side_effect = Exception("401 Unauthorized")

        with pytest.raises(ConfluenceAuthError):
            client.get_page_by_id("123456")

    def test_handle_api_error_404(self, client):
        """Test 404 error is converted to ConfluenceNotFoundError."""
        client._confluence.get_page_by_id.side_effect = Exception("404 Not Found")

        with pytest.raises(ConfluenceNotFoundError):
            client.get_page_by_id("123456")

    def test_handle_api_error_generic(self, client):
        """Test generic errors are converted to ConfluenceError."""
        client._confluence.get_page_by_id.side_effect = Exception("Some API error")

        with pytest.raises(ConfluenceError):
            client.get_page_by_id("123456")
