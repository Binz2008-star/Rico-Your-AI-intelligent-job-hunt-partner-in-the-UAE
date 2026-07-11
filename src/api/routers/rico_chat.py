"""
src/api/routers/rico_chat.py
HTTP adapters that expose Rico AI flows through the layered API.
Rico internals are not modified — this is a pure routing shim.

Routes:
  POST /api/v1/rico/chat                        natural-language chat  (JWT required)
  GET  /api/v1/rico/profile                     user profile           (JWT required)
  GET  /api/v1/rico/settings/saved-searches     list saved searches    (JWT required)
  POST /api/v1/rico/settings/saved-searches     save a search          (JWT required)
  DELETE /api/v1/rico/settings/saved-searches/{id} delete saved search (JWT required)
  GET    /api/v1/rico/chat/history              conversation history   (JWT required)
  DELETE /api/v1/rico/chat/history              clear chat history     (JWT required)
  POST /api/v1/rico/feedback                    feedback on matches    (JWT required)
  GET  /api/v1/rico/openai-smoke                AI runtime probe       (JWT required)
  POST /api/v1/rico/upload-cv                   CV file upload + parsing
  GET  /api/v1/rico/metrics                     Prometheus metrics
  POST /api/v1/rico/webhooks/telegram           Telegram bot webhook (called by Telegram)
  POST /api/v1/rico/webhooks/jotform            Jotform onboarding webhook (called by Jotform)
  POST /api/v1/rico/webhooks/github             GitHub webhook (push, PR, issues, ping)
  POST /api/v1/rico/chat/public                 Public chat (no JWT, session-based, rate-limited)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional
from functools import wraps

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.admin_guard import require_admin_user
from src.api.deps import get_current_user, get_current_user_id
from src.api.public_identity import (
    is_safe_public_session_id,
    is_valid_public_user_id,
    normalize_public_email,
)
from src.api.rate_limit import LIMIT_ADMIN, LIMIT_CHAT, LIMIT_PROFILE, LIMIT_UPLOAD, LIMIT_WEBHOOK, limiter
from src.repositories import onboarding_repo, profile_repo
from src.repositories.learning_repo import get_learning_repository
from src.agent.responses.schema import RicoResponse, build_error_response, _generate_debug_id
from src.agent.runtime import agent_runtime
from src.models.onboarding import ONBOARDING_COMPLETED, ONBOARDING_IN_PROGRESS
from src.rico_agent import RicoAgent
from src.rico_chat_api import generate_error_ref
from src.rico_env import get_ai_provider
from src.rico_hf_client import generate_text, is_available as hf_ok
from src.rico_openai_agent import RicoOpenAIAgent
from src.services.matching_guardrails import build_matching_guardrail_warnings
from src.services.cv_quality_warnings import build_cv_quality_warnings
from src.services.settings_service import get_settings
from src.rico_openai_runtime import call_openai_minimal
from src.schemas.actions import ActionRequest, ActionResponse, ExecutePermissionActionRequest
from src.schemas.chat import RicoChatResponse, RicoSessionContext
from src.services import chat_service
from src.mutation_guard import MutationConfirmationGuard, MutationResult

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_MUTATION_CONFIRMATION_GUARD = MutationConfirmationGuard()

# Constants
_UNSAFE_CHARS_RE = re.compile("[<>\"';\\x00-\\x1f\\x7f\\u202a-\\u202e\\u2066-\\u2069]")
_PDF_MAGIC = b"%PDF"
# Upload size limits, by file kind. Documents (CV/cover-letter/etc.) can carry
# embedded fonts and high-res page images, so they get a generous cap; image
# screenshots are smaller by nature. Both keep a hard safety cap — never unlimited.
_MAX_DOC_BYTES = 25 * 1024 * 1024     # 25 MB — PDF / DOC / DOCX / TXT documents
_MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB — PNG / JPG / WebP / GIF / BMP images
_MAX_UPLOAD_BYTES = _MAX_DOC_BYTES    # coarse hard cap; nothing may exceed this
_MB = 1024 * 1024


def _upload_limit_for(file_format: str) -> int:
    """Per-kind size cap in bytes for an uploaded file (by magic-byte format)."""
    return _MAX_IMAGE_BYTES if file_format == "image" else _MAX_DOC_BYTES


def _too_large_message(limit_bytes: int, is_image: bool) -> str:
    """User-friendly (non-technical) oversize message; never blames CV parsing."""
    mb = limit_bytes // _MB
    if is_image:
        return (
            f"This image is too large. You can upload screenshots up to {mb}MB. "
            "Please take a smaller screenshot or compress the image."
        )
    return (
        f"This file is too large. You can upload CV documents up to {mb}MB. "
        "If your file is larger, please compress it or upload a lighter PDF version."
    )

router = APIRouter(prefix="/api/v1/rico", tags=["rico"])


def _is_production() -> bool:
    """Check if running in production environment."""
    return (os.getenv("RICO_ENV") or os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower() in {
        "prod",
        "production",
    }


# ============================================================================
# Pydantic Models
# ============================================================================

class RicoChatRequest(BaseModel):
    """Authenticated chat request - user_id derived from JWT."""
    message: str = Field(..., max_length=4096)
    operation_id: str | None = Field(None, min_length=8, max_length=80)
    language: str | None = Field(None, pattern="^(en|ar)$")

    @field_validator("message")
    @classmethod
    def non_empty_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class RicoPublicChatRequest(BaseModel):
    """Public chat request with session tracking or email-based user identification."""
    message: str = Field(..., max_length=2048)
    session_id: str | None = Field(None, min_length=8, max_length=64)
    email: str | None = Field(None, max_length=254)
    operation_id: str | None = Field(None, min_length=8, max_length=80)
    language: str | None = Field(None, pattern="^(en|ar)$")

    @field_validator("session_id")
    @classmethod
    def safe_session_id(cls, v: str) -> str:
        if v and not is_safe_public_session_id(v):
            raise ValueError("Session ID must be 8-64 chars: letters, numbers, hyphen, or underscore")
        return v

    @field_validator("email")
    @classmethod
    def safe_email(cls, v: str | None) -> str | None:
        return normalize_public_email(v)

    @field_validator("message")
    @classmethod
    def non_empty_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class SavedSearchRequest(BaseModel):
    """Request to save a search query."""
    query: str = Field(..., min_length=1, max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def non_empty_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class SavedSearchResponse(BaseModel):
    """Response for saved search operations."""
    id: str | None = None
    query: str
    filters: dict[str, Any]
    created_at: str | None = None
    status: str = "saved"


class FeedbackRequest(BaseModel):
    """Feedback on job matches."""
    job_id: str = Field(..., min_length=1, max_length=100)
    feedback_type: str = Field(..., pattern="^(positive|negative|neutral)$")
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=500)


class ProfileResponse(BaseModel):
    """Typed profile response."""
    profile_exists: bool
    user_id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    telegram_username: str | None = None
    target_roles: list[str] | None = None
    preferred_cities: list[str] | None = None
    salary_expectation_aed: int | None = None
    minimum_salary_aed: int | None = None
    skills: list[str] | None = None
    industries: list[str] | None = None
    visa_status: str | None = None
    notice_period: str | None = None
    years_experience: float | None = None
    current_role: str | None = None
    current_company: str | None = None
    linkedin_url: str | None = None
    completeness_score: float | None = None
    warnings: list[dict[str, str]] = Field(default_factory=list)


class ConfirmCVProfileRequest(BaseModel):
    """Request to confirm and save CV profile preview."""
    preview: dict[str, Any] = Field(..., description="Profile preview data to confirm")
    filename: str = Field(..., description="Original CV filename")
    doc_type: str = Field(default="cv", description="Detected document type from upload step")
    upload_id: str | None = Field(
        default=None,
        description=(
            "Opaque id from the matching upload-cv response. Resolved server-side "
            "against the caller's own server-derived identity to recover the "
            "server-computed content hash, byte count, and parsed text for this "
            "exact upload — never trusted/recomputed from client-supplied values."
        ),
    )



class MetricsResponse(BaseModel):
    """Prometheus-style metrics response."""
    uptime_seconds: float
    total_requests: int
    avg_response_time_ms: float
    active_sessions: int
    cache_hit_rate: float
    timestamp: str


# ============================================================================
# Helper Functions
# ============================================================================

def _safe_filename(name: str | None) -> str:
    """Strip path traversal and unsafe chars from an uploaded filename."""
    if not name:
        return "upload"
    name = os.path.basename(name)
    name = _UNSAFE_CHARS_RE.sub("", name)
    return name.strip() or "upload"


def _classification_response(classification: Any, filename: str) -> dict[str, Any]:
    """Build the standard 'classified' response for non-CV document types."""
    pct = int(classification.confidence * 100)
    label = classification.display_label
    # Top two types for display, sorted by score descending.
    scores = classification.confidence_scores
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    score_lines = "\n".join(
        f"{'  '}{'·'} {_display_for_type(t)}: {int(s * 100)}%"
        for t, s in ranked[:3]
        if s > 0.05
    )
    msg = (
        f"I detected this file as:\n\n"
        f"**{label}** ({pct}%)\n\n"
        f"{score_lines}\n\n"
        "What would you like me to do with it?"
    )
    # CAREER-OS-04: attach a first-class attachment_analysis envelope so the chat UI
    # can render what the file is. Read-only description — never mutates profile/settings.
    try:
        from src.services.attachment_analysis_factory import build_attachment_analysis_dict
        analysis = build_attachment_analysis_dict(classification, filename)
        agentic_ui: dict[str, Any] | None = {"attachment_analysis": [analysis]}
    except Exception:  # pragma: no cover - analysis is additive; never break upload
        logger.exception("attachment_analysis_build_failed filename=%s", filename)
        agentic_ui = None

    response: dict[str, Any] = {
        "ok": True,
        "status": "classified",
        "filename": filename,
        **classification.to_dict(),
        "message": msg,
    }
    if agentic_ui is not None:
        response["agentic_ui"] = agentic_ui
    return response


def _display_for_type(doc_type: str) -> str:
    _MAP = {
        "cv": "Resume / CV", "job_description": "Job Description",
        "cover_letter": "Cover Letter", "offer_letter": "Offer Letter",
        "contract": "Employment Contract", "recruiter_email": "Recruiter Email",
        "certificate": "Certificate / License", "identity_document": "Identity Document",
        "company_profile": "Company Profile", "invoice": "Invoice",
        "image": "Image", "unknown": "Document",
    }
    return _MAP.get(doc_type, doc_type.replace("_", " ").title())


# Thin wrappers keep the router on one adapter path while preserving stable patch points.
def get_profile(user_id: str):
    return profile_repo.get_profile(user_id)


def upsert_profile(user_id: str, updates: dict[str, Any], cv_text: str | None = None, require_db: bool = False):
    return profile_repo.upsert_profile(
        user_id=user_id, updates=updates, cv_text=cv_text, require_db=require_db
    )


def list_saved_searches(user_id: str, limit: int = 20):
    return profile_repo.list_saved_searches(user_id, limit=limit)


def save_search(user_id: str, query: str, filters: dict[str, Any]):
    return profile_repo.save_search(user_id, query, filters)


def delete_search(user_id: str, search_id: str):
    return profile_repo.delete_search(user_id, search_id)


def mark_onboarding_complete(user_id: str) -> None:
    onboarding_repo.mark_onboarding_complete(user_id)




def _resolve_upload_user_id(
    request: Request,
    query_user_id: str | None,
    form_user_id: str | None,
) -> str:
    """Resolve user ID for CV upload, allowing authenticated or validated public sessions."""
    try:
        return get_current_user_id(request)
    except HTTPException as auth_exc:
        if getattr(request.state, "access_token_present", False):
            logger.warning(
                "upload_identity_auth_failed path=%s detail=%s",
                request.url.path,
                auth_exc.detail,
            )
            raise auth_exc

    user_id = (query_user_id or form_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")

    if not is_valid_public_user_id(user_id):
        raise HTTPException(
            status_code=401,
            detail="Authentication or valid public session required"
        )

    return user_id


def _validate_jotform_secret(request: Request) -> None:
    """Validate Jotform webhook secret; fail closed in production."""
    webhook_secret = os.getenv("JOTFORM_WEBHOOK_SECRET", "").strip()

    if not webhook_secret:
        if _is_production():
            logger.error("jotform_webhook: JOTFORM_WEBHOOK_SECRET missing in production")
            raise HTTPException(status_code=503, detail="Webhook not configured")
        logger.warning("jotform_webhook: JOTFORM_WEBHOOK_SECRET missing; allowing dev request")
        return

    # Accept secret only from headers — never from query params (they appear in server logs,
    # proxy logs, and browser history, making them an easy credential leak vector).
    provided = (
        request.headers.get("X-Jotform-Signature")
        or request.headers.get("X-Webhook-Secret")
        or ""
    )

    if not provided or not secrets.compare_digest(provided, webhook_secret):
        logger.warning("jotform_webhook: missing or invalid secret")
        raise HTTPException(status_code=403, detail="Invalid or missing webhook secret")


def _validate_telegram_secret(request: Request) -> None:
    """Validate Telegram webhook secret token; fail closed in production."""
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

    if not webhook_secret:
        if _is_production():
            logger.error("telegram_webhook: TELEGRAM_WEBHOOK_SECRET missing in production")
            raise HTTPException(status_code=503, detail="Webhook not configured")
        logger.warning("telegram_webhook: TELEGRAM_WEBHOOK_SECRET missing; allowing dev request")
        return

    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not provided or not secrets.compare_digest(provided, webhook_secret):
        logger.warning("telegram_webhook: missing or invalid secret")
        raise HTTPException(status_code=403, detail="Invalid or missing webhook secret")


def _extract_roles_from_cv_text(cv_text: str) -> list[str]:
    """Extract job titles from CV text using role patterns."""
    if not cv_text:
        return []

    roles = set()
    text_lower = cv_text.lower()

    # Pattern 1: Common role title patterns (Senior X, X Manager, etc.)
    role_patterns = [
        r"(?:senior|lead|principal|staff|junior|mid)?\s*(?:manager|engineer|developer|architect|analyst|consultant|specialist|director|coordinator|officer)",
        r"(?:operations|environmental|hse|qhse|ehs|safety|quality|compliance|sustainability)\s*(?:manager|lead|officer|specialist|coordinator)",
    ]

    for pattern in role_patterns:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            role = match.group(0).strip().title()
            if len(role.split()) <= 4:  # Reasonable role length
                roles.add(role)

    # Pattern 2: Extract from experience section lines
    lines = cv_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Look for lines that look like job titles (capitalized, no numbers at start)
        if re.match(r'^[A-Z][A-Za-z\s&/+-]{3,50}$', line):
            # Filter out common non-role lines
            skip_keywords = {'summary', 'experience', 'education', 'skills', 'certifications', 'languages', 'contact', 'profile'}
            words = line.lower().split()
            if not any(word in skip_keywords for word in words):
                roles.add(line.strip())

    return sorted(list(roles))[:5]  # Return top 5 roles


def _webhook_handler(event_name: str):
    """Decorator to standardize webhook error handling.

    All unhandled exceptions return 500 so the webhook provider retries.
    HTTPException is re-raised as-is (auth 403, validation 422, etc.).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.exception("%s_webhook_error: %s", event_name, e)
                raise HTTPException(status_code=500, detail="Webhook processing error")
        return wrapper
    return decorator


