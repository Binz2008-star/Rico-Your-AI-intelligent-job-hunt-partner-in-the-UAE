"""Tests for profile preferred_cities write-boundary protection (#1336).

Verifies that:
1. ["ابحث عن وظيفه"] does not overwrite an existing valid city.
2. ["دبي", "ابحث عن وظيفة"] stores only ["دبي"].
3. ["دورلي على شغل"] is rejected (omitted from update).
4. Valid Arabic UAE cities remain accepted.
5. An intentional empty list still clears the preference.
6. Both require_db=False and require_db=True paths receive the same sanitized update.
7. db.upsert_profile receives the sanitized preferred_cities (require_db=True).
8. Invalid-only input omits preferred_cities from both Neon and JSON mirror.
9. Non-list input cannot reach either storage path.
10. Sanitizer exception cannot reach either storage path.
11. The exact production value is neutralized on read.
12. _handle_profile_field_update rejects non-city and does not call upsert_profile.
13. _handle_profile_field_update accepts valid city and produces sanitized update.
"""
from unittest.mock import patch, MagicMock, ANY


class TestWriteBoundarySanitization:
    """upsert_profile must sanitize preferred_cities before either storage path."""

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_corrupted_arabic_does_not_overwrite_existing(self, mock_mem, mock_db):
        """["ابحث عن وظيفه"] must be omitted, not replace existing cities."""
        mock_db.return_value = None  # no DB → JSON fallback only
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": ["ابحث عن وظيفه"]})

        # preferred_cities must NOT be in the filtered updates
        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_mixed_valid_invalid_stores_only_valid(self, mock_mem, mock_db):
        """["دبي", "ابحث عن وظيفة"] stores only ["دبي"]."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": ["دبي", "ابحث عن وظيفة"]})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert updates.get("preferred_cities") == ["دبي"]

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_all_invalid_omitted(self, mock_mem, mock_db):
        """["دورلي على شغل"] is omitted entirely."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": ["دورلي على شغل"]})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_valid_arabic_cities_accepted(self, mock_mem, mock_db):
        """Valid Arabic UAE cities remain accepted."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": ["دبي", "أبوظبي", "الشارقة"]})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert updates.get("preferred_cities") == ["دبي", "أبوظبي", "الشارقة"]

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_empty_list_clears_preference(self, mock_mem, mock_db):
        """An intentional empty list still clears the preference."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": []})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert updates.get("preferred_cities") == []

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_non_list_string_omitted(self, mock_mem, mock_db):
        """A string value must be omitted, not stored."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": "دبي"})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_non_list_dict_omitted(self, mock_mem, mock_db):
        """A dict value must be omitted, not stored."""
        mock_db.return_value = None
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        from src.repositories.profile_repo import upsert_profile

        upsert_profile("user@test.com", {"preferred_cities": {"city": "دبي"}})

        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.repositories.profile_repo._db_transaction")
    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_require_db_true_receives_sanitized_in_neon(self, mock_mem, mock_db, mock_txn):
        """require_db=True: db.upsert_profile receives sanitized preferred_cities."""
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.available = True
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_txn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_txn.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_inst.get_user_bundle.return_value = {"id": 1, "email": "user@test.com"}

        from src.repositories.profile_repo import upsert_profile

        upsert_profile(
            "user@test.com",
            {"preferred_cities": ["دبي", "ابحث عن وظيفه"]},
            require_db=True,
        )

        # Verify db.upsert_profile received only ["دبي"]
        upsert_calls = mock_db_inst.upsert_profile.call_args_list
        assert len(upsert_calls) > 0
        profile_data = upsert_calls[0].args[1] if len(upsert_calls[0].args) > 1 else upsert_calls[0].kwargs.get("profile_data", {})
        assert profile_data.get("preferred_cities") == ["دبي"]

        # Also verify JSON mirror received sanitized
        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert updates.get("preferred_cities") == ["دبي"]

    @patch("src.repositories.profile_repo._db_transaction")
    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_require_db_true_invalid_omitted_from_both(self, mock_mem, mock_db, mock_txn):
        """Invalid-only input omits preferred_cities from both Neon and JSON mirror."""
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.available = True
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_txn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_txn.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_inst.get_user_bundle.return_value = {"id": 1, "email": "user@test.com"}

        from src.repositories.profile_repo import upsert_profile

        upsert_profile(
            "user@test.com",
            {"preferred_cities": ["ابحث عن وظيفه"]},
            require_db=True,
        )

        # Verify Neon did NOT receive preferred_cities
        upsert_calls = mock_db_inst.upsert_profile.call_args_list
        for call in upsert_calls:
            profile_data = call.args[1] if len(call.args) > 1 else call.kwargs.get("profile_data", {})
            assert "preferred_cities" not in profile_data

        # Verify JSON mirror did NOT receive preferred_cities
        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.repositories.profile_repo._db_transaction")
    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_require_db_true_non_list_omitted_from_both(self, mock_mem, mock_db, mock_txn):
        """Non-list input cannot reach either Neon or JSON mirror."""
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.available = True
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_txn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_txn.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_inst.get_user_bundle.return_value = {"id": 1, "email": "user@test.com"}

        from src.repositories.profile_repo import upsert_profile

        upsert_profile(
            "user@test.com",
            {"preferred_cities": "دبي"},
            require_db=True,
        )

        # Verify Neon did NOT receive preferred_cities
        upsert_calls = mock_db_inst.upsert_profile.call_args_list
        for call in upsert_calls:
            profile_data = call.args[1] if len(call.args) > 1 else call.kwargs.get("profile_data", {})
            assert "preferred_cities" not in profile_data

        # Verify JSON mirror did NOT receive preferred_cities
        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates

    @patch("src.services.city_validation.sanitize_cities")
    @patch("src.repositories.profile_repo._db_transaction")
    @patch("src.repositories.profile_repo._db")
    @patch("src.repositories.profile_repo._memory")
    def test_sanitizer_exception_omits_from_both(
        self, mock_mem, mock_db, mock_txn, mock_sanitize
    ):
        """Sanitizer exception => preferred_cities omitted from both paths."""
        mock_sanitize.side_effect = RuntimeError("sanitizer crashed")
        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_db_inst.available = True
        mock_store = MagicMock()
        mock_mem.return_value = mock_store
        mock_store.upsert_profile_from_dict.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_txn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_txn.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_inst.get_user_bundle.return_value = {"id": 1, "email": "user@test.com"}

        from src.repositories.profile_repo import upsert_profile

        upsert_profile(
            "user@test.com",
            {"preferred_cities": ["دبي"]},
            require_db=True,
        )

        # Verify Neon did NOT receive preferred_cities
        upsert_calls = mock_db_inst.upsert_profile.call_args_list
        for call in upsert_calls:
            profile_data = call.args[1] if len(call.args) > 1 else call.kwargs.get("profile_data", {})
            assert "preferred_cities" not in profile_data

        # Verify JSON mirror did NOT receive preferred_cities
        call_args = mock_store.upsert_profile_from_dict.call_args
        updates = call_args.kwargs.get("updates", {})
        assert "preferred_cities" not in updates


class TestReadTimeSanitization:
    """The exact production value must be neutralized on read."""

    def test_production_value_neutralized_on_read(self):
        """_sanitize_cities_safe strips the corrupted production value."""
        from src.repositories.profile_repo import _sanitize_cities_safe

        # The two confirmed corrupted production values
        result = _sanitize_cities_safe(["ابحث عن وظيفه"])
        assert result == []

        result = _sanitize_cities_safe(["استثني وظائف لينكد"])
        assert result == []

    def test_valid_cities_pass_read_sanitization(self):
        """Valid cities pass through read-time sanitization unchanged."""
        from src.repositories.profile_repo import _sanitize_cities_safe

        result = _sanitize_cities_safe(["دبي", "أبوظبي"])
        assert result == ["دبي", "أبوظبي"]


class TestChatApiFieldUpdateSanitization:
    """_handle_profile_field_update must sanitize preferred_cities via real call."""

    def test_invalid_city_returns_clarification_no_upsert(self):
        """Invalid city returns a clarification and does NOT call upsert_profile."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._UAE_CITIES = {"dubai": "dubai", "abu dhabi": "abu dhabi",
                           "دبي": "دبي", "أبوظبي": "أبوظبي"}

        profile = MagicMock()
        profile.preferred_cities = []

        with patch.object(api, "_is_arabic_text", return_value=False), \
             patch.object(api, "_as_list", return_value=[]), \
             patch.object(api, "_profile_value", return_value=[]), \
             patch.object(api, "_append_chat") as mock_append, \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_profile_field_update("user@test.com", profile, "I'm now based in search for jobs")

        assert result["type"] == "clarification"
        mock_upsert.assert_not_called()
        mock_append.assert_called_once()

    def test_valid_city_produces_sanitized_update(self):
        """Valid city produces the expected sanitized update via upsert_profile."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._UAE_CITIES = {"dubai": "dubai", "abu dhabi": "abu dhabi",
                           "دبي": "دبي", "أبوظبي": "أبوظبي"}

        profile = MagicMock()
        profile.preferred_cities = []

        with patch.object(api, "_is_arabic_text", return_value=False), \
             patch.object(api, "_as_list", return_value=[]), \
             patch.object(api, "_profile_value", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_profile_field_update("user@test.com", profile, "I'm now based in Dubai")

        mock_upsert.assert_called_once()
        updates = mock_upsert.call_args.kwargs.get("updates", {})
        assert "preferred_cities" in updates
        assert updates["preferred_cities"] == ["Dubai"]
