"""
src/agent/reasoning/trace.py
External reasoning layer — structured, auditable execution state.

Rico never exposes model-internal chain-of-thought. Instead, every decision
the agent makes is tracked as a ReasoningTrace: a visible execution state
where each conclusion is traceable to recorded evidence.

    Goal        → what Rico is trying to do
    Evidence    → operational facts observed while doing it (gates, lookups)
    Assumptions → hypotheses not yet supported by evidence
    Conflicts   → contradictions between pieces of evidence
    Decision    → the action chosen, with rationale and evidence references
    Confidence  → derived score penalized by unresolved conflicts and
                  unverified evidence
    Next action / Blocked → what happens next, or what Rico is waiting for
    Outcome     → what actually happened after execution

Traces are pure data (this module performs no I/O). They serialize with
``to_dict()`` and rehydrate with ``from_dict()``, so a trace persisted by one
process can be resumed, inspected, or extended by another agent — the
persistent Reasoning Graph is built from these nodes
(``src/repositories/reasoning_repo.py``, migration 047).

Privacy contract: evidence values must be OPERATIONAL FACTS ONLY — action
names, gate states, job titles/companies (same class of data as
``action_audit_log``), counters, flags. Never raw chat/document text, contact
identifiers, or any token (see #1076 / src/log_privacy.py). Trace content is
stored, not logged.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Bounded state: a trace is a decision record, not a transcript.
_MAX_ITEMS = 50          # per section (evidence / assumptions / conflicts / …)
_MAX_TEXT = 300          # per free-text field
_MAX_GOAL = 500

TRACE_SCHEMA_VERSION = 1

# Trace lifecycle states
STATUS_GATHERING = "gathering"   # collecting evidence, no decision yet
STATUS_DECIDED = "decided"       # decision made, not yet executed
STATUS_EXECUTED = "executed"     # outcome recorded
STATUS_BLOCKED = "blocked"       # waiting on evidence or user input

_VALID_STATUSES = frozenset(
    {STATUS_GATHERING, STATUS_DECIDED, STATUS_EXECUTED, STATUS_BLOCKED}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(text: Any, limit: int = _MAX_TEXT) -> str:
    return str(text if text is not None else "")[:limit]


@dataclass
class EvidenceItem:
    """One observed operational fact. ``verified`` means the fact was checked
    against an authoritative source (a gate ran, a lookup returned), not
    merely asserted by the caller."""
    id: str
    label: str
    value: str
    source: str = ""
    verified: bool = False
    at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "value": self.value,
            "source": self.source, "verified": self.verified, "at": self.at,
        }


@dataclass
class Assumption:
    """A hypothesis Rico is operating under. status: open | supported | rejected."""
    id: str
    statement: str
    status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "statement": self.statement, "status": self.status}


@dataclass
class Contradiction:
    """Two or more pieces of evidence that disagree. Unresolved contradictions
    lower confidence until resolved with an explanation."""
    id: str
    description: str
    evidence_ids: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "description": self.description,
            "evidence_ids": list(self.evidence_ids),
            "resolved": self.resolved, "resolution": self.resolution,
        }


@dataclass
class Verification:
    """Evidence Rico still needs before (or to firm up) a decision."""
    id: str
    description: str
    satisfied: bool = False
    evidence_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "description": self.description,
            "satisfied": self.satisfied, "evidence_id": self.evidence_id,
        }


@dataclass
class Decision:
    """The chosen action, its rationale, and the evidence it rests on."""
    action: str
    rationale: str
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action, "rationale": self.rationale,
            "evidence_ids": list(self.evidence_ids),
            "confidence": self.confidence, "at": self.at,
        }


class ReasoningTrace:
    """Structured execution state for one agent decision.

    Typical lifecycle::

        trace = ReasoningTrace(goal="apply — ESG Manager", user_id=uid)
        trace.add_evidence("idempotency guard", "no duplicate", verified=True)
        trace.decide("apply_job", "explicit user action routed to tool")
        ...
        trace.record_outcome(ok=True, summary="application submitted")
    """

    def __init__(
        self,
        goal: str,
        user_id: str = "",
        source: str = "",
        trace_id: str = "",
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.goal = _clip(goal, _MAX_GOAL)
        self.user_id = _clip(user_id, 255)
        self.source = _clip(source, 32)
        self.status = STATUS_GATHERING
        self.evidence: List[EvidenceItem] = []
        self.assumptions: List[Assumption] = []
        self.contradictions: List[Contradiction] = []
        self.verifications: List[Verification] = []
        self.decision: Optional[Decision] = None
        self.next_action = ""
        self.blocked_on = ""
        self.outcome: Dict[str, Any] = {}
        self.dropped_items = 0  # adds refused because a section hit _MAX_ITEMS
        self.created_at = _now_iso()
        self.updated_at = self.created_at

    # ── State building ────────────────────────────────────────────────────────

    def add_evidence(
        self, label: str, value: Any, source: str = "", verified: bool = False
    ) -> Optional[EvidenceItem]:
        if len(self.evidence) >= _MAX_ITEMS:
            self.dropped_items += 1
            return None
        item = EvidenceItem(
            id=f"e{len(self.evidence) + 1}",
            label=_clip(label), value=_clip(value),
            source=_clip(source, 64), verified=bool(verified),
        )
        self.evidence.append(item)
        self._touch()
        return item

    def assume(self, statement: str) -> Optional[Assumption]:
        if len(self.assumptions) >= _MAX_ITEMS:
            self.dropped_items += 1
            return None
        item = Assumption(id=f"a{len(self.assumptions) + 1}", statement=_clip(statement))
        self.assumptions.append(item)
        self._touch()
        return item

    def add_contradiction(
        self, description: str, evidence_ids: Optional[List[str]] = None
    ) -> Optional[Contradiction]:
        if len(self.contradictions) >= _MAX_ITEMS:
            self.dropped_items += 1
            return None
        item = Contradiction(
            id=f"c{len(self.contradictions) + 1}",
            description=_clip(description),
            evidence_ids=list(evidence_ids or []),
        )
        self.contradictions.append(item)
        self._touch()
        return item

    def resolve_contradiction(self, contradiction_id: str, resolution: str) -> bool:
        for item in self.contradictions:
            if item.id == contradiction_id:
                item.resolved = True
                item.resolution = _clip(resolution)
                self._touch()
                return True
        return False

    def require_verification(self, description: str) -> Optional[Verification]:
        if len(self.verifications) >= _MAX_ITEMS:
            self.dropped_items += 1
            return None
        item = Verification(
            id=f"v{len(self.verifications) + 1}", description=_clip(description)
        )
        self.verifications.append(item)
        self._touch()
        return item

    def satisfy_verification(self, verification_id: str, evidence_id: str = "") -> bool:
        for item in self.verifications:
            if item.id == verification_id:
                item.satisfied = True
                item.evidence_id = evidence_id
                self._touch()
                return True
        return False

    # ── Decision and outcome ──────────────────────────────────────────────────

    def decide(
        self,
        action: str,
        rationale: str,
        confidence: Optional[float] = None,
        evidence_ids: Optional[List[str]] = None,
    ) -> Decision:
        """Record the chosen action. When ``confidence`` is not given it is
        derived from the current evidence state (see ``derived_confidence``).
        Evidence references default to everything gathered so far."""
        self.decision = Decision(
            action=_clip(action, 128),
            rationale=_clip(rationale),
            evidence_ids=list(evidence_ids) if evidence_ids is not None
            else [e.id for e in self.evidence],
            confidence=self.derived_confidence() if confidence is None
            else max(0.0, min(1.0, float(confidence))),
        )
        if self.status != STATUS_BLOCKED:
            self.status = STATUS_DECIDED
        self._touch()
        return self.decision

    def block(self, blocked_on: str, next_action: str = "") -> None:
        """Mark the trace as waiting on evidence or user input."""
        self.blocked_on = _clip(blocked_on)
        if next_action:
            self.next_action = _clip(next_action)
        self.status = STATUS_BLOCKED
        self._touch()

    def set_next_action(self, next_action: str) -> None:
        self.next_action = _clip(next_action)
        self._touch()

    def record_outcome(self, ok: bool, summary: str = "", **extra: Any) -> None:
        """Record what actually happened after execution. Closes the loop so
        the reasoning graph can later be compared against reality."""
        self.outcome = {
            "ok": bool(ok),
            "summary": _clip(summary),
            "at": _now_iso(),
            **{k: _clip(v) for k, v in extra.items()},
        }
        if self.status != STATUS_BLOCKED:
            self.status = STATUS_EXECUTED
        self._touch()

    # ── Confidence ────────────────────────────────────────────────────────────

    def derived_confidence(self) -> float:
        """Deterministic confidence from the evidence state.

        Start at 1.0, then penalize:
          - 0.15 per unresolved contradiction
          - 0.20 per unsatisfied required verification
          - up to 0.15 total for unverified evidence (0.05 each)
        Floor 0.05 — a trace with evidence is never zero-confidence.
        """
        score = 1.0
        score -= 0.15 * sum(1 for c in self.contradictions if not c.resolved)
        score -= 0.20 * sum(1 for v in self.verifications if not v.satisfied)
        score -= min(0.15, 0.05 * sum(1 for e in self.evidence if not e.verified))
        return round(max(0.05, min(1.0, score)), 2)

    @property
    def confidence(self) -> float:
        return self.decision.confidence if self.decision else self.derived_confidence()

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "trace_id": self.trace_id,
            "goal": self.goal,
            "user_id": self.user_id,
            "source": self.source,
            "status": self.status,
            "evidence": [e.to_dict() for e in self.evidence],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "verifications": [v.to_dict() for v in self.verifications],
            "decision": self.decision.to_dict() if self.decision else None,
            "confidence": self.confidence,
            "next_action": self.next_action,
            "blocked_on": self.blocked_on,
            "outcome": dict(self.outcome),
            "dropped_items": self.dropped_items,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningTrace":
        """Rehydrate a persisted trace so another process/agent can resume
        from the same execution state."""
        trace = cls(
            goal=data.get("goal", ""),
            user_id=data.get("user_id", ""),
            source=data.get("source", ""),
            trace_id=data.get("trace_id", ""),
        )
        status = data.get("status", STATUS_GATHERING)
        trace.status = status if status in _VALID_STATUSES else STATUS_GATHERING
        for e in data.get("evidence") or []:
            trace.evidence.append(EvidenceItem(
                id=e.get("id", f"e{len(trace.evidence) + 1}"),
                label=_clip(e.get("label", "")), value=_clip(e.get("value", "")),
                source=_clip(e.get("source", ""), 64),
                verified=bool(e.get("verified")), at=e.get("at", trace.created_at),
            ))
        for a in data.get("assumptions") or []:
            trace.assumptions.append(Assumption(
                id=a.get("id", f"a{len(trace.assumptions) + 1}"),
                statement=_clip(a.get("statement", "")),
                status=a.get("status", "open"),
            ))
        for c in data.get("contradictions") or []:
            trace.contradictions.append(Contradiction(
                id=c.get("id", f"c{len(trace.contradictions) + 1}"),
                description=_clip(c.get("description", "")),
                evidence_ids=list(c.get("evidence_ids") or []),
                resolved=bool(c.get("resolved")),
                resolution=_clip(c.get("resolution", "")),
            ))
        for v in data.get("verifications") or []:
            trace.verifications.append(Verification(
                id=v.get("id", f"v{len(trace.verifications) + 1}"),
                description=_clip(v.get("description", "")),
                satisfied=bool(v.get("satisfied")),
                evidence_id=v.get("evidence_id", ""),
            ))
        d = data.get("decision")
        if d:
            trace.decision = Decision(
                action=_clip(d.get("action", ""), 128),
                rationale=_clip(d.get("rationale", "")),
                evidence_ids=list(d.get("evidence_ids") or []),
                confidence=float(d.get("confidence", 1.0)),
                at=d.get("at", trace.created_at),
            )
        trace.next_action = _clip(data.get("next_action", ""))
        trace.blocked_on = _clip(data.get("blocked_on", ""))
        trace.outcome = dict(data.get("outcome") or {})
        trace.dropped_items = int(data.get("dropped_items") or 0)
        trace.created_at = data.get("created_at", trace.created_at)
        trace.updated_at = data.get("updated_at", trace.created_at)
        return trace

    def summary_dict(self) -> Dict[str, Any]:
        """Compact form attached to action results (RuntimeResult.data)."""
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "status": self.status,
            "decision": self.decision.action if self.decision else "",
            "confidence": self.confidence,
            "state": self.render(),
        }

    # ── Human-visible execution state ─────────────────────────────────────────

    def render(self) -> str:
        """Render the visible execution state. This is what a user (or another
        agent) sees instead of hidden chain-of-thought — every line traces to
        recorded evidence."""
        lines: List[str] = ["Goal:", f"  {self.goal}"]

        if self.evidence:
            lines += ["", "Evidence:"]
            for e in self.evidence:
                mark = "✓" if e.verified else "•"
                lines.append(f"  {mark} {e.label}: {e.value}")

        open_assumptions = [a for a in self.assumptions if a.status == "open"]
        if open_assumptions:
            lines += ["", "Assumptions:"]
            lines += [f"  - {a.statement}" for a in open_assumptions]

        unresolved = [c for c in self.contradictions if not c.resolved]
        if unresolved:
            lines += ["", "Conflicts:"]
            lines += [f"  - {c.description}" for c in unresolved]

        pending = [v for v in self.verifications if not v.satisfied]
        if pending:
            lines += ["", "Required verification:"]
            lines += [f"  - {v.description}" for v in pending]

        if self.decision:
            lines += ["", "Decision:", f"  {self.decision.action} — {self.decision.rationale}"]

        lines += ["", "Confidence:", f"  {round(self.confidence * 100)}%"]

        if self.next_action:
            lines += ["", "Next action:", f"  {self.next_action}"]

        if self.blocked_on:
            lines += ["", "Blocked:", f"  {self.blocked_on}"]

        if self.outcome:
            mark = "✓" if self.outcome.get("ok") else "✗"
            lines += ["", "Outcome:", f"  {mark} {self.outcome.get('summary', '')}"]

        return "\n".join(lines)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _touch(self) -> None:
        self.updated_at = _now_iso()
