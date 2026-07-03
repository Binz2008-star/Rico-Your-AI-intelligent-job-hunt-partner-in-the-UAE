"""
PR-A — Agentic UI backend schema contracts.

Verifies:
1. All new models construct and serialize correctly.
2. Existing RicoResponse behavior is unchanged (backward compat).
3. RicoResponse.to_dict() includes agentic_ui when set, omits it when None.
4. RicoAgenticUi.is_empty() returns the right value.
5. High-impact actions are correctly typed.
6. RicoAttachmentAnalysis covers all document purpose categories.
"""
from __future__ import annotations

import pytest

from src.agent.responses.agentic_ui import (
    RicoActionImpact,
    RicoActionKind,
    RicoAgenticUi,
    RicoAttachmentAnalysis,
    RicoAttachmentPurpose,
    RicoChatAction,
    RicoPermissionRequest,
    RicoProgressStep,
    RicoProposedChange,
)
from src.agent.responses.schema import RicoResponse, build_error_response


# ── RicoChatAction ────────────────────────────────────────────────────────────

class TestRicoChatAction:

    def test_navigate_action_minimum_fields(self):
        a = RicoChatAction(id="view", label="View jobs", kind=RicoActionKind.navigate, href="/flow")
        assert a.kind == RicoActionKind.navigate
        assert a.impact == RicoActionImpact.low  # default
        assert not a.requires_confirmation

    def test_submit_action_with_endpoint(self):
        a = RicoChatAction(
            id="save",
            label="Save job",
            kind=RicoActionKind.submit,
            impact=RicoActionImpact.medium,
            endpoint="/api/v1/actions/save",
            payload={"job_key": "abc123"},
        )
        assert a.endpoint == "/api/v1/actions/save"
        assert a.payload["job_key"] == "abc123"

    def test_high_impact_action_marks_requires_confirmation(self):
        a = RicoChatAction(
            id="apply",
            label="Apply",
            kind=RicoActionKind.approve,
            impact=RicoActionImpact.high,
            requires_confirmation=True,
        )
        assert a.impact == RicoActionImpact.high
        assert a.requires_confirmation

    def test_chat_continue_action(self):
        a = RicoChatAction(
            id="tailor",
            label="Tailor CV",
            kind=RicoActionKind.chat_continue,
            payload={"prompt": "tailor my CV for this role"},
        )
        assert a.kind == RicoActionKind.chat_continue

    def test_tracking_key_optional(self):
        a = RicoChatAction(id="x", label="X", kind=RicoActionKind.navigate)
        assert a.tracking_key is None

    def test_serializes_to_dict(self):
        a = RicoChatAction(id="v", label="View", kind=RicoActionKind.navigate, href="/flow")
        d = a.model_dump(exclude_none=True)
        assert d["id"] == "v"
        assert d["label"] == "View"
        assert d["href"] == "/flow"
        assert "endpoint" not in d  # None excluded


# ── RicoPermissionRequest ─────────────────────────────────────────────────────

class TestRicoPermissionRequest:

    def _approve(self) -> RicoChatAction:
        return RicoChatAction(
            id="approve", label="Apply now", kind=RicoActionKind.approve,
            impact=RicoActionImpact.high, requires_confirmation=True,
        )

    def _cancel(self) -> RicoChatAction:
        return RicoChatAction(id="cancel", label="Cancel", kind=RicoActionKind.cancel)

    def test_basic_permission_request(self):
        pr = RicoPermissionRequest(
            id="perm-apply-001",
            title="Apply to HSE Manager at Dutco",
            summary="Rico will submit your application using your saved CV.",
            risk_level="high",
            data_used=["active_cv", "profile_email"],
            effects=["Application submitted", "Application tracked in pipeline"],
            approve_action=self._approve(),
            cancel_action=self._cancel(),
        )
        assert pr.risk_level == "high"
        assert pr.review_action is None
        assert len(pr.data_used) == 2
        assert len(pr.effects) == 2

    def test_review_action_optional(self):
        pr = RicoPermissionRequest(
            id="p2",
            title="Send cover letter",
            summary="Rico will send a tailored cover letter.",
            risk_level="medium",
            approve_action=self._approve(),
            cancel_action=self._cancel(),
            review_action=RicoChatAction(
                id="review", label="Edit first", kind=RicoActionKind.open_drawer
            ),
        )
        assert pr.review_action is not None
        assert pr.review_action.label == "Edit first"

    def test_serializes_nested_actions(self):
        pr = RicoPermissionRequest(
            id="p3",
            title="T",
            summary="S",
            risk_level="high",
            approve_action=self._approve(),
            cancel_action=self._cancel(),
        )
        d = pr.model_dump(exclude_none=True)
        assert "approve_action" in d
        assert d["approve_action"]["id"] == "approve"


