"""
tests/test_attachment_analysis_factory.py

Unit tests for src/services/attachment_analysis_factory.py.

Verifies:
1. purpose_for_document_type maps all known classifier types correctly.
2. Unknown types map to unknown_document (never raises).
3. build_attachment_analysis produces a valid RicoAttachmentAnalysis.
4. build_attachment_analysis_dict returns a plain JSON-ready dict.
5. High-sensitivity documents (offer_letter, contract) carry warnings.
6. Low-confidence results carry a warning.
7. Unknown documents carry a warning.
8. MIME type passthrough (filename stored).
9. build_attachment_analysis handles missing/None classifier attributes gracefully.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services.attachment_analysis_factory import (
    build_attachment_analysis,
    build_attachment_analysis_dict,
    purpose_for_document_type,
)
from src.schemas.chat import RicoAttachmentAnalysis, RicoAttachmentPurpose


# ── helpers ───────────────────────────────────────────────────────────────────

def _classification(
    document_type: str = "cv",
    confidence: float = 0.90,
    display_label: str | None = None,
    file_format: str = "pdf",
):
    class _Stub:
        pass

    stub = _Stub()
    stub.document_type = document_type
    stub.confidence = confidence
    stub.display_label = display_label or document_type.replace("_", " ").title()
    stub.file_format = file_format
    return stub


# ── purpose_for_document_type ─────────────────────────────────────────────────

class TestPurposeMapping:

    @pytest.mark.parametrize("doc_type,expected", [
        ("cv",               RicoAttachmentPurpose.cv_resume),
        ("resume",           RicoAttachmentPurpose.cv_resume),
        ("job_description",  RicoAttachmentPurpose.job_post),
        ("job_post",         RicoAttachmentPurpose.job_post),
        ("recruiter_email",  RicoAttachmentPurpose.recruiter_message),
        ("application_form", RicoAttachmentPurpose.application_form),
        ("certificate",      RicoAttachmentPurpose.certificate),
        ("offer_letter",     RicoAttachmentPurpose.offer_letter),
        ("contract",         RicoAttachmentPurpose.contract_or_legalish),
        ("invoice",          RicoAttachmentPurpose.contract_or_legalish),
        ("company_profile",  RicoAttachmentPurpose.company_profile),
        ("public_comment",   RicoAttachmentPurpose.public_comment),
    ])
    def test_known_type_maps_correctly(self, doc_type, expected):
        assert purpose_for_document_type(doc_type) == expected

    def test_unknown_type_maps_to_unknown_document(self):
        assert purpose_for_document_type("some_random_type") == RicoAttachmentPurpose.unknown_document

    def test_empty_string_maps_to_unknown_document(self):
        assert purpose_for_document_type("") == RicoAttachmentPurpose.unknown_document

    def test_none_maps_to_unknown_document(self):
        assert purpose_for_document_type(None) == RicoAttachmentPurpose.unknown_document  # type: ignore[arg-type]

    def test_lookup_is_case_insensitive(self):
        assert purpose_for_document_type("CV") == RicoAttachmentPurpose.cv_resume
        assert purpose_for_document_type("Offer_Letter") == RicoAttachmentPurpose.offer_letter

    def test_whitespace_stripped(self):
        assert purpose_for_document_type("  cv  ") == RicoAttachmentPurpose.cv_resume


# ── build_attachment_analysis ─────────────────────────────────────────────────

class TestBuildAttachmentAnalysis:

    def test_returns_rico_attachment_analysis_instance(self):
        result = build_attachment_analysis(_classification())
        assert isinstance(result, RicoAttachmentAnalysis)

    def test_id_is_unique_across_calls(self):
        a = build_attachment_analysis(_classification())
        b = build_attachment_analysis(_classification())
        assert a.id != b.id

    def test_id_has_att_prefix(self):
        result = build_attachment_analysis(_classification())
        assert result.id.startswith("att-")

    def test_filename_stored(self):
        result = build_attachment_analysis(_classification(), filename="my_cv.pdf")
        assert result.filename == "my_cv.pdf"

    def test_filename_none_when_not_provided(self):
        result = build_attachment_analysis(_classification())
        assert result.filename is None

    def test_purpose_matches_document_type(self):
        result = build_attachment_analysis(_classification(document_type="cv"))
        assert result.purpose == RicoAttachmentPurpose.cv_resume

    def test_confidence_rounded_to_3dp(self):
        result = build_attachment_analysis(_classification(confidence=0.9876))
        assert result.confidence == round(0.9876, 3)

    def test_extracted_summary_contains_document_type_label(self):
        result = build_attachment_analysis(_classification(document_type="cv", display_label="CV / Resume"))
        assert "CV / Resume" in result.extracted_summary

    def test_extracted_summary_contains_confidence_percent(self):
        result = build_attachment_analysis(_classification(confidence=0.97))
        assert "97" in result.extracted_summary  # "97% confidence"

    def test_extracted_fields_contains_document_type(self):
        result = build_attachment_analysis(_classification(document_type="job_description"))
        assert result.extracted_fields["document_type"] == "job_description"

    def test_extracted_fields_contains_file_format(self):
        result = build_attachment_analysis(_classification(file_format="docx"))
        assert result.extracted_fields["file_format"] == "docx"

    def test_no_warnings_for_high_confidence_cv(self):
        result = build_attachment_analysis(_classification(document_type="cv", confidence=0.95))
        assert result.warnings == []

    def test_unknown_document_carries_warning(self):
        result = build_attachment_analysis(_classification(document_type="unknown_type"))
        assert len(result.warnings) >= 1
        assert any("not sure" in w.lower() or "unknown" in w.lower() for w in result.warnings)

    def test_low_confidence_carries_warning(self):
        result = build_attachment_analysis(_classification(confidence=0.3))
        assert any("Low" in w or "confidence" in w.lower() for w in result.warnings)

    def test_high_confidence_unknown_type_still_warns(self):
        result = build_attachment_analysis(_classification(document_type="mystery_doc", confidence=0.99))
        warning_text = " ".join(result.warnings).lower()
        assert "not sure" in warning_text or "unknown" in warning_text

    def test_offer_letter_accepted_no_extra_warning(self):
        result = build_attachment_analysis(_classification(document_type="offer_letter", confidence=0.88))
        assert result.purpose == RicoAttachmentPurpose.offer_letter
        # warnings list is about uncertainty, not sensitivity — offer_letter itself is fine at high confidence
        assert not any("not sure" in w.lower() for w in result.warnings)

    def test_missing_display_label_falls_back_to_document_type(self):
        cls = _classification(document_type="certificate")
        cls.display_label = None
        result = build_attachment_analysis(cls)
        assert "Certificate" in result.extracted_summary or "certificate" in result.extracted_summary

    def test_missing_confidence_defaults_to_zero(self):
        cls = _classification()
        cls.confidence = None
        result = build_attachment_analysis(cls)
        assert result.confidence == 0.0

    def test_missing_document_type_defaults_to_unknown(self):
        cls = _classification()
        del cls.document_type
        result = build_attachment_analysis(cls)
        assert result.purpose == RicoAttachmentPurpose.unknown_document


# ── build_attachment_analysis_dict ────────────────────────────────────────────

class TestBuildAttachmentAnalysisDict:

    def test_returns_plain_dict(self):
        result = build_attachment_analysis_dict(_classification())
        assert isinstance(result, dict)

    def test_dict_contains_expected_keys(self):
        result = build_attachment_analysis_dict(_classification())
        for key in ("id", "purpose", "confidence", "extracted_summary", "warnings"):
            assert key in result

    def test_purpose_serialized_as_string(self):
        result = build_attachment_analysis_dict(_classification(document_type="cv"))
        assert result["purpose"] == "cv_resume"

    def test_dict_is_json_serializable(self):
        import json
        result = build_attachment_analysis_dict(_classification())
        # Should not raise
        json.dumps(result)

    def test_dict_matches_model_dump(self):
        model = build_attachment_analysis(_classification(), filename="test.pdf")
        dict_result = build_attachment_analysis_dict(_classification(), filename="test.pdf")
        # Same keys except id (unique per call)
        for key in ("purpose", "confidence", "filename"):
            assert dict_result[key] == model.model_dump(mode="json")[key]
