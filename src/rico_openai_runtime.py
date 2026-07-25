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
#: Public alias. The agent layer reuses this exact wording for the
#: no-provider-configured case so the two provider-failure paths can never drift
#: into telling the user two different stories about the same outage.
REASONING_UNAVAILABLE_TEXT = _FALLBACK_TEXT
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


def _now_iso() -> str:
    """UTC ISO-8601 timestamp for last_checked_at / last_success_at."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ── Fixed reasoning-provider error vocabulary (reasoning-observability) ────────
# Every reasoning-provider failure is mapped onto EXACTLY one of these values.
# This canonical ``error_category`` is what gets recorded and surfaced on
# /health, /ready and in logs — never the raw exception class. Extending this
# tuple is a deliberate contract change (a test pins the exact set).
ERROR_CATEGORIES: tuple[str, ...] = (
    "not_configured",         # no key / provider not set up
    "invalid_configuration",  # malformed request / bad params (a 400 that is not a model id)
    "unsupported_model",      # retired / unknown model id (400/404 model_not_found, or /models says absent)
    "authentication",         # 401 / 403 / bad key
    "insufficient_balance",   # 402 / out of credit
    "rate_limited",           # 429 / throttled
    "timeout",                # connect or read deadline exceeded
    "connection",             # DNS / refused / reset / unreachable (incl. /models unreachable)
    "provider_4xx",           # other 4xx
    "provider_5xx",           # 5xx upstream
    "response_contract",      # reachable but returned no usable content (empty text / empty stream)
    "unknown",                # unclassifiable
)


def categorize_error(
    *,
    status_code: Optional[int] = None,
    error_type: Optional[str] = None,
    provider_error_code: Optional[str] = None,
    message: Optional[str] = None,
    key_present: Optional[bool] = None,
) -> str:
    """Map an upstream status code / exception / provider error code onto exactly
    one value from ``ERROR_CATEGORIES``.

    Deterministic and side-effect free — the single source of truth for the
    canonical ``error_category`` surfaced everywhere. Never inspects or returns
    any secret; only class names, status codes, provider error codes, and a
    redacted message are consulted.
    """
    et = (error_type or "").lower()
    code = (provider_error_code or "").lower()
    msg = (message or "").lower()

    # No credentials configured at all — an explicit signal beats guessing 401.
    if key_present is False:
        return "not_configured"
    if any(k in msg for k in ("no api key", "api key not", "not configured", "missing api key")):
        return "not_configured"

    # Timeout — a specific connect/read deadline (checked before generic connection).
    if "timeout" in et or "timedout" in et or "timed out" in msg or "timeout" in msg:
        return "timeout"

    # Response-contract: a reachable provider that returned nothing usable
    # (our own empty-stream / empty-text guards).
    if et in ("emptystream", "emptyresponse") or "empty stream" in msg or "returned empty text" in msg:
        return "response_contract"

    # Network reachability failures (DNS, refused, reset, unreachable).
    if (any(k in et for k in ("connectionerror", "apiconnectionerror", "connecterror",
                              "newconnectionerror", "sslerror", "protocolerror"))
            or any(k in msg for k in ("connection refused", "connection reset", "connection aborted",
                                      "failed to establish", "name or service not known",
                                      "temporary failure in name resolution", "network is unreachable",
                                      "max retries exceeded"))):
        return "connection"

    # Explicit balance / credit exhaustion (distinct from rate limiting).
    if (status_code == 402
            or code in ("insufficient_balance", "insufficient_quota")
            or ("insufficient" in code and "balance" in code)
            or "insufficient balance" in msg):
        return "insufficient_balance"

    # Status-code driven classification.
    if status_code is not None:
        if status_code == 429:
            return "rate_limited"
        if status_code in (401, 403):
            return "authentication"
        if status_code == 404:
            return "unsupported_model"
        if status_code == 400:
            if (any(k in code for k in ("model_not_found", "model_not_exist", "unsupported_model",
                                        "invalid_model", "model_decommissioned"))
                    or ("model" in msg and any(k in msg for k in
                        ("not found", "not exist", "does not exist", "unsupported",
                         "decommission", "retired", "unknown model")))):
                return "unsupported_model"
            return "invalid_configuration"
        if 400 <= status_code < 500:
            return "provider_4xx"
        if 500 <= status_code < 600:
            return "provider_5xx"

    # Provider-error-code / exception-class fallbacks when no status code is present.
    if any(k in code for k in ("model_not_found", "model_not_exist", "unsupported_model",
                               "invalid_model", "model_decommissioned")):
        return "unsupported_model"
    if "ratelimit" in et or ("rate" in code and "limit" in code) or "too many requests" in msg:
        return "rate_limited"
    if "authentication" in et or "permissiondenied" in et or code in ("invalid_api_key", "unauthorized"):
        return "authentication"
    if "notfound" in et:
        return "unsupported_model"
    if "badrequest" in et or "unprocessable" in et:
        return "invalid_configuration"
    if "internalservererror" in et or "serviceunavailable" in et:
        return "provider_5xx"

    return "unknown"


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
    "error_category": None,        # canonical ERROR_CATEGORIES value — never the raw class, never a key
    "status_code": None,           # upstream HTTP status (e.g. 400/401/429/503)
    "provider_error_code": None,   # provider's own error code (e.g. "model_not_found") — a category
    "message": None,               # short, secret-redacted upstream message
    "model_attempted": None,       # the model identifier we sent (a name, never a credential)
    "provider": None,
    "last_checked_at": None,       # ISO-8601 UTC of the most recent outcome record
    "last_success_at": None,       # ISO-8601 UTC of the most recent SUCCESS
    "elapsed_ms": None,            # elapsed of the most recent attempt (non-stream path included)
    "attempts": None,              # per-attempt list: {model, elapsed_ms, category, status_code, ok}
    "fallback_engaged": None,      # did a secondary (HF) fallback run this turn?
    "fallback_succeeded": None,    # did that fallback produce usable text?
    "stream_frames": None,         # # of incremental token frames the last stream emitted
    "first_frame_ms": None,        # ms to the FIRST token frame of the last stream
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
    elapsed_ms: Optional[int] = None,
    attempts: Optional[list] = None,
) -> None:
    """Record the most recent reasoning outcome. On success the error fields clear.

    ``error_category`` is a canonical ``ERROR_CATEGORIES`` value supplied by the
    caller (never a raw exception class). ``message`` is passed through
    ``_redact_secrets`` defensively before storing.
    """
    now = _now_iso()
    update: Dict[str, Any] = {
        "provider": provider,
        "reachable": reachable,
        "model_attempted": model_attempted,
        "error_category": None if reachable else (error_category or "unknown"),
        "status_code": None if reachable else status_code,
        "provider_error_code": None if reachable else provider_error_code,
        "message": None if reachable else (_redact_secrets(message)[:_ERROR_MESSAGE_MAX_CHARS] if message else None),
        "last_checked_at": now,
    }
    if elapsed_ms is not None:
        update["elapsed_ms"] = elapsed_ms
    if attempts is not None:
        update["attempts"] = attempts
    if reachable:
        update["last_success_at"] = now
    _LAST_REASONING_OUTCOME.update(update)


def record_fallback_outcome(
    *,
    provider: str = "huggingface",
    engaged: bool,
    succeeded: bool,
    error_category: Optional[str] = None,
    message: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Record whether a secondary (e.g. HuggingFace) fallback engaged and whether
    it produced usable text — so a backup that fails INVISIBLY becomes a loud,
    categorised outcome on /health instead of silently degrading to templated
    text. A backup that fails without an alarm is worse than no backup.

    Only names/categories are stored; ``message`` is secret-redacted. This does
    NOT repair the fallback path, and it never runs inside ``call_openai_minimal``.
    """
    _LAST_REASONING_OUTCOME["fallback_engaged"] = engaged
    _LAST_REASONING_OUTCOME["fallback_succeeded"] = succeeded
    _LAST_REASONING_OUTCOME["last_checked_at"] = _now_iso()
    if engaged and succeeded:
        logger.info(
            "reasoning_fallback_succeeded provider=%s model=%s — secondary backup served the answer",
            provider, model,
        )
    elif engaged and not succeeded:
        # The alarm: the backup ran and returned nothing usable.
        logger.error(
            "reasoning_fallback_empty provider=%s model=%s error_category=%s message=%s "
            "— secondary backup engaged but produced NO usable text; served templated fallback",
            provider, model, error_category or "response_contract",
            _redact_secrets(message) if message else None,
        )


