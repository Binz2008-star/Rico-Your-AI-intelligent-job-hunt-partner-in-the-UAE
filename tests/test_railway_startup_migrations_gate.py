"""RICO_RUN_STARTUP_MIGRATIONS gate — Railway startup safety.

Standing up an additional deployment target (e.g. a second platform) against
an existing, already-migrated Neon database must not re-run write-capable
startup DDL (RicoDB().init(), init_db(), and the four _apply_* migrations).

RICO_RUN_STARTUP_MIGRATIONS=false connects read-only-safe: a strict
read-only schema check runs instead (_require_critical_tables_readonly),
which aborts startup on ANY failure — missing DATABASE_URL, a failed
connection, a failed query, or missing critical tables. Nothing writes.

Default (unset) or an explicit true-like value ("true"/"1"/"yes"/"on")
preserves the current Render/main behavior exactly — every write-capable
path still runs, using the original _check_critical_tables (log-only, never
aborts).

An unrecognized explicit value must never be guessed at — it raises before
any DB call is made, aborting startup rather than booting into an ambiguous
configuration.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

import src.api.app as app_module  # noqa: E402

# start_model_precheck_background spawns a real daemon thread that probes the
# live AI provider — patched out in every lifespan test below so no test ever
# makes a live DeepSeek/OpenAI/HF call (project testing rule).
_PRECHECK_TARGET = "src.rico_openai_runtime.start_model_precheck_background"


# ── _startup_migrations_enabled() parsing ─────────────────────────────────────

def test_default_unset_enables_migrations():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RICO_RUN_STARTUP_MIGRATIONS", None)
        assert app_module._startup_migrations_enabled() is True


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "YES", "on", "On", "  true  "])
def test_recognized_true_values(value):
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        assert app_module._startup_migrations_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "NO", "off", "Off", "  false  "])
def test_recognized_false_values(value):
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        assert app_module._startup_migrations_enabled() is False


@pytest.mark.parametrize("value", ["2", "maybe", "enable", "disable", "tru", "fals", "yesplease", "TRUEISH"])
def test_unrecognized_value_raises_without_any_db_call(value):
    """An invalid explicit value must abort before any DB call — not guess."""
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        with patch("src.db.get_db_connection") as m_conn:
            with pytest.raises(ValueError, match="RICO_RUN_STARTUP_MIGRATIONS"):
                app_module._startup_migrations_enabled()
            m_conn.assert_not_called()


# ── _require_critical_tables_readonly() — every failure mode aborts ──────────

def test_readonly_check_aborts_when_database_url_absent():
    with patch.dict(os.environ, {"DATABASE_URL": ""}):
        with patch("src.db.get_db_connection") as m_conn:
            with pytest.raises(RuntimeError, match="DATABASE_URL"):
                app_module._require_critical_tables_readonly()
            m_conn.assert_not_called()


def test_readonly_check_aborts_when_connection_fails():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
        with patch("src.db.get_db_connection", return_value=None):
            with pytest.raises(RuntimeError, match="connection failed"):
                app_module._require_critical_tables_readonly()


def test_readonly_check_aborts_when_query_fails():
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value.execute.side_effect = Exception("boom")
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
        with patch("src.db.get_db_connection", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="query failed"):
                app_module._require_critical_tables_readonly()
    mock_conn.close.assert_called_once()


def test_readonly_check_aborts_when_tables_missing():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    # Only some critical tables present.
    mock_cursor.fetchall.return_value = [("users",), ("rico_users",)]
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
        with patch("src.db.get_db_connection", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="missing critical tables"):
                app_module._require_critical_tables_readonly()
    mock_conn.close.assert_called_once()


def test_readonly_check_succeeds_when_all_tables_present():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [(t,) for t in app_module._CRITICAL_TABLES]
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
        with patch("src.db.get_db_connection", return_value=mock_conn):
            app_module._require_critical_tables_readonly()  # must not raise
    mock_conn.close.assert_called_once()


# ── lifespan() behavior ────────────────────────────────────────────────────────

class _DummyApp:
    """Minimal stand-in — the lifespan body never touches the app argument."""


def _write_path_mocks():
    """Context managers for every write-capable startup call, the original
    (log-only) critical-tables check, and the new strict read-only check."""
    return dict(
        rico_init=patch("src.rico_db.RicoDB.init"),
        init_db=patch("src.db.init_db"),
        idx=patch.object(app_module, "_apply_performance_indexes"),
        audit=patch.object(app_module, "_apply_audit_helper_tables"),
        doc=patch.object(app_module, "_apply_uploaded_document_context"),
        cv=patch.object(app_module, "_apply_cv_upload_artifacts"),
        check=patch.object(app_module, "_check_critical_tables"),
        readonly=patch.object(app_module, "_require_critical_tables_readonly"),
        precheck=patch(_PRECHECK_TARGET),
    )


@pytest.mark.asyncio
async def test_false_skips_all_write_capable_startup_paths_and_runs_readonly_check():
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": "false"}):
        ctxs = _write_path_mocks()
        with ctxs["rico_init"] as m_rico_init, ctxs["init_db"] as m_init_db, \
                ctxs["idx"] as m_idx, ctxs["audit"] as m_audit, ctxs["doc"] as m_doc, \
                ctxs["cv"] as m_cv, ctxs["check"] as m_check, \
                ctxs["readonly"] as m_readonly, ctxs["precheck"] as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_not_called()
            m_init_db.assert_not_called()
            m_idx.assert_not_called()
            m_audit.assert_not_called()
            m_doc.assert_not_called()
            m_cv.assert_not_called()
            m_check.assert_not_called()  # original log-only check: not used on the false path
            m_readonly.assert_called_once()  # strict read-only check: used instead
            m_precheck.assert_called_once()  # unrelated to this gate — unchanged either way


@pytest.mark.asyncio
async def test_false_with_failing_readonly_check_aborts_startup_before_any_write():
    """If the read-only schema check fails, startup itself must fail — the
    process must never proceed to yield (i.e. start serving traffic)."""
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": "false"}):
        ctxs = _write_path_mocks()
        with ctxs["rico_init"] as m_rico_init, ctxs["init_db"] as m_init_db, \
                ctxs["idx"] as m_idx, ctxs["audit"] as m_audit, ctxs["doc"] as m_doc, \
                ctxs["cv"] as m_cv, ctxs["precheck"] as m_precheck, \
                patch.object(
                    app_module, "_require_critical_tables_readonly",
                    side_effect=RuntimeError("missing critical tables"),
                ):
            with pytest.raises(RuntimeError, match="missing critical tables"):
                async with app_module.lifespan(_DummyApp()):
                    pytest.fail("lifespan must not yield when the readonly check fails")

            m_rico_init.assert_not_called()
            m_init_db.assert_not_called()
            m_idx.assert_not_called()
            m_audit.assert_not_called()
            m_doc.assert_not_called()
            m_cv.assert_not_called()
            m_precheck.assert_not_called()


@pytest.mark.asyncio
async def test_true_preserves_current_behavior():
    """RICO_RUN_STARTUP_MIGRATIONS unset (default): every existing startup
    path still runs, unchanged from pre-flag behavior."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RICO_RUN_STARTUP_MIGRATIONS", None)
        ctxs = _write_path_mocks()
        with ctxs["rico_init"] as m_rico_init, ctxs["init_db"] as m_init_db, \
                ctxs["idx"] as m_idx, ctxs["audit"] as m_audit, ctxs["doc"] as m_doc, \
                ctxs["cv"] as m_cv, ctxs["check"] as m_check, \
                ctxs["readonly"] as m_readonly, ctxs["precheck"] as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_called_once()
            m_init_db.assert_called_once()
            m_idx.assert_called_once()
            m_audit.assert_called_once()
            m_doc.assert_called_once()
            m_cv.assert_called_once()
            m_check.assert_called_once()
            m_readonly.assert_not_called()
            m_precheck.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["true", "1", "yes", "on"])
