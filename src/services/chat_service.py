"""
src/services/chat_service.py
Thin service adapter for Rico AI chat, CV parsing, and webhook flows.
Does not modify Rico internals — delegates directly to existing Rico modules
via deferred imports to avoid eager loading of heavy dependencies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from src.rico.intent import IntentRouter
from src.schemas.chat import RicoSessionContext

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_intent_router = IntentRouter()

# ── Jotform field normalisation ───────────────────────────────────────────────
# Maps raw Jotform label strings (as sent by the form or the Agent "Send API
# Request" test tool) to the snake_case keys that
# rico_jotform_webhook.map_jotform_payload() expects.

_JOTFORM_FIELD_MAP: Dict[str, str] = {
    "Full Name":              "full_name",
    "Name":                   "full_name",
    "Email":                  "email",
    "Email Address":          "email",
    "Phone":                  "phone",
    "Phone Number":           "phone",
    "Telegram Username":      "telegram_username",
    "Target Job Titles":      "target_roles",
    "Target Roles":           "target_roles",
    "Preferred Cities":       "preferred_cities",
    "Preferred Location":     "preferred_cities",
    "Salary Expectation (AED)": "salary_expectation_aed",
    "Minimum Salary (AED)":   "minimum_salary_aed",
    "Skills":                 "skills",
    "Industries":             "industries",
    "Visa Status":            "visa_status",
    "Notice Period":          "notice_period",
    "Years of Experience":    "years_experience",
    "Autonomy Level":         "autonomy_level",
    "Match Strictness":       "match_strictness",
    "Communication Style":    "communication_style",
    "CV Upload":              "cv_upload",
}

# Keys that appear in test/agent payloads but carry no profile data.
_NON_PROFILE_KEYS = frozenset({
    "formID", "form_id", "formId",
    "consent", "ip",
    "submissionID", "submission_id",
})


def _normalize_jotform_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw Jotform field labels to snake_case keys.

    If the payload already has a 'pretty' key it is already in the correct
    format; return it unchanged.  Otherwise remap every key using
    _JOTFORM_FIELD_MAP (with a generic fallback of lower().replace(' ', '_')).
    """
    if "pretty" in payload:
        return payload

    normalized: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _NON_PROFILE_KEYS:
            normalized[key] = value
        else:
            target = _JOTFORM_FIELD_MAP.get(key) or key.lower().replace(" ", "_")
            normalized[target] = value

    return normalized


def _has_user_data(payload: Dict[str, Any]) -> bool:
    """Return True only if a stable unique identifier (email or telegram_username) is present.

    full_name / name are not unique and cannot serve as a user_id, so payloads
    containing only a name are treated as test/agent probes and short-circuited.
    """
    answers = payload.get("pretty", payload)
    return bool(answers.get("email") or answers.get("telegram_username"))


# ── Public service functions ──────────────────────────────────────────────────

def send_message(
    ctx: RicoSessionContext,
    message: str,
    operation_id: str | None = None,
) -> Dict[str, Any]:
    """Policy Gateway → IntentRouter → legacy classifier."""
    from src.repositories.profile_repo import get_profile
    from src.services.operation_state import build_status_response, is_status_followup

    if is_status_followup(message):
        status_response = build_status_response(ctx.user_id)
        if status_response is not None:
            return status_response

    profile = get_profile(ctx.user_id)
    profile_present = profile is not None

    # ── Policy Gateway pre-filter ─────────────────────────────────────────────
    # Handles unsupported external tools and subscription queries deterministically
    # before any AI or legacy routing touches the message.
    from src.rico.policy import classify_request
    policy = classify_request(message, has_auth=(ctx.auth_type == "authenticated"))

    if policy.route == "unsupported":
        return _unsupported_tool_response(policy)

    if policy.route == "clarification" and str(policy.reason).startswith("conflicting_domains:"):
        return _mixed_tool_clarification_response(policy)

    if policy.route == "account_service":
        return _account_service_response(ctx)

    # ── Existing routing unchanged ────────────────────────────────────────────
    decision = _intent_router.route(
        message=message,
        user_id=ctx.user_id,
        profile_context_present=profile_present,
    )

    if decision.should_use_ai:
        return _conversational_ai_reply(ctx=ctx, message=message, profile=profile)

    return _legacy_send_message(ctx=ctx, message=message, operation_id=operation_id)


