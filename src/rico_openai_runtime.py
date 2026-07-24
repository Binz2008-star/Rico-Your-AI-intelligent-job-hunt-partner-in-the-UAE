"""Minimal, stable Rico AI runtime helper.

The module name is kept for backward compatibility, but the helper now supports
both:

  * OpenAI Responses API
  * DeepSeek OpenAI-compatible Chat Completions API

Hard rules:
  * No tools.
  * No response_format / json schema.
  * No streaming.
  * No previous_response_id.
  * No custom metadata.
  * Profile context truncated to 1200 chars.
  * Errors returned as a structured dict — exception class name, truncated
    message, status_code, request_id. Never the API key, headers, or full
    profile contents.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

OPENAI_PRIMARY_MODEL = (
    os.getenv("RICO_OPENAI_MODEL")
    or os.getenv("OPENAI_MODEL")
    or "gpt-4o-mini"
)
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# DeepSeek OpenAI-compatible model identifiers. On 2026-07-24 DeepSeek RETIRED
# the deepseek-chat / deepseek-reasoner aliases (they had mapped internally to
# V4 Flash); deepseek-v4-flash and deepseek-v4-pro are the CURRENT valid ids and
# both support tool-calling + JSON output. Defaults MUST stay current so the
# product never silently runs on an obsolete/retired primary model.
DEEPSEEK_DEFAULT_PRIMARY = "deepseek-v4-flash"
DEEPSEEK_DEFAULT_FALLBACK = "deepseek-v4-pro"
DEEPSEEK_PRIMARY_MODEL = (
    os.getenv("RICO_DEEPSEEK_MODEL")
    or os.getenv("DEEPSEEK_MODEL")
    or DEEPSEEK_DEFAULT_PRIMARY
)
DEEPSEEK_FALLBACK_MODEL = os.getenv("DEEPSEEK_FALLBACK_MODEL", DEEPSEEK_DEFAULT_FALLBACK)
# DEEPSEEK_MODEL_CHAIN is ADDITIVE, never a verbatim replacement: whatever the
# operator lists is trimmed and de-duplicated in order, then the two current
# valid anchors are appended if absent — so an override listing only a junk or
# retired id can never leave the chain without a working model.
_DEEPSEEK_MODEL_CHAIN_ENV = os.getenv("DEEPSEEK_MODEL_CHAIN", "").strip()

_FALLBACK_TEXT = (
    "Rico's core AI reasoning is temporarily unavailable, so I can't analyze your "
    "profile or advise on your search right now. Your saved data — files, jobs, and "
    "applications — is unaffected, and you can try again in a few minutes."
)
_RATE_LIMITED_TEXT = (
    "Rico's AI provider is currently rate-limited. "
    "This is temporary — please try again in a minute."
)
# Sized to fit profile essentials + uploaded_documents metadata + 8-turn
# conversation history; 1200 predates documents/history and silently cut
# the tail of the context JSON (uploaded_documents was serialized last).
_PROFILE_CONTEXT_MAX_CHARS = 4000
_SMOKE_MAX_OUTPUT_TOKENS = 80
# Output cap for real chat turns. This is an upper bound billed on actual output,
# so short answers stay cheap; it only needs to be high enough that long-form
# replies (cover letters, CV drafts, multi-paragraph guidance) finish instead of
# cutting off mid-sentence. 500 was too low and truncated cover letters.
_DEFAULT_MAX_OUTPUT_TOKENS = 1500
_ERROR_MESSAGE_MAX_CHARS = 500

# Defensive: redact anything that looks like an OpenAI/DeepSeek key from echoed
# exception messages. SDK errors occasionally include the key (e.g. when the
# server replies with the raw Authorization header in the error body).
_KEY_LIKE_RE = __import__("re").compile(r"(?:sk|dsk)-[A-Za-z0-9_\-]{6,}")


def _redact_secrets(text: str) -> str:
    return _KEY_LIKE_RE.sub("sk-***REDACTED***", text or "")


def _openai_key_present() -> bool:
    """True when either canonical or legacy OpenAI env var name is set."""
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API"))


def _deepseek_key_present() -> bool:
    """True when the DeepSeek API key is configured."""
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _provider_name(provider: Optional[str]) -> str:
    selected = (provider or "openai").strip().lower()
    return "deepseek" if selected == "deepseek" else "openai"


# ── Reasoning-provider health (reasoning-observability) ───────────────────────
# In-memory record of the most recent reasoning-provider outcome so /health can
# report whether the core AI is actually USABLE — not merely whether a key
# exists. Names and categories ONLY, never a key value or partial key. Resets on
# process restart, which is acceptable: /health reflects the live process.
_LAST_REASONING_OUTCOME: Dict[str, Any] = {
    "reachable": None,             # True after success, False after hard failure, None until first call
    "error_category": None,        # exception class category (e.g. "BadRequestError") — never a key
    "status_code": None,           # upstream HTTP status (e.g. 400/401/429/503)
    "provider_error_code": None,   # provider's own error code (e.g. "model_not_found") — a category
    "message": None,               # short, secret-redacted upstream message
    "model_attempted": None,       # the model identifier we sent (a name, never a credential)
    "provider": None,
}


def _record_reasoning_outcome(
    provider: str,
    *,
    reachable: bool,
    error_category: Optional[str] = None,
    status_code: Optional[int] = None,
    provider_error_code: Optional[str] = None,
    message: Optional[str] = None,
    model_attempted: Optional[str] = None,
) -> None:
    """Record the most recent reasoning outcome. On success the error fields clear.
    ``message`` is passed through ``_redact_secrets`` defensively before storing.
    """
    _LAST_REASONING_OUTCOME.update({
        "provider": provider,
        "reachable": reachable,
        "model_attempted": model_attempted,
        "error_category": None if reachable else (error_category or "UnknownAIError"),
        "status_code": None if reachable else status_code,
        "provider_error_code": None if reachable else provider_error_code,
        "message": None if reachable else (_redact_secrets(message)[:_ERROR_MESSAGE_MAX_CHARS] if message else None),
    })


def get_reasoning_health() -> Dict[str, Any]:
    """Reasoning-provider status for /health. Names, categories, status codes, and
    model identifiers ONLY — never a key value or partial key (the message is
    secret-redacted at record time).

    ``reachable`` is None until the first call this process. ``degraded`` is True
    only with positive evidence the primary is unusable AND no secondary provider
    is configured — so a healthy-looking platform can't hide a dead core AI.
    """
    provider = _provider_name(os.getenv("RICO_AI_PROVIDER"))
    fallback_available = bool((os.getenv("HF_TOKEN") or "").strip())
    last = _LAST_REASONING_OUTCOME
    reachable = last["reachable"]
    return {
        "provider": provider,
        "configured": _provider_key_present(provider),
        "reachable": reachable,
        "last_error_category": last["error_category"],
        "last_status_code": last["status_code"],
        "last_provider_error_code": last["provider_error_code"],
        "last_model_attempted": last["model_attempted"],
        "last_error_message": last["message"],
        "fallback_available": fallback_available,
        "degraded": (reachable is False) and not fallback_available,
    }


def _provider_key_present(provider: str) -> bool:
    return _deepseek_key_present() if provider == "deepseek" else _openai_key_present()


def _provider_models(provider: str) -> tuple[str, str]:
    if provider == "deepseek":
        return DEEPSEEK_PRIMARY_MODEL, DEEPSEEK_FALLBACK_MODEL
    return OPENAI_PRIMARY_MODEL, OPENAI_FALLBACK_MODEL


def _deepseek_model_chain() -> list[str]:
    """Return the ordered list of DeepSeek models to attempt.

    DEEPSEEK_MODEL_CHAIN is ADDITIVE, not a verbatim replacement: the operator's
    list is trimmed and de-duplicated in order, then the two current valid
    anchors (deepseek-v4-flash, deepseek-v4-pro) are appended if absent. This
    guarantees a non-empty chain that always ends with a working model, so an
    override that lists only a junk or retired id can never zero out the fallback.
    """
    chain: list[str] = []

    def _add(model: str) -> None:
        model = (model or "").strip()
        if model and model not in chain:
            chain.append(model)

    if _DEEPSEEK_MODEL_CHAIN_ENV:
        for m in _DEEPSEEK_MODEL_CHAIN_ENV.split(","):
            _add(m)
    else:
        _add(DEEPSEEK_PRIMARY_MODEL)
        _add(DEEPSEEK_FALLBACK_MODEL)
    # Always guarantee both current valid anchors as a last resort.
    _add(DEEPSEEK_DEFAULT_PRIMARY)
    _add(DEEPSEEK_DEFAULT_FALLBACK)
    return chain


def _provider_key(provider: str) -> Optional[str]:
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY")
    return os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API")


def _safe_openai_error(exc: Exception) -> Dict[str, Any]:
    """Extract only safe diagnostic fields from an OpenAI-compatible exception.

    Never returns headers, the request body, or the API key. The response
    object is read only for status_code and the x-request-id header — both
    routinely included in support tickets.
    """
    status_code = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)

    response = getattr(exc, "response", None)
    if response is not None:
        status_code = status_code or getattr(response, "status_code", None)
        headers = getattr(response, "headers", None)
        if headers:
            try:
                request_id = request_id or headers.get("x-request-id")
            except Exception:
                pass

    # The provider's own machine error code (e.g. "model_not_found",
    # "invalid_request_error") — a category, never a credential. OpenAI-compatible
    # SDKs expose it as exc.code; some wrap it in a body dict.
    provider_error_code = getattr(exc, "code", None)
    if provider_error_code is None:
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                provider_error_code = err.get("code") or err.get("type")

    return {
        "error_type": exc.__class__.__name__,
        "message": _redact_secrets(str(exc))[:_ERROR_MESSAGE_MAX_CHARS],
        "status_code": status_code,
        "provider_error_code": provider_error_code,
        "request_id": request_id,
    }


def _extract_response_text(response: Any) -> str:
    """Pull text out of an OpenAI Responses API result without assuming SDK version."""
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if value:
                chunks.append(str(value))

    return "\n".join(chunks).strip()


def _extract_chat_completion_text(response: Any) -> str:
    """Pull text out of an OpenAI-compatible chat completion result."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""

    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message")

    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)

    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
            else:
                text = getattr(item, "text", None) or getattr(item, "content", None)
            if text:
                chunks.append(str(text))
        return "\n".join(chunks).strip()

    return str(content or "").strip()


