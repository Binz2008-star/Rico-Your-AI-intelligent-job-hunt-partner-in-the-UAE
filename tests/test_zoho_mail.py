"""
tests/test_zoho_mail.py
Unit tests for Zoho Mail API integration.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.zoho_mail import (
    ZohoToken,
    ZohoEmail,
    ZohoEmailFetchResult,
    ZohoMailClient,
    _load_token,
    _save_token,
    _exchange_code_for_token,
    _refresh_access_token,
    get_valid_token,
    _get_client_id,
    _get_client_secret,
    _get_redirect_uri,
    _get_accounts_domain,
    _get_auth_url,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_token_file():
    """Create a temporary token file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def sample_token():
    """Create a sample Zoho token."""
    return ZohoToken(
        access_token="test_access_token_123",
        refresh_token="test_refresh_token_456",
        expires_in=3600,
        api_domain="https://mail.zoho.com/api",
        token_type="Bearer",
        obtained_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def expired_token():
    """Create an expired Zoho token."""
    return ZohoToken(
        access_token="expired_access_token",
        refresh_token="valid_refresh_token",
        expires_in=3600,
        api_domain="https://mail.zoho.com/api",
        token_type="Bearer",
        obtained_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


@pytest.fixture
def sample_email():
    """Create a sample email."""
    return ZohoEmail(
        message_id="msg123",
        subject="Test Subject",
        sender="test@example.com",
        to=["recipient@example.com"],
        date="2024-01-01T10:00:00Z",
        body="Test body content",
        snippet="Test snippet",
        is_read=False,
        has_attachments=False,
    )


# ---------------------------------------------------------------------------
# Configuration Tests
# ---------------------------------------------------------------------------

def test_get_client_id_missing():
    """Test that missing client ID raises error."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="ZOHO_CLIENT_ID not set"):
            _get_client_id()


def test_get_client_id_present():
    """Test that client ID is returned when set."""
    with patch.dict(os.environ, {"ZOHO_CLIENT_ID": "test_client_id"}):
        assert _get_client_id() == "test_client_id"


def test_get_client_secret_missing():
    """Test that missing client secret raises error."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="ZOHO_CLIENT_SECRET not set"):
            _get_client_secret()


def test_get_client_secret_present():
    """Test that client secret is returned when set."""
    with patch.dict(os.environ, {"ZOHO_CLIENT_SECRET": "test_secret"}):
        assert _get_client_secret() == "test_secret"


def test_get_redirect_uri_default():
    """Test default redirect URI."""
    with patch.dict(os.environ, {}, clear=True):
        assert _get_redirect_uri() == "http://localhost:8080/callback"


def test_get_redirect_uri_custom():
    """Test custom redirect URI."""
    with patch.dict(os.environ, {"ZOHO_REDIRECT_URI": "http://localhost:3000/callback"}):
        assert _get_redirect_uri() == "http://localhost:3000/callback"


def test_get_accounts_domain_default():
    """Test default accounts domain."""
    with patch.dict(os.environ, {}, clear=True):
        assert _get_accounts_domain() == "accounts.zoho.com"


def test_get_accounts_domain_custom():
    """Test custom accounts domain."""
    with patch.dict(os.environ, {"ZOHO_ACCOUNTS_DOMAIN": "accounts.zoho.eu"}):
        assert _get_accounts_domain() == "accounts.zoho.eu"


def test_get_auth_url():
    """Test authorization URL generation."""
    with patch.dict(os.environ, {
        "ZOHO_CLIENT_ID": "test_id",
        "ZOHO_CLIENT_SECRET": "test_secret",
        "ZOHO_REDIRECT_URI": "http://localhost:8080/callback",
    }):
        url, state = _get_auth_url()
        assert "accounts.zoho.com" in url
        assert "test_id" in url
        assert "offline" in url
        assert "code" in url
        assert len(state) > 0


# ---------------------------------------------------------------------------
# Token Tests
# ---------------------------------------------------------------------------

def test_zoho_token_to_dict(sample_token):
    """Test token serialization to dict."""
    data = sample_token.to_dict()
    assert data["access_token"] == "test_access_token_123"
    assert data["refresh_token"] == "test_refresh_token_456"
    assert data["expires_in"] == 3600
    assert "expires_at" in data
    assert "obtained_at" in data


def test_zoho_token_from_dict():
    """Test token deserialization from dict."""
    data = {
        "access_token": "test_access_token_123",
        "refresh_token": "test_refresh_token_456",
        "expires_in": 3600,
        "api_domain": "https://mail.zoho.com/api",
        "token_type": "Bearer",
        "expires_at": "2024-01-01T10:00:00+00:00",
        "obtained_at": "2024-01-01T09:00:00+00:00",
    }
    token = ZohoToken.from_dict(data)
    assert token.access_token == "test_access_token_123"
    assert token.refresh_token == "test_refresh_token_456"
    assert token.expires_in == 3600


def test_zoho_token_is_expired_valid(sample_token):
    """Test that valid token is not expired."""
    assert not sample_token.is_expired()


def test_zoho_token_is_expired_true(expired_token):
    """Test that expired token is detected."""
    assert expired_token.is_expired()


def test_zoho_token_is_expired_near_expiry():
    """Test that token near expiry (within buffer) is considered expired."""
    near_expiry = ZohoToken(
        access_token="near_expiry_token",
        refresh_token="refresh",
        expires_in=3600,
        api_domain="https://mail.zoho.com/api",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=200),  # Within 300s buffer
    )
    assert near_expiry.is_expired()


def test_save_and_load_token(temp_token_file, sample_token):
    """Test token save and load cycle."""
    with patch('src.zoho_mail.TOKEN_FILE', temp_token_file):
        _save_token(sample_token)
        loaded = _load_token()
        assert loaded is not None
        assert loaded.access_token == sample_token.access_token
        assert loaded.refresh_token == sample_token.refresh_token


def test_load_token_not_found(temp_token_file):
    """Test loading token when file doesn't exist."""
    with patch('src.zoho_mail.TOKEN_FILE', temp_token_file):
        loaded = _load_token()
        assert loaded is None


def test_load_token_invalid_json(temp_token_file):
    """Test loading token with invalid JSON."""
    temp_token_file.write_text("invalid json")
    with patch('src.zoho_mail.TOKEN_FILE', temp_token_file):
        loaded = _load_token()
        assert loaded is None


@patch('src.zoho_mail.requests.post')
def test_exchange_code_for_token(mock_post):
    """Test code exchange for token."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
        "api_domain": "https://mail.zoho.com/api",
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    with patch.dict(os.environ, {
        "ZOHO_CLIENT_ID": "test_id",
        "ZOHO_CLIENT_SECRET": "test_secret",
        "ZOHO_REDIRECT_URI": "http://localhost:8080/callback",
    }):
        token = _exchange_code_for_token("test_code")
        assert token.access_token == "new_access_token"
        assert token.refresh_token == "new_refresh_token"
        assert token.expires_in == 3600


@patch('src.zoho_mail.requests.post')
def test_refresh_access_token(mock_post):
    """Test token refresh."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "access_token": "refreshed_access_token",
        "expires_in": 3600,
        "api_domain": "https://mail.zoho.com/api",
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    
    with patch.dict(os.environ, {
        "ZOHO_CLIENT_ID": "test_id",
        "ZOHO_CLIENT_SECRET": "test_secret",
    }):
        token = _refresh_access_token("valid_refresh_token")
        assert token.access_token == "refreshed_access_token"
        assert token.refresh_token == "valid_refresh_token"  # Preserved


@patch('src.zoho_mail._load_token')
def test_get_valid_token_valid(mock_load_token, sample_token):
    """Test getting valid token when current token is valid."""
    mock_load_token.return_value = sample_token
    token = get_valid_token()
    assert token.access_token == sample_token.access_token


@patch('src.zoho_mail._load_token')
@patch('src.zoho_mail._refresh_access_token')
@patch('src.zoho_mail._save_token')
def test_get_valid_token_refresh(mock_save, mock_refresh, mock_load_token, expired_token):
    """Test getting valid token when refresh is needed."""
    mock_load_token.return_value = expired_token
    mock_refresh.return_value = sample_token = ZohoToken(
        access_token="refreshed_token",
        refresh_token="refresh_token",
        expires_in=3600,
        api_domain="https://mail.zoho.com/api",
    )
    
    token = get_valid_token()
    assert token.access_token == "refreshed_token"
    mock_refresh.assert_called_once()
    mock_save.assert_called_once()


@patch('src.zoho_mail._load_token')
def test_get_valid_token_no_token(mock_load_token):
    """Test getting valid token when no token exists."""
    mock_load_token.return_value = None
    with pytest.raises(RuntimeError, match="No valid token found"):
        get_valid_token()


# ---------------------------------------------------------------------------
# ZohoMailClient Tests
# ---------------------------------------------------------------------------

@patch('src.zoho_mail.get_valid_token')
def test_zoho_mail_client_init(mock_get_token, sample_token):
    """Test ZohoMailClient initialization."""
    mock_get_token.return_value = sample_token
    client = ZohoMailClient()
    assert client.token.access_token == sample_token.access_token
    assert client.api_domain == sample_token.api_domain


@patch('src.zoho_mail.get_valid_token')
def test_zoho_mail_client_init_with_token(mock_get_token, sample_token):
    """Test ZohoMailClient initialization with provided token."""
    client = ZohoMailClient(token=sample_token)
    assert client.token.access_token == sample_token.access_token
    mock_get_token.assert_not_called()


@patch('src.zoho_mail.get_valid_token')
def test_get_headers(mock_get_token, sample_token):
    """Test header generation."""
    mock_get_token.return_value = sample_token
    client = ZohoMailClient()
    headers = client._get_headers()
    assert headers["Authorization"] == f"Bearer {sample_token.access_token}"
    assert headers["Content-Type"] == "application/json"


@patch('src.zoho_mail.get_valid_token')
@patch('src.zoho_mail.requests.request')
def test_make_request(mock_request, mock_get_token, sample_token):
    """Test API request making."""
    mock_get_token.return_value = sample_token
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}
    mock_response.raise_for_status = Mock()
    mock_request.return_value = mock_response
    
    client = ZohoMailClient()
    result = client._make_request("GET", "/test")
    
    assert result == {"data": "test"}
    mock_request.assert_called_once()


