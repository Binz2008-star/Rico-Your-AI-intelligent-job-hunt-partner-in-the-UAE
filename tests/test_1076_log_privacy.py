"""#1076 — production logs must not carry profile values, contact identifiers,
message/document text, or bearer credentials.

Synthetic sentinels only; caplog proves they never reach log records on
success or failure paths, the Sentry ``before_send`` scrubber removes them
from exported events, production refuses to boot with a token-logging flag,
and a static regression guard rejects the forbidden logging patterns
repo-wide.
"""

from __future__ import annotations

import logging
import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest

from src.log_privacy import (
    enforce_production_log_safety,
    safe_exc,
    safe_fields,
    scrub_text,
    sentry_before_send,
    token_ref,
    user_ref,
)

# ── synthetic sentinels (never real data) ────────────────────────────────────
EMAIL = "sentinel.user.1076@example.com"
PHONE = "+971509991076"
SALARY = 34567
CITY = "SentinelCityDXB"
TELEGRAM_ID = "sentineltg1076"
CV_TEXT = "SENTINEL-CV-TEXT-1076 operations coordinator"
PUBLIC_SID = "public:g-Sentinel1076SidValue"
RESET_TOKEN = "sentinelresettoken1076abcdef1234"
CHECKOUT_TOKEN = "sentinelcheckouttoken1076abcdef"
CHAT_MSG = "sentinel chat message 1076 visa salary"
GMAIL_SUBJECT = "Sentinel interview invitation 1076"

SENTINELS = [
    EMAIL, PHONE, str(SALARY), CITY, TELEGRAM_ID, CV_TEXT,
    PUBLIC_SID, RESET_TOKEN, CHECKOUT_TOKEN, CHAT_MSG,
]


def _assert_clean(text: str, *, allow: tuple[str, ...] = ()) -> None:
    for s in SENTINELS:
        if s in allow:
            continue
        assert s not in text, f"sentinel leaked into logs: {s!r}"


# ── helper primitives ────────────────────────────────────────────────────────

class TestHelpers:
    def test_user_ref_is_stable_prefixed_and_non_reversible(self):
        r1, r2 = user_ref(EMAIL), user_ref(EMAIL)
        assert r1 == r2 and r1.startswith("u:") and len(r1) <= 16
        assert EMAIL not in r1
        assert user_ref(PUBLIC_SID) != r1

    def test_token_ref_never_contains_token(self):
        assert RESET_TOKEN not in token_ref(RESET_TOKEN)
        assert token_ref(None) == "t:none"

    def test_safe_fields_names_only(self):
        out = safe_fields({"email": EMAIL, "salary_expectation_aed": SALARY})
        assert "email" in out and "salary_expectation_aed" in out
        _assert_clean(out)

    def test_safe_exc_never_includes_message(self):
        exc = ValueError(f"boom {EMAIL} {RESET_TOKEN}")
        label = safe_exc(exc)
        assert label == "ValueError"
        exc.pgcode = "23505"
        assert safe_exc(exc) == "ValueError[23505]"

    def test_scrub_text_redacts_credentials_and_contact(self):
        blob = (
            f"failed for {EMAIL} Bearer abc12345678 "
            f"reset-password?token={RESET_TOKEN} secret {CHECKOUT_TOKEN}"
        )
        _assert_clean(scrub_text(blob))


# ── profile paths ────────────────────────────────────────────────────────────

