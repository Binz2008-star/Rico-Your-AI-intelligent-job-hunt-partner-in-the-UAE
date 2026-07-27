"""A guest row must never be a candidate for identity resolution.

#1412 closed this for the phone lookup. The same hole was left open on the two
other doorways into `find_identity_candidates`, and it was left open
deliberately: narrowing them was outside that PR's ordered scope, and folding
a change to a signal that is ALLOWED to merge into a PR whose subject was
preventing a merge would have mixed two contracts in one diff.

This is that separate change, for email and Telegram username.

Why it matters more here than on the phone path. Phone was never sufficient to
auto-attach after #1412, so a stray phone candidate produced `ask_user`. Email
and Telegram username ARE sufficient — `_EXISTING_AUTO_MERGE_SIGNAL_KINDS`
contains both — so a single guest-row candidate on either of them still
produces `action="merge"` today. The harm lands on the submitter rather than
on a third party: their submission is attached to a `public:` principal, and
`get_user_bundle` excludes guest rows from authenticated resolution, so they
are then walled off from the data they just entered.

This change does NOT revisit whether email or Telegram username should be
sufficient to auto-merge at all. #1412 froze that contract and recorded the
question as an open residual; it stays open here.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Synthetic throughout. No value here corresponds to a real subscriber.
_EMAIL = "owner@synthetic.test"
_HANDLE = "synthetic_handle"
_GUEST_EXT = "public:web-guest-000042"
_REAL_EXT = "owner@synthetic.test"


def _row(ext, **over):
    base = {
        "id": f"id-{ext}", "external_user_id": ext, "name": None,
        "email": None, "phone": None, "telegram_username": None,
        "profile_data": None, "settings_data": None,
    }
    base.update(over)
    return base


def _fake_txn(rows):
    """Stand in for the driver: it returns whatever the DB would, unfiltered."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda s, *a: False
    conn = MagicMock()
    conn.cursor.return_value = cur

    class _Txn:
        def __enter__(self): return conn
        def __exit__(self, *a): return False

    return _Txn


def _profile(user_id, **kw):
    from src.services.profile_context_resolver import ProfileContext
    return ProfileContext(user_id=user_id, **kw)


# ── The four doorways ───────────────────────────────────────────────────────

class TestGuestRowsAreNotCandidates:
    """Behavioural, not SQL-text. The cursor hands back a guest row alongside a
    real one and only the real one may survive — a predicate that is present
    but ineffective fails these."""

    def test_public_row_excluded_from_email_db_lookup(self):
        from src.repositories import profile_repo

        rows = [_row(_GUEST_EXT, email=_EMAIL), _row(_REAL_EXT, email=_EMAIL)]
        with patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_txn(rows)):
            found = profile_repo.find_profiles_by_email(_EMAIL)

        ids = {getattr(p, "user_id", None) for p in found}
        assert f"id-{_GUEST_EXT}" not in ids, "a public: row must never be an email candidate"
        assert f"id-{_REAL_EXT}" in ids, "the authenticated row must still resolve"

    def test_public_row_excluded_from_email_memory_fallback(self):
        from src.repositories import profile_repo

        mem = MagicMock()
        mem.list_profiles.return_value = [_GUEST_EXT, _REAL_EXT]
        mem.load_profile.side_effect = lambda uid: MagicMock(email=_EMAIL)

        with patch.object(profile_repo, "_db", return_value=None), \
             patch.object(profile_repo, "_memory", return_value=mem):
            found = profile_repo.find_profiles_by_email(_EMAIL)

        ids = {getattr(p, "user_id", None) for p in found}
        assert _GUEST_EXT not in ids, "the memory fallback needs the same exclusion"
        assert _REAL_EXT in ids

    def test_public_row_excluded_from_telegram_db_lookup(self):
        from src.repositories import profile_repo

        rows = [_row(_GUEST_EXT, telegram_username=_HANDLE),
                _row(_REAL_EXT, telegram_username=_HANDLE)]
        with patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_txn(rows)):
            found = profile_repo.find_profiles_by_telegram_username(_HANDLE)

        ids = {getattr(p, "user_id", None) for p in found}
        assert f"id-{_GUEST_EXT}" not in ids, "a public: row must never be a Telegram candidate"
        assert f"id-{_REAL_EXT}" in ids

    def test_public_row_excluded_from_telegram_memory_fallback(self):
        from src.repositories import profile_repo

        mem = MagicMock()
        mem.list_profiles.return_value = [_GUEST_EXT, _REAL_EXT]
        mem.load_profile.side_effect = lambda uid: MagicMock(telegram_username=_HANDLE)

        with patch.object(profile_repo, "_db", return_value=None), \
             patch.object(profile_repo, "_memory", return_value=mem):
            found = profile_repo.find_profiles_by_telegram_username(_HANDLE)

        ids = {getattr(p, "user_id", None) for p in found}
        assert _GUEST_EXT not in ids, "the memory fallback needs the same exclusion"
        assert _REAL_EXT in ids


# ── The consequence the exclusion exists to prevent ─────────────────────────

