"""
tests/test_agentic_ui_contracts.py

Tests for CAREER-OS-01: optional agentic_ui response contracts.

Verifies:
- Old RicoChatResponse payloads still validate without agentic_ui.
- RicoChatResponse validates with empty/default agentic_ui.
- RicoChatResponse validates with actions, permission_request, progress,
  proposed_changes, and attachment_analysis.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.chat import (
    RicoActionImpact,
    RicoActionKind,
    RicoAgenticUi,
    RicoAttachmentAnalysis,
    RicoAttachmentPurpose,
    RicoChatAction,
    RicoChatResponse,
    RicoPermissionRequest,
    RicoProgressStep,
    RicoProposedChange,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _approve_action() -> RicoChatAction:
    return RicoChatAction(
        id="approve",
        label="Approve",
        kind=RicoActionKind.approve,
        impact=RicoActionImpact.high,
        requires_confirmation=True,
        endpoint="/api/v1/actions/apply",
    )


def _cancel_action() -> RicoChatAction:
    return RicoChatAction(id="cancel", label="Cancel", kind=RicoActionKind.cancel)


# ── Backward compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Old RicoChatResponse payloads must still validate without agentic_ui."""

    def test_minimal_text_response(self) -> None:
        r = RicoChatResponse(message="Hello!")
        assert r.message == "Hello!"
        assert r.agentic_ui is None

    def test_full_legacy_response(self) -> None:
        r = RicoChatResponse(
            message="Found 3 jobs.",
            type="job_search_results",
            matches=[{"title": "HSE Manager", "company": "Dutco Group"}],
            options=[{"action": "view_jobs", "label": "View jobs"}],
            next_action="view_jobs",
            next_actions=[{"action": "save_search", "label": "Save search"}],
            intent="job_search",
            response_source="keyword",
            provider="deepseek",
            reasons=["Experience match"],
            success=True,
        )
        assert r.agentic_ui is None
        assert r.message == "Found 3 jobs."

    def test_empty_response_defaults(self) -> None:
        r = RicoChatResponse()
        assert r.message == ""
        assert r.type == "response"
        assert r.success is True
        assert r.agentic_ui is None

    def test_extra_fields_still_allowed(self) -> None:
        r = RicoChatResponse.model_validate(
            {"message": "ok", "unknown_future_field": "value"}
        )
        assert r.message == "ok"

    def test_production_onboarding_shape(self) -> None:
        r = RicoChatResponse.model_validate({
            "message": "Welcome to Rico AI.",
            "type": "onboarding",
            "matches": [],
            "options": [],
            "next_action": None,
            "next_actions": [],
            "intent": None,
            "response_source": "keyword",
            "provider": None,
            "provider_state": None,
            "reasons": [],
            "role": None,
            "success": True,
            "error_ref": None,
            "trace_id": "ERR-83D937A1",
            "response": None,
        })
        assert r.agentic_ui is None
        assert r.type == "onboarding"


# ── Empty/default agentic_ui ──────────────────────────────────────────────────


class TestEmptyAgenticUi:
    """RicoChatResponse validates with empty/default agentic_ui."""

    def test_empty_agentic_ui_defaults(self) -> None:
        ui = RicoAgenticUi()
        assert ui.actions == []
        assert ui.permission_request is None
        assert ui.progress == []
        assert ui.proposed_changes == []
        assert ui.attachment_analysis == []

    def test_response_with_empty_agentic_ui(self) -> None:
        r = RicoChatResponse(message="Hello", agentic_ui=RicoAgenticUi())
        assert r.agentic_ui is not None
        assert r.agentic_ui.actions == []

    def test_agentic_ui_from_dict(self) -> None:
        r = RicoChatResponse.model_validate({"message": "Hi", "agentic_ui": {}})
        assert r.agentic_ui is not None
        assert r.agentic_ui.actions == []


# ── Actions ───────────────────────────────────────────────────────────────────


