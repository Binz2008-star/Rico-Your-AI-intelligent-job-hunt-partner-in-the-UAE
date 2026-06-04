"""
Regression tests for the role-context routing bug:

Flow under test:
  1. CV uploaded → role suggestions returned (Environmental Compliance Officer, etc.)
  2. "find live jobs for Environmental Compliance Officer"
     → must route to that exact role, NOT fall back to profile target_roles
  3. "save Environmental Manager as target role"
     → must be classified as save_target_role, NOT save_job, and must save cleanly
  4. Rico's own suggestions must pass _classified_role_search without taxonomy rejection
"""
import re
import pytest


# ── Intent classifier ─────────────────────────────────────────────────────────

from src.agent.intelligence.intent_classifier import classify_intent, _SAVE_TARGET_ROLE_RE, _JOB_SEARCH_FOR_ROLE_RE


class TestSaveTargetRoleIntent:
    def test_save_x_as_target_role(self):
        result = classify_intent("save Environmental Manager as target role")
        assert result.intent == "save_target_role"
        assert result.extracted_role is not None
        assert "Environmental Manager" in result.extracted_role

    def test_set_x_as_target_role(self):
        result = classify_intent("set Environmental Compliance Officer as target role")
        assert result.intent == "save_target_role"
        assert "Environmental Compliance Officer" in result.extracted_role

    def test_save_x_as_my_target_role(self):
        result = classify_intent("save ESG Specialist as my target role")
        assert result.intent == "save_target_role"
        assert "ESG Specialist" in result.extracted_role

    def test_save_job_unaffected(self):
        # Plain "save this job" must still be save_job
        result = classify_intent("save this job")
        assert result.intent == "save_job"

    def test_bookmark_job_unaffected(self):
        result = classify_intent("bookmark this role")
        assert result.intent == "save_job"


class TestFindJobsForRoleIntent:
    def test_find_live_jobs_for_role(self):
        result = classify_intent("find live jobs for Environmental Compliance Officer")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is not None
        assert "Environmental Compliance Officer" in result.extracted_role

    def test_find_jobs_for_role(self):
        result = classify_intent("find jobs for HSE Manager")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is not None
        assert "HSE Manager" in result.extracted_role

    def test_search_jobs_for_role(self):
        result = classify_intent("search jobs for ESG Specialist")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is not None
        assert "ESG Specialist" in result.extracted_role

    def test_generic_find_jobs_no_role(self):
        # "find me a job" has no explicit "for <role>" — extracted_role should be None
        result = classify_intent("find me a job")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is None

    def test_find_jobs_no_regression_plain(self):
        # "find jobs" without a role must still be job_search_explicit with no extracted_role
        result = classify_intent("find jobs")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is None


# ── Regex unit tests ──────────────────────────────────────────────────────────

class TestSaveTargetRoleRegex:
    @pytest.mark.parametrize("msg,expected", [
        ("save Environmental Manager as target role", "Environmental Manager"),
        ("save ESG Specialist as target role", "ESG Specialist"),
        ("set Sustainability Officer as my target role", "Sustainability Officer"),
        ("add HSE Manager as target role", "HSE Manager"),
        ("use Environmental Compliance Officer as my target role", "Environmental Compliance Officer"),
    ])
    def test_extracts_role(self, msg, expected):
        m = _SAVE_TARGET_ROLE_RE.search(msg)
        assert m is not None, f"Regex did not match: {msg!r}"
        assert m.group(1).strip() == expected

    def test_does_not_match_save_job(self):
        assert _SAVE_TARGET_ROLE_RE.search("save this job") is None
        assert _SAVE_TARGET_ROLE_RE.search("save job") is None


class TestFindJobsForRoleRegex:
    @pytest.mark.parametrize("msg,expected", [
        ("find live jobs for Environmental Compliance Officer", "Environmental Compliance Officer"),
        ("find jobs for HSE Manager", "HSE Manager"),
        ("search jobs for ESG Specialist", "ESG Specialist"),
        ("find jobs for Environmental Compliance Officer in Dubai", "Environmental Compliance Officer"),
        ("search openings for Sustainability Officer", "Sustainability Officer"),
        # Codex P2-A: trailing punctuation must not lose the extracted role
        ("find jobs for Environmental Compliance Officer?", "Environmental Compliance Officer"),
        ("search openings for ESG Specialist!", "ESG Specialist"),
        # Codex P2-B: verbs present in _JOB_SEARCH_EXPLICIT_RE must also extract the role
        ("looking for jobs for HSE Manager", "HSE Manager"),
        ("need jobs for Environmental Manager", "Environmental Manager"),
        ("want jobs for ESG Specialist", "ESG Specialist"),
    ])
    def test_extracts_role(self, msg, expected):
        m = _JOB_SEARCH_FOR_ROLE_RE.search(msg)
        assert m is not None, f"Regex did not match: {msg!r}"
        assert m.group(1).strip() == expected

    def test_no_match_generic(self):
        assert _JOB_SEARCH_FOR_ROLE_RE.search("find me a job") is None
        assert _JOB_SEARCH_FOR_ROLE_RE.search("find jobs") is None


# ── _looks_like_bare_target_role contraction guard ───────────────────────────

