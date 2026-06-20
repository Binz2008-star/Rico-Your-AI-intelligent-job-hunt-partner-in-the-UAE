"""Tests for the synthetic/internal recipient guard in profile_nudge_service.

Covers:
  - _is_synthetic_email unit tests (all exclusion patterns + real addresses)
  - Full sweep mock: synthetic stamped+skipped, no email sent
  - Full sweep mock: internal @ricohunt.com domain stamped+skipped
  - Full sweep mock: real user with incomplete profile gets nudge sent
  - Full sweep mock: real user with complete profile skipped (no email)
  - Idempotency: second sweep finds nothing (already stamped)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from src.services.profile_nudge_service import _is_synthetic_email, run_profile_nudge_sweep


# ── _is_synthetic_email unit tests ────────────────────────────────────────────

class TestIsSyntheticEmail:
    # Internal domain — all @ricohunt.com excluded
    def test_ricohunt_domain_excluded(self):
        assert _is_synthetic_email("info@ricohunt.com") is True

    def test_ricohunt_admin_excluded(self):
        assert _is_synthetic_email("admin@ricohunt.com") is True

    def test_ricohunt_test_user_excluded(self):
        assert _is_synthetic_email("test_user_1469@ricohunt.com") is True

    def test_ricohunt_support_excluded(self):
        assert _is_synthetic_email("support@ricohunt.com") is True

    # Synthetic local parts — external domains
    def test_test_local_excluded(self):
        assert _is_synthetic_email("test@gmail.com") is True

    def test_test_user_local_excluded(self):
        assert _is_synthetic_email("test_user@outlook.com") is True

    def test_test_user_digits_excluded(self):
        assert _is_synthetic_email("test_user_123@example.org") is True

    def test_dummy_excluded(self):
        assert _is_synthetic_email("dummy@yahoo.com") is True

    def test_demo_excluded(self):
        assert _is_synthetic_email("demo@company.com") is True

    def test_demo_with_suffix_excluded(self):
        assert _is_synthetic_email("demo.account@company.com") is True

    def test_example_excluded(self):
        assert _is_synthetic_email("example@gmail.com") is True

    def test_seed_excluded(self):
        assert _is_synthetic_email("seed@company.com") is True

    def test_seed_with_suffix_excluded(self):
        assert _is_synthetic_email("seed_data@company.com") is True

    def test_fake_excluded(self):
        assert _is_synthetic_email("fake@hotmail.com") is True

    def test_user_digits_excluded(self):
        assert _is_synthetic_email("user_1469@gmail.com") is True

    def test_user_digits_short_excluded(self):
        assert _is_synthetic_email("user_1@outlook.com") is True

    def test_malformed_no_at_excluded(self):
        assert _is_synthetic_email("notanemail") is True

    # Real addresses — must NOT be excluded
    def test_real_gmail_eligible(self):
        assert _is_synthetic_email("ahmed.hassan@gmail.com") is False

    def test_real_outlook_eligible(self):
        assert _is_synthetic_email("sara.ali@outlook.com") is False

    def test_real_yahoo_eligible(self):
        assert _is_synthetic_email("jobseeker99@yahoo.com") is False

    def test_real_corporate_eligible(self):
        assert _is_synthetic_email("m.smith@consulting.ae") is False

    def test_testing_not_excluded(self):
        # "testing" starts with "test" but is not "test" or "test_user" — should pass
        assert _is_synthetic_email("testing@gmail.com") is False

    def test_seeds_not_excluded(self):
        # "seeds" is not exactly "seed" + separator
        assert _is_synthetic_email("seeds@company.com") is False

    def test_user_with_name_not_excluded(self):
        # user_john is not user_<digits>
        assert _is_synthetic_email("user_john@gmail.com") is False

    def test_demonstration_not_excluded(self):
        # "demonstration" starts with "demo" but is not "demo" + separator
        assert _is_synthetic_email("demonstration@company.com") is False


# ── Full sweep integration mocks ──────────────────────────────────────────────

def _make_row(user_id, email, name=None, cv_filename=None, target_roles=None, preferred_cities=None):
    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "cv_filename": cv_filename,
        "target_roles": target_roles,
        "preferred_cities": preferred_cities,
    }


def _mock_db_with_rows(rows, migration_present=True):
    """Build a mock RicoDB + connection that returns the given rows."""
    mock_db = MagicMock()
    mock_db.available = True
    mock_conn = MagicMock()
    mock_db.connect.return_value = mock_conn

    # cursor context manager
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # First fetchone: migration check; subsequent fetchall: rows
    mock_cur.fetchone.return_value = (1,) if migration_present else None
    mock_cur.fetchall.return_value = rows
    return mock_db, mock_conn, mock_cur


class TestSweepSyntheticSkipped:
    def test_synthetic_ricohunt_domain_stamped_not_sent(self):
        """test_user_123@ricohunt.com must be stamped and counted as skipped_synthetic."""
        row = _make_row(1, "test_user_123@ricohunt.com", cv_filename=None)
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([row])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email") as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_not_called()
        assert result["skipped_synthetic"] == 1
        assert result["nudges_sent"] == 0
        assert result["skipped"] == 0
        # stamp was written
        mock_conn.commit.assert_called()

    def test_info_ricohunt_stamped_not_sent(self):
        """info@ricohunt.com is an internal mailbox — must not receive a customer nudge."""
        row = _make_row(2, "info@ricohunt.com", cv_filename=None)
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([row])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email") as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_not_called()
        assert result["skipped_synthetic"] == 1
        assert result["nudges_sent"] == 0

    def test_dummy_external_domain_stamped_not_sent(self):
        row = _make_row(3, "dummy@company.ae", cv_filename=None)
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([row])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email") as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_not_called()
        assert result["skipped_synthetic"] == 1


class TestSweepRealUserEligible:
    def test_real_user_incomplete_profile_gets_nudge(self):
        """A real Gmail user with an incomplete profile must receive the nudge."""
        row = _make_row(10, "ahmed.hassan@gmail.com", name="Ahmed Hassan",
                        cv_filename=None, target_roles=None, preferred_cities=None)
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([row])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email", return_value=True) as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_email"] == "ahmed.hassan@gmail.com"
        assert result["nudges_sent"] == 1
        assert result["skipped_synthetic"] == 0
        assert result["skipped"] == 0


class TestSweepCompleteProfileSkipped:
    def test_complete_profile_stamped_not_sent(self):
        """Real user with all fields populated must be stamped but not emailed."""
        row = _make_row(20, "sara.ali@outlook.com", name="Sara Ali",
                        cv_filename="cv.pdf",
                        target_roles=["Marketing Manager"],
                        preferred_cities=["Dubai"])
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([row])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email") as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_not_called()
        assert result["skipped"] == 1
        assert result["nudges_sent"] == 0
        assert result["skipped_synthetic"] == 0


class TestSweepIdempotency:
    def test_second_run_finds_nothing(self):
        """After all users are stamped, a second sweep returns zero counts."""
        mock_db, mock_conn, mock_cur = _mock_db_with_rows([])

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email") as mock_send:
            result = run_profile_nudge_sweep()

        mock_send.assert_not_called()
        assert result["nudges_sent"] == 0
        assert result["skipped"] == 0
        assert result["skipped_synthetic"] == 0
        assert result["status"] == "ok"


class TestSweepMixed:
    def test_mixed_batch_synthetic_and_real(self):
        """Synthetic users skipped, real user with incomplete profile gets nudge."""
        rows = [
            _make_row(1, "test_user_1469@ricohunt.com"),
            _make_row(2, "info@ricohunt.com"),
            _make_row(3, "user_999@gmail.com"),
            _make_row(4, "real.user@yahoo.com", cv_filename=None),
        ]
        mock_db, mock_conn, mock_cur = _mock_db_with_rows(rows)

        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch("src.services.mailer.send_email", return_value=True) as mock_send:
            result = run_profile_nudge_sweep()

        assert result["skipped_synthetic"] == 3  # ricohunt + ricohunt + user_999
        assert result["nudges_sent"] == 1        # real.user@yahoo.com
        assert result["skipped"] == 0
        mock_send.assert_called_once()
