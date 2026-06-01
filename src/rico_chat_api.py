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
# Telegram username: @handle (5–32 chars, alphanumeric + underscore)
TELEGRAM_HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
# Telegram declaration in natural language: "my telegram is @handle", "@handle" etc.
TELEGRAM_MENTION_RE = re.compile(
    r"(?:my\s+)?telegram(?:\s+(?:username|handle|id|account|is|:))?\s+(?:is\s+)?(@[A-Za-z0-9_]{5,32})"
    r"|(?:^|\s)(@[A-Za-z0-9_]{5,32})(?:\s|$)",
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
})
_QUESTION_CHARS: frozenset[str] = frozenset("?？!！;:")
_MAX_ROLE_WORDS: int = 6
_MIN_TOKEN_ALPHA: int = 2

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

    def _append_chat(self, user_id: str, role: str, message: str | dict[str, Any]) -> None:
        """Append chat message to memory (sync) and DB (async fire-and-forget).

        Memory write is synchronous so subsequent reads see the message immediately.
        DB write is dispatched to a background thread to avoid blocking the request
        path on remote PostgreSQL latency (~1s round-trip on Neon).
        """
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
                "email", "phone", "skills", "years_experience",
                "preferred_cities", "target_roles", "industries",
                "salary_expectation_aed", "deal_breakers"
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
    def _looks_like_bare_target_role(message: str) -> bool:
        """Accept only short noun-phrase job titles, not questions or commands."""
        text = (message or "").strip()
        if not text:
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

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        """Convert value to list if not already."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

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

        top_matches = all_matches[:5]
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

        raw_score = m.get("rico_score") or m.get("score") or 0
        # Normalize to [0.0, 1.0] — frontend multiplies by 100 for display.
        # Legacy scoring pipeline (scoring.py) emits 0–100 integers; FitScore
        # (scorer.py) already emits 0.0–1.0 floats. Values > 1 are divided by 100.
        if raw_score:
            _s = float(raw_score)
            normalized_score = round(max(0.0, min(1.0, _s / 100.0 if _s > 1.0 else _s)), 4)
        else:
            normalized_score = 0.0

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
            from src.services.source_quality import classify_url, is_google_intermediary
            if apply_url and is_google_intermediary(apply_url):
                if not alt_link:
                    alt_link = apply_url
                apply_url = ""
                verification_status = "google_intermediary"
            else:
                verification_status = classify_url(apply_url or source_url)
        except Exception:
            verification_status = "needs_source_verification" if apply_url else "lead_needs_verification"

        result = {
            "title": str(m.get("title") or "Untitled role"),
            "company": str(m.get("company") or "Unknown company"),
            "score": normalized_score,
            "apply_url": apply_url,
            "source_url": source_url,
            "alt_link": alt_link,
            "verification_status": verification_status,
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

    def _looks_like_cv_upload(self, message: str) -> bool:
        lower = message.lower()
        return bool(CV_FILE_RE.search(message)) or any(
            phrase in lower
            for phrase in [
                "uploaded cv",
                "upload cv",
                "uploaded resume",
                "upload resume",
                "my cv",
                "my resume",
                "resume attached",
                "cv attached",
            ]
        )

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
                f"I received {filename}. I will use the CV-first profile flow: extract every available detail "
                "from the CV, pre-fill the career profile, and only ask for anything missing or unclear. "
                "I will not run the long manual question-by-question form."
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
    def _is_negative(message: str) -> bool:
        """True for no/لا single-word negatives."""
        text = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return text in RicoChatAPI._NEGATIVE_PHRASES

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
        )
        application_angle_signals = (
            "application angle" in last or "cover letter" in last or "tailor" in last
            or "زاوية تقديم" in last
        )
        reminder_signals = (
            "reminder" in last or "follow up" in last or "تذكير" in last
        )

        if cv_improve_signals:
            return self._answer_with_ai_fallback(
                user_id=user_id,
                message="Give me specific CV improvement suggestions based on my profile and target roles.",
                profile=profile,
                save_user_message=False,
            )
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
    }

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
    @staticmethod
    def _search_jsearch_meta(role: str) -> Any:
        """Query JSearch for live UAE jobs matching *role*, with cache + retry.

        Returns a ``jsearch_client.FetchResult`` so the caller can tell a genuine
        empty result apart from a rate-limited source. Never raises.
        """
        from src import jsearch_client

        result = jsearch_client.search(f"{role} UAE")
        # Stamp a default score so downstream scoring/formatting works unchanged.
        for job in result.items:
            job.setdefault("score", 50)
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
        try:
            fetch = self._search_jsearch_meta(search_role)
            all_matches = fetch.items
            rate_limited = fetch.rate_limited
            if not all_matches:
                search_profile = (
                    _dc_replace(profile, target_roles=[search_role])
                    if is_dataclass(profile)
                    else profile
                )
                workflow_result = self.system.run_for_profile(search_profile)
                all_matches = workflow_result.get("matches", [])
        except Exception as exc:
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

        # Quality-sort: surface live/verified sources before aggregators/dead links.
        _QUALITY_RANK: dict[str, int] = {
            "live_verified": 0,
            "needs_source_verification": 1,
            "google_intermediary": 2,
            "login_required": 3,
            "rate_limited": 4,
            "aggregator_untrusted": 5,
        }
        try:
            from src.services.source_quality import classify_url as _cq, is_google_intermediary as _igi

            def _quality_key(m: dict[str, Any]) -> int:
                url = str(
                    m.get("job_apply_link") or m.get("apply_link") or m.get("link") or ""
                )
                status = "google_intermediary" if _igi(url) else _cq(url)
                return _QUALITY_RANK.get(status, 1)

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
            live_count = sum(1 for m in top_matches if _has_url(m))
            lead_count = len(top_matches) - live_count
            if live_count and lead_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {live_count} current live match(es) and {lead_count} lead(s) that need verification."
                )
            elif live_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {live_count} current live match(es)."
                )
            else:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {lead_count} lead(s) that need verification."
                )
        else:
            base_message = f"Got it — I will target {normalized_role} roles{city_text}{basis_text}."

        if role_intelligence_data and role_intelligence_data.get("fit_score", 1.0) < 0.6:
            adjacent = role_intelligence_data.get("adjacent_roles", [])
            role_names = [r["role"] for r in adjacent[:3]]
            base_message += f" Your CV is also strong for {', '.join(role_names)} roles. I'll search those too if needed."
        elif not top_matches:
            base_message += " No live matches found right now. I've saved this as your target role — you can run this search again anytime."

        return prefix + base_message

    def process_message(
        self,
        user_id: str,
        message: str,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        debug_id = _generate_debug_id()
        self._current_operation_id = operation_id
        try:
            result = self._process_message_inner(user_id, message)
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
    ) -> dict[str, Any]:
        """Run the single conversational AI fallback path used by chat routing."""
        if save_user_message:
            self._append_chat(user_id, "user", message)
        user_context = self._build_openai_context(profile, user_id=user_id)
        blocked_questions = self._get_blocked_questions(profile)
        if isinstance(user_context, dict):
            user_context["blocked_questions"] = blocked_questions

        ai_response = self._get_openai_agent().respond(message, user_context=user_context)
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

    def answer_conversationally(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Route directly to the existing conversational AI fallback path."""
        debug_id = _generate_debug_id()
        try:
            result = self._answer_with_ai_fallback(
                user_id=user_id,
                message=message,
                profile=profile,
                save_user_message=True,
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

    def _process_message_inner(self, user_id: str, message: str) -> dict[str, Any]:
        self._append_chat(user_id, "user", message)
        completed = is_onboarding_complete(user_id)

        if completed:
            return self._handle_active_user(user_id, message)

        if self._looks_like_cv_upload(message):
            mark_onboarding_complete(user_id)
            return self._finalize(
                self._cv_first_profile_response(user_id, message),
                self.SOURCE_KEYWORD,
                profile=None,
            )

        profile = get_profile(user_id)
        if profile is None:
            if getattr(self, "_persist", True):
                upsert_profile(user_id=user_id, updates={"name": user_id})
                set_onboarding_status(user_id, ONBOARDING_IN_PROGRESS)
            response = {
                "type": "onboarding",
                "message": (
                    "Welcome to Rico AI. Upload your CV or tell me your target role, UAE city "
                    "preferences, and salary expectations. If you upload a CV, I will pre-fill "
                    "the profile and only ask for anything missing or unclear."
                ),
            }
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

        # ── Pending field resolver (must run first) ───────────────────────────
        # When Rico has just asked the user for a specific profile field (e.g.
        # "What's your Telegram username?"), the raw value the user sends next
        # (like "@Robin_amg") won't match any intent. Intercept it here so the
        # field is saved and a correct confirmation is returned without falling
        # through to the unknown/fallback handler.
        pending_field_result = self._resolve_pending_field(user_id, message, profile)
        if pending_field_result is not None:
            return self._finalize(pending_field_result, self.SOURCE_KEYWORD, profile=profile)

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
        # Must run before generic routing so "نعم" resolves the last offered action
        # instead of falling through to a generic action card.
        if self._is_affirmative(message):
            pending = self._resolve_pending_intent(user_id, message, profile)
            if pending is not None:
                return self._finalize(pending, self.SOURCE_KEYWORD, profile=profile)
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
        _profile_target_roles = self._as_list(self._profile_value(profile, "target_roles"))
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

        # CV creation — user asks to create a CV (no existing CV)
        if legacy_intent == "cv_create":
            return self._finalize(
                self._handle_cv_creation(user_id, profile),
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
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
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

            # Fall through to legacy router for entity extraction
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)

            # Check if profile has target role before running job search
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if not target_roles:
                if has_cv:
                    # CV present but no confirmed target role → suggest roles from skills
                    return self._finalize(
                        self._handle_profile_role_suggestions(profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                response = {
                    "type": "profile_incomplete",
                    "intent": "search_jobs",
                    "message": (
                        "I can search jobs using your profile. Please confirm:\n"
                        "• Target role (e.g., HSE Manager, ESG Specialist)\n"
                        "• Preferred city (e.g., Dubai, Abu Dhabi)\n"
                        "• Expected salary (optional)\n\n"
                        "I cannot search for jobs until at least your target role is known."
                    ),
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
            top_matches = all_explicit[:5]
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
            title = getattr(intent_result, "extracted_title", None) or "the role"
            company = getattr(intent_result, "extracted_company", None) or "the company"
            profile_skills = self._as_list(self._profile_value(profile, "skills"))
            profile_roles = self._as_list(self._profile_value(profile, "target_roles"))

            # Persist to Application Flow so prepared state survives session/restart
            self._persist_application_lifecycle_event(
                user_id=user_id,
                title=title,
                company=company,
                status="prepared",
            )

            self._store_recent_context(
                user_id,
                self._build_recent_application_context(
                    title=title,
                    company=company,
                    status="prepared",
                    action="prepare_application",
                ),
            )

            context_parts: list[str] = []
            if profile_skills:
                context_parts.append(f"Skills: {', '.join(str(s) for s in profile_skills[:8])}")
            if profile_roles:
                context_parts.append(f"Target roles: {', '.join(str(r) for r in profile_roles[:3])}")
            context_str = ". ".join(context_parts) + ("." if context_parts else "")

            system_prompt = (
                "You are Rico, a UAE career intelligence system. "
                "The user wants to prepare an application for a specific job. "
                "Give a concise application angle: what from their background aligns, "
                "what to lead with in their CV and cover note, and any key gap to address. "
                "Keep it under 200 words."
            )
            ai_input = f"Prepare application for {title} at {company}. {context_str}"
            ai_text = None
            if hf_ok():
                ai_text = generate_text(ai_input, system=system_prompt, max_new_tokens=400)

            if ai_text:
                msg = ai_text
                src = self.SOURCE_HF
            else:
                skills_str = (
                    ", ".join(str(s) for s in profile_skills[:4])
                    if profile_skills else "your documented skills"
                )
                msg = (
                    f"**{title} at {company}**\n\n"
                    f"Lead with: {skills_str}\n\n"
                    f"Angle: position your experience directly against this role. "
                    f"Research {company} and reference specific work in your cover note.\n\n"
                    f"Upload your CV for a full gap analysis against this role."
                )
                src = self.SOURCE_FALLBACK

            response = {
                "type": "prepare_application",
                "intent": "prepare_application",
                "message": msg,
                "options": [
                    {"action": "open_apply_link", "label": "Open apply link",
                     "message": f"open apply link for {title} at {company}"},
                    {"action": "track_job", "label": "Track this job",
                     "message": f"Track this job — {title} at {company}"},
                    {"action": "mark_applied", "label": "Mark as applied",
                     "message": f"Mark as applied — {title} at {company}"},
                    {"action": "save_job", "label": "Save job",
                     "message": f"Save job — {title} at {company}"},
                ],
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, src, profile=profile)

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
                _create_manual_app(title=title, company=company, status="applied", user_id=user_id)
                msg = (
                    f"Tracked — **{title}** at **{company}** marked as applied. "
                    "I will treat this as your latest application context for follow-ups."
                )
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="applied",
                        action="mark_applied",
                    ),
                )
            except Exception:
                msg = (
                    f"Noted — **{title}** at **{company}** marked as applied. "
                    "(Could not write to Application Flow right now — please retry.)"
                )
            response = {
                "type": "mark_applied",
                "intent": "mark_applied",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "job_status": "applied",
                "next_action": "follow_up_after_7_days",
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

            # Could not identify a job from the card — fall back to the tool router.
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

        # Draft message
        if legacy_intent == "draft_message":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
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

    def _handle_cv_creation(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Start the no-CV profile builder / CV draft flow."""
        name = self._profile_value(profile, "name") or ""
        if name:
            greeting = f"Hi {name},"
        else:
            greeting = "Hi there,"
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
        """
        try:
            # Try DB-backed history first (primary for authenticated users)
            from src.services.chat_service import get_chat_history
            db_messages = get_chat_history(user_id, limit=limit)
            if db_messages:
                return db_messages[-limit:] if len(db_messages) > limit else db_messages
        except Exception as e:
            logger.warning("Failed to get recent messages from DB, falling back to memory",
                         extra={"user_id": user_id, "error": str(e)}, exc_info=True)

        # Fallback to memory store (JSON-backed local storage)
        try:
            messages = self.memory.get_chat_messages(user_id, limit=limit)
            return messages[-limit:] if len(messages) > limit else messages
        except Exception as e:
            logger.warning("Failed to get recent messages from memory",
                         extra={"user_id": user_id, "error": str(e)}, exc_info=True)
            return []

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