def _fallback_exists() -> bool:
    """True when a secondary reasoning backup (HuggingFace) is configured."""
    return bool(
        (os.getenv("HF_API_TOKEN") or os.getenv("HF_TOKEN")
         or os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or "").strip()
    )


def _resolved_chain(provider: str) -> list[str]:
    """The ordered model chain that would actually be attempted for ``provider``."""
    if provider == "deepseek":
        return _deepseek_model_chain()
    primary, fallback = _provider_models(provider)
    return [m for m in (primary, fallback) if m]


# ── /models pre-check (reasoning-observability, item 2) ───────────────────────
# A GET /models probe run at STARTUP and then on a long cached interval — never
# per user request, never in the latency path of a chat turn. Its only job is to
# make ``unsupported_model`` deterministic instead of guessed, and to feed the
# health surface. It FAILS SOFT: if /models itself is unreachable we classify
# that as provider reachability and keep serving the configured chain — a dead
# metadata endpoint must never stop us serving.
# SHORT cache window for the /models probe. Hard-coded (no new env var). The
# probe is ADVISORY ONLY and short-lived: a "candidate absent" verdict is honored
# for at most this window, then expires to "unknown" so discovery can never
# permanently mark a model or provider unsupported. Errors fail soft
# (stale-while-error): the normal chain is served untouched.
_MODELS_ADVISORY_WINDOW_SECONDS = 300.0
_MODELS_STATUS: Dict[str, Any] = {
    "provider": None,
    "reachable": None,             # could we reach /models? None until first probe
    "available_models": None,      # frozenset of ids when reachable; None when not
    "error_category": None,        # canonical category when the probe itself failed
    "checked_at": None,            # ISO-8601 UTC of the last probe
    "_checked_monotonic": None,    # internal: for interval math
}