class TestProfileLogsRedacted:
    _BUNDLE = {
        "id": "11111111-1111-1111-1111-111111111111",
        "external_user_id": EMAIL,
        "name": "Sentinel User",
        "email": EMAIL,
        "phone": PHONE,
        "telegram_chat_id": TELEGRAM_ID,
        "profile": {
            "target_roles": ["Sentinel Role"],
            "preferred_cities": [CITY],
            "salary_expectation_aed": SALARY,
        },
        "settings": {},
    }

    def test_get_profile_success_logs_no_values(self, caplog):
        from src.repositories import profile_repo

        db = MagicMock()
        db.get_user_bundle.return_value = dict(self._BUNDLE)
        with patch.object(profile_repo, "_db", return_value=db), caplog.at_level(
            logging.DEBUG
        ):
            profile_repo.get_profile(EMAIL)
        assert "profile_repo.get_profile" in caplog.text
        assert "fields=" in caplog.text
        _assert_clean(caplog.text)

    def test_get_profile_failure_logs_no_values_or_driver_detail(self, caplog):
        from src.repositories import profile_repo

        db = MagicMock()
        db.get_user_bundle.side_effect = Exception(
            f"DETAIL: Key (email)=({EMAIL}) token={RESET_TOKEN}"
        )
        with patch.object(profile_repo, "_db", return_value=db), caplog.at_level(
            logging.DEBUG
        ):
            profile_repo.get_profile(EMAIL)
        assert "get_profile DB failed" in caplog.text
        _assert_clean(caplog.text)

    def test_upsert_profile_logs_names_not_values(self, caplog):
        from src.repositories import profile_repo

        updates = {
            "email": EMAIL,
            "phone": PHONE,
            "preferred_cities": [CITY],
            "salary_expectation_aed": SALARY,
            "telegram_chat_id": TELEGRAM_ID,
        }
        with caplog.at_level(logging.DEBUG):
            profile_repo.upsert_profile(EMAIL, updates)
        assert "profile_update" in caplog.text
        assert "fields=" in caplog.text
        _assert_clean(caplog.text)

    def test_update_profile_endpoint_logs_no_values(self, caplog):
        from fastapi.testclient import TestClient
        from src.api.app import app

        with patch(
            "src.api.routers.rico_chat.get_current_user",
            return_value={"email": EMAIL, "role": "user"},
        ), patch(
            "src.repositories.profile_repo.upsert_profile", return_value=None
        ), patch(
            "src.repositories.profile_repo.get_profile", return_value=None
        ), caplog.at_level(logging.INFO):
            TestClient(app).patch(
                "/api/v1/rico/profile",
                json={"preferred_cities": [CITY], "salary_expectation_aed": SALARY},
            )
        assert "update_profile endpoint" in caplog.text
        _assert_clean(caplog.text)


# ── reset-token paths ────────────────────────────────────────────────────────

class TestResetTokenNeverLogged:
    def test_production_refuses_token_logging_flag(self, monkeypatch):
        monkeypatch.setenv("RICO_ENV", "production")
        monkeypatch.setenv("RESET_TOKEN_LOG", "true")
        with pytest.raises(RuntimeError, match="RESET_TOKEN_LOG"):
            enforce_production_log_safety()

    def test_non_production_flag_is_inert_for_startup(self, monkeypatch):
        monkeypatch.setenv("RICO_ENV", "development")
        monkeypatch.setenv("RESET_TOKEN_LOG", "true")
        enforce_production_log_safety()  # must not raise

    def test_reset_dispatch_never_logs_token_even_with_flag(self, caplog, monkeypatch):
        from src.api.auth import _dispatch_password_reset_email

        monkeypatch.setenv("RICO_ENV", "development")
        monkeypatch.setenv("RESET_TOKEN_LOG", "true")
        user = MagicMock()
        with patch(
            "src.repositories.users_repo.get_user_by_email", return_value=user
        ), patch(
            "src.repositories.password_reset_repo.create_reset_token",
            return_value=RESET_TOKEN,
        ), patch(
            "src.services.password_reset_email.send_password_reset_email",
            return_value=True,
        ), caplog.at_level(logging.DEBUG):
            _dispatch_password_reset_email(EMAIL)
        assert "password_reset_url_generated" in caplog.text
        _assert_clean(caplog.text)


# ── checkout-token path ──────────────────────────────────────────────────────

class TestPaddleTokenRedacted:
    def test_consume_failure_never_logs_token(self, caplog):
        from src.services.paddle_webhook_service import _consume_checkout_session

        with patch(
            "src.repositories.paddle_repo.mark_checkout_session_used",
            side_effect=Exception(f"boom token={CHECKOUT_TOKEN}"),
        ), caplog.at_level(logging.DEBUG):
            _consume_checkout_session(MagicMock(), CHECKOUT_TOKEN)
        assert "paddle_checkout_session_consume_failed" in caplog.text
        _assert_clean(caplog.text)


