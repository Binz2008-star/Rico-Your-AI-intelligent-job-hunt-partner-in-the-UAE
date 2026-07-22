"""Tests for src/jsearch_client.py — the resilient JSearch fetch layer.

Covers the explicit requirements:
- cached JSearch result is reused (no second network call)
- 429 triggers retry/backoff (and exhaustion sets rate_limited)
- alt_link is present in the normalized job result
- normalization maps job_apply_link/job_google_link correctly

No live network calls — urllib.request.urlopen is mocked. time.sleep is patched
so backoff does not actually wait.
"""
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src import jsearch_client


@pytest.fixture(autouse=True)
def _clear_cache_and_key(monkeypatch):
    jsearch_client.clear_cache()
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    # Make backoff instantaneous.
    monkeypatch.setattr(jsearch_client.time, "sleep", lambda *_: None)
    yield
    jsearch_client.clear_cache()


def _resp(payload: dict):
    """A fake context-manager response like urlopen returns."""
    cm = MagicMock()
    cm.__enter__ = lambda self: self
    cm.__exit__ = lambda self, *a: False
    cm.read = lambda: json.dumps(payload).encode()
    return cm


_PAYLOAD = {
    "data": {
        "jobs": [
            {
                "job_id": "abc",
                "job_title": "Systems Engineer",
                "employer_name": "AESG",
                "job_city": "Dubai",
                "job_country": "UAE",
                "job_apply_link": "https://aesg.com/apply/123",
                "job_google_link": "https://google.com/search?q=aesg+engineer",
                "job_description": "desc",
            }
        ]
    }
}


# ── normalization / alt_link ──────────────────────────────────────────────────

class TestNormalize:
    def test_alt_link_present(self):
        job = jsearch_client.normalize_item(_PAYLOAD["data"]["jobs"][0])
        assert job["alt_link"] == "https://google.com/search?q=aesg+engineer"

    def test_apply_link_present(self):
        job = jsearch_client.normalize_item(_PAYLOAD["data"]["jobs"][0])
        assert job["apply_link"] == "https://aesg.com/apply/123"

    def test_link_prefers_apply_then_alt(self):
        job = jsearch_client.normalize_item({"job_google_link": "https://g/x"})
        assert job["link"] == "https://g/x"  # falls back to alt when no apply link

    def test_location_defaults_to_uae(self):
        job = jsearch_client.normalize_item({"job_title": "X"})
        assert job["location"] == "UAE"


# ── apply_options alternate selection ─────────────────────────────────────────

class TestApplyOptionsAlternate:
    """alt_link prefers a trusted apply_options mirror over job_google_link."""

    _GOOGLE = "https://google.com/search?q=env+manager"

    def _item(self, apply_options):
        return {
            "job_title": "Env Manager",
            "employer_name": "Acme",
            "job_apply_link": "https://www.gulftalent.com/uae/job/1",  # login-walled
            "job_google_link": self._GOOGLE,
            "apply_options": apply_options,
        }

    def test_trusted_board_mirror_wins_over_google_link(self):
        job = jsearch_client.normalize_item(self._item([
            {"publisher": "LinkedIn", "apply_link": "https://www.linkedin.com/jobs/view/123", "is_direct": False},
        ]))
        assert job["alt_link"] == "https://www.linkedin.com/jobs/view/123"

    def test_is_direct_employer_link_beats_trusted_board(self):
        job = jsearch_client.normalize_item(self._item([
            {"publisher": "LinkedIn", "apply_link": "https://www.linkedin.com/jobs/view/123", "is_direct": False},
            {"publisher": "Employer", "apply_link": "https://acme-careers.example.com/apply/9", "is_direct": True},
        ]))
        assert job["alt_link"] == "https://acme-careers.example.com/apply/9"

    def test_bad_and_google_options_fall_back_to_google_link(self):
        job = jsearch_client.normalize_item(self._item([
            {"publisher": "Trabajo", "apply_link": "https://ae.trabajo.org/job-1", "is_direct": False},
            {"publisher": "Jobrapido", "apply_link": "https://ae.jobrapido.com/jobpr/2", "is_direct": False},
            {"publisher": "Google", "apply_link": self._GOOGLE, "is_direct": False},
        ]))
        # No trustworthy mirror — legacy behavior preserved.
        assert job["alt_link"] == self._GOOGLE

    def test_unknown_domain_not_promoted(self):
        job = jsearch_client.normalize_item(self._item([
            {"publisher": "Mystery", "apply_link": "https://random-board.example.net/j/5", "is_direct": False},
        ]))
        assert job["alt_link"] == self._GOOGLE

    def test_option_equal_to_primary_skipped(self):
        job = jsearch_client.normalize_item(self._item([
            {"publisher": "GulfTalent", "apply_link": "https://www.gulftalent.com/uae/job/1", "is_direct": True},
        ]))
        assert job["alt_link"] == self._GOOGLE

    def test_junk_apply_options_tolerated(self):
        for junk in (None, "nope", 42, [None, "x", {"publisher": "P"}, {"apply_link": ""}]):
            job = jsearch_client.normalize_item(self._item(junk))
            assert job["alt_link"] == self._GOOGLE

    def test_absent_apply_options_keeps_google_link(self):
        item = self._item([])
        del item["apply_options"]
        job = jsearch_client.normalize_item(item)
        assert job["alt_link"] == self._GOOGLE


