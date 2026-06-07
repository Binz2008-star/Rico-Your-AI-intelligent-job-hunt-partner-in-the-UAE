"""
Tests for src/job_sources/jsearch_adapter.py - JSearch adapter wrapper.

Phase 1: Tests verify that the adapter preserves existing JSearch behavior.
No runtime behavior change - wrapper mode only.

Version: 2.1.0 (Phase 1)
"""

import pytest
from src.job_sources.jsearch_adapter import JSearchAdapter
from src.job_sources.normalized import NormalizedJob


@pytest.fixture
def adapter():
    """Create JSearchAdapter instance for testing."""
    return JSearchAdapter()


@pytest.fixture
def mock_raw_job():
    """Mock raw JSearch job data matching existing structure."""
    return {
        "job_id": "12345",
        "job_title": "HSE Manager",
        "employer_name": "Test Company",
        "job_city": "Dubai",
        "job_country": "UAE",
        "job_apply_link": "https://example.com/apply",
        "job_google_link": "https://google.com/search?q=test",
        "job_description": "Test job description",
        "job_employment_type": "Full-time",
        "job_salary_string": "AED 15000",
        "job_posted_at_datetime_utc": "2024-01-01T00:00:00Z",
    }


class TestJSearchAdapterNormalization:
    """Test that adapter normalization preserves existing JSearch behavior."""

    def test_normalize_preserves_title(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.title == "HSE Manager"

    def test_normalize_preserves_company(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.company == "Test Company"

    def test_normalize_preserves_job_id(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.provider_job_id == "12345"

    def test_normalize_handles_missing_job_id(self, adapter):
        job_without_id = {
            "job_title": "Test",
            "employer_name": "Test Co",
            "job_apply_link": "https://example.com/apply",
        }
        normalized = adapter.normalize(job_without_id)
        assert normalized.provider_job_id == ""

    def test_normalize_prefers_apply_link(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.apply_url == "https://example.com/apply"

    def test_normalize_falls_back_to_link(self, adapter):
        job_without_apply = {
            "job_id": "123",
            "job_title": "Test",
            "employer_name": "Test Co",
            "job_google_link": "https://google.com/test",
        }
        normalized = adapter.normalize(job_without_apply)
        assert normalized.apply_url == "https://google.com/test"

    def test_normalize_preserves_source_name(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.source == "jsearch"

    def test_normalize_preserves_description(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.description == "Test job description"

    def test_normalize_preserves_employment_type(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.employment_type == "Full-time"

    def test_normalize_preserves_salary_string(self, adapter, mock_raw_job):
        normalized = adapter.normalize(mock_raw_job)
        assert normalized.salary_string == "AED 15000"


class TestJSearchAdapterValidation:
    """Test that adapter validation uses existing UAE filtering logic."""

    def test_validate_with_apply_url(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="Dubai",
            country="United Arab Emirates",
            apply_url="https://example.com/apply",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.validate(job) is True

    def test_validate_with_source_url_only(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="Dubai",
            country="United Arab Emirates",
            apply_url="https://example.com/apply",
            source_url="https://example.com/job",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.validate(job) is True

    def test_validate_without_urls_raises_validation_error(self, adapter):
        """Pydantic validator should raise ValueError when both URLs are missing."""
        with pytest.raises(ValueError, match="Must provide at least an apply_url or a source_url"):
            NormalizedJob(
                title="Test",
                company="Test Co",
                location="Dubai",
                country="United Arab Emirates",
                apply_url="",
                source_url="",
                provider_job_id="123",
            )

    def test_validate_uae_location(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="Dubai",
            country="United Arab Emirates",
            apply_url="https://example.com/apply",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.validate(job) is True

    def test_validate_non_uae_location(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="London",
            country="United Kingdom",
            apply_url="https://example.com/apply",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.validate(job) is False


class TestJSearchAdapterInterface:
    """Test that adapter implements required interface methods."""

    def test_source_name_property(self, adapter):
        assert adapter.source_name == "jsearch"

    def test_get_apply_url_prefers_apply(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="Dubai",
            country="United Arab Emirates",
            apply_url="https://example.com/apply",
            source_url="https://example.com/job",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.get_apply_url(job) == "https://example.com/apply"

    def test_get_apply_url_falls_back_to_source(self, adapter):
        job = NormalizedJob(
            title="Test",
            company="Test Co",
            location="Dubai",
            country="United Arab Emirates",
            apply_url="https://example.com/apply",
            source_url="https://example.com/job",
            source="jsearch",
            provider_job_id="123",
        )
        assert adapter.get_apply_url(job) == "https://example.com/apply"
