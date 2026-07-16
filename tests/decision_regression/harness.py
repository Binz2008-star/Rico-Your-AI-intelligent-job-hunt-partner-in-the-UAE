"""
Hermetic golden-regression harness for Rico's DETERMINISTIC decision layer.

Rico's product value rests on a handful of decisions made deterministically on
every request — what an uploaded file *is* (document classifier), which path a
message takes (intent router), whether an action is allowed (guardrails). These
are keyword / magic-byte / rule based, so unlike the LLM layer above them they
can be pinned EXACTLY, offline, in CI.

A silent regression in this layer is invisible until it reaches a user: an
identity document misread as a CV, an image routed into CV extraction. Two such
incidents already shipped to production (#1046 image-as-CV, #1047 identity-doc
bypass). This harness makes that class of regression impossible to merge
unnoticed — every core decision is checked against a labeled golden set on every
CI run.

Design goals:
  * HERMETIC — no network, no DB, no live AI provider; pure deterministic code.
  * COMPOUNDING — adding a case is one JSONL line; adding a decision family is
    one adapter. Every future decision (Gmail thread classification, job-fit
    scoring, new guardrails) plugs into the same accuracy / invariant gate.
  * HONEST — cases that encode a real production incident are marked
    ``hard: true`` and must NEVER regress, independent of the aggregate
    accuracy floor.

This module is decision-agnostic. Family-specific input synthesis lives in the
adapter functions at the bottom (currently: document classifier).
"""
from __future__ import annotations

import base64
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

GOLDENS_DIR = Path(__file__).parent / "goldens"
REPORTS_DIR = Path(__file__).parent / "reports"


# ── Golden case model ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenCase:
    """One labeled decision case.

    ``expected`` is the required decision label. ``min_confidence`` (optional)
    floors the decision's confidence. ``hard`` marks a case that encodes a real
    production incident or a security invariant — it must pass regardless of the
    aggregate accuracy gate. ``synth`` carries family-specific input-building
    fields (e.g. how to build the classifier's bytes).
    """

    id: str
    expected: str
    synth: Dict[str, Any]
    min_confidence: Optional[float] = None
    hard: bool = False
    note: str = ""
    tags: Tuple[str, ...] = ()


def load_goldens(path: Path) -> List[GoldenCase]:
    """Load a JSONL golden file into GoldenCase objects. Fails loudly on a
    missing file or a malformed line — a silently-empty golden set would make
    the whole gate pass vacuously."""
    if not path.exists():
        raise FileNotFoundError(f"golden dataset not found: {path}")
    cases: List[GoldenCase] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"{path.name}:{lineno} is not valid JSON: {exc}") from None
        cid = str(row["id"])
        if cid in seen_ids:
            raise ValueError(f"{path.name}:{lineno} duplicate case id {cid!r}")
        seen_ids.add(cid)
        cases.append(
            GoldenCase(
                id=cid,
                expected=str(row["expected"]),
                synth=row.get("synth", {}),
                min_confidence=row.get("min_confidence"),
                hard=bool(row.get("hard", False)),
                note=str(row.get("note", "")),
                tags=tuple(row.get("tags", [])),
            )
        )
    if not cases:
        raise ValueError(f"golden dataset {path.name} is empty")
    return cases


# ── Prediction + report ───────────────────────────────────────────────────────


@dataclass
class CaseResult:
    case: GoldenCase
    predicted: str
    confidence: float
    label_ok: bool
    confidence_ok: bool

    @property
    def passed(self) -> bool:
        return self.label_ok and self.confidence_ok