def _base_payload(provider: str, primary_model: str) -> Dict[str, Any]:
    return {
        "provider": provider,
        "provider_available": _provider_key_present(provider),
        "openai_available": _openai_key_present(),
        "deepseek_available": _deepseek_key_present(),
        "ai_model": primary_model,
    }


def _failure_payload(
    last_error: Optional[Dict[str, Any]],
    provider: str,
    primary_model: str,
    fallback_model: str,
    *,
    models_tried: Optional[list] = None,
) -> Dict[str, Any]:
    error_category = last_error.get("error_type") if last_error else "UnknownAIError"
    payload = {
        "success": False,
        "type": f"{provider}_error_fallback",
        "response_source": "fallback",
        # Distinct, machine-readable code so a dead core AI is never mistaken for
        # a benign keyword/free-mode fallback (reasoning-observability).
        "error_code": "reasoning_provider_unavailable",
        "provider_state": "degraded",
        "error": error_category,
        "error_detail": last_error,
        "text": _FALLBACK_TEXT,
        "fallback_model": fallback_model,
        **_base_payload(provider, primary_model),
    }
    if models_tried:
        payload["models_tried"] = models_tried
    if provider == "deepseek":
        payload["deepseek_model"] = primary_model
    else:
        payload["openai_model"] = primary_model
    # Record + log loudly: the core reasoning capability is DOWN. Names,
    # categories, status codes and model identifiers only — the message is
    # secret-redacted, never a key value.
    _status = (last_error or {}).get("status_code")
    _provider_err = (last_error or {}).get("provider_error_code")
    _msg = (last_error or {}).get("message")
    _model_attempted = (models_tried or [primary_model])[-1]
    _record_reasoning_outcome(
        provider,
        reachable=False,
        error_category=error_category,
        status_code=_status,
        provider_error_code=_provider_err,
        message=_msg,
        model_attempted=_model_attempted,
    )
    logger.error(
        "reasoning_provider_unavailable provider=%s status_code=%s provider_error_code=%s "
        "error_category=%s model_attempted=%s models_tried=%s message=%s "
        "— core AI reasoning is DOWN; served honest fallback",
        provider, _status, _provider_err, error_category, _model_attempted,
        models_tried or [primary_model], _redact_secrets(_msg) if _msg else None,
    )
    return payload


