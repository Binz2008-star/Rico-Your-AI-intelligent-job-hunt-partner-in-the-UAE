"""Tests for JSearch UAE-wide query construction.

Verifies that a UAE-wide search (empty location) does NOT append "UAE"
to the JSearch query string — the country=ae parameter already handles
geographic scoping, and appending "UAE" degrades full-text matching.

Bug: "Environmental Manager in Dubai" returned 5 results, but
"Environmental Manager in the UAE" returned zero because the query
became "Environmental Manager UAE" instead of "Environmental Manager".
"""
from unittest.mock import patch, MagicMock


class TestJSearchQueryConstruction:
    """_jsearch_search must build correct queries for UAE-wide vs city-scoped."""

    @patch("src.jsearch_client.search")
    def test_uae_wide_query_is_role_only(self, mock_search):
        """Empty location => query is just the role, not 'role UAE'."""
        from src.job_providers import _jsearch_search

        mock_result = MagicMock()
        mock_result.cancelled = False
        mock_search.return_value = mock_result

        _jsearch_search("Environmental Manager", "", "ae")

        call_args = mock_search.call_args
        query = call_args[0][0] if call_args[0] else call_args.kwargs.get("query", "")
        assert query == "Environmental Manager"
        assert "UAE" not in query

    @patch("src.jsearch_client.search")
    def test_city_scoped_query_includes_city(self, mock_search):
        """Non-empty location => query includes the city."""
        from src.job_providers import _jsearch_search

        mock_result = MagicMock()
        mock_result.cancelled = False
        mock_search.return_value = mock_result

        _jsearch_search("Environmental Manager", "Dubai", "ae")

        call_args = mock_search.call_args
        query = call_args[0][0] if call_args[0] else call_args.kwargs.get("query", "")
        assert query == "Environmental Manager Dubai"

    @patch("src.jsearch_client.search")
    def test_uae_wide_query_no_redundant_suffix(self, mock_search):
        """UAE-wide query must not contain 'UAE' as a keyword."""
        from src.job_providers import _jsearch_search

        mock_result = MagicMock()
        mock_result.cancelled = False
        mock_search.return_value = mock_result

        _jsearch_search("Software Engineer", "", "ae")

        call_args = mock_search.call_args
        query = call_args[0][0] if call_args[0] else call_args.kwargs.get("query", "")
        assert query == "Software Engineer"
        assert "UAE" not in query.upper().split()

    @patch("src.jsearch_client.search")
    def test_country_param_passed_through(self, mock_search):
        """country=ae must be passed to jsearch_client.search."""
        from src.job_providers import _jsearch_search

        mock_result = MagicMock()
        mock_result.cancelled = False
        mock_search.return_value = mock_result

        _jsearch_search("Environmental Manager", "", "ae")

        call_args = mock_search.call_args
        country = call_args.kwargs.get("country", "")
        assert country == "ae"
