"""Application status bucketing: reconciliation, unclassified, empty state.

Covers src/services/application_status_display.py and the two chat surfaces
that consume it (_handle_app_pipeline_summary and _build_tracking_message).

Deliberately uses synthetic, randomised status distributions rather than any
observed account's data — the invariants have to hold for any user's statuses
at any scale, not for one smoke-test dataset.
"""
from __future__ import annotations

import random

import pytest

from src.services.application_status_display import (
    UNCLASSIFIED,
    reconciliation_note,
    summarize,
)


# ── The display map's own invariants ─────────────────────────────────────────

class TestReconciliation:
    """The displayed buckets must always account for the headline total."""

    @pytest.mark.parametrize("seed", range(12))
    def test_reconciles_on_random_multi_status_fixture(self, seed):
        rng = random.Random(seed)
        vocabulary = [
            "applied", "saved", "opened", "opened_external", "follow_up_due",
            "prepared", "interview", "offer", "rejected", "decision_made",
            "found", "archived",
        ]
        by_status = {
            status: rng.randint(0, 5000)
            for status in rng.sample(vocabulary, rng.randint(1, len(vocabulary)))
        }
        expected_total = sum(by_status.values())

        summary = summarize(by_status, total=expected_total)

        assert summary.reconciles, (
            f"buckets {summary.displayed_total} != total {summary.total} "
            f"for {by_status!r}"
        )
        assert summary.displayed_total == expected_total
        assert sum(b.count for b in summary.buckets) == expected_total
        assert reconciliation_note(summary) == ""

    def test_every_counted_row_lands_in_exactly_one_bucket(self):
        # "opened" and "opened_external" collapse into one display bucket; the
        # collapse must add, never replace.
        summary = summarize({"opened": 187, "opened_external": 13}, total=200)
        assert summary.count("opened") == 200
        assert summary.reconciles

    def test_mismatched_total_is_disclosed_not_hidden(self):
        # The aggregate claims 194 rows but the grouped counts only add to 3 —
        # the summary must refuse to present 194 as if it were explained.
        summary = summarize({"applied": 1, "offer": 1, "saved": 1}, total=194)

        assert summary.displayed_total == 3
        assert summary.total == 194
        assert not summary.reconciles

        note = reconciliation_note(summary)
        assert "3" in note and "194" in note
        assert "don't reconcile" in note
        assert "194" in reconciliation_note(summary, arabic=True)

    def test_total_defaults_to_bucket_sum_when_not_supplied(self):
        summary = summarize({"applied": 2, "saved": 3})
        assert summary.total == 5
        assert summary.reconciles


class TestUnclassified:
    """A status with no display mapping must appear and be counted."""

    def test_unmapped_status_lands_in_unclassified_and_is_counted(self):
        summary = summarize(
            {"applied": 4, "ghosted_by_recruiter": 7, "needs_review": 2}, total=13
        )

        assert summary.count(UNCLASSIFIED) == 9
        assert summary.reconciles
        assert summary.displayed_total == 13
        assert set(summary.unclassified_statuses) == {
            "ghosted_by_recruiter", "needs_review",
        }
        assert UNCLASSIFIED in [b.key for b in summary.buckets]

    def test_null_status_becomes_unclassified_not_applied(self):
        # A NULL status column comes back from GROUP BY as None. Coercing it to
        # "applied" would fabricate applications the user never made.
        summary = summarize({None: 6, "applied": 1}, total=7)

        assert summary.count("applied") == 1
        assert summary.count(UNCLASSIFIED) == 6
        assert summary.reconciles

    def test_blank_status_becomes_unclassified(self):
        summary = summarize({"   ": 3}, total=3)
        assert summary.count(UNCLASSIFIED) == 3
        assert summary.unclassified_statuses == ("(no status)",)

    def test_status_matching_is_case_and_whitespace_insensitive(self):
        summary = summarize({" Applied ": 2, "APPLIED": 1}, total=3)
        assert summary.count("applied") == 3
        assert summary.count(UNCLASSIFIED) == 0