def _rate_limited_payload(
    last_error: Optional[Dict[str, Any]],
    provider: str,
    primary_model: str,
) -> Dict[str, Any]:
    payload = {
        "success": False,
        "type": f"{provider}_rate_limited",
        "response_source": "rate_limited",
        "provider_state": "rate_limited",
        "error": "RateLimitError",
        "error_detail": last_error,
        "text": _RATE_LIMITED_TEXT,
        **_base_payload(provider, primary_model),
    }
    if provider == "deepseek":
        payload["deepseek_model"] = primary_model
    else:
        payload["openai_model"] = primary_model
    return payload


def _timeout_seconds(env_name: str, default: float) -> float:
    """Positive float from env, else default. Backs the connect/read timeouts."""
    try:
        v = float((os.getenv(env_name) or "").strip())
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def _build_client(provider: str):
    from openai import OpenAI

    kwargs: Dict[str, Any] = {}
    api_key = _provider_key(provider)
    if api_key:
        kwargs["api_key"] = api_key
    if provider == "deepseek":
        kwargs["base_url"] = DEEPSEEK_BASE_URL
    # Disable SDK retries for chat requests - handle 429 explicitly instead
    kwargs["max_retries"] = 0
    # Separate connect vs read timeouts, env-configurable and sized so a heavy
    # V4 Flash completion is not cut off mid-stream by a short read deadline (the
    # old single 15s timeout truncated long answers). Connect stays short to fail
    # fast on an unreachable provider.
    from httpx import Timeout as _HttpxTimeout
    _connect = _timeout_seconds("RICO_AI_CONNECT_TIMEOUT", 10.0)
    _read = _timeout_seconds("RICO_AI_READ_TIMEOUT", 60.0)
    kwargs["timeout"] = _HttpxTimeout(connect=_connect, read=_read, write=_read, pool=_connect)
    return OpenAI(**kwargs)