# ── UAE geo filter ────────────────────────────────────────────────────────────

def _payload_with(*jobs: dict) -> dict:
    return {"data": {"jobs": list(jobs)}}


def _job(**kw) -> dict:
    base = {
        "job_id": "id-" + str(kw.get("employer_name", "x")),
        "job_title": "Engineer",
        "employer_name": "Acme",
        "job_apply_link": "https://acme.com/apply",
    }
    base.update(kw)
    return base


class TestUaeGeoFilter:
    def test_is_uae_job_accepts_ae_code(self):
        assert jsearch_client._is_uae_job({"job_country": "AE"}) is True

    def test_is_uae_job_accepts_full_name(self):
        assert jsearch_client._is_uae_job({"job_country": "United Arab Emirates"}) is True

    def test_is_uae_job_rejects_us(self):
        assert jsearch_client._is_uae_job({"job_country": "US"}) is False

    def test_is_uae_job_rejects_saudi(self):
        assert jsearch_client._is_uae_job({"job_country": "SA"}) is False

    def test_is_uae_job_keeps_unknown_country(self):
        # Missing country is kept — the query already targeted country=ae.
        assert jsearch_client._is_uae_job({"job_title": "X"}) is True
        assert jsearch_client._is_uae_job({"job_country": ""}) is True

    def test_non_uae_job_filtered_out_of_search(self):
        payload = _payload_with(
            _job(employer_name="Raytheon", job_city="El Paso",
                 job_state="Texas", job_country="US")
        )
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(payload)):
            r = jsearch_client.search("engineer UAE")
        assert r.items == []

    def test_mixed_results_keep_only_uae(self):
        payload = _payload_with(
            _job(employer_name="Raytheon", job_country="US"),
            _job(employer_name="AESG", job_city="Dubai", job_country="AE"),
        )
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(payload)):
            r = jsearch_client.search("engineer UAE")
        assert len(r.items) == 1
        assert r.items[0]["company"] == "AESG"

    def test_uae_job_passes_through(self):
        payload = _payload_with(_job(employer_name="AESG", job_country="AE"))
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(payload)):
            r = jsearch_client.search("engineer UAE")
        assert len(r.items) == 1


# ── caching ───────────────────────────────────────────────────────────────────

class TestCaching:
    def test_cached_result_is_reused(self):
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(_PAYLOAD)) as uo:
            r1 = jsearch_client.search("systems engineer UAE")
            r2 = jsearch_client.search("systems engineer UAE")
        assert r1.cache_hit is False
        assert r2.cache_hit is True
        assert len(r2.items) == 1
        # Only ONE network call despite two searches.
        assert uo.call_count == 1

    def test_use_cache_false_bypasses_cache(self):
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(_PAYLOAD)) as uo:
            jsearch_client.search("q UAE")
            jsearch_client.search("q UAE", use_cache=False)
        assert uo.call_count == 2


# ── 429 retry / backoff ─────────────────────────────────────────────────────────

def _http_error(code):
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="err", hdrs=None, fp=io.BytesIO(b"")
    )


class TestRetryBackoff:
    def test_429_retries_then_succeeds(self):
        seq = [_http_error(429), _http_error(429), _resp(_PAYLOAD)]

        def _side_effect(*a, **k):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_side_effect):
            r = jsearch_client.search("q UAE")
        assert r.rate_limited is False
        assert len(r.items) == 1
        assert r.retries == 2  # two 429s before success

    def test_429_exhausted_sets_rate_limited(self):
        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_http_error(429)):
            r = jsearch_client.search("q UAE")
        assert r.rate_limited is True
        assert r.items == []
        assert r.retries == jsearch_client._MAX_RETRIES + 1

    def test_429_serves_stale_cache_when_available(self):
        # Prime cache with a good response.
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(_PAYLOAD)):
            jsearch_client.search("q UAE")
        # Now force fresh fetch to 429 — but cache is still warm, so cache hit short-circuits.
        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_http_error(429)) as uo:
            r = jsearch_client.search("q UAE")
        assert r.cache_hit is True  # served from cache, never hit the network
        assert uo.call_count == 0

    def test_non_retryable_4xx_breaks_immediately(self):
        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_http_error(403)) as uo:
            r = jsearch_client.search("q UAE")
        assert r.rate_limited is False
        assert r.error == "http_403"
        assert uo.call_count == 1  # no retries on 403

    def test_missing_api_key_returns_empty(self, monkeypatch):
        monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
        r = jsearch_client.search("q UAE")
        assert r.items == []
        assert r.error == "no_api_key"


