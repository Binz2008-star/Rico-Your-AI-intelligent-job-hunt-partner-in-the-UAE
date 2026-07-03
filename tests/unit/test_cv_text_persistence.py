# -*- coding: utf-8 -*-
"""Live-QA 2026-07-03 regression — parsed CV text must survive the confirm flow.

Production symptom: after uploading Roben_Edwan_Banking_CV.pdf and confirming
the profile preview, Rico showed the extracted skills yet reported "I don't
have the parsed text from that specific file". Root cause: the confirm handler
persisted only the structured summary — rico_profiles.cv_text (which the
schema, rico_db.upsert_profile, and apply_queue tailoring all already support)
was never written.

These tests pin the plumbing:
  1. profile_repo.upsert_profile forwards cv_text to the DB layer, including
     when there are no profile-field updates at all.
  2. A cv_text of None never reaches COALESCE as an overwrite (DB semantics),
     and the repo does not invent a DB write for a no-op call.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.repositories import profile_repo


def _run_upsert(updates, cv_text, *, bundle_id="db-uuid-1"):
    """Drive profile_repo.upsert_profile with a fully mocked DB + memory."""
    db = MagicMock()
    db.get_user_bundle.return_value = {"id": bundle_id, "email": "user@x.com"}
    conn = MagicMock()

    @contextmanager
    def _fake_txn():
        yield conn

    mem = MagicMock()
    mem.upsert_profile_from_dict.return_value = MagicMock()

    with patch.object(profile_repo, "_db", return_value=db), \
         patch.object(profile_repo, "_db_transaction", _fake_txn), \
         patch.object(profile_repo, "_memory", return_value=mem):
        profile_repo.upsert_profile("user@x.com", updates, cv_text=cv_text)
    return db


def test_cv_text_forwarded_with_profile_updates():
    db = _run_upsert({"skills": ["ISO 14001"], "years_experience": 8}, "RAW CV TEXT BODY")
    assert db.upsert_profile.called, "DB profile upsert must run"
    _, kwargs = db.upsert_profile.call_args
    assert kwargs.get("cv_text") == "RAW CV TEXT BODY"


def test_cv_text_alone_still_writes_to_db():
    """Even with zero profile-field updates, cv_text must reach the DB."""
    db = _run_upsert({}, "ONLY THE CV TEXT")
    assert db.upsert_profile.called
    args, kwargs = db.upsert_profile.call_args
    assert kwargs.get("cv_text") == "ONLY THE CV TEXT"
    # Empty profile merge is a JSONB no-op ('profile || {}') — safe by design.
    assert args[1] == {}


def test_no_cv_text_and_no_updates_skips_db_profile_write():
    """A no-op call must not generate a pointless DB write."""
    db = _run_upsert({}, None)
    assert not db.upsert_profile.called


def test_none_cv_text_with_updates_passes_none_for_coalesce():
    """cv_text=None rides through — COALESCE keeps the existing DB value."""
    db = _run_upsert({"skills": ["excel"]}, None)
    assert db.upsert_profile.called
    _, kwargs = db.upsert_profile.call_args
    assert kwargs.get("cv_text") is None