def _strip_internal_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Strip internal debug fields from responses to prevent leakage."""
    internal_fields = {
        "internal_debug", "raw_prompt", "system_prompt", "full_context",
        "debug_info", "internal_state", "agent_trace", "llm_trace"
    }
    return {k: v for k, v in data.items() if k not in internal_fields}


# ============================================================================
# Metrics (simple in-memory, replace with Prometheus in production)
# ============================================================================

class MetricsCollector:
    """Simple metrics collector - replace with Prometheus in production."""
    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.request_count = 0
        self.total_response_time = 0.0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_request(self, duration_ms: float):
        with self._lock:
            self.request_count += 1
            self.total_response_time += duration_ms

    def record_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self._lock:
            self.cache_misses += 1

    @property
    def avg_response_time_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_response_time / self.request_count

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

_metrics = MetricsCollector()


# ============================================================================
# Profile Endpoints
# ============================================================================

@router.get("/profile", response_model=ProfileResponse)
def rico_get_profile(request: Request) -> ProfileResponse:
    """Get user profile with completeness score."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    profile = get_profile(user_id)

    if profile is None:
        _metrics.record_request((time.time() - start_time) * 1000)
        return ProfileResponse(profile_exists=False, email=user_id)

    # A signup-shell user has a row in rico_users but no career data in the
    # profile JSONB.  They should still be redirected to onboarding.
    from src.services.profile_context_resolver import (
        has_career_profile_data,
        resolve_profile_context as _svc_resolve,
    )
    _svc_ctx = _svc_resolve(user_id, profile)
    if not has_career_profile_data(_svc_ctx):
        _metrics.record_request((time.time() - start_time) * 1000)
        return ProfileResponse(profile_exists=False, email=user_id)

    # completeness_score lives only on the agent context resolver's ProfileContext,
    # not on the service resolver's — fetch it separately.
    from src.agent.context.resolver import resolve_profile_context
    agent_ctx = resolve_profile_context(user_id)
    settings = get_settings(user_id=user_id)

    response = ProfileResponse(
        profile_exists=True,
        user_id=user_id,
        name=getattr(profile, "name", None),
        email=user_id,
        phone=getattr(profile, "phone", None),
        telegram_username=getattr(profile, "telegram_username", None),
        target_roles=getattr(profile, "target_roles", None),
        preferred_cities=getattr(profile, "preferred_cities", None),
        salary_expectation_aed=getattr(profile, "salary_expectation_aed", None),
        minimum_salary_aed=getattr(profile, "minimum_salary_aed", None),
        skills=getattr(profile, "skills", None),
        industries=getattr(profile, "industries", None),
        visa_status=getattr(profile, "visa_status", None),
        notice_period=getattr(profile, "notice_period", None),
        years_experience=getattr(profile, "years_experience", None),
        current_role=getattr(profile, "current_role", None),
        current_company=getattr(profile, "current_company", None),
        linkedin_url=getattr(profile, "linkedin_url", None),
        completeness_score=agent_ctx.completeness_score,
        warnings=build_matching_guardrail_warnings(
            settings=settings,
            profile=profile,
        ),
    )

    _metrics.record_request((time.time() - start_time) * 1000)
    return response


# ============================================================================
# Saved Search Endpoints
# ============================================================================

