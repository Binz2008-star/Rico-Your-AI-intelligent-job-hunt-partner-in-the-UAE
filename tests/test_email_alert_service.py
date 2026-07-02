"""tests/test_email_alert_service.py

Tests for the personalized job-alert email sweep (PR-2).

Everything external is mocked — no live match engine, SMTP, DB, or network.
Invariants verified:
  - kill-switch: sweep sends nothing unless RICO_ENABLE_EMAIL_ALERTS is truthy
  - dry_run bypasses the kill-switch and never sends/logs
  - synthetic/internal recipients are skipped
  - frequency cap: a user emailed within the cadence window is skipped
  - fewer than MIN_JOBS strong matches -> no email
  - happy path: email sent, each job logged for dedup
  - send failure -> reported, nothing logged
  - _find_matches drops excluded (applied/saved), already-emailed, sub-threshold,
    and link-less jobs, and caps at MAX_JOBS
  - render_email: subject reflects count/city, HTML has titles + unsubscribe,
    body carries no CV text / PII
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services import email_alert_service as eas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jobs(n=3):
    return [
        {
            "title": f"Marketing Manager {i}",
            "company": f"Acme {i}",
            "location": "Dubai, UAE",
            "score": 90 - i,
            "link": f"https://example.com/job/{i}",
            "why": "matches your target role and Dubai preference",
            "job_key": f"key{i}",
        }
        for i in range(1, n + 1)
    ]


def _user(email="jane@gmail.com", freq="daily"):
    return {
        "external_user_id": email,
        "name": "Jane",
        "email": email,
        "email_alert_frequency": freq,
    }


# ---------------------------------------------------------------------------
# Kill-switch + sweep orchestration
# ---------------------------------------------------------------------------

class TestSweepKillSwitch:
    def test_disabled_when_flag_off(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_EMAIL_ALERTS", raising=False)
        with patch("src.repositories.profile_repo.get_users_with_email_alerts") as roster:
            out = eas.run_email_alert_sweep()
        assert out["status"] == "disabled"
        assert out["sent"] == 0
        roster.assert_not_called()  # short-circuits before roster lookup

    def test_dry_run_bypasses_kill_switch(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_EMAIL_ALERTS", raising=False)
        with patch("src.repositories.profile_repo.get_users_with_email_alerts", return_value=[_user()]), \
             patch.object(eas, "send_alert_email", return_value={"status": "would_send", "jobs": 4}) as sae:
            out = eas.run_email_alert_sweep(dry_run=True)
        assert out["status"] == "ok"
        assert out["sent"] == 1
        assert sae.call_args.kwargs["dry_run"] is True

    def test_enabled_sends_and_counts(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_EMAIL_ALERTS", "true")
        users = [_user("a@gmail.com"), _user("b@gmail.com"), _user("c@gmail.com")]
        outcomes = [
            {"status": "sent", "jobs": 5},
            {"status": "skipped_no_matches", "jobs": 1},
            {"status": "send_failed", "jobs": 3},
        ]
        with patch("src.repositories.profile_repo.get_users_with_email_alerts", return_value=users), \
             patch.object(eas, "send_alert_email", side_effect=outcomes):
            out = eas.run_email_alert_sweep()
        assert out == {"status": "ok", "users": 3, "sent": 1, "skipped": 1, "failed": 1, "dry_run": False}


# ---------------------------------------------------------------------------
# Per-user send decisions
# ---------------------------------------------------------------------------

class TestSendAlertEmail:
    def _patches(self, *, synthetic=False, recent=False, profile=object(), matches=None):
        """Common patch context for send_alert_email; returns an ExitStack-like list."""
        return {
            "syn": patch("src.services.profile_nudge_service._is_synthetic_email", return_value=synthetic),
            "freq": patch("src.services.email_notifications.emailed_within_hours", return_value=recent),
            "prof": patch("src.repositories.profile_repo.get_profile", return_value=profile),
            "match": patch.object(eas, "_find_matches", return_value=matches if matches is not None else []),
        }

    def test_synthetic_skipped(self):
        p = self._patches(synthetic=True)
        with p["syn"], p["freq"], p["prof"], p["match"]:
            out = eas.send_alert_email(_user("test@ricohunt.com"))
        assert out["status"] == "skipped_synthetic"

    def test_frequency_cap_skips(self):
        p = self._patches(recent=True)
        with p["syn"], p["freq"], p["prof"], p["match"]:
            out = eas.send_alert_email(_user())
        assert out["status"] == "skipped_frequency"

    def test_no_profile_skips(self):
        p = self._patches(profile=None)
        with p["syn"], p["freq"], p["prof"], p["match"]:
            out = eas.send_alert_email(_user())
        assert out["status"] == "skipped_no_profile"

    def test_too_few_matches_no_send(self):
        p = self._patches(matches=_jobs(2))  # below MIN_JOBS default 3
        with p["syn"], p["freq"], p["prof"], p["match"], \
             patch("src.services.mailer.send_email") as send:
            out = eas.send_alert_email(_user())
        assert out["status"] == "skipped_no_matches"
        send.assert_not_called()

    def test_dry_run_would_send_no_side_effects(self):
        p = self._patches(matches=_jobs(4))
        with p["syn"], p["freq"], p["prof"], p["match"], \
             patch("src.services.mailer.send_email") as send, \
             patch("src.services.email_notifications.log_email_alert") as log:
            out = eas.send_alert_email(_user(), dry_run=True)
        assert out["status"] == "would_send"
        assert out["jobs"] == 4
        send.assert_not_called()
        log.assert_not_called()

    def test_happy_path_sends_and_logs_each_job(self):
        jobs = _jobs(4)
        p = self._patches(matches=jobs)
        with p["syn"], p["freq"], p["prof"], p["match"], \
             patch("src.services.email_notifications.ensure_unsubscribe_token", return_value="tok"), \
             patch("src.services.mailer.send_email", return_value=True) as send, \
             patch("src.services.email_notifications.log_email_alert") as log:
            out = eas.send_alert_email(_user())
        assert out["status"] == "sent"
        assert out["jobs"] == 4
        send.assert_called_once()
        # subject + text + html all passed
        kw = send.call_args.kwargs
        assert kw["to_email"] == "jane@gmail.com"
        assert kw["html"] and kw["body"]
        assert log.call_count == 4  # one per job for dedup

    def test_send_failure_reports_and_does_not_log(self):
        jobs = _jobs(3)
        p = self._patches(matches=jobs)
        with p["syn"], p["freq"], p["prof"], p["match"], \
             patch("src.services.email_notifications.ensure_unsubscribe_token", return_value="tok"), \
             patch("src.services.mailer.send_email", return_value=False), \
             patch("src.services.email_notifications.log_email_alert") as log:
            out = eas.send_alert_email(_user())
        assert out["status"] == "send_failed"
        log.assert_not_called()


# ---------------------------------------------------------------------------
# Match filtering
# ---------------------------------------------------------------------------

class TestFindMatches:
    def _run(self, matches, *, excluded=None, already_emailed=None, threshold=50):
        result = {"status": "completed", "matches": matches}
        system = MagicMock()
        system.run_for_profile.return_value = result

        excluded = excluded or []
        already = set(already_emailed or [])

        def _was_sent(user_id, job_key, *a, **k):
            return job_key in already

        with patch("src.rico_repo_adapter.RicoSystem", return_value=system), \
             patch("src.repositories.user_job_context_repo.get_by_status", return_value=excluded), \
             patch("src.services.email_notifications.was_email_alert_sent", side_effect=_was_sent), \
             patch("src.services.settings_service.get_settings", return_value={"score_threshold_watch": threshold}):
            return eas._find_matches(profile=MagicMock(), user_id="u@x.com")

    def _m(self, i, score=80, link=True, loc="Dubai, UAE"):
        d = {"title": f"Role {i}", "company": f"Co {i}", "location": loc,
             "score": score, "rico_explanation": "good fit"}
        if link:
            d["link"] = f"https://x.com/{i}"
        return d

    def test_threshold_filters_low_scores(self):
        got = self._run([self._m(1, score=80), self._m(2, score=40)], threshold=50)
        assert [j["title"] for j in got] == ["Role 1"]

    def test_linkless_jobs_dropped(self):
        got = self._run([self._m(1, link=False), self._m(2)])
        assert [j["title"] for j in got] == ["Role 2"]

    def test_excluded_applied_saved_dropped(self):
        excluded = [{"title": "Role 1", "company": "Co 1"}]
        got = self._run([self._m(1), self._m(2)], excluded=excluded)
        assert [j["title"] for j in got] == ["Role 2"]

    def test_already_emailed_dropped(self):
        from src.applications import get_job_id
        jk = get_job_id({"title": "Role 1", "company": "Co 1",
                         "location": "Dubai, UAE", "link": "https://x.com/1"})
        got = self._run([self._m(1), self._m(2)], already_emailed=[jk])
        assert [j["title"] for j in got] == ["Role 2"]

    def test_caps_at_max_jobs(self):
        got = self._run([self._m(i) for i in range(1, 12)])
        assert len(got) == eas.MAX_JOBS


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRender:
    def test_subject_reflects_count_and_city(self):
        subject, _, _ = eas.render_email(name="Jane", email="j@x.com",
                                         jobs=_jobs(3), unsubscribe_token="tok")
        assert "3" in subject and "Dubai" in subject

    def test_html_has_titles_and_unsubscribe(self):
        _, text, html = eas.render_email(name="Jane", email="j@x.com",
                                         jobs=_jobs(2), unsubscribe_token="tok")
        assert "Marketing Manager 1" in html
        assert "unsubscribe?token=tok" in html
        assert "unsubscribe?token=tok" in text
        # CTA link present in both parts
        assert "https://example.com/job/1" in html
        assert "https://example.com/job/1" in text

    def test_no_pii_or_cv_in_body(self):
        # Body must only contain public listing fields — never CV text / phone / email addr of others
        jobs = _jobs(3)
        _, text, html = eas.render_email(name="Jane", email="jane@gmail.com",
                                         jobs=jobs, unsubscribe_token="tok")
        # The recipient's own email should not be embedded in the marketing body
        assert "jane@gmail.com" not in html
        assert "curriculum" not in html.lower() and "cv text" not in html.lower()


# ---------------------------------------------------------------------------
# Fix #1 — unsubscribe URL resolves in production
# ---------------------------------------------------------------------------

class TestUnsubscribeUrl:
    def test_url_routes_through_frontend_proxy(self):
        # Default (no RICO_UNSUBSCRIBE_BASE_URL): link must go through the /proxy
        # path the frontend rewrites to the backend, NOT the bare /api/v1 path
        # that only exists on the backend host and 404s on the app domain.
        url = eas._unsubscribe_url("tok")
        assert "/proxy/api/v1/email/unsubscribe?token=tok" in url
        # Regression guard for finding #1: the segment right after the host must
        # be /proxy, never /api (the previously-broken form).
        assert "ricohunt.com/api/v1/email" not in url
        assert url.startswith(eas._APP_BASE_URL + "/proxy/")

    def test_proxy_suffix_matches_registered_backend_route(self):
        # The path proxied to the backend must equal a real backend route,
        # otherwise the rewrite lands on a 404.
        from src.api.routers.email_alerts import router

        route_paths = {r.path for r in router.routes}
        assert "/api/v1/email/unsubscribe" in route_paths
        url = eas._unsubscribe_url("tok")
        proxied_path = url.split("/proxy", 1)[1].split("?", 1)[0]
        assert proxied_path in route_paths

    def test_no_token_falls_back_to_settings(self):
        url = eas._unsubscribe_url(None)
        assert url.endswith("/settings")


# ---------------------------------------------------------------------------
# Fix #2 — daily cadence tolerates ~24h cron jitter
# ---------------------------------------------------------------------------

class TestFrequencyWindow:
    def test_daily_window_is_under_24h(self):
        # A 24h-spaced cron must fall OUTSIDE the window, so daily users stay
        # eligible every run instead of being skipped every other day.
        assert eas._FREQ_WINDOW_HOURS["daily"] < 24

    def test_weekly_window_is_under_7_days(self):
        assert eas._FREQ_WINDOW_HOURS["weekly"] < 24 * 7

    def test_send_uses_daily_window_not_full_day(self):
        captured = {}

        def _fake_within_hours(user_id, hours, *a, **k):
            captured["hours"] = hours
            return False  # 24h-old send is outside a <24h window → eligible

        with patch("src.services.profile_nudge_service._is_synthetic_email", return_value=False), \
             patch("src.services.email_notifications.emailed_within_hours", side_effect=_fake_within_hours), \
             patch("src.repositories.profile_repo.get_profile", return_value=object()), \
             patch.object(eas, "_find_matches", return_value=_jobs(3)), \
             patch("src.services.email_notifications.ensure_unsubscribe_token", return_value="tok"), \
             patch("src.services.mailer.send_email", return_value=True), \
             patch("src.services.email_notifications.log_email_alert"):
            out = eas.send_alert_email(_user(freq="daily"))
        # Called with the daily window, which must be < 24h, and the user proceeds.
        assert captured["hours"] == eas._FREQ_WINDOW_HOURS["daily"]
        assert captured["hours"] < 24
        assert out["status"] == "sent"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
