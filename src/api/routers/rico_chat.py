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
  POST /api/v1/rico/upload-cv                   CV file upload + parsing
  GET  /api/v1/rico/metrics                     Prometheus metrics
  POST /api/v1/rico/webhooks/telegram           Telegram bot webhook (called by Telegram)
  POST /api/v1/rico/webhooks/jotform            Jotform onboarding webhook (called by Jotform)
  POST /api/v1/rico/webhooks/github             GitHub webhook (push, PR, issues, ping)
  POST /api/v1/rico/chat/public                 Public chat (no JWT, session-based, rate-limited)
"""
from __future__ import annotations

import asyncio
from collections.abc import Collection
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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.admin_guard import require_admin_user
from src.api.deps import get_current_user, get_current_user_id
from src.log_privacy import safe_exc, safe_fields, user_ref
from src.api.public_identity import (
    is_safe_public_session_id,
    is_valid_public_user_id,
    make_public_user_id,
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
    # Chat thread selector (#1193): "default" = the legacy thread, a UUID = a
    # named thread from the Sessions rail. Omitted = pre-session behavior.
    # NOT the public-chat session_id — that one is guest identity correlation.
    session_id: str | None = Field(None, max_length=64)

    @field_validator("message")
    @classmethod
    def non_empty_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def safe_chat_session_id(cls, v: str | None) -> str | None:
        from src.services.chat_session_context import normalize_chat_session_id
        return normalize_chat_session_id(v)


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


class ScheduledSearchToggleRequest(BaseModel):
    """Pause/resume a single scheduled search (#1249 step 3)."""
    enabled: bool


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


def upsert_profile(
    user_id: str,
    updates: dict[str, Any],
    cv_text: str | None = None,
    require_db: bool = False,
    clear_fields: Collection[str] = (),
):
    # This wrapper is the router's stable patch point — its signature MUST stay
    # a superset of every call the router makes. The 2026-07-18 production save
    # outage was exactly this: the endpoint passed clear_fields=, the wrapper
    # didn't accept it, and the resulting TypeError surfaced as a 503 on EVERY
    # profile save (endpoint tests mock this symbol, so CI could not see it).
    return profile_repo.upsert_profile(
        user_id=user_id, updates=updates, cv_text=cv_text, require_db=require_db,
        clear_fields=clear_fields,
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
    response: Response | None = None,
) -> str:
    """Resolve user ID for CV upload: JWT identity, or the SERVER-AUTHORITATIVE
    guest identity from the signed capability cookie (#1070).

    A JWT identity always wins (caller-supplied public IDs are ignored). For
    guest callers the supplied `public:*` value is required and format-checked
    but is CORRELATION-ONLY — the identity that owns the upload/confirm is the
    sid inside the capability cookie (minted here when absent). A
    client-selected sid can never become ownership identity.
    """
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

    correlation_sid = user_id.split(":", 1)[1]
    sid = _resolve_guest_sid(request, response if response is not None else Response(), correlation_sid)
    return make_public_user_id(sid)


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

@router.get("/scheduled-searches")
def rico_list_scheduled_searches(request: Request) -> dict[str, Any]:
    """Scheduled-search status + latest in-app results for the current user.

    #1249: identity comes from the JWT only — a user can never read another
    user's schedules or results. Results were stored by the cron sweep; this
    endpoint is read-only and works with email alerts fully disabled.
    """
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    from src.services.scheduled_search_service import get_user_schedules

    schedules = get_user_schedules(user_id)
    _metrics.record_request((time.time() - start_time) * 1000)
    return {"schedules": schedules, "total": len(schedules)}


@router.patch("/scheduled-searches/{search_id}")
def rico_toggle_scheduled_search(
    request: Request, search_id: str, body: ScheduledSearchToggleRequest
) -> dict[str, Any]:
    """Pause or resume ONE scheduled search owned by the current user (#1249).

    Identity comes from the JWT only; the id is resolved strictly within the
    authenticated user's own schedules, so a user can never toggle (or probe
    the existence of) another user's search — unknown ids are a plain 404.
    """
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]

    from src.services.scheduled_search_service import set_schedule_enabled_by_id

    ok = set_schedule_enabled_by_id(user_id, search_id, body.enabled)
    _metrics.record_request((time.time() - start_time) * 1000)
    if not ok:
        raise HTTPException(status_code=404, detail="Scheduled search not found")
    return {"id": search_id, "enabled": body.enabled, "status": "updated"}


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

        # Pin the chat thread for every persistence/read inside this turn.
        # Sync endpoints run in a threadpool with their own context copy, so
        # the token-reset in finally is defensive tidiness, not correctness.
        from src.services.chat_session_context import (
            reset_active_chat_session,
            set_active_chat_session,
        )
        _session_token = set_active_chat_session(payload.session_id)
        try:
            result = chat_service.send_message(
                ctx=ctx,
                message=payload.message,
                operation_id=payload.operation_id,
                language=payload.language,
            )
        finally:
            reset_active_chat_session(_session_token)

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
        logger.error(
            "chat_error user=%s message_len=%d err=%s request_ref=%s",
            user_ref(ctx.user_id if "ctx" in locals() else "unknown"),
            len(payload.message) if "payload" in locals() else 0,
            safe_exc(exc),
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


# SSE response headers: no-transform stops intermediaries re-encoding the
# stream; X-Accel-Buffering disables proxy buffering (nginx-style, harmless
# elsewhere). Connection is hop-by-hop and managed by the ASGI server — never
# set it manually. Content-Length must stay absent (chunked streaming).
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _sse_done(response: Any) -> str:
    """Serialize a terminal SSE ``done`` event with a total JSON encoder.

    ``default=str`` guarantees the terminal event is always serializable: a
    stray non-JSON field (datetime, Decimal, or a pydantic model that slipped
    through) renders as its string form instead of raising ``TypeError``
    mid-stream — which the generator's ``except`` would otherwise collapse into a
    generic "Stream error", dropping the already-persisted reply from the wire.
    This is the boundary that #1210 / #1222 / #1225 each patched one field at a
    time; the encoder closes the whole class.
    """
    return f'data: {json.dumps({"type": "done", "response": response}, default=str)}\n\n'


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
        return StreamingResponse(_err(), media_type="text/event-stream", headers=SSE_HEADERS)

    user_id = user["email"]
    ctx = RicoSessionContext.for_authenticated(user_id)

    def _event_stream():
        # SSE comment line first: starts the chunked body immediately so
        # proxies flush headers and hold the connection open through the
        # first-token wait (cold provider calls can take seconds). Comment
        # lines are ignored by SSE clients per spec.
        yield ": connected\n\n"
        try:
            # Shared, transport-independent preflight: identical policy +
            # entitlement decision to the JSON /chat path. A deterministic or
            # over-quota outcome is emitted as a single done event and the AI
            # provider is never called (#1078).
            pre = chat_service.run_chat_preflight(ctx, payload.message)
            if pre.terminal is not None:
                yield _sse_done(pre.terminal)
                return

            # For non-conversational intents (job search, CV ops) fall back to the
            # full JSON response so structured data (job cards, profile preview)
            # arrives correctly. Only pure conversational replies are token-streamed.
            profile = get_profile(user_id)
            if not chat_service.should_stream_ai(ctx, payload.message, profile):
                result = chat_service.send_message(
                    ctx=ctx,
                    message=payload.message,
                    operation_id=payload.operation_id,
                    language=payload.language,
                )
                yield _sse_done(result)
                return

            # Streaming conversational-AI path (already past the entitlement gate).
            api = RicoChatAPI(persist=ctx.can_persist_profile)
            user_context = api._build_openai_context(profile, user_id=user_id)
            profile_context_str = (
                _json.dumps(user_context, ensure_ascii=False)
                if user_context else None
            )
            conversation_history = user_context.get("conversation_history", [])
            from src.rico_env import get_ai_provider
            provider = get_ai_provider()

            # Record the user turn BEFORE the provider call so the monthly usage
            # count is durable even if the client disconnects mid-stream — a
            # provider invocation must never be free of a usage record (#1078).
            api._append_chat(user_id, "user", payload.message)

            full_text: list[str] = []
            try:
                for chunk in call_openai_stream(
                    payload.message,
                    profile_context=profile_context_str,
                    provider=provider,
                    conversation_history=conversation_history,
                    language=payload.language,
                ):
                    full_text.append(chunk)
                    yield f'data: {_json.dumps({"type":"token","text":chunk})}\n\n'
            finally:
                # Persist whatever assistant text streamed — even on early client
                # disconnect (GeneratorExit) — so the transcript matches usage.
                assembled = "".join(full_text)
                if assembled:
                    try:
                        api._append_chat(user_id, "assistant", assembled)
                    except Exception as e:
                        # #1076 delta: user_ref + exception TYPE only — the
                        # guest bearer id and driver messages embedding chat
                        # text must never reach logs (tracebacks included).
                        logger.debug(
                            "chat_stream: assistant persist failed user=%s err=%s",
                            user_ref(user_id), safe_exc(e),
                        )

            done_response = {"message": assembled, "type": "conversational", "response_source": "stream"}
            if (
                pre.gate is not None
                and pre.gate.allowed
                and pre.gate.remaining is not None
                and pre.gate.remaining <= 10
            ):
                done_response["messages_remaining"] = pre.gate.remaining
                if pre.gate.limit is not None:
                    done_response["messages_limit"] = pre.gate.limit
            yield _sse_done(done_response)
        except Exception as e:
            logger.error("chat_stream_error user=%s err=%s", user_ref(user_id), safe_exc(e))
            yield f'data: {_json.dumps({"type":"error","message":"Stream error. Please try again."})}\n\n'

    # A ContextVar set here would NOT reach the generator (each SSE segment
    # runs in a fresh copy of the ASGI task's context), so the wrapper drives
    # every segment — including the finally-block assistant persist — inside
    # one Context with the thread pinned (#1193).
    from src.services.chat_session_context import run_generator_with_session
    return StreamingResponse(
        run_generator_with_session(_event_stream(), payload.session_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/chat/stream/public")
@limiter.limit("10/minute")
def rico_chat_stream_public(request: Request, payload: RicoPublicChatRequest) -> StreamingResponse:
    """Unauthenticated SSE streaming chat for public/guest users.

    Identity + anti-dodge mirror /chat/public: an unverified email never adopts a
    real account — it becomes a namespaced, non-persisting public identity used
    only to hold a *registered* user to their monthly AI cap so they cannot dodge
    it by streaming through the public endpoint. The per-IP rate limit above
    bounds anonymous guest cost and is not resettable by rotating session_id (#1078).
    """
    import json as _json
    from src.rico_openai_runtime import call_openai_stream
    from src.rico_chat_api import RicoChatAPI
    from src.repositories.profile_repo import get_profile
    from src.api.public_identity import is_safe_public_session_id

    if not payload.email and not payload.session_id:
        def _err_missing():
            yield f'data: {_json.dumps({"type":"error","message":"Invalid session."})}\n\n'
        return StreamingResponse(_err_missing(), media_type="text/event-stream", headers=SSE_HEADERS)

    # Anti-dodge: a registered user routing through the public stream with their
    # email is held to the SAME monthly AI cap as the authenticated path. The
    # email is unverified (no JWT) so it grants NO account privilege — only the cap.
    anti_dodge_terminal: dict[str, Any] | None = None
    guest_headers: Response | None = None
    if payload.email:
        from src.repositories.users_repo import get_user_by_email

        registered = get_user_by_email(payload.email)
        if registered:
            from src.services.subscription_gating import check_ai_message_allowed_for_user

            gate = check_ai_message_allowed_for_user(registered.email)
            if gate and not gate.allowed:
                anti_dodge_terminal = _strip_internal_fields(gate.to_response())
        # Namespaced public identity that cannot read/write any real profile.
        email_key = "e-" + hashlib.sha256(
            payload.email.strip().lower().encode("utf-8")
        ).hexdigest()[:40]
        ctx = RicoSessionContext.for_public(email_key)
    else:
        session_id = payload.session_id or ""
        if not is_safe_public_session_id(session_id):
            def _err_bad():
                yield f'data: {_json.dumps({"type":"error","message":"Invalid session."})}\n\n'
            return StreamingResponse(_err_bad(), media_type="text/event-stream", headers=SSE_HEADERS)
        # Server-authoritative guest identity (#1070) — mirror /chat/public.
        # The capability cookie decides the sid; the payload value is
        # correlation-only. HTTPException from the resolver becomes a JSON
        # error response carrying the resolver's cookie operations.
        from fastapi.responses import JSONResponse

        guest_headers = Response()
        guest_headers.raw_headers.clear()
        try:
            sid = _resolve_guest_sid(request, guest_headers, session_id[:64])
        except HTTPException as exc:
            err = JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
            _transfer_guest_headers(guest_headers, err)
            return err
        ctx = RicoSessionContext.for_public(sid)

    user_id = ctx.user_id

    def _event_stream():
        # See rico_chat_stream: immediate SSE comment flushes the response
        # start through buffering proxies before any heavy work runs.
        yield ": connected\n\n"
        # Registered user over their cap — refuse before any provider work.
        if anti_dodge_terminal is not None:
            yield _sse_done(anti_dodge_terminal)
            return
        try:
            # Shared, transport-independent preflight (policy gateway etc.); public
            # sessions are not per-user capped (the gate is authenticated-only).
            pre = chat_service.run_chat_preflight(ctx, payload.message)
            if pre.terminal is not None:
                yield _sse_done(_strip_internal_fields(pre.terminal))
                return

            profile = get_profile(user_id)
            if not chat_service.should_stream_ai(ctx, payload.message, profile):
                result = chat_service.send_message(
                    ctx=ctx,
                    message=payload.message,
                    operation_id=payload.operation_id,
                    language=payload.language,
                )
                yield _sse_done(_strip_internal_fields(result))
                return

            api = RicoChatAPI(persist=False)
            user_context = api._build_openai_context(profile, user_id=user_id)
            profile_context_str = (
                _json.dumps(user_context, ensure_ascii=False) if user_context else None
            )
            conversation_history = user_context.get("conversation_history", [])
            from src.rico_env import get_ai_provider
            provider = get_ai_provider()

            # Record the guest user turn before the provider call so a disconnect
            # cannot erase the record of an incurred provider invocation (#1078).
            api._append_chat(user_id, "user", payload.message)

            full_text: list[str] = []
            try:
                for chunk in call_openai_stream(
                    payload.message,
                    profile_context=profile_context_str,
                    provider=provider,
                    conversation_history=conversation_history,
                    language=payload.language,
                ):
                    full_text.append(chunk)
                    yield f'data: {_json.dumps({"type":"token","text":chunk})}\n\n'
            finally:
                assembled = "".join(full_text)
                if assembled:
                    try:
                        api._append_chat(user_id, "assistant", assembled)
                    except Exception as e:
                        # #1076 delta: user_id here is the PUBLIC session
                        # bearer id — ref + exception type only.
                        logger.debug(
                            "chat_stream_public: assistant persist failed user=%s err=%s",
                            user_ref(user_id), safe_exc(e),
                        )

            yield _sse_done({"message": assembled, "type": "conversational", "response_source": "stream"})
        except Exception as e:
            logger.error("chat_stream_public_error user=%s err=%s", user_ref(user_id), safe_exc(e))
            yield f'data: {_json.dumps({"type":"error","message":"Stream error. Please try again."})}\n\n'

    streaming_response = StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
    if guest_headers is not None:
        _transfer_guest_headers(guest_headers, streaming_response)
    return streaming_response


_GUEST_CAPABILITY_INVALID_DETAIL = {
    "code": "guest_capability_invalid",
    "message": "This guest session token is not valid. Please try again.",
}
_GUEST_CAPABILITY_UNAVAILABLE_DETAIL = {
    "code": "guest_capability_unavailable",
    "message": "Guest sessions are temporarily unavailable. Please try again later.",
}


def _resolve_guest_sid(request: Request, response: Response, correlation_sid: str | None) -> str:
    """Resolve the SERVER-AUTHORITATIVE guest sid for an unauthenticated request (#1070).

    Identity comes only from the signed capability cookie; a fresh identity is
    minted (and endorsed on *response*) when no cookie is present. The
    client-supplied *correlation_sid* carries ZERO authorization meaning — it
    is logged when it differs (one-time legacy migration / multi-tab
    observability) and never adopted as identity.

    Failure modes are distinct and fail closed (#1070 correction 5):
    invalid/expired/tampered token → 403 guest_capability_invalid (bad cookie
    cleared, self-healing next request); missing production secret → 503
    guest_capability_unavailable.
    """
    from src.api.public_identity import (
        GuestCapabilityUnavailable,
        InvalidGuestCapability,
        clear_guest_capability,
        resolve_guest_identity,
    )

    try:
        sid = resolve_guest_identity(request, response)
    except InvalidGuestCapability as exc:
        # Log the FIXED reason code only — never the token/SID/nonce/signature.
        logger.warning(
            "guest_capability_invalid path=%s reason_code=%s",
            request.url.path,
            exc.reason_code,
        )
        # FastAPI discards injected-response headers on HTTPException, so the
        # cookie clear must travel on the exception itself — the invalid
        # cookie is removed and the next request self-heals with a fresh mint.
        cleaner = Response()
        clear_guest_capability(cleaner)
        raise HTTPException(
            status_code=403,
            detail=_GUEST_CAPABILITY_INVALID_DETAIL,
            headers={"set-cookie": cleaner.headers.get("set-cookie", "")},
        )
    except GuestCapabilityUnavailable:
        logger.error("guest_capability_unavailable path=%s", request.url.path)
        raise HTTPException(status_code=503, detail=_GUEST_CAPABILITY_UNAVAILABLE_DETAIL)

    if correlation_sid and correlation_sid != sid:
        logger.info(
            "guest_correlation_mismatch path=%s (client id is correlation-only)",
            request.url.path,
        )
    # The authoritative sid is NEVER disclosed to JavaScript: identity lives
    # exclusively in the HttpOnly capability cookie. No response header/body
    # field carries it — a future frontend cannot mistake it for an id.
    return sid


def _transfer_guest_headers(src: Response, dst) -> None:
    """Copy capability Set-Cookie headers from a placeholder response onto the
    real one — appending Set-Cookie is legal HTTP, but the resolver mints at
    most one capability per request so the result carries exactly one."""
    for key, value in src.raw_headers:
        if key.decode("latin-1").lower() == "set-cookie":
            dst.raw_headers.append((key, value))


@router.post("/chat/public", response_model=RicoChatResponse)
@limiter.limit("10/minute")
def rico_chat_public(request: Request, payload: RicoPublicChatRequest, response: Response) -> RicoChatResponse:
    """Unauthenticated chat for landing page visitors.

    Supports two user identification modes:
    - session_id: for anonymous visitors (user_id = public:{session_id})
    - email: a namespaced, non-persisting public identity (user_id =
      public:e-{hash}). An unverified email never adopts a real account — it
      cannot read/write that account's profile or chat history. It is used only
      as an anti-dodge key so a registered user cannot escape their monthly AI
      cap by routing through the public endpoint.
    """
    start_time = time.time()
    request_ref = generate_error_ref()

    # Validate that either session_id or email is provided
    if not payload.email and not payload.session_id:
        raise HTTPException(status_code=422, detail="Either session_id or email must be provided")

    try:
        # Build session context. An unverified email is NEVER allowed to adopt a real
        # account identity: doing so would let anyone who knows a victim's email read that
        # victim's profile PII into the AI context, persist attacker turns into the victim's
        # chat history, and burn the victim's quota. Instead the email becomes a namespaced,
        # non-persisting public identity — its only privileged use is the anti-dodge quota gate.
        if payload.email:
            from src.repositories.users_repo import get_user_by_email

            registered = get_user_by_email(payload.email)
            # A registered user must not dodge their monthly AI-message cap by routing through
            # the public endpoint with their email. Enforce the same cap the authenticated
            # /chat path applies, keyed on the stored email. The email is unverified (no JWT),
            # so we grant NO authenticated-only privilege (profile persistence, private-job
            # visibility, account/subscription disclosure) — only the usage limit is applied.
            if registered:
                from src.services.subscription_gating import (
                    check_ai_message_allowed_for_user,
                )

                gate = check_ai_message_allowed_for_user(registered.email)
                if gate and not gate.allowed:
                    _metrics.record_request((time.time() - start_time) * 1000)
                    return RicoChatResponse(
                        **_strip_internal_fields(gate.to_response()),
                        trace_id=request_ref,
                    )

            # Namespaced public session that cannot read/write any real profile. The hash
            # keeps distinct emails in distinct public buckets without ever exposing the raw
            # email as a user_id, and for_public() forces can_persist_profile=False.
            email_key = "e-" + hashlib.sha256(
                payload.email.strip().lower().encode("utf-8")
            ).hexdigest()[:40]
            ctx = RicoSessionContext.for_public(email_key)
        else:
            # Server-authoritative guest identity (#1070): the payload
            # session_id is correlation-only; context binds to the sid inside
            # the signed capability cookie (minted here when absent).
            sid = _resolve_guest_sid(request, response, payload.session_id[:64])
            ctx = RicoSessionContext.for_public(sid)

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
    except HTTPException:
        # Deliberate policy responses (e.g. 403 guest_session_unverified) must
        # keep their status code — not be masked as a 200 error-chat message.
        _metrics.record_request((time.time() - start_time) * 1000)
        raise
    except Exception as exc:
        logger.error(
            "chat_public_error user=%s message_len=%d err=%s request_ref=%s",
            user_ref(ctx.user_id if "ctx" in locals() else "unknown"),
            len(payload.message) if "payload" in locals() else 0,
            safe_exc(exc),
            request_ref,
        )
        _metrics.record_request((time.time() - start_time) * 1000)
        return RicoChatResponse(
            message=f"I couldn't process your request. Reference: {request_ref}. Please try again or rephrase your message.",
            type="error",
            trace_id=request_ref,
        )


def _parse_chat_session_param(session_id: str | None) -> str | None:
    """Validate the optional ?session_id= query param ('default' or UUID)."""
    from src.services.chat_session_context import normalize_chat_session_id
    try:
        return normalize_chat_session_id(session_id)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="session_id must be 'default' or a UUID"
        )


@router.get("/chat/sessions")
@limiter.limit(LIMIT_CHAT)
def rico_chat_sessions(request: Request) -> dict[str, Any]:
    """List the authenticated user's chat threads (Sessions rail, #1193).

    Threads are derived from rico_chat_history — the id "default" is the
    legacy thread (rows written before multi-session existed), every other id
    is a client-minted UUID. Title is the thread's first user turn, or null
    for a thread with no user message yet (frontend shows its fallback label).
    """
    start_time = time.time()
    user = get_current_user(request)
    sessions = chat_service.list_chat_sessions(user["email"])
    _metrics.record_request((time.time() - start_time) * 1000)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/chat/history")
@limiter.limit(LIMIT_CHAT)
def rico_chat_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    before: str | None = None,
    session_id: str | None = Query(None, max_length=64),
) -> dict[str, Any]:
    """Get conversation history with pagination.

    session_id (optional): scope to one chat thread — "default" for the
    legacy thread, a UUID for a rail-created thread. Omitted = unfiltered
    (pre-session behavior, all threads mixed newest-first).
    """
    start_time = time.time()
    user = get_current_user(request)
    user_id = user["email"]
    session = _parse_chat_session_param(session_id)

    before_ts = None
    if before:
        try:
            before_ts = datetime.fromisoformat(before.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid timestamp format")

    history = chat_service.get_chat_history(
        user_id, limit=limit, before=before_ts, session_id=session,
    )

    _metrics.record_request((time.time() - start_time) * 1000)
    return {
        "messages": history,
        "total": len(history),
        "has_more": len(history) == limit,
    }


@router.delete("/chat/history", status_code=204)
@limiter.limit(LIMIT_CHAT)
def rico_clear_chat_history(
    request: Request,
    session_id: str | None = Query(None, max_length=64),
) -> None:
    """Delete chat history for the authenticated user (chat messages only).

    session_id (optional): delete one thread only ("default" or a UUID).
    Omitted = delete everything (pre-session behavior).
    """
    user = get_current_user(request)
    user_id = user["email"]
    session = _parse_chat_session_param(session_id)
    chat_service.clear_chat_history(user_id, session_id=session)


@router.get("/operations/{operation_id}")
@limiter.limit(LIMIT_CHAT)
def rico_operation_status(request: Request, operation_id: str) -> dict[str, Any]:
    """Read-only status of a job-search operation owned by the current user.

    Lets the command surface WAIT on a slow search (poll → recover the late
    result from chat history) instead of blindly re-sending it after the
    client-side timeout — the write path stays the chat endpoints; this
    route never starts, retries, or mutates a search.
    """
    user = get_current_user(request)
    if not (8 <= len(operation_id) <= 80):
        raise HTTPException(status_code=404, detail="Operation not found")

    from src.services.operation_state import (
        TERMINAL_STATUSES,
        expire_if_orphaned,
        get_operation,
        is_actively_running,
        is_stale,
        operation_age_seconds,
    )

    operation = get_operation(user["email"], operation_id)
    if not operation or operation.get("type") != "job_search":
        raise HTTPException(status_code=404, detail="Operation not found")
    operation = expire_if_orphaned(user["email"], operation)

    # Deliberately narrow response: status/ownership metadata ONLY — never
    # the stored role/query text, provider payloads, or any profile data.
    status = str(operation.get("status") or "")
    return {
        "operation_id": str(operation.get("operation_id")),
        "status": status,
        "active": is_actively_running(operation),
        "stale": is_stale(operation),
        "terminal": status in TERMINAL_STATUSES,
        "result_count": operation.get("result_count"),
        "age_seconds": operation_age_seconds(operation),
    }


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

# #1077: the user-callable paid-provider probe (GET /openai-smoke) was
# REMOVED. Every authenticated self-signup account could trigger real
# OpenAI/DeepSeek calls (with fallback-chain retries) outside any plan
# accounting, via a GET the browser could prefetch. Liveness stays on the
# free public /health/ai-provider below; active provider probes run only
# from owner-approved server-side release workflows.


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

    # Explicit clears for nullable NUMERIC fields. Pydantic gives an omitted
    # field and an explicit JSON null the same default (None), so
    # `model_fields_set` is the only way to tell "leave unchanged" (omitted)
    # apart from "clear this value" (explicit null). Only these three fields
    # support clearing; every other field keeps omitted==null==unchanged.
    clear_fields = [
        f
        for f in ("salary_expectation_aed", "minimum_salary_aed", "years_experience")
        if f in body.model_fields_set and getattr(body, f) is None
    ]

    # When the user explicitly sets target_roles or skills, bump normalization_version
    # to the current version so get_profile does not re-normalize and silently mutate
    # adjacent fields (e.g. a skills save triggering normalization that changes
    # target_roles). Do NOT call normalize_profile_updates — user input is saved as-is.
    if "target_roles" in updates or "skills" in updates:
        from src.role_normalization import NORMALIZATION_VERSION
        updates["normalization_version"] = NORMALIZATION_VERSION

    # #1076: field names only — updates carry contact/career values.
    logger.info("update_profile endpoint: user=%s %s", user_ref(user_id), safe_fields(updates))

    profile_for_warnings = None
    if updates or clear_fields:
        # Expected post-write state for the durable-truth verifier: set values
        # plus explicit nulls for cleared fields.
        expected_state = {**updates, **{k: None for k in clear_fields}}
        # Durable-truth contract (#764): a user-directed profile write must
        # persist to the canonical DB or fail the request. require_db=True
        # raises instead of silently falling back to the process-local mirror,
        # and the mirror is only updated after the DB commit — so a failure
        # here leaves no phantom state and the client gets a retryable error.
        try:
            profile_for_warnings = upsert_profile(
                user_id, updates, require_db=True, clear_fields=clear_fields,
            )
        except Exception as e:
            # #1076 delta: no raw id, no traceback — psycopg2 error strings can
            # re-emit the bound profile values this endpoint just tried to save.
            # The ref ties the user-visible toast to this exact log line so a
            # live failure is diagnosable without guessing (2026-07-18 smoke).
            error_ref = generate_error_ref()
            logger.error(
                "profile_update persistence failed user=%s ref=%s err=%s",
                user_ref(user_id), error_ref, safe_exc(e),
            )
            raise HTTPException(
                status_code=503,
                detail=f"Profile update could not be saved. Please try again. (ref {error_ref})",
            )
        confirmed = _MUTATION_CONFIRMATION_GUARD.confirm(
            MutationResult(success=True),
            verifier=lambda: _profile_updates_visible(user_id, expected_state),
            success_en="confirmed",
            success_ar="confirmed",
            failure_en="failed",
            failure_ar="failed",
        ) == "confirmed"
        if not confirmed:
            error_ref = generate_error_ref()
            logger.error(
                "profile_update confirmation failed user=%s ref=%s",
                user_ref(user_id), error_ref,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Profile update could not be confirmed. Please try again. (ref {error_ref})",
            )
        logger.info("profile_update user=%s %s", user_ref(user_id), safe_fields(expected_state))
    else:
        logger.warning("profile_update no fields user=%s", user_ref(user_id))
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
        "updated_fields": list(updates.keys()) + clear_fields,
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

def _stored_document_with_hash_exists(user_id: str, content_hash: str) -> bool:
    """True when these exact bytes are already stored for this user.

    Checked across the confirmable doc types because the upload's real type is
    not classified yet at quota time. Returns False on any store failure so the
    quota gate still applies — fail closed on the limit, never open.
    """
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return False
        return any(
            db.find_user_document_by_hash(user_id, doc_type, content_hash)
            for doc_type in ("cv", "cover_letter", "other")
        )
    except Exception:
        logger.warning("upload_dedupe_precheck_failed user=%s", user_ref(user_id))
        return False


@router.post("/upload-cv")
@limiter.limit(LIMIT_UPLOAD)
async def rico_upload_cv(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    user_id: str | None = None,
    form_user_id: str | None = Form(None, alias="user_id"),
) -> dict[str, Any]:
    """Upload and parse CV file (PDF only)."""
    start_time = time.time()
    request_ref = generate_error_ref()
    resolved_user_id = _resolve_upload_user_id(request, user_id, form_user_id, response)

    try:
        # Layered size enforcement (#1080): the app-level ingress middleware
        # caps the raw request body before multipart parsing; the declared-size
        # check below rejects cheaply when the client is honest; and the
        # bounded read enforces the cap on the actual bytes without ever
        # materializing more than the limit plus one chunk.
        declared_size = getattr(file, "size", None)
        if isinstance(declared_size, int) and declared_size > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=_too_large_message(_MAX_DOC_BYTES, is_image=False),
            )

        from src.api.upload_limits import read_upload_bounded
        data = await read_upload_bounded(
            file,
            _MAX_UPLOAD_BYTES,
            detail=_too_large_message(_MAX_DOC_BYTES, is_image=False),
        )
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

        # Per-plan CV storage quota — enforced HERE, after the real magic-byte
        # format is known, and ONLY for document uploads. Three exemptions, all
        # fail-safe:
        #   • Images are transient chat attachments analysed in-session (a job/
        #     recruiter screenshot, an offer-letter photo). They are never
        #     written to user_documents, so they must never be charged against —
        #     or blocked by — the CV storage limit (chat attachment ≠ CV upload).
        #   • An exact re-upload of bytes already stored for this user consumes
        #     no storage, so the limit must not block it (dedupe-before-quota,
        #     #960/#1245): a user at their limit can still re-upload their own
        #     saved CV to refresh its parse — the exact flow Rico suggests.
        #   • Guest/public sessions (public:*) have no plan record.
        # Classifying the format first is what lets the image exemption key on
        # real magic bytes, never the client-supplied extension/MIME.
        if (
            upload_format != "image"
            and not is_valid_public_user_id(resolved_user_id)
            and not _stored_document_with_hash_exists(resolved_user_id, content_hash)
        ):
            from src.services.subscription_gating import enforce_document_quota
            enforce_document_quota(resolved_user_id, "cv")

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

        # ── Format integrity: reject .pdf files without PDF magic bytes ─────────
        # A file renamed to .pdf must not be silently accepted if bytes are not PDF.
        # This prevents garbage injection from fake PDFs.
        if (
            safe_name.lower().endswith(".pdf")
            and classification.file_format != "pdf"
            # Executables are rejected with a hard 422 below — never softened to a
            # 200 "invalid_signature" (a disguised .exe/.pdf must fail closed).
            and classification.file_format != "executable"
        ):
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.warning(
                "cv_upload_format_mismatch user=%s filename=%s declared_format=pdf detected_format=%s request_ref=%s",
                resolved_user_id, safe_name, classification.file_format, request_ref,
            )
            return {
                "ok": False,
                "status": "invalid_signature",
                "document_type": doc_type,
                "file_format": classification.file_format,
                "filename": safe_name,
                "message": (
                    "This file is not a valid PDF. "
                    "Please upload a text-based PDF or Word document."
                ),
            }

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
                # Security: if the reclassified text is an identity document,
                # reject immediately — BEFORE any durable persistence, memory
                # persistence, extracted-text response, or preview logging.
                # An image of a passport with successful OCR must never have its
                # text stored or echoed.
                if text_classification.document_type == "identity_document":
                    _metrics.record_request((time.time() - start_time) * 1000)
                    logger.warning(
                        "doc_image_identity_blocked user=%s filename=%s request_ref=%s",
                        resolved_user_id, safe_name, request_ref,
                    )
                    return {
                        "ok": False,
                        "status": "rejected",
                        "document_type": "identity_document",
                        "message": (
                            "This document appears to be a passport or identity document. "
                            "For your security it was not saved and your profile was not changed. "
                            "Please upload a CV or resume instead."
                        ),
                    }
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
            logger.info(
                "doc_image_ocr_failed user=%s filename=%s chars=%d request_ref=%s",
                resolved_user_id, safe_name, len(extracted or ""), request_ref,
            )
            # Store the image context even without text so follow-up messages
            # ("extract text", "describe image") know an image was uploaded and
            # can answer honestly instead of "no document on record".
            try:
                from src.repositories.uploaded_document_repo import set_last_uploaded_document
                set_last_uploaded_document(
                    resolved_user_id,
                    extracted_text="",
                    filename=safe_name,
                    document_type="image",
                    display_label=classification.display_label or "Image",
                    source="image",
                    request_ref=request_ref,
                )
            except Exception:
                pass
            # Finding 4 (review correction): this branch previously updated ONLY
            # the durable store above, never `recent_context` — so a PRIOR
            # attachment (e.g. an identity document, which DOES get written to
            # recent_context on its own success path just above) stayed the
            # "latest" one seen by `_get_last_uploaded_document` (which reads
            # recent_context first). "What was that?" after this OCR failure
            # answered about the STALE OLDER attachment, not this newest upload
            # — the exact "answered from an older context" defect this PR's own
            # transcript describes. #1364 must deliver this without depending
            # on another PR, so this newer (OCR-failed) upload now fully
            # replaces recent_context's last_uploaded_document too, same as the
            # successful-classification branch above.
            if not is_valid_public_user_id(resolved_user_id):
                try:
                    from src.rico_memory import RicoMemoryStore
                    _mem = RicoMemoryStore()
                    _rctx = _mem.get_context(resolved_user_id, "recent_context") or {}
                    _rctx["last_uploaded_document"] = {
                        "document_type": "image",
                        "display_label": classification.display_label or "Image",
                        "filename": safe_name,
                        "source": "image",
                        "confidence": 0.0,
                        "is_sensitive": False,
                        "extracted_text": "",
                        "suggested_actions": [],
                    }
                    _mem.set_context(resolved_user_id, "recent_context", _rctx)
                except Exception:
                    pass
            # Honest OCR-failure response: no readable text exists, so none of
            # the image actions (Describe / Extract text / Save as target job /
            # Score against my CV) can be honored — offer NONE of them, and say
            # plainly what happened and what the user can do instead.
            resp = _classification_response(classification, safe_name)
            resp["message"] = (
                f"I received your image ({safe_name}), but I couldn't extract any readable "
                "text from it. I can't visually describe images or retry the text "
                "extraction on my own yet. If it shows a job posting or document, try a "
                "clearer screenshot — or paste the text directly into the chat."
            )
            # No extracted_text field at all: the vision-fallback contract
            # (tests/unit/test_upload_image_vision.py) requires its absence when
            # OCR produced nothing — an empty-string field would be noise.
            resp.pop("extracted_text", None)
            resp["suggested_actions"] = []
            return resp

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
            logger.error(
                "cv_upload_parse_error ref=%s user=%s filename_len=%d bytes=%d err=%s",
                request_ref, user_ref(resolved_user_id), len(safe_name or ""),
                len(data), safe_exc(exc),
            )
            # Use shared parse-quality contract to determine specific failure type
            from src.cv_parse_quality import validate_parse_quality, ParseOutcome

            # Try to determine if this is a format vs parse issue
            quality_result = validate_parse_quality(
                text="",
                extracted_chars=0,
                extraction_quality=None,
                parser_exception=exc,
            )

            status = "parse_failed" if quality_result.outcome == ParseOutcome.PARSE_FAILED else "error"
            return {
                "ok": False,
                "status": status,
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

        # Readability gate: require meaningful readable text before preview_ready
        # Use shared parse-quality contract for conservative validation
        from src.cv_parse_quality import validate_parse_quality, ParseOutcome

        quality_result = validate_parse_quality(
            text=parsed.get("text", ""),
            extracted_chars=parsed.get("extracted_chars", 0),
            extraction_quality=parsed.get("extraction_quality", "unknown"),
            parser_exception=None,  # Parser already succeeded here
        )

        if not quality_result.is_readable:
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.info(
                "cv_upload_unreadable user=%s filename=%s outcome=%s chars=%d printable_ratio=%.2f request_ref=%s",
                resolved_user_id, safe_name, quality_result.outcome,
                quality_result.extracted_chars, quality_result.printable_ratio, request_ref,
            )
            return {
                "ok": False,
                "status": "unreadable",
                "document_type": cv_doc_type,
                "file_format": classification.file_format,
                "filename": safe_name,
                "message": (
                    "I couldn't extract enough readable text from this file. "
                    "It may be a scan, image-only PDF, or corrupt file. "
                    "Please upload a text-based PDF or Word document."
                ),
            }

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
            # #1070: for guest sessions resolved_user_id is the SERVER-minted
            # identity, which must never reach page JavaScript — authorization
            # lives only in the HttpOnly capability cookie. Guests get no
            # identity echo; authenticated uploads keep the field unchanged.
            "user_id": None if is_valid_public_user_id(resolved_user_id) else resolved_user_id,
            "upload_id": upload_id,
            "warnings": cv_warnings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "cv_upload_error user=%s filename_len=%d err=%s request_ref=%s",
            user_ref(resolved_user_id),
            len(safe_name) if "safe_name" in locals() else 0,
            safe_exc(exc),
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
    response: Response,
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    """Confirm and save CV profile preview to permanent profile.

    This endpoint accepts JSON, so declaring a Form(...) parameter here would
    force FastAPI to expect an embedded "body" key. Keep user_id in the query
    string for public sessions and resolve auth identity from the cookie.
    """
    start_time = time.time()
    request_ref = generate_error_ref()
    resolved_user_id = _resolve_upload_user_id(request, user_id, None, response)

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

        # Confirmation defense-in-depth: reject artifacts with unreadable cv_text.
        # Use shared parse-quality contract for consistency. For a CV artifact
        # the check runs even when cv_text is missing/empty —
        # validate_artifact_quality(None) exists to flag exactly that state
        # (PARSE_FAILED), but the previous `is not None` guard skipped it, so an
        # empty-text CV confirmed "successfully": the My Files row and skills
        # persisted while rico_profiles.cv_text stayed NULL, leaving chat and
        # matching with a CV they could not actually read. Guest confirms
        # (artifact is None) and non-CV documents keep the previous behaviour.
        _is_cv_artifact = artifact is not None and artifact.get("doc_type") == "cv"
        if confirmed_cv_text is not None or _is_cv_artifact:
            from src.cv_parse_quality import validate_artifact_quality

            quality_result = validate_artifact_quality(confirmed_cv_text)
            if not quality_result.is_readable:
                logger.warning(
                    "cv_confirm_unreadable_artifact user=%s upload_id=%s filename=%s outcome=%s chars=%d printable_ratio=%.2f request_ref=%s",
                    resolved_user_id, payload.upload_id, payload.filename,
                    quality_result.outcome, quality_result.extracted_chars,
                    quality_result.printable_ratio, request_ref,
                )
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "status": "cv_confirmation_required",
                        "message": "The uploaded file didn't contain enough readable text. Please upload a text-based PDF or Word document.",
                    },
                )

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
                logger.error(
                    "cv_confirm_doc_save_failed user=%s err=%s request_ref=%s",
                    user_ref(resolved_user_id), safe_exc(_doc_exc), request_ref,
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
            logger.error(
                "cv_confirm_profile_persist_failed user=%s err=%s request_ref=%s",
                user_ref(resolved_user_id), safe_exc(_profile_exc), request_ref,
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
        logger.error(
            "cv_profile_confirm_error user=%s filename_len=%d err=%s request_ref=%s",
            user_ref(resolved_user_id),
            len(payload.filename or ""),
            safe_exc(exc),
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
