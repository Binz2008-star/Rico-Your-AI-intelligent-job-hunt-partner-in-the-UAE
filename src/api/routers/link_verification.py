"""API endpoints for job link verification."""

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from src.services.link_verifier import LinkVerifier, LinkStatus, VerificationResult, get_link_verifier


router = APIRouter(prefix="/api/v1/links", tags=["link-verification"])


class VerifyLinkRequest(BaseModel):
    """Request model for link verification."""
    url: str


class VerifyLinkResponse(BaseModel):
    """Response model for link verification."""
    status: str
    http_status: Optional[int]
    error_message: Optional[str]
    verified_at: datetime
    redirect_url: Optional[str] = None


@router.post("/verify", response_model=VerifyLinkResponse)
async def verify_link(request: VerifyLinkRequest) -> VerifyLinkResponse:
    """Verify a single job link.
    
    Args:
        request: Link verification request with URL
        
    Returns:
        Verification result with status and details
    """
    verifier = get_link_verifier()
    result = await verifier.verify_link(request.url)
    
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


class BatchVerifyResponse(BaseModel):
    """Response model for batch link verification."""
    results: dict[str, VerifyLinkResponse]


@router.post("/verify-batch", response_model=BatchVerifyResponse)
async def verify_links_batch(request: BatchVerifyRequest) -> BatchVerifyResponse:
    """Verify multiple links in parallel.
    
    Args:
        request: Batch verification request with URLs
        
    Returns:
        Dictionary mapping URL to verification result
    """
    verifier = get_link_verifier()
    results_dict = await verifier.verify_links_batch(request.urls)
    
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
