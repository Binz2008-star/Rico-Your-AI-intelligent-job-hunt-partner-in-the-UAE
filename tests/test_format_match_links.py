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
        # Status is domain-classified; unknown domains get needs_source_verification
        assert out["verification_status"] not in ("lead_needs_verification",)

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
        # No direct apply link — status reflects unverified source
        assert out["verification_status"] in ("lead_needs_verification", "needs_source_verification")
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


class TestApplyOptionsFallback:
    """Raw items reaching _format_match get the apply_options rescue: a trusted
    provider-returned mirror fills alt_link when the primary is login-walled or
    rate-limited and job_google_link was (correctly) blanked."""

    def test_login_walled_primary_gets_trusted_mirror_as_alt(self):
        out = _fmt({
            "title": "Env Manager", "company": "Global Corporation",
            "job_apply_link": "https://www.gulftalent.com/uae/job/1",
            "job_google_link": "https://google.com/search?q=env+manager",
            "apply_options": [
                {"publisher": "LinkedIn", "apply_link": "https://www.linkedin.com/jobs/view/123", "is_direct": False},
            ],
        })
        assert out["verification_status"] == "login_required"
        assert out["apply_url"] == "https://www.gulftalent.com/uae/job/1"
        assert out["alt_link"] == "https://www.linkedin.com/jobs/view/123"

    def test_rate_limited_primary_without_trusted_mirror_stays_unavailable(self):
        # BUG-03 invariant intact: no trustworthy mirror → alt_link stays empty.
        out = _fmt({
            "title": "Env Manager", "company": "Compass",
            "job_apply_link": "https://ae.trabajo.org/job-333",
            "job_google_link": "https://google.com/search?q=jobs",
            "apply_options": [
                {"publisher": "Jobrapido", "apply_link": "https://ae.jobrapido.com/jobpr/9", "is_direct": False},
                {"publisher": "Google", "apply_link": "https://google.com/search?q=jobs2", "is_direct": False},
            ],
        })
        assert out["verification_status"] == "rate_limited"
        assert out["alt_link"] == ""

    def test_existing_real_alt_link_not_overridden(self):
        out = _fmt({
            "title": "Eng", "company": "AESG",
            "job_apply_link": "https://www.gulftalent.com/uae/job/1",
            "job_google_link": "https://naukrigulf.com/job/999",
            "apply_options": [
                {"publisher": "LinkedIn", "apply_link": "https://www.linkedin.com/jobs/view/123", "is_direct": False},
            ],
        })
        # Rescue only fills an EMPTY alt_link — an existing real one is kept.
        assert out["alt_link"] == "https://naukrigulf.com/job/999"

    def test_google_primary_rescued_by_direct_mirror(self):
        out = _fmt({
            "title": "Eng", "company": "AESG",
            "job_apply_link": "https://google.com/search?q=aesg+eng",
            "apply_options": [
                {"publisher": "Employer", "apply_link": "https://careers.aesg.com/apply/7", "is_direct": True},
            ],
        })
        assert out["verification_status"] == "google_intermediary"
        assert out["apply_url"] == ""
        assert out["alt_link"] == "https://careers.aesg.com/apply/7"
