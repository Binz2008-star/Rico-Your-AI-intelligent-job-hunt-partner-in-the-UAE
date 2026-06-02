"""Unit tests for multi-source get_jobs (Indeed + Bayt) dedupe and normalization."""
from unittest.mock import patch

import pandas as pd

from src import job_sources


def _df(rows):
    return pd.DataFrame(rows)


class TestGetJobsMultiSource:
    def test_queries_both_indeed_and_bayt(self):
        calls = []

        def fake_scrape(**kwargs):
            calls.append(kwargs["site_name"][0])
            return _df([])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            job_sources.get_jobs(target_roles=["HSE Manager"])

        assert "indeed" in calls
        assert "bayt" in calls

    def test_dedupe_across_sources_by_link(self):
        shared = {"title": "HSE Manager", "company": "ACME", "location": "Dubai",
                  "job_url": "https://x.com/job/1", "description": "d"}

        def fake_scrape(**kwargs):
            return _df([shared])  # both sources return the same job_url

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            jobs = job_sources.get_jobs(target_roles=["HSE Manager"])

        links = [j["link"] for j in jobs]
        assert links.count("https://x.com/job/1") == 1  # deduped

    def test_source_label_is_set_per_source(self):
        def fake_scrape(**kwargs):
            site = kwargs["site_name"][0]
            return _df([{
                "title": f"{site} role", "company": "C", "location": "Dubai",
                "job_url": f"https://{site}.com/1", "description": "d",
            }])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            jobs = job_sources.get_jobs(target_roles=["HSE Manager"])

        sources = {j["source"] for j in jobs}
        assert sources == {"indeed", "bayt"}

    def test_profile_roles_used_as_queries(self):
        seen_terms = []

        def fake_scrape(**kwargs):
            seen_terms.append(kwargs["search_term"])
            return _df([])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            job_sources.get_jobs(target_roles=["Marketing Manager"])

        assert "Marketing Manager" in seen_terms
        # Hardcoded HSE defaults must NOT be used when a profile role is supplied
        assert "ESG Manager" not in seen_terms

    def test_falls_back_to_hardcoded_queries_without_roles(self):
        seen_terms = []

        def fake_scrape(**kwargs):
            seen_terms.append(kwargs["search_term"])
            return _df([])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            job_sources.get_jobs()

        assert set(seen_terms) >= set(job_sources._QUERIES)

    def test_uae_city_used_as_location(self):
        seen_locations = []

        def fake_scrape(**kwargs):
            seen_locations.append(kwargs["location"])
            return _df([])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            job_sources.get_jobs(target_roles=["HSE Manager"], preferred_cities=["Dubai"])

        assert all(loc == "Dubai" for loc in seen_locations)

    def test_non_uae_city_falls_back_to_country(self):
        seen_locations = []

        def fake_scrape(**kwargs):
            seen_locations.append(kwargs["location"])
            return _df([])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            job_sources.get_jobs(target_roles=["HSE Manager"], preferred_cities=["London"])

        assert all(loc == "United Arab Emirates" for loc in seen_locations)

    def test_one_source_failure_does_not_abort_other(self):
        def fake_scrape(**kwargs):
            if kwargs["site_name"][0] == "indeed":
                raise RuntimeError("indeed blocked")
            return _df([{
                "title": "Bayt role", "company": "C", "location": "Dubai",
                "job_url": "https://bayt.com/1", "description": "d",
            }])

        with patch.object(job_sources, "scrape_jobs", side_effect=fake_scrape), \
             patch.object(job_sources.time, "sleep", lambda *_: None):
            jobs = job_sources.get_jobs(target_roles=["HSE Manager"])

        # Bayt results still returned despite Indeed failing
        assert any(j["source"] == "bayt" for j in jobs)
