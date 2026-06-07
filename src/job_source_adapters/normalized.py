"""
Normalized Job Schema

Defines the unified data structure for jobs across all sources.
Phase 1: Schema definition only (no behavior change).

Version: 2.1.0 (Phase 1)
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class NormalizedJob(BaseModel):
    """Unified job schema across all job sources.

    Phase 1: Schema definition. JSearchAdapter will map existing JSearch
    output to this schema without changing behavior.
    """

    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location (city/state)")
    country: str = Field(..., description="Country name")
    apply_url: str = Field(..., description="Primary application URL")
    source_url: str = Field(default="", description="Source/job listing URL")
    source: str = Field(..., description="Source identifier (e.g., 'jsearch')")
    provider_job_id: str = Field(..., description="Job ID from source provider")
    posted_at: Optional[datetime] = Field(None, description="Job posting timestamp")
    description: str = Field(default="", description="Job description")
    employment_type: Optional[str] = Field(None, description="Employment type (e.g., 'Full-time')")
    salary_string: Optional[str] = Field(None, description="Salary string from source")

    @model_validator(mode="after")
    def at_least_one_url(self):
        """Ensure at least one URL is provided."""
        if not self.apply_url and not self.source_url:
            raise ValueError("Must provide at least an apply_url or a source_url")
        return self
