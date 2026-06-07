"""
Base Job Source Adapter Interface

Defines the abstract interface that all job source adapters must implement.
Phase 1: Interface definition only (no behavior change).

Version: 2.1.0 (Phase 1)
"""

import abc
from typing import List, Dict, Any, Optional
from .normalized import NormalizedJob


class BaseJobSourceAdapter(abc.ABC):
    """Abstract Base Class enforcing standard protocol for all job engine connectors.

    Phase 1: Interface definition only. JSearchAdapter will implement this interface
    without changing existing runtime behavior.
    """

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Returns the unique tracking identifier for the target source adapter."""
        pass

    @abc.abstractmethod
    def search(self, query: str, country: str = "ae") -> List[Dict[str, Any]]:
        """Executes raw data fetch from target provider backend.

        Phase 1: JSearchAdapter will wrap existing jsearch_client.search() method.
        Current production signature: search(query: str, *, use_cache: bool = True, country: str = "ae") -> FetchResult
        """
        pass

    @abc.abstractmethod
    def normalize(self, raw_job: Dict[str, Any]) -> NormalizedJob:
        """Transforms provider raw dictionary context into strict NormalizedJob model instance.

        Phase 1: JSearchAdapter will wrap existing jsearch_client.normalize_item() logic.
        """
        pass

    @abc.abstractmethod
    def validate(self, job: NormalizedJob) -> bool:
        """Validates geographic parameters or content eligibility filters.

        Phase 1: JSearchAdapter will use existing UAE filtering logic from jsearch_client.
        """
        pass

    @abc.abstractmethod
    def get_apply_url(self, job: NormalizedJob) -> str:
        """Extracts sanitized definitive action landing URL.

        Phase 1: JSearchAdapter will prefer apply_url over source_url.
        """
        pass
