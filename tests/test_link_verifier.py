"""Tests for link verification service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.link_verifier import LinkVerifier, LinkStatus, VerificationResult, get_link_verifier, _is_safe_url


@pytest.fixture
def verifier():
    """Create a fresh link verifier instance for each test."""
    return LinkVerifier()


@pytest.mark.asyncio
async def test_verify_link_success(verifier):
    """Test successful link verification."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Job listing</body></html>"
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.LIVE
        assert result.http_status == 200
        assert result.error_message is None
        assert isinstance(result.verified_at, datetime)


@pytest.mark.asyncio
async def test_verify_link_404(verifier):
    """Test 404 status code detection."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 404
        assert result.error_message == "HTTP 404"


@pytest.mark.asyncio
async def test_verify_link_410(verifier):
    """Test 410 Gone status code detection."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 410


@pytest.mark.asyncio
async def test_verify_link_redirect_to_404(verifier):
    """Test redirect to 404 page (should follow and return expired)."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        
        # First call returns redirect
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 301
        mock_response_1.headers = {"location": "https://www.jobted.ae/job/12345"}
        
        # Second call returns 404
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 404
        
        mock_client.get.side_effect = [mock_response_1, mock_response_2]
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://jobted.ae/job/12345")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 404


@pytest.mark.asyncio
async def test_verify_link_redirect_to_dead_page_pattern(verifier):
    """Test redirect to page with dead pattern (should follow and return expired)."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        
        # First call returns redirect
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 301
        mock_response_1.headers = {"location": "https://www.jobted.ae/job/12345"}
        
        # Second call returns 200 with dead pattern
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.text = "<html><body>404 Not Found - The requested page could not be found</body></html>"
        
        mock_client.get.side_effect = [mock_response_1, mock_response_2]
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://jobted.ae/job/12345")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 200
        assert "Dead page pattern detected" in result.error_message


@pytest.mark.asyncio
async def test_verify_jobted_404_page(verifier):
    """Test Jobted 404 page pattern detection."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>404 Not Found - The requested page could not be found</body></html>"
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://jobted.ae/job")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 200
        assert result.error_message == "Dead page pattern detected"


@pytest.mark.asyncio
async def test_verify_indead_dead_page(verifier):
    """Test Indeed dead page pattern detection."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>We can't find this page</body></html>"
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://indeed.com/job")
        
        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 200
        assert result.error_message == "Dead page pattern detected"


@pytest.mark.asyncio
async def test_verify_link_timeout(verifier):
    """Test timeout handling."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        import httpx
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.NEEDS_REVIEW
        assert result.http_status is None
        assert result.error_message == "Request timeout"


@pytest.mark.asyncio
async def test_verify_link_connection_error(verifier):
    """Test connection error handling."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        import httpx
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.NEEDS_REVIEW
        assert result.http_status is None
        assert result.error_message == "Connection failed"


@pytest.mark.asyncio
async def test_verify_link_no_url(verifier):
    """Test handling of empty URL."""
    result = await verifier.verify_link("")
    
    assert result.status == LinkStatus.SOURCE_ONLY
    assert result.http_status is None
    assert result.error_message == "No URL provided"


