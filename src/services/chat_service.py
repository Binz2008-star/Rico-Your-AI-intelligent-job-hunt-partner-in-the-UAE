"""
src/services/chat_service.py
Thin service adapter for Rico AI chat, CV parsing, and webhook flows.
Does not modify Rico internals — delegates directly to existing Rico modules
via deferred imports to avoid eager loading of heavy dependencies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
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

@dataclass(frozen=True)
class ChatPreflight:
    """Result of the transport-independent chat preflight.

    ``terminal`` is a ready-to-return response for a message resolved
    deterministically (status follow-up, policy gateway) or blocked by the
    AI-message entitlement gate — in which case the AI provider must NOT be
    called. ``gate`` is the entitlement check carried forward for the
    remaining-messages banner. Shared by the JSON (send_message) and SSE
    (streaming) transports so both apply identical policy + entitlement
    decisions; streaming changes only the response transport (#1078).
    """
    terminal: Dict[str, Any] | None
    gate: Any | None


def run_chat_preflight(ctx: RicoSessionContext, message: str) -> ChatPreflight:
    """Status follow-up → Policy Gateway → AI-message gate. Transport-independent.

    Any transport (JSON or SSE) must run this before touching the AI provider so
    unsupported-tool, clarification, account-service, and over-quota outcomes are
    identical regardless of how the client fetched the turn.
    """
    from src.services.operation_state import build_status_response, is_status_followup
    from src.services.subscription_gating import check_ai_message_allowed
    from src.rico.policy import classify_request

    if is_status_followup(message):
        status_response = build_status_response(ctx.user_id)
        if status_response is not None:
            return ChatPreflight(terminal=status_response, gate=None)

    # Handles unsupported external tools and subscription queries deterministically
    # before any AI or legacy routing touches the message.
    policy = classify_request(message, has_auth=(ctx.auth_type == "authenticated"))
    if policy.route == "unsupported":
        return ChatPreflight(terminal=_unsupported_tool_response(policy), gate=None)
    if policy.route == "clarification" and str(policy.reason).startswith("conflicting_domains:"):
        return ChatPreflight(terminal=_mixed_tool_clarification_response(policy, message), gate=None)
    if policy.route == "account_service":
        return ChatPreflight(terminal=_account_service_response(ctx), gate=None)

    # ── AI message-limit gate (only applies to AI-routed messages) ───────────
    # Checked after deterministic policy routes so capped users can still reach
    # unsupported-tool clarifications and account_service responses.
    gate = check_ai_message_allowed(ctx)
    if gate and not gate.allowed:
        return ChatPreflight(terminal=gate.to_response(), gate=gate)

    return ChatPreflight(terminal=None, gate=gate)


def should_stream_ai(ctx: RicoSessionContext, message: str, profile: Any | None) -> bool:
    """Whether a message should be token-streamed as conversational AI.

    Mirrors send_message's transport-independent routing so the SSE path streams
    exactly the messages the JSON path answers with conversational AI. Structured
    or deterministic outcomes (document actions, explicit job listings → job
    cards / sign-up CTA, legacy classifier) return False and are served by
    send_message unchanged — only the transport differs (#1078). Callers MUST
    run run_chat_preflight first; this decides transport, not policy/entitlement.
    """
    from src.rico_chat_api import RicoChatAPI as _RicoChatAPI
    if _RicoChatAPI.is_document_action_message(message):
        return False
    from src.rico.intent.gates import is_explicit_job_listing_request
    if is_explicit_job_listing_request(message):
        return False
    decision = _intent_router.route(
        message=message,
        user_id=ctx.user_id,
        profile_context_present=profile is not None,
    )
    # Public/guest sessions with no profile: the legacy classifier loops on the
    # onboarding welcome, so conversational AI is used instead (matches send_message).
    _force_ai = (not decision.should_use_ai) and profile is None and not ctx.can_persist_profile
    return bool(decision.should_use_ai or _force_ai)


def send_message(
    ctx: RicoSessionContext,
    message: str,
    operation_id: str | None = None,
    language: str | None = None,
) -> Dict[str, Any]:
    """Policy Gateway → IntentRouter → legacy classifier."""
    # Shared, transport-independent preflight: status / policy / entitlement gate.
    pre = run_chat_preflight(ctx, message)
    if pre.terminal is not None:
        return pre.terminal
    gate = pre.gate

    # ── Profile fetch (deferred until past gate to avoid DB hit for capped users) ──
    from src.repositories.profile_repo import get_profile
    profile = get_profile(ctx.user_id)
    profile_present = profile is not None

    # ── Uploaded-document action — deterministic, before the AI/legacy split ───
    # "Summarize this document", "Extract key information", "Describe this image"
    # must always read from the freshly uploaded document's transcript. Without
    # this, the intent router can route one button (extract) down the AI path with
    # no transcript — which then paraphrases the public job-listing CTA — while
    # another (summarize) takes the legacy document path and works. Route both the
    # same way whenever a fresh uploaded_document_context exists for this user.
    from src.rico_chat_api import RicoChatAPI as _RicoChatAPI
    if _RicoChatAPI.is_document_action_message(message):
        _doc_reply = _RicoChatAPI(
            persist=ctx.can_persist_profile,
            can_mutate_applications=(ctx.auth_type == "authenticated"),
        ).handle_document_action(
            ctx.user_id, message, language
        )
        if _doc_reply is not None:
            _doc_reply.setdefault("intent", "document_action")
            _doc_reply.setdefault("response_source", "document_context")
            return _doc_reply

    # ── Guard: job-listing requests must never reach a free AI path ───────────
    # The conversational-AI path has no search tools here and will hallucinate
    # company names, roles, salaries, and links from training data.
    #   * Public/no-profile sessions → deterministic sign-up/upload CTA.
    #   * Authenticated sessions → the real, grounded search path (legacy
    #     classifier → JSearch), NEVER the AI path. Without this, an explicit job
    #     request that the open-ended-question gate routes to AI (e.g. a
    #     question-form request, or one the legacy classifier would treat as
    #     unknown) could return fabricated listings that are never persisted to
    #     recent_search_matches — so a later "apply to that one" cannot resolve.
    # Response contract is unchanged: the legacy path emits the same
    # type/message/options/matches shape the command surface already consumes.
    from src.rico.intent.gates import is_explicit_job_listing_request
    _explicit_job_listing = is_explicit_job_listing_request(message)
    if profile is None and not ctx.can_persist_profile:
        if _explicit_job_listing:
            return _public_job_search_cta()

    # ── Existing routing unchanged ────────────────────────────────────────────
    decision = _intent_router.route(
        message=message,
        user_id=ctx.user_id,
        profile_context_present=profile_present,
    )

    # Authenticated users: force an explicit job-listing request onto the real
    # search path even when the open-ended-question gate would have chosen AI.
    _force_real_search = _explicit_job_listing and ctx.auth_type == "authenticated"

    # When the legacy path is chosen but there is no profile and profile writes are
    # disabled (public/guest session), the legacy classifier loops back to the
    # onboarding welcome on every turn because it can never persist state.
    # Route to conversational AI instead so public users get real responses.
    _force_ai = not decision.should_use_ai and profile is None and not ctx.can_persist_profile
    if (decision.should_use_ai or _force_ai) and not _force_real_search:
        result = _conversational_ai_reply(ctx=ctx, message=message, profile=profile, language=language)
    else:
        result = _legacy_send_message(ctx=ctx, message=message, operation_id=operation_id, language=language)

    # Warn authenticated users who are approaching their AI-message allowance.
    # Threshold: ≤10 remaining. For the Free daily allowance (10/day) this shows
    # the counter throughout the day; for Rico Monthly (300/mo) only near the end.
    # Injected into every allowed response so the frontend can surface a persistent
    # banner (and reset countdown) without a separate API call.
    if (
        isinstance(result, dict)
        and gate
        and gate.allowed
        and gate.remaining is not None
        and gate.remaining <= 10
    ):
        result["messages_remaining"] = gate.remaining
        if gate.limit is not None:
            result["messages_limit"] = gate.limit
        reset_at = getattr(gate, "reset_at", None)
        if reset_at is not None:
            result["messages_reset_at"] = reset_at.isoformat()

    return result


def _public_job_search_cta() -> Dict[str, Any]:
    """Deterministic CTA returned when a public/no-profile user requests job listings.

    The AI path has no search tools and would hallucinate listings — this short-circuits
    before any model call is made.
    """
    return {
        "message": (
            "I can only show you **verified, real-time UAE job listings** — not generated ones.\n\n"
            "To search for live jobs matched to your profile:\n"
            "1. **Upload your CV** using the Upload CV button above, or\n"
            "2. **[Sign up at ricohunt.com](https://ricohunt.com)** for a free account\n\n"
            "Once I know your background I'll match you with real openings from UAE job boards "
            "and score each one for you."
        ),
        "type": "onboarding_cta",
        "intent": "job_search",
        "matches": [],
        "options": [],
        "success": True,
        "response_source": "deterministic",
    }


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
    lang = getattr(policy, "language", "en")
    if lang == "ar":
        # Policy layer already computed a localized Arabic message via get_unsupported_message()
        return policy.alternative_suggestion or (
            "لا أستطيع الوصول إلى هذه الخدمة الخارجية من ريكو. "
            "يمكنك رفع أو لصق المعلومات ذات الصلة وسأقوم بتنظيمها."
        )
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


def _continue_message_from_reason(reason: str) -> str:
    """Derive a Rico continue-action message from the supported side of a mixed-domain conflict."""
    if "applications_tracking" in reason:
        return "show my applications"
    if "cv_profile" in reason or "profile" in reason:
        return "show my profile"
    return "find live jobs for my target role"


def _mixed_tool_clarification_response(policy: Any, message: str = "") -> Dict[str, Any]:
    """Clarify mixed requests that combine unsupported external access with a supported action."""
    reason = str(getattr(policy, "reason", "conflicting_domains"))
    lang = getattr(policy, "language", "en")

    if "email_gmail_request" in reason and "job_search" in reason:
        role = _extract_requested_role(message, lang=lang)
        if lang == "ar":
            clarification_msg = f"لا أستطيع الوصول إلى Gmail من ريكو حتى الآن. يمكنني البحث عن وظائف {role} إذا أردت."
        else:
            clarification_msg = f"I can't access Gmail from Rico yet. I can search for {role} roles if you want."
    elif lang == "ar":
        clarification_msg = (
            "هذا الطلب يجمع بين أداة خارجية غير متاحة وإجراء ريكو. "
            "لا أستطيع الوصول إلى الحساب الخارجي مباشرة، لكنني أستطيع المساعدة إذا اخترت المسار."
        )
    else:
        clarification_msg = (
            "That request mixes an unavailable external tool with a Rico action. "
            "I can't access the external account directly, but I can still help if you choose the path."
        )

    return {
        "type": "clarification",
        "message": clarification_msg,
        "intent": "mixed_request",
        "response_source": "policy_gateway",
        "reason": reason,
        "options": [
            {
                "action": "continue_without_external_tool",
                "label": "Continue in Rico",
                "message": _continue_message_from_reason(reason),
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


def _extract_requested_role(message: str, lang: str = "en") -> str:
    """Best-effort role extraction for mixed Gmail + job-search clarification copy."""
    import re

    text = (message or "").strip()
    patterns = [
        r"\bfind\s+(?:me\s+)?(?:a\s+)?job\s+as\s+(.+?)(?:\s+you\s+can\b|\s+and\b|\s+with\b|[.!?]?$)",
        r"\bfind\s+(?:me\s+)?(.+?)\s+jobs?\b",
        r"\bsearch\s+(?:for\s+)?(.+?)\s+jobs?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            role = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
            if role:
                return role
    return "وظيفتك المستهدفة" if lang == "ar" else "that target role"


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
            # Read price from the plan definition so this stays accurate if pricing changes.
            try:
                from src.subscription_plans import RICO_MONTHLY_PLAN
                monthly_label = f"USD {RICO_MONTHLY_PLAN.price_monthly:.2f}/mo (≈ AED 79)"
            except Exception:
                monthly_label = "USD 21.50/mo (≈ AED 79)"
            msg = (
                f"You are on the **Free** plan — {limit} AI messages per day "
                f"(resets daily at 00:00 UTC). "
                f"Upgrade to Rico Monthly ({monthly_label}) for higher limits."
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
    language: str | None = None,
) -> Dict[str, Any]:
    """Run the existing Rico chat pipeline unchanged."""
    from src.rico_chat_api import RicoChatAPI

    return RicoChatAPI(
        persist=ctx.can_persist_profile,
        can_mutate_applications=(ctx.auth_type == "authenticated"),
    ).process_message(
        user_id=ctx.user_id,
        message=message,
        operation_id=operation_id,
        language=language,
    )


def _conversational_ai_reply(
    *,
    ctx: RicoSessionContext,
    message: str,
    profile: Any,
    language: str | None = None,
) -> Dict[str, Any]:
    """Use the existing Rico conversational AI fallback path directly."""
    from src.rico_chat_api import RicoChatAPI

    result = RicoChatAPI(
        persist=ctx.can_persist_profile,
        can_mutate_applications=(ctx.auth_type == "authenticated"),
    ).answer_conversationally(
        user_id=ctx.user_id,
        message=message,
        profile=profile,
        language=language,
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
      4. Do NOT mask a required persistence/idempotency failure: the handler
         runs claim + user/profile/settings/processed in one transaction that
         rolls back on failure, so the exception propagates — the webhook route
         returns HTTP 500 and Jotform retries, then re-claims the same
         submission atomically (#1089). Rejected/ignored/no-user payloads still
         return their own responses.
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
    # Do NOT mask a required-persistence failure as 200 "accepted": the handler
    # runs claim + user/profile/settings/processed in ONE transaction that rolls
    # back on failure, so the exception must propagate → the webhook route
    # decorator returns 500 → the provider retries → the retry re-claims the same
    # submission and re-processes atomically (#1089).
    return _handle(normalized)


def _resolve_db_user_id(user_id: str):
    """Resolve external user_id (email/public-id) to rico_users UUID string.

    For web-app users registered via /auth/register (present in `users` table but
    absent from `rico_users`), auto-provisions the rico_users row on first access so
    that chat history and profile data persist correctly.

    Returns None when DB is unavailable or user cannot be resolved/created.
    """
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return None
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                # Prefer id > email > external_user_id to avoid returning a
                # Jotform/Telegram row whose external_user_id happens to equal
                # this web user's email address (cross-user contamination).
                cur.execute(
                    """
                    SELECT id::text FROM rico_users
                    WHERE external_user_id = %s OR email = %s OR id::text = %s
                    ORDER BY
                        CASE WHEN id::text = %s THEN 0 ELSE 1 END,
                        CASE WHEN email = %s THEN 0 ELSE 1 END,
                        CASE WHEN external_user_id = %s THEN 0 ELSE 1 END,
                        updated_at DESC
                    LIMIT 1
                    """,
                    (user_id, user_id, user_id, user_id, user_id, user_id),
                )
                row = cur.fetchone()
            if row:
                return row["id"]

            # Not found — auto-provision if this is a verified web-app user (email).
            # Public/guest user_ids start with "public:" and are intentionally excluded.
            if not user_id or user_id.startswith("public:") or "@" not in user_id:
                return None

            conn2 = db.connect()
            try:
                with conn2.cursor() as cur:
                    # Use DO NOTHING to avoid overwriting a Jotform/Telegram row
                    # that already occupies external_user_id = this email. If a
                    # conflict exists, fall back to an email-keyed lookup so the
                    # web user gets the correct row and not another user's profile.
                    cur.execute(
                        """
                        INSERT INTO rico_users (external_user_id, email, source)
                        VALUES (%s, %s, 'web')
                        ON CONFLICT (external_user_id) DO NOTHING
                        RETURNING id::text
                        """,
                        (user_id, user_id),
                    )
                    new_row = cur.fetchone()
                conn2.commit()
                if new_row:
                    return new_row["id"]

                # Conflict: external_user_id taken by a non-web row. Look up by
                # email instead so this web user is never linked to a different
                # user's profile row.
                with conn2.cursor() as cur:
                    cur.execute(
                        "SELECT id::text FROM rico_users WHERE email = %s ORDER BY updated_at DESC LIMIT 1",
                        (user_id,),
                    )
                    email_row = cur.fetchone()
                if email_row:
                    return email_row["id"]

                # Still nothing — create a fresh row keyed by a web-namespaced
                # external_user_id that cannot collide with Jotform/Telegram rows.
                with conn2.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO rico_users (external_user_id, email, source)
                        VALUES (%s, %s, 'web')
                        ON CONFLICT (external_user_id) DO UPDATE SET email = EXCLUDED.email
                        RETURNING id::text
                        """,
                        (f"web:{user_id}", user_id),
                    )
                    fallback_row = cur.fetchone()
                conn2.commit()
                return fallback_row["id"] if fallback_row else None
            except Exception as exc:
                logger.warning("chat_service: rico_users auto-provision failed user=%s: %s", user_id, exc)
                try:
                    conn2.rollback()
                except Exception:
                    pass
                return None
            finally:
                conn2.close()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("chat_service: _resolve_db_user_id failed: %s", exc)
        return None


def _db_get_chat_history(
    db_user_id: str,
    limit: int = 50,
    before: datetime | None = None,
    session_id: str | None = None,
) -> list[Dict[str, Any]] | None:
    """Fetch chat history rows from PostgreSQL. Returns None on failure.

    session_id: None = unfiltered (legacy, all threads mixed);
    DEFAULT_SESSION = the legacy thread (rows with NULL session_id);
    a UUID string = that thread only.
    """
    from src.services.chat_session_context import DEFAULT_SESSION

    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return None
        where = "WHERE user_id = %s"
        params: list = [db_user_id]
        if session_id == DEFAULT_SESSION:
            where += " AND session_id IS NULL"
        elif session_id is not None:
            where += " AND session_id = %s"
            params.append(session_id)
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


_ALLOWED_CHAT_ROLES: frozenset[str] = frozenset({"user", "assistant", "system"})


def db_append_chat(user_id: str, role: str, message: str) -> None:
    """Best-effort write of a chat message to PostgreSQL.

    Stamps the ambient active chat session (set by the API router for the
    current request) so every legacy _append_chat call site threads correctly
    without signature changes. No active session, or the default session,
    writes NULL — byte-identical to pre-session behavior.
    """
    if role not in _ALLOWED_CHAT_ROLES:
        logger.warning("chat_service: db_append_chat rejected unknown role=%r user=%s", role, user_id)
        return
    try:
        from src.services.chat_session_context import DEFAULT_SESSION, get_active_chat_session
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return
        db_uid = _resolve_db_user_id(user_id)
        if not db_uid:
            return
        active = get_active_chat_session()
        session_id = None if active in (None, DEFAULT_SESSION) else active
        db.append_chat(db_uid, role, message, session_id=session_id)
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


def get_chat_history(
    user_id: str,
    limit: int = 50,
    before: datetime | None = None,
    session_id: str | None = None,
) -> list[Dict[str, Any]]:
    """
    Get conversation history for a user with pagination support.

    DB-first with fallback to local JSON memory for backward compatibility.

    Args:
        user_id: User identifier (email or public-id)
        limit: Maximum number of messages to return (default: 50)
        before: Optional timestamp for pagination (fetch messages before this time)
        session_id: Optional chat thread filter — DEFAULT_SESSION for the
            legacy thread, a UUID for a named thread. When omitted, the
            ambient active session (set by the chat router) applies, so the
            AI conversational context reads the same thread it writes to.

    Returns:
        List of message dictionaries with role, content, and timestamp
    """
    from src.services.chat_session_context import DEFAULT_SESSION, get_active_chat_session

    effective_session = session_id if session_id is not None else get_active_chat_session()

    # --- DB path (primary) ---
    db_uid = _resolve_db_user_id(user_id)
    if db_uid:
        db_rows = _db_get_chat_history(
            db_uid, limit=limit, before=before, session_id=effective_session,
        )
        # Truthy check: only use DB result when it actually has rows. An empty
        # list (DB query succeeded but 0 rows) falls through to the JSON memory
        # fallback so that history written before DB persistence was active is
        # still visible on refresh.
        if db_rows:
            return db_rows

    # A named (UUID) thread is DB-backed by definition: an empty result is
    # authoritative and the DB being unreachable yields an empty thread. The
    # user-scoped JSON memory would leak other threads' turns into it.
    if effective_session is not None and effective_session != DEFAULT_SESSION:
        return []

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


def clear_chat_history(user_id: str, session_id: str | None = None) -> None:
    """Delete chat history rows for a user (chat only — profile/applications unaffected).

    session_id: None deletes every thread (legacy full clear);
    DEFAULT_SESSION deletes only the legacy thread (NULL session rows);
    a UUID deletes only that thread.
    """
    from src.services.chat_session_context import DEFAULT_SESSION

    db_uid = _resolve_db_user_id(user_id)
    if db_uid:
        try:
            from src.rico_db import RicoDB
            db = RicoDB()
            if db.available:
                conn = db.connect()
                try:
                    with conn.cursor() as cur:
                        if session_id is None:
                            cur.execute(
                                "DELETE FROM rico_chat_history WHERE user_id = %s",
                                (db_uid,),
                            )
                        elif session_id == DEFAULT_SESSION:
                            cur.execute(
                                "DELETE FROM rico_chat_history WHERE user_id = %s AND session_id IS NULL",
                                (db_uid,),
                            )
                        else:
                            cur.execute(
                                "DELETE FROM rico_chat_history WHERE user_id = %s AND session_id = %s",
                                (db_uid, session_id),
                            )
                    conn.commit()
                finally:
                    conn.close()
        except Exception as exc:
            logger.warning("chat_service: clear_chat_history failed for user=%s: %s", user_id, exc)

    # A UUID thread lives only in the DB — the user-scoped JSON file holds the
    # legacy thread and must survive a scoped delete of another thread.
    if session_id is not None and session_id != DEFAULT_SESSION:
        return

    # Best-effort: clear the local JSON chat file as well
    try:
        from src.rico_memory import RicoMemoryStore
        store = RicoMemoryStore()
        chat_path = store._chat_path(user_id)
        if chat_path.exists():
            chat_path.unlink()
    except Exception:
        pass


_SESSION_LIST_LIMIT = 50


def list_chat_sessions(user_id: str) -> list[Dict[str, Any]]:
    """List a user's chat threads, most recently active first.

    Sessions are DERIVED from rico_chat_history (no separate table to drift):
    one row per distinct session_id, with NULL rows folded into the single
    "default" thread. Title is the thread's first real user turn — never
    invented. DB unavailable degrades to the JSON-memory legacy thread (if
    any) so the rail stays truthful rather than erroring.
    """
    from src.services.chat_session_context import DEFAULT_SESSION, derive_session_title

    db_uid = _resolve_db_user_id(user_id)
    if db_uid:
        try:
            from src.rico_db import RicoDB
            db = RicoDB()
            if db.available:
                conn = db.connect()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT COALESCE(session_id::text, %s) AS sid,
                                   MIN(created_at) AS started_at,
                                   MAX(created_at) AS last_activity,
                                   COUNT(*) AS message_count,
                                   COUNT(*) FILTER (WHERE role = 'user') AS user_turns
                            FROM rico_chat_history
                            WHERE user_id = %s
                            GROUP BY COALESCE(session_id::text, %s)
                            ORDER BY MAX(created_at) DESC
                            LIMIT %s
                            """,
                            (DEFAULT_SESSION, db_uid, DEFAULT_SESSION, _SESSION_LIST_LIMIT),
                        )
                        rows = cur.fetchall()
                        cur.execute(
                            """
                            SELECT DISTINCT ON (COALESCE(session_id::text, %s))
                                   COALESCE(session_id::text, %s) AS sid,
                                   message
                            FROM rico_chat_history
                            WHERE user_id = %s AND role = 'user'
                            ORDER BY COALESCE(session_id::text, %s), created_at ASC
                            """,
                            (DEFAULT_SESSION, DEFAULT_SESSION, db_uid, DEFAULT_SESSION),
                        )
                        titles = {r["sid"]: r["message"] for r in cur.fetchall()}
                finally:
                    conn.close()
                return [
                    {
                        "id": r["sid"],
                        "title": derive_session_title(titles.get(r["sid"])),
                        "message_count": int(r["message_count"]),
                        "user_turns": int(r["user_turns"]),
                        "started_at": r["started_at"].isoformat() if r.get("started_at") else None,
                        "last_activity": r["last_activity"].isoformat() if r.get("last_activity") else None,
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.warning("chat_service: list_chat_sessions failed for user=%s: %s", user_id, exc)

    # Fallback: the JSON-memory legacy thread as a single "default" session.
    try:
        from src.rico_chat_api import RicoChatAPI
        messages = RicoChatAPI().memory.get_chat_messages(user_id, limit=200)
    except Exception:
        messages = []
    if not messages:
        return []
    first_user = next(
        (
            m.get("message") or m.get("content")
            for m in messages
            if isinstance(m, dict) and m.get("role") == "user"
        ),
        None,
    )
    return [
        {
            "id": DEFAULT_SESSION,
            "title": derive_session_title(first_user),
            "message_count": len(messages),
            "user_turns": sum(
                1 for m in messages if isinstance(m, dict) and m.get("role") == "user"
            ),
            "started_at": (messages[0].get("created_at") if isinstance(messages[0], dict) else None),
            "last_activity": (messages[-1].get("created_at") if isinstance(messages[-1], dict) else None),
        }
    ]