class TestAgenticUiWithActions:
    """RicoChatResponse validates with agentic_ui.actions."""

    def test_single_navigate_action(self) -> None:
        action = RicoChatAction(
            id="view-jobs",
            label="View jobs",
            kind=RicoActionKind.navigate,
            href="/jobs",
        )
        r = RicoChatResponse(message="Found 7 jobs.", agentic_ui=RicoAgenticUi(actions=[action]))
        assert r.agentic_ui is not None
        assert len(r.agentic_ui.actions) == 1
        assert r.agentic_ui.actions[0].id == "view-jobs"
        assert r.agentic_ui.actions[0].kind == RicoActionKind.navigate
        assert r.agentic_ui.actions[0].impact == RicoActionImpact.low

    def test_submit_action_with_payload(self) -> None:
        action = RicoChatAction(
            id="save-search",
            label="Save search",
            kind=RicoActionKind.submit,
            endpoint="/api/v1/rico/settings/saved-searches",
            payload={"query": "HSE Manager Dubai"},
        )
        r = RicoChatResponse(message="Found jobs.", agentic_ui=RicoAgenticUi(actions=[action]))
        assert r.agentic_ui.actions[0].payload == {"query": "HSE Manager Dubai"}

    def test_multiple_actions(self) -> None:
        actions = [
            RicoChatAction(id="view", label="View jobs", kind=RicoActionKind.navigate),
            RicoChatAction(id="save", label="Save search", kind=RicoActionKind.submit),
            RicoChatAction(id="draft", label="Draft cover letter", kind=RicoActionKind.chat_continue),
        ]
        r = RicoChatResponse(message="Found jobs.", agentic_ui=RicoAgenticUi(actions=actions))
        assert len(r.agentic_ui.actions) == 3

    def test_high_impact_action_with_confirmation(self) -> None:
        action = RicoChatAction(
            id="apply-job",
            label="Apply now",
            kind=RicoActionKind.approve,
            impact=RicoActionImpact.high,
            requires_confirmation=True,
            endpoint="/api/v1/actions/apply",
        )
        assert action.impact == RicoActionImpact.high
        assert action.requires_confirmation is True

    def test_all_action_kinds(self) -> None:
        for kind in RicoActionKind:
            a = RicoChatAction(id="x", label="X", kind=kind)
            assert a.kind == kind

    def test_all_action_impacts(self) -> None:
        for impact in RicoActionImpact:
            a = RicoChatAction(id="x", label="X", kind=RicoActionKind.navigate, impact=impact)
            assert a.impact == impact


# ── Permission request ────────────────────────────────────────────────────────


class TestAgenticUiWithPermissionRequest:
    """RicoChatResponse validates with permission_request."""

    def test_medium_risk_permission(self) -> None:
        perm = RicoPermissionRequest(
            id="perm-save-search",
            title="Save search",
            summary="Rico will save your current search filters.",
            risk_level="medium",
            data_used=["search filters"],
            effects=["Creates a saved search"],
            approve_action=_approve_action(),
            cancel_action=_cancel_action(),
        )
        r = RicoChatResponse(
            message="Save this search?",
            agentic_ui=RicoAgenticUi(permission_request=perm),
        )
        assert r.agentic_ui.permission_request.risk_level == "medium"
        assert r.agentic_ui.permission_request.review_action is None

    def test_high_risk_permission_with_review(self) -> None:
        review = RicoChatAction(id="review", label="Review first", kind=RicoActionKind.open_drawer)
        perm = RicoPermissionRequest(
            id="perm-apply",
            title="Apply to HSE Manager — Dutco Group",
            summary="Rico will submit your application.",
            risk_level="high",
            data_used=["active CV", "cover letter"],
            effects=["Submits application", "Saves record"],
            approve_action=_approve_action(),
            review_action=review,
            cancel_action=_cancel_action(),
        )
        assert perm.risk_level == "high"
        assert perm.review_action is not None
        assert perm.review_action.kind == RicoActionKind.open_drawer

    def test_invalid_risk_level_low_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RicoPermissionRequest(
                id="perm-x",
                title="Test",
                summary="Test",
                risk_level="low",  # only medium/high allowed
                approve_action=_approve_action(),
                cancel_action=_cancel_action(),
            )

    def test_permission_serializes_to_dict(self) -> None:
        perm = RicoPermissionRequest(
            id="perm-001",
            title="Apply",
            summary="Will apply.",
            risk_level="high",
            approve_action=_approve_action(),
            cancel_action=_cancel_action(),
        )
        r = RicoChatResponse(message="Apply?", agentic_ui=RicoAgenticUi(permission_request=perm))
        dumped = r.model_dump()
        assert dumped["agentic_ui"]["permission_request"]["risk_level"] == "high"
        assert dumped["agentic_ui"]["permission_request"]["approve_action"]["id"] == "approve"