class TestEmptyAndDegenerate:
    def test_zero_rows_produces_no_buckets_and_no_invented_numbers(self):
        summary = summarize({}, total=0)
        assert summary.is_empty
        assert summary.buckets == ()
        assert summary.total == 0
        assert summary.displayed_total == 0
        assert summary.reconciles

    def test_zero_counts_do_not_create_buckets(self):
        summary = summarize({"applied": 0, "saved": 0}, total=0)
        assert summary.buckets == ()
        assert summary.is_empty

    def test_none_input_is_survivable(self):
        summary = summarize(None, total=None)
        assert summary.is_empty

    def test_uncoercible_count_does_not_crash_or_inflate(self):
        summary = summarize({"applied": "not a number", "saved": 2}, total=2)
        assert summary.count("applied") == 0
        assert summary.count("saved") == 2
        assert summary.reconciles


# ── The chat surfaces ────────────────────────────────────────────────────────

class _CVProfile:
    """Minimal completed profile — enough to reach the active-user router."""
    def __init__(self):
        self.cv_uploaded = True
        self.has_cv = True
        self.target_roles = ["HSE Officer"]
        self.preferred_cities = ["Dubai"]
        self.years_experience = 8
        self.skills = ["HSE"]
        self.full_name = "Test User"

    def get(self, key, default=None):
        return getattr(self, key, default)


def _run_summary(monkeypatch, message, by_status, total):
    """Drive _handle_app_pipeline_summary with a mocked grouped-stats query."""
    from unittest.mock import MagicMock, patch

    import src.rico_chat_api as mod
    from src.rico_chat_api import RicoChatAPI

    profile = _CVProfile()
    route = MagicMock()
    route.tool_name = None
    route.entities = {}
    route.tool_args = {}
    route.confirmation_prompt = None
    route.source = "keyword"

    monkeypatch.setattr(mod, "get_profile", lambda uid: profile)
    monkeypatch.setattr(mod, "_route", lambda *a, **kw: route)
    monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile)
    monkeypatch.setattr(mod, "hf_ok", lambda: False)

    api = RicoChatAPI()
    api._get_recent_context = lambda uid: {}
    api._append_chat = MagicMock()

    stats = {"total": total, "by_status": by_status}
    with patch("src.repositories.applications_repo.get_stats", return_value=stats):
        return api._handle_app_pipeline_summary("test-user", profile, message)


class TestPipelineSummarySurface:
    def test_every_status_is_accounted_for_in_the_message(self, monkeypatch):
        # The shape that was silently dropping 191 of 194 rows: the two largest
        # buckets have no dedicated field on the response, so they can only
        # survive if the message is built from the buckets themselves.
        by_status = {
            "opened": 187, "follow_up_due": 4, "applied": 1, "offer": 1, "saved": 1,
        }
        result = _run_summary(monkeypatch, "application summary", by_status, 194)

        assert result["total"] == 194
        assert result["reconciles"] is True
        assert sum(b["count"] for b in result["buckets"]) == 194
        assert "187" in result["message"]
        assert "4" in result["message"]

    def test_unclassified_status_reaches_the_user(self, monkeypatch):
        result = _run_summary(
            monkeypatch, "application summary", {"applied": 2, "mystery_state": 5}, 7
        )
        assert result["unclassified"] == 5
        assert result["unclassified_statuses"] == ["mystery_state"]
        assert "Other (unrecognised status)" in result["message"]
        assert sum(b["count"] for b in result["buckets"]) == result["total"]

    def test_zero_rows_gives_honest_empty_state(self, monkeypatch):
        result = _run_summary(monkeypatch, "application summary", {}, 0)

        assert result["total"] == 0
        assert result["buckets"] == []
        assert result["response_rate"] == "N/A"
        assert "haven't logged any applications yet" in result["message"]
        # No invented numbers and no congratulation on an empty pipeline.
        assert "🎉" not in result["message"]
        assert "0%" not in result["message"]

    def test_no_celebration_when_offer_is_a_minority_of_total(self, monkeypatch):
        by_status = {"opened": 187, "follow_up_due": 4, "applied": 1, "offer": 1, "saved": 1}
        result = _run_summary(monkeypatch, "application summary", by_status, 194)

        assert result["offered"] == 1
        assert "🎉" not in result["message"]
        assert "congratulations" not in result["message"].lower()

    def test_celebration_still_fires_when_offers_dominate(self, monkeypatch):
        result = _run_summary(monkeypatch, "application summary", {"offer": 3, "applied": 1}, 4)
        assert "🎉" in result["message"]

    def test_response_rate_states_its_denominator(self, monkeypatch):
        result = _run_summary(
            monkeypatch, "application summary", {"applied": 4, "interview": 1}, 5
        )
        assert result["response_rate"] == "25%"
        assert "of the 4 still in the applied bucket" in result["message"]

    def test_arabic_message_is_arabic(self, monkeypatch):
        result = _run_summary(
            monkeypatch, "ملخص طلباتي", {"opened": 187, "applied": 1}, 188
        )
        assert "مسار طلباتك" in result["message"]
        assert "روابط فُتحت دون تقديم" in result["message"]

    def test_db_failure_is_reported_not_rendered_as_zero(self, monkeypatch):
        from unittest.mock import MagicMock, patch

        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI

        profile = _CVProfile()
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile)
        api = RicoChatAPI()
        api._append_chat = MagicMock()

        with patch(
            "src.repositories.applications_repo.get_stats",
            side_effect=RuntimeError("db down"),
        ):
            result = api._handle_app_pipeline_summary("u", profile, "application summary")

        assert result["unavailable"] is True
        assert "haven't logged any applications" not in result["message"]
        assert "total" not in result


