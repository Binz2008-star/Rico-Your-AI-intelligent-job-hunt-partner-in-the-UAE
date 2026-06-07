"""Tests for RicoChatAPI._effective_target_roles — placeholder role filtering."""
import pytest

from src.rico_chat_api import RicoChatAPI


class TestEffectiveTargetRoles:
    """_effective_target_roles must strip generic/placeholder values."""

    @pytest.mark.parametrize("placeholder", [
        "Any",
        "any",
        "ANY",
        "All",
        "all",
        "Any Role",
        "any role",
        "All Roles",
        "all roles",
        "Open",
        "open",
        "Open to Any",
        "open to any",
        "Open to All",
        "open to all",
        "Any Position",
        "any position",
        "Any Job",
        "any job",
        "Any Jobs",
        "any jobs",
        "Not Specified",
        "not specified",
        "TBD",
        "tbd",
        "N/A",
        "n/a",
    ])
    def test_placeholder_is_filtered_out(self, placeholder: str) -> None:
        result = RicoChatAPI._effective_target_roles([placeholder])
        assert result == [], (
            f"Expected _effective_target_roles([{placeholder!r}]) to return [] "
            "— placeholder role values must not drive a job search"
        )

    @pytest.mark.parametrize("real_role", [
        "HSE Manager",
        "Software Engineer",
        "Business Consultant",
        "Data Scientist",
        "Environmental Compliance Officer",
        "Chief Financial Officer",
        "Senior Backend Developer",
        "Architect",
        "QA Engineer",
        "Pilot",
    ])
    def test_real_role_is_kept(self, real_role: str) -> None:
        result = RicoChatAPI._effective_target_roles([real_role])
        assert result == [real_role], (
            f"Expected real role {real_role!r} to be preserved"
        )

    def test_mixed_list_filters_only_placeholders(self) -> None:
        roles = ["HSE Manager", "Any", "Business Consultant", "all"]
        result = RicoChatAPI._effective_target_roles(roles)
        assert result == ["HSE Manager", "Business Consultant"]

    def test_empty_list_returns_empty(self) -> None:
        assert RicoChatAPI._effective_target_roles([]) == []

    def test_all_placeholders_returns_empty(self) -> None:
        assert RicoChatAPI._effective_target_roles(["Any", "All", "TBD"]) == []

    def test_non_string_entries_are_dropped(self) -> None:
        result = RicoChatAPI._effective_target_roles([None, 123, "HSE Manager"])
        assert result == ["HSE Manager"]

    def test_whitespace_stripped_before_comparison(self) -> None:
        result = RicoChatAPI._effective_target_roles(["  any  ", " All "])
        assert result == []