# ── Progress steps ────────────────────────────────────────────────────────────


class TestAgenticUiWithProgress:
    """RicoChatResponse validates with progress steps."""

    def test_progress_steps_all_statuses(self) -> None:
        steps = [
            RicoProgressStep(id="s1", label="Detecting file type", status="complete"),
            RicoProgressStep(id="s2", label="Reading screenshot text", status="running"),
            RicoProgressStep(id="s3", label="Extracting job details", status="pending"),
            RicoProgressStep(id="s4", label="Saving result", status="failed"),
        ]
        r = RicoChatResponse(
            message="Analyzing your upload...",
            agentic_ui=RicoAgenticUi(progress=steps),
        )
        statuses = [s.status for s in r.agentic_ui.progress]
        assert statuses == ["complete", "running", "pending", "failed"]

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RicoProgressStep(id="x", label="Step", status="unknown_status")

    def test_progress_serializes(self) -> None:
        steps = [RicoProgressStep(id="p1", label="Step 1", status="complete")]
        r = RicoChatResponse(message="Done.", agentic_ui=RicoAgenticUi(progress=steps))
        dumped = r.model_dump()
        assert dumped["agentic_ui"]["progress"][0]["status"] == "complete"


# ── Proposed changes ──────────────────────────────────────────────────────────


class TestAgenticUiWithProposedChanges:
    """RicoChatResponse validates with proposed_changes."""

    def test_proposed_changes_chat_source(self) -> None:
        changes = [
            RicoProposedChange(
                field="preferred_cities",
                current_value=["Abu Dhabi"],
                proposed_value=["Dubai", "Sharjah"],
                source="chat",
            ),
            RicoProposedChange(
                field="minimum_salary_aed",
                current_value=None,
                proposed_value=15000,
                source="chat",
            ),
        ]
        r = RicoChatResponse(
            message="I can update your preferences.",
            agentic_ui=RicoAgenticUi(proposed_changes=changes),
        )
        assert len(r.agentic_ui.proposed_changes) == 2
        assert r.agentic_ui.proposed_changes[0].proposed_value == ["Dubai", "Sharjah"]
        assert r.agentic_ui.proposed_changes[1].current_value is None

    def test_all_valid_sources(self) -> None:
        valid_sources = ["chat", "cv", "file", "screenshot", "system", "user_action"]
        for source in valid_sources:
            c = RicoProposedChange(field="x", proposed_value="y", source=source)  # type: ignore[arg-type]
            assert c.source == source

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RicoProposedChange(field="x", proposed_value="y", source="email")  # type: ignore[arg-type]

    def test_cv_source_accepted(self) -> None:
        change = RicoProposedChange(
            field="skills",
            current_value=None,
            proposed_value=["ISO 45001", "HSE"],
            source="cv",
        )
        assert change.source == "cv"


# ── Attachment analysis ───────────────────────────────────────────────────────


