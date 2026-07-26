"""A phone number is a contact detail, not proof of who someone is.

The Jotform identity path treated an exact phone match as a STRONG signal —
the same weight as a verified email or an explicit user_id — so a single
phone-matched candidate produced ``action="merge"`` and the submission was
attached to that account with no human in the loop.

Two independent defects made that reachable:

  * ``find_profiles_by_phone`` drew candidates with no ``public:`` exclusion,
    so a guest row could be the matched account; and
  * a lone phone match scored 1.0 >= the strong threshold, so the
    "multiple strong matches -> ask_user" guard never engaged.

The guard protects the crowded case and leaves the lonely one exposed: a phone
held by exactly one candidate merges immediately. That asymmetry is why
"multiple candidates -> ask_user" is not, on its own, containment.

Containment here is deliberately narrow: phone stops being sufficient on its
own, and guest rows stop being candidates. Phone normalisation is NOT
redesigned — the mismatch between the suffix-based lookup and the scorer's
exact normalised comparison is recorded as a residual, not fixed here.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Synthetic throughout. No value here corresponds to a real subscriber.
_PHONE = "+971500000001"
_PHONE_ALT_FORMAT = "971 50 000 0001"
_OTHER_PHONE = "+971500000002"


def _profile(user_id, **kw):
    from src.services.profile_context_resolver import ProfileContext
    return ProfileContext(user_id=user_id, **kw)


# ── 1-2, 4-6: the resolution contract ───────────────────────────────────────

class TestPhoneAloneNeverMerges:
    def test_single_phone_only_candidate_is_ask_user_not_merge(self):
        """THE defect. One candidate, matched only by phone, merged silently."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        candidate = _profile("u1", phone=_PHONE)
        signal = IdentitySignal(source="jotform", phone=_PHONE_ALT_FORMAT)
        resolution = map_identity_flow(signal, [candidate])

        assert resolution.action == "ask_user", (
            "a phone match alone is not ownership evidence and must not auto-attach"
        )
        assert resolution.action != "merge"

    def test_multiple_phone_candidates_remain_ask_user(self):
        """Pre-existing guard, pinned so the fix cannot regress it."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        signal = IdentitySignal(source="jotform", phone=_PHONE)
        resolution = map_identity_flow(
            signal, [_profile("u1", phone=_PHONE), _profile("u2", phone=_PHONE)]
        )
        assert resolution.action == "ask_user"

    def test_verified_email_only_single_match_still_merges(self):
        """Preservation. An exact email match is verified evidence and still merges."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        candidate = _profile("u1", email="owner@synthetic.test")
        signal = IdentitySignal(source="jotform", email="owner@synthetic.test")
        resolution = map_identity_flow(signal, [candidate])

        assert resolution.action == "merge"
        assert resolution.matched_user_id == "u1"

    def test_verified_telegram_only_single_match_still_merges(self):
        """Preservation. An exact Telegram handle match still merges."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        candidate = _profile("u1", telegram_username="synthetic_handle")
        signal = IdentitySignal(source="telegram", telegram_username="@synthetic_handle")
        resolution = map_identity_flow(signal, [candidate])

        assert resolution.action == "merge"
        assert resolution.matched_user_id == "u1"

    def test_trusted_user_id_match_still_merges(self):
        """Preservation. An explicit user_id is the caller's own principal."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        candidate = _profile("u1", phone=_PHONE)
        signal = IdentitySignal(source="chat", user_id="u1", phone=_PHONE)
        resolution = map_identity_flow(signal, [candidate])

        assert resolution.action == "merge"
        assert resolution.matched_user_id == "u1"

    def test_phone_plus_verified_email_still_merges(self):
        """Phone is not poison — it is simply not sufficient alone."""
        from src.services.identity_flow_mapper import IdentitySignal, map_identity_flow

        candidate = _profile("u1", email="owner@synthetic.test", phone=_PHONE)
        signal = IdentitySignal(
            source="jotform", email="owner@synthetic.test", phone=_PHONE
        )
        resolution = map_identity_flow(signal, [candidate])
        assert resolution.action == "merge"


# ── 3-4: guest rows are not phone candidates ────────────────────────────────

