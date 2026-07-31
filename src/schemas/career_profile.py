"""Typed career-profile models and provenance contract.

These models define the bounded shape of confirmed, extracted, and suggested
career evidence. They are used by the API layer and stored as JSON inside the
profile JSONB column; no migration is required because the profile JSONB already
holds arbitrary structured data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class ProvenanceState(str, Enum):
    """Canonical provenance for every structured career item."""

    EXTRACTED_FROM_CV = "extracted_from_cv"
    CONFIRMED_BY_USER = "confirmed_by_user"
    EDITED_BY_USER = "edited_by_user"
    ADDED_BY_USER = "added_by_user"
    SUGGESTED_BY_RICO = "suggested_by_rico"
    NEEDS_CONFIRMATION = "needs_confirmation"


class BaseCareerItem(BaseModel):
    """Common fields for every durable piece of career evidence."""

    model_config = {"extra": "ignore"}

    id: Optional[str] = Field(None, description="Stable opaque identifier.")
    source_document_id: Optional[str] = Field(
        None,
        description="Opaque id of the originating document or upload artifact.",
    )
    provenance: ProvenanceState = Field(
        default=ProvenanceState.ADDED_BY_USER,
        description="Who is responsible for this fact.",
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    confirmed_at: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp when the user confirmed the fact.",
    )
    updated_at: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp of the last update to this item.",
    )


class ExperienceItem(BaseCareerItem):
    role: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


class EducationItem(BaseCareerItem):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CertificationItem(BaseCareerItem):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None


class LanguageItem(BaseCareerItem):
    name: Optional[str] = None
    proficiency: Optional[str] = None


class SkillItem(BaseCareerItem):
    name: Optional[str] = None


class CareerProfile(BaseModel):
    """The confirmed, enriched career profile built from CV + user edits."""

    summary: Optional[str] = None
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
    skills: List[SkillItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, value: Any) -> Any:
        """Allow loading legacy plain lists (skills as strings) during transition."""
        if not isinstance(value, dict):
            return value
        skills = value.get("skills")
        if isinstance(skills, list) and skills and not isinstance(skills[0], dict):
            value = dict(value)
            value["skills"] = [
                {"name": s} if isinstance(s, str) else s for s in skills
            ]
        return value


class BaseCareerItemUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    id: Optional[str] = Field(None, description="Existing item id; omit to add.")


class ExperienceItemUpdate(BaseCareerItemUpdate):
    role: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


class EducationItemUpdate(BaseCareerItemUpdate):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CertificationItemUpdate(BaseCareerItemUpdate):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None


class LanguageItemUpdate(BaseCareerItemUpdate):
    name: Optional[str] = None
    proficiency: Optional[str] = None


class SkillItemUpdate(BaseCareerItemUpdate):
    name: Optional[str] = None


EditableItem = Union[
    ExperienceItemUpdate,
    EducationItemUpdate,
    CertificationItemUpdate,
    LanguageItemUpdate,
    SkillItemUpdate,
]


class CareerProfileUpdate(BaseModel):
    """Client-writable subset of CareerProfile.

    Server-owned metadata (provenance, timestamps, confidence, source) is
    stripped and re-derived by the API before persistence.
    """

    model_config = {"extra": "forbid"}

    summary: Optional[str] = None
    experience: List[ExperienceItemUpdate] = Field(default_factory=list)
    education: List[EducationItemUpdate] = Field(default_factory=list)
    certifications: List[CertificationItemUpdate] = Field(default_factory=list)
    languages: List[LanguageItemUpdate] = Field(default_factory=list)
    skills: List[SkillItemUpdate] = Field(default_factory=list)


class ReviewDecision(str, Enum):
    """Possible review decisions for a structured item."""

    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"
    ADD = "add"


class CareerProfileReview(BaseModel):
    """User review of a CV-extracted career profile preview.

    Not used in PR 1; the model exists so the contract is stable when review
    semantics are implemented in a later PR.
    """

    accepted_ids: List[str] = Field(default_factory=list)
    edited_values: List[EditableItem] = Field(default_factory=list)
    rejected_ids: List[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


# Resolve forward references for update/review collections.
CareerProfileUpdate.model_rebuild()
CareerProfileReview.model_rebuild()


class ProfilePreview(BaseModel):
    """Preview of extracted CV data shown to the user before confirmation.

    The `work_experience` and `education` arrays carry typed `ExperienceItem` and
    `EducationItem` objects with provenance `extracted_from_cv`. Other fields are
    flat extracted strings for backward compatibility.
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[float] = None
    target_roles: List[str] = Field(default_factory=list)
    skills_detected: List[str] = Field(default_factory=list)
    existing_skills: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    work_experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    extraction_quality: Optional[str] = None
    extracted_chars: Optional[int] = None


class CompletenessBreakdownItem(BaseModel):
    section: str
    score: float = Field(..., ge=0.0, le=1.0)
    missing: List[str] = Field(default_factory=list)
    needs_confirmation: bool = False


class Completeness(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    sections: List[CompletenessBreakdownItem] = Field(default_factory=list)


def now_iso() -> str:
    """Server-owned timestamp factory for provenance and audit fields."""
    return datetime.now(timezone.utc).isoformat()