class TestAgenticUiWithAttachmentAnalysis:
    """RicoChatResponse validates with attachment_analysis."""

    def test_cv_resume_analysis(self) -> None:
        analysis = RicoAttachmentAnalysis(
            id="att-cv-001",
            filename="my_cv.pdf",
            mime_type="application/pdf",
            purpose=RicoAttachmentPurpose.cv_resume,
            confidence=0.95,
            extracted_summary="HSE professional with 8 years experience.",
            extracted_fields={"name": "Ahmed Al Rashidi", "years_experience": 8},
        )
        r = RicoChatResponse(
            message="CV analyzed.",
            agentic_ui=RicoAgenticUi(attachment_analysis=[analysis]),
        )
        assert r.agentic_ui.attachment_analysis[0].purpose == RicoAttachmentPurpose.cv_resume
        assert r.agentic_ui.attachment_analysis[0].confidence == 0.95

    def test_job_post_screenshot_analysis(self) -> None:
        analysis = RicoAttachmentAnalysis(
            id="att-job-001",
            filename="linkedin_screenshot.png",
            mime_type="image/png",
            purpose=RicoAttachmentPurpose.job_post,
            confidence=0.82,
            extracted_fields={"title": "QHSE Manager", "company": "Example Group"},
            warnings=["Salary not visible in screenshot"],
        )
        assert analysis.purpose == RicoAttachmentPurpose.job_post
        assert len(analysis.warnings) == 1

    def test_unknown_document_minimal(self) -> None:
        analysis = RicoAttachmentAnalysis(
            id="att-unk-001",
            purpose=RicoAttachmentPurpose.unknown_document,
            confidence=0.21,
            warnings=["Could not determine document type"],
        )
        assert analysis.filename is None
        assert analysis.mime_type is None
        assert analysis.extracted_summary is None

    def test_all_attachment_purposes(self) -> None:
        for purpose in RicoAttachmentPurpose:
            a = RicoAttachmentAnalysis(id="x", purpose=purpose, confidence=0.5)
            assert a.purpose == purpose

    def test_attachment_serializes(self) -> None:
        analysis = RicoAttachmentAnalysis(
            id="att-001",
            purpose=RicoAttachmentPurpose.job_post,
            confidence=0.9,
        )
        r = RicoChatResponse(
            message="Found a job post.",
            agentic_ui=RicoAgenticUi(attachment_analysis=[analysis]),
        )
        dumped = r.model_dump()
        assert dumped["agentic_ui"]["attachment_analysis"][0]["purpose"] == "job_post"


# ── Full payload ──────────────────────────────────────────────────────────────


class TestFullAgenticUiPayload:
    """RicoChatResponse validates with all agentic_ui fields populated simultaneously."""

    def test_full_payload_round_trip(self) -> None:
        ui = RicoAgenticUi(
            actions=[
                RicoChatAction(id="view", label="View jobs", kind=RicoActionKind.navigate),
            ],
            permission_request=RicoPermissionRequest(
                id="perm-001",
                title="Apply to job",
                summary="Rico will apply on your behalf.",
                risk_level="high",
                approve_action=_approve_action(),
                cancel_action=_cancel_action(),
            ),
            progress=[
                RicoProgressStep(id="step-1", label="Analyzing", status="complete"),
            ],
            proposed_changes=[
                RicoProposedChange(
                    field="target_roles",
                    proposed_value=["HSE Manager"],
                    source="user_action",
                ),
            ],
            attachment_analysis=[
                RicoAttachmentAnalysis(
                    id="att-001",
                    purpose=RicoAttachmentPurpose.job_post,
                    confidence=0.9,
                ),
            ],
        )
        r = RicoChatResponse(message="Ready to proceed.", agentic_ui=ui)
        dumped = r.model_dump()

        assert dumped["agentic_ui"]["actions"][0]["id"] == "view"
        assert dumped["agentic_ui"]["permission_request"]["risk_level"] == "high"
        assert dumped["agentic_ui"]["progress"][0]["status"] == "complete"
        assert dumped["agentic_ui"]["proposed_changes"][0]["field"] == "target_roles"
        assert dumped["agentic_ui"]["attachment_analysis"][0]["purpose"] == "job_post"

    def test_serialization_round_trip(self) -> None:
        r = RicoChatResponse(
            message="Test",
            agentic_ui=RicoAgenticUi(
                actions=[
                    RicoChatAction(id="a1", label="Do something", kind=RicoActionKind.submit)
                ]
            ),
        )
        dumped = r.model_dump()
        restored = RicoChatResponse.model_validate(dumped)
        assert restored.agentic_ui is not None
        assert restored.agentic_ui.actions[0].kind == RicoActionKind.submit

    def test_agentic_ui_null_omitted_with_exclude_none(self) -> None:
        r = RicoChatResponse(message="Old-style response")
        dumped = r.model_dump(exclude_none=True)
        assert "agentic_ui" not in dumped

    def test_legacy_fields_coexist_with_agentic_ui(self) -> None:
        r = RicoChatResponse(
            message="Found jobs.",
            type="job_search_results",
            matches=[{"title": "HSE Manager"}],
            next_actions=[{"action": "view_jobs", "label": "View jobs"}],
            agentic_ui=RicoAgenticUi(
                actions=[
                    RicoChatAction(id="view", label="View jobs", kind=RicoActionKind.navigate)
                ]
            ),
        )
        assert r.message == "Found jobs."
        assert len(r.matches) == 1
        assert r.agentic_ui is not None
        assert len(r.agentic_ui.actions) == 1