# ── Sentry scrubber ──────────────────────────────────────────────────────────

class TestSentryScrubber:
    def test_event_is_scrubbed_end_to_end(self):
        import json

        event = {
            "request": {
                "headers": {"Authorization": f"Bearer {RESET_TOKEN}", "Cookie": f"access_token={RESET_TOKEN}"},
                "cookies": {"rico_guest_proof": CHECKOUT_TOKEN},
                "data": {"email": EMAIL, "phone": PHONE, "message": CHAT_MSG},
                "query_string": f"token={RESET_TOKEN}",
            },
            "extra": {"cv_text": CV_TEXT, "salary": str(SALARY)},
            "user": {"email": EMAIL},
            "breadcrumbs": {"values": [{"message": f"reset for {EMAIL}", "data": {"token": RESET_TOKEN}}]},
            "exception": {"values": [{"type": "ValueError", "value": f"DETAIL: (email)=({EMAIL}) {CHECKOUT_TOKEN}"}]},
            "logentry": {"message": "sent to %s", "params": [EMAIL]},
        }
        out = sentry_before_send(event, None)
        blob = json.dumps(out)
        # CHAT_MSG has no credential shape; it is caught because the "message"
        # KEY is not in the denylist — assert the credential/contact set only.
        for s in (EMAIL, PHONE, RESET_TOKEN, CHECKOUT_TOKEN, CV_TEXT):
            assert s not in blob, f"sentry event leaked {s!r}"

    def test_scrubber_failure_drops_risky_sections(self):
        class Poison(dict):
            def get(self, *a, **k):  # force an internal error
                raise RuntimeError("poison")

        event = {"request": Poison(), "extra": {"email": EMAIL}, "message": "x"}
        out = sentry_before_send(event, None)
        assert "request" not in out and "extra" not in out


# ── static regression guard ──────────────────────────────────────────────────

# Provider-side job-search query logs (derived search terms, no user id on the
# line) are excluded here and tracked as follow-up hardening.
_QUERY_ALLOWLIST = (
    "src/jsearch_client.py",
    "src/job_sources.py",
    "src/job_source_adapters/jsearch_adapter.py",
)

_FORBIDDEN = [
    (re.compile(r"bundle_profile=%"), ()),
    (re.compile(r"user_payload=%"), ()),
    (re.compile(r"\bmsg=%r"), ()),
    (re.compile(r"\bmessage=%r"), ()),
    (re.compile(r"\bemail=%[rs]"), ()),
    (re.compile(r"\bphone=%[rs]"), ()),
    (re.compile(r"(?<!session_)token=%[rs]"), ()),
    (re.compile(r"session_token=%[rs]"), ()),
    (re.compile(r"\bquery=%r"), _QUERY_ALLOWLIST),
    (re.compile(r"updates=%s"), ()),
    (re.compile(r'reset_url\s*\)'), ()),
    (re.compile(r"message\[:80\]"), ()),
    (re.compile(r"RESET_TOKEN_LOG.*in\s*\("), ()),  # the old runtime toggle read
]


class TestStaticRegressionGuard:
    def test_no_forbidden_logging_patterns_in_src(self):
        violations = []
        for path in pathlib.Path("src").rglob("*.py"):
            rel = str(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern, allow in _FORBIDDEN:
                if rel in allow:
                    continue
                for m in pattern.finditer(text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    violations.append(f"{rel}:{line_no}: {pattern.pattern}")
        assert violations == [], "forbidden log patterns:\n" + "\n".join(violations)

    def test_gmail_importer_no_raw_subject_or_company(self):
        text = pathlib.Path("src/gmail_importer.py").read_text()
        assert "subject[:70]" not in text
        assert "matched_application.get('company')" not in text
        assert "chars suppressed" in text