def refresh_model_availability(provider: Optional[str] = None, *, force: bool = False) -> Dict[str, Any]:
    """Probe the provider's ``GET /models`` once and cache the result. Fail soft.

    Called at startup (in a background thread) and lazily from /ready — NEVER from
    a user chat request, and never as a blocking round trip in front of a prompt.

    ADVISORY ONLY: a successfully-retrieved list with a candidate absent lets us
    skip that candidate for the short advisory window. A timeout, connection
    failure, malformed body, or EMPTY ``data`` array all resolve to
    ``available_models=None`` — i.e. "unknown" — so the normal chain is served
    untouched. Discovery can never permanently mark a model/provider unsupported.
    """
    import time as _time
    prov = _provider_name(provider if provider is not None else os.getenv("RICO_AI_PROVIDER"))
    prev = _MODELS_STATUS.get("_checked_monotonic")
    if (not force) and prev is not None and (_time.monotonic() - prev) < _MODELS_ADVISORY_WINDOW_SECONDS:
        return _MODELS_STATUS

    ids: Optional[frozenset] = None
    reachable = False
    category: Optional[str] = None
    if not _provider_key_present(prov):
        category = "not_configured"
    else:
        try:
            client = _build_client(prov)
            listing = client.models.list()
            data = getattr(listing, "data", None)
            if data is None and isinstance(listing, dict):
                data = listing.get("data")
            collected = set()
            for item in (data or []):
                mid = getattr(item, "id", None)
                if mid is None and isinstance(item, dict):
                    mid = item.get("id")
                if mid:
                    collected.add(str(mid))
            if collected:
                ids = frozenset(collected)
                reachable = True
            else:
                # Empty / malformed data array: the endpoint answered but told us
                # nothing usable. Advisory-off — carry on with the normal chain
                # untouched. NEVER interpret "no models listed" as "every model
                # unsupported".
                category = "response_contract"
                logger.warning(
                    "models_precheck_empty provider=%s — empty/malformed model list; "
                    "advisory-off, serving configured chain untouched", prov,
                )
        except Exception as exc:
            safe = _safe_openai_error(exc)
            category = safe.get("error_category") or "connection"
            logger.warning(
                "models_precheck_unreachable provider=%s error_category=%s status_code=%s "
                "— failing soft; serving configured chain",
                prov, category, safe.get("status_code"),
            )

    _MODELS_STATUS.update({
        "provider": prov,
        "reachable": reachable,
        "available_models": ids,
        "error_category": None if reachable else category,
        "checked_at": _now_iso(),
        "_checked_monotonic": _time.monotonic(),
    })
    return _MODELS_STATUS


