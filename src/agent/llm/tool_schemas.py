"""Model-facing tool schemas — the wire-format half of the agent loop.

Rico already owns a working tool layer: ``src/agent/registry/tool_registry.py``
registers 12 tools and ``src/agent/runtime.py`` dispatches the mutating ones with
idempotency, audit logging and admin gating. What has never existed is the bridge
that lets the *model* choose one. This module is that bridge, and only that: it
maps tool names to JSON Schema, and tool names to the identifiers the rest of the
system already understands.

Three invariants are enforced here rather than left to the caller, because each
one is a safety property:

1. **Class A tools never expose job content.** A mutating tool takes ``job_ref``
   — an ordinal or an opaque job key — and nothing else. There is deliberately no
   ``apply_url``, ``title`` or ``company`` field, so a fabricated job has no
   channel through which to reach a real action. Resolution happens server-side
   against the caller's own grounded result set.

2. **Tool names are not safety-action names.** ``rico_safety.HIGH_IMPACT_ACTIONS``
   contains ``"apply"``; the registry tool is ``"apply_job"``.
   ``RicoSafetyGuard.check_action`` only lowercases and underscores its input, so
   passing a raw tool name through it returns ``allowed=True`` and the high-impact
   gate never fires. ``SAFETY_ACTION_FOR_TOOL`` is the required translation, and
   ``tests/test_tool_schema_contract.py`` pins it.

3. **Approval is never a model-supplied argument.** No schema below accepts an
   approval flag under any spelling. ``_APPROVAL_ARG_NAMES`` exists so callers can
   strip one defensively if a model invents it anyway.

Wire format is the OpenAI **Chat Completions** nested shape
(``{"type": "function", "function": {...}}``). Production runs DeepSeek through
``chat.completions.create``, which requires that shape — the flat Responses-API
shape used by the dormant ``RicoOpenAIAgent._tool_schemas`` does not work there.

This module has no production caller yet. It is imported only by its contract
tests until the loop that consumes it lands.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

# ── Dispatch classes ─────────────────────────────────────────────────────────
#
# Class A — mutating, job-shaped. MUST be dispatched via
# agent_runtime.handle_action(); the mapping below is tool name -> the `action`
# value that runtime already understands (see intent_detector.ACTION_TO_TOOL,
# which maps the same pairing in the opposite direction).
CLASS_A_ACTIONS: dict[str, str] = {
    "apply_job": "apply",
    "save_job": "save",
    "skip_job": "skip",
    "block_company": "block",
    "draft_message": "draft",
    "explain_match": "why",
    "set_reminder": "remind",
    "trigger_pipeline": "trigger_pipeline",
}

# Class B — read-only. No side effects, so no idempotency key is needed, but the
# loop still audits them: a read the model performed on its own initiative should
# be traceable.
CLASS_B_TOOLS: frozenset[str] = frozenset(
    {
        "search_jobs",
        "get_ranked_jobs",
        "get_pipeline_status",
        "get_application_stats",
    }
)

# Tools that act on a specific job and therefore require a resolvable job_ref.
_JOB_SCOPED_TOOLS: frozenset[str] = frozenset(
    {"apply_job", "save_job", "skip_job", "block_company", "draft_message", "explain_match", "set_reminder"}
)

# Global side effect — admin actors only, mirroring
# intent_detector.PRIVILEGED_TOOLS. Kept as its own constant so `schemas_for`
# can omit these before they cost a single prompt token for a normal user.
PRIVILEGED_TOOL_NAMES: frozenset[str] = frozenset({"trigger_pipeline"})

# ── Safety-action translation (invariant 2) ──────────────────────────────────
#
# Maps a registry tool name to the action name rico_safety.check_action expects.
# Only mutating tools appear; a tool absent from this map is not high-impact.
SAFETY_ACTION_FOR_TOOL: dict[str, str] = {
    "apply_job": "apply",
    "draft_message": "send_cover_letter",
}

# Argument names a model must never be able to set. The loop strips these before
# dispatch; no schema declares them, so their presence means the model invented one.
_APPROVAL_ARG_NAMES: frozenset[str] = frozenset(
    {"user_has_approved", "pre_approved", "approved", "confirmed", "user_confirmed"}
)

_JOB_REF_PROPERTY: dict[str, Any] = {
    "type": "string",
    "description": (
        "Which job to act on: either its position in the list just shown to the user "
        "(\"1\", \"2\", \"3\") or the job's exact id from a previous tool result. "
        "Never invent one."
    ),
}


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Build one Chat-Completions function definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _job_scoped(name: str, description: str) -> dict[str, Any]:
    return _fn(name, description, {"job_ref": dict(_JOB_REF_PROPERTY)}, ["job_ref"])


# ── The schema map ───────────────────────────────────────────────────────────
#
# Descriptions are one line each. The whole set is token budget the model pays on
# every turn, so it is asserted under a size ceiling by the contract tests.
LLM_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    # Class A — mutating
    "apply_job": _job_scoped(
        "apply_job",
        "Start an application for one job. Always requires the user's explicit approval first.",
    ),
    "save_job": _job_scoped("save_job", "Save one job to the user's tracker for later."),
    "skip_job": _job_scoped("skip_job", "Mark one job as skipped or not relevant."),
    "block_company": _job_scoped("block_company", "Exclude a job's company from all future results."),
    "draft_message": _job_scoped("draft_message", "Draft a tailored application message for one job."),
    "explain_match": _job_scoped("explain_match", "Explain why one job was recommended to this user."),
    "set_reminder": _job_scoped("set_reminder", "Set a follow-up reminder for one job."),
    "trigger_pipeline": _fn(
        "trigger_pipeline",
        "Start the job pipeline run manually. Administrators only.",
        {},
        [],
    ),
    # Class B — read-only
    "search_jobs": _fn(
        "search_jobs",
        "Search the user's available jobs, filtered by minimum match score.",
        {
            "min_score": {"type": "integer", "minimum": 0, "maximum": 100, "default": 0},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            "source": {"type": "string", "description": "Restrict to one job source."},
        },
        [],
    ),
    "get_ranked_jobs": _fn(
        "get_ranked_jobs",
        "Return the highest-scoring jobs for this user — the default 'show me the best jobs' answer.",
        {
            "min_score": {"type": "integer", "minimum": 0, "maximum": 100, "default": 60},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        [],
    ),
    "get_pipeline_status": _fn("get_pipeline_status", "Report the latest job pipeline run state.", {}, []),
    "get_application_stats": _fn(
        "get_application_stats",
        "Return aggregate statistics about this user's applications.",
        {},
        [],
    ),
}

# Hard ceiling on how many schemas may be sent in one request. Every schema is
# tokens on every turn of every conversation; 8 is enough to cover any single
# user intent and keeps the preamble small enough to stay cache-friendly.
MAX_SCHEMAS_PER_REQUEST = 8


def schemas_for(
    tool_names: Iterable[str] | None = None,
    *,
    actor_is_admin: bool = False,
    has_grounded_jobs: bool = True,
) -> list[dict[str, Any]]:
    """Return the tool definitions to send with one model request.

    Filtering is a cost control and a safety control at once:

    - Privileged tools are omitted for non-admin actors. The runtime would reject
      them anyway (fail-closed), but a tool the model cannot see is a tool it
      cannot spend tokens attempting.
    - Job-scoped tools are omitted when there is no grounded result set, because
      there is nothing for ``job_ref`` to resolve against — offering them invites
      a call that can only fail.

    Ordering is deterministic (registry-declaration order) so the serialized
    preamble is byte-stable across turns and can be prefix-cached.
    """
    requested = list(tool_names) if tool_names is not None else list(LLM_TOOL_SCHEMAS)

    selected: list[dict[str, Any]] = []
    for name in requested:
        schema = LLM_TOOL_SCHEMAS.get(name)
        if schema is None:
            continue
        if name in PRIVILEGED_TOOL_NAMES and not actor_is_admin:
            continue
        if name in _JOB_SCOPED_TOOLS and not has_grounded_jobs:
            continue
        selected.append(schema)

    return selected[:MAX_SCHEMAS_PER_REQUEST]


def serialize(schemas: list[dict[str, Any]]) -> str:
    """Serialize schemas deterministically, for size checks and cache stability."""
    return json.dumps(schemas, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_known_tool(name: str) -> bool:
    return name in LLM_TOOL_SCHEMAS


def strip_approval_args(args: dict[str, Any]) -> dict[str, Any]:
    """Remove any approval-shaped key a model invented.

    No schema declares one, so a well-behaved model never sends one. This exists
    because the consequence of honouring a model-supplied approval flag is a real
    job application submitted without the user's consent.
    """
    return {k: v for k, v in args.items() if k not in _APPROVAL_ARG_NAMES}


def validate_args(tool_name: str, args: Any) -> tuple[bool, dict[str, Any] | str]:
    """Validate model-supplied arguments against a tool's schema.

    Returns ``(True, cleaned_args)`` or ``(False, reason)``. The reason is handed
    back to the model as a tool result so it can correct itself; it is never
    raised, because one malformed tool call must not fail the user's whole turn.

    Deliberately a small hand-rolled check rather than a jsonschema dependency:
    the schemas here use one object level with scalar properties, and adding a
    runtime dependency to the request path for that is not a good trade.
    """
    schema = LLM_TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return False, f"unknown_tool:{tool_name}"

    if not isinstance(args, dict):
        return False, "arguments_must_be_an_object"

    cleaned = strip_approval_args(args)
    params = schema["function"]["parameters"]
    properties: dict[str, Any] = params["properties"]

    unknown = sorted(set(cleaned) - set(properties))
    if unknown:
        return False, f"unknown_arguments:{','.join(unknown)}"

    missing = sorted(set(params["required"]) - set(cleaned))
    if missing:
        return False, f"missing_required:{','.join(missing)}"

    for key, value in cleaned.items():
        spec = properties[key]
        expected = spec.get("type")

        if expected == "integer":
            # bool is an int subclass in Python; a boolean here is a type error.
            if isinstance(value, bool) or not isinstance(value, int):
                return False, f"invalid_type:{key}:expected_integer"
            if "minimum" in spec and value < spec["minimum"]:
                return False, f"out_of_range:{key}:min_{spec['minimum']}"
            if "maximum" in spec and value > spec["maximum"]:
                return False, f"out_of_range:{key}:max_{spec['maximum']}"
        elif expected == "string":
            if not isinstance(value, str):
                return False, f"invalid_type:{key}:expected_string"
            if not value.strip():
                return False, f"empty_value:{key}"

    return True, cleaned


def safety_action_for(tool_name: str) -> str | None:
    """The rico_safety action name for a tool, or None if it is not high-impact.

    Never pass a raw tool name to ``RicoSafetyGuard.check_action`` — see the
    module docstring, invariant 2.
    """
    return SAFETY_ACTION_FOR_TOOL.get(tool_name)