def _unsupported_tool_response(policy: Any) -> Dict[str, Any]:
    """Deterministic response for external integrations Rico doesn't support."""
    tool_name = str(getattr(policy, "tool", "") or "external_tool")
    msg = _unsupported_tool_message(policy)
    return {
        "type": "unsupported_tool",
        "message": msg,
        "intent": "unsupported",
        "response_source": "policy_gateway",
        "tool": tool_name,
        "tool_available": False,
        "domain": getattr(getattr(policy, "domain", None), "value", "unsupported_tool"),
        "reason": getattr(policy, "reason", "unsupported_tool"),
        "options": _unsupported_tool_options(policy),
        "next_action": _unsupported_tool_next_action(policy),
    }


def _unsupported_tool_message(policy: Any) -> str:
    domain_value = getattr(getattr(policy, "domain", None), "value", "")
    fallback = policy.alternative_suggestion or (
        "I can't access that external integration from Rico. "
        "You can upload or paste the relevant information and I'll organise it."
    )

    messages = {
        "email_gmail_request": (
            "I can't access your Gmail or email inbox directly from Rico yet. "
            "Paste a recruiter email, upload an export, or manually add the application details and I can organize the timeline, status, and follow-up."
        ),
        "linkedin_request": (
            "I can't read your LinkedIn profile, messages, or inbox directly from Rico yet. "
            "Paste the profile text, share a public profile URL, or paste a job/message and I can tailor your profile, draft a reply, or track the opportunity."
        ),
        "calendar_request": (
            "I can't access your calendar or book meetings directly from Rico yet. "
            "Tell me the interview time, deadline, or availability window and I can keep the application context and next step clear."
        ),
        "whatsapp_request": (
            "I can't send or receive WhatsApp messages from Rico yet. "
            "Use Telegram notifications if enabled, or paste the WhatsApp message here and I can draft a reply or update the application status."
        ),
    }
    return messages.get(domain_value, fallback)


def _unsupported_tool_options(policy: Any) -> list[Dict[str, Any]]:
    domain_value = getattr(getattr(policy, "domain", None), "value", "")
    common = [
        {
            "action": "show_applications",
            "label": "Open Application Flow",
            "message": "show my applications",
        },
        {
            "action": "find_jobs",
            "label": "Find UAE jobs",
            "message": "find live jobs for my target role",
        },
    ]
    by_domain: dict[str, list[Dict[str, Any]]] = {
        "email_gmail_request": [
            {
                "action": "paste_email",
                "label": "Paste email text",
                "message": "I will paste the recruiter email here",
            },
            {
                "action": "manual_add_application",
                "label": "Add application manually",
                "message": "I want to add an application manually",
            },
        ],
        "linkedin_request": [
            {
                "action": "paste_linkedin_profile",
                "label": "Paste LinkedIn text",
                "message": "I will paste my LinkedIn profile text here",
            },
            {
                "action": "draft_linkedin_reply",
                "label": "Draft LinkedIn reply",
                "message": "I will paste the LinkedIn message here",
            },
        ],
        "calendar_request": [
            {
                "action": "record_interview_time",
                "label": "Record interview time",
                "message": "I want to record an interview time",
            },
            {
                "action": "draft_availability",
                "label": "Draft availability reply",
                "message": "draft a reply with my availability",
            },
        ],
        "whatsapp_request": [
            {
                "action": "paste_whatsapp_message",
                "label": "Paste WhatsApp text",
                "message": "I will paste the WhatsApp message here",
            },
            {
                "action": "telegram_settings",
                "label": "Use Telegram alerts",
                "message": "enable telegram notifications",
            },
        ],
    }
    return by_domain.get(domain_value, []) + common


def _unsupported_tool_next_action(policy: Any) -> str:
    domain_value = getattr(getattr(policy, "domain", None), "value", "")
    return {
        "email_gmail_request": "paste_email_or_add_application",
        "linkedin_request": "paste_linkedin_context",
        "calendar_request": "provide_schedule_details",
        "whatsapp_request": "paste_message_or_use_telegram",
    }.get(domain_value, "provide_manual_context")


def _mixed_tool_clarification_response(policy: Any) -> Dict[str, Any]:
    """Clarify mixed requests that combine unsupported external access with a supported action."""
    return {
        "type": "clarification",
        "message": (
            "That request mixes an unavailable external tool with a Rico action. "
            "I can't access the external account directly, but I can still help if you choose the path."
        ),
        "intent": "mixed_request",
        "response_source": "policy_gateway",
        "reason": getattr(policy, "reason", "conflicting_domains"),
        "options": [
            {
                "action": "continue_without_external_tool",
                "label": "Continue in Rico",
                "message": "find live jobs for my target role",
            },
            {
                "action": "paste_external_context",
                "label": "Paste external details",
                "message": "I will paste the email, LinkedIn, calendar, or WhatsApp details here",
            },
            {
                "action": "show_applications",
                "label": "Open Application Flow",
                "message": "show my applications",
            },
        ],
        "next_action": "choose_supported_path",
    }