# ── RicoProgressStep ──────────────────────────────────────────────────────────

class TestRicoProgressStep:

    def test_all_statuses(self):
        for status in ("pending", "running", "complete", "failed"):
            s = RicoProgressStep(id=f"s-{status}", label="Step", status=status)
            assert s.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(Exception):
            RicoProgressStep(id="x", label="X", status="unknown")


# ── RicoProposedChange ────────────────────────────────────────────────────────

class TestRicoProposedChange:

    def test_all_sources(self):
        for src in ("chat", "cv", "file", "screenshot", "system", "user_action"):
            c = RicoProposedChange(field="preferred_cities", proposed_value=["Dubai"], source=src)
            assert c.source == src

    def test_current_value_optional(self):
        c = RicoProposedChange(field="target_role", proposed_value="HSE Manager", source="chat")
        assert c.current_value is None

    def test_preserves_any_value_types(self):
        c = RicoProposedChange(field="years_experience", current_value=5, proposed_value=8, source="cv")
        assert c.proposed_value == 8


# ── RicoAttachmentAnalysis ────────────────────────────────────────────────────

class TestRicoAttachmentAnalysis:

    def test_all_purpose_categories(self):
        # Assert the exact documented taxonomy rather than a bare count, so adding
        # or removing a category is a deliberate, visible change. `application_evidence`
        # was added for job-confirmation screenshots (BUG-19 / #806).
        expected = {
            "cv_resume", "job_post", "recruiter_message", "application_form",
            "certificate", "offer_letter", "contract_or_legalish", "company_profile",
            "public_comment", "application_evidence", "unknown_document",
        }
        assert {p.value for p in RicoAttachmentPurpose} == expected
        assert RicoAttachmentPurpose.cv_resume in RicoAttachmentPurpose
        assert RicoAttachmentPurpose.unknown_document in RicoAttachmentPurpose

    def test_basic_attachment_analysis(self):
        aa = RicoAttachmentAnalysis(
            id="att-001",
            filename="cv.pdf",
            mime_type="application/pdf",
            purpose=RicoAttachmentPurpose.cv_resume,
            confidence=0.97,
            extracted_summary="5 years HSE experience, NEBOSH certified.",
        )
        assert aa.confidence == 0.97
        assert aa.purpose == RicoAttachmentPurpose.cv_resume
        assert not aa.warnings

    def test_sensitive_doc_has_warnings(self):
        aa = RicoAttachmentAnalysis(
            id="att-002",
            filename="offer_letter.pdf",
            mime_type="application/pdf",
            purpose=RicoAttachmentPurpose.offer_letter,
            confidence=0.85,
            warnings=["Contains salary details", "Legal review recommended"],
        )
        assert len(aa.warnings) == 2

    def test_unknown_document_low_confidence(self):
        aa = RicoAttachmentAnalysis(
            id="att-003",
            purpose=RicoAttachmentPurpose.unknown_document,
            confidence=0.2,
        )
        assert aa.confidence == 0.2
        assert aa.filename is None


# ── RicoAgenticUi ─────────────────────────────────────────────────────────────

