"""Non-blocking advisory warnings for CV extraction quality.

These warnings surface issues noticed during CV parsing so the user can decide
whether to proceed or re-upload a better document. They never block a save,
mutate profile values, or affect scoring.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

Warning = dict[str, str]

_YEARS_EXPERIENCE_MAX = 50
_YEARS_EXPERIENCE_SUSPICIOUS = 25
_SKILLS_MIN = 3


def build_cv_quality_warnings(
    *,
    preview: Mapping[str, Any] | None = None,
    extraction_quality: str | None = None,
    profile: Any | None = None,
) -> list[Warning]:
    """Return non-blocking advisory warnings about a just-uploaded CV.

    Call after parsing, before returning the upload response. Warnings are
    advisory only — they do not block the upload or modify any stored values.

    Args:
        preview: the preview dict built during upload (experience_years, skills_detected,
            current_role, target_roles, etc.).
        extraction_quality: value from ParsedCV ("poor", "partial", "good", "unknown").
        profile: optional stored profile object/dict for active CV identification hints.
    """
    preview = preview or {}
    warnings: list[Warning] = []

    warnings.extend(_extraction_quality_warnings(extraction_quality or "unknown"))
    warnings.extend(_experience_warnings(preview))
    warnings.extend(_skills_warnings(preview))
    warnings.extend(_role_mismatch_warnings(preview, profile))

    return _dedupe(warnings)


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _extraction_quality_warnings(quality: str) -> list[Warning]:
    warnings: list[Warning] = []
    if quality == "poor":
        warnings.append(
            _warning(
                code="cv_extraction_quality_poor",
                field="extraction_quality",
                message=(
                    "Rico extracted very little text from this CV (fewer than 300 characters). "
                    "Job matching may be inaccurate."
                ),
                suggestion="Try uploading a text-based PDF or a DOCX file instead of a scanned image.",
                message_ar=(
                    "استخرج Rico نصاً قليلاً جداً من هذه السيرة الذاتية (أقل من 300 حرف). "
                    "قد تكون مطابقة الوظائف غير دقيقة."
                ),
                suggestion_ar="جرّب رفع ملف PDF يحتوي على نص أو ملف DOCX بدلاً من صورة ممسوحة.",
            )
        )
    elif quality == "partial":
        warnings.append(
            _warning(
                code="cv_extraction_quality_partial",
                field="extraction_quality",
                message=(
                    "Rico extracted limited text from this CV (fewer than 1000 characters). "
                    "Some profile fields may be incomplete."
                ),
                suggestion="If your CV has more content, try a DOCX or text-based PDF for better results.",
                message_ar=(
                    "استخرج Rico نصاً محدوداً من هذه السيرة الذاتية (أقل من 1000 حرف). "
                    "قد تكون بعض حقول الملف الشخصي غير مكتملة."
                ),
                suggestion_ar="إذا كانت سيرتك الذاتية تحتوي على محتوى أكثر، جرّب DOCX أو PDF نصياً للحصول على نتائج أفضل.",
            )
        )
    return warnings


def _experience_warnings(preview: Mapping[str, Any]) -> list[Warning]:
    warnings: list[Warning] = []
    raw = preview.get("experience_years")
    if raw is None:
        return warnings
    try:
        years = float(raw)
    except (TypeError, ValueError):
        return warnings

    if years > _YEARS_EXPERIENCE_MAX:
        warnings.append(
            _warning(
                code="cv_years_experience_unrealistic",
                field="experience_years",
                message=(
                    f"Rico detected {years:.0f} years of experience, which is unusually high. "
                    "This may be a parsing artefact."
                ),
                suggestion="Check your years of experience in the profile and correct it if needed.",
                message_ar=(
                    f"رصد Rico {years:.0f} سنوات من الخبرة، وهو رقم مرتفع بشكل غير عادي. "
                    "قد يكون ذلك ناتجاً عن خطأ في الاستخراج."
                ),
                suggestion_ar="تحقق من سنوات خبرتك في ملفك الشخصي وصحّحها إذا لزم الأمر.",
            )
        )
    elif years > _YEARS_EXPERIENCE_SUSPICIOUS:
        warnings.append(
            _warning(
                code="cv_years_experience_high",
                field="experience_years",
                message=(
                    f"Rico detected {years:.0f} years of experience. "
                    "Please confirm this is correct before using it for job matching."
                ),
                suggestion="Review the experience field in your profile to make sure it matches your CV.",
                message_ar=(
                    f"رصد Rico {years:.0f} سنة من الخبرة. "
                    "يرجى التأكد من صحة هذا الرقم قبل استخدامه في مطابقة الوظائف."
                ),
                suggestion_ar="راجع حقل الخبرة في ملفك الشخصي للتأكد من مطابقته لسيرتك الذاتية.",
            )
        )
    return warnings


def _skills_warnings(preview: Mapping[str, Any]) -> list[Warning]:
    warnings: list[Warning] = []
    skills = preview.get("skills_detected") or preview.get("skills") or []
    if not isinstance(skills, list):
        return warnings
    if 0 < len(skills) < _SKILLS_MIN:
        warnings.append(
            _warning(
                code="cv_skills_low",
                field="skills_detected",
                message=(
                    f"Only {len(skills)} skill(s) were detected in your CV. "
                    "A richer skills list improves job matching accuracy."
                ),
                suggestion=(
                    "Add a dedicated Skills section to your CV with specific tools, "
                    "certifications, and competencies."
                ),
                message_ar=(
                    f"تم اكتشاف {len(skills)} مهارة فقط في سيرتك الذاتية. "
                    "قائمة مهارات أكثر ثراءً تحسّن دقة مطابقة الوظائف."
                ),
                suggestion_ar=(
                    "أضف قسم مهارات مخصصاً في سيرتك الذاتية يتضمن أدوات وشهادات وكفاءات محددة."
                ),
            )
        )
    return warnings


def _role_mismatch_warnings(
    preview: Mapping[str, Any],
    profile: Any | None,
) -> list[Warning]:
    """Warn when the CV's current_role shares no keywords with stored target_roles."""
    warnings: list[Warning] = []
    cv_role = preview.get("current_role")
    if not cv_role or not isinstance(cv_role, str):
        return warnings

    # Prefer target_roles from the preview (freshly extracted), then fall back to
    # the stored profile so the check works on first upload too.
    target_roles: list[str] = list(preview.get("target_roles") or [])
    if not target_roles and profile is not None:
        stored = (
            profile.get("target_roles")
            if isinstance(profile, Mapping)
            else getattr(profile, "target_roles", None)
        )
        if stored:
            target_roles = list(stored)

    if not target_roles:
        return warnings

    cv_words = set(_tokenize(cv_role))
    overlap = any(
        cv_words & set(_tokenize(role))
        for role in target_roles
    )
    if not overlap:
        roles_str = ", ".join(target_roles[:3])
        warnings.append(
            _warning(
                code="cv_role_target_role_mismatch",
                field="current_role",
                message=(
                    f"Your CV lists '{cv_role}' as your current role, but your target roles "
                    f"are [{roles_str}]. There is no keyword overlap, which may reduce match quality."
                ),
                suggestion=(
                    "If you are changing careers, make sure your profile target roles "
                    "reflect the positions you are applying for."
                ),
                message_ar=(
                    f"تُدرج سيرتك الذاتية '{cv_role}' كدورك الحالي، لكن أدوارك المستهدفة "
                    f"هي [{roles_str}]. لا يوجد تداخل في الكلمات المفتاحية، مما قد يقلل من جودة المطابقة."
                ),
                suggestion_ar=(
                    "إذا كنت تغيّر مسارك المهني، تأكد من أن الأدوار المستهدفة في ملفك تعكس "
                    "المناصب التي تتقدم إليها."
                ),
            )
        )
    return warnings


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alpha tokens of length ≥ 2."""
    return [w for w in re.split(r"[^a-zA-Z]+", text.lower()) if len(w) >= 2]


def _warning(
    *,
    code: str,
    field: str,
    message: str,
    suggestion: str,
    message_ar: str,
    suggestion_ar: str,
) -> Warning:
    return {
        "code": code,
        "field": field,
        "severity": "warning",
        "message": message,
        "suggestion": suggestion,
        "message_ar": message_ar,
        "suggestion_ar": suggestion_ar,
    }


def _dedupe(warnings: list[Warning]) -> list[Warning]:
    seen: set[str] = set()
    out: list[Warning] = []
    for w in warnings:
        key = w.get("code", "")
        if key not in seen:
            seen.add(key)
            out.append(w)
    return out
