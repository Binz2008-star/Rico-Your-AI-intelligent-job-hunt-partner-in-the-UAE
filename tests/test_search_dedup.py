"""Tests for src.services.search_dedup.dedupe_job_matches and the provenance
fields it feeds into RicoChatAPI._format_match.

Deduplication uses the SAME canonical identity as the rest of the pipeline
(src.applications.get_job_id): link URL, or title|company|location when no link.
The tests assert both the collapse behaviour and the truthful provenance
annotations (never fabricated, order-preserving, fail-open on unknown records).
"""
from src.services.search_dedup import dedupe_job_matches
from src.rico_chat_api import RicoChatAPI


class TestDedupeJobMatches:
    def test_same_link_collapses_to_one(self):
        matches = [
            {"title": "Data Engineer", "company": "Acme", "location": "Dubai",
             "link": "https://careers.acme.com/job/1", "source": "jsearch"},
            {"title": "Data Engineer", "company": "Acme", "location": "Dubai",
             "link": "https://careers.acme.com/job/1", "source": "jooble"},
        ]
        out = dedupe_job_matches(matches)
        assert len(out) == 1
        assert out[0]["duplicate_count"] == 2
        # Provenance from both providers is preserved, first-seen first.
        assert out[0]["sources"] == ["jsearch", "jooble"]

    def test_first_seen_wins_position_and_fields(self):
        matches = [
            {"title": "PM", "company": "Acme", "location": "Dubai",
             "link": "https://x/1", "source": "jooble", "score": 71},
            {"title": "Analyst", "company": "Beta", "location": "Abu Dhabi",
             "link": "https://x/2", "source": "jsearch", "score": 40},
            {"title": "PM", "company": "Acme", "location": "Dubai",
             "link": "https://x/1", "source": "adzuna", "score": 99},
        ]
        out = dedupe_job_matches(matches)
        assert [m["title"] for m in out] == ["PM", "Analyst"]
        # First-seen record keeps its own score/link; a later duplicate never
        # overwrites the surviving record's fields.
        assert out[0]["score"] == 71
        assert out[0]["link"] == "https://x/1"
        assert out[0]["sources"] == ["jooble", "adzuna"]

    def test_no_link_dedupes_on_title_company_location(self):
        # get_job_id falls back to title|company|location when there is no link,
        # so two linkless copies of the same posting still collapse.
        matches = [
            {"title": "Nurse", "company": "Clinic", "location": "Sharjah", "source": "jooble"},
            {"title": "Nurse", "company": "Clinic", "location": "Sharjah", "source": "adzuna"},
        ]
        out = dedupe_job_matches(matches)
        assert len(out) == 1
        assert out[0]["duplicate_count"] == 2

    def test_distinct_jobs_are_not_merged(self):
        matches = [
            {"title": "PM", "company": "Acme", "location": "Dubai", "link": "https://x/1", "source": "jsearch"},
            {"title": "PM", "company": "Beta", "location": "Dubai", "link": "https://x/2", "source": "jsearch"},
        ]
        out = dedupe_job_matches(matches)
        assert len(out) == 2

    def test_single_source_gets_singleton_provenance(self):
        out = dedupe_job_matches(
            [{"title": "PM", "company": "Acme", "location": "Dubai",
              "link": "https://x/1", "source": "jsearch"}]
        )
        assert out[0]["sources"] == ["jsearch"]
        # duplicate_count of 1 is set internally but is not surfaced as a badge.
        assert out[0]["duplicate_count"] == 1

    def test_non_dict_and_unknown_records_pass_through(self):
        # Fail-open: never drop something we cannot prove is a duplicate.
        matches = ["not a dict", {"foo": "bar"}]  # second has no id-bearing fields
        out = dedupe_job_matches(matches)
        assert len(out) == 2

    def test_non_list_returned_untouched(self):
        assert dedupe_job_matches(None) is None
        assert dedupe_job_matches("nope") == "nope"

    def test_unknown_provider_not_fabricated(self):
        matches = [
            {"title": "PM", "company": "Acme", "location": "Dubai", "link": "https://x/1"},
            {"title": "PM", "company": "Acme", "location": "Dubai", "link": "https://x/1"},
        ]
        out = dedupe_job_matches(matches)
        assert len(out) == 1
        # No source label anywhere → provenance stays empty rather than invented.
        assert out[0]["sources"] == []
        assert out[0]["duplicate_count"] == 2


class TestFormatMatchProvenance:
    def test_sources_surfaced_when_present(self):
        out = RicoChatAPI._format_match(
            {"title": "Eng", "company": "AESG", "apply_link": "https://careers.aesg.com/1",
             "sources": ["jsearch", "jooble"], "duplicate_count": 2},
            None,
        )
        assert out["sources"] == ["jsearch", "jooble"]
        assert out["duplicate_count"] == 2

    def test_sources_fallback_to_single_source(self):
        out = RicoChatAPI._format_match(
            {"title": "Eng", "company": "AESG", "apply_link": "https://careers.aesg.com/1",
             "source": "adzuna"},
            None,
        )
        assert out["sources"] == ["adzuna"]
        # Not a duplicate → no duplicate_count badge.
        assert "duplicate_count" not in out

    def test_no_source_means_no_provenance_key(self):
        out = RicoChatAPI._format_match(
            {"title": "Eng", "company": "AESG", "apply_link": "https://careers.aesg.com/1"},
            None,
        )
        assert "sources" not in out
        assert "duplicate_count" not in out