@dataclass
class Report:
    """Aggregate result of running a decision family over its golden set."""

    family: str
    results: List[CaseResult] = field(default_factory=list)

    # ---- aggregate metrics ----

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def failures(self) -> List[CaseResult]:
        return [r for r in self.results if not r.passed]

    @property
    def hard_failures(self) -> List[CaseResult]:
        return [r for r in self.results if r.case.hard and not r.passed]

    def class_recall(self, expected_label: str) -> float:
        rows = [r for r in self.results if r.case.expected == expected_label]
        if not rows:
            return 1.0  # nothing to recall → vacuously satisfied
        return sum(1 for r in rows if r.label_ok) / len(rows)

    @property
    def confusion(self) -> Dict[str, Dict[str, int]]:
        matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in self.results:
            matrix[r.case.expected][r.predicted] += 1
        return {k: dict(v) for k, v in matrix.items()}

    # ---- serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "total": self.total,
            "passed": self.passed,
            "accuracy": round(self.accuracy, 4),
            "hard_total": sum(1 for r in self.results if r.case.hard),
            "hard_failures": [r.case.id for r in self.hard_failures],
            "failures": [
                {
                    "id": r.case.id,
                    "expected": r.case.expected,
                    "predicted": r.predicted,
                    "confidence": round(r.confidence, 3),
                    "hard": r.case.hard,
                    "note": r.case.note,
                }
                for r in self.failures
            ],
            "confusion": self.confusion,
        }

    def write(self, name: str) -> Path:
        """Persist a JSON report artifact for drift tracking over time. Reports
        are git-ignored; only the harness + goldens are versioned."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        # No timestamp in the name (Date.now is not available in every runner and
        # a stable name lets CI diff the latest report); callers pass a fixed name.
        out = REPORTS_DIR / f"{name}.json"
        out.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return out

    # ---- gates (raise AssertionError, so pytest reports them) ----

    def _describe_failures(self, rows: List[CaseResult]) -> str:
        return "\n".join(
            f"  - {r.case.id}: expected {r.case.expected!r} "
            f"got {r.predicted!r} (conf={r.confidence:.3f})"
            f"{' [HARD]' if r.case.hard else ''}"
            f"{'  — ' + r.case.note if r.case.note else ''}"
            for r in rows
        )

    def assert_hard_invariants(self) -> None:
        """Every case marked ``hard`` (production incidents + security
        invariants) must pass — no aggregate can excuse a hard regression."""
        if self.hard_failures:
            raise AssertionError(
                f"[{self.family}] {len(self.hard_failures)} HARD invariant(s) regressed "
                f"— these encode real incidents/security guarantees:\n"
                + self._describe_failures(self.hard_failures)
            )

    def assert_accuracy(self, min_accuracy: float) -> None:
        if self.accuracy < min_accuracy:
            raise AssertionError(
                f"[{self.family}] accuracy {self.accuracy:.3f} < floor {min_accuracy:.3f} "
                f"({self.passed}/{self.total} passed). Failures:\n"
                + self._describe_failures(self.failures)
            )

    def assert_class_recall(self, expected_label: str, min_recall: float) -> None:
        recall = self.class_recall(expected_label)
        if recall < min_recall:
            bad = [
                r for r in self.results
                if r.case.expected == expected_label and not r.label_ok
            ]
            raise AssertionError(
                f"[{self.family}] recall for {expected_label!r} is {recall:.3f} "
                f"< floor {min_recall:.3f}:\n" + self._describe_failures(bad)
            )


# ── Generic runner ────────────────────────────────────────────────────────────

# A decider takes a built input and returns (label, confidence).
Decider = Callable[[Any], Tuple[str, float]]
# An input builder turns a case's ``synth`` spec into the family's input type.
InputBuilder = Callable[[GoldenCase], Any]


def run_family(family: str, cases: List[GoldenCase], build: InputBuilder, decide: Decider) -> Report:
    report = Report(family=family)
    for case in cases:
        built = build(case)
        label, confidence = decide(built)
        label_ok = label == case.expected
        conf_ok = case.min_confidence is None or confidence >= case.min_confidence
        report.results.append(
            CaseResult(
                case=case,
                predicted=label,
                confidence=confidence,
                label_ok=label_ok,
                confidence_ok=conf_ok,
            )
        )
    return report


# ── Adapter: document classifier ──────────────────────────────────────────────
#
# Synthesizes bytes + filename from a golden case's ``synth`` spec. Kinds:
#   {"kind": "text",   "text": "...", "filename": "x.txt"}     -> raw utf-8 bytes
#   {"kind": "repeat", "text": "..", "times": N, "filename":?} -> text*N (bulk)
#   {"kind": "b64",    "data": "<base64>", "filename": "x"}    -> decoded bytes
#   {"kind": "magic",  "magic": "png|jpg|gif|pdf|mz|elf", "pad": N, "filename":?}
#                                                             -> magic header + pad
# All kinds are deterministic and library-free (no PDF/DOCX parsing needed).

_MAGIC_HEADERS: Dict[str, bytes] = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff\xe0",
    "gif": b"GIF89a",
    "pdf": b"%PDF-1.4",
    "mz": b"MZ\x90\x00",          # DOS/PE executable
    "elf": b"\x7fELF\x02\x01\x01",  # ELF executable
}


def build_classifier_input(case: GoldenCase) -> Tuple[bytes, str]:
    spec = case.synth
    kind = spec.get("kind", "text")
    filename = spec.get("filename", "")
    if kind == "text":
        return spec["text"].encode("utf-8"), filename
    if kind == "repeat":
        return (spec["text"] * int(spec.get("times", 1))).encode("utf-8"), filename
    if kind == "b64":
        return base64.b64decode(spec["data"]), filename
    if kind == "magic":
        header = _MAGIC_HEADERS[spec["magic"]]
        return header + (b"\x00" * int(spec.get("pad", 0))), filename
    raise ValueError(f"unknown classifier synth kind: {kind!r} (case {case.id})")


def decide_classifier(built: Tuple[bytes, str]) -> Tuple[str, float]:
    """Run the REAL production classifier — never a reimplementation."""
    from src.services.document_classifier import classify_document

    data, filename = built
    result = classify_document(data, filename)
    return result.document_type, result.confidence


def run_document_classifier_golden(cases: List[GoldenCase]) -> Report:
    return run_family("document_classifier", cases, build_classifier_input, decide_classifier)
