"""API endpoints for job link verification."""

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, validator

from src.services.link_verifier import LinkVerifier, LinkStatus, VerificationResult, get_link_verifier, _is_safe_url
from src.api.rate_limit import limiter


router = APIRouter(prefix="/api/v1/links", tags=["link-verification"])


class VerifyLinkRequest(BaseModel):
    """Request model for link verification."""
    url: str
    
    @validator('url')
    def validate_url(cls, v):
        """Validate URL is safe from SSRF."""
        if not v:
            raise ValueError("URL is required")
        
        if not _is_safe_url(v):
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
            if not _is_safe_url(url):
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