class TestSingleGuestCandidateNeverMerges:
    """End-to-end through the real finder AND the real mapper.

    Nothing about the decision is mocked — only the database rows are stood in
    for. With the guest row excluded there is no candidate at all, so the
    submission becomes `create_new`: the submitter gets their own row instead
    of being attached to a principal they cannot authenticate as.
    """

    def _resolve(self, rows, signal):
        from src.repositories import profile_repo
        from src.services.identity_flow_mapper import map_identity_flow

        with patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", _fake_txn(rows)), \
             patch.object(profile_repo, "_memory", return_value=MagicMock(list_profiles=lambda: [])):
            candidates = profile_repo.find_identity_candidates(signal)
        return map_identity_flow(signal, candidates)

    def test_single_public_email_candidate_never_merges(self):
        from src.services.identity_flow_mapper import IdentitySignal

        signal = IdentitySignal(source="jotform", email=_EMAIL)
        resolution = self._resolve([_row(_GUEST_EXT, email=_EMAIL)], signal)

        assert resolution.action != "merge", (
            "an email whose only candidate is a guest row must not auto-attach"
        )
        assert resolution.action == "create_new"
        assert resolution.matched_user_id is None

    def test_single_public_telegram_candidate_never_merges(self):
        from src.services.identity_flow_mapper import IdentitySignal

        signal = IdentitySignal(source="telegram", telegram_username=_HANDLE)
        resolution = self._resolve([_row(_GUEST_EXT, telegram_username=_HANDLE)], signal)

        assert resolution.action != "merge", (
            "a Telegram handle whose only candidate is a guest row must not auto-attach"
        )
        assert resolution.action == "create_new"
        assert resolution.matched_user_id is None


# ── Preservation: the frozen contract is untouched ──────────────────────────

class TestLegitimateExactMatchIsPreserved:
    """#1412 froze email/Telegram/user_id as auto-merge signals. This change
    narrows WHO can be a candidate; it must not narrow WHAT merges. These pass
    on the base tree too — that is the point of them."""

    def test_non_public_email_exact_match_still_merges(self):
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        resolution = map_identity_flow(
            IdentitySignal(source="jotform", email=_EMAIL),
            [_profile("u1", email=_EMAIL)],
        )
        assert resolution.action == "merge"
        assert resolution.matched_user_id == "u1"

    def test_non_public_telegram_exact_match_still_merges(self):
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        resolution = map_identity_flow(
            IdentitySignal(source="telegram", telegram_username=f"@{_HANDLE}"),
            [_profile("u1", telegram_username=_HANDLE)],
        )
        assert resolution.action == "merge"
        assert resolution.matched_user_id == "u1"

    def test_authenticated_row_still_resolves_through_both_finders(self):
        """The guard must not cost an authenticated caller their own row."""
        from src.repositories import profile_repo

        with patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction",
                          _fake_txn([_row(_REAL_EXT, email=_EMAIL,
                                          telegram_username=_HANDLE)])):
            by_email = profile_repo.find_profiles_by_email(_EMAIL)
            by_handle = profile_repo.find_profiles_by_telegram_username(_HANDLE)

        assert len(by_email) == 1
        assert len(by_handle) == 1


# ── Preservation: no trusted-field value escapes ────────────────────────────

class TestNoRawTrustedFieldValueEscapes:
    """Locked by #1412 at the egress point. Re-pinned here because this change
    alters which candidates reach that egress, and a regression would surface
    as an email or handle in a response body. Passes on base — a lock, not a
    fail-first item, and reported as such."""

    def test_no_raw_value_reaches_resolution_metadata(self):
        from src.rico_jotform_webhook import _identity_resolution_metadata
        from src.services.identity_flow_mapper import IdentityResolution

        meta = _identity_resolution_metadata(
            IdentityResolution(
                action="ask_user", confidence=0.6, matched_user_id="u1", reasons=[],
                conflicts={
                    "email": (_EMAIL, "other@synthetic.test"),
                    "telegram_username": (_HANDLE, "other_handle"),
                },
            )
        )
        blob = repr(meta)
        for raw in (_EMAIL, "other@synthetic.test", _HANDLE, "other_handle"):
            assert raw not in blob, f"trusted-field value escaped into metadata"
        assert set(meta["conflicts"]) == {"email", "telegram_username"}

    def test_finder_failure_logs_carry_no_raw_value(self, caplog):
        """The error path logs a ref, never the identifier itself."""
        import logging
        from src.repositories import profile_repo

        class _Boom:
            def __enter__(self): raise RuntimeError("db down")
            def __exit__(self, *a): return False

        with caplog.at_level(logging.DEBUG), \
             patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", lambda: _Boom()), \
             patch.object(profile_repo, "_memory",
                          return_value=MagicMock(list_profiles=lambda: [])):
            profile_repo.find_profiles_by_email(_EMAIL)
            profile_repo.find_profiles_by_telegram_username(_HANDLE)

        assert _EMAIL not in caplog.text, "raw email reached a log line"
        assert _HANDLE not in caplog.text, "raw telegram handle reached a log line"
