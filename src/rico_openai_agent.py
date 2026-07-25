"""Rico AI response layer.

Provider selection (via RICO_AI_PROVIDER env var):
  auto/unset    -- DeepSeek if configured, otherwise Hugging Face, otherwise fallback.
  hf            -- Hugging Face Inference API, zero OpenAI cost.
  openai        -- OpenAI API, opt-in only for premium mode.
  deepseek      -- DeepSeek API via the OpenAI-compatible SDK path.

When RICO_AI_PROVIDER=hf:
  - HF is called directly for rich replies.
  - OpenAI is never called regardless of OPENAI_API_KEY presence.
  - Templated fallback is used when HF is unavailable.

When RICO_AI_PROVIDER is unset:
  - DeepSeek is called if DEEPSEEK_API_KEY is present.
  - Otherwise HF is called if a HF key alias is present.
  - Templated fallback is used when neither is available.

When RICO_AI_PROVIDER=openai:
  - OpenAI is called if OPENAI_API_KEY is present.
  - HF is the cascade fallback.

When RICO_AI_PROVIDER=deepseek:
  - DeepSeek is called if DEEPSEEK_API_KEY is present.
  - HF is the cascade fallback.
  - Templated fallback if both fail.
"""

from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.rico_env import get_ai_provider
from src.rico_identity import get_rico_system_prompt
from src.rico_openai_runtime import (
    DEEPSEEK_FALLBACK_MODEL,
    DEEPSEEK_PRIMARY_MODEL,
    OPENAI_FALLBACK_MODEL,
    OPENAI_PRIMARY_MODEL,
    REASONING_UNAVAILABLE_TEXT,
    call_openai_minimal,
)
from src.rico_safety import RicoSafetyGuard

logger = logging.getLogger(__name__)

# Minimal, local Arabic-script detector for the terminal/HF fallback paths
# only. Kept local (not imported from RicoChatAPI) to avoid a circular
# import: rico_chat_api.py already imports this module.
_ARABIC_RE = re.compile(r"[؀-ۿ]")


def _wants_arabic(language: Optional[str], user_message: Optional[str]) -> bool:
    if language == "ar":
        return True
    return bool(_ARABIC_RE.search(user_message or ""))


@dataclass
class RicoToolResult:
    tool_name: str
    result: Dict[str, Any]