def _account_service_response(ctx: RicoSessionContext) -> Dict[str, Any]:
    """Return subscription status (authenticated) or login prompt (public/unauthenticated)."""
    if ctx.auth_type != "authenticated":
        return {
            "type": "login_required",
            "message": "Please log in to view your subscription and account details.",
            "intent": "account_service",
            "response_source": "policy_gateway",
        }

    try:
        from src.subscription_plans import resolve_effective_user_plan
        resolved = resolve_effective_user_plan(ctx.user_id)
        sub = resolved.subscription
        is_active = resolved.is_active
        limit = sub.entitlements.monthly_ai_message_limit

        if is_active and resolved.plan:
            name = resolved.plan.name
            price = resolved.plan.price_monthly
            currency = resolved.plan.currency
            end = sub.current_period_end
            end_str = f"{end.day} {end.strftime('%b %Y')}" if end else "—"
            msg = (
                f"You are on the **{name}** plan ({price} {currency}/mo) — active. "
                f"Current period ends {end_str}. "
                f"Monthly AI message limit: {limit:,}."
            )
        else:
            msg = (
                f"You are on the **Free** plan — {limit} AI messages per month. "
                "Upgrade to Pro (50 AED/mo) or Premium (150 AED/mo) for higher limits."
            )

        return {
            "type": "subscription_status",
            "message": msg,
            "intent": "account_service",
            "response_source": "policy_gateway",
            "plan": sub.plan.value,
            "is_active": is_active,
        }
    except Exception:
        logger.warning("policy_gateway: subscription lookup failed for user=%s", ctx.user_id[:8])
        return {
            "type": "subscription_status",
            "message": (
                "I couldn't retrieve your subscription status right now. "
                "Please visit /subscription to check."
            ),
            "intent": "account_service",
            "response_source": "policy_gateway",
        }


def _legacy_send_message(
    ctx: RicoSessionContext,
    message: str,
    operation_id: str | None = None,
) -> Dict[str, Any]:
    """Run the existing Rico chat pipeline unchanged."""
    from src.rico_chat_api import RicoChatAPI

    return RicoChatAPI(persist=ctx.can_persist_profile).process_message(
        user_id=ctx.user_id,
        message=message,
        operation_id=operation_id,
    )


def _conversational_ai_reply(
    *,
    ctx: RicoSessionContext,
    message: str,
    profile: Any,
) -> Dict[str, Any]:
    """Use the existing Rico conversational AI fallback path directly."""
    from src.rico_chat_api import RicoChatAPI

    result = RicoChatAPI(persist=ctx.can_persist_profile).answer_conversationally(
        user_id=ctx.user_id,
        message=message,
        profile=profile,
    )
    result["response_source"] = result.get("response_source") or "ai_router"
    result["intent"] = "conversational"
    return result


def parse_cv(data: bytes, filename: str = "cv.pdf") -> Dict[str, Any]:
    """Parse CV bytes and return structured ParsedCV dict via CVParser."""
    from src.cv_parser import CVParser
    return CVParser().parse_bytes(data, filename=filename).to_dict()


def handle_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch an incoming Telegram update to the Rico webhook handler."""
    from src.rico_telegram_webhook import process_telegram_update
    return process_telegram_update(update)


def handle_github_event(event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch an incoming GitHub webhook event.

    Supported events: push, pull_request, issues, ping.
    Unrecognised events are acknowledged but not processed.
    """
    logger.info("github_webhook: event=%s action=%s", event, payload.get("action"))

    if event == "ping":
        return {"status": "ok", "message": "pong", "zen": payload.get("zen", "")}

    if event == "push":
        repo = payload.get("repository", {}).get("full_name", "unknown")
        ref = payload.get("ref", "")
        pusher = payload.get("pusher", {}).get("name", "unknown")
        commits = len(payload.get("commits", []))
        logger.info(
            "github_webhook: push repo=%s ref=%s pusher=%s commits=%d",
            repo, ref, pusher, commits,
        )
        return {"status": "ok", "event": "push", "repo": repo, "ref": ref, "commits": commits}

    if event == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name", "unknown")
        logger.info(
            "github_webhook: pull_request action=%s repo=%s pr=%s",
            action, repo, pr.get("number"),
        )
        return {"status": "ok", "event": "pull_request", "action": action, "repo": repo}

    if event == "issues":
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {}).get("full_name", "unknown")
        logger.info(
            "github_webhook: issues action=%s repo=%s issue=%s",
            action, repo, issue.get("number"),
        )
        return {"status": "ok", "event": "issues", "action": action, "repo": repo}

    logger.info("github_webhook: unhandled event=%s — acknowledging", event)
    return {"status": "accepted", "event": event, "message": "Event acknowledged but not processed"}


