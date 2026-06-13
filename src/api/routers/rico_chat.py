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
from fastapi.responses import StreamingResponse
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
from src.models.onboarding import ONBOARDING_IN_PROGRESS
from src.rico_agent import RicoAgent
from src.rico_chat_api import generate_error_ref
from src.rico_env import get_ai_provider
from src.rico_hf_client import generate_text, is_available as hf_ok
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_openai_runtime import call_openai_minimal
from src.schemas.chat import RicoChatResponse, RicoSessionContext
from src.services import chat_service
from src.agent.responses.schema import build_error_response

logger = logging.getLogger(__name__)
_UTC = timezone.utc

# Constants
_UNSAFE_CHARS_RE = re.compile("[<>\"';\\x00-\\x1f\\x7f\\u202a-\\u202e\\u2066-\\u2069]")
_PDF_MAGIC = b"%PDF"
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/api/v1/rico", tags=["rico"])


def _is_production() -> bool:
    """Check if running in production environment."""
    return (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower() in {
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


class ConfirmCVProfileRequest(BaseModel):
    """Request to confirm and save CV profile preview."""
    preview: dict[str, Any] = Field(..., description="Profile preview data to confirm")
    filename: str = Field(..., description="Original CV filename")



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


# Thin wrappers keep the router on one adapter path while preserving stable patch points.
def get_profile(user_id: str):
    return profile_repo.get_profile(user_id)


def upsert_profile(user_id: str, updates: dict[str, Any]):
    return profile_repo.upsert_profile(user_id=user_id, updates=updates)


def list_saved_searches(user_id: str, limit: int = 20):
    return profile_repo.list_saved_searches(user_id, limit=limit)


def save_search(user_id: str, query: str, filters: dict[str, Any]):
    return profile_repo.save_search(user_id, query, filters)


def delete_search(user_id: str, search_id: str):
    return profile_repo.delete_search(user_id, search_id)


def mark_onboarding_complete(user_id: str) -> None:
    onboarding_repo.mark_onboarding_complete(user_id)


def _is_valid_public_user_id(value: str) -> bool:
    """Validate that a user_id matches the expected guest session format."""
    return is_valid_public_user_id(value)


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

    if not _is_valid_public_user_id(user_id):
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
            if not decision.should_use_ai:
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
        updates["preferred_cities"] = [c.strip() for c in body.preferred_cities if c.strip()]
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

    if updates:
        upsert_profile(user_id, updates)
        logger.info("profile_update user=%s fields=%s", user_id, list(updates.keys()))
    else:
        logger.warning("profile_update no fields user=%s", user_id)

    return {"status": "ok", "updated_fields": list(updates.keys())}


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
    if not _is_valid_public_user_id(resolved_user_id):
        from src.services.subscription_gating import enforce_document_quota
        enforce_document_quota(resolved_user_id, "cv")

    try:
        data = await file.read()
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
        if not data:
            raise HTTPException(status_code=422, detail="Uploaded file is empty")
        if not data.startswith(_PDF_MAGIC):
            raise HTTPException(status_code=422, detail="Only PDF files are accepted")

        safe_name = _safe_filename(file.filename)

        # Parse CV with defensive handling for dataclass vs dict return
        try:
            parsed_raw = chat_service.parse_cv(data, filename=safe_name)

            if hasattr(parsed_raw, "to_dict"):
                parsed = parsed_raw.to_dict()
            elif isinstance(parsed_raw, dict):
                parsed = parsed_raw
            else:
                raise TypeError(f"Unexpected CV parser result type: {type(parsed_raw)}")
        except Exception as exc:
            logger.exception(
                "cv_upload_parse_error ref=%s user=%s filename=%s bytes=%d error=%s",
                request_ref,
                resolved_user_id,
                safe_name,
                len(data),
                str(exc),
            )
            return {
                "ok": False,
                "status": "error",
                "error_ref": request_ref,
                "message": (
                    f"CV upload failed. Reference: {request_ref}. "
                    "I could not read this PDF. Please try another text-based PDF under 10 MB."
                ),
            }

        # Log CV upload details for debugging
        logger.info(
            "cv_upload user=%s filename=%s doc_type=%s quality=%s chars=%d skills=%d request_ref=%s",
            resolved_user_id,
            safe_name,
            "unknown",  # Will be updated after detection
            parsed.get("extraction_quality", "unknown"),
            parsed.get("extracted_chars", 0),
            len(parsed.get("skills", [])),
            request_ref,
        )

        # Detect document type to prevent company profiles from being treated as CVs
        from src.cv_parser import CVParser
        try:
            parser = CVParser()
            if hasattr(parser, "detect_document_type"):
                doc_type = parser.detect_document_type(parsed.get("text", ""))
            else:
                # Fallback if detect_document_type doesn't exist in production
                logger.warning(
                    "cv_upload_detect_method_missing ref=%s user=%s filename=%s",
                    request_ref,
                    resolved_user_id,
                    safe_name,
                )
                doc_type = "cv"  # Default to CV if method doesn't exist
        except Exception as exc:
            logger.exception(
                "cv_upload_detect_error ref=%s user=%s filename=%s error=%s",
                request_ref,
                resolved_user_id,
                safe_name,
                str(exc),
            )
            doc_type = "cv"  # Default to CV on detection error

        # Update log with detected document type
        logger.info(
            "cv_upload_detected user=%s filename=%s doc_type=%s quality=%s chars=%d skills=%d request_ref=%s",
            resolved_user_id,
            safe_name,
            doc_type,
            parsed.get("extraction_quality", "unknown"),
            parsed.get("extracted_chars", 0),
            len(parsed.get("skills", [])),
            request_ref,
        )

        # Only reject confirmed company profiles — "unknown" passes through so
        # sparse-but-valid CVs (few section headers) are not incorrectly rejected.
        if doc_type == "company_profile":
            _metrics.record_request((time.time() - start_time) * 1000)
            logger.warning(
                "cv_upload_rejected user=%s filename=%s doc_type=%s reason=not_cv request_ref=%s",
                resolved_user_id,
                safe_name,
                doc_type,
                request_ref,
            )
            return {
                "ok": False,
                "status": "rejected",
                "document_type": doc_type,
                "message": (
                    "This document looks like a company profile, not a personal CV/resume. "
                    "I did not update your personal job profile. "
                    "Please upload a personal CV or resume."
                ),
                "parsed": parsed,
            }

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

        _metrics.record_request((time.time() - start_time) * 1000)
        logger.info(
            "cv_upload_preview user=%s filename=%s quality=%s preview_ready request_ref=%s",
            resolved_user_id,
            safe_name,
            parsed.get("extraction_quality", "unknown"),
            request_ref,
        )

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

        # Update permanent profile
        upsert_profile(user_id=resolved_user_id, updates=profile_updates)
        record_profile_optimization_usage(resolved_user_id)

        # Only mark onboarding complete for authenticated users (not public sessions)
        if not is_valid_public_user_id(resolved_user_id):
            mark_onboarding_complete(resolved_user_id)

        # Save document record for the file manager (authenticated users only)
        if not is_valid_public_user_id(resolved_user_id):
            try:
                from src.rico_db import RicoDB as _RicoDB
                _doc_db = _RicoDB()
                if _doc_db.available:
                    skills = profile_updates.get("skills") or []
                    _doc_db.save_user_document(
                        user_id=resolved_user_id,
                        filename=payload.filename,
                        original_filename=payload.filename,
                        doc_type="cv",
                        file_size=0,
                        skills_count=len(skills),
                        skills_json=list(skills),
                        years_experience=profile_updates.get("years_experience"),
                        current_role=profile_updates.get("current_role"),
                        is_primary=True,
                    )
            except Exception as _doc_exc:
                logger.warning("cv_confirm_doc_save_failed user=%s error=%s", resolved_user_id, str(_doc_exc))

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
    return chat_service.handle_telegram_update(update)


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