@router.get("/settings/saved-searches")
def rico_list_saved_searches(request: Request) -> dict[str, Any]:
    """List all saved searches for the authenticated user."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    rows = list_saved_searches(user_id)
    searches = []
    for row in rows:
        r = dict(row)
        if "created_at" in r and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        searches.append(r)

    _metrics.record_request((time.time() - start_time) * 1000)
    return {"searches": searches, "total": len(searches)}


@router.post("/settings/saved-searches", status_code=201, response_model=SavedSearchResponse)
def rico_create_saved_search(request: Request, body: SavedSearchRequest) -> SavedSearchResponse:
    """Save a new search query."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    search_id = save_search(user_id, body.query, body.filters)

    _metrics.record_request((time.time() - start_time) * 1000)
    return SavedSearchResponse(
        id=str(search_id) if search_id is not None else None,
        query=body.query,
        filters=body.filters,
        status="saved"
    )


@router.delete("/settings/saved-searches/{search_id}", status_code=204)
def rico_delete_saved_search(request: Request, search_id: str) -> None:
    """Delete a saved search by ID."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    deleted = delete_search(user_id, search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found")

    _metrics.record_request((time.time() - start_time) * 1000)


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.post("/chat", response_model=RicoChatResponse)
@limiter.limit(LIMIT_CHAT)
def rico_chat(request: Request, payload: RicoChatRequest) -> RicoChatResponse:
    """Authenticated chat endpoint."""
    start_time = time.time()
    request_ref = generate_error_ref()
    try:
        user = get_current_user(request)
        ctx = RicoSessionContext.for_authenticated(user["email"])

        logger.info(
            "chat_request user=%s message_len=%d request_ref=%s",
            ctx.user_id,
            len(payload.message),
            request_ref,
        )

        result = chat_service.send_message(
            ctx=ctx,
            message=payload.message,
            operation_id=payload.operation_id,
            language=payload.language,
        )

        logger.info(
            "chat_response user=%s intent=%s matches=%d request_ref=%s",
            ctx.user_id,
            result.get("intent", "unknown"),
            len(result.get("matches", [])),
            request_ref,
        )

        _metrics.record_request((time.time() - start_time) * 1000)
        return RicoChatResponse(**result, trace_id=request_ref)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "chat_error user=%s message_len=%d error_type=%s error=%s request_ref=%s",
            ctx.user_id if "ctx" in locals() else "unknown",
            len(payload.message) if "payload" in locals() else 0,
            type(exc).__name__,
            str(exc) or repr(exc),
            request_ref,
        )
        _metrics.record_request((time.time() - start_time) * 1000)
        error_response = build_error_response(
            f"I couldn't process your request. Reference: {request_ref}. Please try again or rephrase your message.",
            log_exc=exc,
            user_id=ctx.user_id if "ctx" in locals() else "unknown",
        )
        error_response["error_ref"] = request_ref
        return RicoChatResponse(**error_response, trace_id=request_ref)


@router.post("/chat/stream")
@limiter.limit(LIMIT_CHAT)
def rico_chat_stream(request: Request, payload: RicoChatRequest) -> StreamingResponse:
    """Authenticated SSE streaming chat — yields tokens as they arrive from the AI.

    Response: text/event-stream
    Each SSE event is one of:
      data: {"type":"token","text":"<chunk>"}
      data: {"type":"done","response":{ ...full RicoChatResponse fields... }}
      data: {"type":"error","message":"<msg>"}
    """
    import json as _json
    from src.rico_openai_runtime import call_openai_stream
    from src.rico_chat_api import RicoChatAPI
    from src.repositories.profile_repo import get_profile

    try:
        user = get_current_user(request)
    except HTTPException as exc:
        def _err():
            yield f'data: {_json.dumps({"type":"error","message":"Unauthorized"})}\n\n'
        return StreamingResponse(_err(), media_type="text/event-stream")

    user_id = user["email"]
    ctx = RicoSessionContext.for_authenticated(user_id)

    def _event_stream():
        try:
            # For non-conversational intents (job search, CV ops) fall back to
            # the full JSON response so structured data (job cards, profile preview)
            # arrives correctly. Only pure conversational replies are streamed.
            from src.services.chat_service import _intent_router  # type: ignore[attr-defined]
            profile = get_profile(user_id)
            decision = _intent_router.route(
                message=payload.message,
                user_id=user_id,
                profile_context_present=profile is not None,
            )
            if not decision.should_use_ai:
                # Non-streaming path: emit full response as a single "done" event
                result = chat_service.send_message(ctx=ctx, message=payload.message, language=payload.language)
                yield f'data: {_json.dumps({"type":"done","response":result})}\n\n'
                return

            # Streaming AI path
            api = RicoChatAPI(persist=ctx.can_persist_profile)
            user_context = api._build_openai_context(profile, user_id=user_id)
            profile_context_str = (
                _json.dumps(user_context, ensure_ascii=False)
                if user_context else None
            )
            conversation_history = user_context.get("conversation_history", [])
            from src.rico_env import get_ai_provider
            provider = get_ai_provider()

            full_text = []
            for chunk in call_openai_stream(
                payload.message,
                profile_context=profile_context_str,
                provider=provider,
                conversation_history=conversation_history,
                language=payload.language,
            ):
                full_text.append(chunk)
                yield f'data: {_json.dumps({"type":"token","text":chunk})}\n\n'

            # Persist the final assembled message
            assembled = "".join(full_text)
            api._append_chat(user_id, "user", payload.message)
            api._append_chat(user_id, "assistant", assembled)

            yield f'data: {_json.dumps({"type":"done","response":{"message":assembled,"type":"conversational","response_source":"stream"}})}\n\n'
        except Exception as exc:
            logger.exception("chat_stream_error user=%s", user_id)
            yield f'data: {_json.dumps({"type":"error","message":"Stream error. Please try again."})}\n\n'

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/stream/public")
@limiter.limit("10/minute")
def rico_chat_stream_public(request: Request, payload: RicoPublicChatRequest) -> StreamingResponse:
    """Unauthenticated SSE streaming chat for public/guest users."""
    import json as _json
    from src.rico_openai_runtime import call_openai_stream
    from src.rico_chat_api import RicoChatAPI
    from src.repositories.profile_repo import get_profile
    from src.api.public_identity import is_safe_public_session_id

    session_id = payload.session_id or ""
    if not session_id or not is_safe_public_session_id(session_id):
        def _err():
            yield f'data: {_json.dumps({"type":"error","message":"Invalid session."})}\n\n'
        return StreamingResponse(_err(), media_type="text/event-stream")

    user_id = f"public:{session_id}"
    ctx = RicoSessionContext.for_public(user_id)

    def _event_stream():
        try:
            from src.services.chat_service import _intent_router  # type: ignore[attr-defined]
            profile = get_profile(user_id)
            decision = _intent_router.route(
                message=payload.message,
                user_id=user_id,
                profile_context_present=profile is not None,
            )
            # Only take the legacy (non-streaming) path when the user has a profile.
            # When profile is None the legacy classifier loops back to the onboarding
            # welcome on every turn (no profile to persist for public sessions).
            # Fall through to the AI streaming path so profileless guests get real replies.
            if not decision.should_use_ai and profile is not None:
                result = chat_service.send_message(ctx=ctx, message=payload.message, language=payload.language)
                yield f'data: {_json.dumps({"type":"done","response":result})}\n\n'
                return

            api = RicoChatAPI(persist=False)
            user_context = api._build_openai_context(profile, user_id=user_id)
            profile_context_str = (
                _json.dumps(user_context, ensure_ascii=False) if user_context else None
            )
            conversation_history = user_context.get("conversation_history", [])
            from src.rico_env import get_ai_provider
            provider = get_ai_provider()

            full_text = []
            for chunk in call_openai_stream(
                payload.message,
                profile_context=profile_context_str,
                provider=provider,
                conversation_history=conversation_history,
                language=payload.language,
            ):
                full_text.append(chunk)
                yield f'data: {_json.dumps({"type":"token","text":chunk})}\n\n'

            assembled = "".join(full_text)
            api._append_chat(user_id, "user", payload.message)
            api._append_chat(user_id, "assistant", assembled)
            yield f'data: {_json.dumps({"type":"done","response":{"message":assembled,"type":"conversational","response_source":"stream"}})}\n\n'
        except Exception:
            logger.exception("chat_stream_public_error user=%s", user_id)
            yield f'data: {_json.dumps({"type":"error","message":"Stream error. Please try again."})}\n\n'

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/public", response_model=RicoChatResponse)
@limiter.limit("10/minute")
def rico_chat_public(request: Request, payload: RicoPublicChatRequest) -> RicoChatResponse:
    """Unauthenticated chat for landing page visitors.

    Supports two user identification modes:
    - session_id: for anonymous visitors (user_id = public:{session_id})
    - email: for users who completed Jotform onboarding (user_id = email)
    """
    start_time = time.time()
    request_ref = generate_error_ref()

    # Validate that either session_id or email is provided
    if not payload.email and not payload.session_id:
        raise HTTPException(status_code=422, detail="Either session_id or email must be provided")

    try:
        # Build session context: email-identified users can persist profile; anonymous cannot
        if payload.email:
            from src.repositories.users_repo import get_user_by_email

            registered = get_user_by_email(payload.email)
            # Canonicalize to the stored email for a registered user so usage counting and
            # profile persistence use the same identity key as the authenticated /chat path
            # (and so casing/whitespace variants can't mint a fresh usage bucket).
            email_identity = registered.email if registered else payload.email
            ctx = RicoSessionContext(
                user_id=email_identity,
                auth_type="public",
                can_persist_profile=True,
                can_view_private_jobs=False,
                rate_limit_tier="standard",
            )
            # A registered user must not dodge their monthly AI-message cap by routing through
            # the public endpoint with their email. Enforce the same cap the authenticated
            # /chat path applies. auth_type stays "public" deliberately: the email is unverified
            # (no JWT), so we must NOT grant authenticated-only privileges (private-job
            # visibility, account/subscription disclosure) on the strength of an unverified
            # email — only the usage limit is applied here.
            if registered:
                from src.services.subscription_gating import (
                    check_ai_message_allowed_for_user,
                )

                gate = check_ai_message_allowed_for_user(email_identity)
                if gate and not gate.allowed:
                    _metrics.record_request((time.time() - start_time) * 1000)
                    return RicoChatResponse(
                        **_strip_internal_fields(gate.to_response()),
                        trace_id=request_ref,
                    )
        else:
            ctx = RicoSessionContext.for_public(payload.session_id[:64])

        logger.info(
            "chat_public_request user=%s message_len=%d request_ref=%s",
            ctx.user_id,
            len(payload.message),
            request_ref,
        )

        result = chat_service.send_message(
            ctx=ctx,
            message=payload.message,
            operation_id=payload.operation_id,
            language=payload.language,
        )

        logger.info(
            "chat_public_response user=%s intent=%s matches=%d request_ref=%s",
            ctx.user_id,
            result.get("intent", "unknown"),
            len(result.get("matches", [])),
            request_ref,
        )

        # Strip internal diagnostics from unauthenticated responses
        stripped_result = _strip_internal_fields(result)

        _metrics.record_request((time.time() - start_time) * 1000)
        return RicoChatResponse(**stripped_result, trace_id=request_ref)
    except Exception as exc:
        logger.exception(
            "chat_public_error user=%s message_len=%d error_type=%s error=%s request_ref=%s",
            ctx.user_id if "ctx" in locals() else "unknown",
            len(payload.message) if "payload" in locals() else 0,
            type(exc).__name__,
            str(exc) or repr(exc),
            request_ref,
        )
        _metrics.record_request((time.time() - start_time) * 1000)
        return RicoChatResponse(
            message=f"I couldn't process your request. Reference: {request_ref}. Please try again or rephrase your message.",
            type="error",
            trace_id=request_ref,
        )


@router.get("/chat/history")
@limiter.limit(LIMIT_CHAT)
def rico_chat_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    before: str | None = None,
) -> dict[str, Any]:
    """Get conversation history with pagination."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    before_ts = None
    if before:
        try:
            before_ts = datetime.fromisoformat(before.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid timestamp format")

    history = chat_service.get_chat_history(user_id, limit=limit, before=before_ts)

    _metrics.record_request((time.time() - start_time) * 1000)
    return {
        "messages": history,
        "total": len(history),
        "has_more": len(history) == limit,
    }


@router.delete("/chat/history", status_code=204)
@limiter.limit(LIMIT_CHAT)
def rico_clear_chat_history(request: Request) -> None:
    """Delete all chat history for the authenticated user (chat messages only)."""
    user = get_current_user(request)
    user_id = user["email"]
    chat_service.clear_chat_history(user_id)


# ============================================================================
# Feedback Endpoint
# ============================================================================

@router.post("/feedback", status_code=204)
def rico_feedback(request: Request, body: FeedbackRequest) -> None:
    """Record user feedback on job matches for learning."""
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    # Map rating to weight for learning
    weight_map = {1: -0.5, 2: -0.2, 3: 0.0, 4: 0.3, 5: 0.7}
    weight = weight_map.get(body.rating, 0.0)

    # Record in learning repository
    learning_repo = get_learning_repository()
    learning_repo.record_signal(
        canonical_user_id=user_id,
        signal_type="feedback",
        signal_value=body.feedback_type,
        signal_weight=weight,
        source="user_feedback",
        metadata={
            "job_id": body.job_id,
            "rating": body.rating,
            "comment": body.comment,
        }
    )

    _metrics.record_request((time.time() - start_time) * 1000)


# ============================================================================
# AI Probe Endpoint
# ============================================================================

@router.get("/openai-smoke")
@limiter.limit(LIMIT_CHAT)
def rico_openai_smoke(request: Request) -> dict[str, Any]:
    """Minimal premium-provider runtime probe."""
    start_time = time.time()
    get_current_user(request)

    provider = get_ai_provider()
    agent = RicoOpenAIAgent()

    if provider not in ("openai", "deepseek"):
        _metrics.record_request((time.time() - start_time) * 1000)
        return {
            "success": False,
            "provider": provider,
            "provider_available": agent.provider_available,
            "openai_available": False,
            "deepseek_available": agent.deepseek_available,
            "hf_available": agent.hf_available,
            "response": (
                f"Premium AI provider disabled (active provider: {provider}). "
                "Set RICO_AI_PROVIDER=openai or RICO_AI_PROVIDER=deepseek to enable advanced reasoning."
            ),
            "error": "OpenAIProviderDisabled",
            "error_detail": None,
            "model": None,
            "fallback_model": None,
        }

    if provider == "openai":
        result = call_openai_minimal("Say OK", smoke=True)
    else:
        result = call_openai_minimal("Say OK", smoke=True, provider=provider)

    _metrics.record_request((time.time() - start_time) * 1000)
    return {
        "success": result.get("success", False),
        "provider": provider,
        "provider_available": result.get("provider_available"),
        "model": (
            result.get("model")
            or result.get("deepseek_model")
            or result.get("openai_model")
        ),
        "fallback_model": result.get("fallback_model"),
        "response": result.get("text"),
        "error": result.get("error"),
        "error_detail": result.get("error_detail"),
        "openai_available": result.get(
            "openai_available",
            bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API")),
        ),
        "deepseek_available": result.get(
            "deepseek_available",
            bool(os.getenv("DEEPSEEK_API_KEY")),
        ),
    }


# ============================================================================
# AI Provider Health Endpoint (Admin Only)
# ============================================================================

@router.get("/admin/health/ai-provider")
@limiter.limit(LIMIT_ADMIN)
def rico_ai_provider_health_admin(request: Request) -> dict[str, Any]:
    """Admin-only health check endpoint exposing current AI provider availability and state."""
    require_admin_user(get_current_user(request))
    from src.rico_openai_agent import RicoOpenAIAgent
    from src.rico_env import get_ai_provider

    provider = get_ai_provider()
    agent = RicoOpenAIAgent()

    # Get Jotform form IDs (without exposing secrets)
    jotform_form_id = os.getenv("JOTFORM_FORM_ID") or os.getenv("JOTFORM_RICO_FORM_ID")
    jotform_configured = bool(jotform_form_id)

    # Check webhook secret status (without exposing the secret)
    webhook_secret_configured = bool(os.getenv("JOTFORM_WEBHOOK_SECRET"))

    from src.rico_openai_runtime import (
        DEEPSEEK_PRIMARY_MODEL,
        DEEPSEEK_FALLBACK_MODEL,
        OPENAI_PRIMARY_MODEL,
        OPENAI_FALLBACK_MODEL,
        _deepseek_model_chain,
    )

    if provider == "deepseek":
        selected_model = DEEPSEEK_PRIMARY_MODEL
        fallback_models = _deepseek_model_chain()[1:]
    else:
        selected_model = OPENAI_PRIMARY_MODEL
        fallback_models = [OPENAI_FALLBACK_MODEL]

    return {
        "active_provider": provider,
        "provider_available": agent.provider_available,
        "openai_available": agent.openai_available,
        "deepseek_available": agent.deepseek_available,
        "hf_available": agent.hf_available,
        "provider_state": "available" if agent.provider_available else "unavailable",
        "selected_model": selected_model,
        "fallback_models": fallback_models,
        "jotform_form_configured": jotform_configured,
        "jotform_webhook_secret_configured": webhook_secret_configured,
        "timestamp": datetime.now(_UTC).isoformat(),
    }


@router.get("/health/ai-provider")
def rico_ai_provider_health_public(request: Request) -> dict[str, Any]:
    """Public health check endpoint with minimal information."""
    from src.rico_env import get_ai_provider

    provider = get_ai_provider()

    return {
        "status": "healthy",
        "timestamp": datetime.now(_UTC).isoformat(),
    }


# ============================================================================
# Profile Update Endpoint
# ============================================================================

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    telegram_username: Optional[str] = Field(None, max_length=100)
    target_roles: Optional[list[str]] = Field(None, max_length=50)
    preferred_cities: Optional[list[str]] = Field(None, max_length=20)
    salary_expectation_aed: Optional[int] = Field(None, ge=0, le=10_000_000)
    minimum_salary_aed: Optional[int] = Field(None, ge=0, le=10_000_000)
    years_experience: Optional[float] = Field(None, ge=0, le=60)
    current_role: Optional[str] = Field(None, max_length=200)
    current_company: Optional[str] = Field(None, max_length=200)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    visa_status: Optional[str] = Field(None, max_length=100)
    notice_period: Optional[str] = Field(None, max_length=100)
    skills: Optional[list[str]] = Field(None, max_length=100)
    industries: Optional[list[str]] = Field(None, max_length=50)


def _profile_updates_visible(user_id: str, updates: dict[str, Any]) -> bool:
    """Confirm profile writes through the same profile read path used by the UI."""
    profile = profile_repo.get_profile(user_id)
    if profile is None:
        return False
    for key, expected in updates.items():
        actual = getattr(profile, key, None)
        if isinstance(expected, list):
            if list(actual or []) != expected:
                return False
        elif actual != expected:
            return False
    return True


@router.patch("/profile")
@limiter.limit(LIMIT_PROFILE)
def update_profile(request: Request, body: ProfileUpdateRequest) -> dict[str, Any]:
    """Direct profile update endpoint for inline edits."""
    user = get_current_user(request)
    user_id = user["email"]

    updates: dict[str, Any] = {}
    if body.name is not None:
        name = body.name.strip()
        if name:
            updates["name"] = name
    if body.phone is not None:
        phone = body.phone.strip()
        if phone:
            updates["phone"] = phone
    if body.telegram_username is not None:
        telegram = body.telegram_username.strip()
        if telegram:
            updates["telegram_username"] = telegram
    if body.target_roles is not None:
        from src.role_normalization import validate_and_normalize_target_roles
        updates["target_roles"] = validate_and_normalize_target_roles(body.target_roles)
    if body.preferred_cities is not None:
        from src.services.city_validation import sanitize_cities
        updates["preferred_cities"] = sanitize_cities(
            [c.strip() for c in body.preferred_cities if c.strip()]
        ) or []
    if body.salary_expectation_aed is not None:
        updates["salary_expectation_aed"] = body.salary_expectation_aed
    if body.minimum_salary_aed is not None:
        updates["minimum_salary_aed"] = body.minimum_salary_aed
    if body.years_experience is not None:
        updates["years_experience"] = body.years_experience
    if body.current_role is not None:
        updates["current_role"] = body.current_role.strip()
    if body.current_company is not None:
        updates["current_company"] = body.current_company.strip()
    if body.linkedin_url is not None:
        updates["linkedin_url"] = body.linkedin_url.strip()
    if body.visa_status is not None:
        updates["visa_status"] = body.visa_status.strip()
    if body.notice_period is not None:
        updates["notice_period"] = body.notice_period.strip()
    if body.skills is not None:
        from src.role_normalization import validate_and_normalize_skills
        updates["skills"] = validate_and_normalize_skills(body.skills)
    if body.industries is not None:
        updates["industries"] = [i.strip() for i in body.industries if i.strip()]

    # When the user explicitly sets target_roles or skills, bump normalization_version
    # to the current version so get_profile does not re-normalize and silently mutate
    # adjacent fields (e.g. a skills save triggering normalization that changes
    # target_roles). Do NOT call normalize_profile_updates — user input is saved as-is.
    if "target_roles" in updates or "skills" in updates:
        from src.role_normalization import NORMALIZATION_VERSION
        updates["normalization_version"] = NORMALIZATION_VERSION

    logger.info("update_profile endpoint: user_id=%s updates=%s", user_id, updates)

    profile_for_warnings = None
    if updates:
        profile_for_warnings = upsert_profile(user_id, updates)
        confirmed = _MUTATION_CONFIRMATION_GUARD.confirm(
            MutationResult(success=True),
            verifier=lambda: _profile_updates_visible(user_id, updates),
            success_en="confirmed",
            success_ar="confirmed",
            failure_en="failed",
            failure_ar="failed",
        ) == "confirmed"
        if not confirmed:
            raise HTTPException(
                status_code=500,
                detail="Profile update could not be confirmed. Please try again.",
            )
        logger.info("profile_update user=%s fields=%s", user_id, list(updates.keys()))
    else:
        logger.warning("profile_update no fields user=%s", user_id)
        profile_for_warnings = get_profile(user_id)

    matching_fields_updated = bool({"target_roles", "preferred_cities"} & updates.keys())
    warnings = (
        build_matching_guardrail_warnings(
            settings=get_settings(user_id=user_id),
            profile=profile_for_warnings,
        )
        if matching_fields_updated
        else []
    )
    response = {
        "status": "ok",
        "updated_fields": list(updates.keys()),
    }
    if warnings:
        response["warnings"] = warnings
    return response


# ============================================================================
# Metrics Endpoint
# ============================================================================

@router.get("/metrics", response_model=MetricsResponse)
def rico_metrics(request: Request) -> MetricsResponse:
    """Prometheus-style metrics endpoint."""
    # Require authentication for metrics
    get_current_user(request)

    return MetricsResponse(
        uptime_seconds=_metrics.uptime_seconds,
        total_requests=_metrics.request_count,
        avg_response_time_ms=_metrics.avg_response_time_ms,
        active_sessions=0,  # Would need session tracking with HyperLogLog
        cache_hit_rate=_metrics.cache_hit_rate,
        timestamp=datetime.now(_UTC).isoformat(),
    )


# ============================================================================
# CV Upload Endpoint
# ============================================================================

@router.post("/upload-cv")
@limiter.limit(LIMIT_UPLOAD)
async def rico_upload_cv(
    request: Request,
    file: UploadFile = File(...),
    user_id: str | None = None,
    form_user_id: str | None = Form(None, alias="user_id"),
) -> dict[str, Any]:
    """Upload and parse CV file (PDF only)."""
    start_time = time.time()
    request_ref = generate_error_ref()
    resolved_user_id = _resolve_upload_user_id(request, user_id, form_user_id)

    # Enforce per-plan CV quota for authenticated users.
    # Guest/public sessions (public:*) are exempt — they have no plan record.
    if not is_valid_public_user_id(resolved_user_id):
        from src.services.subscription_gating import enforce_document_quota
        enforce_document_quota(resolved_user_id, "cv")

    try:
        # Reject clearly-oversized files BEFORE reading the whole body into memory,
        # using the multipart-declared size when available (coarse hard cap).
        declared_size = getattr(file, "size", None)
        if isinstance(declared_size, int) and declared_size > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=_too_large_message(_MAX_DOC_BYTES, is_image=False),
            )

        data = await file.read()
        if not data:
            raise HTTPException(status_code=422, detail="Uploaded file is empty")

        # Server-side hash of the ORIGINAL bytes actually received — never
        # accepted from the client. Carried through the short-lived upload
        # artifact (see cv_upload_artifact_repo) so confirm-cv-profile can
        # later resolve it server-side by upload_id instead of trusting a
        # client-echoed hash or re-parsing.
        content_hash = hashlib.sha256(data).hexdigest()

        safe_name = _safe_filename(file.filename)

        # Per-kind size cap, enforced from the real magic-byte format BEFORE any
        # parsing/classification — documents (25 MB) vs images (10 MB). Oversized
        # uploads are rejected here with a user-friendly message, never blamed on
        # CV parsing and never asking the user to pointlessly retry.
        from src.services.document_classifier import classify_document, detect_format
        upload_format = detect_format(data, safe_name)
        size_limit = _upload_limit_for(upload_format)
        if len(data) > size_limit:
            raise HTTPException(
                status_code=413,
                detail=_too_large_message(size_limit, is_image=upload_format == "image"),
            )

        # ── Document Intelligence — classify BEFORE any pipeline ──────────────
        # Every uploaded file is classified first. Only confirmed CVs enter the
        # CV extraction pipeline. All other types return classification + actions.
        loop = asyncio.get_event_loop()
        classification = await loop.run_in_executor(
            None, classify_document, data, safe_name
        )
        doc_type = classification.document_type
        confidence = classification.confidence

        logger.info(
            "doc_classify user=%s filename=%s type=%s confidence=%.2f format=%s request_ref=%s",
            resolved_user_id, safe_name, doc_type, confidence,
            classification.file_format, request_ref,
        )

        # Executables (EXE/DLL): always rejected — never process.
        if classification.file_format == "executable":
            raise HTTPException(status_code=422, detail="Executable files are not accepted")

        # Images: try a vision-model transcription so a job-posting / recruiter
        # screenshot becomes readable, then re-classify the extracted text (a job
        # screenshot → job_description with real actions). Falls back to the
        # format-only image response when no vision model is configured or it
        # returns nothing — the upload is never blocked.
        if classification.file_format == "image":
            from src.services.image_extractor import extract_text_from_image
            extracted = await loop.run_in_executor(
                None, extract_text_from_image, data, safe_name
            )
            if extracted and len(extracted.strip()) >= 20:
                text_classification = await loop.run_in_executor(
                    None, classify_document, extracted.encode("utf-8"), "image-text.txt"
                )
                # Remember the transcription so follow-up chat ("save as target
                # job", "score against my CV") can reference the screenshot.
                # Durable store first — survives Render restarts, multiple
                # instances, and RICO_MEMORY_BACKEND=postgres (where the JSON
                # memory store below is a no-op). Keyed by the resolved user /
                # public-session id, so authenticated and public sessions both work.
                try:
                    from src.repositories.uploaded_document_repo import set_last_uploaded_document
                    set_last_uploaded_document(
                        resolved_user_id,
                        extracted_text=extracted[:4000],
                        filename=safe_name,
                        document_type=text_classification.document_type,
                        display_label=text_classification.display_label,
                        source="image",
                        request_ref=request_ref,
                    )
                except Exception:
                    pass
                if not is_valid_public_user_id(resolved_user_id):
                    try:
                        from src.rico_memory import RicoMemoryStore
                        _mem = RicoMemoryStore()
                        _rctx = _mem.get_context(resolved_user_id, "recent_context") or {}
                        _rctx["last_uploaded_document"] = {
                            "document_type": text_classification.document_type,
                            "display_label": text_classification.display_label,
                            "filename": safe_name,
                            "source": "image",
                            "extracted_text": extracted[:4000],
                            "suggested_actions": list(text_classification.suggested_actions or []),
                        }
                        _mem.set_context(resolved_user_id, "recent_context", _rctx)
                    except Exception:
                        pass
                _metrics.record_request((time.time() - start_time) * 1000)
                logger.info(
                    "doc_image_extracted user=%s filename=%s type=%s chars=%d request_ref=%s",
                    resolved_user_id, safe_name, text_classification.document_type,
                    len(extracted), request_ref,
                )
                resp = _classification_response(text_classification, safe_name)
                preview = extracted.strip()
                if len(preview) > 600:
                    preview = preview[:600].rsplit(" ", 1)[0] + "…"
                resp["message"] = (
                    f"I read your image — it looks like a **{text_classification.display_label}**. "
                    f"Here's what I found:\n\n{preview}\n\nWhat would you like me to do with it?"
                )
                resp["extracted_text"] = extracted[:4000]
                resp["source"] = "image"
                return resp
            _metrics.record_request((time.time() - start_time) * 1000)
            return _classification_response(classification, safe_name)

        # Identity documents: hard block — never echo content.
        if doc_type == "identity_document":
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.warning(
                "doc_classify_blocked user=%s filename=%s type=%s request_ref=%s",
                resolved_user_id, safe_name, doc_type, request_ref,
            )
            return {
                "ok": False,
                "status": "rejected",
                "document_type": doc_type,
                "message": (
                    "This document appears to be a passport or identity document. "
                    "For your security it was not saved and your profile was not changed. "
                    "Please upload a CV or resume instead."
                ),
            }

        # No-text / image-only documents: a screenshot or scan exported as a PDF,
        # or an otherwise empty/unreadable file. There is no extractable text, so the
        # CV parser would only emit a misleading "poor quality" CV preview (#674
        # residual). Return a clear needs-text response — never the CV pipeline.
        # (OCR/vision for these is handled separately and is out of scope here.)
        _NEAR_EMPTY_CHARS = 25
        _NO_TEXT_MIN_BYTES = 1024
        extracted_chars = int(classification.metadata.get("chars", 0) or 0)
        text_bearing_format = classification.file_format in ("pdf", "doc", "docx", "text")
        if text_bearing_format and len(data) >= _NO_TEXT_MIN_BYTES and (
            doc_type == "no_text"
            or (doc_type == "unknown" and confidence <= 0.0 and extracted_chars < _NEAR_EMPTY_CHARS)
        ):
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.info(
                "doc_classify_no_text user=%s filename=%s format=%s chars=%d request_ref=%s",
                resolved_user_id, safe_name, classification.file_format,
                extracted_chars, request_ref,
            )
            return {
                "ok": True,
                "status": "classified",
                "document_type": "no_text",
                "file_format": classification.file_format,
                "filename": safe_name,
                "confidence": round(confidence, 3),
                "suggested_actions": [],
                "display_label": "Unreadable / Image-only Document",
                "message": (
                    "I couldn't find any readable text in this file. It looks like a "
                    "scan, photo, or screenshot saved as a PDF rather than a text "
                    "document. I can read text-based PDFs and Word files — if this is "
                    "your CV, please upload a text-based version."
                ),
            }

        # Non-CV documents → return classification + actions, never the CV pipeline.
        # CV types that also proceed through extraction: "cv", "cover_letter", "unknown"
        #
        # #908 RC4: doc_type is already the argmax classification across every
        # category INCLUDING "cv" (see DocumentClassifier._classify_text's
        # ranking) — if a non-CV type won that comparison, the document is not
        # a CV regardless of how low the blended `confidence` score is. The
        # previous gate additionally required `confidence >= 0.18 and
        # confidence > cv_score`, but `confidence` is a *scaled-down* blend of
        # the top raw score (penalised when a runner-up is close), so it can
        # fall below cv_score's raw, unscaled value even though doc_type
        # legitimately won on raw score. That let a low-confidence invoice
        # slip into the CV extraction pipeline and, once confirmed, become
        # the user's permanent "Active CV". Exclusion is now type-driven —
        # confidence is no longer part of the decision.
        _CV_PIPELINE_TYPES = {"cv", "cover_letter", "unknown"}
        if doc_type not in _CV_PIPELINE_TYPES:
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.info(
                "doc_classify_routed user=%s filename=%s type=%s confidence=%.2f request_ref=%s",
                resolved_user_id, safe_name, doc_type, confidence, request_ref,
            )
            # Store classification in session context so Rico can reference the
            # uploaded document in subsequent chat turns (e.g. "can you review it?").
            if not is_valid_public_user_id(resolved_user_id):
                try:
                    from src.rico_memory import RicoMemoryStore
                    _mem = RicoMemoryStore()
                    _rctx = _mem.get_context(resolved_user_id, "recent_context") or {}
                    _rctx["last_uploaded_document"] = {
                        "document_type": doc_type,
                        "display_label": classification.display_label,
                        "filename": safe_name,
                        "confidence": round(confidence, 3),
                        "suggested_actions": list(classification.suggested_actions or []),
                    }
                    _mem.set_context(resolved_user_id, "recent_context", _rctx)
                except Exception:
                    pass
            return _classification_response(classification, safe_name)

        # ── CV extraction pipeline ────────────────────────────────────────────
        # Only reached for type=cv/cover_letter/unknown (or low-confidence non-CV).
        try:
            parsed_raw = await loop.run_in_executor(
                None, chat_service.parse_cv, data, safe_name
            )

            if hasattr(parsed_raw, "to_dict"):
                parsed = parsed_raw.to_dict()
            elif isinstance(parsed_raw, dict):
                parsed = parsed_raw
            else:
                raise TypeError(f"Unexpected CV parser result type: {type(parsed_raw)}")
        except Exception as exc:
            logger.exception(
                "cv_upload_parse_error ref=%s user=%s filename=%s bytes=%d error=%s",
                request_ref, resolved_user_id, safe_name, len(data), str(exc),
            )
            return {
                "ok": False,
                "status": "error",
                "error_ref": request_ref,
                "message": (
                    f"Upload failed. Reference: {request_ref}. "
                    "I could not read this file. "
                    "Please try a text-based PDF or Word document under 25 MB."
                ),
            }

        # Refined type from CVParser (may agree with or override the classifier).
        cv_doc_type = parsed.get("document_type", "unknown")
        # Trust classifier for non-cv types it already identified.
        if doc_type not in ("unknown",) and cv_doc_type == "unknown":
            cv_doc_type = doc_type

        logger.info(
            "cv_upload user=%s filename=%s doc_type=%s quality=%s chars=%d skills=%d request_ref=%s",
            resolved_user_id, safe_name, cv_doc_type,
            parsed.get("extraction_quality", "unknown"),
            parsed.get("extracted_chars", 0),
            len(parsed.get("skills", [])),
            request_ref,
        )

        # Company profile: route through classification instead of CV pipeline.
        if cv_doc_type == "company_profile":
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.warning(
                "cv_upload_rejected user=%s filename=%s doc_type=%s reason=not_cv request_ref=%s",
                resolved_user_id, safe_name, cv_doc_type, request_ref,
            )
            # Build a classification response using the known type.
            from src.services.document_classifier import _SUGGESTED_ACTIONS, _DISPLAY_LABELS, ClassificationResult
            alt = ClassificationResult(
                document_type="company_profile",
                confidence=0.85,
                confidence_scores={"company_profile": 0.85},
                suggested_actions=_SUGGESTED_ACTIONS["company_profile"],
                display_label=_DISPLAY_LABELS["company_profile"],
                file_format=classification.file_format,
            )
            return _classification_response(alt, safe_name)

        # Build profile preview without auto-updating the permanent profile
        existing_profile = get_profile(resolved_user_id)
        existing_skills = getattr(existing_profile, "skills", []) if existing_profile else []

        # Extract target roles from CV text using role patterns
        cv_text = parsed.get("text", "")
        target_roles = _extract_roles_from_cv_text(cv_text)

        # Build preview data with trust controls - separate detected from existing
        detected_skills = parsed.get("skills", []) if parsed.get("skills") else []
        preview = {
            "name": parsed.get("name"),
            "email": parsed.get("emails", [None])[0] if parsed.get("emails") else None,
            "phone": parsed.get("phones", [None])[0] if parsed.get("phones") else None,
            "current_role": parsed.get("current_role"),
            "experience_years": parsed.get("years_experience_hint"),
            "target_roles": target_roles if target_roles else [],
            "skills_detected": detected_skills,
            "existing_skills": existing_skills,
            "skills": detected_skills if detected_skills else existing_skills,  # For backward compatibility
            "certifications": parsed.get("certifications", []),
            "languages": parsed.get("languages", []),
        }

        cv_warnings = build_cv_quality_warnings(
            preview=preview,
            extraction_quality=parsed.get("extraction_quality"),
            profile=existing_profile,
        )

        _metrics.record_request((time.time() - start_time) * 1000)
        logger.info(
            "cv_upload_preview user=%s filename=%s quality=%s warnings=%d preview_ready request_ref=%s",
            resolved_user_id,
            safe_name,
            parsed.get("extraction_quality", "unknown"),
            len(cv_warnings),
            request_ref,
        )

        upload_id: str | None = None
        if not is_valid_public_user_id(resolved_user_id):
            try:
                from src.rico_memory import RicoMemoryStore
                _mem = RicoMemoryStore()
                _rctx = _mem.get_context(resolved_user_id, "recent_context") or {}
                _rctx["last_uploaded_document"] = {
                    "document_type": doc_type or "cv",
                    "display_label": "Resume / CV",
                    "filename": safe_name,
                    "confidence": round(confidence, 3),
                    "suggested_actions": [],
                }
                _mem.set_context(resolved_user_id, "recent_context", _rctx)
            except Exception:
                pass

            # Durable, short-lived server-side artifact (#963) — carries the
            # server-computed hash, byte count, and full parsed text from
            # this upload to the matching confirm-cv-profile call. Replaces
            # the RicoMemoryStore "last_uploaded_cv_text" stash, which is a
            # no-op in production (RICO_MEMORY_BACKEND=postgres). The client
            # receives only the opaque id — never the hash or text directly.
            try:
                from src.repositories.cv_upload_artifact_repo import create_cv_upload_artifact
                upload_id = create_cv_upload_artifact(
                    resolved_user_id,
                    filename=safe_name,
                    doc_type=doc_type or "cv",
                    content_hash=content_hash,
                    file_size=len(data),
                    cv_text=cv_text,
                )
            except Exception:
                upload_id = None

        return {
            "ok": True,
            "status": "preview_ready",
            "document_type": doc_type,
            "extraction_quality": parsed.get("extraction_quality"),
            "extracted_chars": parsed.get("extracted_chars"),
            "filename": safe_name,
            "preview": preview,
            "parsed": parsed,
            "user_id": resolved_user_id,
            "upload_id": upload_id,
            "warnings": cv_warnings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "cv_upload_error user=%s filename=%s error=%s request_ref=%s",
            resolved_user_id,
            safe_name if "safe_name" in locals() else "unknown",
            str(exc),
            request_ref,
        )
        _metrics.record_request((time.time() - start_time) * 1000)
        raise HTTPException(
            status_code=500,
            detail=f"CV upload failed. Reference: {request_ref}"
        )


