"""
JSearch Source Adapter

Wraps existing JSearch functionality behind the unified source interface.
Phase 1: No behavior change - preserves existing JSearch client usage.

Version: 2.1.0 (Phase 1)
"""

import logging
from typing import List, Dict, Any, Optional
from .base import BaseJobSourceAdapter
from .normalized import NormalizedJob

logger = logging.getLogger("job_sources.jsearch_adapter")


class JSearchAdapter(BaseJobSourceAdapter):
    """Wraps existing JSearch functionality behind the unified source interface.

    Phase 1: This adapter wraps the existing jsearch_client module without changing
    any runtime behavior. The existing fetch_jsearch_jobs() function in src/job_sources.py
    continues to work unchanged.
    """

    def __init__(self):
        """Initialize adapter. No client injection needed - uses module-level functions."""
        logger.info("JSearchAdapter initialized (Phase 1: wrapper mode, no behavior change)")

    @property
    def source_name(self) -> str:
        return "jsearch"

    def search(self, query: str, country: str = "ae") -> List[Dict[str, Any]]:
        """Executes raw data fetch using existing jsearch_client.search().

        Phase 1: Wraps existing jsearch_client.search() with exact same signature.
        Current production signature: search(query: str, *, use_cache: bool = True, country: str = "ae") -> FetchResult
        """
        from src import jsearch_client

        logger.debug("JSearchAdapter.search query=%r country=%s", query, country)
        fetch_result = jsearch_client.search(query, country=country)

        if fetch_result.error:
            logger.warning("JSearchAdapter.search error=%s", fetch_result.error)
            return []

        logger.info("JSearchAdapter.search results=%d cache_hit=%s",
                   len(fetch_result.items), fetch_result.cache_hit)
        return fetch_result.items

    def normalize(self, raw_job: Dict[str, Any]) -> NormalizedJob:
        """Transforms raw JSearch dict into NormalizedJob using existing normalization logic.

        Phase 1: Maps existing jsearch_client.normalize_item() output to NormalizedJob schema.
        The jsearch_client.normalize_item() already returns a dict with the correct structure.
        """
        from src import jsearch_client

        # Use existing normalization logic
        normalized_dict = jsearch_client.normalize_item(raw_job)

        return NormalizedJob(
            title=normalized_dict.get("title", ""),
            company=normalized_dict.get("company", ""),
            location=normalized_dict.get("location", ""),
            country=self._extract_country(normalized_dict),
            apply_url=normalized_dict.get("apply_link", "") or normalized_dict.get("link", ""),
            source_url=normalized_dict.get("alt_link", ""),
            source=self.source_name,
            provider_job_id=normalized_dict.get("job_id", ""),
            posted_at=normalized_dict.get("job_posted_at_datetime_utc", None),
            description=normalized_dict.get("description", ""),
            employment_type=normalized_dict.get("employment_type", None),
            salary_string=normalized_dict.get("salary_string", None),
        )

    def _extract_country(self, normalized_dict: Dict[str, Any]) -> str:
        """Extract country from location field or default to UAE.

        Phase 1: Uses existing logic from jsearch_client.normalize_item() which
        defaults location to "UAE" if no city/state/country is present.
        """
        location = normalized_dict.get("location", "")
        if "UAE" in location or "United Arab Emirates" in location:
            return "United Arab Emirates"
        # Default to UAE as per existing behavior
        return "United Arab Emirates"

    def validate(self, job: NormalizedJob) -> bool:
        """Validates job has required fields and UAE location.

        Phase 1: Uses existing UAE filtering logic from jsearch_client._UAE_CITY_NAMES.
        A job is valid if it has apply_url OR source_url.
        """
        from src import jsearch_client

        # Check if job has valid URL (Pydantic validator already ensures this)
        if not job.apply_url and not job.source_url:
            return False

        # UAE filtering: check if location contains UAE city names
        location_lower = job.location.lower()
        uae_cities = jsearch_client._UAE_CITY_NAMES
        is_uae = any(uae_city in location_lower for uae_city in uae_cities)

        # Also accept if country is explicitly UAE
        is_uae = is_uae or "uae" in job.country.lower() or "united arab emirates" in job.country.lower()

        return is_uae

    def get_apply_url(self, job: NormalizedJob) -> str:
        """Extracts the best apply URL.

        Phase 1: Prefers apply_url over source_url, matching existing jsearch_client logic.
        """
        return job.apply_url or job.source_url or ""