@patch('src.zoho_mail.get_valid_token')
@patch('src.zoho_mail.requests.request')
def test_get_messages(mock_request, mock_get_token, sample_token):
    """Test fetching messages."""
    mock_get_token.return_value = sample_token
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            {
                "messageId": "msg1",
                "subject": "Test Subject",
                "from": {"address": "sender@example.com"},
                "to": [{"address": "recipient@example.com"}],
                "receivedTime": "2024-01-01T10:00:00Z",
                "summary": "Test body",
                "isRead": False,
                "hasAttachment": False,
            }
        ],
        "status": {"total": 1},
    }
    mock_response.raise_for_status = Mock()
    mock_request.return_value = mock_response
    
    client = ZohoMailClient()
    result = client.get_messages(limit=10)
    
    assert len(result.emails) == 1
    assert result.emails[0].subject == "Test Subject"
    assert result.total_count == 1


@patch('src.zoho_mail.get_valid_token')
@patch('src.zoho_mail.requests.request')
def test_get_message_detail(mock_request, mock_get_token, sample_token):
    """Test fetching message detail."""
    mock_get_token.return_value = sample_token
    mock_response = Mock()
    mock_response.json.return_value = {"data": {"messageId": "msg1"}}
    mock_response.raise_for_status = Mock()
    mock_request.return_value = mock_response
    
    client = ZohoMailClient()
    result = client.get_message_detail("msg1")
    
    assert result["data"]["messageId"] == "msg1"


