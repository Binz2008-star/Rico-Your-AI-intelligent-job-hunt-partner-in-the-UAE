"""src/agent/intelligence/engineering_review_mode.py
Scoped "Engineering Review Mode" behavior for Rico.

This module is intentionally SEPARATE from Rico's career-agent identity
(`src/rico_identity.py`) and from the user-facing chat intent routers
(`src/rico_intent_router.py`, `src/agent/intelligence/intent_classifier.py`).

Boundary (non-negotiable):
  - This behavior is for repository / engineering review contexts ONLY:
    pull requests, CI logs, branches, diffs, merge/split/block decisions,
    and repo engineering questions.
  - It MUST NOT activate for normal Rico career chat: job search, CV upload,
    application tracking, interview prep, subscription/billing, onboarding,
    or profile conversations.

It is OPT-IN: nothing here is wired into the live job-seeker chat path, and it
does NOT modify `get_rico_system_prompt`. A caller that knows it is operating in
an engineering/repo-review surface can import `get_engineering_review_prompt()`
to obtain the scoped system-prompt section, or use
`is_engineering_review_context()` / `maybe_review_prompt_section()` to gate it
deterministically on the incoming message.

Public API:
  is_engineering_review_context(message, signals=None) -> bool
  maybe_review_prompt_section(message, signals=None) -> str
  get_engineering_review_prompt() -> str
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# ── Scoped behavior text ──────────────────────────────────────────────────────

# Risk-based PR triage rules. This is a SCOPED section, never the global Rico
# personality. It is only meaningful when an engineering/repo-review context is
# detected (see is_engineering_review_context).
ENGINEERING_REVIEW_BEHAVIOR = """\
Engineering Review Mode (repository work only)

This mode applies ONLY to repository / engineering review. It never applies to
job-seeker conversations (job search, CV, applications, interviews, billing).

When reviewing engineering work, use risk-based PR triage.

For every proposed branch or PR:
1. Identify the scope category:
   frontend/i18n, backend/schema, job search, scoring, lifecycle/apply,
   billing/auth, security, workers/notifications, or cleanup.
2. Determine risk level: low, medium, high, or blocked.
3. Check whether the PR has one clear purpose.
4. If it mixes unrelated scopes, recommend splitting it into smaller PRs.
5. Never approve auto-apply, billing, auth, database migration, or lifecycle
   changes when bundled with unrelated work.
6. Link the work to the correct GitHub issue or epic.
7. Require CI/build/tests appropriate to the touched area.
8. Recommend merge order based on dependencies.
9. Prefer small PRs from latest main.
10. Never merge all PRs at once.
11. For old or deleted-upstream branches, salvage only selected changes onto
    fresh branches from origin/main.
12. For apply-related work, preserve approval-gated submission. Rico may
    prepare, score, track, and open links, but must not submit applications
    without explicit user approval."""

# Pre-merge gates checklist (required checks before recommending MERGE).
ENGINEERING_REVIEW_GATES = """\
Before recommending MERGE, require:
- CI green
- changed files match the stated scope
- no unrelated files
- no auto-apply bypass
- no backend touched if the PR is frontend-only
- no frontend touched if the PR is backend-only
- merge one PR at a time (never all at once)"""

# Mandatory output shape for any triage decision.
DECISION_TEMPLATE = """\
Always respond using this exact decision template:

Decision: MERGE / SPLIT / BLOCK / DEFER

Reason:
- ...

Scope allowed:
- ...

Scope not allowed:
- ...

Required checks:
- ...