def _resolve_trusted_cv_artifact(
    resolved_user_id: str, payload: ConfirmCVProfileRequest
) -> dict[str, Any] | None:
    """Resolve and strictly validate the upload-cv artifact for a confirm call.

    Returns the artifact dict ONLY when it is complete and trustworthy:
    present, unexpired, scoped to this exact server-derived user_id, and its
    filename matches what the client is confirming. Returns ``None`` for
    every failure mode (missing upload_id, an expired/foreign/unresolvable
    artifact, a filename mismatch, or a resolved row missing content_hash /
    file_size / filename / doc_type) -- the caller must treat ``None`` as
    "reject the confirm outright", never as "proceed without a hash".
    """
    if not payload.upload_id:
        return None
    from src.repositories.cv_upload_artifact_repo import resolve_cv_upload_artifact
    artifact = resolve_cv_upload_artifact(resolved_user_id, payload.upload_id)
    if not artifact:
        return None
    if (
        not artifact.get("content_hash")
        or artifact.get("file_size") is None
        or not artifact.get("filename")
        or not artifact.get("doc_type")
    ):
        return None
    if artifact.get("filename") != payload.filename:
        return None
    return artifact


@router.post("/confirm-cv-profile")
@limiter.limit(LIMIT_UPLOAD)
async def confirm_cv_profile(
    request: Request,
    payload: ConfirmCVProfileRequest,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    """Confirm and save CV profile preview to permanent profile.

    This endpoint accepts JSON, so declaring a Form(...) parameter here would
    force FastAPI to expect an embedded "body" key. Keep user_id in the query
    string for public sessions and resolve auth identity from the cookie.
    """
    start_time = time.time()
    request_ref = generate_error_ref()
    resolved_user_id = _resolve_upload_user_id(request, user_id, None)

    try:
        logger.info(
            "cv_profile_confirm user=%s filename=%s request_ref=%s",
            resolved_user_id,
            payload.filename,
            request_ref,
        )

        from src.services.subscription_gating import (
            enforce_profile_optimization_allowed,
            record_profile_optimization_usage,
        )
        # Allow the very first CV confirm unconditionally (new-user onboarding must never
        # be blocked). Subsequent uploads are gated against the plan's monthly limit.
        enforce_profile_optimization_allowed(resolved_user_id, is_first_upload=True)

        # Build profile updates from preview - use skills_detected if available, fallback to skills
        preview_skills = payload.preview.get("skills_detected") or payload.preview.get("skills", [])
        # SECURITY: never persist email/phone parsed from CV text. A CV routinely contains a
        # referee's, a previous employer's, or a mis-parsed contact detail; routing it through
        # upsert_profile -> upsert_user (which COALESCEs email/phone) would silently overwrite
        # the authenticated uploader's canonical identity and could break password reset or
        # lock them out. Account identity comes from the authenticated session / registration,
        # not from uploaded document text. The parsed contact details are still surfaced to the
        # user in the upload preview for display; users set email/phone via their explicit input.
        profile_updates = {
            "name": payload.preview.get("name"),
            "current_role": payload.preview.get("current_role"),
            "skills": preview_skills,
            "years_experience": payload.preview.get("experience_years"),
            "target_roles": payload.preview.get("target_roles", []) if payload.preview.get("target_roles") else None,
            "certifications": payload.preview.get("certifications", []),
            "languages": payload.preview.get("languages", []),
            "cv_filename": payload.filename,
            "cv_status": "parsed",
            "cv_extracted_at": datetime.now(_UTC).isoformat(),
            "profile_creation_mode": "cv_first",
            "manual_profile_wizard_disabled": True,
        }

        # Normalize target roles to prevent broad standalone roles (Engineer, Manager, etc.)
        from src.role_normalization import normalize_profile_updates
        profile_updates = normalize_profile_updates(profile_updates)

        # Filter out None/empty values, but preserve name if it exists in preview
        # even if other fields are empty - name is critical for profile identity
        filtered_updates = {k: v for k, v in profile_updates.items() if v not in (None, [], {})}
        # Ensure name is preserved if extracted from CV
        if profile_updates.get("name") and "name" not in filtered_updates:
            filtered_updates["name"] = profile_updates["name"]
        profile_updates = filtered_updates

        # Resolve and STRICTLY validate the short-lived upload artifact (#963)
        # server-side, scoped to the caller's OWN server-derived identity
        # (never a client-supplied user_id) and a freshness window. A missing
        # upload_id, an expired/foreign artifact (resolve returns None), a
        # filename mismatch against payload.filename, or an artifact missing
        # any of content_hash/file_size/filename/doc_type means this confirm
        # cannot be trusted -- reject outright with NO side effects (no
        # profile write, no document, no onboarding-status change) rather
        # than silently degrading to an unhashed/untracked document. Never
        # routed through RicoMemoryStore (a no-op under
        # RICO_MEMORY_BACKEND=postgres, the production backend).
        #
        # Public/guest sessions never persist a document at all (see the
        # `is_valid_public_user_id` guard on the document-save block below,
        # unchanged since before #963) and were never issued an artifact by
        # upload-cv in the first place (also gated the same way) -- so this
        # requirement does not apply to them; a guest confirm still proceeds
        # profile-only, exactly as before.
        artifact: dict[str, Any] | None = None
        if not is_valid_public_user_id(resolved_user_id):
            artifact = _resolve_trusted_cv_artifact(resolved_user_id, payload)
            if artifact is None:
                logger.warning(
                    "cv_confirm_artifact_rejected user=%s upload_id=%s filename=%s request_ref=%s",
                    resolved_user_id, payload.upload_id, payload.filename, request_ref,
                )
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "status": "cv_confirmation_required",
                        "message": "Please upload the CV again before confirming.",
                    },
                )

        confirmed_cv_text: str | None = (artifact or {}).get("cv_text") or None

        # ── Write order & partial-state policy (#975 review) ──────────────────
        # For authenticated users the durable My Files document write happens
        # FIRST and its failure fails the whole confirm with a non-2xx — it is
        # NEVER swallowed. Rationale: this is the one write whose silent failure
        # reproduces the original #963 bug (the user is told "profile confirmed"
        # while the CV never lands in My Files). Doing it first means a failure
        # leaves NOTHING else changed — no profile mutation, no onboarding-status
        # flip, no success claim. The later writes (upsert_profile, onboarding
        # status) already handle their own DB errors and never raise, and are
        # self-healing (onboarding status is re-derived on every /onboarding/
        # status GET and re-evaluated on every submit), so ordering them after
        # the hard document write is safe.
        #
        # Guest/public sessions have no My Files and were never issued an
        # artifact, so they skip this block entirely (profile-only confirm).
        if not is_valid_public_user_id(resolved_user_id):
            from src.rico_db import RicoDB as _RicoDB
            _doc_db = _RicoDB()
            if not _doc_db.available:
                # Cannot persist to My Files -> do not claim success, and fail
                # BEFORE any profile/onboarding mutation.
                logger.error(
                    "cv_confirm_doc_db_unavailable user=%s request_ref=%s",
                    resolved_user_id, request_ref,
                )
                _metrics.record_request((time.time() - start_time) * 1000)
                return JSONResponse(
                    status_code=503,
                    content={
                        "ok": False,
                        "status": "cv_persistence_unavailable",
                        "message": "We couldn't save your CV right now. Please try again in a moment.",
                    },
                )
            skills = profile_updates.get("skills") or []
            # #908 RC4: doc_type is always the server-derived value recorded on
            # the trusted artifact at upload time — payload.doc_type
            # (client-echoed) is never used for persistence — and only ever the
            # known-safe set. is_primary is only set for a real "cv".
            _CONFIRMABLE_DOC_TYPES = ("cv", "cover_letter", "other")
            _resolved_doc_type = (
                artifact["doc_type"] if artifact["doc_type"] in _CONFIRMABLE_DOC_TYPES else "other"
            )
            try:
                _doc_db.get_or_create_user_document(
                    user_id=resolved_user_id,
                    filename=artifact["filename"],
                    original_filename=artifact["filename"],
                    doc_type=_resolved_doc_type,
                    file_size=artifact["file_size"],
                    content_hash=artifact["content_hash"],
                    skills_count=len(skills),
                    skills_json=list(skills),
                    years_experience=profile_updates.get("years_experience"),
                    current_role=profile_updates.get("current_role"),
                    is_primary=(_resolved_doc_type == "cv"),
                )
            except Exception as _doc_exc:
                # NEVER swallowed (the #975 blocker): fail the confirm with a
                # non-2xx BEFORE any profile/onboarding mutation. No false
                # success, no "CV saved" claim, no onboarding completion.
                logger.exception(
                    "cv_confirm_doc_save_failed user=%s error=%s request_ref=%s",
                    resolved_user_id, str(_doc_exc), request_ref,
                )
                _metrics.record_request((time.time() - start_time) * 1000)
                return JSONResponse(
                    status_code=500,
                    content={
                        "ok": False,
                        "status": "cv_persistence_failed",
                        "message": "We couldn't save your CV. Please try again.",
                    },
                )

        # Persist the profile fields to Neon. This is REQUIRED (require_db=True),
        # NOT best-effort: without it upsert_profile would swallow a silent Neon
        # failure and return the JSON memory mirror, and confirm would report
        # success while target_roles/skills/years/cv_status never actually
        # persisted (the same false-success class as the My Files write above).
        # On failure we return a non-2xx BEFORE marking onboarding complete, so
        # the user retries instead of believing their profile saved. The retry
        # is safe: the My Files write above dedupes on content_hash, and this
        # upsert is a keyed UPSERT.
        try:
            upsert_profile(
                user_id=resolved_user_id,
                updates=profile_updates,
                cv_text=confirmed_cv_text,
                require_db=True,
            )
        except Exception as _profile_exc:
            logger.exception(
                "cv_confirm_profile_persist_failed user=%s error=%s request_ref=%s",
                resolved_user_id, str(_profile_exc), request_ref,
            )
            _metrics.record_request((time.time() - start_time) * 1000)
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "status": "profile_persistence_failed",
                    "message": "We couldn't save your CV. Please try again.",
                },
            )
        record_profile_optimization_usage(resolved_user_id)

        # Onboarding completion must reflect the SAME minimum-profile gate
        # onboarding/submit evaluates — never a blind side effect of
        # confirming a CV. Confirming a CV alone (without target_roles /
        # preferred_cities / years_experience) must not flip onboarding to
        # "complete"; conversely this lets a CV-only confirm from /command
        # complete onboarding when the gate already passes, exactly as
        # onboarding/submit would. Public/guest sessions have no onboarding
        # state to update.
        if not is_valid_public_user_id(resolved_user_id):
            from src.services.profile_context_resolver import (
                evaluate_minimum_profile,
                resolve_profile_context,
            )
            _merged_profile = get_profile(resolved_user_id)
            _ctx = resolve_profile_context(resolved_user_id, _merged_profile)
            _gate_ok, _missing_fields = evaluate_minimum_profile(_ctx)
            onboarding_repo.set_onboarding_status(
                resolved_user_id,
                ONBOARDING_COMPLETED if _gate_ok else ONBOARDING_IN_PROGRESS,
            )

        _metrics.record_request((time.time() - start_time) * 1000)
        logger.info(
            "cv_profile_confirmed user=%s fields=%d request_ref=%s",
            resolved_user_id,
            len(profile_updates),
            request_ref,
        )

        return {
            "ok": True,
            "status": "profile_updated",
            "message": "Profile confirmed. I can now use it for job matching.",
            "profile": profile_updates,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "cv_profile_confirm_error user=%s filename=%s error=%s request_ref=%s",
            resolved_user_id,
            payload.filename,
            str(exc),
            request_ref,
        )
        _metrics.record_request((time.time() - start_time) * 1000)
        raise HTTPException(
            status_code=500,
            detail=f"Profile confirmation failed. Reference: {request_ref}"
        )


