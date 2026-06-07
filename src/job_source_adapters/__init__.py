"""
Job Sources Adapter Architecture

Provides a unified interface for job discovery sources with normalized schemas.
Phase 1: JSearch adapter foundation (no behavior change).

Version: 2.1.0 (Phase 1)
"""

from .normalized import NormalizedJob
from .base import BaseJobSourceAdapter
from .jsearch_adapter import JSearchAdapter

__all__ = ["NormalizedJob", "BaseJobSourceAdapter", "JSearchAdapter"]