_MODELS_BG_STARTED = False


def start_model_precheck_background(provider: Optional[str] = None) -> None:
    """Start the ONLY thing allowed to refresh the /models cache: a daemon that
    probes once at startup and then re-probes on the background interval, forever.

    Runs off the request path entirely — no inbound HTTP request (including /ready
    or /health) ever triggers an upstream probe, so the endpoints can't be looped
    to burn the provider balance. Non-blocking (daemon thread), best-effort, and
    fails soft. Idempotent: starting twice is a no-op.
    """
    global _MODELS_BG_STARTED
    if _MODELS_BG_STARTED:
        return
    import threading
    import time as _time

    def _run() -> None:
        while True:
            try:
                refresh_model_availability(provider, force=True)
            except Exception:  # pragma: no cover - defensive
                pass
            try:
                _time.sleep(_MODELS_ADVISORY_WINDOW_SECONDS)
            except Exception:  # pragma: no cover - defensive
                return

    try:
        threading.Thread(target=_run, name="rico-models-precheck", daemon=True).start()
        _MODELS_BG_STARTED = True
    except Exception:  # pragma: no cover - defensive
        pass


def _fresh_available_models(provider: Optional[str] = None) -> Optional[frozenset]:
    """The available-model set ONLY when a successful probe is still inside the
    short advisory window; ``None`` otherwise (cold, stale, errored, empty, or a
    different provider) so callers fail soft and never skip on stale/absent data."""
    import time as _time
    if not _MODELS_STATUS.get("reachable"):
        return None
    # Never apply one provider's model list to another provider's chain.
    if provider is not None and _MODELS_STATUS.get("provider") not in (None, provider):
        return None
    available = _MODELS_STATUS.get("available_models")
    if available is None:
        return None
    prev = _MODELS_STATUS.get("_checked_monotonic")
    if prev is None or (_time.monotonic() - prev) >= _MODELS_ADVISORY_WINDOW_SECONDS:
        return None  # stale success → advisory expired → treat as unknown
    return available


def is_model_supported(model: str, provider: Optional[str] = None) -> Optional[bool]:
    """Advisory support verdict from the cached /models probe.

    True  → fresh successful probe lists this id.
    False → fresh successful probe does NOT list this id (advisory unsupported).
    None  → unknown (never probed, stale, unreachable, empty, or other provider).
    """
    available = _fresh_available_models(provider)
    if available is None:
        return None
    return model in available


def _advisory_chain(chain: list[str], provider: Optional[str] = None) -> list[str]:
    """Drop models a FRESH successful probe reports absent — advisory only. If that
    would empty the chain, return the full chain unchanged (never refuse to serve).
    Cold / stale / errored / empty / other-provider probe → chain returned untouched."""
    available = _fresh_available_models(provider)
    if available is None:
        return chain
    filtered = [m for m in chain if m in available]
    return filtered or chain


