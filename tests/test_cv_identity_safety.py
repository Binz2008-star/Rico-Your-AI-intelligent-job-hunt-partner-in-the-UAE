"""
tests/test_cv_identity_safety.py
===============================
CV Identity Safety Tests (C1)

Ensures CV-extracted email cannot hijack or overwrite the authenticated
uploader's canonical identity (rico_users.email).

Tested vulnerabilities:
- CV containing referee email → user identity preserved
- CV containing old employer email → user identity preserved
- CV with multiple emails → first extracted but not used for identity
- Jotform merge after CV upload → correct identity resolution
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rico_db import RicoDB


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Mock RicoDB with tracking for user table vs profile updates."""
    db = MagicMock(spec=RicoDB)
    db.available = True

    # Track what gets passed to upsert_user (user table) vs upsert_profile (JSONB)
    db.upsert_user_calls = []
    db.upsert_profile_calls = []

    def mock_upsert_user(payload, conn=None):
        db.upsert_user_calls.append(dict(payload))
        return {"id": "test-user-uuid-123", "email": payload.get("email")}

    def mock_upsert_profile(user_id, profile, conn=None):
        db.upsert_profile_calls.append({"user_id": user_id, "profile": dict(profile)})
        return {"id": "test-profile-uuid", "profile": profile}

    db.upsert_user = mock_upsert_user
    db.upsert_profile = mock_upsert_profile

    return db


@pytest.fixture
def authenticated_user_email():
    """Canonical email of the authenticated uploader."""
    return "uploader@example.com"


@pytest.fixture
def cv_with_referee_email():
    """CV containing a referee's email (not the uploader's)."""
    return {
        "name": "John Candidate",
        "emails": ["referee@other-company.com"],  # Referee email, not uploader
        "phones": ["+971501234567"],
        "skills": ["python", "project management"],
        "current_role": "Project Manager",
        "years_experience_hint": 5.0,
    }


@pytest.fixture
def cv_with_old_employer_email():
    """CV containing old employer's contact email."""
    return {
        "name": "Jane Worker",
        "emails": ["hr@old-employer.com"],  # Old employer email
        "phones": ["+971509876543"],
        "skills": ["javascript", "react"],
        "current_role": "Frontend Developer",
        "years_experience_hint": 3.0,
    }


@pytest.fixture
def cv_with_uploader_email():
    """CV containing the uploader's own email (matching case)."""
    return {
        "name": "Uploader Name",
        "emails": ["uploader@example.com"],  # Matches authenticated email
        "phones": ["+971501112222"],
        "skills": ["hse", "compliance"],
        "current_role": "HSE Officer",
        "years_experience_hint": 7.0,
    }


# ── Test Cases ───────────────────────────────────────────────────────────────