# ── Cooperative cancellation (TASK-20260721-014) ──────────────────────────────

from src.services.cancellation import CancellationToken


def _tok(is_cancelled):
    return CancellationToken(operation_id="op_j", attempt=1, is_cancelled=is_cancelled)


class TestJsearchCancellation:
    def test_cancel_at_entry_issues_no_request(self):
        with patch.object(jsearch_client.urllib.request, "urlopen") as uo:
            r = jsearch_client.search("q UAE", cancel=_tok(lambda: True))
        assert r.cancelled is True
        assert r.error == "ownership_lost"
        assert r.provider == "none"
        assert uo.call_count == 0            # NO HTTP request

    def test_cancel_skips_cache_delivery(self):
        # Prime the cache with a good response (no cancellation).
        with patch.object(jsearch_client.urllib.request, "urlopen", return_value=_resp(_PAYLOAD)):
            jsearch_client.search("q UAE")
        # Now a de-owned worker must NOT be served the cache hit.
        with patch.object(jsearch_client.urllib.request, "urlopen") as uo:
            r = jsearch_client.search("q UAE", cancel=_tok(lambda: True))
        assert r.cancelled is True
        assert r.cache_hit is False
        assert uo.call_count == 0

    def test_no_new_retry_after_ownership_lost(self):
        """Finding #1/#3: a 429 that would normally retry must NOT start a new
        attempt once ownership is lost during the backoff wait."""
        state = {"n": 0}

        def _side_effect(*a, **k):
            state["n"] += 1
            raise _http_error(429)  # every attempt 429s

        # ownership is lost right after the first attempt fails → no 2nd request.
        cancel = _tok(lambda: state["n"] >= 1)
        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_side_effect) as uo:
            r = jsearch_client.search("q UAE", cancel=cancel)
        assert r.cancelled is True
        assert r.error == "ownership_lost"
        assert uo.call_count == 1            # first attempt only, no retry

    def test_interruptible_backoff_returns_promptly(self, monkeypatch):
        """Finding #3: the backoff wait is interruptible — a lost lease stops the
        wait via the cancel poll, it is NOT a fixed time.sleep(backoff)."""
        # Make the real wait observable: count sleep calls, keep them tiny.
        sleeps = {"n": 0}
        monkeypatch.setattr(
            jsearch_client.time, "sleep",
            lambda s: sleeps.__setitem__("n", sleeps["n"] + 1),
        )
        # Big backoff base so a non-interruptible sleep would loop many times;
        # cancellation observed during the wait ends it immediately.
        monkeypatch.setattr(jsearch_client, "_BACKOFF_BASE_S", 100.0)
        state = {"attempts": 0}

        def _side_effect(*a, **k):
            state["attempts"] += 1
            raise _http_error(429)

        # Not cancelled at the attempt guard; cancelled once we're in the wait.
        flip = {"n": 0}

        def _is_cancelled():
            flip["n"] += 1
            # checks 1-3 are False (entry, attempt guard, HTTP-error guard); the
            # 4th check — the first poll inside the backoff wait — flips True, so
            # cancellation is observed DURING the wait, exercising its
            # interruptibility rather than the error-handler short-circuit.
            return flip["n"] > 3

        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_side_effect):
            r = jsearch_client.search("q UAE", cancel=_tok(_is_cancelled))
        assert r.cancelled is True
        assert state["attempts"] == 1        # only one HTTP attempt was made
        assert sleeps["n"] <= 1              # the wait was cut short, not 100s of polls

    def test_inflight_success_after_cancel_writes_no_cache_no_observations(self, monkeypatch):
        """Finding #2/#5: a successful response that lands after ownership loss
        is discarded — no cache write, no job_observations, distinct cancelled."""
        recorded = {"n": 0}
        import src.repositories.job_observations_repo as obs
        monkeypatch.setattr(obs, "record_observations",
                            lambda *a, **k: recorded.__setitem__("n", recorded["n"] + 1))
        state = {"served": False}

        def _urlopen(*a, **k):
            state["served"] = True  # response is now in flight / arriving
            return _resp(_PAYLOAD)

        # Not cancelled at entry/attempt guard; cancelled once the body arrived.
        with patch.object(jsearch_client.urllib.request, "urlopen", side_effect=_urlopen):
            r = jsearch_client.search("q UAE", cancel=_tok(lambda: state["served"]))
        assert r.cancelled is True
        assert recorded["n"] == 0                     # no observations
        assert jsearch_client._cache_get("q UAE") is None  # no cache write