def _call_openai_responses(
    client: Any,
    model: str,
    system_prompt: str,
    final_user_message: str,
    *,
    smoke: bool,
    conversation_history: Optional[list] = None,
) -> str:
    history = conversation_history or []
    input_messages = [{"role": "system", "content": system_prompt}]
    input_messages.extend(history)
    input_messages.append({"role": "user", "content": final_user_message})
    response = client.responses.create(
        model=model,
        input=input_messages,
        max_output_tokens=(
            _SMOKE_MAX_OUTPUT_TOKENS if smoke else _DEFAULT_MAX_OUTPUT_TOKENS
        ),
    )
    return _extract_response_text(response)


def _call_deepseek_chat(
    client: Any,
    model: str,
    system_prompt: str,
    final_user_message: str,
    *,
    smoke: bool,
    conversation_history: Optional[list] = None,
) -> str:
    history = conversation_history or []
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": final_user_message})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=(
            _SMOKE_MAX_OUTPUT_TOKENS if smoke else _DEFAULT_MAX_OUTPUT_TOKENS
        ),
    )
    return _extract_chat_completion_text(response)


def call_openai_minimal(
    user_message: str,
    profile_context: Optional[str] = None,
    *,
    smoke: bool = False,
    provider: Optional[str] = None,
    conversation_history: Optional[list] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Send the simplest possible call to the active premium provider.

    The function name is preserved for backward compatibility. `provider`
    accepts "openai" or "deepseek"; default is "openai".
    """

    active_provider = _provider_name(provider)
    primary_model, fallback_model = _provider_models(active_provider)
    profile_present = bool(profile_context)

    try:
        client = _build_client(active_provider)
    except Exception as exc:
        last_error = _safe_openai_error(exc)
        logger.warning(
            "Rico AI client init/import failed",
            extra={
                "provider": active_provider,
                "ai_error": last_error,
                "smoke": smoke,
            },
        )
        payload = _failure_payload(last_error, active_provider, primary_model, fallback_model)
        payload["profile_context_present"] = profile_present
        return payload

    from src.rico_identity import get_language_rule, get_rico_system_prompt
    import re as _re
    _arabic_re = _re.compile(r'[؀-ۿ]')
    _user_lang = "ar" if (language == "ar" or _arabic_re.search(str(user_message or ""))) else "en"
    system_prompt = get_rico_system_prompt() + get_language_rule(_user_lang)

    final_user_message = "Say OK" if smoke else str(user_message or "")

    if profile_context and not smoke:
        safe_context = str(profile_context)[:_PROFILE_CONTEXT_MAX_CHARS]
        final_user_message = (
            f"[User profile]\n{safe_context}\n\n"
            f"[User message]\n{final_user_message}"
        )

    safe_history = (conversation_history or [])[:8] if not smoke else []

    last_error: Optional[Dict[str, Any]] = None
    if active_provider == "deepseek":
        model_attempts = _deepseek_model_chain()
    else:
        model_attempts = [primary_model]
        if fallback_model and fallback_model != primary_model:
            model_attempts.append(fallback_model)

    models_tried: list = []

    for model in model_attempts:
        models_tried.append(model)
        try:
            if active_provider == "deepseek":
                text = _call_deepseek_chat(
                    client,
                    model,
                    system_prompt,
                    final_user_message,
                    smoke=smoke,
                    conversation_history=safe_history,
                )
            else:
                text = _call_openai_responses(
                    client,
                    model,
                    system_prompt,
                    final_user_message,
                    smoke=smoke,
                    conversation_history=safe_history,
                )

            if not text:
                raise RuntimeError(f"{active_provider} response returned empty text")

            _record_reasoning_outcome(active_provider, reachable=True, model_attempted=model)
            return {
                "success": True,
                "response_source": active_provider,
                "provider": active_provider,
                "model": model,
                "text": text,
                "profile_context_present": profile_present,
                **_base_payload(active_provider, model),
            }

        except Exception as exc:
            last_error = _safe_openai_error(exc)
            is_rate_limit = (
                last_error.get("status_code") == 429
                or "RateLimitError" in last_error.get("error_type", "")
            )
            is_invalid_model = last_error.get("status_code") == 400
            log_level = (
                "Rico AI provider rate limited — skipping retry"
                if is_rate_limit
                else f"Rico AI model {model!r} invalid or failed — trying next"
                if is_invalid_model
                else "Rico AI provider call failed safely"
            )
            logger.warning(
                log_level,
                extra={
                    "provider": active_provider,
                    "error_type": last_error.get("error_type"),
                    "status_code": last_error.get("status_code"),
                    "model": model,
                    "smoke": smoke,
                    "profile_context_present": profile_present,
                },
            )
            if is_rate_limit:
                payload = _rate_limited_payload(last_error, active_provider, model)
                payload["profile_context_present"] = profile_present
                payload["is_rate_limited"] = True
                # Rate-limited = reachable (auth OK, throttled), not "unusable".
                _record_reasoning_outcome(
                    active_provider, reachable=True,
                    error_category="RateLimitError", model_attempted=model,
                )
                return payload
            # For non-429 errors (including 400 invalid model, 401, 500, timeout)
            # continue to next model in chain.

    payload = _failure_payload(
        last_error, active_provider, primary_model, fallback_model,
        models_tried=models_tried,
    )
    payload["profile_context_present"] = profile_present
    return payload


def call_openai_stream(
    user_message: str,
    profile_context: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    conversation_history: Optional[list] = None,
    language: Optional[str] = None,
) -> Generator[str, None, None]:
    """Stream text tokens from the active AI provider as they arrive.

    Yields raw text chunks. The caller is responsible for SSE framing.
    Falls back to yielding the full non-streamed text if streaming fails.
    """
    import re as _re
    from src.rico_identity import get_rico_system_prompt

    active_provider = _provider_name(provider)
    primary_model, fallback_model = _provider_models(active_provider)

    _arabic_re = _re.compile(r'[؀-ۿ]')
    _user_lang = "ar" if (language == "ar" or _arabic_re.search(str(user_message or ""))) else "en"
    from src.rico_identity import get_language_rule as _get_language_rule
    system_prompt = get_rico_system_prompt() + _get_language_rule(_user_lang)

    final_message = str(user_message or "")
    if profile_context:
        safe_context = str(profile_context)[:_PROFILE_CONTEXT_MAX_CHARS]
        final_message = f"[User profile]\n{safe_context}\n\n[User message]\n{final_message}"

    safe_history = (conversation_history or [])[:8]

    try:
        client = _build_client(active_provider)
    except Exception:
        result = call_openai_minimal(user_message, profile_context, provider=provider,
                                     conversation_history=conversation_history, language=language)
        yield result.get("text", "")
        return

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(safe_history)
    messages.append({"role": "user", "content": final_message})

    import time

    # Walk the SAME model chain the non-streaming path uses, streaming from each
    # model in turn. A model that fails BEFORE emitting any token (retired id →
    # 400, connect timeout, etc.) hops to the next model, still streaming. If
    # every model fails, yield ONE honest, categorised fallback — never a silent
    # empty stream, never a guaranteed-failed primary-only attempt.
    model_attempts = (
        _deepseek_model_chain() if active_provider == "deepseek"
        else [m for m in (primary_model, fallback_model) if m]
    )
    last_error: Optional[Dict[str, Any]] = None
    for model in model_attempts:
        started = time.monotonic()
        produced = False
        try:
            if active_provider == "deepseek":
                stream = client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=_DEFAULT_MAX_OUTPUT_TOKENS, stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        produced = True
                        yield delta.content
            else:
                stream = client.responses.create(
                    model=model, input=messages,
                    max_output_tokens=_DEFAULT_MAX_OUTPUT_TOKENS, stream=True,
                )
                for event in stream:
                    text = getattr(getattr(event, "delta", None), "text", None) or ""
                    if text:
                        produced = True
                        yield text
            if produced:
                _record_reasoning_outcome(active_provider, reachable=True, model_attempted=model)
                return  # streamed a real answer
            # Empty stream (no tokens) → treat as failure and hop to the next model.
            last_error = {"error_type": "EmptyStream", "status_code": None,
                          "provider_error_code": None, "message": "empty stream"}
        except Exception as exc:
            last_error = _safe_openai_error(exc)
            last_error["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            if produced:
                # Tokens already sent to the client; we cannot cleanly restart on
                # another model. Record the partial and stop.
                _record_reasoning_outcome(
                    active_provider, reachable=True, model_attempted=model,
                    error_category=last_error.get("error_type"),
                    status_code=last_error.get("status_code"),
                )
                return
            # No tokens yet → a timeout/400/connection failure is safe to hop on.
            continue

    # Every model failed before producing a token → one honest, logged fallback
    # (no silent empty stream).
    _category = (last_error or {}).get("error_type") or "UnknownAIError"
    _record_reasoning_outcome(
        active_provider, reachable=False,
        error_category=_category,
        status_code=(last_error or {}).get("status_code"),
        provider_error_code=(last_error or {}).get("provider_error_code"),
        message=(last_error or {}).get("message"),
        model_attempted=(model_attempts[-1] if model_attempts else None),
    )
    logger.error(
        "reasoning_stream_unavailable provider=%s error_category=%s status_code=%s "
        "models_tried=%s — streaming chain exhausted; served honest fallback",
        active_provider, _category, (last_error or {}).get("status_code"), model_attempts,
    )
    yield _FALLBACK_TEXT
