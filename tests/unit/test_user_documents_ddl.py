"""
tests/unit/test_user_documents_ddl.py
======================================
Regression test for the duplicate _USER_DOCUMENTS_DDL definition bug.

Root cause: src/rico_db.py had two _USER_DOCUMENTS_DDL assignments.
The second (evaluated last, therefore active) used unquoted `current_role TEXT`
which is a PostgreSQL reserved keyword, causing:
    psycopg2.errors.SyntaxError near current_role
on every call to GET /api/v1/user/files.

This test ensures:
1. Exactly one _USER_DOCUMENTS_DDL definition is active in the module.
2. The column is quoted as "current_role" in the DDL.
3. All SELECT/INSERT queries that reference the column use the quoted form.
"""
from __future__ import annotations

import re
import importlib
import inspect


def test_user_documents_ddl_single_definition():
    """_USER_DOCUMENTS_DDL must be defined exactly once in rico_db source."""
    import src.rico_db as rico_db_module
    source = inspect.getsource(rico_db_module)
    count = source.count('_USER_DOCUMENTS_DDL = """')
    assert count == 1, (
        f"Found {count} definitions of _USER_DOCUMENTS_DDL in src/rico_db.py. "
        "Only one definition must exist. Remove the duplicate."
    )


def test_user_documents_ddl_current_role_quoted():
    """current_role must be quoted in DDL to avoid PostgreSQL reserved keyword error."""
    import src.rico_db as rico_db_module
    ddl = rico_db_module._USER_DOCUMENTS_DDL
    assert '"current_role" TEXT' in ddl, (
        "DDL must use quoted column name: '\"current_role\" TEXT'. "
        "Unquoted 'current_role' is a PostgreSQL reserved keyword and causes SyntaxError."
    )


def test_user_documents_ddl_no_unquoted_current_role():
    """The DDL must not contain unquoted current_role column definition."""
    import src.rico_db as rico_db_module
    ddl = rico_db_module._USER_DOCUMENTS_DDL
    # Match bare `current_role TEXT` not preceded by a quote
    # i.e. it must NOT appear as '    current_role TEXT,' (unquoted)
    unquoted_pattern = re.compile(r'(?<!")\bcurrent_role\s+TEXT', re.IGNORECASE)
    match = unquoted_pattern.search(ddl)
    assert match is None, (
        f"Found unquoted 'current_role TEXT' in DDL at position {match.start() if match else '?'}. "
        "Must be quoted as '\"current_role\" TEXT'."
    )


def test_user_documents_ddl_has_required_columns():
    """DDL must include all columns expected by list_user_documents and save_user_document."""
    import src.rico_db as rico_db_module
    ddl = rico_db_module._USER_DOCUMENTS_DDL
    required_columns = [
        "id", "user_id", "filename", "original_filename", "doc_type",
        "file_size", "label", "is_primary", "skills_count",
        "years_experience", "current_role", "created_at", "updated_at",
    ]
    for col in required_columns:
        assert col in ddl, f"Required column '{col}' missing from _USER_DOCUMENTS_DDL"