class TestGuestRowsAreNotPhoneCandidates:
    def test_public_rows_excluded_from_db_lookup(self):
        """A guest row returned by the driver must not survive as a candidate.

        Asserted behaviourally against the real function: the cursor hands back
        one guest row and one authenticated row, and only the authenticated one
        may come out. A SQL-text assertion alone would pass for a predicate that
        is present but ineffective.
        """
        from src.repositories import profile_repo

        rows = [
            {"id": "guest-1", "external_user_id": "public:web-guest-000001",
             "phone": _PHONE, "email": None, "name": None,
             "telegram_username": None, "profile_data": None, "settings_data": None},
            {"id": "real-1", "external_user_id": "owner@synthetic.test",
             "phone": _PHONE, "email": "owner@synthetic.test", "name": None,
             "telegram_username": None, "profile_data": None, "settings_data": None},
        ]

        cur = MagicMock()
        cur.fetchall.return_value = rows
        cur.__enter__ = lambda s: cur
        cur.__exit__ = lambda s, *a: False
        conn = MagicMock()
        conn.cursor.return_value = cur

        class _Txn:
            def __enter__(self): return conn
            def __exit__(self, *a): return False

        with patch.object(profile_repo, "_db", return_value=MagicMock()), \
             patch.object(profile_repo, "_db_transaction", lambda: _Txn()):
            found = profile_repo.find_profiles_by_phone(_PHONE)

        ids = {getattr(p, "user_id", None) for p in found}
        assert "guest-1" not in ids, "a public: row must never be a phone candidate"

    def test_public_rows_excluded_from_memory_fallback(self):
        """The memory path is a second, independent doorway into candidacy."""
        from src.repositories import profile_repo

        mem = MagicMock()
        mem.list_profiles.return_value = ["public:web-guest-000002", "owner@synthetic.test"]

        def _load(uid):
            p = MagicMock()
            p.phone = _PHONE
            return p

        mem.load_profile.side_effect = _load

        with patch.object(profile_repo, "_db", return_value=None), \
             patch.object(profile_repo, "_memory", return_value=mem):
            found = profile_repo.find_profiles_by_phone(_PHONE)

        ids = {getattr(p, "user_id", None) for p in found}
        assert "public:web-guest-000002" not in ids, (
            "the memory fallback must apply the same guest exclusion as the DB path"
        )


# ── 7-8: the webhook boundary ───────────────────────────────────────────────

class TestAskUserWritesNothingAndLeaksNothing:
    def _run_phone_only_submission(self, db):
        """Drive the REAL resolver — nothing about the decision is mocked."""
        from src.rico_jotform_webhook import handle_jotform_submission

        candidate = _profile("existing-user-999", phone=_PHONE)
        env = {k: v for k, v in os.environ.items() if k != "JOTFORM_FORM_ID"}
        with patch("src.rico_jotform_webhook.RicoDB", return_value=db), \
             patch.dict(os.environ, env, clear=True), \
             patch("src.rico_jotform_webhook.find_identity_candidates",
                   return_value=[candidate]), \
             patch("src.repositories.onboarding_repo.mark_onboarding_complete"):
            return handle_jotform_submission(
                {"submissionID": "sub-phone-containment-1",
                 "phone": _PHONE, "consent": True}
            )

    def test_ask_user_performs_zero_identity_profile_or_settings_writes(self):
        db = MagicMock()
        db.upsert_user.return_value = {"id": "db-uuid-1"}
        db.register_webhook_event.return_value = True

        result = self._run_phone_only_submission(db)

        assert result["reason"] == "pending_identity_confirmation"
        db.upsert_user.assert_not_called()
        db.upsert_profile.assert_not_called()
        db.upsert_settings.assert_not_called()
        # The submission is still claimed, so a provider retry is still deduped.
        db.register_webhook_event.assert_called_once()
        db.mark_webhook_event_processed.assert_called_once()

    def test_no_raw_phone_reaches_response_metadata_or_logs(self, caplog):
        """The conflict path is where the values actually escape.

        ``_find_conflicts`` records ``(signal_value, candidate_value)`` pairs,
        and the webhook copies that dict verbatim into the HTTP response body.
        A phone-only submission never reaches it — a conflict needs BOTH sides
        to hold a value — so the leak is exercised with a verified email match
        plus a differing phone, which is the shape that reaches ``ask_user``
        carrying conflicts.
        """
        import logging
        from src.rico_jotform_webhook import handle_jotform_submission

        db = MagicMock()
        db.upsert_user.return_value = {"id": "db-uuid-1"}
        db.register_webhook_event.return_value = True

        candidate = _profile(
            "existing-user-998", email="owner@synthetic.test", phone=_OTHER_PHONE
        )
        env = {k: v for k, v in os.environ.items() if k != "JOTFORM_FORM_ID"}
        with caplog.at_level(logging.DEBUG), \
             patch("src.rico_jotform_webhook.RicoDB", return_value=db), \
             patch.dict(os.environ, env, clear=True), \
             patch("src.rico_jotform_webhook.find_identity_candidates",
                   return_value=[candidate]), \
             patch("src.repositories.onboarding_repo.mark_onboarding_complete"):
            result = handle_jotform_submission(
                {"submissionID": "sub-phone-containment-2",
                 "email": "owner@synthetic.test", "phone": _PHONE, "consent": True}
            )

        blob = repr(result) + "\n" + caplog.text
        for raw in (_PHONE, _OTHER_PHONE):
            digits = "".join(ch for ch in raw if ch.isdigit())
            assert raw not in blob, "raw phone must never reach the response or the log"
            assert digits not in blob, "nor its digit-only form"
        # The conflict is still REPORTED — the field name survives, the value does not.
        assert "phone" in repr(result.get("identity_resolution", {}).get("conflicts", {}))