# ============================================================================
# Webhook Endpoints
# ============================================================================

@router.post("/webhooks/telegram")
@limiter.limit(LIMIT_WEBHOOK)
@_webhook_handler("telegram")
async def rico_telegram_webhook(request: Request) -> dict[str, Any]:
    """Telegram bot webhook endpoint."""
    _validate_telegram_secret(request)
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}  # Bad JSON - always ACK

    result = chat_service.handle_telegram_update(update)

    # process_telegram_update() returns {"chat_id": ..., "reply": ...} but does
    # not call the Telegram Bot API — we must push the reply here.
    chat_id = result.get("chat_id")
    reply = result.get("reply")
    if chat_id and reply:
        reply_text = reply if isinstance(reply, str) else reply.get("message", "")
        if reply_text:
            from src.telegram_bot import send_telegram_to_user
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_telegram_to_user, str(chat_id), reply_text)

    return {"ok": True}


@router.post("/webhooks/jotform")
@limiter.limit(LIMIT_WEBHOOK)
@_webhook_handler("jotform")
async def rico_jotform_webhook(request: Request) -> dict[str, Any]:
    """Jotform onboarding webhook endpoint."""
    _validate_jotform_secret(request)
    try:
        payload = await request.json()
    except Exception:
        logger.warning("jotform_webhook: invalid JSON body")
        return {"status": "accepted", "message": "Webhook received"}
    return chat_service.handle_jotform_submission(payload)