Merge order:
1. ...
2. ..."""


def get_engineering_review_prompt() -> str:
    """Return the full scoped Engineering Review Mode system-prompt section.

    Intended to be injected as an ADDITIONAL system-prompt section by an
    engineering/repo-review surface — not appended to the career-agent prompt
    used by normal job-seeker chat.
    """
    return f"{ENGINEERING_REVIEW_BEHAVIOR}\n\n{ENGINEERING_REVIEW_GATES}\n\n{DECISION_TEMPLATE}"


# ── Context detection (deterministic) ─────────────────────────────────────────

# Authoritative engineering references: if present, this is engineering review
# regardless of any career vocabulary in the same message.
_PR_REF_RE = re.compile(
    r"\bpull\s+requests?\b"
    r"|\bPR\s*#?\d+\b"
    r"|#\d+\b"
    r"|\b(?:this|that|the|your|my)\s+PRs?\b",
    re.IGNORECASE,
)

# Strong engineering signals. Unambiguous repo/CI/VCS vocabulary that is
# effectively never present in career chat.
_STRONG_ENG_RE = re.compile(
    r"\bPRs?\b"
    r"|\bgit(?:hub)?\b"
    r"|\bbranch(?:es)?\b"
    r"|\brebas(?:e|ing)\b"
    r"|\bcherry[\s-]?pick\b"
    r"|\bsquash\b"
    r"|\bmerge\s+conflicts?\b"
    r"|\bdiffs?\b"
    r"|\bcommits?\b"
    r"|\bcode\s+review\b"
    r"|\bchanged\s+files?\b"
    r"|\bCI\b"
    r"|\bpipelines?\b"
    r"|\bgithub\s+actions?\b"
    r"|\bworkflow\s+runs?\b"
    r"|\bbuild\s+(?:is\s+)?(?:failing|failed|broken|green|red|passing)\b"
    r"|\bchecks?\s+(?:are\s+)?(?:failing|passing|green|red)\b",
    re.IGNORECASE,
)

# Triage decision verbs. Ambiguous on their own ("block"/"skip" are job actions
# in Rico), so they only count as engineering when paired with a repo signal.
_DECISION_VERB_RE = re.compile(
    r"\b(?:merge|split|block|defer|rebase|squash)\b",
    re.IGNORECASE,
)
_REPO_HINT_RE = re.compile(
    r"\bbranch(?:es)?\b|\bdiffs?\b|\bmain\b|\bupstream\b|\borigin\b|\brepo(?:sitory)?\b",
    re.IGNORECASE,
)

# Career veto vocabulary. If any of these appear (and there is no authoritative
# PR reference), the message is treated as career chat and the mode stays OFF.
# Bias is intentionally toward NOT activating, so career chat is never hijacked.
_CAREER_VETO_RE = re.compile(
    r"\bjobs?\b|\bvacanc(?:y|ies)\b|\bopenings?\b|\bhiring\b|\brecruiters?\b"
    r"|\broles?\b|\bpositions?\b"
    r"|\bcv\b|\bresum[eé]s?\b|\bcover\s+letters?\b"
    r"|\bapply(?:ing)?\s+(?:for|to)\b|\bapplications?\b|\bapplied\s+(?:to|for)\b"
    r"|\binterviews?\b"
    r"|\bsalar(?:y|ies)\b|\bcompensation\b"
    r"|\bsubscriptions?\b|\bbilling\b|\binvoices?\b|\bcheckout\b"
    r"|\bupgrade\s+my\s+plan\b|\bmy\s+(?:profile|subscription|plan)\b"
    r"|\bonboarding\b",
    re.IGNORECASE,
)

# Structured signal keys a caller may pass to force activation when it already
# knows it is in an engineering/repo surface (e.g., a GitHub PR webhook handler).
_ENGINEERING_SIGNAL_KEYS = frozenset({
    "pr", "pull_request", "is_pr", "ci", "diff", "branch",
    "github", "code_review", "review", "commit", "repo",
})


def _has_structured_signal(signals: Optional[Iterable[str]]) -> bool:
    """True if any caller-provided signal token denotes an engineering context."""
    if not signals:
        return False
    try:
        return any(str(s).strip().lower() in _ENGINEERING_SIGNAL_KEYS for s in signals)
    except TypeError:
        return False


def is_engineering_review_context(
    message: str,
    signals: Optional[Iterable[str]] = None,
) -> bool:
    """Return True only for repository / engineering review contexts.

    Deterministic precedence (safety-first — defaults to OFF):
      1. Caller-provided structured signals (authoritative).
      2. Explicit PR reference ("pull request", "this PR", "#123") — authoritative.
      3. Any career vocabulary present -> OFF (never hijack job-seeker chat).
      4. Strong engineering vocabulary present -> ON.
      5. A triage decision verb paired with a repo hint -> ON.
      6. Otherwise -> OFF.

    Never raises.
    """
    text = message or ""

    if _has_structured_signal(signals):
        return True

    if _PR_REF_RE.search(text):
        logger.debug("review_mode_context source=pr_ref")
        return True

    if _CAREER_VETO_RE.search(text):
        return False

    if _STRONG_ENG_RE.search(text):
        logger.debug("review_mode_context source=strong_eng")
        return True

    if _DECISION_VERB_RE.search(text) and _REPO_HINT_RE.search(text):
        logger.debug("review_mode_context source=decision+repo")
        return True

    return False


def maybe_review_prompt_section(
    message: str,
    signals: Optional[Iterable[str]] = None,
) -> str:
    """Return the scoped review prompt if (and only if) the context matches.

    Returns "" for career / non-engineering messages, so a caller can safely do:

        system_prompt = base_prompt + maybe_review_prompt_section(user_message)

    without ever polluting normal job-seeker conversations.
    """
    if is_engineering_review_context(message, signals):
        return get_engineering_review_prompt()
    return ""