def get_models_status() -> Dict[str, Any]:
    """Public, secret-free view of the /models probe for the health surface."""
    available = _MODELS_STATUS.get("available_models")
    return {
        "reachable": _MODELS_STATUS.get("reachable"),
        "checked_at": _MODELS_STATUS.get("checked_at"),
        "error_category": _MODELS_STATUS.get("error_category"),
        "available_count": (len(available) if available is not None else None),
    }


def get_reasoning_health() -> Dict[str, Any]:
    """Reasoning-provider status for /health. Names, categories, status codes, and
    model identifiers ONLY — never a key value or partial key (the message is
    secret-redacted at record time).

    ``reachable`` is None until the first call this process. ``degraded`` is True
    only with positive evidence the primary is unusable AND no secondary provider
    is configured — so a healthy-looking platform can't hide a dead core AI.
    Reads cached state only — never triggers a network probe (keeps /health fast
    and unable to fail).
    """
    provider = _provider_name(os.getenv("RICO_AI_PROVIDER"))
    fallback_exists = _fallback_exists()
    last = _LAST_REASONING_OUTCOME
    reachable = last["reachable"]
    try:
        chain = _resolved_chain(provider)
    except Exception:
        chain = []
    return {
        "provider": provider,
        "configured": _provider_key_present(provider),
        "model_chain": chain,
        "reachable": reachable,
        # Canonical category (item 1) plus the long-standing ``last_*`` aliases.
        "error_category": last["error_category"],
        "last_error_category": last["error_category"],
        "last_status_code": last["status_code"],
        "last_status": last["status_code"],
        "last_provider_error_code": last["provider_error_code"],
        "last_model_attempted": last["model_attempted"],
        "last_error_message": last["message"],
        "last_checked_at": last["last_checked_at"],
        "last_success_at": last["last_success_at"],
        "last_elapsed_ms": last["elapsed_ms"],
        "attempts": last["attempts"],
        "fallback_exists": fallback_exists,
        # Back-compat alias kept for existing consumers/tests.
        "fallback_available": fallback_exists,
        "fallback_engaged": last["fallback_engaged"],
        "fallback_succeeded": last["fallback_succeeded"],
        "last_stream_frames": last["stream_frames"],
        "last_first_frame_ms": last["first_frame_ms"],
        "models_precheck": get_models_status(),
        # Degraded when core reasoning is down AND there is no WORKING backstop:
        # either no fallback configured, or the fallback engaged and produced
        # nothing usable (a backup that fails invisibly must still ring the alarm).
        "degraded": (reachable is False) and (
            (not fallback_exists)
            or (last["fallback_engaged"] is True and last["fallback_succeeded"] is False)
        ),
    }