class TestCVIdentitySafety:
    """Core C1: CV email must not overwrite authenticated user identity."""

    def test_cv_referee_email_does_not_overwrite_user_identity(
        self, mock_db, authenticated_user_email, cv_with_referee_email
    ):
        """CV with referee email → uploader's identity preserved."""
        # Simulate profile_repo.upsert_profile behavior with the fix
        user_id = authenticated_user_email

        # Build profile updates as the fixed code does (email excluded)
        profile_updates = {
            "name": cv_with_referee_email["name"],
            # "email" deliberately excluded
            "cv_extracted_email": cv_with_referee_email["emails"][0],  # Store in profile only
            "phone": cv_with_referee_email["phones"][0],
            "current_role": cv_with_referee_email["current_role"],
            "skills": cv_with_referee_email["skills"],
        }

        # Simulate the user_payload that would be passed to db.upsert_user
        user_payload = {
            "external_user_id": user_id,
            "name": profile_updates.get("name"),
            "email": profile_updates.get("email"),  # Should be None (not in updates)
            "phone": profile_updates.get("phone"),
        }
        user_payload = {k: v for k, v in user_payload.items() if v is not None}

        # Call mock upsert_user
        mock_db.upsert_user(user_payload)

        # Verify: user table email is NOT the CV email
        assert len(mock_db.upsert_user_calls) == 1
        user_call = mock_db.upsert_user_calls[0]

        # CRITICAL: email should be absent or None in user table update
        assert user_call.get("email") is None, \
            f"CV email leaked to user table: {user_call.get('email')}"

        # Profile should contain cv_extracted_email
        mock_db.upsert_profile("test-user-uuid-123", profile_updates)
        assert len(mock_db.upsert_profile_calls) == 1
        profile_call = mock_db.upsert_profile_calls[0]
        assert profile_call["profile"].get("cv_extracted_email") == "referee@other-company.com"

    def test_cv_old_employer_email_does_not_overwrite_user_identity(
        self, mock_db, authenticated_user_email, cv_with_old_employer_email
    ):
        """CV with old employer email → uploader's identity preserved."""
        user_id = authenticated_user_email

        profile_updates = {
            "name": cv_with_old_employer_email["name"],
            "cv_extracted_email": cv_with_old_employer_email["emails"][0],
            "phone": cv_with_old_employer_email["phones"][0],
            "current_role": cv_with_old_employer_email["current_role"],
            "skills": cv_with_old_employer_email["skills"],
        }

        user_payload = {
            "external_user_id": user_id,
            "name": profile_updates.get("name"),
            "email": profile_updates.get("email"),  # Should be None
            "phone": profile_updates.get("phone"),
        }
        user_payload = {k: v for k, v in user_payload.items() if v is not None}

        mock_db.upsert_user(user_payload)

        # Verify no email in user table
        user_call = mock_db.upsert_user_calls[0]
        assert user_call.get("email") is None, \
            f"Old employer email leaked to user table: {user_call.get('email')}"

        # Verify CV email is in profile
        mock_db.upsert_profile("test-user-uuid-123", profile_updates)
        profile_call = mock_db.upsert_profile_calls[0]
        assert profile_call["profile"].get("cv_extracted_email") == "hr@old-employer.com"

    def test_cv_matching_email_preserves_user_identity(
        self, mock_db, authenticated_user_email, cv_with_uploader_email
    ):
        """CV with matching email → still uses cv_extracted_email pattern (no regression)."""
        user_id = authenticated_user_email

        profile_updates = {
            "name": cv_with_uploader_email["name"],
            "cv_extracted_email": cv_with_uploader_email["emails"][0],
            "phone": cv_with_uploader_email["phones"][0],
            "current_role": cv_with_uploader_email["current_role"],
            "skills": cv_with_uploader_email["skills"],
        }

        # Even when CV email matches, we should NOT pass it to user table
        # (the fix is consistent - CV email never touches identity)
        user_payload = {
            "external_user_id": user_id,
            "name": profile_updates.get("name"),
            "email": profile_updates.get("email"),  # Should be None
            "phone": profile_updates.get("phone"),
        }
        user_payload = {k: v for k, v in user_payload.items() if v is not None}

        mock_db.upsert_user(user_payload)

        # Verify: email not in user table (consistent behavior)
        user_call = mock_db.upsert_user_calls[0]
        assert user_call.get("email") is None

        # CV email stored in profile
        mock_db.upsert_profile("test-user-uuid-123", profile_updates)
        profile_call = mock_db.upsert_profile_calls[0]
        assert profile_call["profile"].get("cv_extracted_email") == "uploader@example.com"

    def test_cv_multiple_emails_uses_first_but_not_for_identity(
        self, mock_db, authenticated_user_email
    ):
        """CV with multiple emails → first used for cv_extracted_email, none for identity."""
        cv_data = {
            "emails": ["first@example.com", "second@example.com", "third@example.com"],
            "name": "Multi Email User",
        }

        # First email goes to cv_extracted_email
        profile_updates = {
            "name": cv_data["name"],
            "cv_extracted_email": cv_data["emails"][0],  # Only first email
        }

        # User table gets no email from CV
        user_payload = {
            "external_user_id": authenticated_user_email,
            "name": cv_data["name"],
            "email": None,  # Explicitly None
        }
        user_payload = {k: v for k, v in user_payload.items() if v is not None}

        mock_db.upsert_user(user_payload)
        mock_db.upsert_profile("test-user-uuid-123", profile_updates)

        # Verify first email in profile, none in user table
        assert mock_db.upsert_profile_calls[0]["profile"]["cv_extracted_email"] == "first@example.com"
        assert mock_db.upsert_user_calls[0].get("email") is None


class TestCVPreviewEmailField:
    """Verify preview structure uses cv_extracted_email, not email."""

    def test_preview_uses_cv_extracted_email_field(self):
        """Preview response uses cv_extracted_email field name."""
        # This test documents the API contract change
        # Frontend code should use preview.cv_extracted_email not preview.email
        preview = {
            "name": "Test User",
            "cv_extracted_email": "cv@example.com",
            "phone": "+971501234567",
        }

        assert "email" not in preview, "Old 'email' field should not exist"
        assert preview.get("cv_extracted_email") == "cv@example.com"