@pytest.mark.asyncio
async def test_verify_links_batch(verifier):
    """Test batch link verification."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        
        # Mock different responses for different URLs
        def get_side_effect(url, *args, **kwargs):
            mock_response = MagicMock()
            if "404" in url:
                mock_response.status_code = 404
            else:
                mock_response.status_code = 200
                mock_response.text = "<html><body>Job listing</body></html>"
            return mock_response
        
        mock_client.get.side_effect = get_side_effect
        mock_get_client.return_value = mock_client
        
        urls = ["https://example.com/job1", "https://example.com/job404"]
        results = await verifier.verify_links_batch(urls)
        
        assert len(results) == 2
        assert results["https://example.com/job1"].status == LinkStatus.LIVE
        assert results["https://example.com/job404"].status == LinkStatus.EXPIRED


def test_get_link_verifier_singleton():
    """Test that get_link_verifier returns singleton instance."""
    verifier1 = get_link_verifier()
    verifier2 = get_link_verifier()
    
    assert verifier1 is verifier2


@pytest.mark.asyncio
async def test_close_client(verifier):
    """Test closing HTTP client."""
    # Manually set the client to test close behavior
    with patch('src.services.link_verifier.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Initialize client
        verifier._client = mock_client
        
        await verifier.close()
        
        mock_client.aclose.assert_called_once()
        assert verifier._client is None


def test_is_safe_url_blocks_localhost():
    """Test that localhost URLs are blocked."""
    assert not _is_safe_url("http://localhost:8080")
    assert not _is_safe_url("http://127.0.0.1")
    assert not _is_safe_url("http://127.0.0.1:3000")
    assert not _is_safe_url("http://0.0.0.0")


def test_is_safe_url_blocks_private_ips():
    """Test that private IP ranges are blocked."""
    assert not _is_safe_url("http://10.0.0.1")
    assert not _is_safe_url("http://172.16.0.1")
    assert not _is_safe_url("http://192.168.1.1")
    assert not _is_safe_url("http://169.254.169.254")  # AWS metadata


def test_is_safe_url_blocks_metadata_ips():
    """Test that cloud metadata IPs are blocked."""
    assert not _is_safe_url("http://169.254.169.254")
    assert not _is_safe_url("http://metadata.google.internal")


def test_is_safe_url_blocks_non_http_schemes():
    """Test that non-HTTP schemes are blocked."""
    assert not _is_safe_url("file:///etc/passwd")
    assert not _is_safe_url("ftp://example.com")
    assert not _is_safe_url("gopher://example.com")


def test_is_safe_url_allows_public_urls():
    """Test that public URLs are allowed."""
    assert _is_safe_url("https://example.com")
    assert _is_safe_url("https://jobted.ae/job")
    assert _is_safe_url("https://indeed.com/job")
    assert _is_safe_url("http://example.com")


@pytest.mark.asyncio
async def test_verify_link_blocks_redirect_to_private_ip(verifier):
    """Test that redirects to private IPs are blocked."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "http://192.168.1.1/internal"}
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.BLOCKED
        assert result.http_status == 302
        assert "SSRF protection" in result.error_message
        assert result.redirect_url == "http://192.168.1.1/internal"


@pytest.mark.asyncio
async def test_verify_link_blocks_initial_metadata_ip(verifier):
    """Test that an initial URL to a cloud metadata IP is blocked before any fetch.

    Regression for the SSRF gap where verify_link() fetched the initial URL
    before validating it (only redirect targets were checked). Callers such as
    the chat flow invoke verify_link() directly, bypassing route-level
    validation, so the method must self-protect.
    """
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        result = await verifier.verify_link("http://169.254.169.254/latest/meta-data/")

        assert result.status == LinkStatus.BLOCKED
        assert "SSRF protection" in result.error_message
        # The request must never be issued for a blocked initial URL.
        mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_link_blocks_initial_localhost(verifier):
    """Test that an initial URL to localhost is blocked before any fetch."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        result = await verifier.verify_link("http://localhost:8000/internal")

        assert result.status == LinkStatus.BLOCKED
        assert "SSRF protection" in result.error_message
        mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_link_blocks_initial_private_ip(verifier):
    """Test that an initial URL to a private IP range is blocked before any fetch."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        result = await verifier.verify_link("http://192.168.1.1/admin")

        assert result.status == LinkStatus.BLOCKED
        assert "SSRF protection" in result.error_message
        mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_link_blocks_initial_non_http_scheme(verifier):
    """Test that an initial file:// URL is blocked before any fetch."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        result = await verifier.verify_link("file:///etc/passwd")

        assert result.status == LinkStatus.BLOCKED
        assert "SSRF protection" in result.error_message
        mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_indeed_expired_job_page_200(verifier):
    """Test Indeed job page that returns HTTP 200 but body says expired."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>"
            "<h1>This job has expired on Indeed</h1>"
            "<p>Reasons could include: the employer is not accepting applications,</p>"
            "<p>is not actively hiring, or is reviewing applications</p>"
            "</body></html>"
        )
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await verifier.verify_link("https://indeed.com/job/abc123")

        assert result.status == LinkStatus.EXPIRED
        assert result.http_status == 200
        assert "Dead page pattern detected" in result.error_message
