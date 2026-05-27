"""API endpoints for job link verification."""

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, validator
import re
import ipaddress

from src.services.link_verifier import LinkVerifier, LinkStatus, VerificationResult, get_link_verifier
from src.api.rate_limit import limiter


router = APIRouter(prefix="/api/v1/links", tags=["link-verification"])


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


def is_safe_url(url: str) -> bool:
    """Check if URL is safe from SSRF attacks.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is safe, False otherwise
    """
    try:
        from urllib.parse import urlparse
        
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
        
        # Block private IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    return False
        except ValueError:
            # Not an IP address, might be a hostname
            pass
        
        return True
    except Exception:
        return False


class VerifyLinkRequest(BaseModel):
    """Request model for link verification."""
    url: str
    
    @validator('url')
    def validate_url(cls, v):
        """Validate URL is safe from SSRF."""
        if not v:
            raise ValueError("URL is required")
        
        if not is_safe_url(v):
            raise ValueError("URL is not allowed (SSRF protection)")
        
        return v


class VerifyLinkResponse(BaseModel):
    """Response model for link verification."""
    status: str
    http_status: Optional[int]
    error_message: Optional[str]
    verified_at: datetime
    redirect_url: Optional[str] = None


@router.post("/verify", response_model=VerifyLinkResponse)
@limiter.limit("10/minute")  # Rate limit to prevent abuse
async def verify_link(request: Request, link_request: VerifyLinkRequest) -> VerifyLinkResponse:
    """Verify a single job link.
    
    Args:
        request: FastAPI request object
        link_request: Link verification request with URL
        
    Returns:
        Verification result with status and details
    """
    verifier = get_link_verifier()
    result = await verifier.verify_link(link_request.url)
    
    return VerifyLinkResponse(
        status=result.status.value,
        http_status=result.http_status,
        error_message=result.error_message,
        verified_at=result.verified_at,
        redirect_url=result.redirect_url,
    )


class BatchVerifyRequest(BaseModel):
    """Request model for batch link verification."""
    urls: list[str]
    
    @validator('urls')
    def validate_urls(cls, v):
        """Validate all URLs are safe from SSRF."""
        if len(v) > 10:  # Limit batch size
            raise ValueError("Maximum 10 URLs per batch")
        
        for url in v:
            if not is_safe_url(url):
                raise ValueError(f"URL '{url}' is not allowed (SSRF protection)")
        
        return v


class BatchVerifyResponse(BaseModel):
    """Response model for batch link verification."""
    results: dict[str, VerifyLinkResponse]


@router.post("/verify-batch", response_model=BatchVerifyResponse)
@limiter.limit("5/minute")  # Stricter rate limit for batch
async def verify_links_batch(request: Request, batch_request: BatchVerifyRequest) -> BatchVerifyResponse:
    """Verify multiple links in parallel.
    
    Args:
        request: FastAPI request object
        batch_request: Batch verification request with URLs
        
    Returns:
        Dictionary mapping URL to verification result
    """
    verifier = get_link_verifier()
    results_dict = await verifier.verify_links_batch(batch_request.urls)
    
    # Convert to response format
    results = {}
    for url, result in results_dict.items():
        results[url] = VerifyLinkResponse(
            status=result.status.value,
            http_status=result.http_status,
            error_message=result.error_message,
            verified_at=result.verified_at,
            redirect_url=result.redirect_url,
        )
    
    return BatchVerifyResponse(results=results)