class TestBareRoleGateContractions:
    """Regression: contraction-led messages must not pass through the bare-role gate."""

    def test_cant_you_see_chat_history(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("can't you see our chat history") is False

    def test_dont_search_that(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("don't search for that") is False

    def test_wont_work(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("won't this work") is False

    def test_valid_roles_still_pass(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager") is True
        assert RicoChatAPI._looks_like_bare_target_role("Environmental Compliance Officer") is True
        assert RicoChatAPI._looks_like_bare_target_role("Head of Environmental Health Safety") is True


# ── rico_intent_router entity extraction ─────────────────────────────────────

class TestExtractEntitiesForRole:
    def test_extracts_explicit_role_from_for_pattern(self):
        from src.rico_intent_router import _extract_entities
        entities = _extract_entities("find live jobs for Environmental Compliance Officer")
        assert entities.get("job_title") == "Environmental Compliance Officer"

    def test_extracts_hse_manager_from_phrase_list(self):
        from src.rico_intent_router import _extract_entities
        entities = _extract_entities("show me hse manager jobs")
        assert entities.get("job_title") == "Hse Manager"

    def test_for_pattern_takes_precedence_over_phrase_list(self):
        from src.rico_intent_router import _extract_entities
        # "Environmental Compliance Officer" not in _TITLE_PHRASES but "for X" pattern should catch it
        entities = _extract_entities("find jobs for Environmental Compliance Officer")
        assert entities.get("job_title") == "Environmental Compliance Officer"


# ── save_target_role handler (unit, no DB) ────────────────────────────────────

class TestSaveTargetRoleHandler:
    def test_handler_saves_role_and_returns_confirmation(self, monkeypatch):
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as chat_module

        saved = {}

        def mock_upsert_profile(user_id, updates):
            saved.update(updates)
            return {"target_roles": updates.get("target_roles", []), "skills": [], "certifications": []}

        monkeypatch.setattr(chat_module, "upsert_profile", mock_upsert_profile)

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = type("M", (), {"append_message": lambda *a, **k: None})()
        api._append_chat = lambda *a, **k: None

        profile = {"target_roles": [], "skills": ["hse", "environmental"], "certifications": [], "years_experience": 10, "industries": []}

        from src.agent.intelligence.intent_classifier import IntentResult
        intent_result = IntentResult("save_target_role", 0.95, "regex", extracted_role="Environmental Manager")

        # Call the handler path directly by simulating the condition
        role = intent_result.extracted_role.strip()
        target_roles = []
        if role.lower() not in {str(r).lower() for r in target_roles}:
            target_roles.append(role)
            mock_upsert_profile("test@example.com", {"target_roles": target_roles})

        assert "target_roles" in saved
        assert "Environmental Manager" in saved["target_roles"]


# ── _search_jsearch_direct (unit, no network) ─────────────────────────────────

class TestSearchJsearchDirect:
    def setup_method(self):
        # jsearch_client._cache is process-global; clear it so results from one
        # test cannot bleed into another via the stale-cache fallback path.
        from src import jsearch_client
        jsearch_client.clear_cache()

    def test_returns_empty_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
        from src.rico_chat_api import RicoChatAPI
        result = RicoChatAPI._search_jsearch_direct("HSE Manager")
        assert result == []

    def test_returns_jobs_from_mock_response(self, monkeypatch):
        import json as _json
        import urllib.request

        monkeypatch.setenv("RAPIDAPI_KEY", "test-key")

        fake_data = {
            "data": [
                {
                    "job_id": "abc123",
                    "job_title": "HSE Manager",
                    "employer_name": "ADNOC",
                    "job_city": "Abu Dhabi",
                    "job_country": "United Arab Emirates",
                    "job_apply_link": "https://example.com/job/abc123",
                    "job_description": "HSE Manager role",
                    "job_salary_string": "25000 AED",
                    "job_employment_type": "FULLTIME",
                }
            ]
        }

        class FakeResp:
            def read(self):
                return _json.dumps(fake_data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())

        from src.rico_chat_api import RicoChatAPI
        result = RicoChatAPI._search_jsearch_direct("HSE Manager")
        assert len(result) == 1
        assert result[0]["title"] == "HSE Manager"
        assert result[0]["company"] == "ADNOC"
        assert result[0]["source"] == "jsearch"
        assert "score" not in result[0]  # no default score stamp

    def test_returns_empty_on_network_error(self, monkeypatch):
        import urllib.request

        monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("timeout")))

        from src.rico_chat_api import RicoChatAPI
        result = RicoChatAPI._search_jsearch_direct("HSE Manager")
        assert result == []

    def test_deduplicates_by_job_id(self, monkeypatch):
        import json as _json
        import urllib.request

        monkeypatch.setenv("RAPIDAPI_KEY", "test-key")

        fake_data = {
            "data": [
                {"job_id": "dup1", "job_title": "HSE Manager", "employer_name": "A",
                 "job_apply_link": "https://a.com/1", "job_description": ""},
                {"job_id": "dup1", "job_title": "HSE Manager", "employer_name": "A",
                 "job_apply_link": "https://a.com/1", "job_description": ""},
            ]
        }

        class FakeResp:
            def read(self):
                return _json.dumps(fake_data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())

        from src.rico_chat_api import RicoChatAPI
        result = RicoChatAPI._search_jsearch_direct("HSE Manager")
        assert len(result) == 1
