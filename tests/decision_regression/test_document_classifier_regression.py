"""
Regression gate for Rico's document classifier — the deterministic decision that
drives the entire upload experience (CV vs image vs identity-document vs no-text)
and that suffered two production incidents (#1046 image-as-CV, #1047 identity-doc
bypass).

Hermetic: runs the REAL classifier over a labeled golden set with no network, no
DB, and no PDF/DOCX libraries (all inputs are plain text or magic bytes). Any
change that degrades a core decision, or regresses a security invariant, fails
here — before it reaches a user.

To extend: add a line to goldens/document_classification.jsonl. To add a whole
new decision family (intent router, Gmail thread classification, a guardrail),
add an adapter in harness.py and a sibling test — see README.md.
"""
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from tests.decision_regression.harness import (  # noqa: E402
    GOLDENS_DIR,
    load_goldens,
    run_document_classifier_golden,
)

_GOLDEN = GOLDENS_DIR / "document_classification.jsonl"


def _report():
    return run_document_classifier_golden(load_goldens(_GOLDEN))


def test_hard_invariants_never_regress():
    """Production incidents + security guarantees, independent of aggregate
    accuracy: images stay images (#1046), identity documents stay blockable
    (#1047), executables stay rejected."""
    report = _report()
    report.write("document_classifier_latest")  # artifact for drift tracking
    report.assert_hard_invariants()


def test_security_critical_recall_is_total():
    """The classes whose misclassification is a security or data-integrity
    failure must have perfect recall — an identity document or executable must
    NEVER slip through as something benign."""
    report = _report()
    report.assert_class_recall("identity_document", 1.0)
    report.assert_class_recall("executable", 1.0)
    report.assert_class_recall("image", 1.0)


def test_overall_accuracy_floor():
    """Broad-drift guard: the whole golden set must stay above the accuracy
    floor, so a change that quietly degrades several document types is caught
    even when no single hard invariant trips."""
    report = _report()
    report.assert_accuracy(min_accuracy=0.90)


def test_confidence_floors_hold():
    """Where a golden case declares a min_confidence, the classifier must meet
    it — a correct label at collapsing confidence is itself a regression signal
    (the router uses confidence to gate downstream behavior)."""
    report = _report()
    weak = [
        r for r in report.results
        if r.label_ok and not r.confidence_ok
    ]
    assert not weak, "confidence dropped below the golden floor for:\n" + "\n".join(
        f"  - {r.case.id}: conf={r.confidence:.3f} < {r.case.min_confidence}" for r in weak
    )


def test_golden_dataset_is_meaningful():
    """Guard the guard: the golden set must be non-trivial and actually contain
    the hard security/incident cases, so the gate can never pass vacuously."""
    cases = load_goldens(_GOLDEN)
    assert len(cases) >= 12
    hard = [c for c in cases if c.hard]
    assert len(hard) >= 6
    expected_hard = {c.expected for c in hard}
    assert {"image", "identity_document", "executable"} <= expected_hard