class TestRicoAgenticUi:

    def test_empty_by_default(self):
        ui = RicoAgenticUi()
        assert ui.is_empty()
        assert ui.actions == []
        assert ui.permission_request is None

    def test_not_empty_with_action(self):
        ui = RicoAgenticUi(actions=[
            RicoChatAction(id="v", label="View", kind=RicoActionKind.navigate, href="/flow")
        ])
        assert not ui.is_empty()

    def test_not_empty_with_permission_request(self):
        ui = RicoAgenticUi(
            permission_request=RicoPermissionRequest(
                id="p",
                title="T",
                summary="S",
                risk_level="high",
                approve_action=RicoChatAction(id="a", label="A", kind=RicoActionKind.approve),
                cancel_action=RicoChatAction(id="c", label="C", kind=RicoActionKind.cancel),
            )
        )
        assert not ui.is_empty()

    def test_not_empty_with_progress(self):
        ui = RicoAgenticUi(progress=[RicoProgressStep(id="s1", label="Searching", status="running")])
        assert not ui.is_empty()

    def test_to_response_dict_excludes_nones(self):
        ui = RicoAgenticUi(actions=[
            RicoChatAction(id="v", label="View jobs", kind=RicoActionKind.navigate, href="/flow")
        ])
        d = ui.to_response_dict()
        assert "permission_request" not in d
        assert d["actions"][0]["id"] == "v"

    def test_full_envelope_serializes(self):
        ui = RicoAgenticUi(
            actions=[RicoChatAction(id="a1", label="Save search", kind=RicoActionKind.submit)],
            progress=[RicoProgressStep(id="p1", label="Searching...", status="running")],
            proposed_changes=[
                RicoProposedChange(field="preferred_cities", proposed_value=["Dubai"], source="chat")
            ],
            attachment_analysis=[
                RicoAttachmentAnalysis(
                    id="at1",
                    purpose=RicoAttachmentPurpose.job_post,
                    confidence=0.9,
                    extracted_summary="QHSE Manager role at Example Group",
                )
            ],
        )
        d = ui.to_response_dict()
        assert len(d["actions"]) == 1
        assert len(d["progress"]) == 1
        assert len(d["proposed_changes"]) == 1
        assert len(d["attachment_analysis"]) == 1


# ── RicoResponse backward compatibility ───────────────────────────────────────

class TestRicoResponseBackwardCompat:

    def test_existing_response_unchanged_when_no_agentic_ui(self):
        r = RicoResponse(success=True, type="job_matches", message="Found 3 jobs")
        d = r.to_dict()
        assert d["success"] is True
        assert d["type"] == "job_matches"
        assert d["message"] == "Found 3 jobs"
        assert "agentic_ui" not in d  # must be absent — old clients must not see it

    def test_agentic_ui_included_when_set(self):
        ui = RicoAgenticUi(actions=[
            RicoChatAction(id="view", label="View jobs", kind=RicoActionKind.navigate, href="/flow")
        ])
        r = RicoResponse(
            success=True,
            type="job_matches",
            message="Found 3 jobs",
            agentic_ui=ui.to_response_dict(),
        )
        d = r.to_dict()
        assert "agentic_ui" in d
        assert d["agentic_ui"]["actions"][0]["label"] == "View jobs"

    def test_agentic_ui_absent_when_none(self):
        r = RicoResponse(success=True, type="clarification", message="Which city?")
        d = r.to_dict()
        assert "agentic_ui" not in d

    def test_existing_fields_still_present(self):
        r = RicoResponse(
            success=True,
            type="job_matches",
            message="Found jobs",
            matches=[{"title": "HSE Manager"}],
            next_action="review_results",
        )
        d = r.to_dict()
        assert d["matches"] == [{"title": "HSE Manager"}]
        assert d["next_action"] == "review_results"

    def test_build_error_response_unaffected(self):
        d = build_error_response("Something went wrong.")
        assert d["success"] is False
        assert d["type"] == "error"
        assert "agentic_ui" not in d

    def test_empty_agentic_ui_still_included_when_explicitly_set(self):
        empty_ui = RicoAgenticUi()
        r = RicoResponse(
            success=True,
            type="clarification",
            message="What role?",
            agentic_ui=empty_ui.to_response_dict(),
        )
        d = r.to_dict()
        # If caller explicitly sets it (even empty), it appears in the dict
        assert "agentic_ui" in d
