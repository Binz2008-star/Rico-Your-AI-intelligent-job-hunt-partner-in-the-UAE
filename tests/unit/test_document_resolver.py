"""Tests for document_resolver service.

All DB calls are mocked via patch on get_user_documents so no live DB is needed.

Coverage:
  - get_cv_candidates filters to 'cv' type only
  - get_primary_cv returns is_primary=True, or None
  - get_latest_cv returns first item from sorted list, or None
  - resolve_user_cv: primary wins, latest fallback, profile fallback, None when nothing
  - has_cv: True/False
  - has_only_identity_documents: True when only identity docs, False otherwise
  - identity_document docs do not count as CVs
"""
from __future__ import annotations

import pytest
from unittest.mock import patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _patch_docs(docs):
    return patch(
        "src.services.document_resolver.get_user_documents",
        return_value=docs,
    )


# ── get_cv_candidates ─────────────────────────────────────────────────────────

class TestGetCvCandidates:
    def test_filters_to_cv_type_only(self):
        docs = [
            {"doc_type": "cv", "filename": "my_cv.pdf", "is_primary": True},
            {"doc_type": "cover_letter", "filename": "letter.pdf", "is_primary": False},
            {"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False},
            {"doc_type": "other", "filename": "cert.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import get_cv_candidates
            result = get_cv_candidates("user1")
        assert len(result) == 1
        assert result[0]["doc_type"] == "cv"

    def test_returns_empty_when_no_cvs(self):
        docs = [{"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import get_cv_candidates
            result = get_cv_candidates("user1")
        assert result == []

    def test_returns_empty_when_no_docs(self):
        with _patch_docs([]):
            from src.services.document_resolver import get_cv_candidates
            result = get_cv_candidates("user1")
        assert result == []


# ── get_primary_cv ────────────────────────────────────────────────────────────

class TestGetPrimaryCv:
    def test_returns_primary(self):
        docs = [
            {"doc_type": "cv", "filename": "primary.pdf", "is_primary": True},
            {"doc_type": "cv", "filename": "other.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import get_primary_cv
            result = get_primary_cv("user1")
        assert result is not None
        assert result["filename"] == "primary.pdf"

    def test_returns_none_when_no_primary(self):
        docs = [{"doc_type": "cv", "filename": "cv.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import get_primary_cv
            result = get_primary_cv("user1")
        assert result is None

    def test_returns_none_when_no_cv_docs(self):
        docs = [{"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": True}]
        with _patch_docs(docs):
            from src.services.document_resolver import get_primary_cv
            result = get_primary_cv("user1")
        assert result is None


# ── get_latest_cv ─────────────────────────────────────────────────────────────

class TestGetLatestCv:
    def test_returns_first_cv_in_list(self):
        # list_user_documents returns primary-first then newest — mock preserves that order
        docs = [
            {"doc_type": "cv", "filename": "latest.pdf", "is_primary": False},
            {"doc_type": "cv", "filename": "older.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import get_latest_cv
            result = get_latest_cv("user1")
        assert result is not None
        assert result["filename"] == "latest.pdf"

    def test_returns_none_when_no_cvs(self):
        docs = [{"doc_type": "cover_letter", "filename": "letter.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import get_latest_cv
            result = get_latest_cv("user1")
        assert result is None


# ── resolve_user_cv ───────────────────────────────────────────────────────────

class TestResolveUserCv:
    def test_primary_wins_over_latest(self):
        """Primary CV is always preferred, regardless of upload order."""
        docs = [
            {"doc_type": "cv", "filename": "primary.pdf", "is_primary": True},
            {"doc_type": "cv", "filename": "newer_unprimary.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import resolve_user_cv
            result = resolve_user_cv("user1")
        assert result is not None
        assert result["filename"] == "primary.pdf"

    def test_latest_used_when_no_primary(self):
        """When no primary, the most recently uploaded CV is used."""
        docs = [
            {"doc_type": "cv", "filename": "latest.pdf", "is_primary": False},
            {"doc_type": "cv", "filename": "older.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import resolve_user_cv
            result = resolve_user_cv("user1")
        assert result is not None
        assert result["filename"] == "latest.pdf"

    def test_profile_fallback_when_no_user_documents(self):
        """Legacy profile CV is used when no user_documents exist."""
        with _patch_docs([]):
            from src.services.document_resolver import resolve_user_cv
            profile = {"cv_filename": "from_profile.pdf", "cv_status": "parsed"}
            result = resolve_user_cv("user1", profile=profile)
        assert result is not None
        assert result["filename"] == "from_profile.pdf"
        assert result.get("is_legacy") is True

    def test_profile_fallback_requires_parsed_status(self):
        """Profile fallback only activates when cv_status == 'parsed'."""
        with _patch_docs([]):
            from src.services.document_resolver import resolve_user_cv
            profile = {"cv_filename": "pending.pdf", "cv_status": "received_pending_extraction"}
            result = resolve_user_cv("user1", profile=profile)
        assert result is None

    def test_returns_none_when_nothing(self):
        """No documents and no profile → None."""
        with _patch_docs([]):
            from src.services.document_resolver import resolve_user_cv
            result = resolve_user_cv("user1")
        assert result is None

    def test_identity_docs_not_counted_as_cv(self):
        """Passport/Emirates ID docs do not satisfy CV resolution."""
        docs = [{"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import resolve_user_cv
            result = resolve_user_cv("user1")
        assert result is None

    def test_user_documents_takes_priority_over_profile(self):
        """CV in user_documents beats the legacy profile fallback."""
        docs = [{"doc_type": "cv", "filename": "real_cv.pdf", "is_primary": True}]
        with _patch_docs(docs):
            from src.services.document_resolver import resolve_user_cv
            profile = {"cv_filename": "old_profile_cv.pdf", "cv_status": "parsed"}
            result = resolve_user_cv("user1", profile=profile)
        assert result is not None
        assert result["filename"] == "real_cv.pdf"


# ── has_cv ────────────────────────────────────────────────────────────────────

class TestHasCv:
    def test_true_when_cv_in_user_documents(self):
        docs = [{"doc_type": "cv", "filename": "cv.pdf", "is_primary": True}]
        with _patch_docs(docs):
            from src.services.document_resolver import has_cv
            assert has_cv("user1") is True

    def test_false_when_only_identity_docs(self):
        docs = [{"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import has_cv
            assert has_cv("user1") is False

    def test_true_via_profile_fallback(self):
        with _patch_docs([]):
            from src.services.document_resolver import has_cv
            profile = {"cv_filename": "cv.pdf", "cv_status": "parsed"}
            assert has_cv("user1", profile=profile) is True

    def test_false_when_nothing(self):
        with _patch_docs([]):
            from src.services.document_resolver import has_cv
            assert has_cv("user1") is False


# ── has_only_identity_documents ───────────────────────────────────────────────

class TestHasOnlyIdentityDocuments:
    def test_true_when_only_passport(self):
        docs = [{"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import has_only_identity_documents
            assert has_only_identity_documents("user1") is True

    def test_false_when_cv_also_present(self):
        docs = [
            {"doc_type": "cv", "filename": "cv.pdf", "is_primary": True},
            {"doc_type": "identity_document", "filename": "passport.pdf", "is_primary": False},
        ]
        with _patch_docs(docs):
            from src.services.document_resolver import has_only_identity_documents
            assert has_only_identity_documents("user1") is False

    def test_false_when_no_docs(self):
        with _patch_docs([]):
            from src.services.document_resolver import has_only_identity_documents
            assert has_only_identity_documents("user1") is False

    def test_false_when_only_cover_letter(self):
        """Cover letter without any identity doc should return False."""
        docs = [{"doc_type": "cover_letter", "filename": "letter.pdf", "is_primary": False}]
        with _patch_docs(docs):
            from src.services.document_resolver import has_only_identity_documents
            assert has_only_identity_documents("user1") is False