class TestTrackingMessageSurface:
    """_build_tracking_message counts from the aggregate, itemizes from the page."""

    def _api(self):
        from unittest.mock import MagicMock

        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        api._append_chat = MagicMock()
        return api

    def test_counts_come_from_stats_not_from_the_page(self):
        # One page of 2 rows, but the aggregate says 194. The reply must speak
        # for all 194 — counting the page would report a page as a pipeline.
        stats = {
            "total": 194,
            "by_status": {"opened": 187, "follow_up_due": 4, "applied": 1,
                          "offer": 1, "saved": 1},
        }
        page = [
            {"title": "HSE Officer", "company": "Acme", "status": "applied"},
            {"title": "Safety Lead", "company": "Globex", "status": "opened"},
        ]
        msg = self._api()._build_tracking_message(page, stats)

        assert "194 tracked applications" in msg
        assert "187 links opened, not applied" in msg
        assert "and 184 more" in msg

    def test_unclassified_status_reaches_this_surface_too(self):
        stats = {"total": 5, "by_status": {"applied": 2, "weird_state": 3}}
        page = [{"title": "T", "company": "C", "status": "applied"}]
        msg = self._api()._build_tracking_message(page, stats)

        assert "3 other (unrecognised status)" in msg

    def test_zero_rows_gives_honest_empty_state(self):
        msg = self._api()._build_tracking_message([], {"total": 0, "by_status": {}})
        assert "no tracked applications yet" in msg
        assert "🎉" not in msg

    def test_derived_follow_up_is_distinguished_from_stored_status(self):
        stats = {"total": 10, "by_status": {"applied": 6, "follow_up_due": 4}}
        page = [
            {"title": "T1", "company": "C1", "status": "applied", "needs_follow_up": True},
            {"title": "T2", "company": "C2", "status": "applied"},
        ]
        msg = self._api()._build_tracking_message(page, stats)

        assert "4 follow-ups due" in msg          # stored status, all 10 rows
        assert "Derived signal (not a stored status)" in msg
        assert "of the 2 records I loaded" in msg  # scoped to the page, stated

    def test_non_reconciling_stats_are_disclosed(self):
        stats = {"total": 194, "by_status": {"applied": 1}}
        page = [{"title": "T", "company": "C", "status": "applied"}]
        msg = self._api()._build_tracking_message(page, stats)

        assert "don't reconcile" in msg
        assert "194" in msg
