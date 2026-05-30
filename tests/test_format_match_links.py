"""Tests for _format_match link preservation and the apply-fallback chain.

Requirement: the apply fallback uses alt_link when the primary apply link is
unavailable, and both apply_url and source_url/alt_link are preserved in the
match payload sent to the frontend.
"""
from src.rico_chat_api import RicoChatAPI


def _fmt(job):
    return RicoChatAPI._format_match(job, None)


class TestFormatMatchLinks:
    def test_apply_link_becomes_apply_url(self):
        out = _fmt({"title": "Eng", "company": "AESG", "job_apply_link": "https://a/apply"})
        assert out["apply_url"] == "https://a/apply"
        assert out["verification_status"] == "live"

    def test_google_link_becomes_alt_link(self):
        out = _fmt({"title": "Eng", "company": "AESG", "job_google_link": "https://g/x"})
        assert out["alt_link"] == "https://g/x"

    def test_alt_link_preserved_alongside_apply(self):
        out = _fmt({
            "title": "Eng", "company": "AESG",
            "job_apply_link": "https://a/apply",
            "job_google_link": "https://g/x",
        })
        assert out["apply_url"] == "https://a/apply"
        assert out["alt_link"] == "https://g/x"

    def test_no_apply_link_marks_lead(self):
        out = _fmt({"title": "Eng", "company": "AESG", "job_google_link": "https://g/x"})
        assert out["apply_url"] == ""
        assert out["verification_status"] == "lead_needs_verification"
        # alt_link is still available so the UI can offer it as a fallback.
        assert out["alt_link"] == "https://g/x"

    def test_normalized_alt_link_field_is_read(self):
        # When the job comes from jsearch_client.normalize_item it uses alt_link/apply_link.
        out = _fmt({
            "title": "Eng", "company": "AESG",
            "apply_link": "https://a/apply", "alt_link": "https://g/x",
        })
        assert out["apply_url"] == "https://a/apply"
        assert out["alt_link"] == "https://g/x"

    def test_source_url_falls_back_to_alt_then_apply(self):
        # No explicit source_url → source_url should fall back to alt_link.
        out = _fmt({
            "title": "Eng", "company": "AESG",
            "job_apply_link": "https://a/apply", "job_google_link": "https://g/x",
        })
        assert out["source_url"] == "https://g/x"
