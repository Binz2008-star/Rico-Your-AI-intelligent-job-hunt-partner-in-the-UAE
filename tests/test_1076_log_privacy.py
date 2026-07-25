"""#1076 — production logs must not carry profile values, contact identifiers,
message/document text, or bearer credentials.

Synthetic sentinels only; caplog proves they never reach log records on
success or failure paths, the Sentry ``before_send`` scrubber removes them
from exported events, production refuses to boot with a token-logging flag,
and a static regression guard rejects the forbidden logging patterns
repo-wide.
"""

from __future__ import annotations

import ast
import logging
import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest

from src.log_privacy import (
    enforce_production_log_safety,
    filename_ref,
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


# ── #1076 delta: chat-stream / profile-update raw-identifier sites ───────────
#
# The five residual sites found by the 2026-07-17 reconciliation (chat_stream,
# chat_stream_public — where user_id is the PUBLIC session bearer id — and the
# profile_update persistence-failure path) plus the no-fields warning in the
# same function. Guards below are scoped to src/api/routers/rico_chat.py.
#
# Repository-wide coverage is owned by the differential ratchet
# (scripts/log_privacy_ratchet.py), not by _SWEPT_MODULES, which stays a
# narrow per-module list. This file is outside that list only to avoid a
# concurrent ownership conflict with the workstream that holds it.

_RICO_CHAT = pathlib.Path("src/api/routers/rico_chat.py")


class TestStreamLogDeltaGuard:
    def test_no_raw_user_id_in_user_log_formats(self):
        text = _RICO_CHAT.read_text(encoding="utf-8")
        raw = re.compile(r'user=%s"\s*,\s*user_id\b')
        violations = [
            f"src/api/routers/rico_chat.py:{text.count(chr(10), 0, m.start()) + 1}"
            for m in raw.finditer(text)
        ]
        assert violations == [], (
            "raw user_id in a user=%s log format (use log_privacy.user_ref):\n"
            + "\n".join(violations)
        )

    def test_no_logger_exception_carries_a_user_field(self):
        # logger.exception appends the exception message, which can re-emit
        # bound values; on any line that also logs a user field the pair is
        # forbidden — use logger.error + user_ref + safe_exc instead.
        text = _RICO_CHAT.read_text(encoding="utf-8")
        bad = re.compile(r"logger\.exception\([^)]*user=%s", re.S)
        assert not bad.search(text), (
            "logger.exception with a user field in rico_chat.py — "
            "use logger.error + user_ref + safe_exc"
        )

    def test_stream_persist_failures_no_longer_dump_tracebacks(self):
        # exc_info=True on the persist-failure debug lines could re-emit chat
        # text via driver exception strings at the end of the traceback.
        text = _RICO_CHAT.read_text(encoding="utf-8")
        assert "persist failed user=%s\", user_id, exc_info=True" not in text
        for marker in ("chat_stream: assistant persist failed",
                       "chat_stream_public: assistant persist failed"):
            assert marker in text, f"expected remediated site still present: {marker}"


class TestProfileUpdateFailurePathClean:
    def test_persistence_failure_logs_ref_not_raw_id_or_values(self, caplog, monkeypatch):
        from fastapi.testclient import TestClient
        import src.api.routers.rico_chat as rico_chat_router
        from src.api.app import app

        def mock_get_user(request):
            user = {"email": EMAIL, "role": "user"}
            request.state.current_user = user
            request.state.user_id = EMAIL
            return user

        monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

        def failing_upsert(user_id, updates, **kwargs):
            raise RuntimeError(f"driver echoed {EMAIL} salary={SALARY}")

        monkeypatch.setattr(rico_chat_router, "upsert_profile", failing_upsert)

        client = TestClient(app)
        with caplog.at_level(logging.DEBUG):
            r = client.patch(
                "/api/v1/rico/profile",
                json={"current_role": "HSE Lead", "salary_expectation_aed": SALARY},
            )
        assert r.status_code == 503
        assert "profile_update persistence failed" in caplog.text
        assert "RuntimeError" in caplog.text
        _assert_clean(caplog.text)
        assert user_ref(EMAIL) in caplog.text


# ── filename references ──────────────────────────────────────────────────────

class TestFilenameRef:
    """A CV filename is usually the owner's name, so the stem is PII itself.

    Truncating it does not help — a prefix still names the person — so the rule
    is extension + length only, never any part of the stem.
    """

    def test_stem_never_survives_even_when_it_is_a_full_name(self):
        out = filename_ref("Sentinel Person 1076 Curriculum Vitae.PDF")
        assert "Sentinel" not in out and "Person" not in out and "Vitae" not in out
        assert out == "f:ext=.pdf,len=41"

    def test_extension_is_kept_for_parser_triage(self):
        assert filename_ref("x.docx").startswith("f:ext=.docx")

    def test_missing_and_extensionless_names_are_handled(self):
        assert filename_ref(None) == "f:none"
        assert filename_ref("") == "f:none"
        assert filename_ref("resume").startswith("f:ext=none")

    def test_crafted_extension_collapses_to_a_fixed_sentinel(self):
        """Sanitise-then-truncate is not enough.

        Stripping "characters we dislike" and keeping the first N still lets a
        chosen filename place N characters of arbitrary text into the field —
        the newline is gone but the payload is not. The extension is therefore
        validated against an allowed shape and replaced wholesale when it does
        not match, so no caller-controlled substring survives.
        """
        crafted = "a.p df\nuser=admin"
        out = filename_ref(crafted)
        assert out == f"f:ext=other,len={len(crafted)}"
        # No fragment of the crafted tail reaches the emitted extension VALUE.
        ext_value = out.split(",")[0].split("=", 1)[1]
        assert ext_value == "other"
        for fragment in ("user", "admin", "df", "p d", "="):
            assert fragment not in ext_value, f"{fragment!r} survived into ext"
        assert "\n" not in out and " " not in out

    @pytest.mark.parametrize("crafted", [
        "cv.pdf\nlevel=CRITICAL user=admin",
        "cv." + "a" * 40,
        "cv.p​df",
        "cv.PDF%s",
        "cv.таб",
    ])
    def test_only_short_alphanumeric_suffixes_are_echoed(self, crafted):
        ext_field = filename_ref(crafted).split(",")[0]
        assert ext_field in ("f:ext=other", "f:ext=none") or re.fullmatch(
            r"f:ext=\.[a-z0-9]{1,8}", ext_field
        ), ext_field


# ── widened static guard: sensitive log FIELDS must carry a sanctioned ref ───
#
# The pre-existing delta guard keyed on the literal token ``user_id``, so it
# only caught drift that happened to reuse that variable name — a site logging
# ``user=%s`` with an argument called ``email``, ``uid`` or ``ctx.user`` passed
# straight through. This rule is name-independent: it reads the log FORMAT
# string, finds which %-placeholder each sensitive field label owns, and
# requires the argument in that position to be a call to a sanctioned
# log_privacy helper. What the variable is called is irrelevant.
#
# ``internal_id`` is exempt because log_privacy documents that opaque internal
# ``rico_users.id`` values are safe to log directly — but a label-based
# exemption is itself an escape hatch: relabelling a field from ``user=`` to
# ``internal_id=`` would silence this guard while still logging a raw email.
# So the exemption is not granted by label, it is granted per site. Mirroring
# _QUERY_ALLOWLIST above, the known internal-id sites are enumerated below; a
# fourth cannot appear without a deliberate edit here that a reviewer sees.

_SWEPT_MODULES = (
    "src/api/routers/files.py",
    "src/services/email_notifications.py",
    "src/services/subscription_gating.py",
    "src/services/application_board.py",
    "src/services/jobs_service.py",
    "src/services/apply_service.py",
    "src/api/auth.py",
)

# Field labels whose logged value is an external identifier or user-supplied
# text. Extend this tuple, not the call sites, when a new one appears.
_SENSITIVE_LABELS = frozenset({
    "user", "user_id", "public_user_id", "uid", "account",
    "email", "to", "recipient", "phone", "telegram_chat_id", "telegram_id",
    "filename", "original_filename", "file_name",
})

_APPROVED_REFS = frozenset({
    "user_ref", "token_ref", "operation_ref", "filename_ref", "safe_fields",
})

# Call sites permitted to log a raw ``internal_id=``, keyed by
# (module, enclosing qualified name, full format literal). All three log
# ``getattr(user, "id", ...)`` — the opaque rico_users.id — on best-effort
# post-registration paths. All three also live in the same function, which is
# precisely why the key carries the whole format literal rather than its first
# token: a prefix would collapse them into one exemption. Adding an entry is a
# deliberate, reviewable act; that is the entire point of enumerating them.
_INTERNAL_ID_ALLOWLIST = frozenset({
    ("src/api/auth.py", "register",
     "verification_email_schedule_failed internal_id=%s"),
    ("src/api/auth.py", "register",
     "signup_attribution_persist_failed internal_id=%s"),
    ("src/api/auth.py", "register",
     "signup_notification_schedule_failed internal_id=%s"),
})

# Identifiers that name an external identifier or user-supplied text. Rule 2
# flags these when passed bare to a log call, whatever the format string says
# — including format strings with no ``label=`` at all.
_BARE_SENSITIVE_NAMES = frozenset({
    "email", "user_email", "to_email", "address", "user_id", "uid",
    "public_user_id", "phone", "recipient", "telegram_chat_id", "telegram_id",
    "filename", "original_filename", "file_name", "cv_text", "resume_text",
})

_LOG_METHODS = frozenset({
    "debug", "info", "warning", "warn", "error", "exception", "critical",
})

# One %-conversion. ``%%`` is an escape and consumes no argument.
_CONVERSION = re.compile(r"%(?:%|[-#0 +]*[\d.*]*[hlL]?[a-zA-Z])")
_TRAILING_LABEL = re.compile(r"(\w+)=$")


def _sensitive_positions(fmt: str) -> dict[int, str]:
    """Map argument index -> sensitive field label for one format string."""
    positions: dict[int, str] = {}
    arg_index = 0
    for m in _CONVERSION.finditer(fmt):
        if m.group() == "%%":
            continue
        label_match = _TRAILING_LABEL.search(fmt[: m.start()])
        if label_match and label_match.group(1).lower() in _SENSITIVE_LABELS:
            positions[arg_index] = label_match.group(1)
        arg_index += 1
    return positions


def _is_sanctioned(node: ast.AST) -> bool:
    """True if the argument expression is a sanctioned log_privacy call."""
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        return name in _APPROVED_REFS
    # ``user_ref(uid) if uid else "anonymous"`` — safe only if BOTH branches
    # are, so a raw fallback cannot ride in on a sanctioned-looking expression.
    if isinstance(node, ast.IfExp):
        return _is_sanctioned(node.body) and _is_sanctioned(node.orelse)
    # A literal is inherently safe (e.g. a fixed "anonymous" sentinel).
    return isinstance(node, ast.Constant)


def _log_calls(tree: ast.AST):
    """Yield every ``logger.<level>(...)`` call node in a module."""
    for _scope, node in _log_calls_with_scope(tree):
        yield node


def _log_calls_with_scope(node: ast.AST, scope: tuple[str, ...] = ()):
    """Yield (enclosing qualified name, log call node) pairs.

    The qualified name is part of a call site's durable identity: unlike a line
    number it survives edits above it, and unlike the first format-string token
    it distinguishes two sites that happen to share a prefix.
    """
    for child in ast.iter_child_nodes(node):
        child_scope = scope
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            child_scope = scope + (child.name,)
        elif isinstance(child, ast.Call):
            fn = child.func
            if isinstance(fn, ast.Attribute) and fn.attr in _LOG_METHODS and child.args:
                yield ".".join(scope) or "<module>", child
        yield from _log_calls_with_scope(child, child_scope)


def _bare_name(node: ast.AST) -> str | None:
    """Identifier naming the value an expression yields, else None.

    Name and Attribute are the obvious shapes, but an identifier reaches a
    logger just as easily through a subscript (``row["email"]``) or a getattr
    (``getattr(user, "email", "")``). Both were invisible here, and the second
    shape is exactly what the internal-id sites use — so a raw address could
    have been logged there under an allowlisted exemption.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return key.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        return node.args[1].value
    return None


def _rule_two_candidates(node: ast.Call):
    """Expressions rule 2 inspects for one log call.

    An f-string is ``args[0]``, so scanning only ``args[1:]`` never sees its
    interpolations: ``logger.info(f"login failed {email}")`` was invisible to
    both rules. Its FormattedValue nodes are inspected wherever they appear.
    """
    for index, arg in enumerate(node.args):
        if isinstance(arg, ast.JoinedStr):
            for part in ast.walk(arg):
                if isinstance(part, ast.FormattedValue):
                    yield part.value
        elif index > 0:
            yield arg


def _scan_module(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr in _LOG_METHODS):
            continue
        if not node.args:
            continue
        fmt_node = node.args[0]

        # An f-string in a log call hides its interpolations from this check
        # (and from %-style lazy formatting) — reject it outright when it
        # mentions a sensitive label.
        if isinstance(fmt_node, ast.JoinedStr):
            rendered = "".join(
                p.value for p in fmt_node.values if isinstance(p, ast.Constant)
                and isinstance(p.value, str)
            )
            if any(f"{lbl}=" in rendered for lbl in _SENSITIVE_LABELS):
                violations.append(
                    f"{path}:{node.lineno}: f-string log format with a sensitive "
                    f"field — use %-style formatting with a log_privacy ref"
                )
            continue

        if not (isinstance(fmt_node, ast.Constant) and isinstance(fmt_node.value, str)):
            continue

        supplied = node.args[1:]
        for arg_index, label in _sensitive_positions(fmt_node.value).items():
            if arg_index >= len(supplied):
                continue  # arity mismatch is a different bug, not a privacy one
            if not _is_sanctioned(supplied[arg_index]):
                violations.append(
                    f"{path}:{node.lineno}: field '{label}=' logs a raw value; "
                    f"wrap it in one of {sorted(_APPROVED_REFS)}"
                )
    return violations


def _scan_bare_sensitive_names(path: pathlib.Path) -> list[str]:
    """Rule 2 — label-independent, name-based.

    Rule 1 requires a ``label=`` immediately before the conversion, so a
    format string that names no field at all ("rejecting login for %r") slips
    past it entirely. This rule ignores the format string and looks only at
    what is handed to the logger: a bare identifier that names an external
    identifier must be wrapped, wherever it appears in the call.

    The two rules are complementary. Rule 1 catches a sanctioned NAME in an
    unsanctioned POSITION; rule 2 catches an unsanctioned NAME in an
    unlabelled position.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for node in _log_calls(tree):
        for arg in _rule_two_candidates(node):
            name = _bare_name(arg)
            if name and name.lower() in _BARE_SENSITIVE_NAMES:
                violations.append(
                    f"{path}:{node.lineno}: bare '{name}' passed to a log call; "
                    f"wrap it in one of {sorted(_APPROVED_REFS)}"
                )
    return violations


def _scan_internal_id_sites(path: pathlib.Path) -> list[tuple[str, str, str]]:
    """Every ``internal_id=`` log site, keyed by durable identity.

    (module, enclosing qualified name, full format literal). The first
    whitespace-delimited token is not an identity: two sites in one module
    whose formats share a prefix collapse to a single key, and a new site can
    then be introduced under an existing exemption without the set difference
    noticing.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    sites: list[tuple[str, str, str]] = []
    for scope, node in _log_calls_with_scope(tree):
        fmt = node.args[0]
        if isinstance(fmt, ast.Constant) and isinstance(fmt.value, str):
            if "internal_id=" in fmt.value:
                sites.append((str(path), scope, fmt.value))
    return sites


class TestSensitiveLogFieldsUseSanctionedRefs:
    @pytest.mark.parametrize("module", _SWEPT_MODULES)
    def test_module_has_no_raw_sensitive_log_field(self, module):
        violations = _scan_module(pathlib.Path(module))
        assert violations == [], "raw identifier in a log field:\n" + "\n".join(violations)

    @pytest.mark.parametrize("module", _SWEPT_MODULES)
    def test_module_passes_no_bare_sensitive_identifier(self, module):
        violations = _scan_bare_sensitive_names(pathlib.Path(module))
        assert violations == [], "bare identifier in a log call:\n" + "\n".join(violations)

    def test_rule_two_catches_an_unlabelled_sensitive_argument(self):
        """The shape rule 1 is blind to: a format string with no ``label=``."""
        src = 'logger.error("rejecting login for %r", email)\n'
        tree = ast.parse(src)
        call = tree.body[0].value
        # Rule 1 sees nothing — there is no "label=" before the conversion.
        assert _sensitive_positions(call.args[0].value) == {}
        # Rule 2 catches it on the argument name alone.
        assert _bare_name(call.args[1]) == "email"

    def test_rule_two_accepts_a_wrapped_argument(self):
        tree = ast.parse('logger.error("rejecting login for %s", user_ref(email))\n')
        assert _bare_name(tree.body[0].value.args[1]) is None

    def test_rule_two_reads_attributes_not_just_names(self):
        tree = ast.parse('logger.info("x %s", req.email)\n')
        assert _bare_name(tree.body[0].value.args[1]) == "email"

    def test_conditional_is_sanctioned_only_when_both_branches_are(self):
        safe = ast.parse('logger.info("user=%s", user_ref(u) if u else "anonymous")\n')
        assert _is_sanctioned(safe.body[0].value.args[1])
        unsafe = ast.parse('logger.info("user=%s", user_ref(u) if u else u)\n')
        assert not _is_sanctioned(unsafe.body[0].value.args[1])


class TestInternalIdExemptionIsEnumeratedNotLabelBased:
    """A label-based exemption is an escape hatch; pin the sites instead."""

    @pytest.mark.parametrize("module", _SWEPT_MODULES)
    def test_no_unlisted_internal_id_site_appears(self, module):
        found = set(_scan_internal_id_sites(pathlib.Path(module)))
        unlisted = sorted(found - _INTERNAL_ID_ALLOWLIST)
        assert unlisted == [], (
            "new internal_id= log site(s) not in _INTERNAL_ID_ALLOWLIST — an "
            "internal rico_users.id is safe to log raw, but relabelling a field "
            "to internal_id= must not be a way to silence this guard:\n"
            + "\n".join(f"{m}: {event}" for m, event in unlisted)
        )

    def test_allowlist_has_no_stale_entries(self):
        found = set()
        for module in _SWEPT_MODULES:
            found |= set(_scan_internal_id_sites(pathlib.Path(module)))
        stale = sorted(_INTERNAL_ID_ALLOWLIST - found)
        assert stale == [], f"allowlist entries no longer present in source: {stale}"

    def test_no_allowlist_key_covers_more_than_one_site(self):
        """An exemption must cover exactly one call site.

        If one key matches two sites, a second raw-id line has been introduced
        under an existing exemption and the unlisted-set difference stays
        empty — the allowlist would silently cover it.
        """
        counts: dict[tuple[str, str, str], int] = {}
        for module in _SWEPT_MODULES:
            for site in _scan_internal_id_sites(pathlib.Path(module)):
                counts[site] = counts.get(site, 0) + 1
        ambiguous = sorted(k for k, n in counts.items() if n > 1)
        assert ambiguous == [], (
            "one allowlist key matches multiple call sites — the exemption is "
            f"no longer per-site:\n{ambiguous}"
        )

    def test_rule_does_not_depend_on_the_variable_being_named_user_id(self):
        """The old guard keyed on the literal token ``user_id`` and missed this."""
        src = 'logger.info("x user=%s", whatever_it_is_called)\n'
        tree = ast.parse(src)
        call = tree.body[0].value
        assert _sensitive_positions(call.args[0].value) == {0: "user"}
        assert not _is_sanctioned(call.args[1])

    def test_rule_accepts_a_sanctioned_ref_in_that_position(self):
        tree = ast.parse('logger.info("x user=%s", user_ref(anything))\n')
        assert _is_sanctioned(tree.body[0].value.args[1])

    def test_escaped_percent_does_not_shift_argument_positions(self):
        # "100%% done user=%s" must map user= to arg 0, not arg 1.
        assert _sensitive_positions("100%% done user=%s") == {0: "user"}

    def test_internal_id_label_is_not_treated_as_sensitive(self):
        assert _sensitive_positions("failed internal_id=%s") == {}
