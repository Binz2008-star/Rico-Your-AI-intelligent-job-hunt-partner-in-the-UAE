"""Personalized cover letter writer — AI-first, template fallback."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CoverLetterIdentityError(Exception):
    """Raised when required identity information is missing for cover letter generation."""
    pass


@dataclass(frozen=True)
class CoverLetterIdentity:
    """Structured identity object for cover letter generation.

    All fields must be verified user data. No generic fallbacks allowed.
    """
    name: str
    location: str
    title: Optional[str] = None
    company: Optional[str] = None
    years_experience: Optional[float] = None
    profile_line: Optional[str] = None
    verified_strengths: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise CoverLetterIdentityError("Identity name is required and cannot be empty")
        if not self.location or not self.location.strip():
            raise CoverLetterIdentityError("Identity location is required and cannot be empty")


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _letter_language(job: Dict[str, Any]) -> str:
    """Return the requested output language for the letter ('ar' or 'en')."""
    lang = str(job.get("language") or "").strip().lower()
    return "ar" if lang in ("ar", "arabic", "ar-ae", "ar_sa") else "en"


def _build_profile_line(
    identity: CoverLetterIdentity,
    job: Dict[str, Any],
    language: str = "en",
) -> str:
    """Build a profile sentence from verified identity fields only."""
    if identity.profile_line:
        return identity.profile_line

    arabic = language == "ar"
    parts: List[str] = []
    if identity.years_experience:
        if arabic:
            parts.append(f"خبرة تزيد عن {int(identity.years_experience)} سنوات في المجال")
        else:
            parts.append(f"{int(identity.years_experience)}+ years of relevant experience")

    if identity.verified_strengths:
        job_text = f"{job.get('title','')} {job.get('description','')} {job.get('requirements','')}".lower()
        relevant = [
            s for s in identity.verified_strengths[:5]
            if any(kw in job_text for kw in s.lower().split())
        ]
        if relevant:
            if arabic:
                parts.append("خبرة في " + "، ".join(relevant[:3]))
            else:
                parts.append("expertise in " + ", ".join(relevant[:3]))

    if identity.title:
        parts.append(f"المنصب الحالي {identity.title}" if arabic else f"current role as {identity.title}")
    if identity.company:
        parts.append(f"في {identity.company}" if arabic else f"at {identity.company}")

    if not parts:
        raise CoverLetterIdentityError(
            "Profile line or verified experience data required. "
            "Provide profile_line, years_experience, or verified_strengths."
        )
    return ("، و".join(parts) if arabic else " and ".join(parts))


def _ai_generate_cover_letter(
    job: Dict[str, Any],
    identity: CoverLetterIdentity,
    profile_line: str,
    language: str = "en",
) -> Optional[str]:
    """Call the active AI provider to write the cover letter.

    Returns None when the provider is unavailable so the caller falls back
    to the template path. Never raises.
    """
    try:
        from src.rico_env import get_ai_provider
        provider = get_ai_provider()
        if provider not in ("openai", "deepseek"):
            return None

        from src.rico_openai_runtime import call_openai_minimal

        title = _clean(job.get("title")) or "the advertised role"
        company = _clean(job.get("company")) or "your organization"
        location = _clean(job.get("location")) or "the UAE"
        description_snippet = str(job.get("description") or "")[:800]

        if language == "ar":
            prompt = (
                f"اكتب خطاب تقديم احترافي ومختصر لطلب التوظيف التالي.\n\n"
                f"المسمى الوظيفي: {title}\n"
                f"الشركة: {company}\n"
                f"الموقع: {location}\n"
                f"مقتطف من الوصف الوظيفي: {description_snippet}\n\n"
                f"ملف المتقدم: {profile_line}\n"
                f"اسم المتقدم: {_clean(identity.name)}\n"
                f"موقع المتقدم: {_clean(identity.location)}\n\n"
                f"التعليمات:\n"
                f"- اكتب الخطاب بالكامل باللغة العربية\n"
                f"- من 3 إلى 4 فقرات قصيرة\n"
                f"- خصّص الخطاب للمسمى الوظيفي والشركة تحديداً\n"
                f"- ابدأ بـ 'إلى مسؤول التوظيف،'\n"
                f"- اختم بـ 'مع خالص التقدير،' ثم اسم المتقدم وموقعه\n"
                f"- لا تختلق مؤهلات أو خبرات غير مذكورة أعلاه\n"
                f"- استخدم نبرة مهنية واثقة تناسب سوق العمل في الإمارات\n"
            )
        else:
            prompt = (
                f"Write a concise, professional cover letter for the following job application.\n\n"
                f"Job title: {title}\n"
                f"Company: {company}\n"
                f"Location: {location}\n"
                f"Job description excerpt: {description_snippet}\n\n"
                f"Applicant profile: {profile_line}\n"
                f"Applicant name: {_clean(identity.name)}\n"
                f"Applicant location: {_clean(identity.location)}\n\n"
                f"Instructions:\n"
                f"- 3–4 short paragraphs\n"
                f"- Tailor specifically to the job title and company\n"
                f"- Open with 'Dear Hiring Manager,'\n"
                f"- Close with 'Sincerely,' then the applicant's name and location\n"
                f"- Do not invent credentials or experience not mentioned above\n"
                f"- Write in a confident, professional tone suitable for UAE job applications\n"
            )

        result = call_openai_minimal(prompt, provider=provider)
        if result.get("success"):
            text = result.get("text", "").strip()
            if language == "ar":
                if text and re.search(r"[؀-ۿ]", text):
                    return text
            elif text and "Dear Hiring Manager" in text:
                return text
        return None
    except Exception:
        logger.debug("cover_letter_ai_generation_failed", exc_info=True)
        return None


def _template_cover_letter(
    job: Dict[str, Any],
    identity: CoverLetterIdentity,
    profile_line: str,
    language: str = "en",
) -> str:
    """Template fallback — generic but domain-agnostic."""
    if language == "ar":
        return _template_cover_letter_ar(job, identity, profile_line)

    title = _clean(job.get("title")) or "the advertised role"
    company = _clean(job.get("company")) or "your organization"
    location = _clean(job.get("location")) or "the UAE"

    # Build bullet lines from verified strengths mapped against the job text
    job_text = f"{title} {job.get('description', '')}".lower()
    bullets: List[str] = []
    for s in (identity.verified_strengths or [])[:4]:
        bullets.append(f"- {s.capitalize()}.")
    if not bullets:
        bullets = [
            f"- Relevant experience aligned with the {title} responsibilities.",
            f"- Track record of delivering results in similar roles.",
        ]

    bullet_block = "\n".join(bullets)
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my interest in the {title} position at {company} in {location}.\n\n"
        f"I bring {profile_line}. This background positions me well to contribute to {company}'s goals "
        f"in this role.\n\n"
        f"Relevant experience I would bring:\n{bullet_block}\n\n"
        f"I would welcome the opportunity to discuss how my background can support {company}.\n\n"
        f"Sincerely,\n"
        f"{_clean(identity.name)}\n"
        f"{_clean(identity.location)}\n"
    )


def _template_cover_letter_ar(
    job: Dict[str, Any],
    identity: CoverLetterIdentity,
    profile_line: str,
) -> str:
    """Arabic template fallback — used when the request language is Arabic."""
    title = _clean(job.get("title")) or "الوظيفة المعلن عنها"
    company = _clean(job.get("company")) or "مؤسستكم"
    location = _clean(job.get("location")) or "الإمارات"

    bullets: List[str] = []
    for s in (identity.verified_strengths or [])[:4]:
        bullets.append(f"- {s}.")
    if not bullets:
        bullets = [
            f"- خبرة ذات صلة بمسؤوليات وظيفة {title}.",
            f"- سجل حافل في تحقيق النتائج في أدوار مماثلة.",
        ]

    bullet_block = "\n".join(bullets)
    return (
        f"إلى مسؤول التوظيف،\n\n"
        f"أكتب إليكم للتعبير عن اهتمامي بوظيفة {title} لدى {company} في {location}.\n\n"
        f"أمتلك {profile_line}. تؤهلني هذه الخلفية للإسهام بفعالية في تحقيق أهداف {company} في هذا الدور.\n\n"
        f"الخبرات ذات الصلة التي سأقدمها:\n{bullet_block}\n\n"
        f"يسعدني أن أناقش معكم كيف يمكن لخلفيتي أن تدعم {company}.\n\n"
        f"مع خالص التقدير،\n"
        f"{_clean(identity.name)}\n"
        f"{_clean(identity.location)}\n"
    )


def generate_cover_letter_with_identity(
    job: Dict[str, Any],
    identity: CoverLetterIdentity,
) -> str:
    """Generate a cover letter — AI when provider is available, template fallback.

    Args:
        job: Job posting data with title, company, description, etc.
        identity: Verified user identity (name, location, strengths, etc.)

    Returns:
        Cover letter string.

    Raises:
        CoverLetterIdentityError: If required identity data is missing.
    """
    language = _letter_language(job)
    profile_line = _build_profile_line(identity, job, language)

    ai_letter = _ai_generate_cover_letter(job, identity, profile_line, language)
    if ai_letter:
        logger.info("cover_letter_generated source=ai lang=%s name=%s", language, identity.name[:20])
        return ai_letter

    letter = _template_cover_letter(job, identity, profile_line, language)
    logger.info("cover_letter_generated source=template lang=%s name=%s", language, identity.name[:20])
    return letter


def generate_cover_letter(
    job: Dict[str, Any],
    identity: Optional[CoverLetterIdentity] = None,
) -> str:
    """Generate a cover letter using verified identity information.

    Raises:
        CoverLetterIdentityError: If identity is not provided or validation fails.
    """
    if identity is None:
        raise CoverLetterIdentityError(
            "Verified identity is required for cover letter generation. "
            "Use generate_cover_letter_with_identity(job, CoverLetterIdentity(...)) "
            "or provide a valid identity object."
        )
    return generate_cover_letter_with_identity(job, identity)


def generate_batch_cover_letters(
    jobs: List[Dict[str, Any]],
    identity: Optional[CoverLetterIdentity] = None,
) -> Dict[str, str]:
    """Generate cover letters for multiple jobs using verified identity.

    Raises:
        CoverLetterIdentityError: If identity is not provided.
    """
    if identity is None:
        raise CoverLetterIdentityError(
            "Verified identity is required for cover letter generation. "
            "Use generate_batch_cover_letters_with_identity(jobs, CoverLetterIdentity(...)) "
            "or provide a valid identity object."
        )
    return generate_batch_cover_letters_with_identity(jobs, identity)


def generate_batch_cover_letters_with_identity(
    jobs: List[Dict[str, Any]],
    identity: CoverLetterIdentity,
) -> Dict[str, str]:
    """Generate cover letters for multiple jobs using structured identity object."""
    letters: Dict[str, str] = {}
    for job in jobs:
        key = job.get("link") or f"{job.get('company','')}_{job.get('title','')}"
        letters[str(key)] = generate_cover_letter_with_identity(job, identity)
    logger.info("batch_cover_letters_complete total=%s", len(letters))
    return letters
