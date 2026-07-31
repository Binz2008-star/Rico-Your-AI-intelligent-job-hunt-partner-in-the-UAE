"""Typed read-only Career Profile contract.

These models define the bounded shape of career data that can be truthfully
derived from current canonical storage. They are used by the API response layer
only; no client writes are accepted in this contract.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ProvenanceState(str, Enum):
    """Canonical provenance for preview/extracted career items."""

    EXTRACTED_FROM_CV = "extracted_from_cv"


class BaseCareerItem(BaseModel):
    """Common server-owned fields for every piece of career evidence."""

    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    source_document_id: Optional[str] = None
    provenance: ProvenanceState = ProvenanceState.EXTRACTED_FROM_CV
    confidence: Optional[float] = None
    confirmed_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExperienceItem(BaseCareerItem):
    """One work experience entry, derived from CV extraction."""

    role: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    start_date: Optional[str] = Field(None, max_length=20)
    end_date: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=200)


class EducationItem(BaseCareerItem):
    """One education entry, derived from CV extraction."""

    institution: Optional[str] = Field(None, max_length=200)
    degree: Optional[str] = Field(None, max_length=100)
    field: Optional[str] = Field(None, max_length=100)
    start_date: Optional[str] = Field(None, max_length=20)
    end_date: Optional[str] = Field(None, max_length=20)


class SkillItem(BaseModel):
    """One skill as stored in canonical legacy profile.skills."""

    model_config = {"extra": "ignore"}

    name: Optional[str] = Field(None, max_length=100)


class CertificationItem(BaseModel):
    """One certification as stored in canonical legacy profile.certifications."""

    model_config = {"extra": "ignore"}

    name: Optional[str] = Field(None, max_length=100)


class LanguageItem(BaseModel):
    """One language as stored in canonical legacy profile.languages."""

    model_config = {"extra": "ignore"}

    name: Optional[str] = Field(None, max_length=100)
    proficiency: Optional[str] = Field(None, max_length=50)


class CareerProfile(BaseModel):
    """Read-only confirmed Career Profile derived from canonical legacy fields."""

    model_config = {"extra": "ignore"}

    skills: List[SkillItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
