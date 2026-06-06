"""
src/zoho_mail.py
Zoho Mail API integration with OAuth 2.0 authorization (read-only for inbox intelligence).

Setup (one-time):
    1. Go to https://api-console.zoho.com
    2. ADD CLIENT → Server-based Applications (NOT Self Client)
    3. Set:
       - Client Name: Rico Mail Connector
       - Homepage URL: https://ricohunt.com
       - Authorized Redirect URI: https://mail.zoho.com/integPlatform/connectors/ricomail/v2/redirect
    4. Note down Client ID and Client Secret
    5. Add credentials to .env file
    6. Run: python -m src.zoho_mail authorize
    7. After browser authorization, run: python -m src.zoho_mail exchange-code <code>

Important Notes:
    - This integration is READ-ONLY (no email sending capabilities)
    - Uses Server-based Applications OAuth client type
    - Data center may vary: accounts.zoho.com (global) or accounts.zoho.eu (EU)
    - Token is stored in zoho_token.json (automatically ignored by git)
    - Token refresh is automatic when expired

Usage:
    python -m src.zoho_mail authorize          # Start OAuth flow
    python -m src.zoho_mail exchange-code <code>  # Exchange auth code for token
    python -m src.zoho_mail fetch-emails       # Fetch recent emails
    python -m src.zoho_mail fetch-emails --limit 5  # Smoke test

Environment:
    ZOHO_CLIENT_ID          — OAuth client ID
    ZOHO_CLIENT_SECRET       — OAuth client secret
    ZOHO_REDIRECT_URI        — OAuth redirect URI (must match Zoho API Console exactly)
    ZOHO_ACCOUNTS_DOMAIN     — Zoho accounts domain (default: accounts.zoho.com, use accounts.zoho.eu for EU)

Scopes (read-only):
    ZohoMail.accounts.READ   — Account information
    ZohoMail.messages.READ   — Read email messages
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import secrets
import sys
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = BASE_DIR / "zoho_token.json"

# Zoho OAuth endpoints
DEFAULT_ACCOUNTS_DOMAIN = "accounts.zoho.com"
AUTH_PATH = "/oauth/v2/auth"
TOKEN_PATH = "/oauth/v2/token"

# Zoho Mail API endpoints
MAIL_API_BASE = "https://mail.zoho.com/api"

# OAuth scopes for Zoho Mail (read-only for inbox intelligence)
SCOPES = [
    "ZohoMail.accounts.READ",
    "ZohoMail.messages.READ",
]

# Token buffer - refresh before actual expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300


@dataclass
class ZohoToken:
    """OAuth token response from Zoho."""
    access_token: str
    refresh_token: str
    expires_in: int
    api_domain: str
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    obtained_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "api_domain": self.api_domain,
            "token_type": self.token_type,
        }
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        if self.obtained_at:
            data["obtained_at"] = self.obtained_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZohoToken":
        token = cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            api_domain=data.get("api_domain", ""),
            token_type=data.get("token_type", "Bearer"),
        )
        if "expires_at" in data:
            token.expires_at = datetime.fromisoformat(data["expires_at"])
        if "obtained_at" in data:
            token.obtained_at = datetime.fromisoformat(data["obtained_at"])
        return token

    def is_expired(self) -> bool:
        """Check if token is expired or needs refresh."""
        if not self.expires_at:
            return True
        expiry_buffer = self.expires_at - timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS)
        return datetime.now(timezone.utc) > expiry_buffer


@dataclass
class ZohoEmail:
    """Email message from Zoho Mail."""
    message_id: str
    subject: str
    sender: str
    to: List[str]
    date: str
    body: str
    snippet: str
    is_read: bool
    has_attachments: bool


@dataclass
class ZohoEmailFetchResult:
    """Result of email fetch operation."""
    emails: List[ZohoEmail]
    total_count: int
    fetched_at: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_client_id() -> str:
    client_id = os.getenv("ZOHO_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError(
            "ZOHO_CLIENT_ID not set. Add it to .env file from Zoho API Console."
        )
    return client_id


def _get_client_secret() -> str:
    client_secret = os.getenv("ZOHO_CLIENT_SECRET", "").strip()
    if not client_secret:
        raise RuntimeError(
            "ZOHO_CLIENT_SECRET not set. Add it to .env file from Zoho API Console."
        )
    return client_secret


def _get_redirect_uri() -> str:
    redirect_uri = os.getenv("ZOHO_REDIRECT_URI", "https://mail.zoho.com/integPlatform/connectors/ricomail/v2/redirect").strip()
    return redirect_uri


def _get_accounts_domain() -> str:
    return os.getenv("ZOHO_ACCOUNTS_DOMAIN", DEFAULT_ACCOUNTS_DOMAIN).strip()


def _get_auth_url() -> str:
    """Generate authorization URL for OAuth flow."""
    client_id = _get_client_id()
    redirect_uri = _get_redirect_uri()
    accounts_domain = _get_accounts_domain()

    scope_str = ",".join(SCOPES)
    state = secrets.token_urlsafe(16)

    params = {
        "scope": scope_str,
        "client_id": client_id,
        "response_type": "code",
        "access_type": "offline",
        "redirect_uri": redirect_uri,
        "state": state,
    }

    auth_url = f"https://{accounts_domain}{AUTH_PATH}?{urllib.parse.urlencode(params)}"
    return auth_url, state


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

def _load_token() -> Optional[ZohoToken]:
    """Load token from file if exists."""
    if not TOKEN_FILE.exists():
        return None

    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return ZohoToken.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning(f"token_load_failed: {exc}")
        return None


def _save_token(token: ZohoToken) -> None:
    """Save token to file."""
    # Set expiry timestamp if not present
    if not token.obtained_at:
        token.obtained_at = datetime.now(timezone.utc)
    if not token.expires_at:
        token.expires_at = token.obtained_at + timedelta(seconds=token.expires_in)

    TOKEN_FILE.write_text(json.dumps(token.to_dict(), indent=2), encoding="utf-8")
    logger.info("zoho_token_saved")


def _exchange_code_for_token(code: str) -> ZohoToken:
    """Exchange authorization code for access token."""
    client_id = _get_client_id()
    client_secret = _get_client_secret()
    redirect_uri = _get_redirect_uri()
    accounts_domain = _get_accounts_domain()

    token_url = f"https://{accounts_domain}{TOKEN_PATH}"

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(token_url, data=data, timeout=30)
    response.raise_for_status()

    token_data = response.json()
    token = ZohoToken(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data["expires_in"],
        api_domain=token_data.get("api_domain", ""),
        token_type=token_data.get("token_type", "Bearer"),
    )

    logger.info("zoho_token_exchanged")
    return token


def _refresh_access_token(refresh_token: str) -> ZohoToken:
    """Refresh access token using refresh token."""
    client_id = _get_client_id()
    client_secret = _get_client_secret()
    accounts_domain = _get_accounts_domain()

    token_url = f"https://{accounts_domain}{TOKEN_PATH}"

    data = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }

    response = requests.post(token_url, data=data, timeout=30)
    response.raise_for_status()

    token_data = response.json()
    token = ZohoToken(
        access_token=token_data["access_token"],
        refresh_token=refresh_token,  # Keep existing refresh token
        expires_in=token_data["expires_in"],
        api_domain=token_data.get("api_domain", ""),
        token_type=token_data.get("token_type", "Bearer"),
    )

    logger.info("zoho_token_refreshed")
    return token


def get_valid_token() -> ZohoToken:
    """Get valid access token, refreshing if necessary."""
    token = _load_token()

    if token and not token.is_expired():
        return token

    if token and token.refresh_token:
        logger.info("zoho_token_expired_refreshing")
        new_token = _refresh_access_token(token.refresh_token)
        _save_token(new_token)
        return new_token

    raise RuntimeError(
        "No valid token found. Run with --authorize to complete OAuth flow."
    )


# ---------------------------------------------------------------------------
# OAuth Callback Server
# ---------------------------------------------------------------------------

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP server to handle OAuth callback."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request for OAuth callback."""
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if "code" in query:
            code = query["code"][0]
            try:
                token = _exchange_code_for_token(code)
                _save_token(token)

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization Successful!</h1>"
                    b"<p>You can close this window and return to the terminal.</p></body></html>"
                )
                logger.info("zoho_oauth_success")
            except Exception as exc:
                logger.exception("zoho_oauth_failed")
                self.send_response(500)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>Authorization Failed</h1>"
                    f"<p>Error: {exc}</p></body></html>".encode()
                )
        else:
            error = query.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Authorization Error</h1>"
                f"<p>Error: {error}</p></body></html>".encode()
            )
            logger.error(f"zoho_oauth_error: {error}")


