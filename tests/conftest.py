"""Repo-wide pytest defaults.

Operation-ownership backend: the whole historical suite was written against
the in-process operation store, and unit tests must never touch a real
database (OPERATING_RULES). Force the memory backend for tests by default;
suites that exercise the shared Postgres store (e.g.
tests/integration/test_operation_ownership_postgres.py) opt back in
explicitly with monkeypatch.setenv("RICO_OPERATION_STORE", "postgres"),
which overrides this default for the duration of the test.
"""
from __future__ import annotations

import os

os.environ["RICO_OPERATION_STORE"] = "memory"
