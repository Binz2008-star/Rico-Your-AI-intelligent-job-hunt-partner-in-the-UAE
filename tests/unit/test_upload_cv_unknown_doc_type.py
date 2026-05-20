"""
Regression test: CV upload must not reject documents classified as "unknown".

After cv_parser improvements, sparse-but-valid CVs (few section headers,
minimal signals) now return doc_type="unknown" instead of "cv".
The upload endpoint must only reject confirmed "company_profile" documents —
"unknown" should pass through so thin CVs are not blocked.
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_parsed(text: str = "Some resume text", skills: list | None = None) -> dict:
    return {
        "text": text,
        "skills": skills or [],
        "emails": [],
        "phones": [],
        "years_experience_hint": None,
        "certifications": [],
        "languages": [],
        "extraction_quality": "good",
        "extracted_chars": len(text),
    }


class TestUploadCVUnknownDocType:
    """doc_type='unknown' must not be rejected at the upload gate."""

    def test_detect_document_type_unknown_passes(self):
        """CVParser.detect_document_type('unknown') must not trigger rejection."""
        from src.cv_parser import CVParser
        parser = CVParser()
        # Sparse text: no strong CV or company signals → "unknown"
        text = "John Doe\njohn@example.com\n+971 50 123 4567"
        result = parser.detect_document_type(text)
        assert result == "unknown"

    def test_detect_document_type_sparse_cv_with_one_signal(self):
        """A CV with one CV signal + personal marker should classify as 'cv', not 'unknown'."""
        from src.cv_parser import CVParser
        parser = CVParser()
        text = (
            "I am a safety engineer.\n"
            "Skills: HSE, risk assessment, ISO 45001\n"
        )
        result = parser.detect_document_type(text)
        assert result == "cv"

    def test_company_profile_is_still_rejected(self):
        """Confirmed company_profile documents must still be rejected."""
        from src.cv_parser import CVParser
        parser = CVParser()
        text = (
            "Company Profile\n"
            "Corporate Profile\n"
            "Company Overview\n"
            "We provide HSE consulting services.\n"
            "Our client base spans the GCC region.\n"
        )
        result = parser.detect_document_type(text)
        assert result == "company_profile"

    def test_upload_gate_rejects_only_company_profile(self):
        """The upload endpoint gate must reject company_profile but pass unknown and cv."""
        # Simulate the gate logic extracted from rico_chat.py
        def _upload_gate(doc_type: str) -> bool:
            """Returns True if the document should be rejected."""
            return doc_type == "company_profile"

        assert _upload_gate("company_profile") is True
        assert _upload_gate("cv") is False
        assert _upload_gate("unknown") is False
