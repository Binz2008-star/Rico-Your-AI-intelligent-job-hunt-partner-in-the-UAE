"""
tests/conftest.py
=================
Top-level pytest fixtures shared across all non-unit, non-evaluation tests.

Key fixtures: ``no_db``, ``profile_gate_open``
-----------------------------------------------
Stub out PostgreSQL so profile/repo tests run in CI without a live Postgres
instance. Without these fixtures the DB-backed tests produce:
  psycopg2.OperationalError: connection to server at "localhost" ... Connection refused

and the API persistence tests produce:
  AssertionError: assert None == 'Roben Edwan'

because upsert_profile silently ignores the DB write failure and the
profile GET returns profile_exists=False when has_career_profile_data sees
a name-only in-memory profile.
"""
from __future__ import annotations

import pytest
from contextlib import contextmanager
from unittest.mock import patch


# ---------------------------------------------------------------------------
# no_db: force profile_repo to use memory-only path
# ---------------------------------------------------------------------------

@pytest.fixture()
def no_db():
    """
    Stub PostgreSQL layer so profile repo tests run on the JSON memory store.

    Uses patch.object so the in-module _db() call is intercepted correctly
    (monkeypatch.setattr on a module function doesn't intercept in-module
    calls because the function is bound by the local 'db = _db()' lookup).

    Patches:
    - src.repositories.profile_repo._db        → always returns None
    - src.repositories.profile_repo._db_transaction → yields None (no-op)
    """
    import src.repositories.profile_repo as _repo

    @contextmanager
    def _null_transaction():
        yield None

    with (
        patch.object(_repo, "_db", lambda: None),
        patch.object(_repo, "_db_transaction", _null_transaction),
    ):
        yield


# ---------------------------------------------------------------------------
# profile_gate_open: bypass has_career_profile_data in rico_get_profile
# ---------------------------------------------------------------------------

@pytest.fixture()
def profile_gate_open():
    """
    Bypass the has_career_profile_data gate in rico_get_profile so the API
    GET endpoint returns the full stored profile regardless of which fields
    are set.

    This is needed for API persistence tests that set only a single field
    (e.g. name, notice_period) which alone doesn't satisfy the career-data
    gate — causing ProfileResponse(profile_exists=False) to be returned.
    """
    # has_career_profile_data is a lazy import inside rico_get_profile —
    # patch it at the source module so the local import picks up the mock.
    with patch(
        "src.services.profile_context_resolver.has_career_profile_data",
        return_value=True,
    ):
        yield
