"""tests/test_1076_log_redaction.py

#1076 — production logs must not contain career-profile or contact values.

Three layers of proof:
1. Unit behavior of the shared helper (src/services/log_redaction.py).
2. caplog sentinel tests: synthetic sentinel values for email, phone, salary,
   city, Telegram ids, target roles, CV text, and a public session id must
   never appear in log output on successful OR failing profile read/write and
   saved-search paths, while safe metadata (fingerprint, field names) stays
   observable.
3. Static regression guard: an AST scan of the remediated modules fails if a
   logging call regresses to passing raw profile dictionaries/values again.

All DB calls are patched — no real database required.
"""
from __future__ import annotations

import ast
import logging
import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.log_redaction import (
    safe_error,
    safe_field_names,
    safe_len,
    user_fingerprint,
)

# ── Synthetic sentinels (never real user data) ────────────────────────────────
SENTINEL_EMAIL = "pii.sentinel.email@example.com"
SENTINEL_PHONE = "+971509990001"
SENTINEL_NAME = "Sentinel Fullname"
SENTINEL_CITY = "SentinelCityXYZ"
SENTINEL_SALARY = 987654
SENTINEL_ROLE = "Sentinel Unicorn Wrangler"
SENTINEL_TG_CHAT = "tg-chat-sentinel-42"
SENTINEL_TG_USER = "sentinel_tg_user"
SENTINEL_CV_TEXT = "SENTINEL-CV-TEXT-BODY do not log"
SENTINEL_PUBLIC_SID = "public-sentinel-session-id-123"
SENTINEL_QUERY = "sentinel secret search query"

ALL_SENTINELS = [
    SENTINEL_EMAIL, SENTINEL_PHONE, SENTINEL_NAME, SENTINEL_CITY,
    str(SENTINEL_SALARY), SENTINEL_ROLE, SENTINEL_TG_CHAT, SENTINEL_TG_USER,
    SENTINEL_CV_TEXT, SENTINEL_PUBLIC_SID, SENTINEL_QUERY,
]


def _assert_no_sentinels(caplog):
    text = caplog.text
    for sentinel in ALL_SENTINELS:
        assert sentinel not in text, f"sentinel leaked into logs: {sentinel!r}"


@contextmanager
def _fake_transaction():
    yield MagicMock()


def _bundle(profile=None):
    from src.role_normalization import NORMALIZATION_VERSION
    return {
        "id": "db-uuid-1",
        "external_user_id": SENTINEL_EMAIL,
        "name": SENTINEL_NAME,
        "email": SENTINEL_EMAIL,
        "phone": SENTINEL_PHONE,
        "telegram_username": SENTINEL_TG_USER,
        "profile": profile or {
            "target_roles": [SENTINEL_ROLE],
            "preferred_cities": [SENTINEL_CITY],
            "salary_expectation_aed": SENTINEL_SALARY,
            "normalization_version": NORMALIZATION_VERSION,
        },
        "settings": {},
    }


def _mock_db(bundle=None, available=True):
    db = MagicMock()
    db.available = available
    db.get_user_bundle.return_value = bundle
    db.upsert_user.return_value = {"id": "db-uuid-1"}
    return db


# ── 1. Helper unit behavior ───────────────────────────────────────────────────

class TestHelpers:
    def test_fingerprint_is_stable_and_non_reversible(self):
        fp = user_fingerprint(SENTINEL_EMAIL)
        assert fp == user_fingerprint(SENTINEL_EMAIL)
        assert fp.startswith("u:")
        assert SENTINEL_EMAIL not in fp
        assert "@" not in fp

    def test_fingerprint_distinguishes_users(self):
        assert user_fingerprint("a@x.com") != user_fingerprint("b@x.com")

    def test_fingerprint_handles_none_and_empty(self):
        assert user_fingerprint(None) == "u:none"
        assert user_fingerprint("") == "u:empty"

    def test_safe_field_names_returns_names_only(self):
        names = safe_field_names({"email": SENTINEL_EMAIL, "phone": SENTINEL_PHONE})
        assert names == ["email", "phone"]
        assert SENTINEL_EMAIL not in str(names)

    def test_safe_field_names_handles_none(self):
        assert safe_field_names(None) == []

    def test_safe_len(self):
        assert safe_len([1, 2, 3]) == 3
        assert safe_len(None) == 0
        assert safe_len(42) == 0

    def test_safe_error_is_type_only(self):
        err = ValueError(f"driver echoed {SENTINEL_EMAIL}")
        assert safe_error(err) == "ValueError"
        assert SENTINEL_EMAIL not in safe_error(err)


