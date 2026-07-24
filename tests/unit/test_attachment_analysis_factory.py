"""Unit tests for src/services/attachment_analysis_factory.py (CAREER-OS-04)."""
from dataclasses import dataclass, field
from typing import Any

from src.schemas.chat import RicoAttachmentAnalysis, RicoAttachmentPurpose
from src.services.attachment_analysis_factory import (
    build_attachment_analysis,
    build_attachment_analysis_dict,
    purpose_for_document_type,
)


@dataclass
class _FakeClassification:
    document_type: str
    confidence: float
    display_label: str
    file_format: str = "pdf"
    confidence_scores: dict[str, float] = field(default_factory=dict)


def test_purpose_mapping_known_types():
    assert purpose_for_document_type("job_description") == RicoAttachmentPurpose.job_post
    assert purpose_for_document_type("recruiter_email") == RicoAttachmentPurpose.recruiter_message
    assert purpose_for_document_type("offer_letter") == RicoAttachmentPurpose.offer_letter
    assert purpose_for_document_type("contract") == RicoAttachmentPurpose.contract_or_legalish
    assert purpose_for_document_type("company_profile") == RicoAttachmentPurpose.company_profile
    assert purpose_for_document_type("CV") == RicoAttachmentPurpose.cv_resume  # case-insensitive


def test_purpose_mapping_unknown_falls_back():
    assert purpose_for_document_type("something_weird") == RicoAttachmentPurpose.unknown_document
    assert purpose_for_document_type("") == RicoAttachmentPurpose.unknown_document


def test_build_returns_valid_model():
    c = _FakeClassification("job_description", 0.91, "Job Description")
    a = build_attachment_analysis(c, "role.pdf")
    assert isinstance(a, RicoAttachmentAnalysis)
    assert a.purpose == RicoAttachmentPurpose.job_post
    assert a.filename == "role.pdf"
    assert a.confidence == 0.91
    assert "Job Description" in (a.extracted_summary or "")
    assert a.extracted_fields["document_type"] == "job_description"
    assert a.id.startswith("att-")


def test_low_confidence_and_unknown_emit_a_single_warning():
    c = _FakeClassification("mystery", 0.2, "Document")
    a = build_attachment_analysis(c, "x.pdf")
    assert a.purpose == RicoAttachmentPurpose.unknown_document
    # The unknown-purpose warning already states the uncertainty; a separate
    # low-confidence warning would just repeat the same fact, so exactly one
    # warning is emitted (previously both fired, producing a duplicate).
    assert len(a.warnings) == 1
    assert "not sure" in a.warnings[0].lower()


def test_low_confidence_known_type_still_warns():
    """A recognized type (not unknown_document) with low confidence still
    gets the low-confidence warning — only the unknown-document case
    suppresses it as redundant."""
    c = _FakeClassification("job_description", 0.3, "Job Description")
    a = build_attachment_analysis(c, "role.pdf")
    assert a.purpose == RicoAttachmentPurpose.job_post
    assert len(a.warnings) == 1
    assert "low classification confidence" in a.warnings[0].lower()


def test_dict_is_json_ready():
    c = _FakeClassification("certificate", 0.8, "Certificate / License")
    d = build_attachment_analysis_dict(c, "cert.pdf")
    assert isinstance(d, dict)
    assert d["purpose"] == "certificate"        # enum serialized to its value
    assert d["confidence"] == 0.8
    assert d["filename"] == "cert.pdf"


def test_handles_missing_attributes_gracefully():
    class _Bare:
        document_type = "unknown"
        confidence = 0.0
        display_label = "Document"
        file_format = "unknown"

    a = build_attachment_analysis(_Bare(), None)
    assert a.purpose == RicoAttachmentPurpose.unknown_document
    assert a.filename is None
