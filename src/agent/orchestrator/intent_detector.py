"""
src/agent/orchestrator/intent_detector.py
Deterministic keyword-based intent detection.
No LLM calls, no embeddings — pure string matching ordered by specificity.

Each intent maps to a single canonical tool name in the registry.
Add entries to INTENT_PATTERNS to extend without touching the orchestrator.

Bilingual (EN/AR): messages are normalized before matching — lowercased, and
Arabic text is canonicalized (diacritics/tatweel stripped, alef/hamza variants
unified, ة→ه, ى→ي) so keyword matching is insensitive to common orthographic
variation. Table keywords pass through the same normalization at module load,
so they may be written naturally (with ة/ئ/أ) — both sides always compare in
one canonical form.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Tashkeel (harakat), Quranic annotation marks, and tatweel (ـ).
_AR_DIACRITICS_RE = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")

# Orthographic variants folded to one canonical form. Matches the message side
# only — table keywords are pre-normalized by convention (see module docstring).
_AR_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
})


def _normalize(message: str) -> str:
    """Lowercase + canonicalize Arabic orthography for keyword matching."""
    text = (message or "").lower().strip()
    text = _AR_DIACRITICS_RE.sub("", text)
    return text.translate(_AR_FOLD)


# Intent → (tool_name, list_of_trigger_keywords)
# First match wins — order by specificity (most specific first).
# Arabic keywords are pre-normalized (see _normalize / module docstring).
_INTENT_TABLE: list[Tuple[str, str, list[str]]] = [
    (
        "trigger_pipeline",
        "trigger_pipeline",
        [
            "trigger", "run pipeline", "start pipeline", "kick off", "run now",
            # AR: run/start the pipeline
            "شغل البايبلاين", "تشغيل البايبلاين", "ابدا البايبلاين", "شغل خط الوظائف",
        ],
    ),
    (
        "get_pipeline_status",
        "get_pipeline_status",
        [
            "pipeline", "last run", "pipeline status", "schedule", "when did",
            # AR: pipeline / last run / status of the pipeline
            "بايبلاين", "اخر تشغيل", "حاله الخط", "متي اشتغل",
        ],
    ),
    (
        "get_application_stats",
        "get_application_stats",
        [
            "stats", "statistics", "how many", "applications", "progress",
            "report", "summary", "success rate", "interview", "rejection",
            # AR: statistics / my applications / report / interviews / rejection
            "احصائيات", "احصاءات", "كم طلب", "طلباتي", "تقرير", "ملخص",
            "نسبه النجاح", "مقابله", "مقابلات", "رفض", "تقدمي",
        ],
    ),
    (
        "get_ranked_jobs",
        "get_ranked_jobs",
        [
            "best jobs", "top jobs", "ranked", "today", "new jobs",
            "show jobs", "show me", "list jobs", "any jobs", "what jobs",
            "jobs today", "find jobs", "search", "match",
            # AR: best jobs / new jobs / show jobs / vacancies / search
            "افضل الوظائف", "وظائف اليوم", "وظائف جديده", "اعرض الوظائف",
            "وريني الوظائف", "ورني الوظائف", "اي وظائف", "وظائف", "وظيفه",
            "شواغر", "فرص عمل", "ابحث", "بحث", "دور لي",
        ],
    ),
]

# Normalize the table's own keywords at load time so keyword and message are
# guaranteed to share one canonical form — table authors may then write Arabic
# keywords naturally (with ة/ئ/أ) without matching ever depending on it.
_INTENT_TABLE = [
    (intent, tool, [_normalize(kw) for kw in keywords])
    for intent, tool, keywords in _INTENT_TABLE
]

_FALLBACK_INTENT = "help"
_FALLBACK_TOOL: Optional[str] = None   # help has no tool


def detect(message: str) -> Tuple[str, Optional[str]]:
    """
    Return (intent_name, tool_name_or_None) for the given message.
    Falls back to ("help", None) when nothing matches.
    Bilingual: English and Arabic keywords are matched against the
    orthography-normalized message (see _normalize).
    """
    normalized = _normalize(message)
    for intent, tool, keywords in _INTENT_TABLE:
        if any(kw in normalized for kw in keywords):
            return intent, tool
    return _FALLBACK_INTENT, _FALLBACK_TOOL


# ── Supported actions (for action-execution path) ─────────────────────────────

# Maps action.type → tool_name
ACTION_TO_TOOL: dict[str, str] = {
    "apply":            "apply_job",
    "skip":             "skip_job",
    "not_relevant":     "skip_job",       # semantic alias; same side effect
    "save":             "save_job",
    "block":            "block_company",
    "trigger_pipeline": "trigger_pipeline",
    "draft":            "draft_message",
    "why":              "explain_match",
    "remind":           "set_reminder",
}

VALID_ACTION_TYPES = frozenset(ACTION_TO_TOOL)

# Tools that perform a global / system-wide side effect and must only run for an
# authenticated admin actor — regardless of the surface (HTTP action, agent-chat
# action, or NL-detected intent). Enforced at every execution chokepoint
# (runtime + orchestrator) with a fail-closed default. See #1093.
PRIVILEGED_TOOLS = frozenset({"trigger_pipeline"})