# ── 2. caplog sentinel proofs ─────────────────────────────────────────────────

class TestGetProfileLogs:
    def test_success_read_logs_no_profile_values(self, caplog):
        from src.repositories import profile_repo
        with patch.object(profile_repo, "_db", return_value=_mock_db(bundle=_bundle())), \
             patch.object(profile_repo, "_memory", return_value=MagicMock()):
            with caplog.at_level(logging.DEBUG):
                profile = profile_repo.get_profile(SENTINEL_EMAIL)
        assert profile is not None
        _assert_no_sentinels(caplog)
        # Safe metadata remains observable
        assert user_fingerprint(SENTINEL_EMAIL) in caplog.text
        assert "profile_fields=" in caplog.text

    def test_failed_read_logs_no_identifiers_even_from_exception(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db()
        db.get_user_bundle.side_effect = RuntimeError(
            f"driver echoed value: {SENTINEL_EMAIL} / {SENTINEL_PUBLIC_SID}"
        )
        mem = MagicMock()
        mem.load_profile.return_value = None
        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_memory", return_value=mem):
            with caplog.at_level(logging.DEBUG):
                profile_repo.get_profile(SENTINEL_PUBLIC_SID)
        _assert_no_sentinels(caplog)
        assert "get_profile DB failed" in caplog.text
        assert "RuntimeError" in caplog.text


class TestUpsertProfileLogs:
    UPDATES = {
        "name": SENTINEL_NAME,
        "phone": SENTINEL_PHONE,
        "target_roles": [SENTINEL_ROLE],
        "preferred_cities": [SENTINEL_CITY],
        "salary_expectation_aed": SENTINEL_SALARY,
        "telegram_chat_id": SENTINEL_TG_CHAT,
        "telegram_username": SENTINEL_TG_USER,
    }

    def test_success_write_web_user_logs_no_values(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db(bundle=_bundle())
        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_memory", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_transaction):
            with caplog.at_level(logging.DEBUG):
                profile_repo.upsert_profile(
                    SENTINEL_EMAIL, dict(self.UPDATES), cv_text=SENTINEL_CV_TEXT
                )
        _assert_no_sentinels(caplog)
        assert "fields=" in caplog.text

    def test_success_write_external_user_logs_payload_fields_only(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db(bundle=None)
        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_memory", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_transaction):
            with caplog.at_level(logging.DEBUG):
                profile_repo.upsert_profile(SENTINEL_PUBLIC_SID, dict(self.UPDATES))
        _assert_no_sentinels(caplog)
        assert "user_payload_fields=" in caplog.text

    def test_failed_write_logs_no_values(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db(bundle=None)
        db.upsert_user.side_effect = RuntimeError(f"insert failed for {SENTINEL_PHONE}")
        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_memory", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_transaction):
            with caplog.at_level(logging.DEBUG):
                profile_repo.upsert_profile(SENTINEL_PUBLIC_SID, dict(self.UPDATES))
        _assert_no_sentinels(caplog)
        assert "upsert_profile DB failed" in caplog.text

    def test_require_db_error_message_carries_fingerprint_not_raw_id(self):
        from src.repositories import profile_repo
        with patch.object(profile_repo, "_db", return_value=None), \
             patch.object(profile_repo, "_memory", return_value=MagicMock()):
            with pytest.raises(RuntimeError) as excinfo:
                profile_repo.upsert_profile(
                    SENTINEL_PUBLIC_SID, {"name": SENTINEL_NAME}, require_db=True
                )
        assert SENTINEL_PUBLIC_SID not in str(excinfo.value)
        assert user_fingerprint(SENTINEL_PUBLIC_SID) in str(excinfo.value)


class TestSavedSearchLogs:
    def test_saved_search_logs_length_not_query(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db()
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = None

        @contextmanager
        def _tx():
            yield conn

        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_db_transaction", _tx):
            with caplog.at_level(logging.DEBUG):
                profile_repo.save_search(SENTINEL_PUBLIC_SID, SENTINEL_QUERY)
        _assert_no_sentinels(caplog)
        assert "query_chars=" in caplog.text

    def test_saved_search_failure_logs_no_query_or_sid(self, caplog):
        from src.repositories import profile_repo
        db = _mock_db()
        db.upsert_user.side_effect = RuntimeError(f"boom {SENTINEL_QUERY}")
        with patch.object(profile_repo, "_db", return_value=db), \
             patch.object(profile_repo, "_db_transaction", _fake_transaction):
            with caplog.at_level(logging.DEBUG):
                profile_repo.save_search(SENTINEL_PUBLIC_SID, SENTINEL_QUERY)
        _assert_no_sentinels(caplog)
        assert "save_search DB failed" in caplog.text


# ── 3. Static regression guard ────────────────────────────────────────────────

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

# Bare names that must never be passed raw to a logging call in the guarded
# modules. Wrapping them in the redaction helpers (safe_field_names,
# user_fingerprint, safe_len, safe_error) or len()/list()/sorted()/type() is
# what the remediation requires, and those wrapped forms do not appear as bare
# Name arguments in the AST.
_FORBIDDEN_LOG_ARG_NAMES = {
    "updates", "filtered_updates", "user_payload", "profile_data", "bundle",
    "cv_text", "user_id", "email", "email_norm", "phone", "digits",
    "username_norm", "query", "user_row", "prefs", "valid_prefs",
}

_GUARDED_MODULES = [
    "src/repositories/profile_repo.py",
    "src/api/routers/rico_chat.py",
]

_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def _iter_logging_calls(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOG_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ):
            yield node


def _violations_in(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    violations = []
    for call in _iter_logging_calls(tree):
        for arg in call.args[1:]:  # arg 0 is the format string
            if isinstance(arg, ast.Name) and arg.id in _FORBIDDEN_LOG_ARG_NAMES:
                violations.append(f"{path}:{call.lineno} bare `{arg.id}` in logger call")
            # .get("profile") / .get("name") style raw-value extraction
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and arg.func.attr == "get"
                and arg.args
                and isinstance(arg.args[0], ast.Constant)
                and arg.args[0].value in {"profile", "name", "email", "phone", "settings"}
            ):
                violations.append(
                    f"{path}:{call.lineno} raw `.get({arg.args[0].value!r})` in logger call"
                )
        # f-string interpolating a forbidden name
        for arg in list(call.args) + [kw.value for kw in call.keywords]:
            if isinstance(arg, ast.JoinedStr):
                for part in ast.walk(arg):
                    if isinstance(part, ast.Name) and part.id in _FORBIDDEN_LOG_ARG_NAMES:
                        violations.append(
                            f"{path}:{call.lineno} f-string logs `{part.id}`"
                        )
    return violations


class TestStaticLogGuard:
    def test_guarded_modules_have_no_raw_value_logging(self):
        all_violations = []
        for rel in _GUARDED_MODULES:
            all_violations.extend(_violations_in(os.path.join(_REPO_ROOT, rel)))
        assert not all_violations, "\n".join(all_violations)

    def test_profile_repo_never_uses_logger_exception(self):
        # logger.exception appends the exception message (which can re-emit
        # driver-bound values) to the log record — profile paths must log
        # exception TYPES only via safe_error().
        path = os.path.join(_REPO_ROOT, "src/repositories/profile_repo.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        offenders = [
            f"{path}:{call.lineno}"
            for call in _iter_logging_calls(tree)
            if call.func.attr == "exception"
        ]
        assert not offenders, "\n".join(offenders)
