"""Link verification service for detecting dead/expired job links."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import httpx
import ipaddress


class LinkStatus(Enum):
    """Classification of link verification results."""
    LIVE = "live"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    REDIRECT = "redirect"
    SOURCE_ONLY = "source_only"
    NEEDS_REVIEW = "needs_review"


@dataclass
class VerificationResult:
    """Result of link verification."""
    status: LinkStatus
    http_status: Optional[int]
    error_message: Optional[str]
    verified_at: datetime
    redirect_url: Optional[str] = None


# SSRF Protection: Block private IP ranges and localhost
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),    # Private Class A
    ipaddress.ip_network("172.16.0.0/12"), # Private Class B
    ipaddress.ip_network("192.168.0.0/16"), # Private Class C
    ipaddress.ip_network("169.254.0.0/16"), # Link-local
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),      # IPv6 private
    ipaddress.ip_network("fe80::/10"),     # IPv6 link-local
]

# AWS/GCP/Azure metadata IPs
METADATA_IPS = [
    "169.254.169.254",  # AWS
    "metadata.google.internal",  # GCP
    "169.254.169.254",  # Azure
]


def _is_safe_url(url: str) -> bool:
    """Check if URL is safe from SSRF attacks.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is safe, False otherwise
    """
    try:
        from urllib.parse import urlparse
        import socket
        
        parsed = urlparse(url)
        
        # Only allow http and https
        if parsed.scheme not in ("http", "https"):
            return False
        
        # Block localhost variants
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        
        # Block metadata IPs
        if hostname in METADATA_IPS:
            return False
        
        # Block private IP ranges (including resolved hostnames)
        try:
            # First check if it's a literal IP
            ip = ipaddress.ip_address(hostname)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    return False
        except ValueError:
            # Not a literal IP, resolve hostname to check resolved IP
            try:
                # Resolve hostname to IP addresses
                resolved_ips = socket.getaddrinfo(hostname, None)
                for addrinfo in resolved_ips:
                    ip_str = addrinfo[4][0]  # Get IP from sockaddr
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        for private_range in PRIVATE_IP_RANGES:
                            if ip in private_range:
                                return False
                    except ValueError:
                        continue
            except (socket.gaierror, socket.error, OSError):
                # DNS resolution failed, treat as unsafe
                return False
        
        return True
    except Exception:
        return False


class LinkVerifier:
    """Service for verifying job links and detecting dead pages."""
    
    # Dead page patterns
    JOBTED_404_PATTERNS = [
        "404 Not Found",
        "The requested page could not be found",
    ]
    
    INDEED_DEAD_PATTERNS = [
        "We can't find this page",
    ]
    
    # Dead HTTP status codes
    DEAD_STATUS_CODES = {404, 410, 451}
    
    # Server error status codes (5xx)
    SERVER_ERROR_CODES = {500, 502, 503, 504}
    
    # Client error status codes that indicate issues (non-dead)
    CLIENT_ERROR_CODES = {403, 429}
    
    # Verification timeout in seconds
    TIMEOUT = 10
    
    # Maximum redirects to follow
    MAX_REDIRECTS = 5
    
    # User agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    ]
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def verify_link(self, url: str) -> VerificationResult:
        """Verify a single job link.
        
        Args:
            url: The job link to verify
            
        Returns:
            VerificationResult with status and details
        """
        if not url:
            return VerificationResult(
                status=LinkStatus.SOURCE_ONLY,
                http_status=None,
                error_message="No URL provided",
                verified_at=datetime.utcnow(),
            )
        
        try:
            client = await self._get_client()
            headers = {"User-Agent": self.USER_AGENTS[0]}
            
            # Manually follow redirects with SSRF validation at each step
            current_url = url
            redirect_count = 0
            
            while redirect_count <= self.MAX_REDIRECTS:
                response = await client.get(current_url, headers=headers, follow_redirects=False)
                
                # Check for dead status codes
                if response.status_code in self.DEAD_STATUS_CODES:
                    return VerificationResult(
                        status=LinkStatus.EXPIRED,
                        http_status=response.status_code,
                        error_message=f"HTTP {response.status_code}",
                        verified_at=datetime.utcnow(),
                    )
                
                # Check for server errors
                if response.status_code in self.SERVER_ERROR_CODES:
                    return VerificationResult(
                        status=LinkStatus.NEEDS_REVIEW,
                        http_status=response.status_code,
                        error_message=f"Server error: HTTP {response.status_code}",
                        verified_at=datetime.utcnow(),
                    )
                
                # Check for client errors that indicate issues
                if response.status_code in self.CLIENT_ERROR_CODES:
                    return VerificationResult(
                        status=LinkStatus.NEEDS_REVIEW,
                        http_status=response.status_code,
                        error_message=f"Client error: HTTP {response.status_code}",
                        verified_at=datetime.utcnow(),
                    )
                
                # Check for redirects
                if 300 <= response.status_code < 400:
                    redirect_url = response.headers.get("location")
                    if not redirect_url:
                        return VerificationResult(
                            status=LinkStatus.NEEDS_REVIEW,
                            http_status=response.status_code,
                            error_message="Redirect without location header",
                            verified_at=datetime.utcnow(),
                        )
                    
                    # Resolve relative redirects before SSRF validation
                    from urllib.parse import urljoin
                    redirect_url = urljoin(current_url, redirect_url)
                    
                    # Validate redirect URL for SSRF
                    if not _is_safe_url(redirect_url):
                        return VerificationResult(
                            status=LinkStatus.BLOCKED,
                            http_status=response.status_code,
                            error_message="Redirect to blocked URL (SSRF protection)",
                            verified_at=datetime.utcnow(),
                            redirect_url=redirect_url,
                        )
                    
                    current_url = redirect_url
                    redirect_count += 1
                    continue
                
                # Not a redirect, check content
                if response.status_code == 200:
                    content = response.text
                    if self._is_dead_page(content, url):
                        return VerificationResult(
                            status=LinkStatus.EXPIRED,
                            http_status=response.status_code,
                            error_message="Dead page pattern detected",
                            verified_at=datetime.utcnow(),
                        )
                
                # Link is live
                return VerificationResult(
                    status=LinkStatus.LIVE,
                    http_status=response.status_code,
                    error_message=None,
                    verified_at=datetime.utcnow(),
                )
            
            # Too many redirects
            return VerificationResult(
                status=LinkStatus.BLOCKED,
                http_status=None,
                error_message="Too many redirects (possible redirect loop)",
                verified_at=datetime.utcnow(),
            )
            
        except httpx.TimeoutException:
            return VerificationResult(
                status=LinkStatus.NEEDS_REVIEW,
                http_status=None,
                error_message="Request timeout",
                verified_at=datetime.utcnow(),
            )
        except httpx.ConnectError:
            return VerificationResult(
                status=LinkStatus.NEEDS_REVIEW,
                http_status=None,
                error_message="Connection failed",
                verified_at=datetime.utcnow(),
            )
        except Exception as e:
            return VerificationResult(
                status=LinkStatus.NEEDS_REVIEW,
                http_status=None,
                error_message=str(e),
                verified_at=datetime.utcnow(),
            )
    
    def _is_dead_page(self, content: str, url: str) -> bool:
        """Check if page content indicates a dead page.
        
        Args:
            content: HTML content of the page
            url: The URL being checked
            
        Returns:
            True if page appears to be dead
        """
        content_lower = content.lower()
        
        # Check Jobted patterns
        if "jobted" in url.lower():
            for pattern in self.JOBTED_404_PATTERNS:
                if pattern.lower() in content_lower:
                    return True
        
        # Check Indeed patterns
        if "indeed" in url.lower():
            for pattern in self.INDEED_DEAD_PATTERNS:
                if pattern.lower() in content_lower:
                    return True
        
        return False
    
    async def verify_links_batch(self, urls: list[str]) -> dict[str, VerificationResult]:
        """Verify multiple links in parallel.
        
        Args:
            urls: List of URLs to verify
            
        Returns:
            Dictionary mapping URL to VerificationResult
        """
        tasks = [self.verify_link(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return dict(zip(urls, results))


# Singleton instance
_link_verifier: Optional[LinkVerifier] = None


def get_link_verifier() -> LinkVerifier:
    """Get singleton link verifier instance."""
    global _link_verifier
    if _link_verifier is None:
        _link_verifier = LinkVerifier()
    return _link_verifier
