"""Rico conversational AI API.

This module transforms the existing automation system into a chat-first
career agent. Rico accepts natural language messages, updates memory,
triggers workflows, and responds with autonomous actions.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace as _dc_replace
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, NamedTuple

# Standard library imports first
# Third-party imports (none currently)
# Local imports
from src.agent.intelligence.intent_classifier import classify_intent
from src.agent.intelligence.normalizer import normalize_role
from src.agent.intelligence.recommender import recommend_adjacent_roles
from src.agent.intelligence.role_classifier import classify_role_candidate
from src.agent.intelligence.role_suggester import (
    generate_role_suggestions as _suggest_roles,
    needs_clarification as _needs_clarification,
)
from src.agent.intelligence.scorer import score_profile_fit
from src.agent.responses.schema import RicoResponse, build_error_response, _generate_debug_id
from src.agent.runtime import agent_runtime
from src.models.onboarding import ONBOARDING_IN_PROGRESS
from src.rico_agent import RicoAgent
from src.rico_hf_client import generate_text, is_available as hf_ok
from src.rico_intent_router import route as _route
from src.rico_match_explainer import build_match_explanation
from src.rico_memory import RicoMemoryStore
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_repo_adapter import RicoSystem
from src.repositories.onboarding_repo import (
    is_onboarding_complete,
    mark_onboarding_complete,
    set_onboarding_status,
)
from src.repositories.profile_repo import get_profile, upsert_profile
from src.services.profile_context_resolver import resolve_profile_context
from src.services.operation_state import (
    mark_completed,
    mark_failed,
    start_job_search_operation,
)

logger = logging.getLogger(__name__)


# ── Intent v2 backward compatibility mapping ────────────────────────────────

_LEGACY_INTENT_MAP = {
    # Job search
    "job_search.explicit_role": "job_search_explicit",
    "job_search.profile_match": "job_search_profile_match",
    "job_search.role_suggestions": "profile_role_suggestions",
    # Job actions
    "job_action.prepare_application": "prepare_application",
    "job_action.open_apply_link": "open_apply_link",
    "job_action.track_job": "track_job",
    "job_action.mark_applied": "mark_applied",
    "job_action.save_job": "save_job",
    "job_action.apply_job": "apply_job",
    "job_action.bulk_apply_unsafe": "bulk_apply_unsafe",
    "job_action.explain_fit": "explain_match",
    # Application tracking
    "application.show_flow": "application_tracking",
    "application.recent_context": "application_tracking",
    # Lifecycle queries (chat-side funnel memory)
    "lifecycle.show_saved": "lifecycle_show_saved",
    "lifecycle.show_applied": "lifecycle_show_applied",
    "lifecycle.show_opened_not_applied": "lifecycle_show_opened_not_applied",
    # Recent context follow-up (native legacy name, pass through)
    "recent_context": "recent_context",
    # Profile
    "profile.show": "profile_summary",
    "profile.update": "profile_update",
    "profile.update_target_roles": "save_target_role",
    "cv.create": "cv_create",
    "cv.generate": "cv_generate",
    # Career prep
    "career_prep.interview": "interview_prep",
    "career_prep.application_angle": "draft_message",
}


def _map_intent_to_legacy(intent: str) -> str:
    """Map Intent v2 dotted notation to legacy intent names for backward compatibility."""
    return _LEGACY_INTENT_MAP.get(intent, intent)

# Constants
CV_FILE_RE = re.compile(r"\b[\w .()_-]+\.(?:pdf|docx?|txt)\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
FOLLOWUP_BOUNDARY_PUNCT_RE = re.compile(r"^[\s\"'([{]+|[\s\"')\]}.,!?;:]+$")
PROFILE_LIST_SPLIT_RE = re.compile(r"[,;\n\r|]+")
# Telegram username: @handle (5–32 chars, alphanumeric + underscore)
TELEGRAM_HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
# Telegram declaration in natural language: "my telegram is @handle", "@handle" etc.
TELEGRAM_MENTION_RE = re.compile(
    r"(?:my\s+)?telegram(?:\s+(?:username|handle|id|account|is|:))?\s+(?:is\s+)?(@[A-Za-z0-9_]{5,32})"
    r"|(?:^|\s)(@[A-Za-z0-9_]{5,32})(?:\s|$)",
    re.IGNORECASE,
)

# CV improvement follow-up phrases — used ONLY when last_flow_state == "cv_builder".
# Never apply this pattern without flow-state context or it will misfire on
# "improve my cover letter", "enhance it" for other content, etc.
_CV_IMPROVE_FOLLOWUP_RE = re.compile(
    # English: standalone improvement requests (no "cv"/"resume" word needed)
    r"\bplease\s+improve\s+it\b"
    r"|\bimprove\s+it\b"
    r"|\benhance\s+it\b"
    r"|\bmake\s+it\s+(better|shorter|longer|more\s+professional|professional)\b"
    r"|\brefine\s+it\b"
    r"|\btailor\s+it\b"
    # Arabic: "improve it [professionally]"
    r"|(?:نعم\s+)?حسنها(?:\s+بشكل\s+احتراف(?:ي|ياً?))?"
    r"|(?:نعم\s+)?طورها"
    r"|احسنها"
    r"|حسّنها"
    # Arabic: "improve/develop the CV"
    r"|(?:نعم\s+)?حسن\s+(?:ال)?سير[هة](?:\s+(?:ال)?ذاتي[هة])?"
    r"|(?:نعم\s+)?طور\s+(?:ال)?سير[هة](?:\s+(?:ال)?ذاتي[هة])?",
    re.IGNORECASE | re.UNICODE,
)

# Strings that must never appear inside a deterministic CV draft body.
# Used as a post-generation guard in _handle_cv_generate_from_profile.
_CV_PLACEHOLDER_PATTERNS = re.compile(
    r"\[Start\s+Date\]"
    r"|\[End\s+Date\]"
    r"|\[Company\s+Name\]"
    r"|\[Job\s+Title\]"
    r"|\[Add\s+\w"
    r"|Add\s+\d+.{0,20}responsibilities\s+here"
    r"|\bTBD\b"
    r"|\bassumed\b"
    r"|please\s+confirm(?:\s+inside)?",
    re.IGNORECASE,
)

# Domain-agnostic. A bare role is a short noun phrase. Anything starting with
# one of these tokens is a question, command, greeting, or sentence - never
# a role title.
_NON_ROLE_STARTERS: frozenset[str] = frozenset({
    "what", "whats", "what's", "how", "hows", "how's", "why", "when",
    "where", "who", "whom", "whose", "which",
    "is", "are", "am", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "done",
    "have", "has", "had", "having",
    "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "ought",
    "tell", "show", "give", "find", "search", "get", "fetch", "list",
    "explain", "describe", "compare", "help", "please",
    "want", "need", "looking",
    # Gerunds of action verbs — never start a job title
    # "listing" excluded: "Listing Agent" is a real UAE/real-estate role title
    "finding", "searching", "showing", "getting", "fetching",
    "tailoring", "improving", "updating", "tracking",
    "hi", "hello", "hey", "greetings", "thanks", "thank", "ok", "okay",
    "yes", "yeah", "yep", "ya", "no", "nope", "sure", "fine", "good", "great",
    "cool", "nice", "wow", "oh", "ah",
    "i", "im", "i'm", "me", "my", "mine", "myself",
    "we", "our", "ours", "us",
    "the", "a", "an", "this", "that", "these", "those",
    "some", "any", "every", "all", "none", "each", "many", "few",
    "and", "but", "or", "so", "if", "because", "though", "while", "as",
    # Imperative command / toggle verbs — start a settings command, never a job title
    "enable", "disable", "turn", "activate", "deactivate",
    "mute", "unmute", "configure", "connect",
})
_QUESTION_CHARS: frozenset[str] = frozenset("?？!！;:")
_MAX_ROLE_WORDS: int = 6

# Location names that are never valid job-role titles. A message consisting
# entirely of these terms (e.g. "UAE", "Dubai", "jobs in UAE") should redirect
# to a profile-based search, not a role-classification error.
_LOCATION_TERMS: frozenset[str] = frozenset({
    # Country / region
    "uae", "emirates", "united arab emirates",
    # UAE cities / emirates
    "dubai", "abu dhabi", "abudhabi", "sharjah", "ajman",
    "ras al khaimah", "ras al-khaimah", "fujairah", "umm al quwain",
    "umm al-quwain",
    # GCC / region
    "gcc", "gulf", "middle east", "mena",
    # Arabic equivalents (normalised, no diacritics)
    "الإمارات", "الامارات", "دبي", "أبوظبي", "ابوظبي",
    "الشارقة", "الشارقه", "عجمان", "رأس الخيمة", "راس الخيمه",
    "الفجيرة", "الفجيره", "أم القيوين", "ام القيوين",
})
_MIN_TOKEN_ALPHA: int = 2

# Role values that users leave as default placeholders and that cannot drive a
# useful JSearch query.  Treat them as "no target role set" so the classifier
# falls through to role-suggestion prompts instead of returning irrelevant jobs.
_PLACEHOLDER_ROLE_VALUES: frozenset[str] = frozenset({
    "any", "all", "any role", "all roles", "open", "open to any",
    "open to all", "any position", "any job", "any jobs",
    "not specified", "tbd", "n/a",
})

# Settings / notification commands ("enable telegram notifications", "turn off
# email alerts", "disable reminders"). These are not job roles and not job
# searches — route them to Settings guidance instead of role classification.
_SETTINGS_COMMAND_RE = re.compile(
    r"\b(enable|disable|turn\s+(?:on|off)|activate|deactivate|mute|unmute|"
    r"switch\s+(?:on|off)|stop|start)\b"
    r".{0,40}"
    r"\b(notification|notifications|alert|alerts|telegram|whatsapp|reminder|reminders)\b",
    re.IGNORECASE,
)

def generate_error_ref() -> str:
    """Generate a unique error reference ID for tracking and support lookup."""
    return f"ERR-{uuid.uuid4().hex[:8].upper()}"

ONBOARDING_FIELD_LABELS = {
    "email": "email address",
    "phone": "phone number",
    "preferred_city": "preferred UAE city",
    "target_roles": "target role",
    "salary_expectation_aed": "salary expectation",
    "deal_breakers": "roles or companies to avoid",
}

# OpenAI context limits
MAX_CONTEXT_MESSAGES = 10
MAX_PROFILE_TOKENS = 200  # Conservative estimate for profile summary

# Phrases that identify pipeline-generated artifacts. Messages containing these
# must never be fed back to the LLM as authentic user statements.
_PIPELINE_ARTIFACT_PHRASES: tuple[str, ...] = (
    "i have uae experience in executive operations",
    "ceo support",
    "i am interested in the",  # generated_message template prefix
)

_ALLOWED_LLM_ROLES: frozenset[str] = frozenset({"user", "assistant"})


def _sanitize_history_for_llm(messages: list[dict]) -> list[dict]:
    """Return only safe, authentic conversation turns for LLM context injection.

    Drops:
    - Any message whose role is not 'user' or 'assistant'
    - Any user-role message whose content matches a known pipeline artifact phrase
      (guards against generated drafts stored with wrong role)
    """
    safe = []
    for m in messages:
        role = str(m.get("role", "")).lower()
        if role not in _ALLOWED_LLM_ROLES:
            continue
        content = str(m.get("content") or m.get("message") or "").strip().lower()
        if not content:
            continue
        if role == "user" and any(phrase in content for phrase in _PIPELINE_ARTIFACT_PHRASES):
            logger.warning("chat_sanitizer: dropped pipeline artifact stored as role=user")
            continue
        safe.append(m)
    return safe

# Acknowledgement replies — short, warm, non-restarting
_ACKNOWLEDGEMENT_REPLIES: dict[str, str] = {
    "thanks": "You're welcome!",
    "thank you": "You're welcome!",
    "thank you so much": "Happy to help anytime!",
    "thanks a lot": "Happy to help!",
    "thank you very much": "Happy to help!",
    "much appreciated": "Glad I could help.",
    "appreciate it": "Glad I could help.",
    "appreciate that": "Glad I could help.",
    "great": "Glad to help.",
    "perfect": "Happy to help.",
    "excellent": "Glad to hear that!",
    "wonderful": "Glad to hear that!",
    "awesome": "Great!",
    "cool": "Good to know.",
    "nice": "Good to know.",
    "ok": "Of course.",
    "okay": "Of course.",
    "ok thanks": "You're welcome.",
    "okay thanks": "You're welcome.",
    "ok thank you": "You're welcome.",
    "okay thank you": "You're welcome.",
    "got it": "Sounds good.",
    "understood": "Sounds good.",
    "noted": "Noted.",
    "sounds good": "Glad that works for you.",
    "looks good": "Glad that works for you.",
    "makes sense": "Great.",
    "cheers": "Cheers!",
    # Arabic
    "شكرا": "عفواً!",
    "شكراً": "عفواً!",
    "شكرا جزيلا": "على الرحب والسعة!",
    "شكراً جزيلاً": "على الرحب والسعة!",
    "ممتاز": "يسعدني ذلك.",
    "رائع": "يسعدني ذلك.",
    "فهمت": "ممتاز.",
    "تمام": "بالتوفيق.",
    "ماشي": "حسناً.",
    "حسنا": "حسناً.",
}
_DEFAULT_ACK_REPLY = "Of course! What would you like to do next?"


def _acknowledgement_reply(message: str) -> str:
    """Return a short warm reply for acknowledgement phrases."""
    key = message.strip().lower()
    return _ACKNOWLEDGEMENT_REPLIES.get(key, _DEFAULT_ACK_REPLY)


class HandlerResult(NamedTuple):
    """Result type for handler functions."""
    response: dict[str, Any]
    should_save: bool = True


def profile_to_dict(profile: Any) -> dict[str, Any]:
    """Normalize profile to dict, handling dataclass, dict, and object types."""
    if profile is None:
        return {}
    if is_dataclass(profile):
        return {k: v for k, v in asdict(profile).items() if v not in (None, "", [], {})}
    if isinstance(profile, dict):
        return {k: v for k, v in profile.items() if v not in (None, "", [], {})}
    return {
        k: getattr(profile, k)
        for k in dir(profile)
        if not k.startswith("_") and getattr(profile, k, None) not in (None, "", [], {})
    }


class RicoChatAPI:
    """Simple conversational controller for Rico AI."""

    # Deterministic follow-up phrases (must be checked before role classification)
    _FOLLOWUP_BOTH_ACTION_PHRASES = frozenset({
        "both",
        "both please",
        "do both",
        "yes both",
    })

    _FOLLOWUP_KEEP_ALL_PHRASES = frozenset({
        "keep all",
        "keep them all",
        "yes keep all",
        "keep everything",
    })

    def __init__(self, *, persist: bool = True) -> None:
        self.memory = RicoMemoryStore()
        self.agent = RicoAgent(profile_store=self.memory)
        self.system = RicoSystem()
        self.openai_agent = RicoOpenAIAgent()
        self._persist = persist
        self._current_operation_id: str | None = None

    @staticmethod
    def _is_broad_manager_role(role_text: str) -> bool:
        text = re.sub(r"\s+", " ", (role_text or "").strip().lower())
        text = re.sub(r"^(?:a|an|the)\s+", "", text)
        return text in {"manager", "managers"}

    def _broad_manager_clarification(self, user_id: str) -> dict[str, Any]:
        suggestions = [
            "HSE Manager",
            "Operations Manager",
            "HR Manager",
            "Environmental Manager",
            "General Manager",
        ]
        response = {
            "type": "clarification",
            "intent": "search_jobs",
            "message": (
                "Manager is too broad for a live job search. Which manager role should I search?"
            ),
            "options": [
                {
                    "action": "search_role",
                    "label": role,
                    "message": f"find live jobs for {role}",
                    "role": role,
                }
                for role in suggestions
            ],
            "next_action": "narrow_job_search",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _begin_job_search_operation(self, user_id: str, role_or_query: str) -> dict[str, Any]:
        operation = start_job_search_operation(
            user_id=user_id,
            role_or_query=role_or_query,
            operation_id=self._current_operation_id,
        )
        self._current_operation_id = str(operation["operation_id"])
        return operation

    _ALLOWED_CHAT_ROLES: frozenset[str] = frozenset({"user", "assistant", "system"})

    def _append_chat(self, user_id: str, role: str, message: str | dict[str, Any]) -> None:
        """Append chat message to memory (sync) and DB (async fire-and-forget).

        Memory write is synchronous so subsequent reads see the message immediately.
        DB write is dispatched to a background thread to avoid blocking the request
        path on remote PostgreSQL latency (~1s round-trip on Neon).
        """
        if role not in self._ALLOWED_CHAT_ROLES:
            logger.warning("rico_chat_api: _append_chat rejected unknown role=%r user=%s", role, user_id)
            return
        payload = json.dumps(message) if isinstance(message, dict) else message
        try:
            self.memory.append_chat_message(user_id, role, payload)
        except Exception:
            logger.error("rico_chat_api: memory append_chat_message failed user=%s role=%s", user_id, role, exc_info=True)
        if not getattr(self, "_persist", True):
            return
        # Async DB persistence — non-blocking, daemon so worker shutdown is
        # not stalled by a slow or unreachable Postgres during deploys.
        import threading
        from src.services.chat_service import db_append_chat

        def _safe_db_append(uid: str, r: str, p: str) -> None:
            try:
                db_append_chat(uid, r, p)
            except Exception:
                logger.error("rico_chat_api: db_append_chat failed user=%s", uid, exc_info=True)

        threading.Thread(
            target=_safe_db_append,
            args=(user_id, role, payload),
            daemon=True,
        ).start()

    def _build_openai_context(self, profile: Any, user_id: str | None = None) -> dict[str, Any]:
        """Build context for OpenAI agent from profile and recent conversation history."""
        if profile is None:
            ctx: dict[str, Any] = {"profile_exists": False}
        else:
            if is_dataclass(profile):
                raw = asdict(profile)
            elif isinstance(profile, dict):
                raw = dict(profile)
            else:
                raw = {k: getattr(profile, k) for k in dir(profile) if not k.startswith("_")}

            essential_fields = {
                # Deliberately excludes "email": the user's identity is established
                # by the JWT, not the profile record. Including email in the AI
                # context risks leaking a stale or cross-user email into the
                # model's reply (e.g. "you have a profile on record as X@Y.com").
                "phone", "skills", "years_experience",
                "preferred_cities", "target_roles", "industries",
                "salary_expectation_aed", "deal_breakers",
                "telegram_username", "telegram_chat_id",
                "name", "visa_status", "notice_period",
                "current_company", "current_role", "linkedin_url",
            }
            ctx = {
                "profile_exists": True,
                **{k: v for k, v in raw.items() if k in essential_fields and v not in (None, "", [], {})},
            }

        # Embed last 8 turns so the AI has conversation context for yes/no and follow-ups
        if user_id:
            try:
                recent = self._get_recent_messages(user_id, limit=8)
                if recent:
                    ctx["conversation_history"] = [
                        {"role": m.get("role", "user"), "content": str(m.get("content") or m.get("message") or "")}
                        for m in recent
                        if m.get("content") or m.get("message")
                    ]
            except Exception:
                pass

            # Cross-session recall: surface jobs the user recently discussed so
            # Rico can say "you looked at the AESG role last Tuesday — want an update?"
            summary = self._recent_jobs_summary(user_id)
            if summary:
                ctx["recently_discussed_jobs"] = summary

            # Inject verification status for recent search matches to prevent hallucination
            try:
                recent_ctx = self._get_recent_context(user_id)
                recent_matches = recent_ctx.get("recent_search_matches", [])
                if recent_matches:
                    ctx["recent_job_verification_status"] = [
                        {
                            "title": m.get("title", ""),
                            "company": m.get("company", ""),
                            "verification_status": m.get("verification_status", "unknown"),
                        }
                        for m in recent_matches
                        if m.get("title")
                    ]
            except Exception:
                pass

            # Inject learned behavioral preferences from rico_learning_signals so the
            # AI knows which roles/locations the user gravitates toward and which
            # companies to avoid — derived from apply/save/skip/block actions.
            try:
                from src.repositories.learning_repo import get_learning_repository
                _lr = get_learning_repository()
                _learned: dict[str, Any] = {}
                _roles = [r for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
                if _roles:
                    _learned["preferred_roles"] = _roles
                _locs = [loc for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
                if _locs:
                    _learned["preferred_locations"] = _locs
                _skills = [s for s, _ in _lr.get_top_preferences(user_id, "skill", limit=8)]
                if _skills:
                    _learned["preferred_skills"] = _skills
                _cos = [(c, w) for c, w in _lr.get_top_preferences(user_id, "company", limit=10) if w < 0]
                if _cos:
                    _learned["avoided_companies"] = [c for c, _ in _cos]
                if _learned:
                    ctx["learned_preferences"] = _learned
            except Exception:
                pass

        return ctx

    def _recent_jobs_summary(self, user_id: str, limit: int = 3) -> str:
        """Compact one-line summary of recently discussed jobs for the system prompt.

        Returns '' when nothing is available or the lookup fails. Never raises.
        """
        try:
            from src.repositories.user_job_context_repo import get_recently_discussed
            rows = get_recently_discussed(user_id, limit=limit)
        except Exception:
            return ""
        if not rows:
            return ""
        now = datetime.now(timezone.utc)
        parts: list[str] = []
        for r in rows:
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            if not title:
                continue
            status = (r.get("status") or "discussed").strip()
            when = r.get("last_discussed_at")
            ago = self._humanize_ago(when, now)
            label = f"{title}" + (f" at {company}" if company else "")
            parts.append(f"{label} ({status}{', ' + ago if ago else ''})")
        return "; ".join(parts)

    @staticmethod
    def _humanize_ago(when: Any, now: Any) -> str:
        """Render a timestamp as 'today' / 'yesterday' / 'N days ago'. '' on failure."""
        if when is None:
            return ""
        try:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            days = (now - when).days
        except Exception:
            return ""
        if days <= 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days} days ago"
        weeks = days // 7
        return "last week" if weeks == 1 else f"{weeks} weeks ago"

    @staticmethod
    def _profile_value(profile: Any, key: str, default: Any = None) -> Any:
        """Get value from profile, handling dict and object types."""
        if profile is None:
            return default
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    @staticmethod
    def _has_cv_profile(profile: Any) -> bool:
        """Check if profile has CV data."""
        if profile is None:
            return False
        return bool(
            RicoChatAPI._profile_value(profile, "cv_filename")
            or RicoChatAPI._profile_value(profile, "cv_status")
            or RicoChatAPI._profile_value(profile, "skills")
            or RicoChatAPI._profile_value(profile, "years_experience")
        )

    @staticmethod
    def _effective_target_roles(roles: list[Any]) -> list[Any]:
        """Return roles with generic placeholders ('Any', 'All', etc.) stripped out."""
        return [
            r for r in roles
            if isinstance(r, str) and r.strip().lower() not in _PLACEHOLDER_ROLE_VALUES
        ]

    @staticmethod
    def _looks_like_bare_target_role(message: str) -> bool:
        """Accept only short noun-phrase job titles, not questions or commands."""
        text = (message or "").strip()
        if not text:
            return False
        # An email address is never a job role — it's typically an answer to a
        # prompt (e.g. "what's the company email?"). Don't misread it as a role
        # and emit "I do not recognize '...' as a job role."
        if EMAIL_RE.search(text):
            return False
        # Pure Arabic / non-ASCII input can't match the English role taxonomy
        if not any(ch.isascii() and ch.isalpha() for ch in text):
            return False
        if any(ch in _QUESTION_CHARS for ch in text):
            return False
        if ". " in text or text.endswith("..."):
            return False
        if any(ch.isdigit() for ch in text):
            return False

        tokens = text.split()
        if not tokens or len(tokens) > _MAX_ROLE_WORDS:
            return False

        # A message made up entirely of location terms is a location-qualified
        # job search, not a bare job role title. Check the full phrase first
        # (handles multi-word cities like "Abu Dhabi"), then per-token.
        if text.lower() in _LOCATION_TERMS:
            return False
        _loc_fillers = {"jobs", "job", "roles", "role", "in", "the", "a", "an"}
        non_location_tokens = [
            t for t in tokens
            if t.lower() not in _LOCATION_TERMS and t.lower() not in _loc_fillers
        ]
        if not non_location_tokens:
            return False

        # Contractions (e.g. "can't", "don't") start with a verb, not a job title.
        # They never appear in English role names, so reject on apostrophe in first token.
        first_raw = tokens[0].lower()
        if "'" in first_raw or "’" in first_raw:
            return False
        first = first_raw.strip(".,/&+-()")
        if first in _NON_ROLE_STARTERS:
            return False
        if not any(
            sum(1 for ch in tok if ch.isalpha()) >= _MIN_TOKEN_ALPHA
            for tok in tokens
        ):
            return False

        if text.lower() in RicoChatAPI._WHATS_NEXT_PHRASES:
            return False
        return True

    # Role suffix words used to detect space-concatenated Title Case role blobs.
    _ROLE_SUFFIX_RE = re.compile(
        r"\b(?:Manager|Director|Officer|Lead|Specialist|Consultant|Advisor|"
        r"Coordinator|Executive|Head|Analyst|Engineer|Associate|President|VP)\b"
    )
    # Captures a role-suffix word + the space before the next capitalised word.
    # Used to insert a split sentinel (\x00) without variable-width lookbehind.
    _ROLE_SUFFIX_BOUNDARY_RE = re.compile(
        r"(Manager|Director|Officer|Lead|Specialist|Consultant|Advisor|"
        r"Coordinator|Executive|Head|Analyst|Engineer|Associate|President|VP) "
        r"(?=[A-Z])"
    )

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        """Convert profile values to a flat list.

        Profile data can arrive from older forms as comma/newline-separated
        strings. Flatten those before role search so one stored text blob never
        becomes one giant job title.

        Also handles space-concatenated Title Case role blobs produced by older
        Jotform/onboarding paths (e.g. "Environmental Manager HSE Manager"):
        these are split at Title Case word boundaries when the string is long
        and contains multiple known role-suffix words.
        """
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        result: list[Any] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, str):
                for part in PROFILE_LIST_SPLIT_RE.split(item):
                    cleaned = part.strip().strip("-*\u2022").strip()
                    if not cleaned:
                        continue
                    # Secondary split: detect space-joined Title Case role blobs.
                    # Apply only when string is suspiciously long and contains
                    # at least two known role-suffix words \u2014 avoids false splits
                    # on legitimate multi-word titles like "General Manager Retail".
                    if (
                        len(cleaned) > 50
                        and len(RicoChatAPI._ROLE_SUFFIX_RE.findall(cleaned)) >= 2
                    ):
                        sentinel = RicoChatAPI._ROLE_SUFFIX_BOUNDARY_RE.sub(
                            lambda m: m.group(1) + "\x00", cleaned
                        )
                        sub_parts = sentinel.split("\x00")
                        for sp in sub_parts:
                            sp = sp.strip()
                            if sp:
                                result.append(sp)
                    else:
                        result.append(cleaned)
                continue
            result.append(item)
        return result

    @staticmethod
    def normalize_role_label(text: str) -> str:
        """Title-case role text while preserving known acronyms."""
        if not text:
            return text
        acronyms = {"HSE", "QHSE", "EHS", "ESG", "UAE", "ISO", "CV", "NEBOSH"}
        words = text.split()
        result = []
        for w in words:
            upper = w.upper()
            if upper in acronyms:
                result.append(upper)
            else:
                result.append(w.capitalize())
        return " ".join(result)

    # ── Live / generic job search detection ────────────────────────────────

    _LIVE_SEARCH_RE = re.compile(
        # live/current near jobs/roles/openings (both word orders)
        r"\b(live|current)\b.{0,40}\b(jobs?|roles?|openings?)\b"
        r"|\b(jobs?|roles?|openings?)\b.{0,40}\b(live|current)\b"
        # "uae jobs/roles" only when a role word follows (>=3 chars after whitespace)
        r"|\buae\s+(?:jobs?|roles?|openings?)\s+(?:for\s+)?\w{3}"
        r"|\b(?:jobs?|roles?|openings?)\s+(?:for\s+)?\w{3}.{0,40}\buae\b"
        # find openings (bare -- strong enough signal on its own)
        r"|\bfind\b.{0,20}\bopenings?\b"
        # show current openings (explicit)
        r"|\bshow\b.{0,20}\bcurrent\b.{0,20}\bopenings?\b",
        re.IGNORECASE,
    )

    _GENERIC_JOB_REQUEST_RE = re.compile(
        r"^\s*(?:i\s+(?:am|m)\s+|am\s+)?(?:looking\s+for|find|show|get|need|want)\s+(?:a\s+)?(?:job|jobs|work|role|roles)\s*$"
        r"|^\s*(?:i\s+)?(?:need|want)\s+(?:a\s+)?(?:job|jobs|work|role|roles)\s*$"
        r"|^\s*(?:find|show|get)\s+(?:me\s+)?(?:a\s+)?(?:job|jobs|role|roles)\s*$"
        r"|^\s*(?:show|find|get)\s+me\s+jobs?\s*$"
        r"|^\s*jobs?\s+(?:for\s+me|please)\s*$",
        re.IGNORECASE,
    )

    # Matches self-referential role phrases that should resolve to saved profile roles.
    # English: "my target role/roles", "my saved role/roles", "my saved target role/roles"
    # Arabic:  "دوري المستهدف", "أدواري المستهدفة", "وظيفتي المستهدفة", "وظيفتي المحفوظة"
    _SELF_REF_ROLE_RE = re.compile(
        r"^my(?:\s+saved)?\s+(?:target\s+)?roles?$"
        r"|^(?:دوري|أدواري|وظيفتي)\s+(?:المستهدف(?:ة)?|المحفوظ(?:ة)?)$",
        re.IGNORECASE,
    )

    # Matches explicit requests to view submitted applications — must route to
    # application_tracking regardless of prior turn context.
    # "show applications" / "list applications" (no "my") are intentionally excluded:
    # those bare forms stay in _LIST_FOLLOWUP_PHRASES so they replay lifecycle context
    # when a prior application turn exists, which is the correct contextual behavior.
    # English: "show my applications", "my applications", etc.
    # Arabic:  "طلباتي", "اعرض طلباتي", etc.
    _SHOW_MY_APPLICATIONS_RE = re.compile(
        r"^(?:"
        r"(?:show|list|view|see|display|check|track)\s+my\s+applications?|"
        r"my\s+applications?"
        r"|(?:اعرض|أعرض|عرض|اظهر|أظهر|ارني|أريني)\s+طلباتي"
        r"|طلباتي"
        r")$",
        re.IGNORECASE,
    )

    # Matches direct reminder commands like "Set a follow-up reminder for Penspen"
    # or "Remind me to follow up" — these are button-click phrases from the UI
    # that must be caught before role classification interprets them as job titles.
    _SET_REMINDER_RE = re.compile(
        r"(?:"
        r"set\s+(?:a\s+)?(?:follow[- ]up\s+)?reminder"
        r"|remind\s+me\s+(?:to\s+follow\s+up|about)"
        r"|follow[- ]up\s+reminder"
        r"|اضبط\s+تذكير|ضع\s+تذكير|تذكيرني"
        r")",
        re.IGNORECASE,
    )

    _MANUAL_APPLICATION_LOG_QUESTION_RE = re.compile(
        r"\bhow\s+can\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
        r"(?:it|this|this\s+job|the\s+job|that\s+job)\b"
        r"|\b(?:can|could|will|would)\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
        r"(?:it|this|this\s+job|the\s+job|that\s+job)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_live_job_search_request(message: str) -> bool:
        """True when user explicitly asks for live/current/UAE/openings jobs."""
        return bool(RicoChatAPI._LIVE_SEARCH_RE.search(message))

    @staticmethod
    def _looks_like_generic_job_request(message: str) -> bool:
        """True for generic job-search phrases without a specific role."""
        return bool(RicoChatAPI._GENERIC_JOB_REQUEST_RE.search(message))

    @staticmethod
    def _looks_like_career_execution_request(message: str) -> bool:
        """True when the user expects Rico to execute career discovery/search."""
        text = (message or "").strip().lower()
        if not text:
            return False
        return (
            "find me a career" in text
            or "find a career" in text
            or "career in " in text
            or "cannot find me a career" in text
            or ("why should i search" in text and "career" in text)
        )

    @staticmethod
    def _extract_career_industry_targets(message: str, profile: Any) -> list[str]:
        """Extract the user's requested industry, with profile industries as fallback."""
        text = (message or "").strip()
        targets: list[str] = []
        match = re.search(r"\bcareer\s+in\s+([a-zA-Z][a-zA-Z &/-]{2,40})", text, re.IGNORECASE)
        if not match:
            match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z &/-]{2,40})", text, re.IGNORECASE)
        if match:
            industry = re.split(r"[.?!,;:]", match.group(1).strip())[0].strip()
            if industry:
                targets.append(industry.lower())

        for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "industries")):
            industry = str(item).strip().lower()
            if industry and industry not in targets:
                targets.append(industry)

        return targets or ["uae"]

    @staticmethod
    def _career_execution_roles(profile: Any, industry_targets: list[str]) -> list[str]:
        roles: list[str] = []
        for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "target_roles")):
            role = str(item).strip()
            if role and role not in roles:
                roles.append(role)

        skills = {str(item).strip().lower() for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "skills"))}
        industries = set(industry_targets)
        if "banking" in industries:
            for role in ("Compliance Manager", "ESG Manager", "Operational Risk Manager"):
                if role not in roles:
                    roles.append(role)
        if {"compliance", "risk"} & skills and "Compliance Manager" not in roles:
            roles.append("Compliance Manager")
        if {"esg", "sustainability"} & skills and "ESG Manager" not in roles:
            roles.append("ESG Manager")
        if {"hse", "safety"} & skills and "HSE Manager" not in roles:
            roles.append("HSE Manager")

        return roles[:5] or ["Career Manager"]

    def _handle_career_execution(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Turn career-discovery requests into concrete executable searches."""
        industry_targets = self._extract_career_industry_targets(message, profile)
        primary_industry = industry_targets[0]
        industry_label = primary_industry.title()
        roles = self._career_execution_roles(profile, industry_targets)
        queries = [f"{role} {industry_label} UAE" for role in roles]

        all_matches: list[dict[str, Any]] = []
        for query in queries:
            try:
                all_matches.extend(self._search_jsearch_direct(query))
            except Exception as exc:
                logger.debug("career_execution_search_failed query=%r error=%s", query, exc)

        top_matches = self._sort_by_company_quality(
            self._rerank_by_learned_preferences(all_matches, user_id)
        )[:5]
        formatted = [self._format_match(m, profile) for m in top_matches]
        execution_state = "MATCHES_SCORED" if formatted else "SEARCH_RUNNING"
        role_text = ", ".join(roles[:3])
        msg = (
            f"I will use your CV profile to search concrete {industry_label} career paths in the UAE. "
            f"I am starting with: {role_text}."
        )
        if formatted:
            msg += f" I found {len(formatted)} current match(es)."
        else:
            msg += " I did not find scored matches yet, so these searches are ready to refine."

        response = {
            "type": "job_matches",
            "intent": "career_execution",
            "execution_state": execution_state,
            "active_profile": bool(profile),
            "message": msg,
            "matches": formatted,
            "next_action": "search_jobs",
            "industry_targets": industry_targets,
            "last_search_queries": queries,
        }
        self._append_chat(user_id, "assistant", response)
        if formatted:
            self._store_search_matches_context(user_id, formatted)
        return response

    @staticmethod
    def _looks_like_next_step_followup(message: str) -> bool:
        """True for short post-confirmation follow-ups like 'so?' or 'what now?'."""
        text = RicoChatAPI._normalize_followup_phrase(message)
        return text in RicoChatAPI._FOLLOWUP_NEXT_STEP_PHRASES

    @staticmethod
    def _normalize_followup_phrase(message: str) -> str:
        """Normalize short follow-up text so punctuation does not break fast paths."""
        text = re.sub(r"\s+", " ", (message or "").strip().lower())
        return FOLLOWUP_BOUNDARY_PUNCT_RE.sub("", text)

    def _handle_next_step_options(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Return instant options after role confirmation — no AI, no pipeline."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        suggestions = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        # Prefer fresh CV-derived suggestions over potentially stale target_roles
        role = (
            suggestions[0]["label"] if suggestions
            else target_roles[0] if target_roles
            else "your target role"
        )

        response: dict[str, Any] = {
            "type": "options",
            "message": "Next, choose what you want me to do.",
            "options": [
                {
                    "action": "find_live_jobs",
                    "label": "Find live UAE jobs",
                    "message": f"find live jobs for {role}",
                    "role": role,
                },
                {
                    "action": "save_target_role",
                    "label": "Save as target role",
                    "message": f"save {role} as target role",
                    "role": role,
                },
                {
                    "action": "prepare_application_angle",
                    "label": "Prepare application angle",
                    "message": f"prepare application angle for {role}",
                    "role": role,
                },
                {
                    "action": "show_profile_roles",
                    "label": "Show roles from my CV",
                    "message": "show roles from my CV",
                },
            ],
            "next_action": "choose_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _handle_keep_all_target_roles(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Handle 'keep all' follow-up - confirm keeping all target roles."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role_text = ", ".join(map(str, target_roles)) if target_roles else "your current target roles"

        response = {
            "type": "target_roles_confirmed",
            "message": f"Got it — I will keep all current target roles: {role_text}.",
            "target_roles": target_roles,
            "next_actions": [
                {"action": "find_live_jobs", "label": "Find live UAE jobs", "message": "find live jobs for my target roles"},
                {"action": "prepare_application_angle", "label": "Prepare application angle", "message": "prepare application angle for my target roles"},
                {"action": "show_profile_roles", "label": "Show roles from my CV", "message": "show roles from my CV"},
            ],
            "next_action": "choose_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _handle_both_requested_actions(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Handle 'both please' follow-up - trigger both job search and resume review."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[-1] if target_roles else "your target role"

        response = {
            "type": "combined_action_plan",
            "message": (
                f"Got it — I will do both: start with live UAE job matching for {role}, "
                "then prepare your resume/application angle for the strongest matches."
            ),
            "next_actions": [
                {"action": "find_live_jobs", "label": "Find live UAE jobs", "message": f"find live jobs for {role}"},
                {"action": "prepare_application_angle", "label": "Prepare application angle", "message": f"prepare application angle for {role}"},
            ],
            "next_action": "find_live_jobs_then_prepare_application",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _looks_like_selected_role(self, message: str, profile: Any) -> bool:
        """True when the message looks like a user selecting a suggested role.

        Guards (checked in order, fail-fast):
          1. Non-empty, not live search, not generic job request
          2. No question mark
          3. No action verbs (find/search/show/...)
          4. Short phrase -- _looks_like_bare_target_role
          5. Exact or fuzzy match: generated suggestions + target_roles
          6. Fallback: classify_role_candidate says profile_relevant or known_but_off_profile
        """
        if not message or not profile:
            return False

        text       = message.strip()
        text_lower = text.lower()

        if self._is_live_job_search_request(text_lower):
            return False
        if self._looks_like_generic_job_request(text_lower):
            return False
        if "?" in text:
            return False
        if set(text_lower.split()) & self._ACTION_WORDS:
            return False
        if not self._looks_like_bare_target_role(text):
            return False

        # Build known-role set: generated suggestions + saved target_roles
        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
        )
        known: set[str] = {s["label"].lower() for s in suggested}
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        known.update(r.lower() for r in target_roles if isinstance(r, str))

        if text_lower in known:
            return True
        for k in known:
            if k in text_lower or text_lower in k:
                return True

        # Classifier fallback - only profile_relevant roles get fast-path confirmation
        # known_but_off_profile roles should go through _classified_role_search for clarification
        try:
            classification, canonical_role = classify_role_candidate(text, profile)
            if classification == "profile_relevant" and canonical_role:
                return True
        except Exception:
            pass

        return False

    def _extract_selected_role(self, message: str, profile: Any) -> str:
        """Extract the best-matched role label, preserving acronym casing."""
        text       = (message or "").strip()
        text_lower = text.lower()

        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
        )
        # Exact match in suggestions
        for s in suggested:
            if s["label"].lower() == text_lower:
                return s["label"]

        # Exact match in target_roles
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        for r in target_roles:
            if isinstance(r, str) and r.lower() == text_lower:
                return r

        # Fuzzy: suggestion label contained in message
        for s in suggested:
            if s["label"].lower() in text_lower:
                return s["label"]

        # Fuzzy: saved role contained in message
        for r in target_roles:
            if isinstance(r, str) and r.lower() in text_lower:
                return r

        # Classifier canonical name
        try:
            _, canonical_role = classify_role_candidate(text, profile)
            if canonical_role:
                return canonical_role
        except Exception:
            pass

        return self.normalize_role_label(text)

    def _handle_role_confirmation(
        self, user_id: str, role: str, profile: Any
    ) -> dict[str, Any]:
        """Deterministic role_confirmation -- no AI, no external calls."""
        skills = self._as_list(self._profile_value(profile, "skills"))
        years  = self._profile_value(profile, "years_experience")
        certs  = self._as_list(self._profile_value(profile, "certifications"))

        skill_lower = [s.lower() for s in skills]
        cert_lower  = [c.lower() for c in certs]
        all_lower   = skill_lower + cert_lower

        # Safe numeric parsing
        try:
            years_num = float(years)
        except (TypeError, ValueError):
            years_num = None

        reasons: list[str] = []

        if any(k in s for s in all_lower for k in ("iso", "audit", "compliance")):
            reasons.append("You have ISO, audit, or compliance background.")

        if any(k in c for c in cert_lower for k in ("nebosh", "iosh")):
            reasons.append("Your safety certifications support this role.")

        if any(k in s for s in all_lower for k in ("environmental", "esg", "sustainability")):
            reasons.append("Your background aligns with environmental and sustainability work.")

        if any("hse" in s or "safety" in s for s in skill_lower):
            reasons.append("Your HSE/safety background matches this role.")

        if years_num is not None:
            if years_num >= 10:
                reasons.append("Your experience level supports senior roles.")
            elif years_num >= 5:
                reasons.append("Your experience level supports experienced professional roles.")
            else:
                reasons.append(f"Your ~{int(years_num)} years of experience fits this role.")

        if not reasons:
            reasons.append("This role aligns with your profile.")

        response = {
            "type": "role_confirmation",
            "message": f"{role} is a strong fit for your CV.",
            "role": role,
            "reasons": reasons,
            "next_actions": [
                {
                    "action":  "find_live_jobs",
                    "label":   "Find live UAE jobs",
                    "message": f"find live jobs for {role}",
                    "role":    role,
                },
                {
                    "action":  "save_target_role",
                    "label":   "Save as target role",
                    "message": f"save {role} as target role",
                    "role":    role,
                },
                {
                    "action":  "prepare_application_angle",
                    "label":   "Prepare application angle",
                    "message": f"prepare application angle for {role}",
                    "role":    role,
                },
            ],
            "next_action": "choose_role_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    @staticmethod
    def _format_match(m: dict[str, Any], profile: Any) -> dict[str, Any]:
        """Return a backward-compatible chat match with v1 structured guidance."""
        explanation = build_match_explanation(m, profile)

        raw_score = m.get("rico_score") or m.get("score")
        # Normalize to [0.0, 1.0] — frontend multiplies by 100 for display.
        # Legacy scoring pipeline (scoring.py) emits 0–100 integers; FitScore
        # (scorer.py) already emits 0.0–1.0 floats. Values > 1 are divided by 100.
        # None is emitted when no scorer ran — the frontend hides the score badge.
        if raw_score:
            _s = float(raw_score)
            normalized_score: float | None = round(max(0.0, min(1.0, _s / 100.0 if _s > 1.0 else _s)), 4)
            if normalized_score == 0.0:
                normalized_score = None
        else:
            normalized_score = None

        # Preserve URL fields so the frontend can surface apply links and distinguish
        # verified live postings from leads that still need a working apply URL.
        # alt_link (job_google_link) is kept separately so the apply-fallback chain
        # can offer an alternate link when the primary apply URL is unavailable.
        apply_url = str(
            m.get("job_apply_link") or m.get("apply_link") or m.get("link") or ""
        ).strip()
        alt_link = str(m.get("job_google_link") or m.get("alt_link") or "").strip()
        source_url = str(
            m.get("source_url") or alt_link or apply_url
        ).strip()

        # Classify source quality from domain patterns — no network call.
        # Google Jobs links (jobs.google.com, google.com/search) are search
        # intermediary pages, not direct apply URLs. Move them to alt_link so
        # the frontend can offer them as a fallback, but don't present them as
        # the primary "Apply" action.
        try:
            from src.services.source_quality import classify_url, is_google_intermediary, classify_company
            if apply_url and is_google_intermediary(apply_url):
                if not alt_link:
                    alt_link = apply_url
                apply_url = ""
                verification_status = "google_intermediary"
            else:
                verification_status = classify_url(apply_url or source_url)
            company_quality = classify_company(str(m.get("company") or ""))
        except Exception:
            verification_status = "needs_source_verification" if apply_url else "lead_needs_verification"
            company_quality = "ok"

        result = {
            "title": str(m.get("title") or "Untitled role"),
            "company": str(m.get("company") or "Unknown company"),
            "score": normalized_score,
            "apply_url": apply_url,
            "source_url": source_url,
            "alt_link": alt_link,
            "verification_status": verification_status,
            "company_quality": company_quality,
            "actions": ["Prepare application", "Save", "Ask why", "Skip"],
            **explanation,
        }

        location = m.get("location")
        if location:
            result["location"] = str(location)

        why = m.get("rico_explanation")
        if why:
            result["why"] = str(why)

        return result

    @staticmethod
    def _sort_by_company_quality(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Stable sort: named/verified companies first, anonymous/low-quality last.

        Does not remove any jobs — low-quality entries appear at the tail so they
        are only shown when there are not enough better alternatives.
        """
        try:
            from src.services.source_quality import is_low_quality_company as _lqc
            return sorted(matches, key=lambda m: 1 if _lqc(str(m.get("company") or "")) else 0)
        except Exception:
            return matches

    @staticmethod
    def _rerank_by_learned_preferences(
        matches: list[dict[str, Any]],
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Boost jobs matching the user's learned role/location preferences to the top.

        Scoring (lower = better, stable secondary sort preserves original order):
          -3  title contains a preferred role
          -2  location contains a preferred location
          +5  company in avoided list

        Falls back to original order when no preferences are recorded or on error.
        """
        if not matches or not user_id:
            return matches
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            pref_roles = [r.lower() for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
            pref_locs = [loc.lower() for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
            avoided = {
                c.lower()
                for c, w in _lr.get_top_preferences(user_id, "company", limit=10)
                if w < 0
            }
            if not pref_roles and not pref_locs and not avoided:
                return matches

            def _pref_key(m: dict[str, Any]) -> int:
                title = (m.get("title") or "").lower()
                location = (m.get("location") or m.get("city") or "").lower()
                company = (m.get("company") or "").lower()
                score = 0
                if any(r in title for r in pref_roles):
                    score -= 3
                if any(loc in location for loc in pref_locs):
                    score -= 2
                if company in avoided:
                    score += 5
                return score

            return sorted(matches, key=_pref_key)
        except Exception:
            return matches

    def _get_openai_agent(self) -> RicoOpenAIAgent:
        """Get or create OpenAI agent instance."""
        agent = getattr(self, "openai_agent", None)
        if agent is None:
            agent = RicoOpenAIAgent()
            self.openai_agent = agent
        return agent

    SOURCE_KEYWORD = "keyword"
    SOURCE_OPENAI = "openai"
    SOURCE_DEEPSEEK = "deepseek"
    SOURCE_HF = "huggingface"
    SOURCE_FALLBACK = "fallback"
    SOURCE_RATE_LIMITED = "rate_limited"

    @staticmethod
    def _source_for_openai_response(response: dict[str, Any]) -> str:
        """Determine source type from response metadata."""
        rtype = response.get("type")
        if rtype == "openai_response":
            return RicoChatAPI.SOURCE_OPENAI
        if rtype == "deepseek_response":
            return RicoChatAPI.SOURCE_DEEPSEEK
        if rtype == "hf_response":
            return RicoChatAPI.SOURCE_HF
        if (
            rtype in {"openai_rate_limited", "deepseek_rate_limited"}
            or response.get("provider_state") == "rate_limited"
        ):
            return RicoChatAPI.SOURCE_RATE_LIMITED
        return RicoChatAPI.SOURCE_FALLBACK

    @staticmethod
    def _bool_attr(agent: Any, name: str, *, fallback: str | None = None) -> bool:
        """Get boolean attribute from agent with optional fallback."""
        value = getattr(agent, name, None)
        if isinstance(value, bool):
            return value
        if fallback:
            fallback_value = getattr(agent, fallback, None)
            if isinstance(fallback_value, bool):
                return fallback_value
        return False

    def _finalize(
        self,
        response: dict[str, Any],
        source: str,
        *,
        profile: Any = None,
    ) -> dict[str, Any]:
        """Finalize response with metadata."""
        agent = self._get_openai_agent()

        # Get Jotform form IDs from environment
        jotform_form_id = os.getenv("JOTFORM_FORM_ID") or os.getenv("JOTFORM_RICO_FORM_ID")

        # Provider diagnostics are only logged internally, not exposed to users
        # Admin diagnostics available at /health/ai-provider endpoint
        return {
            **response,
            "response_source": response.get("response_source", source),
            "openai_available": self._bool_attr(agent, "openai_available", fallback="available"),
            "deepseek_available": self._bool_attr(agent, "deepseek_available"),
            "hf_available": self._bool_attr(agent, "hf_available"),
            "provider_available": self._bool_attr(agent, "provider_available", fallback="available"),
            "openai_model": str(getattr(agent, "model", "") or ""),
            "profile_context_present": profile is not None,
            # Always a string — null would fail frontend Zod schema validation.
            "jotform_form_id": jotform_form_id or "",
        }

    # Phrases that signal the user wants to provide a CV — either uploading now
    # or announcing that they have one. None of these require an actual file to
    # be present in the message; they trigger a redirect to the upload button.
    _CV_INTENT_PHRASES: tuple[str, ...] = (
        "uploaded cv", "upload cv", "uploaded resume", "upload resume",
        "my cv", "my resume", "resume attached", "cv attached",
        "i have a cv", "i have a resume", "have a cv", "have a resume",
        "have my cv", "have my resume",
        "i'll upload", "ill upload", "will upload", "going to upload",
        "upload it", "uploading my cv", "uploading my resume",
        "attach my cv", "attach my resume",
        "سيرتي الذاتية", "رفع السيرة", "لدي سيرة",
    )

    def _looks_like_cv_upload(self, message: str) -> bool:
        lower = message.lower()
        if bool(CV_FILE_RE.search(message)) or any(
            phrase in lower for phrase in self._CV_INTENT_PHRASES
        ):
            return True
        # Detect raw pasted CV text: long message with structural CV sections
        return self._looks_like_pasted_cv_text(message)

    _PASTED_CV_SECTION_RE = re.compile(
        r"\b(work\s+experience|professional\s+experience|employment\s+history"
        r"|education|qualifications|skills|certifications|objective|summary"
        r"|خبرات?\s+عمل|المؤهلات|مهارات|تعليم|الخبرة\s+العملية)\b",
        re.IGNORECASE | re.UNICODE,
    )
    _PASTED_CV_DATE_RE = re.compile(
        r"\b(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|present|current|now|حتى\s+الآن)\b",
        re.IGNORECASE | re.UNICODE,
    )

    def _looks_like_pasted_cv_text(self, message: str) -> bool:
        """Heuristic: long message containing CV structural signals → treat as pasted CV."""
        if len(message) < 400:
            return False
        section_hits = len(self._PASTED_CV_SECTION_RE.findall(message))
        date_hits = len(self._PASTED_CV_DATE_RE.findall(message))
        # Require at least 2 section keywords OR 1 section + 1 date range
        return section_hits >= 2 or (section_hits >= 1 and date_hits >= 1)

    def _looks_like_cv_intent_no_file(self, message: str) -> bool:
        """True when user announces they have a CV but hasn't attached a file yet."""
        lower = message.lower()
        if CV_FILE_RE.search(message):
            return False  # actual filename present — handled by cv_first_profile_response
        announce_phrases = (
            "i have a cv", "i have a resume", "have a cv", "have a resume",
            "have my cv", "have my resume",
            "i'll upload", "ill upload", "will upload", "going to upload",
            "upload it", "uploading my cv", "uploading my resume",
            "attach my cv", "attach my resume",
            "سيرتي الذاتية", "رفع السيرة", "لدي سيرة",
        )
        return any(phrase in lower for phrase in announce_phrases)

    def _extract_inline_contact_updates(self, message: str) -> dict[str, Any]:
        """Extract email, phone, and Telegram handle from message."""
        updates: dict[str, Any] = {}
        emails = EMAIL_RE.findall(message)
        phones = PHONE_RE.findall(message)
        if emails:
            updates["email"] = emails[0]
        if phones:
            updates["phone"] = phones[0].strip()
        m = TELEGRAM_MENTION_RE.search(message)
        if m:
            handle = m.group(1) or m.group(2)
            if handle:
                updates["telegram_username"] = handle
        return updates

    def _cv_first_profile_response(self, user_id: str, message: str) -> dict[str, Any]:
        """Handle CV-first profile creation response."""
        filename_match = CV_FILE_RE.search(message)
        filename = filename_match.group(0).strip() if filename_match else "uploaded CV"
        updates = {
            "profile_creation_mode": "cv_first",
            "cv_filename": filename,
            "cv_status": "received_pending_extraction",
            "manual_profile_wizard_disabled": True,
        }
        updates.update(self._extract_inline_contact_updates(message))
        profile = upsert_profile(user_id=user_id, updates=updates)

        missing = [
            ONBOARDING_FIELD_LABELS.get(key, key)
            for key, label in [
                ("email", "email address"),
                ("phone", "phone number"),
                ("preferred_city", "preferred UAE city"),
                ("target_roles", "target role"),
                ("salary_expectation_aed", "salary expectation"),
                ("deal_breakers", "roles or companies to avoid"),
            ]
            if not getattr(profile, key, None) and not (isinstance(profile, dict) and profile.get(key))
        ]

        response = {
            "type": "cv_first_profile",
            "message": (
                f"I found your {filename} and I'll use it to search for matching UAE jobs. "
                "I'm checking roles that fit your background now."
            ),
            "next_action": "parse_cv_and_prefill_profile",
            "manual_questions_disabled": True,
            "missing_after_extraction_should_be_limited_to": missing,
            "confirmation_prompt": (
                "After extraction, show the profile summary and ask: save this profile, or edit a field?"
            ),
        }
        self._append_chat(user_id, "assistant", response)
        return response

    def _handle_pasted_cv_text(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Handle raw pasted CV text from an active user.

        Extracts inline contact details, stores the CV text for async parsing,
        and returns a structured acknowledgement without sending the blob to AI.
        """
        updates: dict[str, Any] = {"pasted_cv_pending": True}
        updates.update(self._extract_inline_contact_updates(message))
        # Truncate stored text to 8000 chars to avoid DB size issues
        updates["pasted_cv_text"] = message[:8000]
        upsert_profile(user_id=user_id, updates=updates)

        response_msg = (
            "I can see your CV details. I'll extract your profile from this text — "
            "give me a moment to parse your experience, skills, and education.\n\n"
            "Once extracted, I'll show you a profile summary and you can confirm or edit any field. "
            "You can also upload a PDF or Word CV for more accurate extraction."
        )
        response = {
            "type": "cv_text_received",
            "message": response_msg,
            "next_action": "parse_pasted_cv_text",
        }
        self._append_chat(user_id, "assistant", response_msg)
        return response

    _WHATS_NEXT_PHRASES = frozenset([
        "what's next", "whats next", "what next", "what now",
        "what can you do", "what can i do", "help", "options", "menu",
        "show options", "show menu", "next steps",
    ])

    # Phrases users type when selecting a help-menu option or expressing generic
    # job-search intent — must NEVER be classified as job role titles.
    _JOB_SEARCH_HELP_PHRASES: frozenset[str] = frozenset({
        "finding jobs",
        "finding jobs matching my target roles",
        "find matching uae jobs",
        "find me matching jobs",
        "job search",
        "job searching",
        "search for jobs",
        "help me find jobs",
        "help me search for jobs",
    })

    _ACTION_WORDS = frozenset({
        "find", "search", "show", "get", "apply", "save",
        "prepare", "draft", "update", "track",
    })

    _FOLLOWUP_NEXT_STEP_PHRASES = frozenset({
        "so", "so?", "what now", "what now?", "what's next", "whats next",
        "next", "next?", "then", "then?", "now", "now?", "ok", "okay",
        "continue", "go on",
    })

    # Multi-word continuation phrases that are never job role titles.
    # Matched after normalisation — see _is_continuation_intent().
    _CONTINUATION_PHRASES: frozenset[str] = frozenset({
        # English multi-word — bare "continue" / "go on" are intentionally excluded
        # because they are already in _FOLLOWUP_NEXT_STEP_PHRASES and route to the
        # options menu via _looks_like_next_step_followup (which strips punctuation).
        "keep going", "its ok keep going", "it's ok keep going",
        "ok keep going", "okay keep going",
        "go ahead", "go ahead please", "please go ahead",
        "yes continue", "yes please continue", "sure continue",
        "ok continue", "okay continue", "yes go ahead",
        "continue please", "please continue", "just continue",
        "carry on", "yes carry on", "ok carry on",
        "sounds good continue", "let's continue", "lets continue",
        "proceed", "yes proceed", "ok proceed",
        # Arabic
        "كمل", "استمر", "واصل", "ماشي كمل", "ماشي استمر",
        "تمام كمل", "تمام استمر", "اوك كمل", "اوك استمر",
        "يلا كمل", "يلا استمر", "نعم استمر", "نعم كمل",
        "حسنا استمر", "طيب كمل", "طيب استمر",
    })

    # Signals in the last assistant message that indicate a post-CV/profile
    # context where continuation means "proceed with job search".
    _POST_CV_CONTINUATION_SIGNALS: tuple[str, ...] = (
        "based on your cv", "from your cv", "your cv has been",
        "cv parsed", "cv uploaded", "profile built", "profile updated",
        "i suggest", "suggested roles", "i found the following roles",
        "roles from your background", "roles i suggest",
        "what would you like to do", "what should i search",
        "shall i start searching", "shall i search",
        "ready to search", "you can now search",
        "want me to search", "search for roles",
        "بناءً على سيرتك", "بناء على سيرتك", "تم تحليل سيرتك",
        "الأدوار المقترحة", "ماذا تريد أن أفعل", "هل أبحث",
    )

    # Affirmative / negative single-word replies in EN + AR
    _AFFIRMATIVE_PHRASES = frozenset({
        "yes", "yeah", "yep", "yup", "sure", "absolutely", "of course",
        "please", "go ahead", "do it", "ok", "okay", "alright", "sounds good",
        "نعم", "أيوه", "ايوه", "اوك", "حسنا", "تفضل", "اكيد", "طبعا", "موافق",
        "بالتأكيد", "نعم من فضلك", "يلا", "اه", "آه",
    })
    _NEGATIVE_PHRASES = frozenset({
        "no", "nope", "nah", "not now", "skip", "cancel", "never mind",
        "لا", "لأ", "مو الحين", "مو ذا", "بعدين", "ما ابي", "ما أبغى",
    })

    _ARABIC_WHAT_NOW_TERMS = frozenset({
        "مالحل", "ما الحل", "ماالحل",
        "مالحل الان", "مالحل الآن",
        "ايش نسوي", "شو نسوي",
        "ايش اسوي", "شو اسوي",
        "وش نسوي",
    })

    @staticmethod
    def _is_arabic_what_now(message: str) -> bool:
        """True for Arabic 'what now / what's the solution' follow-up phrases."""
        text = re.sub(r"[\s؟?.!,]+", " ", (message or "").strip().lower()).strip()
        return any(term in text for term in RicoChatAPI._ARABIC_WHAT_NOW_TERMS)

    @staticmethod
    def _is_affirmative(message: str) -> bool:
        """True for yes/نعم/sure single-word affirmatives."""
        text = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return text in RicoChatAPI._AFFIRMATIVE_PHRASES

    @staticmethod
    def _is_continuation_intent(message: str) -> bool:
        """True for multi-word 'keep going / continue / كمل' phrases that are never job titles.

        Catches messages like "its ok keep going", "ok keep going", "كمل", "استمر"
        that pass _looks_like_bare_target_role because their first token is not in
        _NON_ROLE_STARTERS, but whose intent is clearly "proceed, not a role name".
        """
        text = re.sub(r"[\s؟?.!،,‌‍]+", " ", (message or "").strip().lower()).strip()
        if text in RicoChatAPI._CONTINUATION_PHRASES:
            return True
        # Regex patterns for common continuation structures not worth enumerating
        if re.fullmatch(
            r"(its?\s+ok(ay)?\s+)?keep\s+going|"
            r"(ok(ay)?|sure|yes|alright)\s+(keep\s+going|continue|go\s+on|carry\s+on|proceed)|"
            r"(just\s+)(continue|proceed|carry\s+on|go\s+ahead)(\s+please)?|"
            r"(continue|proceed|carry\s+on|go\s+ahead)\s+please|"
            r"please\s+(continue|proceed|carry\s+on|go\s+ahead)|"
            r"(كمل|استمر|واصل)(\s+من\s+فضلك)?|"
            r"(ماشي|تمام|اوك|يلا|نعم|حسنا|طيب)\s+(كمل|استمر|واصل)",
            text,
        ):
            return True
        return False

    @staticmethod
    def _is_negative(message: str) -> bool:
        """True for no/لا single-word negatives."""
        text = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return text in RicoChatAPI._NEGATIVE_PHRASES

    @staticmethod
    def _is_arabic_text(message: str) -> bool:
        return bool(re.search(r"[\u0600-\u06FF]", message or ""))

    @staticmethod
    def _wants_no_favorite(message: str) -> bool:
        lower = (message or "").lower()
        return bool(
            re.search(r"\b(do\s*not|don't|dont|no|not)\b.{0,24}\b(favou?rite|save|bookmark)\b", lower)
            or re.search(r"\b(favou?rite|save|bookmark)\b.{0,24}\b(no|not)\b", lower)
            or "لا تحفظ" in message
            or "لا تضيف" in message
            or "مفضلة" in message and ("لا" in message or "بدون" in message)
        )

    @staticmethod
    def _requests_application_draft(message: str) -> bool:
        lower = (message or "").lower()
        if re.search(r"\b(draft|write|compose|prepare|generate|create)\b.{0,50}\b(message|email|letter|cover|inmail|linkedin)\b", lower):
            return True
        normalized = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", message or "")
        normalized = re.sub(r"[آأإٱ]", "ا", normalized)
        has_message_word = "رساله" in normalized or "رسالة" in normalized
        has_draft_verb = any(term in normalized for term in ("صيغ", "اكتب", "اكتبها", "جهز", "نراجع"))
        return has_draft_verb or (has_message_word and RicoChatAPI._requests_application_send(message))

    @staticmethod
    def _requests_application_send(message: str) -> bool:
        lower = (message or "").lower()
        if re.search(r"\b(send|submit|forward|deliver|go ahead|proceed|do it)\b", lower):
            return True
        normalized = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", message or "")
        normalized = re.sub(r"[آأإٱ]", "ا", normalized)
        return any(term in normalized for term in ("ارسل", "ارسال", "ابعث", "قدّم", "قدم", "كمل"))

    @staticmethod
    def _mentions_linkedin_channel(message: str) -> bool:
        lower = (message or "").lower()
        return "linkedin" in lower or "inmail" in lower or "لينكد" in message

    @staticmethod
    def _looks_like_application_channel_followup(message: str) -> bool:
        if not message or not message.strip():
            return False
        return (
            RicoChatAPI._requests_application_draft(message)
            or RicoChatAPI._requests_application_send(message)
            or RicoChatAPI._wants_no_favorite(message)
        )

    @staticmethod
    def _job_context_value(job: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = job.get(key)
            if value:
                return str(value).strip()
        return ""

    def _resolve_recent_application_job(self, user_id: str) -> dict[str, Any] | None:
        """Return the most recent job/application context for draft/send follow-ups."""
        try:
            ctx = self._get_recent_context(user_id)
        except Exception:
            ctx = {}
        if not isinstance(ctx, dict) or not ctx:
            return None

        pending = ctx.get("_pending_application_send")
        if isinstance(pending, dict) and isinstance(pending.get("job"), dict):
            return dict(pending["job"])

        app = ctx.get("recent_application") if isinstance(ctx.get("recent_application"), dict) else {}
        job: dict[str, Any] = {
            "title": app.get("title") or ctx.get("recent_job") or ctx.get("recent_search_role") or "",
            "company": app.get("company") or ctx.get("recent_company") or "",
            "location": app.get("location") or ctx.get("recent_location") or "",
            "salary": (
                app.get("salary") or app.get("salary_range") or app.get("salary_string")
                or ctx.get("recent_salary") or ctx.get("salary") or ""
            ),
            "link": app.get("link") or app.get("apply_url") or app.get("source_url") or "",
            "status": app.get("status") or ctx.get("recent_status") or "",
        }

        matches = ctx.get("recent_search_matches") or []
        if isinstance(matches, list):
            for match in matches:
                if not isinstance(match, dict):
                    continue
                title = str(match.get("title") or "")
                company = str(match.get("company") or "")
                if (
                    (job["title"] and job["title"].lower() in title.lower())
                    or (job["company"] and job["company"].lower() in company.lower())
                    or not job["title"]
                ):
                    for key in ("title", "company", "location"):
                        if not job.get(key) and match.get(key):
                            job[key] = str(match[key]).strip()
                    job["salary"] = job.get("salary") or self._job_context_value(
                        match, "salary", "salary_range", "salary_string", "salary_range_aed"
                    )
                    job["link"] = job.get("link") or self._job_context_value(
                        match, "apply_url", "source_url", "link", "alt_link"
                    )
                    break

        if not (job.get("title") or job.get("company")):
            return None
        return job

    @staticmethod
    def _format_application_job_context(job: dict[str, Any], *, arabic: bool) -> str:
        title = RicoChatAPI._job_context_value(job, "title") or ("الدور" if arabic else "the role")
        company = RicoChatAPI._job_context_value(job, "company") or ("الشركة" if arabic else "the company")
        location = RicoChatAPI._job_context_value(job, "location")
        salary = RicoChatAPI._job_context_value(job, "salary", "salary_range", "salary_string", "salary_range_aed")
        if arabic:
            parts = [f"{title} - {company}"]
            if location:
                parts.append(location)
            if salary:
                parts.append(salary)
            return "، ".join(parts)
        parts = [f"{title} at {company}"]
        if location:
            parts.append(location)
        if salary:
            parts.append(salary)
        return " - ".join(parts)

    def _draft_application_message(self, job: dict[str, Any], profile: Any, *, arabic: bool) -> str:
        title = self._job_context_value(job, "title") or ("الدور" if arabic else "the role")
        company = self._job_context_value(job, "company") or ("الشركة" if arabic else "the company")
        skills = self._as_list(self._profile_value(profile, "skills"))
        certs = self._as_list(self._profile_value(profile, "certifications"))
        strengths = ", ".join(str(s) for s in (skills + certs)[:4]) or ("خبرتي ذات الصلة" if arabic else "my relevant experience")
        if arabic:
            return (
                f"مرحباً،\n\n"
                f"أود التقدم لدور {title} لدى {company}. لدي خبرة مرتبطة بمتطلبات الدور، "
                f"خصوصاً في {strengths}. أعتقد أن خلفيتي في التدقيق والامتثال البيئي يمكن أن تضيف قيمة مباشرة للفريق.\n\n"
                f"يسعدني مشاركة سيرتي الذاتية ومناقشة كيف يمكنني دعم احتياجاتكم.\n\n"
                f"مع التحية"
            )
        return (
            f"Hello,\n\n"
            f"I would like to apply for the {title} role at {company}. My background aligns with the role, "
            f"especially around {strengths}. I believe my audit, compliance, and UAE-market experience can add value quickly.\n\n"
            f"I would be happy to share my CV and discuss how I can support your team.\n\n"
            f"Best regards"
        )

    def _handle_application_channel_followup(
        self, user_id: str, message: str, profile: Any
    ) -> dict[str, Any] | None:
        """Clarify draft/send channels without claiming unsupported application submission."""
        if not self._looks_like_application_channel_followup(message):
            return None

        job = self._resolve_recent_application_job(user_id)
        if not job:
            return None

        arabic = self._is_arabic_text(message)
        wants_draft = self._requests_application_draft(message)
        wants_send = self._requests_application_send(message)
        no_favorite = self._wants_no_favorite(message)
        recruiter_email = EMAIL_RE.search(message or "")
        link = self._job_context_value(job, "link", "apply_url", "source_url")
        linkedin_context = self._mentions_linkedin_channel(message) or "linkedin" in link.lower() or "inmail" in link.lower()
        job_context = self._format_application_job_context(job, arabic=arabic)

        draft = self._draft_application_message(job, profile, arabic=arabic)
        if arabic:
            lead = f"تمام، لن أضيفها إلى المفضلة. السياق الحالي: {job_context}." if no_favorite else f"السياق الحالي: {job_context}."
            if wants_draft:
                message_text = f"{lead}\n\nهذه صياغة نراجعها:\n\n{draft}\n\n"
                if wants_send:
                    message_text += (
                        "هل تريد إرسالها عبر البريد؟ أرسل لي إيميل الـ recruiter. "
                        "أما LinkedIn/InMail فأعطيك النص للنسخ واللصق فقط، ولا أستطيع إرسالها عبر LinkedIn مباشرة. "
                        "ولو كانت بوابة توظيف، أستطيع إرشادك للرابط فقط ولا أدّعي التقديم المباشر."
                    )
                else:
                    message_text += "إذا أردت إرسالها، أعطني إيميل الـ recruiter أو رابط/طريقة الإرسال. بوابات التوظيف أتعامل معها كرابط وإرشاد فقط."
            else:
                message_text = (
                    f"{lead}\n\nأعطني إيميل الـ recruiter أو رابط/طريقة الإرسال. "
                    "إذا كانت LinkedIn/InMail فسأعطيك النص للنسخ واللصق فقط، ولا أستطيع إرسالها عبر LinkedIn مباشرة. "
                    "وإذا كانت بوابة توظيف فأستطيع إرشادك للرابط فقط، لا التقديم المباشر."
                )
        else:
            lead = f"Got it - I will not save or favorite it. Current job context: {job_context}." if no_favorite else f"Current job context: {job_context}."
            if wants_draft:
                message_text = f"{lead}\n\nDraft to review:\n\n{draft}\n\n"
                if wants_send:
                    message_text += (
                        "If this should go by email, send me the recruiter's email; I will keep it as a draft unless mail sending is available and explicitly confirmed. "
                        "For LinkedIn/InMail, I can only give you copy/paste text; I cannot send through LinkedIn directly. "
                        "For job portals, I can guide/open the link only; I cannot claim direct submission."
                    )
                else:
                    message_text += "If you want to send it, give me the recruiter email or the apply channel/link. For job portals, I can guide/open the link only."
            else:
                message_text = (
                    f"{lead}\n\nSend where? Give me the recruiter email, or the apply link/channel. "
                    "For LinkedIn/InMail, I can only give you copy/paste text; I cannot send through LinkedIn directly. "
                    "For job portals, I can guide/open the link only; I cannot claim direct submission."
                )
        if recruiter_email and not linkedin_context:
            if arabic:
                message_text += "\n\nوصلني إيميل الـ recruiter. سأبقيها كمسودة جاهزة للمراجعة قبل أي إرسال فعلي."
            else:
                message_text += "\n\nI have the recruiter email. I will keep this as a review-ready draft before any actual send."

        try:
            ctx = self._get_recent_context(user_id)
            ctx["_pending_application_send"] = {
                "job": job,
                "draft": draft,
                "needs_destination": True,
                "linkedin_copy_only": linkedin_context,
            }
            self._store_recent_context(user_id, ctx)
        except Exception:
            pass

        response = {
            "type": "application_channel_clarification" if not wants_draft else "draft_message",
            "intent": "application_channel_clarification",
            "message": message_text,
            "job_title": self._job_context_value(job, "title"),
            "job_company": self._job_context_value(job, "company"),
            "job_context": job_context,
            "draft": draft if wants_draft else "",
            "next_action": "await_send_destination",
            "channel_policy": {
                "linkedin": "copy_paste_only",
                "email": "requires_recruiter_email_and_mail_integration",
                "job_portal": "open_or_guide_only",
            },
        }
        self._append_chat(user_id, "assistant", message_text)
        return response

    # Phrases the user says to request a list of results after Rico shows a summary.
    _LIST_FOLLOWUP_PHRASES = frozenset({
        # English
        "list them", "show them", "show list", "show me", "show me them",
        "list it", "show it", "list", "show all", "show all of them",
        "display them", "give me the list", "give me them", "print them",
        "what are they", "which ones", "tell me which ones",
        # Application/lifecycle-specific aliases (resolve to last lifecycle context)
        "list applications", "show applications",
        "list my applications", "show my applications",
        "list saved", "show saved", "list my saved", "show my saved",
        # Arabic
        "اذكرهم", "اذكرها", "اعرضهم", "اعرضها", "ورجيني القائمة",
        "ورني القائمة", "عرضهم", "عرضها", "اعرض القائمة", "القائمة",
        "وريني", "ورني", "اعرضلي", "اكتبهم", "اكتبها",
    })

    @staticmethod
    def _is_list_followup(message: str) -> bool:
        # Normalize before matching so "list them,," / "list them." both resolve.
        return RicoChatAPI._normalize_followup_phrase(message) in RicoChatAPI._LIST_FOLLOWUP_PHRASES

    # ── Canonical "last turn" memory ─────────────────────────────────────────
    # One reliable record of the last meaningful thing Rico did, so vague
    # follow-ups ("make sure", "that one", "list them") can anchor to a real
    # intent + object instead of being re-classified from scratch by the AI.
    #
    # Only "anchor-worthy" response types update it; clarifications, smalltalk,
    # errors and option menus deliberately do NOT overwrite the anchor, so a
    # follow-up after a clarification still resolves against the last real turn.
    _LAST_TURN_INTENT_BY_TYPE = {
        "application_status":        "application_tracking",
        "application":               "application_tracking",
        "lifecycle_query":           "lifecycle_query",
        "job_matches":               "job_search",
        "job_search_explicit":       "job_search",
        "no_results_recovery":       "job_search",
        "save_job":                  "save_job",
        "track_job":                 "track_job",
        "open_apply_link":           "open_apply_link",
        "mark_applied":              "mark_applied",
        "prepare_application":       "prepare_application",
        "explain_match":             "explain_match",
        "draft_message":             "draft_message",
        "interview_prep":            "interview_prep",
        "profile_summary":           "profile_summary",
        "profile_role_suggestions":  "profile_role_suggestions",
    }

    # Lifecycle/application intents whose anchor a "list them"/"make sure" replays.
    _LAST_TURN_LIFECYCLE_INTENTS = frozenset({"application_tracking", "lifecycle_query"})

    # Short "verify / are you sure / re-confirm" follow-ups. These must NOT fall
    # through to bare-role classification (which would treat "make sure please"
    # as a job title). They re-confirm the last informational turn instead.
    _VERIFY_FOLLOWUP_PHRASES = frozenset({
        "make sure", "make sure please", "please make sure",
        "are you sure", "you sure", "u sure", "sure about that",
        "is that right", "is that correct", "is this correct", "is this right",
        "are you certain", "you certain", "really", "for real", "seriously",
        "double check", "double check please", "check again", "recheck",
        "verify", "verify please", "verify that", "confirm that", "make certain",
        # Arabic
        "متأكد", "هل أنت متأكد", "تأكد", "تأكد من فضلك", "أكد",
    })

    def _set_last_turn(
        self,
        user_id: str,
        *,
        intent: str,
        response_type: str,
        obj: dict[str, Any] | None = None,
        user_message: str = "",
    ) -> None:
        """Persist the single canonical last-turn record."""
        try:
            self.memory.set_context(user_id, "last_turn", {
                "intent": intent,
                "response_type": response_type,
                "object": obj or {},
                "user_message": (user_message or "")[:300],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.debug("rico_chat: failed to store last_turn user=%s", user_id)

    def _get_last_turn(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "last_turn") or {}
        except Exception:
            return {}

    def _record_last_turn(self, user_id: str, message: str, result: dict[str, Any]) -> None:
        """From a finalized response, update the canonical last-turn anchor.

        Only anchor-worthy response types update it (see _LAST_TURN_INTENT_BY_TYPE);
        clarifications / errors / menus are skipped so the anchor stays meaningful.
        """
        if not isinstance(result, dict):
            return
        rtype = str(result.get("type") or "")
        intent = self._LAST_TURN_INTENT_BY_TYPE.get(rtype)
        if not intent:
            return  # not anchor-worthy — keep the previous anchor intact

        obj: dict[str, Any] = {}
        entities = result.get("entities")
        if isinstance(entities, dict):
            if entities.get("title"):
                obj["title"] = entities["title"]
            if entities.get("company"):
                obj["company"] = entities["company"]
        # Carry the lifecycle replay marker so "list them"/"make sure" can re-run it.
        if intent in self._LAST_TURN_LIFECYCLE_INTENTS:
            qt = (self._get_lifecycle_context(user_id) or {}).get("last_query_type")
            if qt:
                obj["query_type"] = qt
        self._set_last_turn(
            user_id, intent=intent, response_type=rtype, obj=obj, user_message=message,
        )

    @staticmethod
    def _is_verify_followup(message: str) -> bool:
        """True for short 'are you sure / make sure / re-confirm' follow-ups."""
        norm = RicoChatAPI._normalize_followup_phrase(message)
        if norm in RicoChatAPI._VERIFY_FOLLOWUP_PHRASES:
            return True
        # Arabic phrases may carry diacritics/extra spacing — check membership loosely.
        stripped = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return stripped in RicoChatAPI._VERIFY_FOLLOWUP_PHRASES

    _VALID_LIFECYCLE_QUERY_TYPES = frozenset({
        "lifecycle_show_saved",
        "lifecycle_show_applied",
        "lifecycle_show_opened_not_applied",
    })

    def _resolve_lifecycle_query_for_followup(self, user_id: str) -> str | None:
        """Resolve which lifecycle query a 'list them' follow-up should replay.

        Prefers the dedicated lifecycle context; falls back to the canonical
        last-turn anchor so the follow-up still works if only the anchor is set.
        """
        last_query = (self._get_lifecycle_context(user_id) or {}).get("last_query_type")
        if last_query in self._VALID_LIFECYCLE_QUERY_TYPES:
            return last_query
        last = self._get_last_turn(user_id)
        if last.get("intent") in self._LAST_TURN_LIFECYCLE_INTENTS:
            qt = (last.get("object") or {}).get("query_type")
            if qt in self._VALID_LIFECYCLE_QUERY_TYPES:
                return qt
            # An application-tracking turn with no explicit query_type defaults
            # to the applied funnel — that's what was just shown.
            if last.get("intent") == "application_tracking":
                return "lifecycle_show_applied"
        return None

    def _resolve_verify_followup(self, user_id: str, profile: Any) -> dict[str, Any] | None:
        """Anchor a 'make sure / are you sure' follow-up to the last real turn.

        Re-runs the last informational query so Rico re-confirms with fresh data
        instead of re-classifying the vague phrase as a new role/intent. Never
        triggers a mutation (apply/save) — those still require explicit action.
        """
        last = self._get_last_turn(user_id)
        intent = last.get("intent")
        if not intent:
            return None

        if intent in self._LAST_TURN_LIFECYCLE_INTENTS:
            lifecycle_query = self._resolve_lifecycle_query_for_followup(user_id)
            if intent == "application_tracking" and not (last.get("object") or {}).get("query_type"):
                # The last turn was the applications summary — re-run it verbatim.
                resp = self._handle_application_tracking(user_id, intent="application_tracking")
            elif lifecycle_query:
                resp = self._handle_lifecycle_query(user_id, lifecycle_query)
            else:
                resp = self._handle_application_tracking(user_id, intent="application_tracking")
            # Prefix so the user sees this as a re-confirmation, not a fresh answer.
            base = resp.get("message") or ""
            resp["message"] = (
                "I double-checked — here's exactly what I have on record:\n\n" + base
                if base else "I double-checked your records."
            )
            return resp

        if intent == "job_search":
            obj = last.get("object") or {}
            title = obj.get("title") or ""
            if title:
                return {
                    "type": "clarification",
                    "message": (
                        f"Yes — the last search I showed you was for \"{title}\". "
                        "Want me to re-run it for fresh live results, or refine the role or city?"
                    ),
                }
            return {
                "type": "clarification",
                "message": (
                    "Yes — that was the latest live search I ran. Want me to re-run it "
                    "for fresh results, or narrow it by role or city?"
                ),
            }

        # Save / apply / track / prepare etc. — confirm the specific job on record.
        obj = last.get("object") or {}
        title = obj.get("title")
        company = obj.get("company")
        if title and company:
            action_label = {
                "save_job": "saved", "track_job": "tracked",
                "mark_applied": "marked as applied", "open_apply_link": "opened the apply link for",
                "prepare_application": "prepared an application for",
            }.get(intent, "noted")
            return {
                "type": "clarification",
                "message": (
                    f"Confirmed — I have \"{title}\" at {company} {action_label} in your tracker. "
                    "Want me to show the full list or take the next step?"
                ),
                "entities": {"title": title, "company": company},
            }
        return None

    def _store_lifecycle_context(self, user_id: str, query_type: str) -> None:
        """Remember the last lifecycle query so a follow-up 'list them' can replay it."""
        try:
            self.memory.set_context(user_id, "lifecycle_query_context", {"last_query_type": query_type})
        except Exception:
            logger.debug("rico_chat: failed to store lifecycle context user=%s", user_id)

    def _get_lifecycle_context(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "lifecycle_query_context") or {}
        except Exception:
            return {}

    def _get_last_assistant_message(self, user_id: str) -> str:
        """Return the last assistant message text for pending-intent resolution."""
        try:
            recent = self._get_recent_messages(user_id, limit=10)
            for m in reversed(recent):
                if m.get("role") == "assistant":
                    return str(m.get("content") or m.get("message") or "")
        except Exception:
            pass
        return ""

    def _set_flow_state(self, user_id: str, state: str) -> None:
        """Persist the current conversational flow state for follow-up routing."""
        try:
            ctx = self._get_recent_context(user_id)
            ctx["last_flow_state"] = state
            self._store_recent_context(user_id, ctx)
        except Exception:
            pass

    def _resolve_pending_intent(self, user_id: str, message: str, profile: Any) -> dict[str, Any] | None:
        """If last Rico message offered a yes/no action and user affirms, execute it.

        Returns a response dict if a pending intent was resolved, else None.
        """
        if not self._is_affirmative(message):
            return None

        last = self._get_last_assistant_message(user_id).lower()
        if not last:
            return None

        # Detect what Rico last offered
        cv_improve_signals = (
            "اقتراح" in last or "تحسين سيرة" in last or "improve your cv" in last
            or "cv improvement" in last or "update your cv" in last
        )
        job_search_signals = (
            "find live" in last or "search for" in last or "ابحث" in last
            or "وظائف حية" in last or "shall i search" in last or "want me to search" in last
            or any(sig in last for sig in self._POST_CV_CONTINUATION_SIGNALS)
        )
        application_angle_signals = (
            "application angle" in last or "cover letter" in last or "tailor" in last
            or "زاوية تقديم" in last
        )
        reminder_signals = (
            "reminder" in last or "follow up" in last or "تذكير" in last
        )

        if cv_improve_signals:
            return self._handle_cv_generate_from_profile(user_id, profile)
        if job_search_signals:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else "my target role"
            return self._answer_with_ai_fallback(
                user_id=user_id,
                message=f"Find live UAE jobs for {role}",
                profile=profile,
                save_user_message=False,
            )
        if application_angle_signals:
            return self._answer_with_ai_fallback(
                user_id=user_id,
                message="Prepare my application angle and suggest how to tailor it for the role.",
                profile=profile,
                save_user_message=False,
            )
        if reminder_signals:
            return {
                "type": "reminder_set",
                "message": "تم ضبط التذكير. سأذكرك بالمتابعة." if "تذكير" in last else "Reminder set. I'll nudge you to follow up.",
            }

        return None

    # ── Pending field resolver ────────────────────────────────────────────────

    _PENDING_FIELD_ASK_SIGNALS: dict[str, tuple[str, ...]] = {
        "telegram_username": (
            "telegram username", "your telegram", "@username",
            "اسم المستخدم في تيليجرام", "تيليجرام",
        ),
        "phone": (
            "phone number", "your phone", "mobile number",
            "رقم الهاتف", "رقم جوالك",
        ),
        "email": (
            "email address", "your email", "بريدك الإلكتروني",
        ),
        "preferred_cities": (
            "preferred cities", "preferred city", "which city", "what city",
            "city (e.g.", "city preference", "المدن المفضلة", "المدينة المفضلة",
        ),
    }

    # Known UAE cities for preferred_cities field resolution
    _UAE_CITIES: frozenset[str] = frozenset({
        "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
        "fujairah", "umm al quwain", "al ain", "deira", "bur dubai",
        "دبي", "أبوظبي", "الشارقة", "عجمان", "رأس الخيمة",
        "الفجيرة", "أم القيوين", "العين",
    })

    def _resolve_pending_field(
        self, user_id: str, message: str, profile: Any
    ) -> "dict[str, Any] | None":
        """Intercept user replies to Rico's field prompts (e.g. 'What is your Telegram?').

        Checks the last assistant message for known field-request signals and, if the
        current user message looks like a valid value for that field, saves it and
        returns a confirmation response — bypassing intent classification entirely.

        Returns a response dict if a pending field was resolved, else None.
        """
        msg = message.strip()
        if not msg:
            return None

        ctx = self._get_recent_context(user_id)
        # Explicit pending field stored by an earlier turn
        pending_field: str | None = ctx.get("_pending_field")

        # Fallback: infer from last assistant message
        if not pending_field:
            last_msg = self._get_last_assistant_message(user_id).lower()
            for field, signals in self._PENDING_FIELD_ASK_SIGNALS.items():
                if any(sig in last_msg for sig in signals):
                    pending_field = field
                    break

        if not pending_field:
            return None

        # ── Telegram handle ───────────────────────────────────────────────────
        if pending_field == "telegram_username":
            handle = msg if msg.startswith("@") else f"@{msg}"
            if not TELEGRAM_HANDLE_RE.match(handle):
                return None
            upsert_profile(user_id=user_id, updates={"telegram_username": handle})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = (
                f"Got it — I've saved your Telegram username as **{handle}**. "
                "You'll receive job alerts and updates there."
            )
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"telegram_username": handle},
            }

        # ── Phone number ──────────────────────────────────────────────────────
        if pending_field == "phone":
            if not PHONE_RE.match(msg):
                return None
            upsert_profile(user_id=user_id, updates={"phone": msg})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = f"Got it — I've saved your phone number as **{msg}**."
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"phone": msg},
            }

        # ── Email address ─────────────────────────────────────────────────────
        if pending_field == "email":
            if not EMAIL_RE.fullmatch(msg):
                return None
            upsert_profile(user_id=user_id, updates={"email": msg})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = f"Got it — I've saved your email as **{msg}**."
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"email": msg},
            }

        # ── Preferred cities (CV flow) ────────────────────────────────────────
        if pending_field == "preferred_cities":
            # Reject messages that look like intents rather than city answers.
            # A city reply is short and does not contain intent-bearing verbs.
            _INTENT_VERBS = re.compile(
                r"\b(find|search|show|get|help|apply|generate|create|make|write|"
                r"update|start|look|resume|cv|cover|letter|job|jobs|work)\b",
                re.IGNORECASE,
            )
            if _INTENT_VERBS.search(msg):
                return None
            # Also reject long free-text answers unlikely to be city names
            if len(msg.split()) > 6:
                return None
            # Accept any non-empty text as city input — normalise and save
            raw_cities = [c.strip() for c in re.split(r"[,،/|]+", msg) if c.strip()]
            if not raw_cities:
                return None
            # Title-case known UAE cities; keep others as entered
            normalised = []
            for c in raw_cities:
                if c.lower() in self._UAE_CITIES:
                    normalised.append(c.title())
                else:
                    normalised.append(c)
            upsert_profile(user_id=user_id, updates={"preferred_cities": normalised})
            ctx.pop("_pending_field", None)
            ctx.pop("_pending_cv_generate", None)
            self._store_recent_context(user_id, ctx)
            # Reload profile so the CV draft picks up the new cities
            updated_profile = self._resolve_profile(user_id)
            return self._handle_cv_generate_from_profile(user_id, updated_profile)

        return None

    _JOB_SEARCH_OPTIONS = {
        "type": "options",
        "message": "Here is what I can help you with:",
        "options": [
            {"action": "find_jobs",          "label": "Find matching UAE jobs"},
            {"action": "apply",              "label": "Prepare a job application"},
            {"action": "interview_prep",     "label": "Prepare for an interview"},
            {"action": "update_profile",     "label": "Update my profile"},
            {"action": "track_applications", "label": "Track my applications"},
        ],
    }

    @staticmethod
    def _search_jsearch_meta(role: str) -> Any:
        """Query JSearch for live UAE jobs matching *role*, with cache + retry.

        Returns a ``jsearch_client.FetchResult`` so the caller can tell a genuine
        empty result apart from a rate-limited source. Never raises.
        """
        from src import jsearch_client

        result = jsearch_client.search(f"{role} UAE")
        logger.info(
            "jsearch_direct role=%r results=%d cache_hit=%s rate_limited=%s",
            role, len(result.items), result.cache_hit, result.rate_limited,
        )
        return result

    @staticmethod
    def _search_jsearch_direct(role: str) -> list[dict[str, Any]]:
        """Backward-compatible list wrapper around :meth:`_search_jsearch_meta`."""
        return RicoChatAPI._search_jsearch_meta(role).items

    def _target_role_search_response(
        self, user_id: str, role: str, profile: Any, from_saved_profile: bool = False
    ) -> dict[str, Any]:
        """Handle target role search with role intelligence integration."""
        try:
            normalized_role = normalize_role(role)
        except Exception as e:
            logger.warning("Role normalization failed", extra={"user_id": user_id, "role": role, "error": str(e)})
            normalized_role = role

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        if normalized_role and normalized_role.lower() not in {str(item).lower() for item in target_roles}:
            target_roles.append(normalized_role)
            profile = upsert_profile(user_id=user_id, updates={"target_roles": target_roles})

        search_role = normalized_role or role
        operation = self._begin_job_search_operation(user_id, search_role)
        operation_id = str(operation["operation_id"])

        # Primary path: live JSearch query for the exact requested role.
        # Falls back to the legacy scraper pipeline only when JSearch is unavailable.
        rate_limited = False
        import time as _time
        _search_start = _time.monotonic()
        try:
            fetch = self._search_jsearch_meta(search_role)
            all_matches = fetch.items
            rate_limited = fetch.rate_limited
            _search_elapsed = _time.monotonic() - _search_start
            logger.info(
                "job_search: role=%r results=%d rate_limited=%s elapsed=%.2fs op=%s",
                search_role, len(all_matches), rate_limited, _search_elapsed, operation_id,
            )
            if not all_matches:
                search_profile = (
                    _dc_replace(profile, target_roles=[search_role])
                    if is_dataclass(profile)
                    else profile
                )
                workflow_result = self.system.run_for_profile(search_profile)
                all_matches = workflow_result.get("matches", [])
        except Exception as exc:
            _search_elapsed = _time.monotonic() - _search_start
            logger.warning(
                "job_search_failed: role=%r elapsed=%.2fs op=%s err=%s",
                search_role, _search_elapsed, operation_id, type(exc).__name__,
            )
            mark_failed(user_id, operation_id, str(exc))
            raise

        # Filter out already-applied jobs
        try:
            from src.applications import is_applied_batch, get_job_id
            if all_matches:
                applied_map = is_applied_batch(all_matches, user_id=user_id)
                all_matches = [m for m in all_matches if not applied_map.get(get_job_id(m), False)]
        except Exception as e:
            logger.debug("Applied-job filter unavailable: %s", e)

        # Filter out UAE-nationals-only listings for non-national users.
        try:
            nationality = (
                self._profile_value(profile, "nationality") or
                self._profile_value(profile, "citizenship") or ""
            ).strip().lower()
            is_uae_national = nationality in ("uae", "emirati", "emirati national", "uae national")
            if not is_uae_national and all_matches:
                from src.eligibility_filter import filter_for_non_nationals
                all_matches = filter_for_non_nationals(all_matches)
        except Exception as e:
            logger.debug("Eligibility filter unavailable: %s", e)

        # Deduplicate by title+company fingerprint within this response.
        # JSearch deduplicates by job_id, but the same role at the same company
        # can appear under slightly different job_ids (different posting dates).
        seen_fps: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for m in all_matches:
            fp = (
                str(m.get("title") or "").lower().strip()
                + "|"
                + str(m.get("company") or "").lower().strip()
            )
            if fp and fp != "|" and fp not in seen_fps:
                seen_fps.add(fp)
                deduped.append(m)
        all_matches = deduped

        # Profile-fit ranking: score each result against the user's target roles,
        # skills, and deal-breakers. Zero-latency (pure keyword matching) so it
        # doesn't add round-trip time to the chat response.
        try:
            from src.llm_scorer import rank_by_profile_fit as _rbpf
            _profile_target_roles = self._as_list(
                self._profile_value(profile, "target_roles")
            )
            _profile_skills = self._as_list(
                self._profile_value(profile, "skills")
            )
            _profile_deal_breakers = self._as_list(
                self._profile_value(profile, "deal_breakers")
            )
            all_matches = _rbpf(
                all_matches,
                target_roles=[str(r) for r in _profile_target_roles if r],
                skills=[str(s) for s in _profile_skills if s],
                deal_breakers=[str(d) for d in _profile_deal_breakers if d],
            )
        except Exception:
            pass

        # Quality-sort: within same profile-fit tier, surface live/verified
        # sources before aggregators/dead links.
        _QUALITY_RANK: dict[str, int] = {
            "live_verified": 0,
            "needs_source_verification": 1,
            "google_intermediary": 2,
            "login_required": 3,
            "rate_limited": 4,
            "aggregator_untrusted": 5,
        }
        try:
            from src.services.source_quality import (
                classify_url as _cq, is_google_intermediary as _igi,
                is_low_quality_company as _lqc,
            )
            # Pre-compute learned preference sets once (avoid repeated DB calls per job)
            _pref_roles: list[str] = []
            _pref_locs: list[str] = []
            _avoided_cos: set[str] = set()
            try:
                from src.repositories.learning_repo import get_learning_repository as _glr
                _lr = _glr()
                _pref_roles = [r.lower() for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
                _pref_locs = [loc.lower() for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
                _avoided_cos = {
                    c.lower() for c, w in _lr.get_top_preferences(user_id, "company", limit=10) if w < 0
                }
            except Exception:
                pass

            def _quality_key(m: dict[str, Any]) -> int:
                url = str(
                    m.get("job_apply_link") or m.get("apply_link") or m.get("link") or ""
                )
                status = "google_intermediary" if _igi(url) else _cq(url)
                # Secondary sort: quality within profile-fit bands
                fit = m.get("profile_fit_score", 0)
                fit_band = max(0, 5 - fit // 20)  # 5 bands (0=best fit, 4=worst)
                # Company quality penalty: anonymous/low_quality jobs sort after legitimate ones
                company_penalty = 20 if _lqc(str(m.get("company") or "")) else 0
                # Preference bonus: jobs matching learned role/location float up
                title = (m.get("title") or "").lower()
                location = (m.get("location") or m.get("city") or "").lower()
                company_lower = (m.get("company") or "").lower()
                pref_bonus = 0
                if _pref_roles and any(r in title for r in _pref_roles):
                    pref_bonus -= 3
                if _pref_locs and any(loc in location for loc in _pref_locs):
                    pref_bonus -= 2
                if company_lower in _avoided_cos:
                    pref_bonus += 5
                return fit_band * 10 + _QUALITY_RANK.get(status, 1) + company_penalty + pref_bonus

            all_matches.sort(key=_quality_key)
        except Exception:
            pass

        top_matches = all_matches[:5]
        formatted = [self._format_match(m, profile) for m in top_matches]

        skills = self._as_list(self._profile_value(profile, "skills"))[:8]
        years = self._profile_value(profile, "years_experience")
        cities = self._as_list(self._profile_value(profile, "preferred_cities"))
        city_text = f" in {', '.join(map(str, cities[:2]))}" if cities else " in the UAE"
        basis = []
        if years:
            basis.append(f"~{years} years experience")
        if skills:
            basis.append("skills: " + ", ".join(map(str, skills[:6])))
        basis_text = " using your CV profile" + (f" ({'; '.join(basis)})" if basis else "")

        role_intelligence_data = self._enrich_with_role_intelligence(
            user_id, normalized_role, profile, skills, years, cities
        )

        message = self._build_role_search_message(
            normalized_role, city_text, basis_text, top_matches, role_intelligence_data,
            from_saved_profile=from_saved_profile,
        )

        response = {
            "type": "job_matches",
            "intent": "search_jobs",
            "message": message,
            "matches": formatted,
            "entities": {"job_title": normalized_role, "from_cv_profile": True},
            "operation_id": operation_id,
            "operation_status": "completed",
            "operation_type": "job_search",
            "result_count": len(formatted),
            "search_query": search_role,
            "broadened": len(all_matches) == 0,
            "rate_limited": rate_limited,
        }

        if rate_limited:
            response["rate_limit_notice"] = (
                "This source is temporarily rate-limited. "
                "Try the alternate link on each result, or search again shortly."
            )

        if role_intelligence_data:
            response["role_intelligence"] = role_intelligence_data

        self._append_chat(user_id, "assistant", response)
        mark_completed(user_id, operation_id, len(formatted))
        if formatted:
            self._store_search_matches_context(user_id, formatted, search_role=search_role)
        return response

    def _enrich_with_role_intelligence(
        self,
        user_id: str,
        normalized_role: str,
        profile: Any,
        skills: list[Any],
        years: Any,
        cities: list[Any],
    ) -> dict[str, Any] | None:
        """Enrich response with role intelligence data."""
        try:
            from src.rico_agent import RicoProfile

            rico_profile = RicoProfile(
                user_id=user_id,
                skills=skills or [],
                years_experience=years,
                preferred_cities=cities or [],
                industries=self._as_list(self._profile_value(profile, "industries")) or []
            )

            fit_score = score_profile_fit(rico_profile, normalized_role)

            adjacent_roles = []
            if fit_score.overall_score < 0.6:
                adjacent_roles = recommend_adjacent_roles(rico_profile, normalized_role, limit=3)

            if not adjacent_roles:
                return None

            return {
                "normalized_role": normalized_role,
                "fit_score": fit_score.overall_score,
                "adjacent_roles": [
                    {"role": r.canonical_role, "similarity": r.similarity_score, "reason": r.reason}
                    for r in adjacent_roles
                ]
            }
        except Exception as e:
            logger.warning("Role intelligence enrichment failed", extra={"user_id": user_id, "role": normalized_role, "error": str(e)})
            return None

    def _build_role_search_message(
        self,
        normalized_role: str,
        city_text: str,
        basis_text: str,
        top_matches: list[Any],
        role_intelligence_data: dict[str, Any] | None,
        from_saved_profile: bool = False,
    ) -> str:
        """Build message for role search response."""
        if from_saved_profile:
            prefix = f"Searching based on your saved target role: {normalized_role}. "
        else:
            prefix = ""
        if top_matches:
            def _has_url(m: Any) -> bool:
                return bool(
                    m.get("job_apply_link") or m.get("apply_link") or m.get("link")
                )
            link_count = sum(1 for m in top_matches if _has_url(m))
            lead_count = len(top_matches) - link_count
            total = len(top_matches)
            if link_count and lead_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {total} candidate match(es) from the job source pipeline "
                    f"({link_count} with provider links, {lead_count} need verification)."
                )
            elif link_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {link_count} match(es) with provider data available."
                )
            else:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {lead_count} candidate match(es) that need source verification."
                )
        else:
            base_message = f"Got it — I will target {normalized_role} roles{city_text}{basis_text}."

        if role_intelligence_data and role_intelligence_data.get("fit_score", 1.0) < 0.6:
            adjacent = role_intelligence_data.get("adjacent_roles", [])
            role_names = [r["role"] for r in adjacent[:3]]
            base_message += f" Your CV is also strong for {', '.join(role_names)} roles. I'll search those too if needed."
        elif not top_matches:
            base_message += " I couldn't retrieve live jobs right now. I can still suggest target searches based on your CV — or try again later."

        return prefix + base_message

    def process_message(
        self,
        user_id: str,
        message: str,
        operation_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        debug_id = _generate_debug_id()
        self._current_operation_id = operation_id
        try:
            result = self._process_message_inner(user_id, message, language=language)
            # Guarantee debug_id on every response
            if isinstance(result, dict):
                result.setdefault("debug_id", debug_id)
                message_text = str(result.get("message") or "").strip()
                if not message_text:
                    logger.error(
                        "rico_empty_message_response user=%s type=%s source=%s",
                        user_id,
                        result.get("type", "unknown"),
                        result.get("response_source", "unknown"),
                    )
                    error_response = build_error_response(
                        "Rico could not produce a usable reply for that request. Please rephrase your request or ask a more specific question.",
                        debug_id=debug_id,
                        user_id=user_id,
                    )
                    for key in (
                        "provider",
                        "model",
                        "response_source",
                        "provider_state",
                        "profile_context_present",
                        "jotform_form_id",
                        "fallback_model",
                        "openai_model",
                        "deepseek_model",
                        "error",
                        "error_detail",
                        "is_rate_limited",
                    ):
                        if key in result:
                            error_response[key] = result[key]
                    error_response.setdefault("error", "empty_message")
                    return error_response
                result.setdefault("success", True)
                # Update the canonical last-turn anchor so vague follow-ups
                # ("make sure", "list them", "that one") can resolve reliably.
                self._record_last_turn(user_id, message, result)
            return result
        except Exception as exc:
            if self._current_operation_id:
                mark_failed(user_id, self._current_operation_id, str(exc))
            return build_error_response(
                "Something went wrong processing your message.",
                debug_id=debug_id,
                log_exc=exc,
                user_id=user_id,
            )
        finally:
            self._current_operation_id = None

    def _answer_with_ai_fallback(
        self,
        user_id: str,
        message: str,
        profile: Any,
        *,
        save_user_message: bool,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Run the single conversational AI fallback path used by chat routing."""
        if save_user_message:
            self._append_chat(user_id, "user", message)
        user_context = self._build_openai_context(profile, user_id=user_id)
        blocked_questions = self._get_blocked_questions(profile)
        if isinstance(user_context, dict):
            user_context["blocked_questions"] = blocked_questions

        ai_response = self._get_openai_agent().respond(message, user_context=user_context, language=language)
        raw_ai_message = ai_response.get("message", "")
        filtered_ai_message = self._preserve_ai_message(raw_ai_message, blocked_questions)
        ai_response["message"] = filtered_ai_message

        if filtered_ai_message:
            self._append_chat(user_id, "assistant", filtered_ai_message)

        result = self._finalize(
            ai_response,
            self._source_for_openai_response(ai_response),
            profile=profile,
        )
        result.setdefault("success", True)
        return result

    def answer_conversationally(self, user_id: str, message: str, profile: Any, language: str | None = None) -> dict[str, Any]:
        """Route directly to the existing conversational AI fallback path."""
        debug_id = _generate_debug_id()
        try:
            result = self._answer_with_ai_fallback(
                user_id=user_id,
                message=message,
                profile=profile,
                save_user_message=True,
                language=language,
            )
            if isinstance(result, dict):
                result.setdefault("debug_id", debug_id)
                message_text = str(result.get("message") or "").strip()
                if not message_text:
                    logger.error(
                        "rico_empty_message_response user=%s type=%s source=%s",
                        user_id,
                        result.get("type", "unknown"),
                        result.get("response_source", "unknown"),
                    )
                    error_response = build_error_response(
                        "Rico could not produce a usable reply for that request. Please rephrase your request or ask a more specific question.",
                        debug_id=debug_id,
                        user_id=user_id,
                    )
                    for key in (
                        "provider",
                        "model",
                        "response_source",
                        "provider_state",
                        "profile_context_present",
                        "jotform_form_id",
                        "fallback_model",
                        "openai_model",
                        "deepseek_model",
                        "error",
                        "error_detail",
                        "is_rate_limited",
                    ):
                        if key in result:
                            error_response[key] = result[key]
                    error_response.setdefault("error", "empty_message")
                    return error_response
                result.setdefault("success", True)
            return result
        except Exception as exc:
            return build_error_response(
                "Something went wrong processing your message.",
                debug_id=debug_id,
                log_exc=exc,
                user_id=user_id,
            )

    def _process_message_inner(self, user_id: str, message: str, language: str | None = None) -> dict[str, Any]:
        self._append_chat(user_id, "user", message)
        completed = is_onboarding_complete(user_id)

        if completed:
            return self._handle_active_user(user_id, message)

        if self._looks_like_cv_upload(message):
            # If the user has announced they have a CV but hasn't attached a file,
            # direct them to the Upload CV button instead of faking a filename.
            if self._looks_like_cv_intent_no_file(message):
                arabic = self._is_arabic_text(message)
                cv_guidance = (
                    "ممتاز! لرفع سيرتك الذاتية استخدم زر **رفع السيرة الذاتية** في الصفحة. "
                    "بعد الرفع سأقرأ السيرة تلقائياً وأملأ ملفك المهني."
                    if arabic else
                    "Use the **Upload CV** button on this page to upload your CV. "
                    "Once uploaded, I will read it automatically and pre-fill your career profile "
                    "with your experience, skills, and target roles — no manual questionnaire needed."
                )
                self._append_chat(user_id, "assistant", cv_guidance)
                return self._finalize(
                    {
                        "type": "cv_upload_guidance",
                        "message": cv_guidance,
                        "next_action": "upload_cv",
                        "options": [
                            {
                                "action": "upload_cv",
                                "label": "رفع السيرة الذاتية" if arabic else "Upload CV",
                                "message": "upload cv",
                            },
                        ],
                    },
                    self.SOURCE_KEYWORD,
                    profile=None,
                )
            mark_onboarding_complete(user_id)
            return self._finalize(
                self._cv_first_profile_response(user_id, message),
                self.SOURCE_KEYWORD,
                profile=None,
            )

        profile = get_profile(user_id)
        if profile is None:
            if getattr(self, "_persist", True):
                upsert_profile(user_id=user_id, updates={})
                set_onboarding_status(user_id, ONBOARDING_IN_PROGRESS)
            import re as _re
            _is_ar = language == "ar" or bool(_re.search(r'[؀-ۿ]', message))
            onboarding_msg = (
                "أهلاً بك في ريكو. أرفع سيرتك الذاتية أو أخبرني بالمسمى الوظيفي الذي تستهدفه "
                "والمدينة التي تفضل العمل فيها بالإمارات وتوقعات راتبك. "
                "عند رفع السيرة الذاتية سأملأ الملف الشخصي تلقائيًا وأسألك فقط عن أي معلومات ناقصة."
                if _is_ar else
                "Welcome to Rico AI. Upload your CV or tell me your target role, UAE city "
                "preferences, and salary expectations. If you upload a CV, I will pre-fill "
                "the profile and only ask for anything missing or unclear."
            )
            response = {"type": "onboarding", "message": onboarding_msg}
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=None)

        mark_onboarding_complete(user_id)
        return self._handle_active_user(user_id, message)

    def _resolve_profile(self, user_id: str):
        """Load and normalise profile into a ProfileContext.

        This is the migration point for #96 — eventually all callers
        will consume ProfileContext directly instead of raw dict/objects.
        """
        raw = get_profile(user_id)
        return resolve_profile_context(user_id, raw)

    def _handle_active_user(self, user_id: str, message: str) -> dict[str, Any]:
        """Intent-first active-user handler.

        Pipeline:
          1. Deterministic follow-up phrases (before role classification)
          2. Classify intent (never defaults to job search)
          3. Route by intent
          4. For role-like text, use 3-tier role classifier
          5. Unknown / nonsense → clarification, not search
        """
        try:
            return self._handle_active_user_inner(user_id, message)
        except Exception:
            logger.exception("rico_routing_error user=%s msg=%r", user_id, message)
            fallback = {
                "type": "clarification",
                "message": (
                    "I'm here to help with your UAE job search. "
                    "You can search for a role, upload your CV, ask about your applications, "
                    "or say 'help' for all options."
                ),
            }
            self._append_chat(user_id, "assistant", fallback["message"])
            return self._finalize(fallback, self.SOURCE_KEYWORD, profile=None)

    def _handle_active_user_inner(self, user_id: str, message: str) -> dict[str, Any]:
        """Inner routing — called by _handle_active_user which provides the safe fallback."""
        profile = self._resolve_profile(user_id)
        has_cv = profile.has_cv
        text = self._normalize_followup_phrase(message)

        # ── Pasted CV text detection ──────────────────────────────────────────
        # A user may paste raw CV text instead of uploading a file.  Detect it
        # early so the long blob never reaches the AI provider (avoiding both
        # context-window errors and generic crash responses).
        if self._looks_like_pasted_cv_text(message):
            return self._finalize(
                self._handle_pasted_cv_text(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pending field resolver (must run first) ───────────────────────────
        # When Rico has just asked the user for a specific profile field (e.g.
        # "What's your Telegram username?"), the raw value the user sends next
        # (like "@Robin_amg") won't match any intent. Intercept it here so the
        # field is saved and a correct confirmation is returned without falling
        # through to the unknown/fallback handler.
        pending_field_result = self._resolve_pending_field(user_id, message, profile)
        if pending_field_result is not None:
            return self._finalize(pending_field_result, self.SOURCE_KEYWORD, profile=profile)

        # ── CV builder flow-state follow-up ──────────────────────────────────
        # When Rico has just returned a CV draft (last_flow_state == "cv_builder"),
        # route improvement follow-ups like "please improve it" or Arabic
        # "نعم حسنها بشكل محترف" directly to the deterministic CV handler instead
        # of AI fallback, which may invent achievements, percentages, or placeholders.
        _flow_ctx = self._get_recent_context(user_id)
        if _flow_ctx.get("last_flow_state") == "cv_builder" and _CV_IMPROVE_FOLLOWUP_RE.search(message):
            return self._finalize(
                self._handle_cv_generate_from_profile(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Proactive Telegram declaration: "my telegram is @handle" ─────────
        # When the user volunteers their Telegram handle with the keyword "telegram"
        # in the same message, save it immediately without needing a pending slot.
        _tg_match = TELEGRAM_MENTION_RE.search(message)
        if _tg_match and "telegram" in message.lower():
            _tg_handle = _tg_match.group(1) or _tg_match.group(2)
            if _tg_handle and TELEGRAM_HANDLE_RE.match(_tg_handle):
                upsert_profile(user_id=user_id, updates={"telegram_username": _tg_handle})
                _tg_reply = (
                    f"Got it — I've saved your Telegram username as **{_tg_handle}**. "
                    "You'll receive job alerts and updates there."
                )
                self._append_chat(user_id, "assistant", _tg_reply)
                return self._finalize(
                    {
                        "type": "preferences_updated",
                        "message": _tg_reply,
                        "updated": {"telegram_username": _tg_handle},
                    },
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # Arabic "I already applied" reports are lifecycle updates, not send/draft
        # requests and not job searches. Catch before the channel follow-up guard,
        # whose broad Arabic "قدم" send verb can otherwise intercept them.
        if self._is_arabic_text(message) and any(
            term in message for term in ("قدم", "تقديم", "التقديم", "ارسل", "أرسل")
        ):
            status_intent = classify_intent(message, has_cv_profile=has_cv)
            if _map_intent_to_legacy(status_intent.intent) == "application_status_update":
                logger.info(
                    "rico_intent user=%s intent=%s legacy_intent=%s confidence=%.2f source=%s",
                    user_id,
                    status_intent.intent,
                    status_intent.legacy_intent,
                    status_intent.confidence,
                    status_intent.source,
                )
                return self._finalize(
                    self._handle_application_status_update(user_id, message, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # ── Application draft/send channel clarification ─────────────────────
        # Follow-ups like "go ahead", "send it", or Arabic "صيغ رسالة ... وارسلها"
        # must preserve the current job context without claiming unsupported
        # LinkedIn/job-portal submission or re-showing the same action menu.
        application_channel_result = self._handle_application_channel_followup(user_id, message, profile)
        if application_channel_result is not None:
            return self._finalize(application_channel_result, self.SOURCE_KEYWORD, profile=profile)

        # ── CV upload announcement: "i have a cv" / "ill upload it" ─────────────
        # When a user announces a CV without attaching a file, they need to be
        # directed to the Upload CV button. Saying "this chat doesn't support
        # file uploads" is wrong — the platform has a dedicated upload page.
        # This guard runs before any AI call so the user always gets a clear,
        # deterministic direction instead of a questionnaire or false refusal.
        if self._looks_like_cv_intent_no_file(message):
            arabic = self._is_arabic_text(message)
            if arabic:
                cv_guidance = (
                    "ممتاز! لرفع سيرتك الذاتية استخدم زر **رفع السيرة الذاتية** في الصفحة. "
                    "بعد الرفع سأقرأ السيرة تلقائياً وأملأ ملفك المهني."
                )
            else:
                cv_guidance = (
                    "Use the **Upload CV** button on this page to upload your CV. "
                    "Once uploaded, I will read it automatically and pre-fill your career profile "
                    "with your experience, skills, and target roles — no manual questionnaire needed."
                )
            self._append_chat(user_id, "assistant", cv_guidance)
            return self._finalize(
                {
                    "type": "cv_upload_guidance",
                    "message": cv_guidance,
                    "next_action": "upload_cv",
                    "options": [
                        {
                            "action": "upload_cv",
                            "label": "Upload CV" if not arabic else "رفع السيرة الذاتية",
                            "message": "upload cv",
                        },
                    ],
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Explicit "show my applications" guard ────────────────────────────────
        # "show my applications", "my applications", "اعرض طلباتي", "طلباتي", etc.
        # are direct intents — route to application_tracking without requiring a
        # prior lifecycle context (which the list-followup block would need).
        if RicoChatAPI._SHOW_MY_APPLICATIONS_RE.match(text):
            return self._finalize(
                self._handle_application_tracking(user_id, intent="application_tracking"),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Direct reminder commands ─────────────────────────────────────────────
        # "Set a follow-up reminder for Penspen", "Remind me to follow up", etc.
        # These come from UI suggestion buttons and must be caught before role
        # classification interprets them as job-title queries.
        if RicoChatAPI._SET_REMINDER_RE.search(message):
            # Extract company/job name from "for <name>" or "with <name>" suffix.
            _company_match = re.search(r"\b(?:for|with)\s+(.+)$", message, re.IGNORECASE)
            _company = _company_match.group(1).strip() if _company_match else None
            if _company:
                reply = (
                    f"Reminder set for **{_company}**. "
                    "I'll nudge you to follow up in 7 days if you haven't heard back."
                )
            else:
                reply = (
                    "Reminder set. I'll nudge you to follow up in 7 days "
                    "if you haven't heard back from your latest application."
                )
            self._append_chat(user_id, "assistant", reply)
            return self._finalize(
                {"type": "reminder_set", "message": reply},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Lifecycle list follow-up: "list them" / "show them" / "اذكرهم" ───────
        # Must run before the affirmative resolver so short list-commands don't
        # fall through to the AI and crash on ambiguous short input.
        if self._is_list_followup(message):
            last_query = self._resolve_lifecycle_query_for_followup(user_id)
            if last_query:
                return self._finalize(
                    self._handle_lifecycle_query(user_id, last_query),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            # "list them" after a job search — replay the cached recent_search_matches.
            ctx = self._get_recent_context(user_id)
            cached_matches = ctx.get("recent_search_matches") or []
            if cached_matches:
                lines = []
                for i, m in enumerate(cached_matches, 1):
                    title = m.get("title", "")
                    company = m.get("company", "")
                    loc = m.get("location", "")
                    link = m.get("apply_url", "") or m.get("source_url", "")
                    loc_part = f" · {loc}" if loc else ""
                    link_part = f" — [Apply]({link})" if link else ""
                    lines.append(f"{i}. **{title}** at **{company}**{loc_part}{link_part}")
                role_hint = ctx.get("recent_search_role") or ctx.get("recent_role") or ctx.get("recent_job") or "your last search"
                msg = f"Here are the results from {role_hint}:\n\n" + "\n".join(lines)
                return self._finalize(
                    {"type": "job_matches", "message": msg, "jobs": cached_matches},
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            # Nothing to list yet — give a clear prompt instead of falling to AI.
            return self._finalize(
                {
                    "type": "clarification",
                    "message": (
                        "I don't have a recent search or list to show you yet. "
                        "Try: 'find jobs for Environmental Compliance Officer in Dubai' "
                        "or 'show my saved jobs'."
                    ),
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Verify / "make sure" follow-up: re-confirm the last real turn ───────
        # Without this, "make sure please" after an applied-jobs reply gets
        # classified as a bare job role. Anchor it to the last_turn instead.
        if self._is_verify_followup(message):
            verified = self._resolve_verify_followup(user_id, profile)
            if verified is not None:
                return self._finalize(verified, self.SOURCE_KEYWORD, profile=profile)
            # Memory miss (e.g. multi-worker Render) — acknowledge without crashing.
            return self._finalize(
                {
                    "type": "clarification",
                    "message": (
                        "I'm not sure which result you'd like me to double-check. "
                        "Could you tell me what you'd like me to verify?"
                    ),
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pending-intent resolver: yes/no after Rico's question ──────────────
        # Must run before generic routing so "نعم" / "كمل" / "keep going" resolves
        # the last offered action instead of falling through to role classification.
        if self._is_affirmative(message) or self._is_continuation_intent(message):
            pending = self._resolve_pending_intent(user_id, message, profile)
            if pending is not None:
                return self._finalize(pending, self.SOURCE_KEYWORD, profile=profile)
            # Continuation with no specific pending offer: if CV exists, proceed with
            # the best known role; otherwise ask for one.
            if self._is_continuation_intent(message):
                return self._finalize(
                    self._handle_post_cv_continuation(user_id, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
        if self._is_negative(message):
            # User declined the offered action — acknowledge and let them continue
            return self._finalize(
                {"type": "clarification", "message": "حسناً، أخبرني بما تريد فعله." if any(ord(c) > 127 for c in message) else "Got it. What would you like to do instead?"},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Acknowledgement early check (must be before next-step followup fast path) ──
        # Phrases like "ok", "great", "thanks" are also in _FOLLOWUP_NEXT_STEP_PHRASES
        # and _AFFIRMATIVE_PHRASES. If no pending intent was resolved above, treat
        # them as acknowledgements and return a short warm reply immediately.
        _msg_lower = message.strip().lower()
        if _msg_lower in _ACKNOWLEDGEMENT_REPLIES:
            ack_text = _acknowledgement_reply(message)
            response = {"type": "acknowledgement", "message": ack_text}
            self._append_chat(user_id, "assistant", ack_text)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # ── Deterministic follow-up phrases (must be before role classification) ──
        if text in self._FOLLOWUP_KEEP_ALL_PHRASES:
            return self._finalize(
                self._handle_keep_all_target_roles(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        if text in self._FOLLOWUP_BOTH_ACTION_PHRASES:
            return self._finalize(
                self._handle_both_requested_actions(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        logger.info(
            "rico_followup_check user=%s has_cv=%s msg=%r followup=%s",
            user_id, has_cv, message, self._looks_like_next_step_followup(message),
        )

        # Fast path: short follow-up after role confirmation → instant options
        if has_cv and (
            self._looks_like_next_step_followup(message)
            or self._is_arabic_what_now(message)
        ):
            logger.info("rico_followup_hit user=%s msg=%r", user_id, message)
            return self._finalize(
                self._handle_next_step_options(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Fast path: user selected a suggested role → deterministic confirmation
        if has_cv and not self._is_live_job_search_request(message):
            if self._looks_like_selected_role(message, profile):
                return self._finalize(
                    self._handle_role_confirmation(
                        user_id=user_id,
                        role=self._extract_selected_role(message, profile),
                        profile=profile,
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # Generic job request with CV and no established target roles → suggest CV-based roles
        # When target roles are already set, skip to intent classification so run_for_profile fires
        _profile_target_roles = self._effective_target_roles(
            self._as_list(self._profile_value(profile, "target_roles"))
        )
        if (
            has_cv
            and not _profile_target_roles
            and not self._is_live_job_search_request(message)
            and self._looks_like_generic_job_request(message)
        ):
            return self._finalize(
                self._handle_profile_role_suggestions(profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Step 1: Unified intent classification ────────────────────────────
        if has_cv and self._looks_like_career_execution_request(message):
            return self._finalize(
                self._handle_career_execution(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        intent_result = classify_intent(message, has_cv_profile=has_cv)
        intent = intent_result.intent

        # Map Intent v2 dotted notation to legacy intent names for backward compatibility
        legacy_intent = _map_intent_to_legacy(intent)

        logger.info(
            "rico_intent user=%s intent=%s legacy_intent=%s confidence=%.2f source=%s",
            user_id, intent, legacy_intent, intent_result.confidence, intent_result.source,
        )

        # ── Step 2: Route by intent ──────────────────────────────────────────

        # Help / menu
        if legacy_intent == "help":
            self._append_chat(user_id, "assistant", self._JOB_SEARCH_OPTIONS)
            return self._finalize(self._JOB_SEARCH_OPTIONS, self.SOURCE_KEYWORD, profile=profile)

        # Acknowledgement — short warm reply; never restarts or greets
        if legacy_intent == "acknowledgement":
            ack_text = _acknowledgement_reply(message)
            response = {"type": "acknowledgement", "message": ack_text}
            self._append_chat(user_id, "assistant", ack_text)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Positive job feedback — record learning signal and acknowledge
        if legacy_intent == "job_feedback_positive":
            return self._finalize(
                self._handle_job_feedback_positive(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Negative job feedback — record learning signal and acknowledge
        if legacy_intent == "job_feedback_negative":
            return self._finalize(
                self._handle_job_feedback_negative(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Smalltalk (greetings: hi/hello/hey/bye)
        # If the user is mid-conversation, return a brief continuation instead of
        # the cold-start greeting — avoids the "Hi! I am Rico…" restart after a
        # profile/details response.
        if legacy_intent == "smalltalk":
            recent = self._get_recent_messages(user_id, limit=4)
            has_active_conversation = len(recent) >= 2
            if has_active_conversation:
                followup = "What would you like to do next? I can search jobs, review applications, or answer questions about your profile."
                response = {"type": "clarification", "message": followup}
            else:
                followup = "Hi! I am Rico, your job search assistant. Tell me a role to search, upload your CV, or say 'help' for options."
                response = {"type": "clarification", "message": followup}
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Subscription / pricing
        if legacy_intent == "subscription.show_plans":
            _AMBIGUOUS_SUBSCRIBE_PHRASES = frozenset([
                "how can i subscribe", "how do i subscribe", "how to subscribe",
                "i want to subscribe", "i want to upgrade",
            ])
            if message.strip().lower() in _AMBIGUOUS_SUBSCRIBE_PHRASES:
                clarify_response = {
                    "type": "subscription.clarify",
                    "message": "What would you like to subscribe to?",
                    "options": [
                        {"action": "show_plans", "label": "Rico Pro / Premium plans", "message": "Show me Rico subscription plans and pricing"},
                        {"action": "job_alerts", "label": "Job alert notifications", "message": "How do job alert notifications work?"},
                    ],
                }
                self._append_chat(user_id, "assistant", clarify_response["message"])
                return self._finalize(clarify_response, self.SOURCE_KEYWORD, profile=profile)
            sub_response = self._handle_subscription_plans(user_id, profile)
            self._append_chat(user_id, "assistant", sub_response.get("message", ""))
            return self._finalize(sub_response, self.SOURCE_KEYWORD, profile=profile)

        # Delegated decision — user asks Rico to choose
        if legacy_intent == "delegated_decision":
            return self._finalize(
                self._handle_delegated_decision(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Onboarding skip
        if legacy_intent == "onboarding_answer":
            response = {
                "type": "profile_skip",
                "message": (
                    "Skipped. I will leave that field blank and continue without forcing it. "
                    "You can update it later."
                ),
                "field_status": "skipped",
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # CV upload / parse — but if CV is already parsed, don't restart wizard
        if legacy_intent == "cv_upload_or_parse":
            # Guard: if the message is a question about using someone else's CV
            # (no actual file attached), route to AI so it can answer naturally
            # instead of mistakenly treating it as a CV upload action.
            _lower_msg = message.lower()
            _is_cv_question = (
                not CV_FILE_RE.search(message)
                and any(kw in _lower_msg for kw in (
                    "friend", "someone else", "can i use", "use his", "use her",
                    "use their", "use my friend", "his cv", "her cv", "their cv",
                    "account for", "needs his own", "needs her own",
                ))
            )
            if _is_cv_question:
                friend_cv_msg = (
                    "You can paste or share your friend's CV text in this chat and I can analyse it "
                    "for them right now — no account needed for a one-off review.\n\n"
                    "However, for saved profile, job tracking, personalised alerts, and application "
                    "history, your friend needs their own Rico account at ricohunt.com.\n\n"
                    "Important: if you upload a CV here it will overwrite *your* profile, so only do "
                    "that if you intend to update your own details."
                )
                response = {"type": "account_delegation", "message": friend_cv_msg}
                self._append_chat(user_id, "assistant", friend_cv_msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            cv_status = self._profile_value(profile, "cv_status")
            if cv_status == "parsed" or self._profile_value(profile, "manual_profile_wizard_disabled"):
                # If the user is actually asking to find jobs, search using their profile
                # rather than telling them their CV is already set up.
                _is_job_request = (
                    self._is_live_job_search_request(message)
                    or self._looks_like_generic_job_request(message)
                    or any(kw in message.lower() for kw in (
                        "find", "search", "jobs", "roles", "match my cv",
                        "based on my cv", "using my cv", "suit me",
                    ))
                )
                if _is_job_request:
                    _target_roles = self._effective_target_roles(
                        self._as_list(self._profile_value(profile, "target_roles"))
                    )
                    if _target_roles:
                        return self._finalize(
                            self._target_role_search_response(
                                user_id, _target_roles[0], profile, from_saved_profile=True
                            ),
                            self.SOURCE_KEYWORD,
                            profile=profile,
                        )
                    return self._finalize(
                        self._handle_profile_role_suggestions(profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                response = {
                    "type": "profile_summary",
                    "message": (
                        "Your CV is already parsed and your profile is set up. "
                        "You can say 'show my profile' to review it, or tell me a role to search."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            return self._finalize(
                self._cv_first_profile_response(user_id, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # CV generation — user wants a new CV draft from their existing parsed profile
        if legacy_intent == "cv_generate":
            return self._finalize(
                self._handle_cv_generate_from_profile(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # CV creation — user asks to create a CV (no existing CV)
        if legacy_intent == "cv_create":
            # If CV is already parsed, treat this as a generate request instead
            # of asking the user to start from scratch.
            if self._has_cv_profile(profile):
                return self._finalize(
                    self._handle_cv_generate_from_profile(user_id, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            return self._finalize(
                self._handle_cv_creation(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Learning profile summary — what Rico has inferred from user behavior
        if legacy_intent == "learning_profile_summary":
            return self._finalize(
                self._handle_learning_profile_summary(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Preference correction — user wants to forget / veto a learned preference
        if legacy_intent == "preference_correction":
            return self._finalize(
                self._handle_preference_correction(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Application insights — success rates, response patterns, follow-up intel
        if legacy_intent == "application_insights":
            return self._finalize(
                self._handle_application_insights(user_id),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Profile summary
        if legacy_intent == "profile_summary":
            from src.agent.context.resolver import resolve_profile_context
            try:
                ctx = resolve_profile_context(user_id)
                prof_dict = profile_to_dict(ctx.profile) if ctx.profile else {}
            except Exception:
                prof_dict = profile_to_dict(profile) if profile else {}
            response = {
                "type": "profile_summary",
                "message": "Here is your current profile.",
                "profile": prof_dict,
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Profile role suggestions - deterministic fast path based on CV skills/certifications
        if legacy_intent == "profile_role_suggestions":
            return self._finalize(
                self._handle_profile_role_suggestions(profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Generic follow-up confirmations should never fall into role classification.
        if legacy_intent == "follow_up_confirmation":
            # Priority 1: resume a pending apply confirmation (user said "yes"/"1"/"go ahead"
            # after Rico asked "Did you apply? Confirm you submitted.")
            try:
                _ctx = self._get_recent_context(user_id)
                _pending = _ctx.get("_pending_confirm_apply")
                if _pending and _pending.get("title") and _pending.get("company"):
                    from src.repositories.applications_repo import create_manual as _create_manual_app
                    _title = _pending["title"]
                    _company = _pending["company"]
                    # Clear the flag — user has now confirmed
                    _ctx.pop("_pending_confirm_apply", None)
                    self._store_recent_context(user_id, _ctx)
                    try:
                        _saved = _create_manual_app(
                            title=_title,
                            company=_company,
                            status="applied",
                            user_id=user_id,
                        )
                        if not _saved:
                            raise RuntimeError("application create_manual returned false")
                        _msg = (
                            f"Got it — **{_title}** at **{_company}** is marked as applied. "
                            "I'll track it as your latest application. "
                            "You can follow it from Applications (/applications)."
                        )
                        _response_type = "mark_applied"
                        _job_status = "applied"
                        _next_action = "follow_up_after_7_days"
                        self._store_recent_context(
                            user_id,
                            self._build_recent_application_context(
                                title=_title,
                                company=_company,
                                status="applied",
                                action="mark_applied",
                            ),
                        )
                    except Exception:
                        _msg = (
                            f"I understand you submitted **{_title}** at **{_company}**, "
                            "but I couldn't save it right now. Please try again shortly."
                        )
                        _response_type = "application_status_update_failed"
                        _job_status = None
                        _next_action = "retry_application_status_update"
                    self._append_chat(user_id, "assistant", _msg)
                    return self._finalize(
                        {
                            "type": _response_type,
                            "intent": "mark_applied",
                            "message": _msg,
                            "job_title": _title,
                            "job_company": _company,
                            "job_status": _job_status,
                            "target_route": "/applications",
                            "next_action": _next_action,
                        },
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass  # fall through to generic confirmation handling

            # Priority 2: resume a pending role search confirmation
            # (user replied YES after known_but_off_profile clarification)
            try:
                _ctx2 = self._get_recent_context(user_id)
                _pending_role = _ctx2.get("_pending_role_confirmation")
                if _pending_role and _pending_role.get("role"):
                    _role = _pending_role["role"]
                    _ctx2.pop("_pending_role_confirmation", None)
                    self._store_recent_context(user_id, _ctx2)
                    return self._finalize(
                        self._target_role_search_response(user_id, _role, profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

            if text == "all":
                return self._finalize(
                    self._handle_keep_all_target_roles(user_id, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            if has_cv:
                return self._finalize(
                    self._handle_next_step_options(user_id, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            response = {
                "type": "clarification",
                "message": (
                    "I am ready to continue. Upload your CV or tell me your target role "
                    "so I know what action to take next."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Application tracking — route to applications repo, NOT job search
        if legacy_intent == "application_tracking":
            return self._finalize(
                self._handle_application_tracking(user_id, intent=intent),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        if legacy_intent == "application_status_update":
            return self._finalize(
                self._handle_application_status_update(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Lifecycle funnel queries — chat-side memory (user_job_context)
        if legacy_intent in (
            "lifecycle_show_saved",
            "lifecycle_show_applied",
            "lifecycle_show_opened_not_applied",
        ):
            return self._finalize(
                self._handle_lifecycle_query(user_id, legacy_intent),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Profile-match job search (use CV/profile, not a named role)
        if legacy_intent == "job_search_profile_match":
            if not has_cv:
                response = {
                    "type": "clarification",
                    "message": (
                        "I don't have enough profile data yet to find matching jobs. "
                        "Upload your CV or tell me your target role, skills, and preferred city."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            # Use profile target roles for search
            target_roles = self._effective_target_roles(
                self._as_list(self._profile_value(profile, "target_roles"))
            )
            logger.info(
                "rico_profile_match_search user=%s target_roles=%s has_cv=%s",
                user_id, target_roles, has_cv,
            )
            role = target_roles[0] if target_roles else "your profile"
            return self._finalize(
                self._target_role_search_response(
                    user_id, role, profile, from_saved_profile=bool(target_roles)
                ),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Profile update — route BEFORE role-change fallback
        if legacy_intent == "profile_update":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            prefs = routed.tool_args.get("preferences", {})
            if prefs:
                upsert_profile(user_id=user_id, updates=prefs)
            response = {
                "type": "preferences_updated",
                "message": "Got it. I have updated your preferences and will apply them to future searches.",
                "updated": prefs,
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, routed.source, profile=profile)

        # Role change — extract role and classify
        if legacy_intent == "role_change" and intent_result.extracted_role:
            return self._finalize(
                self._classified_role_search(user_id, intent_result.extracted_role, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Explicit job search (regex-matched "find ... jobs" etc.)
        if legacy_intent == "job_search_explicit":
            # If the message names an explicit role ("find jobs for Environmental
            # Compliance Officer"), honour it and bypass profile target_roles fallback.
            if intent_result.extracted_role:
                return self._finalize(
                    self._classified_role_search(user_id, intent_result.extracted_role, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

            # No explicit role in this message — check recent conversation context
            # before falling back to profile target_roles.  This preserves continuity
            # when users switch languages mid-conversation (e.g. searched "software jobs"
            # in English then sent "ابحث لي وظائف في أبوظبي" in Arabic).
            try:
                _ctx = self._get_recent_context(user_id)
                _prior_role = (
                    _ctx.get("recent_search_role")
                    or _ctx.get("recent_role")
                    or _ctx.get("recent_job")
                )
                if _prior_role:
                    return self._finalize(
                        self._classified_role_search(user_id, _prior_role, profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

            # Fall through to legacy router for entity extraction
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)

            # Check if profile has target role before running job search
            target_roles = self._effective_target_roles(
                self._as_list(self._profile_value(profile, "target_roles"))
            )
            if not target_roles:
                if has_cv:
                    # CV present but no confirmed target role → suggest roles from skills
                    return self._finalize(
                        self._handle_profile_role_suggestions(profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                _is_ar = self._is_arabic_text(message)
                _incomplete_msg = (
                    "لإجراء البحث أحتاج إلى معرفة المسمى الوظيفي المستهدف أولاً.\n"
                    "أخبرني:\n"
                    "• المسمى الوظيفي (مثل: مهندس برمجيات، محاسب)\n"
                    "• المدينة المفضلة (مثل: دبي، أبوظبي)\n"
                    "• توقعات الراتب (اختياري)"
                    if _is_ar else
                    "I can search jobs using your profile. Please confirm:\n"
                    "• Target role (e.g., HSE Manager, ESG Specialist)\n"
                    "• Preferred city (e.g., Dubai, Abu Dhabi)\n"
                    "• Expected salary (optional)\n\n"
                    "I cannot search for jobs until at least your target role is known."
                )
                response = {
                    "type": "profile_incomplete",
                    "intent": "search_jobs",
                    "message": _incomplete_msg,
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, routed.source, profile=profile)

            # Removed fast-path override to prevent intent interception
            # Previously: generic job searches without job_title were intercepted by profile suggestions
            # Now: all explicit job searches execute through the normal workflow
            operation = self._begin_job_search_operation(user_id, str(target_roles[0]))
            operation_id = str(operation["operation_id"])
            try:
                workflow_result = self.system.run_for_profile(profile)
            except Exception as exc:
                mark_failed(user_id, operation_id, str(exc))
                raise

            # Handle blocked status from job search
            if workflow_result.get("status") == "blocked":
                mark_failed(
                    user_id,
                    operation_id,
                    workflow_result.get("message", "Job search was blocked by incomplete profile."),
                )
                response = {
                    "type": "profile_incomplete",
                    "intent": "search_jobs",
                    "message": workflow_result.get("message", "Please provide at least one target role before searching for jobs."),
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, routed.source, profile=profile)

            all_explicit = workflow_result.get("matches", [])
            try:
                from src.applications import is_applied_batch, get_job_id
                if all_explicit:
                    app_map = is_applied_batch(all_explicit, user_id=user_id)
                    all_explicit = [m for m in all_explicit if not app_map.get(get_job_id(m), False)]
            except Exception:
                pass
            top_matches = self._sort_by_company_quality(
                self._rerank_by_learned_preferences(all_explicit, user_id)
            )[:5]
            formatted = [self._format_match(m, profile) for m in top_matches]
            if top_matches:
                job_msg = "I found {} strong UAE job matches for you.".format(len(top_matches))
                response = {
                    "type": "job_matches",
                    "intent": "search_jobs",
                    "message": job_msg,
                    "matches": formatted,
                    "entities": routed.entities,
                    "operation_id": operation_id,
                    "operation_status": "completed",
                    "operation_type": "job_search",
                    "result_count": len(formatted),
                }
                self._append_chat(user_id, "assistant", response)
                mark_completed(user_id, operation_id, len(formatted))
                if formatted:
                    self._store_search_matches_context(user_id, formatted)
                return self._finalize(response, routed.source, profile=profile)
            else:
                mark_completed(user_id, operation_id, 0)
                if has_cv:
                    response = self._handle_no_results_recovery(user_id, profile, target_roles)
                    response.update({
                        "operation_id": operation_id,
                        "operation_status": "completed",
                        "operation_type": "job_search",
                        "result_count": 0,
                    })
                    return self._finalize(
                        response,
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                response = {
                    "type": "job_matches",
                    "intent": "search_jobs",
                    "message": (
                        "No strong UAE job matches found right now. "
                        "Try specifying your target role — for example: "
                        "'find HSE Manager jobs in Dubai'."
                    ),
                    "matches": [],
                    "entities": routed.entities,
                    "operation_id": operation_id,
                    "operation_status": "completed",
                    "operation_type": "job_search",
                    "result_count": 0,
                }
                self._append_chat(user_id, "assistant", response)
                return self._finalize(response, routed.source, profile=profile)

        # Prepare application — from job card "Prepare application — {title} at {company}"
        if legacy_intent == "prepare_application":
            # 1. Resolve job from intent extraction or recent context.
            raw_title = (getattr(intent_result, "extracted_title", None) or "").strip()
            raw_company = (getattr(intent_result, "extracted_company", None) or "").strip()
            # Strip the old fallback sentinel values the handler used before.
            if raw_title in ("the role",):
                raw_title = ""
            if raw_company in ("the company",):
                raw_company = ""

            title, company, _ctx_row = raw_title, raw_company, None
            if not title or not company:
                try:
                    from src.repositories.user_job_context_repo import (
                        get_recently_discussed as _grd_pa,
                        get_recently_interacted as _gri_pa,
                    )
                    _recent_pa = _grd_pa(user_id, limit=1) or _gri_pa(user_id, limit=1)
                    if _recent_pa:
                        _ctx_row = _recent_pa[0]
                        title = title or (_ctx_row.get("title") or "")
                        company = company or (_ctx_row.get("company") or "")
                except Exception:
                    pass

            if not title or not company:
                msg = (
                    "Which job would you like me to prepare the application for? "
                    "Tell me the job title and company, or search for jobs first."
                )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # 2. Get user CV — required for tailoring.
            _cv_text = ""
            _db_pa = None
            try:
                from src.rico_db import RicoDB
                _db_pa = RicoDB()
                _bundle = _db_pa.get_user_bundle(user_id)
                if _bundle:
                    _cv_text = (_bundle.get("cv_text") or "").strip()
            except Exception:
                pass

            if not _cv_text:
                msg = (
                    f"To prepare your application for **{title}** at **{company}**, "
                    "I need your CV first. Upload it from your profile or paste it in chat."
                )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {"type": "prepare_application", "intent": "prepare_application",
                     "message": msg, "next_action": "upload_cv"},
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # 3. Build job context fields.
            _apply_url = (_ctx_row or {}).get("apply_url") or ""
            _source_url = (_ctx_row or {}).get("source_url") or ""
            _location = (_ctx_row or {}).get("location") or "UAE"
            _job_key = self._derive_lifecycle_job_key(title, company)

            # 4. Duplicate protection — reuse existing pending draft for same job.
            _existing_draft = None
            try:
                if _db_pa is None:
                    from src.rico_db import RicoDB
                    _db_pa = RicoDB()
                _pending = _db_pa.get_application_drafts(user_id, status="pending")
                _existing_draft = next(
                    (d for d in _pending if d.get("job_key") == _job_key), None
                )
            except Exception:
                pass

            if _existing_draft:
                _draft = _existing_draft
                _reused = True
            else:
                # 5. Generate tailored CV + cover letter.
                _reused = False
                try:
                    from src.rico_apply_ai import tailor_application as _tailor
                    _tail = _tailor(
                        cv_text=_cv_text,
                        profile=profile if isinstance(profile, dict) else {},
                        job={
                            "title": title,
                            "company": company,
                            "description": "",
                            "apply_url": _apply_url or _source_url,
                            "location": _location,
                        },
                    )
                    _tailored_cv = (_tail.get("tailored_cv") or "").strip()
                    _cover_letter = (_tail.get("cover_letter") or "").strip()
                except Exception as _exc:
                    logger.warning("prepare_application tailor failed user=%s: %s", user_id, _exc)
                    msg = (
                        f"I had trouble generating the draft for **{title}** at **{company}** right now. "
                        "Please try again in a moment."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

                if not _tailored_cv or not _cover_letter:
                    msg = (
                        f"The draft for **{title}** at **{company}** came back incomplete. "
                        "Please try again or provide the job description for better results."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

                # 6. Insert into application_drafts.
                try:
                    if _db_pa is None:
                        from src.rico_db import RicoDB
                        _db_pa = RicoDB()
                    _draft = _db_pa.create_application_draft(
                        user_id=user_id,
                        job_key=_job_key,
                        job_title=title,
                        company=company,
                        job_description="",
                        apply_url=_apply_url or _source_url,
                        tailored_cv=_tailored_cv,
                        cover_letter=_cover_letter,
                    )
                except Exception as _exc:
                    logger.warning("create_application_draft failed user=%s: %s", user_id, _exc)
                    msg = (
                        f"I prepared your draft for **{title}** at **{company}** but couldn't save it. "
                        "Please try again shortly."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

            # 7. Update user_job_context lifecycle → prepared.
            try:
                from src.repositories.user_job_context_repo import set_lifecycle_status as _slc_pa
                _slc_pa(
                    user_id=user_id, title=title, company=company, status="prepared",
                    apply_url=_apply_url, source_url=_source_url,
                )
            except Exception:
                pass

            # 8. Learning signal for draft preparation.
            try:
                from src.repositories.learning_repo import get_learning_repository
                get_learning_repository().infer_signals_from_job_action(
                    user_id, "prepared",
                    {"title": title, "company": company, "apply_url": _apply_url or _source_url},
                )
            except Exception:
                pass

            # 9. Store recent context.
            self._store_recent_context(
                user_id,
                self._build_recent_application_context(
                    title=title, company=company, status="prepared", action="prepare_application",
                ),
            )

            _draft_id = str(_draft.get("id") or "")
            _cl = _draft.get("cover_letter") or ""
            _cl_preview = _cl[:350]
            _reuse_note = (
                "_(Existing pending draft found — showing that one.)_\n\n" if _reused else ""
            )
            msg = (
                f"{_reuse_note}**Draft ready — {title} at {company}**\n\n"
                f"**Cover letter preview:**\n{_cl_preview}"
                f"{'…' if len(_cl) > 350 else ''}\n\n"
                "Your tailored CV has been prepared. "
                "Review the full draft from Applications (/applications)."
            )
            response = {
                "type": "prepare_application",
                "intent": "prepare_application",
                "message": msg,
                "draft_id": _draft_id,
                "job_title": title,
                "job_company": company,
                "reused_draft": _reused,
                "options": [
                    {"action": "open_apply_link", "label": "Open apply link",
                     "message": f"open apply link for {title} at {company}"},
                    {"action": "mark_applied", "label": "Mark as applied",
                     "message": f"Mark as applied — {title} at {company}"},
                ],
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Mark as applied — from job card "Mark as applied — {title} at {company}"
        if legacy_intent == "mark_applied":
            from src.repositories.applications_repo import create_manual as _create_manual_app
            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""

            # Guard: require apply-link evidence or prior explicit confirmation.
            # If neither exists, return a clarification and set the pending-confirm flag.
            if not self._has_apply_evidence(user_id, title, company):
                msg = (
                    f"Before I mark **{title}** at **{company}** as applied, "
                    "can you confirm you submitted your application? "
                    "I don't have a record of you opening the apply link for this role."
                )
                # Store confirmation flag so the next "Mark as applied" for the same
                # job is treated as explicit manual confirmation and proceeds.
                try:
                    ctx = self._get_recent_context(user_id)
                    ctx["_pending_confirm_apply"] = {"title": title, "company": company}
                    self._store_recent_context(user_id, ctx)
                except Exception:
                    pass
                response = {
                    "type": "clarification",
                    "intent": "mark_applied",
                    "message": msg,
                    "job_title": title,
                    "job_company": company,
                    "options": [
                        {
                            "action": "confirm_mark_applied",
                            "label": "Yes, I applied",
                            "message": f"Mark as applied — {title} at {company}",
                        },
                        {
                            "action": "open_apply_link",
                            "label": "Show apply link first",
                            "message": f"open apply link for {title} at {company}",
                        },
                    ],
                    "next_action": "confirm_application",
                }
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            # Evidence confirmed — clear the pending flag and write the record.
            try:
                ctx = self._get_recent_context(user_id)
                ctx.pop("_pending_confirm_apply", None)
                self._store_recent_context(user_id, ctx)
            except Exception:
                pass

            try:
                saved = _create_manual_app(title=title, company=company, status="applied", user_id=user_id)
                if not saved:
                    raise RuntimeError("application create_manual returned false")
                msg = (
                    f"Tracked — **{title}** at **{company}** marked as applied. "
                    "I will treat this as your latest application context for follow-ups. "
                    "You can follow it from Applications (/applications)."
                )
                response_type = "mark_applied"
                job_status = "applied"
                next_action = "follow_up_after_7_days"
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="applied",
                        action="mark_applied",
                    ),
                )
                # Fire learning signal for confirmed application.
                try:
                    from src.repositories.learning_repo import get_learning_repository
                    get_learning_repository().infer_signals_from_job_action(
                        user_id, "apply", {"title": title, "company": company}
                    )
                except Exception:
                    pass
            except Exception:
                msg = (
                    f"I understand you submitted **{title}** at **{company}**, "
                    "but I couldn't save it right now. Please try again shortly."
                )
                response_type = "application_status_update_failed"
                job_status = None
                next_action = "retry_application_status_update"
            response = {
                "type": response_type,
                "intent": "mark_applied",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "job_status": job_status,
                "target_route": "/applications",
                "next_action": next_action,
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Track this job — from job card "Track this job — {title} at {company}"
        if legacy_intent == "track_job":
            from src.repositories.applications_repo import create_manual as _create_manual_app
            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""
            # Use URL evidence from recent context to distinguish a live posting
            # (apply link was opened/verified) from a lead that still needs verification.
            has_url = self._has_apply_evidence(user_id, title, company)
            try:
                _create_manual_app(title=title, company=company, status="saved", user_id=user_id)
                if has_url:
                    msg = (
                        f"Saved — **{title}** at **{company}**. "
                        "I will use this as your latest job context."
                    )
                else:
                    msg = (
                        f"Saved as lead — **{title}** at **{company}**. "
                        "This role hasn't been verified via an apply link yet — "
                        "open the apply link to confirm it's still live before applying."
                    )
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="saved",
                        action="track_job",
                    ),
                )
            except Exception:
                msg = (
                    f"Noted — **{title}** at **{company}** added to your tracking list. "
                    "(Could not write to Application Flow right now — please retry.)"
                )
            response = {
                "type": "track_job",
                "intent": "track_job",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "job_status": "saved",
                "next_action": "review_or_mark_applied",
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Open apply link — show URL only; never triggers apply confirmation
        if legacy_intent == "open_apply_link":
            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""
            apply_url = None
            source_was_lead = False

            # 1. Recent search matches (same session) — checked first so a job returned
            #    by a search can be acted on immediately without saving it first.
            #    Scan all matches for this title/company: prefer a live URL over a lead.
            #    Do NOT set apply_url="" on a lead match — that would skip Application Flow.
            if title and company:
                try:
                    ctx = self._get_recent_context(user_id)
                    for m in ctx.get("recent_search_matches", []):
                        if (title.lower() in (m.get("title") or "").lower() and
                                company.lower() in (m.get("company") or "").lower()):
                            url = (m.get("apply_url") or m.get("link") or "").strip()
                            if url:
                                apply_url = url
                                break  # Found a live URL — stop scanning
                            else:
                                # Lead match — note it, but keep scanning for a live URL entry
                                source_was_lead = (
                                    m.get("verification_status") == "lead_needs_verification"
                                )
                except Exception:
                    pass

            # 2. Application Flow records (saved / previously applied jobs)
            if not apply_url and title and company:
                try:
                    from src.repositories.applications_repo import get_all as _get_all_apps
                    for rec in _get_all_apps(user_id=user_id):
                        if (title.lower() in (rec.get("title") or "").lower() and
                                company.lower() in (rec.get("company") or "").lower()):
                            url = self._extract_rec_url(rec)
                            if url:
                                apply_url = url
                                source_was_lead = False  # Real URL found — clear lead flag
                                break
                            elif apply_url is None:
                                apply_url = ""
                except Exception:
                    pass

            # 3. Neon user_job_context — survives restarts and postgres memory mode
            db_source_url = None
            if not apply_url and title and company:
                try:
                    from src.repositories.user_job_context_repo import find_by_title_company
                    row = find_by_title_company(user_id, title, company)
                    if row:
                        if row.get("apply_url"):
                            apply_url = row["apply_url"]
                            source_was_lead = False
                        elif row.get("source_url"):
                            db_source_url = row["source_url"]
                            source_was_lead = (
                                row.get("verification_status") == "lead_needs_verification"
                            )
                except Exception:
                    pass

            # Check if link is expired before opening
            is_expired = False
            try:
                ctx = self._get_recent_context(user_id)
                for m in ctx.get("recent_search_matches", []):
                    if (title.lower() in (m.get("title") or "").lower() and
                            company.lower() in (m.get("company") or "").lower()):
                        if m.get("verification_status") == "expired":
                            is_expired = True
                            break
            except Exception:
                pass

            if is_expired:
                msg = (
                    f"The apply link for **{title}** at **{company}** appears to be expired.\n\n"
                    "You can:\n"
                    "• **Refresh** — I can try to find an updated listing\n"
                    "• **Dismiss** — Remove this role from your feed\n"
                    "• **Search** — Look for similar roles right now"
                )
                response = {
                    "type": "open_apply_link",
                    "intent": "open_apply_link",
                    "message": msg,
                    "apply_url": None,
                    "verification_status": "expired",
                    "options": [
                        {"action": "refresh_link", "label": "Refresh", "message": f"refresh link for {title} at {company}"},
                        {"action": "dismiss_job", "label": "Dismiss", "message": f"dismiss {title} at {company}"},
                        {"action": "search_similar", "label": "Search similar", "message": f"search similar to {title} at {company}"},
                    ],
                }
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            if apply_url:
                msg = f"Apply link for **{title}** at **{company}**: {apply_url}"
                # Persist to Application Flow so opened state survives session/restart
                self._persist_application_lifecycle_event(
                    user_id=user_id,
                    title=title,
                    company=company,
                    status="opened_external",
                    url=apply_url,
                )
                # Store URL evidence so a subsequent "Mark as applied" can proceed
                # without requiring a separate confirmation step.
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="opened_external",
                        action="open_apply_link",
                        link=apply_url,
                    ),
                )
                # Opening an apply link is distinct browsing interest — lighter than save.
                try:
                    from src.repositories.learning_repo import get_learning_repository
                    get_learning_repository().infer_signals_from_job_action(
                        user_id, "opened_external", {"title": title, "company": company, "apply_url": apply_url}
                    )
                except Exception:
                    pass
            elif db_source_url:
                msg = (
                    f"I don't have a direct apply link saved for **{title}** at **{company}**, "
                    f"but I found the source job listing: {db_source_url}\n\n"
                    "Open it to apply from the official listing."
                )
            elif title and company:
                if source_was_lead:
                    msg = (
                        f"**{title}** at **{company}** was returned as a lead — "
                        "it has no verified apply link yet. "
                        "Check the company website or LinkedIn to confirm the role is still live "
                        "before applying."
                    )
                else:
                    msg = (
                        f"I don't have the official apply link saved yet for **{title}** at **{company}**. "
                        "I'll keep this role marked as needs source verification and continue with verified matches."
                    )
            else:
                # No title/company provided — try to resolve from recently discussed jobs
                resolved_recent = None
                try:
                    from src.repositories.user_job_context_repo import (
                        get_recently_discussed as _get_recently_discussed,
                        get_recently_interacted as _get_recently_interacted,
                    )
                    recent = _get_recently_discussed(user_id, limit=1)
                    if not recent:
                        recent = _get_recently_interacted(user_id, limit=1)
                    if recent:
                        resolved_recent = recent[0]
                except Exception:
                    pass

                if resolved_recent:
                    title = resolved_recent.get("title") or ""
                    company = resolved_recent.get("company") or ""
                    apply_url = resolved_recent.get("apply_url") or ""
                    source_url_fallback = resolved_recent.get("source_url") or ""
                    if apply_url:
                        msg = f"Apply link for **{title}** at **{company}**: {apply_url}"
                        self._persist_application_lifecycle_event(
                            user_id=user_id,
                            title=title,
                            company=company,
                            status="opened_external",
                            url=apply_url,
                        )
                        self._store_recent_context(
                            user_id,
                            self._build_recent_application_context(
                                title=title,
                                company=company,
                                status="opened_external",
                                action="open_apply_link",
                                link=apply_url,
                            ),
                        )
                        try:
                            from src.repositories.learning_repo import get_learning_repository
                            get_learning_repository().infer_signals_from_job_action(
                                user_id, "opened_external", {"title": title, "company": company, "apply_url": apply_url}
                            )
                        except Exception:
                            pass
                    elif source_url_fallback:
                        msg = (
                            f"I don't have a direct apply link for **{title}** at **{company}**, "
                            f"but here's the source listing: {source_url_fallback}"
                        )
                    else:
                        msg = (
                            f"I found your recent job **{title}** at **{company}**, "
                            "but I don't have an apply link saved for it yet. "
                            "Run a search to refresh the listing."
                        )
                else:
                    msg = "Please specify the job title and company so I can look up the apply link."
            response = {"type": "open_apply_link", "intent": "open_apply_link",
                        "message": msg, "apply_url": apply_url}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Recent context follow-up — "where?", "show it", "what about the job I just applied to?"
        if legacy_intent == "recent_context":
            ctx = self._get_recent_context(user_id)
            if ctx:
                msg = self._build_recent_context_message(ctx)
            else:
                apps = None
                try:
                    from src.repositories.applications_repo import get_all as _get_all_apps
                    apps = _get_all_apps(user_id=user_id)
                except Exception:
                    apps = None
                if apps is None:
                    msg = (
                        "I couldn't retrieve your application history right now. "
                        "Please try again shortly."
                    )
                elif apps:
                    latest = self._enrich_applications([self._sort_applications_recent(apps)[0]])[0]
                    job = (latest.get("title") or "Unknown")
                    company = (latest.get("company") or "Unknown")
                    status = latest.get("status_label") or latest.get("status") or "tracked"
                    days = latest.get("days_since_applied")
                    days_str = (
                        f", applied {days} day{'s' if days != 1 else ''} ago"
                        if days is not None else ""
                    )
                    fu_hint = " Consider following up now." if latest.get("needs_follow_up") else " Keep tracking it here."
                    msg = (
                        f"Most recent: **{job}** at **{company}** — status: **{status}**{days_str}. "
                        f"{fu_hint}"
                    )
                else:
                    msg = (
                        "You don't have any tracked applications yet. "
                        "Say 'Mark as applied' on any job to start tracking."
                    )
            response = {"type": "recent_context", "intent": "recent_context", "message": msg}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Bulk / unsafe apply — safety block: never auto-apply to all jobs
        if legacy_intent == "bulk_apply_unsafe":
            _bulk_msg = (
                "I can't apply to all jobs automatically. "
                "Please choose specific jobs to apply for, or narrow your search first.\n\n"
                "ما بقدر أقدّم على كل الوظائف تلقائيًا. "
                "اختار وظائف محددة أو ضيّق البحث أولاً."
            )
            response = {
                "type": "safety_block",
                "intent": "bulk_apply_unsafe",
                "message": _bulk_msg,
            }
            self._append_chat(user_id, "assistant", _bulk_msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Apply job — confirmation gate
        if intent == "apply_job":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            response = {
                "type": "confirmation_required",
                "intent": "apply_job",
                "message": routed.confirmation_prompt or (
                    "To confirm: mark this job as applied and track it. "
                    "Reply YES to confirm or CANCEL to abort."
                ),
                "tool_args": routed.tool_args,
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, routed.source, profile=profile)

        # Save target role — "save X as target role" / "set X as target role"
        if legacy_intent == "save_target_role" and intent_result.extracted_role:
            role = intent_result.extracted_role.strip()
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if role.lower() not in {str(r).lower() for r in target_roles}:
                target_roles.append(role)
                upsert_profile(user_id=user_id, updates={"target_roles": target_roles})
            response = {
                "type": "preferences_updated",
                "message": (
                    f"Got it — I've saved **{role}** as your target role. "
                    "I'll use it for all future job searches. "
                    "Say 'find jobs' whenever you're ready."
                ),
                "updated": {"target_roles": target_roles},
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Save job
        if legacy_intent == "save_job":
            # "Save — {title} at {company}" comes from a Rico-generated job card.
            # Resolve the job from recent results / persisted context so the user
            # is never asked for a URL to save something Rico itself produced.
            raw_title = (getattr(intent_result, "extracted_title", None) or "").strip()
            raw_company = (getattr(intent_result, "extracted_company", None) or "").strip()
            resolved = self._resolve_card_job(user_id, raw_title, raw_company)
            title = ((resolved.get("title") if resolved else None) or raw_title).strip()
            company = ((resolved.get("company") if resolved else None) or raw_company).strip()

            if title and company:
                apply_url = ((resolved.get("apply_url") if resolved else "") or "").strip()
                source_url = ((resolved.get("source_url") if resolved else "") or "").strip()
                alt_url = (
                    ((resolved.get("alt_url") or resolved.get("alt_link")) if resolved else "") or ""
                ).strip()
                # No direct apply URL → save with the best available source/alt link
                # and flag it for verification. Never block the save on a missing URL.
                effective_source = source_url or alt_url
                verification_status = (resolved or {}).get("verification_status") or "lead_needs_verification"
                if not apply_url and effective_source:
                    verification_status = "needs_source_verification"

                job_dict = {
                    "title": title,
                    "company": company,
                    "apply_url": apply_url,
                    "source_url": effective_source,
                    "alt_url": alt_url,
                    "verification_status": verification_status,
                }
                # Stable job_key (title+company) keeps runtime idempotency correct
                # and lets the runtime stamp record_interaction + set_lifecycle_status.
                job_key = self._derive_lifecycle_job_key(title, company)
                result = agent_runtime.handle_action(
                    user_id=user_id, action="save", job=job_dict, job_key=job_key, source="chat",
                )
                if result.ok:
                    success_msg = f"Saved — {title} at {company}. I'll keep it in your tracked jobs."
                else:
                    logger.warning(
                        "rico_chat: save action not ok user=%s title=%s err=%s",
                        user_id, title, result.error,
                    )
                    success_msg = (
                        f"Noted — {title} at {company} is in your tracker. "
                        "I'll keep it with your saved jobs."
                    )
                response = {
                    "type": "save_job",
                    "intent": "save_job",
                    "message": success_msg,
                    "entities": {"title": title, "company": company},
                    "verification_status": verification_status,
                }
                self._append_chat(user_id, "assistant", success_msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            # No title/company from card — try recently discussed/interacted job before router.
            _recent_resolved = None
            try:
                from src.repositories.user_job_context_repo import (
                    get_recently_discussed as _get_recently_discussed_sj,
                    get_recently_interacted as _get_recently_interacted_sj,
                )
                _recent_list = _get_recently_discussed_sj(user_id, limit=1)
                if not _recent_list:
                    _recent_list = _get_recently_interacted_sj(user_id, limit=1)
                if _recent_list:
                    _recent_resolved = _recent_list[0]
            except Exception:
                pass

            if _recent_resolved:
                title = (_recent_resolved.get("title") or "").strip()
                company = (_recent_resolved.get("company") or "").strip()
                if title and company:
                    apply_url = (_recent_resolved.get("apply_url") or "").strip()
                    source_url = (_recent_resolved.get("source_url") or "").strip()
                    job_dict = {
                        "title": title,
                        "company": company,
                        "apply_url": apply_url,
                        "source_url": source_url,
                        "verification_status": "lead_needs_verification",
                    }
                    job_key = self._derive_lifecycle_job_key(title, company)
                    result = agent_runtime.handle_action(
                        user_id=user_id, action="save", job=job_dict, job_key=job_key, source="chat",
                    )
                    success_msg = (
                        f"Saved — {title} at {company}. I'll keep it in your tracked jobs."
                        if result.ok else
                        f"Noted — {title} at {company} is in your tracker."
                    )
                    response = {
                        "type": "save_job",
                        "intent": "save_job",
                        "message": success_msg,
                        "entities": {"title": title, "company": company},
                    }
                    self._append_chat(user_id, "assistant", success_msg)
                    return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            # Could not identify a job from the card or recent context — fall back to the tool router.
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                result = agent_runtime.handle_action(
                    user_id=user_id, action="save", job_key=job_key, source="chat",
                )
                response = {
                    "type": "save_job",
                    "intent": "save_job",
                    "message": result.message,
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", result.message)
                return self._finalize(response, routed.source, profile=profile)

        # Explain match
        if legacy_intent == "explain_match":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                result = agent_runtime.handle_action(
                    user_id=user_id, action="why", job_key=job_key, source="chat",
                )
                response = {
                    "type": "explain_match",
                    "intent": "explain_match",
                    "message": result.message,
                }
                self._append_chat(user_id, "assistant", result.message)
                return self._finalize(response, routed.source, profile=profile)

        # Draft message / cover letter
        if legacy_intent == "draft_message":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                # Resolve job dict so generate_message gets full context + profile identity
                _routed_job = self._resolve_recent_application_job(user_id) or {}
                if _routed_job:
                    from src.message_generator import generate_message as _gen_msg
                    cover = _gen_msg(_routed_job, profile=profile)
                    self._append_chat(user_id, "assistant", cover)
                    return self._finalize(
                        {"type": "draft_message", "intent": "draft_message", "message": cover},
                        routed.source, profile=profile,
                    )
                result = agent_runtime.handle_action(
                    user_id=user_id, action="draft", job_key=job_key, source="chat",
                )
                response = {
                    "type": "draft_message",
                    "intent": "draft_message",
                    "message": result.message,
                }
                self._append_chat(user_id, "assistant", result.message)
                return self._finalize(response, routed.source, profile=profile)
            # Try latest-job context before asking user to specify
            _latest_job = self._resolve_recent_application_job(user_id)
            if _latest_job and (_latest_job.get("title") or _latest_job.get("company")):
                from src.message_generator import generate_message
                cover = generate_message(_latest_job, profile=profile)
                self._append_chat(user_id, "assistant", cover)
                return self._finalize(
                    {"type": "draft_message", "intent": "draft_message", "message": cover},
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            # No job in context at all — guide user to pick a role or job first
            name = self._profile_value(profile, "name") or ""
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if target_roles:
                roles_hint = ", ".join(target_roles[:3])
                msg = (
                    f"I can write a cover letter for you{', ' + name if name else ''}. "
                    f"Which role should I tailor it for?\n\n"
                    f"Your target roles: **{roles_hint}**\n\n"
                    "Reply with a role name, or paste a job posting and I'll tailor it directly."
                )
            else:
                msg = (
                    f"I can write a cover letter for you{', ' + name if name else ''}. "
                    "Which role and company should I target?\n\n"
                    "Reply with:\n"
                    "• Role title and company name\n"
                    "• Or paste the job posting directly"
                )
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(
                {"type": "cover_letter_prompt", "message": msg, "next_action": "provide_job_for_cover_letter"},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Show latest pending application draft
        if legacy_intent == "show_draft":
            _drafts_sd = []
            try:
                from src.rico_db import RicoDB
                _drafts_sd = RicoDB().get_application_drafts(user_id, status="pending")
            except Exception:
                pass

            if not _drafts_sd:
                msg = (
                    "You don't have any pending application drafts yet. "
                    "Say **'prepare application'** for a saved job and I'll generate one."
                )
            else:
                _d = _drafts_sd[0]
                _d_title = _d.get("job_title") or "Unknown"
                _d_company = _d.get("company") or "Unknown"
                _d_cl = _d.get("cover_letter") or ""
                _d_preview = _d_cl[:400]
                msg = (
                    f"**Latest draft — {_d_title} at {_d_company}**\n\n"
                    f"**Cover letter:**\n{_d_preview}"
                    f"{'…' if len(_d_cl) > 400 else ''}\n\n"
                    "Your tailored CV is also ready. "
                    "Visit Applications (/applications) to review and approve."
                )
            response = {"type": "show_draft", "intent": "show_draft", "message": msg}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Interview prep
        if legacy_intent == "interview_prep":
            user_context = self._build_openai_context(profile, user_id=user_id)
            system_prompt = (
                "You are Rico, a UAE career coach. Give concise, practical interview preparation "
                "tips including likely questions, company research pointers, and answer frameworks."
            )
            hf_text = None
            if hf_ok():
                hf_text = generate_text(message, system=system_prompt, max_new_tokens=400)
            msg = hf_text or (
                "I will prepare interview notes, likely questions, and suggested answers based on your target role. "
                "Share the specific job title or company name for a more tailored response."
            )
            response = {"type": "interview_prep", "message": msg}
            self._append_chat(user_id, "assistant", msg)
            src = self.SOURCE_HF if hf_text else self.SOURCE_FALLBACK
            return self._finalize(response, src, profile=profile)

        # Nonsense — do NOT search
        if legacy_intent == "nonsense":
            response = {
                "type": "clarification",
                "message": (
                    "I could not understand that message. "
                    "Try telling me a job role to search, or say 'help' for options."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # ── Step 3: Unknown intent — try role classification, then clarify ───

        # Help-option phrase guard: phrases from the help menu ("Finding jobs",
        # "job search", etc.) are action selections, not job role titles.
        # Route them to a role-prompt so the user can name a concrete role.
        if message.strip().lower() in self._JOB_SEARCH_HELP_PHRASES:
            if has_cv:
                return self._finalize(
                    self._handle_profile_role_suggestions(profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            response = {
                "type": "clarification",
                "intent": "search_jobs",
                "message": (
                    "Sure — which role should I search for? "
                    "Tell me a specific role like 'HSE Manager' or "
                    "'Environmental Engineer', or upload your CV and I'll suggest roles from your background."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Settings / notification commands ("enable telegram notifications",
        # "turn off email alerts") are neither job roles nor job searches.
        # Guide the user to Settings instead of emitting a role error.
        if _SETTINGS_COMMAND_RE.search(message):
            response = {
                "type": "settings_guidance",
                "intent": "settings_update",
                "message": (
                    "You can manage notifications — Telegram, WhatsApp and job "
                    "alerts — from your Settings page. Open Settings → Notifications "
                    "to turn them on or off."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Only attempt role search if message looks like a plausible role (short text, no digits)
        if has_cv and self._looks_like_bare_target_role(message):
            logger.info(
                "bare_role_gate_pass user=%s msg_len=%d",
                user_id,
                len(message),
            )
            return self._finalize(
                self._classified_role_search(user_id, message.strip(), profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )
        logger.info(
            "bare_role_gate_reject_to_ai user=%s msg_len=%d",
            user_id,
            len(message),
        )

        # Final fallback: use AI for natural reply, but never treat as job search
        return self._answer_with_ai_fallback(
            user_id=user_id,
            message=message,
            profile=profile,
            save_user_message=False,
        )

    # ── New intent-specific handlers ─────────────────────────────────────────

    def _store_search_matches_context(self, user_id: str, formatted: list[dict[str, Any]], search_role: str = "") -> None:
        """Merge recent search results into context and persist to Neon."""
        try:
            ctx = self._get_recent_context(user_id)
            if search_role:
                ctx["recent_search_role"] = search_role
            ctx["recent_search_matches"] = [
                {
                    "title": m.get("title", ""),
                    "company": m.get("company", ""),
                    "location": m.get("location", ""),
                    "apply_url": m.get("apply_url", ""),
                    "source_url": m.get("source_url", ""),
                    "link": m.get("apply_url", ""),
                    "verification_status": m.get("verification_status", "lead_needs_verification"),
                }
                for m in formatted
            ]
            self._store_recent_context(user_id, ctx)
        except Exception:
            logger.debug("rico_chat: failed to store search matches context user=%s", user_id)

        # Persist to Neon so links survive restarts and postgres memory mode.
        try:
            from src.repositories.user_job_context_repo import upsert_matches
            upsert_matches(user_id, formatted)
        except Exception:
            logger.debug("rico_chat: failed to persist search matches to DB user=%s", user_id)

        # Fire per-user Telegram notification for the top match (best-effort).
        # Opt-in check and rate guard happen inside send_user_notification.
        try:
            if formatted:
                from src.services.telegram_notifications import send_user_notification
                top = formatted[0]
                role = search_role or top.get("title", "your search")
                n = len(formatted)
                msg = (
                    f"🔔 <b>Rico found {n} new job match{'es' if n != 1 else ''}</b> for <b>{role}</b>.\n\n"
                    f"Open the Rico app to review and apply."
                )
                send_user_notification(
                    user_id=user_id,
                    message=msg,
                    alert_type="job_alert",
                    job=None,
                )
        except Exception:
            logger.debug("rico_chat: failed to send Telegram job-alert user=%s", user_id)

    @staticmethod
    def _get_status_rank(status: str) -> int:
        """Return numeric rank for application status to prevent regression.

        Higher rank = more advanced status.
        """
        STATUS_RANK = {
            "saved": 10,
            "opened": 20,
            "opened_external": 20,
            "prepared": 30,
            "applied": 40,
            "follow_up_due": 50,
            "interview": 60,
            "offer": 70,
            "rejected": 70,
            "decision_made": 80,
            "archived": 90,
        }
        return STATUS_RANK.get(status, 0)

    @staticmethod
    def _should_update_status(current_status: str, new_status: str) -> bool:
        """Return True if new_status should replace current_status.

        Only update if new status is equal or more advanced than current.
        Never downgrade from applied/interview/offer/rejected/decision_made.
        """
        current_rank = RicoChatAPI._get_status_rank(current_status)
        new_rank = RicoChatAPI._get_status_rank(new_status)
        return new_rank >= current_rank

    def _resolve_card_job(
        self, user_id: str, raw_title: str, raw_company: str
    ) -> Optional[dict[str, Any]]:
        """Resolve a job-card action back to the job Rico generated.

        When the user clicks "Save — {title} at {company}", the classifier's
        greedy "... at ..." split can mis-attribute the boundary (e.g. a company
        like "Careers at UAE"). This reconstructs the original "{title} at
        {company}" string and matches it against, in order:
          1. the last search-result payload (recent_search_matches in context),
          2. persisted user_job_context (find_by_title_company across splits),
          3. recently interacted / discussed jobs.
        Returns the matched job dict (title/company/apply_url/source_url/...) or
        None. Never raises.
        """
        raw_title = (raw_title or "").strip()
        raw_company = (raw_company or "").strip()
        if not raw_title and not raw_company:
            return None
        payload = (f"{raw_title} at {raw_company}" if raw_company else raw_title).strip().lower()

        def _matches(cand_title: str, cand_company: str) -> bool:
            ct = (cand_title or "").strip()
            cc = (cand_company or "").strip()
            if not ct:
                return False
            combined = (f"{ct} at {cc}" if cc else ct).strip().lower()
            if combined == payload:
                return True
            return payload.startswith(ct.lower()) and (not cc or payload.endswith(cc.lower()))

        # 1. Last search-result payload (in-memory context).
        try:
            ctx = self._get_recent_context(user_id)
            for m in ctx.get("recent_search_matches", []) or []:
                if _matches(m.get("title", ""), m.get("company", "")):
                    return dict(m)
        except Exception:
            logger.debug("rico_chat: card-job recent-match lookup failed user=%s", user_id, exc_info=True)

        # 2 + 3. Persisted context + recently interacted/discussed (survives restarts).
        try:
            from src.repositories.user_job_context_repo import (
                find_by_title_company,
                get_recently_interacted,
                get_recently_discussed,
            )
            # Try each plausible title/company boundary of the reconstructed payload
            # so "Careers at UAE" is matched as the company rather than truncated.
            full = f"{raw_title} at {raw_company}" if raw_company else raw_title
            parts = full.split(" at ")
            candidates: list[tuple[str, str]] = []
            if raw_title and raw_company:
                candidates.append((raw_title, raw_company))
            for i in range(1, len(parts)):
                t = " at ".join(parts[:i]).strip()
                c = " at ".join(parts[i:]).strip()
                if t and c and (t, c) not in candidates:
                    candidates.append((t, c))
            for t, c in candidates:
                row = find_by_title_company(user_id, t, c)
                if row:
                    return row
            for fn in (get_recently_interacted, get_recently_discussed):
                for row in fn(user_id) or []:
                    if _matches(row.get("title", ""), row.get("company", "")):
                        return row
        except Exception:
            logger.debug("rico_chat: card-job db lookup failed user=%s", user_id, exc_info=True)

        return None

    @staticmethod
    def _derive_lifecycle_job_key(title: str, company: str, url: str = "") -> str:
        """Derive stable job key for lifecycle events.

        Prefers title + company fallback to match mark_applied/create_manual behavior.
        Only uses URL if title/company are not available.
        """
        from src.applications import get_job_id
        # Prefer title/company fallback to match mark_applied behavior
        if title and company:
            return get_job_id({"title": title, "company": company})
        # Fallback to URL if title/company missing
        if url:
            return get_job_id({"link": url})
        # Last resort: title only
        return get_job_id({"title": title or "", "company": ""})

    def _get_existing_application_status(
        self, user_id: str, job_key: str
    ) -> Optional[str]:
        """Get current status for user/job from rico_job_recommendations.

        Returns None if no record exists.
        """
        try:
            from src.repositories.applications_repo import find_by_job_id
            existing = find_by_job_id(job_key, user_id)
            if existing:
                return existing.get("status")
        except Exception:
            pass
        return None

    def _persist_application_lifecycle_event(
        self,
        user_id: str,
        title: str,
        company: str,
        status: str,
        url: str = "",
        location: str = "",
    ) -> None:
        """Persist application lifecycle event to rico_job_recommendations.

        Safely wraps DB write so response flow is not blocked on failure.
        Uses stable job key to match mark_applied/create_manual behavior.
        Prevents status regression by checking existing status before upsert.
        """
        try:
            from src.repositories.applications_repo import create as _create_app

            # Derive stable job key (prefer title/company to match mark_applied)
            job_key = self._derive_lifecycle_job_key(title, company, url)

            # Check existing status to prevent regression
            existing_status = self._get_existing_application_status(user_id, job_key)

            # Only update if no record exists or new status is equal/more advanced
            if existing_status is None or self._should_update_status(existing_status, status):
                _create_app(
                    job_id=job_key,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    status=status,
                    source="chat",
                    user_id=user_id,
                )
            else:
                logger.debug(
                    "rico_chat: skipped lifecycle status update user=%s title=%s company=%s "
                    "existing_status=%s new_status=%s (would regress)",
                    user_id, title, company, existing_status, status
                )
        except Exception:
            # DB write failure should not block the response
            logger.debug(
                "rico_chat: failed to persist lifecycle event user=%s title=%s company=%s status=%s",
                user_id, title, company, status
            )
        # Also stamp user_job_context with the lifecycle timestamp so Rico can
        # answer funnel-memory questions ("show jobs I opened but didn't apply to").
        try:
            from src.repositories.user_job_context_repo import set_lifecycle_status
            set_lifecycle_status(
                user_id=user_id,
                title=title,
                company=company,
                status=status,
                apply_url=url,
            )
        except Exception:
            logger.debug(
                "rico_chat: failed to stamp user_job_context lifecycle user=%s title=%s",
                user_id, title,
            )

    def _resolve_application_status_job(
        self,
        user_id: str,
        message: str,
    ) -> dict[str, Any] | None:
        """Resolve an "I applied to that job" report to recent Rico job context."""
        try:
            ctx = self._get_recent_context(user_id)
        except Exception:
            ctx = {}
        candidates: list[dict[str, Any]] = []

        if isinstance(ctx, dict):
            pending = ctx.get("_pending_application_send")
            if isinstance(pending, dict) and isinstance(pending.get("job"), dict):
                candidates.append(dict(pending["job"]))

            recent_app = ctx.get("recent_application")
            if isinstance(recent_app, dict):
                candidates.append(dict(recent_app))

            matches = ctx.get("recent_search_matches") or []
            if isinstance(matches, list):
                candidates.extend(dict(m) for m in matches if isinstance(m, dict))

        message_lower = (message or "").lower()
        for candidate in candidates:
            title = self._job_context_value(candidate, "title")
            company = self._job_context_value(candidate, "company")
            if (
                (title and title.lower() in message_lower)
                or (company and company.lower() in message_lower)
            ):
                return candidate

        if candidates:
            return candidates[0]

        try:
            from src.repositories.user_job_context_repo import (
                get_recently_discussed,
                get_recently_interacted,
            )

            for lookup in (get_recently_interacted, get_recently_discussed):
                rows = lookup(user_id) or []
                for row in rows:
                    if isinstance(row, dict) and (row.get("title") or row.get("company")):
                        return dict(row)
        except Exception:
            logger.debug(
                "rico_chat: failed to resolve applied-status job context user=%s",
                user_id,
                exc_info=True,
            )
        return None

    def _persist_confirmed_application_status(
        self,
        *,
        user_id: str,
        job: dict[str, Any],
    ) -> tuple[bool, str]:
        """Strictly persist an applied-status report before Rico confirms it."""
        title = self._job_context_value(job, "title")
        company = self._job_context_value(job, "company")
        location = self._job_context_value(job, "location")
        url = self._job_context_value(job, "apply_url", "link", "source_url")
        if not title or not company:
            return False, ""

        job_key = self._derive_lifecycle_job_key(title, company, url)
        try:
            existing_status = self._get_existing_application_status(user_id, job_key)
            if existing_status is None or self._should_update_status(existing_status, "applied"):
                from src.repositories.applications_repo import create as _create_app

                created = _create_app(
                    job_id=job_key,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    status="applied",
                    source="chat",
                    user_id=user_id,
                )
                if not created:
                    return False, job_key

            from src.repositories.user_job_context_repo import set_lifecycle_status

            lifecycle_ok = set_lifecycle_status(
                user_id=user_id,
                title=title,
                company=company,
                status="applied",
                apply_url=url,
                note="User reported application submitted in chat.",
            )
            if not lifecycle_ok:
                return False, job_key

            return True, job_key
        except Exception:
            logger.exception(
                "rico_chat: failed strict applied-status persistence user=%s title=%s company=%s",
                user_id,
                title,
                company,
            )
            return False, job_key

    def _store_application_status_context(
        self,
        user_id: str,
        *,
        job: dict[str, Any],
        job_id: str,
    ) -> None:
        title = self._job_context_value(job, "title")
        company = self._job_context_value(job, "company")
        link = self._job_context_value(job, "apply_url", "link", "source_url")
        context = self._build_recent_application_context(
            title=title,
            company=company,
            status="applied",
            action="application_status_update",
            route="/applications",
            job_id=job_id,
            link=link,
        )
        try:
            existing = self._get_recent_context(user_id)
            if isinstance(existing, dict):
                existing.update(context)
                context = existing
        except Exception:
            pass
        self._store_recent_context(user_id, context)

    def _handle_application_status_update(
        self,
        user_id: str,
        message: str,
        profile: Any,
    ) -> dict[str, Any]:
        """Handle user reports that an application has already been submitted."""
        arabic = self._is_arabic_text(message)
        if str(user_id or "").startswith("public:"):
            msg = (
                "سجّل الدخول أولاً لكي أحفظ طلباتك في Applications."
                if arabic else
                "Sign in first so I can save this in Applications."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "clarification",
                "intent": "application_status_update",
                "message": msg,
                "next_action": "sign_in_required",
            }

        job = self._resolve_application_status_job(user_id, message)
        title = self._job_context_value(job or {}, "title")
        company = self._job_context_value(job or {}, "company")
        if not arabic and self._MANUAL_APPLICATION_LOG_QUESTION_RE.search(message or ""):
            if job and title and company:
                msg = (
                    "I can log that manually in Applications (/applications). "
                    f"If you already submitted **{title}** at **{company}**, reply "
                    "'mark it as applied' and I will save it after the database update succeeds."
                )
                next_action = "confirm_mark_applied"
            else:
                msg = (
                    "I can add a manually submitted application to Applications (/applications). "
                    "Send me the job title, company name, and source/link if available, "
                    "then I can mark it as applied."
                )
                next_action = "provide_manual_application_details"
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "manual_application_logging_guidance",
                "intent": "application_status_update",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "target_route": "/applications",
                "next_action": next_action,
            }

        if not job or not title or not company:
            msg = (
                "أي وظيفة تقصد؟ أرسل اسم الوظيفة أو الشركة لكي أسجلها كطلب تم تقديمه."
                if arabic else
                "I can add it to Applications (/applications) as applied. "
                "Send me the job title, company name, and source/link if available."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "clarification",
                "intent": "application_status_update",
                "message": msg,
                "next_action": "choose_job_to_mark_applied",
            }

        persisted, job_id = self._persist_confirmed_application_status(user_id=user_id, job=job)
        if persisted:
            self._store_application_status_context(user_id, job=job, job_id=job_id)
            if arabic:
                msg = (
                    "تم تسجيل التقديم بنجاح. يمكنك متابعته من صفحة Applications (/applications).\n\n"
                    f"{title} - {company}"
                )
            else:
                msg = (
                    "Application marked as submitted. You can track it from Applications (/applications).\n\n"
                    f"{title} at {company}"
                )
            response_type = "application_status_update"
            next_action = "view_applications"
        else:
            if arabic:
                msg = (
                    "فهمت أنك قدمت على هذه الوظيفة، لكن لم أستطع حفظها الآن. "
                    "حاول مرة أخرى بعد قليل."
                )
            else:
                msg = (
                    "I understand you submitted this application, but I could not save it right now. "
                    "Please try again shortly."
                )
            response_type = "application_status_update_failed"
            next_action = "retry_application_status_update"

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": response_type,
            "intent": "application_status_update",
            "message": msg,
            "job_id": job_id,
            "job_title": title,
            "job_company": company,
            "job_status": "applied" if persisted else None,
            "target_route": "/applications",
            "next_action": next_action,
        }

    def _store_recent_context(self, user_id: str, context: dict[str, Any]) -> None:
        try:
            self.memory.set_context(user_id, "recent_context", context)
        except Exception:
            logger.warning("rico_chat: failed to store recent context for user=%s", user_id)

    def _get_recent_context(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "recent_context") or {}
        except Exception:
            return {}

    @staticmethod
    def _extract_rec_url(rec: dict[str, Any]) -> str:
        """Return the best available apply URL from a recommendation record.

        Checks top-level fields first (link, apply_url, job_apply_link, apply_link,
        source_url), then falls back to the same keys inside a nested 'job_data' or
        'job' sub-dict for records that were not fully flattened by get_recommendations.
        """
        top_level_url = (
            rec.get("link")
            or rec.get("apply_url")
            or rec.get("job_apply_link")
            or rec.get("apply_link")
            or rec.get("source_url")
            or ""
        )
        if top_level_url:
            return str(top_level_url).strip()
        nested = rec.get("job_data") or rec.get("job") or {}
        if isinstance(nested, dict):
            return str(
                nested.get("link")
                or nested.get("apply_url")
                or nested.get("job_apply_link")
                or nested.get("apply_link")
                or nested.get("source_url")
                or ""
            ).strip()
        return ""

    def _has_apply_evidence(self, user_id: str, title: str, company: str) -> bool:
        """Return True when there is evidence the user opened an apply link for title/company.

        Evidence sources (checked in order):
          1. Recent context: `_pending_confirm_apply` flag set by the clarification response.
          2. Recent context: a recorded `link` for a matching job (set by open_apply_link handler).
        """
        try:
            ctx = self._get_recent_context(user_id)
            # Explicit manual-confirmation flag set when we returned a clarification
            pending = ctx.get("_pending_confirm_apply") or {}
            if (
                pending.get("title", "").lower() == title.lower()
                and pending.get("company", "").lower() == company.lower()
            ):
                return True
            # URL evidence from a prior open_apply_link or application_tracking action
            recent_app = ctx.get("recent_application") or {}
            if (
                title.lower() in (recent_app.get("title") or "").lower()
                and company.lower() in (recent_app.get("company") or "").lower()
                and recent_app.get("link")
            ):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _application_status_label(status: str | None) -> str:
        labels = {
            "saved": "saved for review",
            "opened": "opened",
            "opened_external": "opened externally",
            "applied": "applied",
            "interview": "interview stage",
            "rejected": "rejected",
            "offer": "offer stage",
            "decision_made": "closed",
        }
        return labels.get((status or "").strip().lower(), status or "tracked")

    def _build_recent_application_context(
        self,
        *,
        title: str,
        company: str,
        status: str,
        action: str,
        route: str = "/command",
        job_id: str | None = None,
        link: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        status_label = self._application_status_label(status)
        return {
            "type": "application",
            "recent_job": title,
            "recent_company": company,
            "recent_application": {
                "job_id": job_id,
                "title": title,
                "company": company,
                "status": status,
                "status_label": status_label,
                "link": link or "",
                "route": route,
                "last_action": action,
                "updated_at": now,
            },
            "recent_status": status,
            "recent_status_label": status_label,
            "recent_route": route,
            "recent_action": action,
            "timeline": [
                {
                    "status": status,
                    "label": status_label,
                    "action": action,
                    "at": now,
                }
            ],
        }

    @staticmethod
    def _parse_application_dt(app: dict[str, Any]) -> datetime:
        raw = app.get("date_updated") or app.get("date_applied") or ""
        if raw:
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                pass
        return datetime.min.replace(tzinfo=timezone.utc)

    def _sort_applications_recent(self, apps: list[dict]) -> list[dict]:
        return sorted(apps, key=self._parse_application_dt, reverse=True)

    def _enrich_applications(self, apps: list[dict]) -> list[dict]:
        """Add days_since_applied, days_since_update, needs_follow_up to each app dict."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = []
        for app in apps:
            enriched = dict(app)
            days_applied: int | None = None
            raw_applied = app.get("date_applied")
            if raw_applied:
                try:
                    dt = datetime.fromisoformat(raw_applied.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    days_applied = (now - dt).days
                except (ValueError, TypeError):
                    pass
            days_updated: int | None = None
            raw_updated = app.get("date_updated")
            if raw_updated:
                try:
                    dt = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    days_updated = (now - dt).days
                except (ValueError, TypeError):
                    pass
            enriched["days_since_applied"] = days_applied
            enriched["days_since_update"] = days_updated
            # Follow-up needed: applied/opened status with no update for 7+ days
            enriched["needs_follow_up"] = (
                app.get("status") in ("applied", "opened")
                and days_updated is not None
                and days_updated >= 7
            )
            enriched["status_label"] = self._application_status_label(app.get("status"))
            result.append(enriched)
        return result

    def _build_recent_context_message(self, ctx: dict[str, Any]) -> str:
        app = ctx.get("recent_application") if isinstance(ctx.get("recent_application"), dict) else {}
        job = app.get("title") or ctx.get("recent_job") or "Unknown"
        company = app.get("company") or ctx.get("recent_company") or "Unknown"
        status = app.get("status_label") or ctx.get("recent_status_label") or self._application_status_label(ctx.get("recent_status"))
        route = app.get("route") or ctx.get("recent_route") or "/command"
        action = app.get("last_action") or ctx.get("recent_action") or "tracked"
        updated_at = app.get("updated_at")

        time_hint = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - dt).days
                if days == 0:
                    time_hint = " Updated today."
                elif days > 0:
                    time_hint = f" Updated {days} day{'s' if days != 1 else ''} ago."
            except (TypeError, ValueError):
                pass

        next_step = "Next step: update the status when you get a reply."
        if (app.get("status") or ctx.get("recent_status")) == "applied":
            next_step = "Next step: follow up if there is no response after 7 days."
        elif (app.get("status") or ctx.get("recent_status")) == "saved":
            next_step = "Next step: review the role and mark it as applied when you submit."

        return (
            f"Your latest application context is **{job}** at **{company}**. "
            f"It is currently **{status}** from the last action: {action}.{time_hint} "
            f"{next_step}"
        )

    def _build_tracking_message(self, apps: list[dict], stats: dict) -> str:
        """Build an actionable prose summary of application pipeline state."""
        total = len(apps)
        if total == 0:
            return (
                "You have no tracked applications yet. "
                "When you apply to a job through Rico, I will track it here. "
                "You can also say 'mark as applied' on any job."
            )

        by_status: dict[str, list[dict]] = {}
        for app in apps:
            by_status.setdefault(app.get("status", "unknown"), []).append(app)

        offers = by_status.get("offer", [])
        interviews = by_status.get("interview", [])
        applied = by_status.get("applied", []) + by_status.get("opened", [])
        saved = by_status.get("saved", [])
        rejected = by_status.get("rejected", [])
        follow_up = [a for a in apps if a.get("needs_follow_up")]

        stage_parts = []
        if offers:
            stage_parts.append(f"{len(offers)} offer")
        if interviews:
            stage_parts.append(f"{len(interviews)} interview")
        if applied:
            stage_parts.append(f"{len(applied)} applied")
        if saved:
            stage_parts.append(f"{len(saved)} saved")
        if rejected:
            stage_parts.append(f"{len(rejected)} rejected")
        stage_line = ", ".join(stage_parts) if stage_parts else f"{total} tracked"

        sentences = [
            f"You have {total} tracked application{'s' if total != 1 else ''}: {stage_line}."
        ]

        active = offers + interviews
        if active:
            names = [
                f"**{a.get('title', 'Unknown')}** at **{a.get('company', 'Unknown')}**"
                for a in active[:3]
            ]
            sentences.append(f"Active: {', '.join(names)}.")

        if follow_up:
            fu_companies = [f"**{a.get('company', 'Unknown')}**" for a in follow_up[:3]]
            suffix = f" (+{len(follow_up) - 3} more)" if len(follow_up) > 3 else ""
            sentences.append(
                f"{len(follow_up)} application{'s' if len(follow_up) != 1 else ''} "
                f"may need a follow-up (no update in 7+ days): "
                f"{', '.join(fu_companies)}{suffix}."
            )

        sentences.append("Ask me to 'list my applications' any time to see the full list.")
        return " ".join(sentences)

    def _handle_subscription_plans(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Return Rico subscription plans and pricing."""
        # Try to get user's current plan from subscription repo
        try:
            from src.repositories.subscription_repo import get_subscription
            sub = get_subscription(user_id)
            current_plan = (sub.get("plan") or "free") if sub else "free"
        except Exception:
            current_plan = "free"

        plans_msg = (
            "Rico has two plans:\n"
            "• **Pro** — AED 29/month (unlimited AI chats, priority alerts, CV optimization)\n"
            "• **Premium** — AED 49/month (Pro + interview prep, cover letters, dedicated support)\n\n"
            "Subscribe at ricohunt.com/subscription or ask me for details."
        )
        return {
            "type": "subscription.show_plans",
            "message": plans_msg,
            "plans": [
                {"name": "Pro", "price_aed": 29, "period": "monthly"},
                {"name": "Premium", "price_aed": 49, "period": "monthly"},
            ],
            "current_plan": current_plan,
            "next_action": "choose_plan_or_continue",
            "options": [
                {"action": "subscription_pro_details", "label": "Tell me more about Pro", "message": "Tell me more about the Rico Pro plan"},
                {"action": "subscription_premium_details", "label": "Tell me more about Premium", "message": "Tell me more about the Rico Premium plan"},
                {"action": "subscription_how_to", "label": "How do I subscribe?", "message": "How do I subscribe to Rico Pro or Premium?"},
            ],
        }

    def _handle_learning_profile_summary(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Show the user what Rico has learned from their behavioral signals.

        Reads top preferences from LearningRepository and formats a plain-language
        summary so users can verify what Rico has inferred and correct mistakes.
        """
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            roles = [r for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
            locs = [loc for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
            skills = [s for s, _ in _lr.get_top_preferences(user_id, "skill", limit=6)]
            avoided = [
                c for c, w in _lr.get_top_preferences(user_id, "company", limit=5) if w < 0
            ]

            if not any([roles, locs, skills, avoided]):
                msg = (
                    "I haven't learned anything specific yet — I build your preference profile "
                    "from your actions. Save, apply, or skip jobs and I'll start personalising results."
                )
            else:
                lines = ["Here is what I've learned from your actions so far:\n"]
                if roles:
                    lines.append(f"**Preferred roles:** {', '.join(roles)}")
                if locs:
                    lines.append(f"**Preferred locations:** {', '.join(locs)}")
                if skills:
                    lines.append(f"**Relevant skills:** {', '.join(skills)}")
                if avoided:
                    lines.append(f"**Companies to avoid:** {', '.join(avoided)}")
                lines.append(
                    "\nThis shapes which jobs float to the top of your results. "
                    "Tell me if anything looks wrong and I'll correct it."
                )
                msg = "\n".join(lines)
        except Exception:
            msg = (
                "I couldn't retrieve your preference profile right now. "
                "Try again in a moment — your data is safe."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "learning_profile_summary", "message": msg}

    def _handle_preference_correction(
        self, user_id: str, message: str, profile: Any
    ) -> dict[str, Any]:
        """Remove a learned preference at the user's explicit request.

        Parses the message to extract what type of preference to clear and the
        value, then calls LearningRepository.clear_preference() which writes a
        durable veto signal and removes the key from the in-memory cache.
        """
        import re as _re

        _LOCATIONS = {
            "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
            "fujairah", "umm al quwain", "riyadh", "jeddah", "dammam",
            "doha", "kuwait", "muscat", "manama", "abu dhabi",
            "uae", "saudi arabia", "qatar", "bahrain", "oman",
        }

        msg_lower = message.lower()

        # Determine preference type
        pref_type = "role"
        if "skill" in msg_lower:
            pref_type = "skill"
        elif "company" in msg_lower or "employer" in msg_lower:
            pref_type = "company"
        else:
            for loc in _LOCATIONS:
                if loc in msg_lower:
                    pref_type = "location"
                    break

        # Extract the value: strip command words then take remaining text
        _STRIP = _re.compile(
            r"\b(forget|remove|clear|delete|drop|don.?t\s+want|not\s+interested\s+in"
            r"|my\s+preference\s+for|preference\s+for|preference|from\s+my\s+preferences"
            r"|انسَ|احذف|تفضيلي\s*ل?|لا\s+أريد\s+وظائف\s+في)\b",
            _re.IGNORECASE,
        )
        cleaned = _STRIP.sub("", message).strip(" .,،!؟?")
        # Remove leading filler words
        cleaned = _re.sub(
            r"^(for|about|in|at|ل|عن|في|that|this|the)\s+",
            "", cleaned, flags=_re.IGNORECASE,
        ).strip()
        # Collapse whitespace
        cleaned = _re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned or len(cleaned) < 2:
            reply = (
                "Please tell me what specific preference to remove — for example:\n"
                "- \"Forget my preference for Dubai\"\n"
                "- \"Remove Python from my skills\"\n"
                "- \"I don't want jobs in Abu Dhabi\""
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "preference_correction", "message": reply}

        try:
            from src.repositories.learning_repo import get_learning_repository
            get_learning_repository().clear_preference(user_id, pref_type, cleaned)
            _labels = {
                "role": "role preference",
                "location": "location preference",
                "skill": "skill",
                "company": "company",
            }
            label = _labels.get(pref_type, "preference")
            reply = (
                f"Done — I've removed **{cleaned}** from your {label} list. "
                "It won't influence your results anymore.\n\n"
                "If you change your mind, just save or apply to relevant jobs and I'll pick it up again."
            )
        except Exception:
            reply = (
                "I couldn't remove that preference right now. "
                "Please try again in a moment — your other data is safe."
            )

        self._append_chat(user_id, "assistant", reply)
        return {"type": "preference_correction", "message": reply}

    def _handle_application_insights(self, user_id: str) -> dict[str, Any]:
        """Analyze the user's tracked applications and surface success patterns.

        Calls ResponseIntelligenceEngine.analyze_response_patterns() on the user's
        application history and formats a plain-language insight summary.
        """
        try:
            from src.repositories.applications_repo import get_all
            apps = get_all(user_id=user_id) or []

            if len(apps) < 3:
                count = len(apps)
                noun = "application" if count == 1 else "applications"
                msg = (
                    f"You have {count} tracked {noun} so far. "
                    "Once you have a few more I'll be able to show you patterns — "
                    "success rate, how long employers typically respond, and where to focus."
                )
            else:
                from src.decision_engine import JobDecisionEngine
                from src.response_intelligence import (
                    JsonFileStateStore,
                    ResponseIntelligenceEngine,
                )
                from pathlib import Path

                _engine = ResponseIntelligenceEngine(
                    decision_engine=JobDecisionEngine(profile={}, target_roles=[]),
                    state_store=JsonFileStateStore(Path("data/scoring_adjustments.json")),
                )
                result = _engine.analyze_response_patterns(apps)

                if "error" in result:
                    msg = "I couldn't analyze your applications right now. Try again in a moment."
                else:
                    total = result["total_applications"]
                    success_pct = result["success_rate_pct"]
                    avg_days = result.get("avg_response_time_days", 0.0)
                    dist = result.get("response_distribution", {})
                    insights = result.get("insights", [])

                    lines = [f"**Application Analysis — {total} tracked applications**\n"]

                    status_parts = []
                    for status, count in sorted(dist.items(), key=lambda x: -x[1]):
                        if count > 0 and status != "no_response":
                            label = status.replace("_", " ").title()
                            status_parts.append(f"{label}: {count}")
                    if status_parts:
                        lines.append("**Outcomes:** " + " · ".join(status_parts))

                    lines.append(f"**Success rate:** {success_pct}%")
                    if avg_days > 0:
                        lines.append(f"**Avg employer response:** {avg_days:.0f} days")

                    if insights:
                        lines.append("")
                        for ins in insights[:3]:
                            lines.append(f"**Insight — {ins['insight_type'].replace('_', ' ').title()}**")
                            if ins.get("recommendation"):
                                lines.append(ins["recommendation"])

                    msg = "\n".join(lines)
        except Exception:
            msg = (
                "I couldn't load your application data right now. "
                "Try again in a moment."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "application_insights", "message": msg}

    def _handle_job_feedback_positive(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Record a positive learning signal when the user says a job is a great match.

        Calls infer_signals_from_job_action(..., "save", job) on the most recently
        shown job so role/location/company weights are boosted. Falls back to a
        generic positive signal when no recent job context is available.
        """
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
            if matches:
                top = matches[0]
                _lr.infer_signals_from_job_action(user_id, "save", top)
                title = top.get("title") or "that role"
                company = top.get("company") or ""
                label = f"**{title}**" + (f" at {company}" if company else "")
                msg = (
                    f"Great — {label} is marked as a strong match. "
                    "I'll prioritise similar roles in future searches."
                )
            else:
                _lr.record_signal(
                    user_id,
                    "feedback",
                    "positive_match",
                    signal_weight=0.6,
                    source="chat_feedback",
                    metadata={"message": message[:200]},
                )
                msg = "Glad to hear it! Tell me if you want to save it or prepare an application."
        except Exception:
            msg = "Great — I'll keep that in mind when searching for more roles."

        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_feedback", "message": msg}

    def _handle_job_feedback_negative(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Record a negative learning signal when the user says a job isn't suitable.

        Looks up the most recently shown job from context and calls
        infer_signals_from_job_action(..., "not_relevant", job) so role/location/company
        signals are updated with negative weights. Falls back to a generic signal when no
        recent job is in context. Never raises — a bare acknowledgement is returned on error.
        """
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
            if matches:
                top = matches[0]
                _lr.infer_signals_from_job_action(user_id, "not_relevant", top)
                title = top.get("title") or "that role"
                company = top.get("company") or ""
                label = f"**{title}**" + (f" at {company}" if company else "")
                msg = (
                    f"Noted — {label} isn't the right fit. "
                    "I'll use that to refine future recommendations."
                )
            else:
                _lr.record_signal(
                    user_id,
                    "feedback",
                    "negative_match",
                    signal_weight=-0.3,
                    source="chat_feedback",
                    metadata={"message": message[:200]},
                )
                msg = "Understood. Tell me what kind of role you're looking for and I'll find better matches."
        except Exception:
            msg = "Got it — I'll keep that in mind when searching for roles."

        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_feedback", "message": msg}

    def _handle_delegated_decision(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Handle 'you decide' / 'choose for me' by picking the strongest CV-aligned role."""
        has_cv = bool(profile and self._profile_value(profile, "cv_status") == "parsed")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))

        if has_cv and target_roles:
            chosen_role = target_roles[0]
            return {
                "type": "job_search_explicit",
                "message": (
                    f"Based on your CV, I'll proceed with the strongest match: **{chosen_role}**."
                    f" Searching live jobs now..."
                ),
                "chosen_role": chosen_role,
                "source": "delegated_cv_choice",
                "next_action": "search_jobs",
            }

        if target_roles:
            chosen_role = target_roles[0]
            return {
                "type": "job_search_explicit",
                "message": (
                    f"I'll proceed with your target role: **{chosen_role}**."
                    f" Searching live jobs now..."
                ),
                "chosen_role": chosen_role,
                "source": "delegated_target_role_choice",
                "next_action": "search_jobs",
            }

        return {
            "type": "clarification",
            "message": (
                "I'd be happy to choose for you, but I need more context first. "
                "Upload your CV or tell me your target role and preferred city."
            ),
            "next_action": "need_profile_for_delegation",
        }

    def _handle_post_cv_continuation(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Handle 'keep going / كمل / continue' after CV upload or profile-building.

        Priority:
        1. Profile has target_roles → search with the first one.
        2. Profile has CV → suggest roles and ask user to choose.
        3. No context → ask one concise question.
        """
        has_cv = bool(profile and self._profile_value(profile, "cv_status") == "parsed")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))

        if target_roles:
            chosen_role = target_roles[0]
            return self._classified_role_search(user_id, chosen_role, profile)

        if has_cv:
            return self._handle_profile_role_suggestions(profile)

        clarification = "What role should I search for first?"
        self._append_chat(user_id, "assistant", clarification)
        return {
            "type": "clarification",
            "intent": "search_jobs",
            "message": clarification,
        }

    def _handle_cv_creation(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Start the no-CV profile builder / CV draft flow."""
        name = self._profile_value(profile, "name") or ""
        if name:
            greeting = f"Hi {name},"
        else:
            greeting = "Hi there,"
        self._set_flow_state(user_id, "cv_builder")
        return {
            "type": "cv_creation",
            "message": (
                f"{greeting} I can help you build a CV from scratch. "
                "Tell me your:\n"
                "• Current or most recent job title\n"
                "• Years of experience\n"
                "• Key skills and certifications\n"
                "• Preferred industries and cities\n\n"
                "Or paste any existing work history and I'll format it into a proper CV."
            ),
            "next_action": "collect_cv_fields",
            "fields_needed": ["current_role", "years_experience", "skills", "industries", "preferred_cities"],
        }

    def _handle_cv_generate_from_profile(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Generate a professional CV draft from the user's already-parsed profile.

        Uses extracted fields: name, email, phone, skills, experience, target roles,
        certifications, preferred cities. Asks only for genuinely missing fields.
        """
        if not self._has_cv_profile(profile):
            # No parsed profile — redirect to upload or manual creation
            return {
                "type": "cv_creation",
                "message": (
                    "I don't have your CV data yet. "
                    "Please upload your CV (PDF or Word) and I'll use it to build a new one, "
                    "or tell me your work history and I'll format it for you."
                ),
                "next_action": "upload_cv",
            }

        name = self._profile_value(profile, "name") or ""
        email = self._profile_value(profile, "email") or ""
        phone = self._profile_value(profile, "phone") or ""
        skills = self._as_list(self._profile_value(profile, "skills"))
        years_exp = self._profile_value(profile, "years_experience")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        certifications = self._as_list(self._profile_value(profile, "certifications"))
        preferred_cities = self._as_list(self._profile_value(profile, "preferred_cities"))
        industries = self._as_list(self._profile_value(profile, "industries"))
        current_role = self._profile_value(profile, "current_role") or (target_roles[0] if target_roles else "")

        # Pull extended parsed-CV fields to check what sections are actually stored
        work_experience = self._as_list(self._profile_value(profile, "work_experience"))
        education = self._as_list(self._profile_value(profile, "education"))

        # Identify genuinely missing fields that would improve the CV
        missing: list[str] = []
        if not current_role:
            missing.append("current or most recent job title")
        if years_exp is None:
            missing.append("years of experience")
        if not skills:
            missing.append("key skills and certifications")
        if not preferred_cities:
            missing.append("preferred cities (e.g. Dubai, Abu Dhabi)")

        # Sections absent from parsed CV — do not generate placeholders for these
        unparsed_sections: list[str] = []
        if not work_experience:
            unparsed_sections.append("Work Experience")
        if not education:
            unparsed_sections.append("Education")

        # If cities are missing, store pending field so the next reply is captured
        if not preferred_cities:
            ctx = self._get_recent_context(user_id)
            ctx["_pending_field"] = "preferred_cities"
            ctx["_pending_cv_generate"] = True
            self._store_recent_context(user_id, ctx)

        # Build the CV draft from extracted data only — no placeholders
        sections: list[str] = []

        header_parts = [name] if name else []
        contact_parts = [p for p in [email, phone] if p]
        if contact_parts:
            header_parts.append(" | ".join(contact_parts))
        if preferred_cities:
            header_parts.append(", ".join(preferred_cities[:2]))
        if header_parts:
            sections.append("\n".join(header_parts))

        if current_role or years_exp is not None:
            summary_parts: list[str] = []
            if current_role:
                summary_parts.append(current_role)
            if years_exp is not None:
                summary_parts.append(f"{years_exp} years of experience")
            if industries:
                summary_parts.append(f"in {', '.join(industries[:2])}")
            sections.append("**Professional Summary**\n" + " · ".join(summary_parts))

        if skills:
            sections.append("**Key Skills**\n" + " · ".join(skills[:12]))

        if certifications:
            sections.append("**Certifications**\n" + "\n".join(f"• {c}" for c in certifications[:6]))

        if target_roles:
            sections.append("**Target Roles**\n" + " · ".join(target_roles[:4]))

        cv_draft = "\n\n".join(sections)

        greeting = f"Here is your CV draft, {name}:" if name else "Here is your CV draft:"

        if missing:
            missing_note = (
                "\n\n**To complete the CV I still need:**\n"
                + "\n".join(f"• {f}" for f in missing)
                + "\n\nReply with these details and I'll add them."
            )
        elif unparsed_sections:
            # Profile is present but parsed CV lacks full sections — be honest
            missing_note = (
                "\n\n**Sections not yet available from your parsed CV:** "
                + ", ".join(unparsed_sections)
                + ".\n\nTo add these, upload your CV file (PDF or Word) "
                "or paste your work history and I'll format it."
            )
        else:
            missing_note = (
                "\n\nAll available profile sections are included. "
                "Tell me if you'd like to tailor this CV for a specific role."
            )

        message = f"{greeting}\n\n---\n\n{cv_draft}\n\n---{missing_note}"
        self._append_chat(user_id, "assistant", message)
        self._set_flow_state(user_id, "cv_builder")
        return {
            "type": "cv_draft",
            "message": message,
            "cv_draft": cv_draft,
            "missing_fields": missing,
            "unparsed_sections": unparsed_sections,
            "next_action": "collect_missing_cv_fields" if missing else "cv_ready",
        }

    def _handle_application_tracking(self, user_id: str, intent: str = "application_tracking") -> dict[str, Any]:
        """Route application tracking requests to the applications repository."""
        try:
            from src.repositories.applications_repo import get_all, get_stats
            apps = get_all(user_id=user_id)
            stats = get_stats(user_id=user_id)
        except Exception:
            # Fallback to legacy file-based store
            from src.applications import get_applied_jobs, get_application_stats
            apps = get_applied_jobs()
            stats = get_application_stats()

        enriched = self._enrich_applications(self._sort_applications_recent(apps))
        follow_up_needed = [a for a in enriched if a.get("needs_follow_up")]
        msg = self._build_tracking_message(enriched, stats)
        if enriched:
            latest = enriched[0]
            self._store_recent_context(
                user_id,
                self._build_recent_application_context(
                    title=latest.get("title") or "Unknown",
                    company=latest.get("company") or "Unknown",
                    status=latest.get("status") or "tracked",
                    action="application_tracking",
                    job_id=latest.get("job_id"),
                    link=latest.get("link"),
                ),
            )
        # Store lifecycle context so "list them" after a summary shows applied jobs.
        self._store_lifecycle_context(user_id, "lifecycle_show_applied")
        # Cache the enriched apps so "list them" can replay without querying migration-022 columns.
        try:
            self.memory.set_context(user_id, "cached_application_list", {
                "apps": enriched[:20],
                "stats": stats,
            })
        except Exception:
            pass
        return {
            "type": "application_status",
            "message": msg,
            "applications": enriched,
            "stats": stats,
            "follow_up_needed": follow_up_needed,
        }

    def _handle_lifecycle_query(self, user_id: str, query_type: str) -> dict[str, Any]:
        """Answer funnel-memory questions from user_job_context.

        Handles three Rico chat questions:
          - lifecycle_show_saved            → "show saved jobs"
          - lifecycle_show_applied          → "what jobs did I apply to?"
          - lifecycle_show_opened_not_applied → "show jobs I opened but did not apply to"
        """
        from src.repositories.user_job_context_repo import (
            get_by_status,
            get_opened_not_applied,
        )

        if query_type == "lifecycle_show_saved":
            rows = get_by_status(user_id, "saved")
            label = "saved"
            empty_msg = "You haven't saved any jobs yet. When you save a job from Rico, it'll appear here."
        elif query_type == "lifecycle_show_applied":
            rows = get_by_status(user_id, "applied")
            label = "applied"
            empty_msg = "I don't have any jobs marked as applied yet. After you apply, hit 'Mark as applied' so Rico can track it."
        else:  # lifecycle_show_opened_not_applied
            rows = get_opened_not_applied(user_id)
            label = "opened but not applied"
            empty_msg = "No jobs in that bucket yet — these are jobs where you clicked the apply link but haven't marked as applied."

        # Always remember the last lifecycle query so "list them" can replay it.
        self._store_lifecycle_context(user_id, query_type)

        # Fallback: if the lifecycle table returned nothing (e.g. migration 022 not yet applied),
        # try the in-memory cache written by _handle_application_tracking so "list them" after
        # an application summary still returns the correct list without needing new DB columns.
        if not rows and query_type == "lifecycle_show_applied":
            try:
                cached = self.memory.get_context(user_id, "cached_application_list") or {}
                cached_apps = cached.get("apps") or []
                if cached_apps:
                    rows = [
                        {
                            "title": a.get("title") or "",
                            "company": a.get("company") or "",
                            "apply_url": a.get("link") or a.get("apply_url") or "",
                            "source_url": a.get("source_url") or "",
                            "status": a.get("status") or "applied",
                        }
                        for a in cached_apps
                    ]
            except Exception:
                pass

        if not rows:
            return {
                "type": "lifecycle_query",
                "intent": query_type,
                "message": empty_msg,
                "jobs": [],
                "count": 0,
            }

        lines = [f"Here are your **{label}** jobs ({len(rows)}):\n"]
        for r in rows[:20]:
            title = r.get("title") or "Unknown Role"
            company = r.get("company") or "Unknown Company"
            url = r.get("apply_url") or r.get("source_url") or ""
            link_part = f" — [Apply]({url})" if url else ""
            lines.append(f"• **{title}** at {company}{link_part}")

        return {
            "type": "lifecycle_query",
            "intent": query_type,
            "message": "\n".join(lines),
            "jobs": rows[:20],
            "count": len(rows),
        }

    def _handle_profile_role_suggestions(self, profile: Any) -> dict[str, Any]:
        """Generate deterministic role suggestions based on CV skills/certifications.

        Fast path: no OpenAI, no job search, just profile data → role mapping.
        """
        if not profile:
            return {
                "type": "profile_role_suggestions",
                "message": "I need your CV or profile data to suggest roles. Upload your CV first.",
                "options": [],
                "next_action": "upload_cv"
            }

        # Extract profile data
        skills = self._as_list(self._profile_value(profile, "skills"))
        certifications = self._as_list(self._profile_value(profile, "certifications"))
        years_experience = self._profile_value(profile, "years_experience")
        industries = self._as_list(self._profile_value(profile, "industries"))
        current_role = self._profile_value(profile, "current_role")

        suggestions = self._generate_role_suggestions(
            skills, certifications, years_experience, industries, current_role
        )

        if not suggestions:
            # Weak/empty profile — prompt user to add skills or upload CV
            return {
                "type": "profile_role_suggestions",
                "message": (
                    "I need a bit more information to suggest the right roles for you. "
                    "Add your skills or upload your CV to get started."
                ),
                "options": [],
                "next_action": "add_skills",
            }

        return {
            "type": "profile_role_suggestions",
            "message": (
                f"Based on your CV, here are {len(suggestions)} roles that match your background. "
                "Choose one to start searching:"
            ),
            "options": suggestions,
            "next_action": "select_role_to_search",
        }

    def _handle_no_results_recovery(
        self,
        user_id: str,
        profile: Any,
        searched_roles: list[str],
    ) -> dict[str, Any]:
        """Return structured role-broadening options when live search returns no matches."""
        suggestions = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        searched_lower = {r.lower() for r in searched_roles}
        alt_options = [
            {"action": "search_role", "label": s["label"], "reason": s.get("reason", "")}
            for s in suggestions
            if s["label"].lower() not in searched_lower
        ][:5]

        if searched_roles:
            alt_options.append({
                "action": "broaden_search",
                "label": f"Broaden search for {searched_roles[0]}",
                "message": f"find {searched_roles[0]} jobs in UAE",
            })
        alt_options.append({
            "action": "show_all_suggestions",
            "label": "Show more roles from my CV",
            "message": "show roles from my cv",
        })

        searched_label = ", ".join(searched_roles[:2]) if searched_roles else "your target role"
        return {
            "type": "no_results_recovery",
            "message": (
                f"No live UAE matches found for **{searched_label}** right now. "
                "Here are related roles from your CV that may have active openings:"
            ),
            "options": alt_options,
            "next_action": "select_role_to_search",
        }

    def _generate_role_suggestions(
        self,
        skills: list[str],
        certifications: list[str],
        years_experience: float | None,
        industries: list[str],
        current_role: str | None = None,
    ) -> list[dict[str, str]]:
        """Delegate to the standalone role suggester and adapt to label-keyed list."""
        result = _suggest_roles(
            skills=skills,
            certifications=certifications,
            years_experience=years_experience,
            industries=industries,
            current_role=current_role,
        )
        return [
            {"action": r["title"], "label": r["title"], "reason": r.get("reason", "")}
            for r in result.get("roles", [])
        ]

    def _classified_role_search(self, user_id: str, role_text: str, profile: Any) -> dict[str, Any]:
        """Use 3-tier role classifier before searching.

        - profile_relevant → search directly
        - known_but_off_profile → ask confirmation
        - unknown → clarify / redirect

        Roles that Rico itself suggested (from role_suggester) are treated as
        profile_relevant without running them through the taxonomy classifier,
        because they are already derived from the user's CV.
        """
        # Location guard: if role_text is just a location (UAE, Dubai, etc.) redirect to
        # profile-based search rather than returning a misleading "I don't recognise X as a role".
        role_tokens = role_text.strip().lower().split()
        _loc_fillers = {"jobs", "job", "roles", "role", "in", "the", "a", "an", "for"}
        if role_tokens and all(t in _LOCATION_TERMS or t in _loc_fillers for t in role_tokens):
            saved_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if saved_roles:
                return self._target_role_search_response(user_id, str(saved_roles[0]), profile)
            response = {
                "type": "clarification",
                "message": (
                    f"I can search for jobs in the UAE. "
                    "What role are you looking for? (e.g. HSE Manager, Project Engineer, Finance Analyst)"
                ),
                "options": [{"action": "upload_cv", "label": "Upload CV to auto-detect role"}],
            }
            self._append_chat(user_id, "assistant", response["message"])
            return response

        # Self-reference guard: "my target role / my saved role / دوري المستهدف" etc.
        # Resolve to the user's saved profile roles instead of treating the phrase as a job title.
        if RicoChatAPI._SELF_REF_ROLE_RE.match(role_text.strip()):
            saved_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if not saved_roles:
                response = {
                    "type": "clarification",
                    "message": (
                        "I don't have a saved target role on your profile yet. "
                        "Tell me your target role (e.g. 'HSE Manager') or upload your CV and I'll set it for you."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return response
            return self._target_role_search_response(
                user_id, str(saved_roles[0]), profile, from_saved_profile=True
            )

        from rapidfuzz import fuzz as _fuzz

        # Roles already in the user's target_roles are always profile_relevant.
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role_lower = role_text.strip().lower()
        if self._is_broad_manager_role(role_text):
            return self._broad_manager_clarification(user_id)

        for tr in target_roles:
            if _fuzz.ratio(role_lower, str(tr).lower()) >= 70:
                return self._target_role_search_response(user_id, role_text.strip(), profile)

        # Rico's own suggestions are always profile_relevant — they came from the CV.
        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        suggested_lower = {s["label"].lower() for s in suggested}
        if role_lower in suggested_lower:
            return self._target_role_search_response(user_id, role_text.strip(), profile)

        classification, canonical_role = classify_role_candidate(role_text, profile)

        if classification == "profile_relevant" and canonical_role:
            return self._target_role_search_response(user_id, canonical_role, profile)

        if classification == "known_but_off_profile" and canonical_role:
            response = {
                "type": "clarification",
                "message": (
                    f"'{canonical_role}' is a real role, but it does not look close to your CV profile. "
                    f"Should I search for {canonical_role} jobs anyway? Reply YES or tell me a different role."
                ),
                "options": [
                    {"action": "confirm_search", "label": f"Yes, search {canonical_role}"},
                    {"action": "show_profile_roles", "label": "Show roles from my CV"},
                ],
            }
            self._append_chat(user_id, "assistant", response["message"])
            try:
                _ctx = self._get_recent_context(user_id)
                _ctx["_pending_role_confirmation"] = {"role": canonical_role}
                self._store_recent_context(user_id, _ctx)
            except Exception:
                pass
            return response

        # unknown role
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        suggestion = ""
        if target_roles:
            suggestion = f" Based on your CV, I can search for: {', '.join(str(r) for r in target_roles[:3])}."
        response = {
            "type": "clarification",
            "message": (
                f"I do not recognize '{role_text}' as a job role.{suggestion} "
                "Try a specific role title, or say 'help' for options."
            ),
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _get_recent_messages(self, user_id: str, limit: int = MAX_CONTEXT_MESSAGES) -> list[dict[str, str]]:
        """Get recent messages for context, respecting token limits.

        Prefers DB-backed chat history for authenticated users, falls back to memory.
        Messages are sanitized before return: only user/assistant roles are kept and
        any message whose content matches known pipeline-generated artifacts is dropped
        so generated drafts can never be fed back to the LLM as user statements.
        """
        raw: list[dict] = []
        try:
            # Try DB-backed history first (primary for authenticated users)
            from src.services.chat_service import get_chat_history
            db_messages = get_chat_history(user_id, limit=limit)
            if db_messages:
                raw = db_messages[-limit:] if len(db_messages) > limit else db_messages
        except Exception as e:
            logger.warning("Failed to get recent messages from DB, falling back to memory",
                         extra={"user_id": user_id, "error": str(e)}, exc_info=True)

        if not raw:
            # Fallback to memory store (JSON-backed local storage)
            try:
                messages = self.memory.get_chat_messages(user_id, limit=limit)
                raw = messages[-limit:] if len(messages) > limit else messages
            except Exception as e:
                logger.warning("Failed to get recent messages from memory",
                             extra={"user_id": user_id, "error": str(e)}, exc_info=True)
                return []

        return _sanitize_history_for_llm(raw)

    def _get_blocked_questions(self, profile: Any) -> list[str]:
        """Return list of question types that should not be asked based on profile data."""
        blocked = []
        if profile is None:
            return blocked

        has_cv = bool(
            self._profile_value(profile, "cv_filename")
            or self._profile_value(profile, "cv_status") == "parsed"
        )

        # Check for years_experience (explicit value or any CV upload)
        if self._profile_value(profile, "years_experience") or has_cv:
            blocked.append("experience")

        # Check for preferred_cities
        if self._profile_value(profile, "preferred_cities") or self._profile_value(profile, "cities"):
            blocked.append("location")

        # Check for skills or industries
        skills = self._profile_value(profile, "skills")
        if (skills and len(skills) > 0) or self._profile_value(profile, "industries"):
            blocked.append("industry")

        return blocked

    @staticmethod
    def _contains_blocked_question_pattern(text: str, blocked_questions: list[str]) -> bool:
        lower_text = text.lower()
        for blocked in blocked_questions:
            if blocked == "experience" and any(pattern in lower_text for pattern in [
                "experience level", "years experience", "years of experience",
                "how many years", "how much experience", "entry/mid/senior",
                "experience?", "your experience"
            ]):
                return True
            if blocked == "location" and any(pattern in lower_text for pattern in [
                "location", "city", "where", "uae city", "preferred city",
                "which city", "where are you", "where do you want"
            ]):
                return True
            if blocked == "industry" and any(pattern in lower_text for pattern in [
                "industry", "sector", "field", "which industry", "what industry"
            ]):
                return True
        return False

    def _remove_blocked_questions(self, response: str, blocked_questions: list[str]) -> str:
        """Remove lines that only ask for profile facts we already know."""
        if not response or not blocked_questions:
            return response

        filtered_lines = []
        for line in response.split("\n"):
            if self._contains_blocked_question_pattern(line, blocked_questions):
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()

    def _remove_blocked_question_sentences(self, response: str, blocked_questions: list[str]) -> str:
        """Prefer sentence-level cleanup before falling back to the raw provider reply."""
        if not response or not blocked_questions:
            return response

        fragments = re.split(r"(?<=[.!?])\s+", response.strip())
        kept_fragments = []
        for fragment in fragments:
            trimmed = fragment.strip()
            if not trimmed:
                continue
            if trimmed.endswith("?") and self._contains_blocked_question_pattern(trimmed, blocked_questions):
                continue
            kept_fragments.append(trimmed)

        return " ".join(kept_fragments).strip()

    def _preserve_ai_message(self, response: str, blocked_questions: list[str]) -> str:
        """Never discard a non-empty provider reply just because the broad filter removed it."""
        raw_message = str(response or "").strip()
        if not raw_message:
            return raw_message

        filtered_message = self._remove_blocked_questions(raw_message, blocked_questions)
        if filtered_message:
            return filtered_message

        minimally_filtered = self._remove_blocked_question_sentences(raw_message, blocked_questions)
        if minimally_filtered:
            logger.warning(
                "rico_ai_response_line_filter_empty_using_sentence_fallback blocked=%s",
                blocked_questions,
            )
            return minimally_filtered

        logger.warning(
            "rico_ai_response_filter_empty_using_raw_fallback blocked=%s",
            blocked_questions,
        )
        return raw_message

    @staticmethod
    def _build_router_context(user_id: str, profile: Any) -> dict:
        """Build the context dict passed to the intent router."""
        ctx: dict = {}
        if profile:
            try:
                ctx["profile"] = asdict(profile) if is_dataclass(profile) else dict(profile)
            except Exception as e:
                logger.warning("Failed to build router context", extra={"user_id": user_id, "error": str(e)})
        return ctx


def demo() -> None:
    """Demo function for testing the chat API."""
    api = RicoChatAPI()

    messages: list[str] = [
        "Roben_Edwan_CV.pdf here u go",
        "take it from the c.v!",
        "Please skip this question.",
        "I need HSE Manager jobs in Dubai",
        "Find jobs for me",
        "Prepare me for interview",
    ]

    for message in messages:
        print("USER:", message)
        print("RICO:")
        print(json.dumps(api.process_message("demo-user", message), indent=2))
        print("-" * 80)


if __name__ == "__main__":
    demo()
