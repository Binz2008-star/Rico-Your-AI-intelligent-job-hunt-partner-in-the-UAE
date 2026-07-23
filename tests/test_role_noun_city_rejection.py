"""#1336 PR2 — a role name must never be captured as a preferred city.

Production transcript: a profile-less user was asked (in one sentence) to
share both a target role and a preferred UAE city. Only ``preferred_cities``
was armed as the pending field, so the user's natural reply to the role half
("Environmental Manager") was captured whole as a city — because
``sanitize_cities`` had no job-title vocabulary in its rejection bank.

Two real-handler regressions are pinned here (not direct sanitizer-only
assertions — see ``tests/test_city_validation.py`` for those):

1. ``RicoChatAPI._resolve_pending_field`` must reject a role-shaped reply for
   the ``preferred_cities`` pending field and must NOT call ``upsert_profile``.
2. A mixed reply (role + a real city) must save only the real city.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.rico_chat_api import RicoChatAPI


def _make_api(pending_field: str = "preferred_cities") -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = MagicMock()
    ctx = {"_pending_field": pending_field}
    api._get_recent_context = MagicMock(return_value=dict(ctx))
    api._store_recent_context = MagicMock()
    api._append_chat = MagicMock()
    return api


class TestResolvePendingFieldRejectsRoleTitle:
    def test_bare_role_title_not_saved_as_city(self):
        api = _make_api()
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field(
                "user@test.com", "Environmental Manager", profile={}
            )

        assert result is None
        mock_upsert.assert_not_called()
        api._store_recent_context.assert_not_called()

    def test_mixed_role_and_city_saves_only_city(self):
        api = _make_api()
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field(
                "user@test.com", "Environmental Manager, Dubai", profile={}
            )

        assert result is not None
        mock_upsert.assert_called_once_with(
            user_id="user@test.com", updates={"preferred_cities": ["Dubai"]}
        )

    def test_real_city_still_saved(self):
        api = _make_api()
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field("user@test.com", "Dubai", profile={})

        assert result is not None
        mock_upsert.assert_called_once_with(
            user_id="user@test.com", updates={"preferred_cities": ["Dubai"]}
        )