@patch('src.zoho_mail.get_valid_token')
@patch('src.zoho_mail.requests.request')
def test_send_email(mock_request, mock_get_token, sample_token):
    """Test sending email."""
    mock_get_token.return_value = sample_token
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": {"messageId": "new_msg_id"}
    }
    mock_response.raise_for_status = Mock()
    mock_request.return_value = mock_response
    
    client = ZohoMailClient()
    result = client.send_email(
        to="recipient@example.com",
        subject="Test Subject",
        body="Test body",
    )
    
    assert result["data"]["messageId"] == "new_msg_id"


@patch('src.zoho_mail.get_valid_token')
@patch('src.zoho_mail.requests.request')
def test_send_email_with_cc_bcc(mock_request, mock_get_token, sample_token):
    """Test sending email with CC and BCC."""
    mock_get_token.return_value = sample_token
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": {"messageId": "new_msg_id"}
    }
    mock_response.raise_for_status = Mock()
    mock_request.return_value = mock_response
    
    client = ZohoMailClient()
    result = client.send_email(
        to="recipient@example.com",
        subject="Test Subject",
        body="Test body",
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
    )
    
    assert result["data"]["messageId"] == "new_msg_id"
    # Verify the request includes CC and BCC
    call_args = mock_request.call_args
    assert "ccAddress" in call_args[1]["json"]
    assert "bccAddress" in call_args[1]["json"]


# ---------------------------------------------------------------------------
# Data Model Tests
# ---------------------------------------------------------------------------

def test_zoho_email_dataclass(sample_email):
    """Test ZohoEmail dataclass."""
    assert sample_email.message_id == "msg123"
    assert sample_email.subject == "Test Subject"
    assert sample_email.sender == "test@example.com"
    assert sample_email.is_read is False
    assert sample_email.has_attachments is False


def test_zoho_email_fetch_result():
    """Test ZohoEmailFetchResult dataclass."""
    emails = [
        ZohoEmail(
            message_id="msg1",
            subject="Subject 1",
            sender="sender1@example.com",
            to=["recipient@example.com"],
            date="2024-01-01T10:00:00Z",
            body="Body 1",
            snippet="Snippet 1",
            is_read=False,
            has_attachments=False,
        )
    ]
    result = ZohoEmailFetchResult(
        emails=emails,
        total_count=1,
        fetched_at="2024-01-01T10:00:00Z",
    )
    assert len(result.emails) == 1
    assert result.total_count == 1
    assert result.fetched_at == "2024-01-01T10:00:00Z"
