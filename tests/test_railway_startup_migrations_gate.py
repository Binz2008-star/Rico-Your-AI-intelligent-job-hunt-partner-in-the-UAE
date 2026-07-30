"""RICO_RUN_STARTUP_MIGRATIONS gate — Railway startup safety.

Standing up an additional deployment target (e.g. a second platform) against
an existing, already-migrated Neon database must not re-run write-capable
startup DDL (RicoDB().init(), init_db(), and the four _apply_* migrations).
RICO_RUN_STARTUP_MIGRATIONS=false connects read-only-safe: schema
verification (_check_critical_tables, a SELECT-only check) still runs, but
nothing writes.

Default (unset, or any value other than the literal "false") preserves the
current Render/main behavior exactly — every write-capable path still runs.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

import src.api.app as app_module  # noqa: E402


# ── _startup_migrations_enabled() unit tests ──────────────────────────────────

def test_default_unset_enables_migrations():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RICO_RUN_STARTUP_MIGRATIONS", None)
        assert app_module._startup_migrations_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "  false  "])
def test_explicit_false_disables_migrations(value):
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        assert app_module._startup_migrations_enabled() is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "anything-else"])
def test_non_false_values_preserve_current_behavior(value):
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": value}):
        assert app_module._startup_migrations_enabled() is True


# ── lifespan() behavior ────────────────────────────────────────────────────────

class _DummyApp:
    """Minimal stand-in — the lifespan body never touches the app argument."""


# start_model_precheck_background spawns a real daemon thread that probes the
# live AI provider — patched out in every lifespan test below so no test ever
# makes a live DeepSeek/OpenAI/HF call (project testing rule).
_PRECHECK_TARGET = "src.rico_openai_runtime.start_model_precheck_background"


@pytest.mark.asyncio
async def test_false_skips_all_write_capable_startup_paths():
    """RICO_RUN_STARTUP_MIGRATIONS=false: no DDL, no writes — only the
    read-only critical-tables check runs."""
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": "false"}):
        with patch("src.rico_db.RicoDB.init") as m_rico_init, \
                patch("src.db.init_db") as m_init_db, \
                patch.object(app_module, "_apply_performance_indexes") as m_idx, \
                patch.object(app_module, "_apply_audit_helper_tables") as m_audit, \
                patch.object(app_module, "_apply_uploaded_document_context") as m_doc, \
                patch.object(app_module, "_apply_cv_upload_artifacts") as m_cv, \
                patch.object(app_module, "_check_critical_tables") as m_check, \
                patch(_PRECHECK_TARGET) as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_not_called()
            m_init_db.assert_not_called()
            m_idx.assert_not_called()
            m_audit.assert_not_called()
            m_doc.assert_not_called()
            m_cv.assert_not_called()
            m_check.assert_called_once()
            # Unrelated to the migration gate — unchanged in both branches.
            m_precheck.assert_called_once()


@pytest.mark.asyncio
async def test_true_preserves_current_behavior():
    """RICO_RUN_STARTUP_MIGRATIONS unset (default) or explicitly true: every
    existing startup path still runs, unchanged from pre-flag behavior."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RICO_RUN_STARTUP_MIGRATIONS", None)
        with patch("src.rico_db.RicoDB.init") as m_rico_init, \
                patch("src.db.init_db") as m_init_db, \
                patch.object(app_module, "_apply_performance_indexes") as m_idx, \
                patch.object(app_module, "_apply_audit_helper_tables") as m_audit, \
                patch.object(app_module, "_apply_uploaded_document_context") as m_doc, \
                patch.object(app_module, "_apply_cv_upload_artifacts") as m_cv, \
                patch.object(app_module, "_check_critical_tables") as m_check, \
                patch(_PRECHECK_TARGET) as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_called_once()
            m_init_db.assert_called_once()
            m_idx.assert_called_once()
            m_audit.assert_called_once()
            m_doc.assert_called_once()
            m_cv.assert_called_once()
            m_check.assert_called_once()
            m_precheck.assert_called_once()


@pytest.mark.asyncio
async def test_explicit_true_matches_default():
    with patch.dict(os.environ, {"RICO_RUN_STARTUP_MIGRATIONS": "true"}):
        with patch("src.rico_db.RicoDB.init") as m_rico_init, \
                patch("src.db.init_db") as m_init_db, \
                patch.object(app_module, "_apply_performance_indexes") as m_idx, \
                patch.object(app_module, "_apply_audit_helper_tables") as m_audit, \
                patch.object(app_module, "_apply_uploaded_document_context") as m_doc, \
                patch.object(app_module, "_apply_cv_upload_artifacts") as m_cv, \
                patch.object(app_module, "_check_critical_tables") as m_check, \
                patch(_PRECHECK_TARGET) as m_precheck:
            async with app_module.lifespan(_DummyApp()):
                pass

            m_rico_init.assert_called_once()
            m_init_db.assert_called_once()
            m_idx.assert_called_once()
            m_audit.assert_called_once()
            m_doc.assert_called_once()
            m_cv.assert_called_once()
            m_check.assert_called_once()
            m_precheck.assert_called_once()