@router.post("/webhooks/github")
@limiter.limit(LIMIT_WEBHOOK)
@_webhook_handler("github")
async def rico_github_webhook(request: Request) -> dict[str, Any]:
    """GitHub webhook endpoint (push, PR, issues, ping)."""
    raw_body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()

    if not secret:
        if _is_production():
            logger.error("github_webhook: GITHUB_WEBHOOK_SECRET missing in production")
            raise HTTPException(status_code=503, detail="Webhook not configured")
        logger.warning("github_webhook: GITHUB_WEBHOOK_SECRET missing; allowing dev request")
    else:
        expected = "sha256=" + hmac.new(
            secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not sig or not hmac.compare_digest(sig, expected):
            logger.warning("github_webhook: invalid signature")
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")
    if not event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except Exception:
        logger.warning("github_webhook: invalid JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    return chat_service.handle_github_event(event, payload)


# ── CAREER-OS-03: Permission Engine execute endpoint ──────────────────────────


def _audit_permission_denied(user_id: str, req: ExecutePermissionActionRequest) -> None:
    """Record a denied permission-execute attempt in the action audit log.

    A denial (forged / expired / replayed / user-action-job mismatch) is a
    security-relevant signal. Logging it through the existing audit_repo keeps the
    approval trail complete without introducing a parallel audit table. Best-effort —
    never raises, never blocks the 403 response.
    """
    try:
        from datetime import datetime, timezone

        from src.repositories import audit_repo

        job = req.job or {}
        audit_repo.log_action({
            "action_id":      req.permission_id,
            "action_type":    req.action,
            "user_email":     user_id,
            "job_id":         req.job_key or str(job.get("id") or ""),
            "job_title":      job.get("title"),
            "job_company":    job.get("company"),
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "result_status":  "denied",
            "result_message": "permission validation failed (not found, expired, used, or user/action/job mismatch)",
            "duration_ms":    0,
            "failure_reason": "permission_denied",
        })
    except Exception:
        logger.debug("execute: permission-denied audit write failed", exc_info=True)


@router.post("/actions/execute", response_model=ActionResponse)
@limiter.limit(LIMIT_CHAT)
def execute_permission_action(
    request: Request,
    req: ExecutePermissionActionRequest,
    user: dict = Depends(get_current_user),
) -> ActionResponse:
    """Execute a Rico action that the user explicitly approved via the Permission Engine UI.

    `user_id` is always derived from the JWT — callers cannot spoof other users.
    The `permission_id` is recorded in the audit source so approvals are traceable.
    Routes through the agent_runtime singleton; safety guardrails are always enforced.
    """
    from src.services import pending_permissions
    user_id = user["email"]
    if not pending_permissions.validate_and_consume(
        req.permission_id, user_id, req.action, job_key=req.job_key
    ):
        _audit_permission_denied(user_id, req)
        raise HTTPException(
            status_code=403,
            detail="Permission request not found, expired, or already used.",
        )
    result = agent_runtime.handle_action(
        user_id=user_id,
        action=req.action,
        job_key=req.job_key,
        job=req.job,
        source=f"permission:{req.permission_id}",
        dry_run=False,
        pre_approved=True,
    )
    return ActionResponse(**result.to_dict())
