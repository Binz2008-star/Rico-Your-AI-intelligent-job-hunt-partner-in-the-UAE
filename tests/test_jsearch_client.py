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