class RicoOpenAIAgent:
    """Rico reasoning layer using OpenAI Responses API when configured."""

    def __init__(self, tools: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None) -> None:
        # Canonical name is OPENAI_API_KEY. OPEN_AI_API is read as a temporary
        # fallback so existing Render deployments keep working until the env
        # var is renamed.
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API")
        self.api_key = self.openai_api_key  # backward-compatible alias used by older tests/callers
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model = self._resolve_model()
        self.tools = tools or {}
        self.safety = RicoSafetyGuard()

    @property
    def available(self) -> bool:
        return self.openai_available or self.deepseek_available

    @property
    def openai_available(self) -> bool:
        return bool(self.openai_api_key or getattr(self, "api_key", None))

    @property
    def deepseek_available(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def hf_available(self) -> bool:
        """True when any HF key alias is set."""
        return bool(
            os.getenv("HF_API_TOKEN") or os.getenv("HF_API_KEY")
            or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        )

    @property
    def _use_openai(self) -> bool:
        """True only when operator explicitly opts in via RICO_AI_PROVIDER=openai."""
        return get_ai_provider() == "openai" and self.openai_available

    @property
    def _use_deepseek(self) -> bool:
        """True only when operator opts in to DeepSeek and the key is present."""
        return get_ai_provider() == "deepseek" and self.deepseek_available

    @property
    def provider_available(self) -> bool:
        provider = get_ai_provider()
        if provider == "openai":
            return self.openai_available
        if provider == "deepseek":
            return self.deepseek_available
        if provider == "huggingface":
            return self.hf_available
        return False

    def _resolve_model(self) -> str:
        provider = get_ai_provider()
        if provider == "deepseek":
            return os.getenv("RICO_DEEPSEEK_MODEL") or os.getenv("DEEPSEEK_MODEL") or DEEPSEEK_PRIMARY_MODEL
        if provider == "huggingface":
            return os.getenv("HF_TEXT_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        return os.getenv("RICO_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or OPENAI_PRIMARY_MODEL

    def respond(
        self,
        user_message: str,
        user_context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        safety_check_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Callers that augment user_message with untrusted document content
        # (OCR text, attachment excerpts) pass the ORIGINAL user request here
        # so safety evaluates genuine user intent, never embedded document text.
        safety = self.safety.check_message(
            safety_check_message if safety_check_message is not None else user_message
        )
        if not safety.allowed:
            return {
                "type": "safety_refusal",
                "message": safety.safe_response,
                "category": safety.category,
            }

        # Default path: HF is the primary provider (zero OpenAI cost)
        if not self._use_openai and not self._use_deepseek:
            if self.hf_available:
                hf_result = self._hf_fallback_with_record(user_message, user_context, language=language)
                if hf_result:
                    return hf_result
            # No usable reasoning provider. `respond()` is only ever reached on
            # the conversational-AI path — the router already decided this
            # request needs the model — so the ONLY honest answer here is that
            # reasoning is unavailable. Returning a cosy capability blurb makes a
            # dead provider look like a deliberate reply and hides the outage.
            return self._reasoning_unavailable_response(language=language, user_message=user_message)

        # Premium path: RICO_AI_PROVIDER=openai|deepseek explicitly set
        provider = "deepseek" if self._use_deepseek else "openai"
        def _json_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        profile_context = (
            json.dumps(user_context, ensure_ascii=False, default=_json_default)
            if user_context else None
        )
        conversation_history = (
            user_context.get("conversation_history", [])
            if isinstance(user_context, dict) else []
        )
        result = call_openai_minimal(
            user_message,
            profile_context=profile_context,
            provider=provider,
            conversation_history=conversation_history,
            language=language,
        )

        if result.get("success"):
            return {
                "type": f"{provider}_response",
                "message": result["text"],
                "model": result.get("model") or self.model,
                "provider": provider,
            }

        # Premium provider failed — cascade to HF. The cascade is now instrumented:
        # whether the backup engaged and whether it produced usable text is
        # recorded + logged, so a fallback that silently returns None can never
        # degrade us to templated text without ringing an alarm (reasoning-observability).
        if self.hf_available:
            hf_result = self._hf_fallback_with_record(user_message, user_context, language=language)
            if hf_result:
                return hf_result

        if result.get("is_rate_limited"):
            return {
                "type": f"{provider}_rate_limited",
                "message": result.get("text") or REASONING_UNAVAILABLE_TEXT,
                "provider": provider,
                "provider_state": "rate_limited",
                "response_source": "rate_limited",
                "error_category": result.get("error_category") or "rate_limited",
            }

        model_key = "deepseek_model" if provider == "deepseek" else "openai_model"
        fallback_model = (
            result.get("fallback_model")
            or (DEEPSEEK_FALLBACK_MODEL if provider == "deepseek" else OPENAI_FALLBACK_MODEL)
        )

        # `_failure_payload` already marks a dead provider with a distinct,
        # machine-readable `error_code`, a `degraded` provider_state and a
        # canonical `error_category`. Dropping them here collapsed an honest
        # "reasoning is down" reply into the same SOURCE_FALLBACK bucket as a
        # benign keyword fallback (`_source_for_openai_response`), so nothing
        # downstream — envelope, analytics, or the owner reading a reply — could
        # tell an outage from a normal answer. Forward them instead.
        #
        # The message default is REASONING_UNAVAILABLE_TEXT, the same honest wording the
        # payload carries, so a missing/blank `text` can never degrade into a
        # capability blurb that reads like a real answer.
        return {
            "type": f"{provider}_error_fallback",
            "message": result.get("text") or REASONING_UNAVAILABLE_TEXT,
            "error": result.get("error"),
            "error_detail": result.get("error_detail"),
            "error_code": result.get("error_code") or "reasoning_provider_unavailable",
            "error_category": result.get("error_category"),
            "provider_state": result.get("provider_state") or "degraded",
            "response_source": result.get("response_source") or "fallback",
            model_key: result.get(model_key) or self.model,
            "fallback_model": fallback_model,
            "provider": "fallback",
        }

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> RicoToolResult:
        if tool_name not in self.tools:
            return RicoToolResult(tool_name, {"error": "tool_not_registered"})

        action_safety = self.safety.check_action(
            tool_name,
            user_has_approved=bool(arguments.get("user_has_approved")),
        )
        if not action_safety.allowed:
            return RicoToolResult(tool_name, {
                "error": "approval_required",
                "message": action_safety.safe_response,
                "required_user_confirmation": action_safety.required_user_confirmation,
            })

        return RicoToolResult(tool_name, self.tools[tool_name](**arguments))

    def _build_user_prompt(self, user_message: str, user_context: Optional[Dict[str, Any]]) -> str:
        context = json.dumps(user_context or {}, ensure_ascii=False, indent=2)
        return f"User message:\n{user_message}\n\nKnown Rico context:\n{context}"

    def _hf_fallback_with_record(
        self,
        user_message: str,
        user_context: Optional[Dict[str, Any]],
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run the HuggingFace backup and RECORD whether it engaged and whether it
        produced usable text.

        A backup that fails invisibly is worse than no backup — it removes the
        alarm. So a ``None``/empty result here yields a distinct, categorised
        outcome and an explicit error log line (via ``record_fallback_outcome``)
        instead of silently degrading to templated text. This only observes the
        cascade — it does NOT repair the HF path and never runs inside
        ``call_openai_minimal``.
        """
        from src.rico_openai_runtime import record_fallback_outcome

        model = os.getenv("HF_TEXT_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        hf_result = self._call_hf_free(user_message, user_context, language=language)
        if hf_result and hf_result.get("message"):
            record_fallback_outcome(
                provider="huggingface", engaged=True, succeeded=True,
                model=hf_result.get("model") or model,
            )
            return hf_result
        record_fallback_outcome(
            provider="huggingface", engaged=True, succeeded=False,
            error_category="response_contract",
            message="huggingface fallback returned no usable text",
            model=model,
        )
        return None

    def _call_hf_free(
        self,
        user_message: str,
        user_context: Optional[Dict[str, Any]],
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Delegate to rico_hf_client.generate_text for a consistent, configurable HF call.

        Uses HF_TEXT_MODEL env var (default: HuggingFaceH4/zephyr-7b-beta).
        Returns None on failure so the caller can fall back to templated text.
        """
        from src.rico_hf_client import generate_text, is_available

        if not is_available():
            return None

        system = (
            "You are Rico, a helpful UAE job-search assistant. "
            "Answer clearly, practically, and briefly. "
            "Help users find jobs, prepare applications, and track opportunities in the UAE."
        )
        if _wants_arabic(language, user_message):
            system += " IMPORTANT: The user is writing in Arabic. Reply entirely in Arabic."

        # Build a structured chat-style prompt so the model sees conversation turns
        # rather than a raw JSON blob it cannot parse.
        ctx = user_context or {}
        history: List[Dict[str, Any]] = ctx.get("conversation_history", [])

        # Profile summary: skip large/nested fields that add noise without meaning
        _skip = {"conversation_history", "uploaded_documents", "recently_discussed_jobs",
                  "recent_job_verification_status", "learned_preferences", "blocked_questions"}
        profile_fields = {k: v for k, v in ctx.items() if k not in _skip}

        parts: List[str] = []
        if profile_fields:
            parts.append(f"[User profile]\n{json.dumps(profile_fields, ensure_ascii=False)}")

        for m in history[-6:]:
            role = str(m.get("role", "")).lower()
            content = str(m.get("content") or m.get("message") or "").strip()
            if not content:
                continue
            if role == "assistant":
                parts.append(f"Rico: {content}")
            else:
                parts.append(f"User: {content}")

        parts.append(f"User: {user_message}")
        parts.append("Rico:")

        prompt = "\n".join(parts)

        model = os.getenv("HF_TEXT_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        text = generate_text(prompt, system=system, max_new_tokens=300, model=model)
        if not text:
            return None
        return {
            "type": "hf_response",
            "message": text,
            "provider": "huggingface",
            "model": model,
        }

    def _reasoning_unavailable_response(
        self, language: Optional[str] = None, user_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Honest reply when NO reasoning provider is usable at all.

        Reached when the active provider has no key AND HuggingFace is absent or
        returned nothing — i.e. Rico cannot reason about this request. Since
        ``respond()`` is only called on the conversational-AI path, the router
        has already decided the request needs the model, so silence about the
        outage is a lie about the answer.

        This previously returned a capability blurb ("I'm here to help with your
        UAE job search. Upload your CV to get started…") carrying no error_code
        and no provider_state. During a provider outage that reads as a real —
        if unhelpful — answer rather than a failure, which is precisely how such
        an incident stays invisible to the owner. It now says what is true and
        carries the same machine-readable markers ``_failure_payload`` uses, so
        the honest degraded state is visible to the envelope and to analytics.

        The English wording is imported from the runtime rather than restated,
        so this path and the configured-but-failing path can never drift into
        telling the user two different stories about the same outage.
        """
        if _wants_arabic(language, user_message):
            message = (
                "قدرة الاستدلال الأساسية في ريكو غير متاحة مؤقتاً، لذا لا أستطيع "
                "تحليل ملفك أو تقديم نصيحة بشأن بحثك الآن. بياناتك المحفوظة — "
                "الملفات والوظائف والطلبات — لم تتأثر، ويمكنك المحاولة مرة أخرى بعد دقائق."
            )
        else:
            message = REASONING_UNAVAILABLE_TEXT
        return {
            "type": "reasoning_unavailable",
            "message": message,
            "provider": "fallback",
            "response_source": "fallback",
            "error_code": "reasoning_provider_unavailable",
            "error_category": "not_configured",
            "provider_state": "degraded",
        }

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "search_jobs",
                "description": "Search UAE jobs for the user based on profile and preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "city": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "update_preferences",
                "description": "Update Rico user preferences learned from chat.",
                "parameters": {
                    "type": "object",
                    "properties": {"preferences": {"type": "object"}},
                    "required": ["preferences"],
                },
            },
            {
                "type": "function",
                "name": "write_cover_letter",
                "description": "Draft a truthful cover letter for a selected job.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "tone": {"type": "string", "default": "professional"},
                        "user_has_approved": {"type": "boolean", "default": False},
                    },
                    "required": ["job_id"],
                },
            },
            {
                "type": "function",
                "name": "prepare_interview",
                "description": "Prepare interview notes and likely questions for a selected job.",
                "parameters": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                    "required": ["job_id"],
                },
            },
            {
                "type": "function",
                "name": "track_application",
                "description": "Track application status and next follow-up step.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["job_id", "status"],
                },
            },
        ]