def handle_jotform_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a Jotform onboarding webhook payload.

    Steps:
      1. Normalise field names (raw Jotform labels → snake_case).
      2. Short-circuit for test/empty payloads that carry no user data —
         returns 'accepted' without touching the DB.
      3. Delegate to the Rico handler for real submissions.
      4. Catch DB errors and return a graceful 'accepted' response so the
         webhook always returns 200 (Jotform retries on non-200).
    """
    normalized = _normalize_jotform_payload(payload)

    if not _has_user_data(normalized):
        logger.info(
            "jotform_webhook: no user data in payload keys=%s — "
            "accepting without DB insert",
            sorted(payload.keys()),
        )
        return {
            "status": "accepted",
            "message": "Webhook reachable, no profile fields provided",
        }

    from src.rico_jotform_webhook import handle_jotform_submission as _handle
    try:
        return _handle(normalized)
    except Exception as exc:
        logger.error("jotform_submission_failed: %s", exc, exc_info=True)
        return {
            "status": "accepted",
            "message": "Submission received; DB write pending when service recovers",
        }


def _resolve_db_user_id(user_id: str):
    """Resolve external user_id (email/public-id) to rico_users UUID string.

    Returns None when DB is unavailable or user doesn't exist.
    """
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return None
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text FROM rico_users
                    WHERE external_user_id = %s OR email = %s OR id::text = %s
                    LIMIT 1
                    """,
                    (user_id, user_id, user_id),
                )
                row = cur.fetchone()
            return row["id"] if row else None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("chat_service: _resolve_db_user_id failed: %s", exc)
        return None


def _db_get_chat_history(
    db_user_id: str, limit: int = 50, before: datetime | None = None,
) -> list[Dict[str, Any]] | None:
    """Fetch chat history rows from PostgreSQL. Returns None on failure."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return None
        where = "WHERE user_id = %s"
        params: list = [db_user_id]
        if before:
            where += " AND created_at < %s"
            params.append(before)
        params.append(limit)
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT role, message, metadata, created_at "
                    f"FROM rico_chat_history {where} "
                    f"ORDER BY created_at DESC LIMIT %s",
                    params,
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        # Reverse so oldest-first (chat order)
        rows.reverse()
        return [
            {
                "role": r["role"],
                "content": r["message"],
                "timestamp": r["created_at"].isoformat() if r.get("created_at") else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("chat_service: DB chat history fetch failed: %s", exc)
        return None


def db_append_chat(user_id: str, role: str, message: str) -> None:
    """Best-effort write of a chat message to PostgreSQL."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return
        db_uid = _resolve_db_user_id(user_id)
        if not db_uid:
            return
        db.append_chat(db_uid, role, message)
    except Exception as exc:
        logger.debug("chat_service: db_append_chat failed: %s", exc)


def _message_is_before(message: Any, before: datetime) -> bool:
    """Return True for fallback memory messages before the pagination cursor."""
    if not isinstance(message, dict) or not message.get("timestamp"):
        return False
    try:
        return datetime.fromisoformat(str(message["timestamp"]).replace("Z", "+00:00")) < before
    except (TypeError, ValueError):
        logger.debug("chat_service: skipping message with invalid timestamp")
        return False


def get_chat_history(user_id: str, limit: int = 50, before: datetime | None = None) -> list[Dict[str, Any]]:
    """
    Get conversation history for a user with pagination support.

    DB-first with fallback to local JSON memory for backward compatibility.

    Args:
        user_id: User identifier (email or public-id)
        limit: Maximum number of messages to return (default: 50)
        before: Optional timestamp for pagination (fetch messages before this time)

    Returns:
        List of message dictionaries with role, content, and timestamp
    """
    # --- DB path (primary) ---
    db_uid = _resolve_db_user_id(user_id)
    if db_uid:
        db_rows = _db_get_chat_history(db_uid, limit=limit, before=before)
        if db_rows is not None:
            return db_rows

    # --- Fallback: local JSON memory ---
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI()
    messages = api.memory.get_chat_messages(user_id, limit=limit)

    if before:
        messages = [
            m for m in messages
            if _message_is_before(m, before)
        ]

    # Normalise to dict format (messages may already be dicts from JSON)
    result = []
    for m in messages:
        if isinstance(m, dict):
            result.append({
                "role": m.get("role", "unknown"),
                "content": m.get("content") or m.get("message", ""),
                "timestamp": m.get("timestamp"),
            })
        else:
            result.append({
                "role": getattr(m, "role", "unknown"),
                "content": getattr(m, "content", ""),
                "timestamp": m.timestamp.isoformat() if hasattr(m, "timestamp") else None,
            })
    return result