async def test_explicit_true_like_values_match_default(value):
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        ctxs = _write_path_mocks()
        with ctxs["rico_init"] as m_rico_init, ctxs["init_db"] as m_init_db, \
                ctxs["idx"] as m_idx, ctxs["audit"] as m_audit, ctxs["doc"] as m_doc, \
                ctxs["cv"] as m_cv, ctxs["check"] as m_check, \
                ctxs["readonly"] as m_readonly, ctxs["precheck"] as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_called_once()
            m_init_db.assert_called_once()
            m_idx.assert_called_once()
            m_audit.assert_called_once()
            m_doc.assert_called_once()
            m_cv.assert_called_once()
            m_check.assert_called_once()
            m_readonly.assert_not_called()
            m_precheck.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_value_aborts_before_any_startup_path_including_precheck():
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": "maybe"}):
        ctxs = _write_path_mocks()
        with ctxs["rico_init"] as m_rico_init, ctxs["init_db"] as m_init_db, \
                ctxs["idx"] as m_idx, ctxs["audit"] as m_audit, ctxs["doc"] as m_doc, \
                ctxs["cv"] as m_cv, ctxs["check"] as m_check, \
                ctxs["readonly"] as m_readonly, ctxs["precheck"] as m_precheck:
            with pytest.raises(ValueError, match="RICO_RUN_STARTUP_MIGRATIONS"):
                async with app_module.lifespan(_DummyApp()):
                    pytest.fail("lifespan must not yield on an invalid gate value")

            m_rico_init.assert_not_called()
            m_init_db.assert_not_called()
            m_idx.assert_not_called()
            m_audit.assert_not_called()
            m_doc.assert_not_called()
            m_cv.assert_not_called()
            m_check.assert_not_called()
            m_readonly.assert_not_called()
            m_precheck.assert_not_called()