def _start_oauth_callback_server(port: int = 8080) -> None:
    """Start local HTTP server for OAuth callback."""
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    logger.info(f"zoho_oauth_server_started port={port}")
    server.handle_request()


def authorize() -> None:
    """Start OAuth authorization flow using Zoho Mail Connector."""
    auth_url, state = _get_auth_url()
    redirect_uri = _get_redirect_uri()

    print(f"\nOpening browser for authorization...")
    print(f"Authorization URL: {auth_url}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"\nAfter authorization, you'll be redirected to Zoho Mail Connector.")
    print(f"Copy the authorization code from the URL or use the connector interface.")
    print(f"\nFor manual code exchange, run: python -m src.zoho_mail exchange-code <code>")
    print(f"\nOpening browser...\n")

    webbrowser.open(auth_url)


# ---------------------------------------------------------------------------
# Zoho Mail API Client
# ---------------------------------------------------------------------------

class ZohoMailClient:
    """Client for Zoho Mail API operations."""

    def __init__(self, token: Optional[ZohoToken] = None):
        self.token = token or get_valid_token()
        # Force correct base URL for Zoho Mail API
        self.api_domain = "https://mail.zoho.com/api"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization."""
        return {
            "Authorization": f"Zoho-oauthtoken {self.token.access_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated API request."""
        url = f"{self.api_domain}{endpoint}"
        headers = self._get_headers()

        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=data,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_messages(
        self,
        limit: int = 50,
        start: int = 0,
        folder: str = "Inbox",
    ) -> ZohoEmailFetchResult:
        """Fetch messages from Zoho Mail."""
        # First get account ID
        accounts_result = self._make_request("GET", "/accounts")
        if not accounts_result.get("data"):
            raise RuntimeError("No accounts found")

        account_id = accounts_result["data"][0]["accountId"]

        # Get messages for the account
        params = {
            "limit": limit,
            "start": start,
        }

        result = self._make_request("GET", f"/accounts/{account_id}/messages/view", params=params)

        emails = []
        for msg_data in result.get("data", []):
            email = ZohoEmail(
                message_id=msg_data.get("messageId", ""),
                subject=msg_data.get("subject", ""),
                sender=msg_data.get("from", {}).get("address", ""),
                to=[addr.get("address", "") for addr in msg_data.get("to", [])],
                date=msg_data.get("receivedTime", ""),
                body=msg_data.get("summary", ""),
                snippet=msg_data.get("summary", "")[:200],
                is_read=msg_data.get("isRead", False),
                has_attachments=msg_data.get("hasAttachment", False),
            )
            emails.append(email)

        return ZohoEmailFetchResult(
            emails=emails,
            total_count=result.get("status", {}).get("total", len(emails)),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        """Fetch detailed message content."""
        accounts_result = self._make_request("GET", "/accounts")
        account_id = accounts_result["data"][0]["accountId"]

        params = {"messageId": message_id}
        return self._make_request("GET", f"/accounts/{account_id}/messages/view", params=params)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_authorize(args: argparse.Namespace) -> int:
    """Handle --authorize command."""
    try:
        authorize()
        print("\nAuthorization URL opened in browser.")
        print("After authorization, run: python -m src.zoho_mail exchange-code <code>")
        return 0
    except Exception as exc:
        logger.exception("authorize_failed")
        print(f"\nAuthorization failed: {exc}")
        return 1


def cmd_exchange_code(args: argparse.Namespace) -> int:
    """Handle --exchange-code command for manual code exchange."""
    if not args.code:
        print("Error: Authorization code required.")
        print("Usage: python -m src.zoho_mail exchange-code <code>")
        return 1

    try:
        token = _exchange_code_for_token(args.code)
        _save_token(token)
        print("\nAuthorization completed successfully!")
        print(f"Token saved to: {TOKEN_FILE}")
        return 0
    except Exception as exc:
        logger.exception("exchange_code_failed")
        print(f"\nCode exchange failed: {exc}")
        return 1


def cmd_fetch_emails(args: argparse.Namespace) -> int:
    """Handle --fetch-emails command."""
    try:
        client = ZohoMailClient()
        result = client.get_messages(limit=args.limit, folder=args.folder)

        print(f"\nFetched {len(result.emails)} emails (total: {result.total_count})")
        print(f"Fetched at: {result.fetched_at}\n")

        for email in result.emails:
            status = "[READ]" if email.is_read else "[UNREAD]"
            attach = "[ATTACH]" if email.has_attachments else ""
            print(f"{status} {attach} {email.date}")
            print(f"  From: {email.sender}")
            print(f"  To: {', '.join(email.to)}")
            print(f"  Subject: {email.subject}")
            print(f"  Snippet: {email.snippet}")
            print()

        return 0
    except Exception as exc:
        logger.exception("fetch_emails_failed")
        print(f"\nFailed to fetch emails: {exc}")
        return 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(
        description="Zoho Mail API integration with OAuth 2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Authorize command
    subparsers.add_parser("authorize", help="Start OAuth authorization flow")

    # Exchange code command
    exchange_parser = subparsers.add_parser("exchange-code", help="Exchange authorization code for token")
    exchange_parser.add_argument("code", help="Authorization code from Zoho")

    # Fetch emails command
    fetch_parser = subparsers.add_parser("fetch-emails", help="Fetch recent emails")
    fetch_parser.add_argument(
        "--limit", type=int, default=50, help="Number of emails to fetch (default: 50)"
    )
    fetch_parser.add_argument(
        "--folder", default="Inbox", help="Folder to fetch from (default: Inbox)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "authorize": cmd_authorize,
        "exchange-code": cmd_exchange_code,
        "fetch-emails": cmd_fetch_emails,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