def get_readiness() -> Dict[str, Any]:
    """Readiness verdict for GET /ready: ``ready=False`` (→ 503) only when core
    reasoning has NO reachable valid model. Fails soft — an unreachable /models
    probe never makes us un-ready, because we still serve the configured chain.

    /health stays HTTP 200 and merely reports ``degraded``; /ready is the
    503-capable probe. Both answer from the SAME cached provider state and make
    NO per-request upstream call — an inbound request must never trigger an
    outbound (billable) provider call, or an unauthenticated endpoint becomes a
    cost/abuse amplifier. Only the non-blocking startup + background refresh
    updates the cache.
    """
    provider = _provider_name(os.getenv("RICO_AI_PROVIDER"))
    configured = _provider_key_present(provider)
    fallback_exists = _fallback_exists()
    try:
        chain = _resolved_chain(provider)
    except Exception:
        chain = []

    reasons: list[str] = []
    ready = True

    if not configured:
        ready = False
        reasons.append("not_configured")

    # A fresh, successful /models probe that lists NONE of the resolved chain →
    # definitively no reachable valid model. A stale/errored/empty probe returns
    # None here and never flips readiness (fail soft).
    available = _fresh_available_models()
    if available is not None and chain and not any(m in available for m in chain):
        ready = False
        reasons.append("no_supported_model")

    # A live hard-failure whose category means the core is persistently unusable,
    # with no secondary backup, is not ready. Transient categories (timeout,
    # connection, rate_limited, provider_5xx) do NOT flip readiness.
    reachable = _LAST_REASONING_OUTCOME["reachable"]
    last_category = _LAST_REASONING_OUTCOME["error_category"]
    _persistent = {"not_configured", "unsupported_model", "authentication",
                   "invalid_configuration", "insufficient_balance"}
    if reachable is False and last_category in _persistent and not fallback_exists:
        ready = False
        reasons.append(f"reasoning_{last_category}")

    return {
        "ready": ready,
        "provider": provider,
        "configured": configured,
        "model_chain": chain,
        "fallback_exists": fallback_exists,
        "reasons": reasons,
        "reasoning_provider": get_reasoning_health(),
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

    redacted_message = _redact_secrets(str(exc))[:_ERROR_MESSAGE_MAX_CHARS]
    return {
        "error_type": exc.__class__.__name__,
        # Canonical ERROR_CATEGORIES value (item 1) — the single field callers use
        # as error_category, never the raw class name.
        "error_category": categorize_error(
            status_code=status_code,
            error_type=exc.__class__.__name__,
            provider_error_code=provider_error_code,
            message=redacted_message,
        ),
        "message": redacted_message,
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
    attempts: Optional[list] = None,
) -> Dict[str, Any]:
    # Raw exception class (kept for diagnostics + the long-standing "error" field).
    error_type = last_error.get("error_type") if last_error else "UnknownAIError"
    _status = (last_error or {}).get("status_code")
    _provider_err = (last_error or {}).get("provider_error_code")
    _msg = (last_error or {}).get("message")
    # Canonical ERROR_CATEGORIES value (item 1) — never the raw class. Prefer the
    # category already computed on the error; else derive it; a missing key wins.
    key_present = _provider_key_present(provider)
    error_category = (last_error or {}).get("error_category") or categorize_error(
        status_code=_status, error_type=error_type,
        provider_error_code=_provider_err, message=_msg, key_present=key_present,
    )
    if not key_present:
        error_category = "not_configured"
    _model_attempted = (models_tried or [primary_model])[-1]
    # Deterministic upgrade: if a fresh /models probe says this id is absent, the
    # failure IS unsupported_model (guessing → knowing).
    if is_model_supported(_model_attempted, provider) is False:
        error_category = "unsupported_model"

    payload = {
        "success": False,
        "type": f"{provider}_error_fallback",
        "response_source": "fallback",
        # Distinct, machine-readable code so a dead core AI is never mistaken for
        # a benign keyword/free-mode fallback (reasoning-observability).
        "error_code": "reasoning_provider_unavailable",
        "provider_state": "degraded",
        # "error" stays the raw class for backward-compat; "error_category" is the
        # canonical vocabulary value.
        "error": error_type,
        "error_category": error_category,
        "error_detail": last_error,
        "text": _FALLBACK_TEXT,
        "fallback_model": fallback_model,
        **_base_payload(provider, primary_model),
    }
    if models_tried:
        payload["models_tried"] = models_tried
    if attempts:
        payload["attempts"] = attempts
    if provider == "deepseek":
        payload["deepseek_model"] = primary_model
    else:
        payload["openai_model"] = primary_model
    # Record + log loudly: the core reasoning capability is DOWN. Names,
    # categories, status codes and model identifiers only — the message is
    # secret-redacted, never a key value.
    _last_elapsed = attempts[-1].get("elapsed_ms") if attempts else None
    _record_reasoning_outcome(
        provider,
        reachable=False,
        error_category=error_category,
        status_code=_status,
        provider_error_code=_provider_err,
        message=_msg,
        model_attempted=_model_attempted,
        elapsed_ms=_last_elapsed,
        attempts=attempts,
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

    import time as _time

    last_error: Optional[Dict[str, Any]] = None
    if active_provider == "deepseek":
        model_attempts = _deepseek_model_chain()
    else:
        model_attempts = [primary_model]
        if fallback_model and fallback_model != primary_model:
            model_attempts.append(fallback_model)
    # Advisory /models skip (fresh successful probe only; never empties the chain).
    model_attempts = _advisory_chain(model_attempts, active_provider)

    models_tried: list = []
    # Per-attempt telemetry — the model tried, how long it took, how it failed.
    attempts: list = []

    for model in model_attempts:
        models_tried.append(model)
        _started = _time.monotonic()
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

            _elapsed = int((_time.monotonic() - _started) * 1000)
            attempts.append({"model": model, "elapsed_ms": _elapsed,
                             "category": None, "status_code": None, "ok": True})
            _record_reasoning_outcome(
                active_provider, reachable=True, model_attempted=model,
                elapsed_ms=_elapsed, attempts=attempts,
            )
            return {
                "success": True,
                "response_source": active_provider,
                "provider": active_provider,
                "model": model,
                "text": text,
                "attempts": attempts,
                "profile_context_present": profile_present,
                **_base_payload(active_provider, model),
            }

        except Exception as exc:
            _elapsed = int((_time.monotonic() - _started) * 1000)
            last_error = _safe_openai_error(exc)
            _status = last_error.get("status_code")
            # Canonical category, upgraded to unsupported_model when a fresh probe
            # deterministically says this id is absent.
            _category = last_error.get("error_category") or "unknown"
            if is_model_supported(model, active_provider) is False:
                _category = "unsupported_model"
            attempts.append({"model": model, "elapsed_ms": _elapsed,
                             "category": _category, "status_code": _status, "ok": False})
            is_rate_limit = _category == "rate_limited"
            log_level = (
                "Rico AI provider rate limited — skipping retry"
                if is_rate_limit
                else f"Rico AI model {model!r} failed ({_category}) — trying next"
            )
            logger.warning(
                log_level,
                extra={
                    "provider": active_provider,
                    "error_type": last_error.get("error_type"),
                    "error_category": _category,
                    "status_code": _status,
                    "model": model,
                    "elapsed_ms": _elapsed,
                    "smoke": smoke,
                    "profile_context_present": profile_present,
                },
            )
            if is_rate_limit:
                payload = _rate_limited_payload(last_error, active_provider, model)
                payload["profile_context_present"] = profile_present
                payload["is_rate_limited"] = True
                payload["attempts"] = attempts
                # Rate-limited = reachable (auth OK, throttled), not "unusable".
                _record_reasoning_outcome(
                    active_provider, reachable=True,
                    error_category="rate_limited", model_attempted=model,
                    elapsed_ms=_elapsed, attempts=attempts,
                )
                return payload
            # For every other category (unsupported_model, authentication, timeout,
            # connection, provider_5xx, response_contract …) continue to next model.

    payload = _failure_payload(
        last_error, active_provider, primary_model, fallback_model,
        models_tried=models_tried, attempts=attempts,
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
    # Advisory /models skip (fresh successful probe only; never empties the chain).
    model_attempts = _advisory_chain(model_attempts, active_provider)

    last_error: Optional[Dict[str, Any]] = None
    attempts: list = []
    for model in model_attempts:
        started = time.monotonic()
        produced = False
        frames = 0
        first_frame_ms: Optional[int] = None
        try:
            if active_provider == "deepseek":
                stream = client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=_DEFAULT_MAX_OUTPUT_TOKENS, stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        if not produced:
                            first_frame_ms = int((time.monotonic() - started) * 1000)
                        produced = True
                        frames += 1
                        yield delta.content
            else:
                stream = client.responses.create(
                    model=model, input=messages,
                    max_output_tokens=_DEFAULT_MAX_OUTPUT_TOKENS, stream=True,
                )
                for event in stream:
                    text = getattr(getattr(event, "delta", None), "text", None) or ""
                    if text:
                        if not produced:
                            first_frame_ms = int((time.monotonic() - started) * 1000)
                        produced = True
                        frames += 1
                        yield text
            if produced:
                _elapsed = int((time.monotonic() - started) * 1000)
                attempts.append({"model": model, "elapsed_ms": _elapsed, "category": None,
                                 "status_code": None, "ok": True,
                                 "frames": frames, "first_frame_ms": first_frame_ms})
                # Streamed a real answer. Record frame count + first-frame latency:
                # the ONLY signal that distinguishes real incremental streaming from
                # a single buffered blob served under a 200 (the production defect).
                _record_reasoning_outcome(
                    active_provider, reachable=True, model_attempted=model,
                    elapsed_ms=_elapsed, attempts=attempts,
                )
                _LAST_REASONING_OUTCOME["stream_frames"] = frames
                _LAST_REASONING_OUTCOME["first_frame_ms"] = first_frame_ms
                return
            # Empty stream (no tokens) → response-contract failure; hop to next model.
            last_error = {"error_type": "EmptyStream", "error_category": "response_contract",
                          "status_code": None, "provider_error_code": None,
                          "message": "empty stream"}
            attempts.append({"model": model,
                             "elapsed_ms": int((time.monotonic() - started) * 1000),
                             "category": "response_contract", "status_code": None,
                             "ok": False, "frames": 0, "first_frame_ms": None})
        except Exception as exc:
            _elapsed = int((time.monotonic() - started) * 1000)
            last_error = _safe_openai_error(exc)
            last_error["elapsed_ms"] = _elapsed
            _category = last_error.get("error_category") or "unknown"
            if is_model_supported(model, active_provider) is False:
                _category = "unsupported_model"
            attempts.append({"model": model, "elapsed_ms": _elapsed, "category": _category,
                             "status_code": last_error.get("status_code"), "ok": False,
                             "frames": frames, "first_frame_ms": first_frame_ms})
            if produced:
                # Tokens already sent to the client; we cannot cleanly restart on
                # another model. Record the partial and stop.
                _record_reasoning_outcome(
                    active_provider, reachable=True, model_attempted=model,
                    error_category=_category, status_code=last_error.get("status_code"),
                    elapsed_ms=_elapsed, attempts=attempts,
                )
                _LAST_REASONING_OUTCOME["stream_frames"] = frames
                _LAST_REASONING_OUTCOME["first_frame_ms"] = first_frame_ms
                return
            # No tokens yet → a timeout/400/connection failure is safe to hop on.
            continue

    # Every model failed before producing a token → one honest, logged fallback
    # (no silent empty stream).
    _category = (last_error or {}).get("error_category") or "unknown"
    _last_model = (model_attempts[-1] if model_attempts else None)
    if _last_model is not None and is_model_supported(_last_model, active_provider) is False:
        _category = "unsupported_model"
    _record_reasoning_outcome(
        active_provider, reachable=False,
        error_category=_category,
        status_code=(last_error or {}).get("status_code"),
        provider_error_code=(last_error or {}).get("provider_error_code"),
        message=(last_error or {}).get("message"),
        model_attempted=_last_model,
        elapsed_ms=(last_error or {}).get("elapsed_ms"),
        attempts=attempts,
    )
    _LAST_REASONING_OUTCOME["stream_frames"] = 0
    logger.error(
        "reasoning_stream_unavailable provider=%s error_category=%s status_code=%s "
        "models_tried=%s — streaming chain exhausted; served honest fallback",
        active_provider, _category, (last_error or {}).get("status_code"), model_attempts,
    )
    yield _FALLBACK_TEXT
