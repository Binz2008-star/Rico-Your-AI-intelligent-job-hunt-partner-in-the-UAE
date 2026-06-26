"""
Regression: confirmation/acknowledgement words must never be saved as a city.

Reproduction (production): Rico asked for the user's preferred city (pending
field = preferred_cities). The user replied "تمام" (ok/fine). "تمام" was not in
_CITY_REJECT_WORDS, so it was persisted as preferred_cities=["تمام"] and then
rendered as a city line in every generated CV draft.

After the fix, "تمام" (and other AR/EN confirmations) are rejected: the pending
field resolver returns None without writing the profile, so the message routes
normally instead of contaminating profile data.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


def _make_api(pending_field: str = "preferred_cities"):
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._append_chat = MagicMock()
    api._get_recent_context = MagicMock(
        return_value={"_pending_field": pending_field, "_pending_cv_generate": True}
    )
    api._store_recent_context = MagicMock()
    api._get_last_assistant_message = MagicMock(return_value="أي مدينة تفضل؟")
    api._resolve_profile = MagicMock(return_value={"user_id": "u1"})
    api._handle_cv_generate_from_profile = MagicMock(
        return_value={"type": "cv_draft", "message": "draft"}
    )
    return api


_CONFIRMATION_WORDS = ["تمام", "اوك", "حسناً", "ايوه", "اكيد", "yes", "ok", "thanks", "no"]


class TestCityRejectConfirmationWords:
    @pytest.mark.parametrize("word", _CONFIRMATION_WORDS)
    def test_confirmation_not_saved_as_city(self, word):
        api = _make_api()
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field("u1", word, {"user_id": "u1"})
        assert result is None, f"{word!r} should not resolve as a city"
        mock_upsert.assert_not_called()

    def test_tamam_is_in_reject_set(self):
        assert "تمام" in RicoChatAPI._CITY_REJECT_WORDS

    def test_real_city_still_saved(self):
        api = _make_api()
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field("u1", "دبي", {"user_id": "u1"})
        # A genuine city is persisted and continues the CV-generation flow.
        mock_upsert.assert_called_once()
        saved = mock_upsert.call_args.kwargs.get("updates", {})
        assert saved.get("preferred_cities") == ["دبي"]
        assert result is not None