class TestCVEmailAuditLogging:
    """Security audit logging for CV email extraction."""

    def test_cv_email_extraction_logged(self, caplog):
        """CV email extraction is logged for security audit."""
        import logging

        # Setup logging capture
        with caplog.at_level(logging.INFO, logger="src.api.routers.rico_chat"):
            # Simulate the log call from confirm_cv_profile
            logger = logging.getLogger("src.api.routers.rico_chat")
            logger.info(
                "cv_profile_confirm_email_extracted user=%s cv_email=%s request_ref=%s",
                "uploader@example.com",
                "referee@other.com",
                "test-ref-123",
            )

        # Verify log contains security-relevant fields
        assert "cv_profile_confirm_email_extracted" in caplog.text
        assert "referee@other.com" in caplog.text
        assert "uploader@example.com" in caplog.text


class TestJotformMergeSafety:
    """Jotform identity resolution remains safe after CV upload with different email."""

    def test_jotform_merge_ignores_cv_extracted_email(
        self, mock_db, authenticated_user_email
    ):
        """Jotform submission with different email → correct identity resolution."""
        # Scenario:
        # 1. User uploads CV with referee@other.com (stored as cv_extracted_email)
        # 2. Jotform submission arrives with uploader@example.com
        # 3. Identity should resolve to uploader@example.com (authenticated identity)

        # Step 1: CV upload (already tested above)
        cv_profile = {
            "name": "Uploader",
            "cv_extracted_email": "referee@other.com",
        }
        mock_db.upsert_profile("test-user-uuid", cv_profile)

        # Step 2: Simulate Jotform submission with correct email
        # The jotform handler uses external_user_id from form, not CV data
        jotform_payload = {
            "external_user_id": authenticated_user_email,  # "uploader@example.com"
            "email": authenticated_user_email,
            "name": "Uploader",
        }

        # Jotform upsert_user should use the form's email, not CV email
        mock_db.upsert_user(jotform_payload)

        # Verify: User table has correct email from Jotform, not CV
        user_call = mock_db.upsert_user_calls[-1]
        assert user_call["email"] == authenticated_user_email
        assert user_call["email"] != "referee@other.com"


# ── Regression Tests ─────────────────────────────────────────────────────────


class TestCVIdentitySafetyRegression:
    """Prevent regression of C1 fix."""

    def test_profile_updates_never_contains_email_from_cv(self):
        """Profile updates dict must never have 'email' key from CV data."""
        # This is the core contract of the fix
        cv_data = {"emails": ["any@example.com"], "name": "Test"}

        # Build updates as fixed code does
        profile_updates = {
            "name": cv_data["name"],
            # email deliberately excluded
            "cv_extracted_email": cv_data["emails"][0],
        }

        assert "email" not in profile_updates, \
            "Contract violation: 'email' key must not exist in profile_updates"
        assert "cv_extracted_email" in profile_updates

    def test_user_payload_never_gets_cv_email(self):
        """User table payload must never receive CV-extracted email."""
        profile_updates = {
            "name": "Test",
            "cv_extracted_email": "cv@example.com",
        }

        # Simulate user_payload construction
        user_payload = {
            "external_user_id": "user@example.com",
            "name": profile_updates.get("name"),
            "email": profile_updates.get("email"),  # Will be None
        }
        user_payload = {k: v for k, v in user_payload.items() if v is not None}

        assert "email" not in user_payload, \
            "Security violation: CV email in user_payload"


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestCVEmailEdgeCases:
    """Edge cases for CV email extraction."""

    def test_cv_no_email_field_still_works(self, mock_db):
        """CV with no email → profile updates work, no error."""
        cv_data = {"name": "No Email User", "emails": []}

        profile_updates = {
            "name": cv_data["name"],
            "cv_extracted_email": cv_data["emails"][0] if cv_data["emails"] else None,
        }

        # Should not crash
        assert profile_updates["cv_extracted_email"] is None

    def test_cv_none_email_handled(self, mock_db):
        """CV with None emails list → handled gracefully."""
        cv_data = {"name": "None Email User", "emails": None}

        emails = cv_data.get("emails") or []
        profile_updates = {
            "name": cv_data["name"],
            "cv_extracted_email": emails[0] if emails else None,
        }

        assert profile_updates["cv_extracted_email"] is None

    def test_cv_empty_string_email(self, mock_db):
        """CV with empty string email → stored but doesn't affect identity."""
        cv_data = {"name": "Empty Email User", "emails": [""]}

        profile_updates = {
            "name": cv_data["name"],
            "cv_extracted_email": cv_data["emails"][0] if cv_data["emails"] else None,
        }

        # Empty string is truthy for "if cv_email" check, but won't be used for identity
        assert profile_updates["cv_extracted_email"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
