from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.intelligence.intent_classifier import IntentResult
from src.rico_chat_api import RicoChatAPI


USER = "flow-user@example.com"


def _api_with_context() -> tuple[RicoChatAPI, dict]:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    context: dict = {}
    api.memory.get_context.side_effect = lambda _user, key: context if key == "recent_context" else None
    def set_context(_user: str, key: str, value: dict) -> None:
        if key == "recent_context":
            next_value = dict(value)
            context.clear()
            context.update(next_value)
    api.memory.set_context.side_effect = set_context
    return api, context


def _profile() -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Engineer", "Manager"]
    profile.skills = ["HSE", "QHSE", "Environmental Compliance", "Sustainability", "ISO 14001"]
    profile.certifications = ["NEBOSH"]
    profile.industries = ["Environmental"]
    profile.years_experience = 10
    profile.current_role = "HSE Specialist"
    return profile


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.openai_available = False
    agent.deepseek_available = False
    agent.hf_available = False
    agent.provider_available = True
    agent.model = ""
    return agent


def _run(api: RicoChatAPI, message: str, profile: MagicMock, intent: IntentResult | None = None) -> dict:
    patches = [
        patch.object(api, "_resolve_profile", return_value=profile),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
    ]
    if intent is not None:
        patches.append(patch("src.rico_chat_api.classify_intent", return_value=intent))

    with patches[0], patches[1], patches[2], patches[3]:
        if intent is not None:
            with patches[4]:
                return api._handle_active_user(USER, message)
        return api._handle_active_user(USER, message)


def test_store_search_matches_persists_to_db():
    """_store_search_matches_context must write matches to Neon via upsert_matches."""
    api, _ = _api_with_context()
    matches = [
        {"title": "HSE Manager", "company": "Acme", "apply_url": "https://acme.com/apply",
         "source_url": "https://acme.com/src", "verification_status": "live"},
    ]

    with patch(
        "src.repositories.user_job_context_repo.upsert_matches"
    ) as mock_upsert:
        api._store_search_matches_context(USER, matches)

    mock_upsert.assert_called_once_with(USER, matches)


def test_open_apply_link_finds_url_from_db():
    """open_apply_link must return the apply URL retrieved from user_job_context when memory/apps are empty."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )
    db_row = {
        "title": "HSE Manager",
        "company": "Acme",
        "apply_url": "https://acme.com/apply",
        "source_url": "https://acme.com/src",
        "verification_status": "live",
        "searched_at": None,
    }

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=db_row,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "https://acme.com/apply" in result["message"]
    assert result.get("apply_url") == "https://acme.com/apply"


def test_open_apply_link_falls_back_to_source_url():
    """When apply_url is absent but source_url exists in DB, Rico returns the source listing link."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )
    db_row = {
        "title": "HSE Manager",
        "company": "Acme",
        "apply_url": "",
        "source_url": "https://acme.com/src",
        "verification_status": "lead_needs_verification",
        "searched_at": None,
    }

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=db_row,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "https://acme.com/src" in result["message"]
    assert "official listing" in result["message"].lower()


def test_open_apply_link_checks_db_after_url_less_application_record():
    """A saved Application Flow record without URL must not block the persisted DB lookup."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )
    db_row = {
        "title": "HSE Manager",
        "company": "Acme",
        "apply_url": "https://acme.com/apply",
        "source_url": "https://acme.com/src",
        "verification_status": "live",
        "searched_at": None,
    }

    with (
        patch(
            "src.repositories.applications_repo.get_all",
            return_value=[{"title": "HSE Manager", "company": "Acme", "link": ""}],
        ),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=db_row,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "https://acme.com/apply" in result["message"]
    assert result.get("apply_url") == "https://acme.com/apply"


def test_open_apply_link_does_not_tell_user_to_search_manually():
    """The old error 'Search for the role on the company website or LinkedIn' must be gone."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=None,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "search for the role on the company website" not in result["message"].lower()
    assert "linkedin" not in result["message"].lower()
    assert "needs source verification" in result["message"].lower()


def test_user_job_context_lookup_does_not_match_single_word_title_substring():
    """The DB lookup should not match "Manager" to a stored "General Manager" row."""
    from src.repositories import user_job_context_repo

    class Cursor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple]] = []

        def execute(self, sql: str, params: tuple) -> None:
            self.calls.append((sql, params))

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Conn:
        def __init__(self) -> None:
            self.cursor_obj = Cursor()

        def cursor(self):
            return self.cursor_obj

        def close(self) -> None:
            pass

    conn = Conn()

    with patch("src.db.get_db_connection", return_value=conn):
        row = user_job_context_repo.find_by_title_company(USER, "Manager", "Acme")

    assert row is None
    assert len(conn.cursor_obj.calls) == 1
    assert "lower(title) = lower(%s)" in conn.cursor_obj.calls[0][0]


def test_user_job_context_upsert_skips_missing_title_or_company_and_source_only_links():
    """Rows without identifiers are skipped and identical apply/source URLs persist as source only."""
    from src.repositories import user_job_context_repo

    class Cursor:
        def __init__(self) -> None:
            self.params: list[tuple] = []

        def execute(self, _sql: str, params: tuple) -> None:
            self.params.append(params)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Conn:
        def __init__(self) -> None:
            self.cursor_obj = Cursor()

        def cursor(self):
            return self.cursor_obj

        def commit(self) -> None:
            pass

        def close(self) -> None:
            pass

    conn = Conn()
    matches = [
        {"title": "", "company": "Acme", "apply_url": "https://skip.example/apply"},
        {"title": "HSE Manager", "company": "", "apply_url": "https://skip.example/apply"},
        {
            "title": "HSE Manager",
            "company": "Acme",
            "apply_url": "https://google.example/source",
            "source_url": "https://google.example/source",
        },
    ]

    with patch("src.db.get_db_connection", return_value=conn):
        user_job_context_repo.upsert_matches(USER, matches)

    assert len(conn.cursor_obj.params) == 1
    assert conn.cursor_obj.params[0][4] == ""
    assert conn.cursor_obj.params[0][5] == "https://google.example/source"


def test_saved_target_role_search_mentions_saved_role():
    """_build_role_search_message with from_saved_profile=True must include the transparency prefix."""
    api, _ = _api_with_context()
    message = api._build_role_search_message(
        normalized_role="HSE Manager",
        city_text=" in the UAE",
        basis_text=" using your CV profile",
        top_matches=[],
        role_intelligence_data=None,
        from_saved_profile=True,
    )

    assert message.startswith("Searching based on your saved target role: HSE Manager.")
