"""Tests for link verification service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.link_verifier import LinkVerifier, LinkStatus, VerificationResult, get_link_verifier


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
async def test_verify_link_redirect(verifier):
    """Test redirect detection."""
    with patch.object(verifier, '_get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "https://example.com/new-location"}
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await verifier.verify_link("https://example.com/job")
        
        assert result.status == LinkStatus.REDIRECT
        assert result.http_status == 302
        assert result.redirect_url == "https://example.com/new-location"


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
