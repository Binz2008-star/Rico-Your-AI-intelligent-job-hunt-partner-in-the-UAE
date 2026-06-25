"""Context-Aware Response Formatting for Rico chat replies.

A small, deterministic *presentation* layer: it composes polished Markdown
``message`` text for the contexts where structure aids clarity (status/PR/CI
reports, job summaries, step-by-step instructions, safe errors) and otherwise
leaves casual replies untouched.

This module contains NO business logic. It never decides routing, scoring,
trust, persistence, auth, or provider behavior — callers pass already-decided
data in and get formatted text out. It adds no LLM dependency.

Design rules (mirrors the product spec):
  * Markdown only when it improves clarity; casual text passes through unchanged.
  * Bold for the key decision / blocker / main issue only — not decoration.
  * Tables for comparisons / status / job summaries; code formatting for IDs,
    SHAs, filenames, commands, endpoints, env vars, exact values.
  * UPPERCASE labels only for short critical states (DO NOT MERGE, BLOCKED, …).
  * No emojis in serious/technical responses.
  * Language follows the caller (``"en"`` / ``"ar"``); Arabic gets Arabic labels
    and is never silently switched to English.
  * A plain-text fallback is available when the client can't render Markdown.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "inline_code",
    "code_block",
    "bold",
    "md_table",
    "format_status_report",
    "format_job_summary",
    "format_action_steps",
    "format_safe_error",
    "apply_context_formatting",
]

# Apply-link trust labels (display only — the trust decision is made upstream
# by the #747 gate; this layer only renders the already-resolved status).
_APPLY_STATUS_LABELS = {
    "en": {
        "verified": "Verified",
        "unverified": "Unverified",
        "blocked": "Blocked",
        "unavailable": "Unavailable",
    },
    "ar": {
        "verified": "موثّق",
        "unverified": "غير مُتحقَّق",
        "blocked": "محظور",
        "unavailable": "غير متوفر",
    },
}

_LABELS = {
    "en": {
        "decision": "Decision",
        "role": "Role",
        "company": "Company",
        "location": "Location",
        "match": "Match",
        "apply_link": "Apply link",
        "field": "Field",
        "value": "Value",
        "next": "Next",
        "reference": "Reference",
    },
    "ar": {
        "decision": "القرار",
        "role": "الدور",
        "company": "الشركة",
        "location": "الموقع",
        "match": "التطابق",
        "apply_link": "رابط التقديم",
        "field": "الحقل",
        "value": "القيمة",
        "next": "التالي",
        "reference": "المرجع",
    },
}

# Critical state words that may be rendered as UPPERCASE labels.
_CRITICAL_STATES = frozenset({
    "do not merge", "do_not_merge", "blocked", "urgent", "ready", "merge",
})

_ARABIC_RE = re.compile(r"[؀-ۿ]")


def _lang(language: Optional[str]) -> str:
    """Normalize to a supported language code, defaulting to English."""
    return "ar" if (language or "").lower().startswith("ar") else "en"


def detect_language(text: str) -> str:
    """Best-effort language hint from text (Arabic vs English). Deterministic."""
    return "ar" if _ARABIC_RE.search(text or "") else "en"


# ── Primitive inline/block helpers ────────────────────────────────────────────

def inline_code(value: Any) -> str:
    """Wrap a value (SHA, id, filename, command, endpoint, env var) in backticks.

    Empty values render as an em dash so a table cell never collapses.
    """
    text = "" if value is None else str(value)
    if not text.strip():
        return "—"
    return f"`{text}`"


def code_block(text: str, lang: str = "") -> str:
    """Fence a block of copy-paste text (command, payload, SQL, JSON, log)."""
    body = (text or "").rstrip("\n")
    return f"```{lang}\n{body}\n```"


def bold(text: str) -> str:
    """Bold a short, important span (key decision, blocker, main issue)."""
    t = (text or "").strip()
    return f"**{t}**" if t else ""


def _critical_label(text: str) -> str:
    """Render a recognized critical state as an UPPERCASE bold label.

    Only fires for known short states (DO NOT MERGE, BLOCKED, READY, …); any
    other text is returned bolded but unchanged so prose is never shouted.
    """
    key = (text or "").strip().lower()
    if key in _CRITICAL_STATES:
        return f"**{text.strip().upper()}**"
    return bold(text)


def _escape_cell(value: Any) -> str:
    """Make a value safe inside a Markdown table cell (escape pipes/newlines)."""
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("|", "\\|").strip()
    return text or "—"


def md_table(headers: Sequence[str], rows: Iterable[Sequence[Any]], *, markdown: bool = True) -> str:
    """Render a GitHub-flavored Markdown table, or a readable plain fallback.

    When ``markdown`` is False (client can't render tables), emit aligned
    ``key: value`` lines instead so the content stays legible.
    """
    headers = list(headers)
    rows = [list(r) for r in rows]
    if not markdown:
        lines = []
        for r in rows:
            # A 2-column table is almost always key/value → render "key: value".
            # Wider tables fall back to "header: cell" pairs joined with " · ".
            if len(headers) == 2 and len(r) >= 2:
                lines.append(f"{_escape_cell(r[0])}: {_escape_cell(r[1])}")
            else:
                parts = [f"{headers[i]}: {_escape_cell(c)}" for i, c in enumerate(r) if i < len(headers)]
                lines.append(" · ".join(parts))
        return "\n".join(lines)
    head = "| " + " | ".join(_escape_cell(h) for h in headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join(
        "| " + " | ".join(_escape_cell(c) for c in r) + " |" for r in rows
    )
    return "\n".join([head, sep, body]) if body else "\n".join([head, sep])


# ── Context formatters ────────────────────────────────────────────────────────

def format_status_report(
    title: str,
    rows: Sequence[Sequence[Any]],
    *,
    decision: Optional[str] = None,
    headers: Optional[Sequence[str]] = None,
    commands: Optional[Sequence[str]] = None,
    language: str = "en",
    markdown: bool = True,
) -> str:
    """Format a PR / CI / status report: a status table + a bold final decision.

    ``rows`` are ``(field, value)`` pairs by default; pass ``headers`` for a
    custom table shape. Values that look like SHAs/branches/paths should already
    be wrapped via :func:`inline_code` by the caller, or pass plain strings.
    ``commands`` are rendered as a fenced shell block beneath the table.
    """
    lang = _lang(language)
    L = _LABELS[lang]
    hdrs = list(headers) if headers else [L["field"], L["value"]]
    parts: list[str] = []
    if title:
        parts.append(f"## {title.strip()}")
    parts.append(md_table(hdrs, rows, markdown=markdown))
    if decision:
        parts.append(f"{bold(L['decision'])}: {_critical_label(decision)}")
    if commands:
        parts.append(code_block("\n".join(commands), "bash"))
    return "\n\n".join(p for p in parts if p)


def _apply_status_text(job: Mapping[str, Any], lang: str) -> str:
    """Resolve the apply-link display label without over-promoting it.

    The trust decision is upstream (#747). Here we only map an already-resolved
    status to a neutral label. An unverified/blocked/unavailable link is shown
    as a plain status word — never a bolded or prominently-linked call to action.
    """
    raw = str(job.get("apply_status") or job.get("verification_status") or "").strip().lower()
    labels = _APPLY_STATUS_LABELS[lang]
    if raw in ("verified", "trusted", "ok"):
        url = str(job.get("apply_url") or "").strip()
        # Only a verified link may be surfaced as an actual link.
        return f"{labels['verified']}: {url}" if url else labels["verified"]
    if raw in ("blocked",):
        return labels["blocked"]
    if raw in ("unverified", "lead", "unconfirmed"):
        return labels["unverified"]
    return labels["unavailable"]


def format_job_summary(
    job: Mapping[str, Any],
    *,
    language: str = "en",
    markdown: bool = True,
) -> str:
    """Format a single job as a compact card: title line + a match table.

    Structured fields only (role/company/location/match/apply link). The apply
    link is rendered as a neutral status label; an unverified link is never
    bolded or visually promoted.
    """
    lang = _lang(language)
    L = _LABELS[lang]
    title = str(job.get("title") or job.get("role") or "").strip()
    company = str(job.get("company") or "").strip()
    location = str(job.get("location") or "").strip()
    match = job.get("match") or job.get("score")

    header = bold(title) if title else ""
    if company:
        header = f"{header} — {company}" if header else company

    rows: list[list[str]] = []
    if title:
        rows.append([L["role"], title])
    if company:
        rows.append([L["company"], company])
    if location:
        rows.append([L["location"], location])
    if match not in (None, ""):
        match_str = f"{match}%" if isinstance(match, (int, float)) else str(match)
        rows.append([L["match"], match_str])
    # Apply link is always shown as a neutral status (last row), never bolded.
    rows.append([L["apply_link"], _apply_status_text(job, lang)])

    parts = [header] if header else []
    parts.append(md_table([L["field"], L["value"]], rows, markdown=markdown))
    return "\n\n".join(p for p in parts if p)


def format_action_steps(
    steps: Sequence[Any],
    *,
    next_action: Optional[str] = None,
    language: str = "en",
) -> str:
    """Format step-by-step user instructions as a numbered list.

    A step may be a plain string, or a ``(text, command)`` pair / mapping with a
    ``command`` — the command is rendered in a fenced block under the step.
    Ends with a bold "next required action" line when provided.
    """
    lang = _lang(language)
    L = _LABELS[lang]
    lines: list[str] = []
    for i, step in enumerate(steps, 1):
        text, command = _split_step(step)
        lines.append(f"{i}. {text}".rstrip())
        if command:
            lines.append(code_block(command, "bash"))
    out = "\n".join(lines)
    if next_action:
        out = f"{out}\n\n{bold(L['next'])}: {next_action.strip()}"
    return out


def _split_step(step: Any) -> tuple[str, str]:
    """Normalize a step into ``(text, command)``."""
    if isinstance(step, Mapping):
        return str(step.get("text") or step.get("step") or "").strip(), str(step.get("command") or "").strip()
    if isinstance(step, (tuple, list)) and len(step) == 2:
        return str(step[0]).strip(), str(step[1]).strip()
    return str(step).strip(), ""


# Patterns that look like raw internal error detail and must not reach the user.
_RAW_ERROR_RE = re.compile(
    r"traceback|\bexception\b|psycopg2|sqlstate|operationalerror|"
    r"stack trace|at 0x[0-9a-f]+|file \".*\", line \d+|\berrno\b",
    re.IGNORECASE,
)


def format_safe_error(
    message: str,
    *,
    reference: Optional[str] = None,
    language: str = "en",
    fallback: Optional[str] = None,
) -> str:
    """Format a user-safe error: a short, bold main issue — never raw internals.

    If *message* looks like a raw internal error (stack trace, driver error,
    SQLSTATE, …) it is replaced with a safe generic message so nothing leaks.
    An optional ``reference`` (debug id) is appended in code formatting.
    """
    lang = _lang(language)
    L = _LABELS[lang]
    safe_default = fallback or (
        "حدث خطأ غير متوقع. حاول مرة أخرى بعد قليل."
        if lang == "ar" else
        "Something went wrong. Please try again in a moment."
    )
    text = (message or "").strip()
    if not text or _RAW_ERROR_RE.search(text):
        text = safe_default
    out = bold(text)
    if reference:
        out = f"{out}\n\n{L['reference']}: {inline_code(reference)}"
    return out


# ── Generic dispatcher ────────────────────────────────────────────────────────

def apply_context_formatting(
    response_type: str,
    data: Mapping[str, Any],
    language: str = "en",
) -> str:
    """Route to the right formatter by *response_type*.

    Casual / conversational replies pass through unchanged (no over-formatting).
    Unknown types fall back to the raw ``message`` text, so this is always safe
    to call as a thin presentation wrapper.
    """
    rtype = (response_type or "").strip().lower()
    data = dict(data or {})

    if rtype in ("status_report", "pr_status", "ci_status"):
        return format_status_report(
            data.get("title", ""),
            data.get("rows", []),
            decision=data.get("decision"),
            headers=data.get("headers"),
            commands=data.get("commands"),
            language=language,
            markdown=data.get("markdown", True),
        )
    if rtype in ("job_summary", "job_card"):
        return format_job_summary(data, language=language, markdown=data.get("markdown", True))
    if rtype in ("action_steps", "instructions"):
        return format_action_steps(
            data.get("steps", []),
            next_action=data.get("next_action"),
            language=language,
        )
    if rtype in ("error", "safe_error"):
        return format_safe_error(
            data.get("message", ""),
            reference=data.get("reference") or data.get("debug_id"),
            language=language,
        )
    # casual / chat / unknown → leave the natural text untouched.
    return str(data.get("message", "")).strip()
