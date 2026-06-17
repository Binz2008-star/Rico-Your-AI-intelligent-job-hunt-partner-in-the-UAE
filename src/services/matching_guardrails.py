"""Warnings for profile/settings values that can make job matching too narrow."""
from __future__ import annotations

import re
from typing import Any, Mapping

Warning = dict[str, str]

CORE_ROLE_TERMS = ("manager", "environmental", "compliance", "esg", "hse")

UAE_CITY_ALIASES = {
    "abu dhabi": "Abu Dhabi",
    "ajman": "Ajman",
    "al ain": "Al Ain",
    "dubai": "Dubai",
    "fujairah": "Fujairah",
    "ras al khaimah": "Ras Al Khaimah",
    "sharjah": "Sharjah",
    "umm al quwain": "Umm Al Quwain",
    "أبو ظبي": "Abu Dhabi",
    "ابوظبي": "Abu Dhabi",
    "أبوظبي": "Abu Dhabi",
    "الشارقة": "Sharjah",
    "العين": "Al Ain",
    "الفجيرة": "Fujairah",
    "ام القيوين": "Umm Al Quwain",
    "أم القيوين": "Umm Al Quwain",
    "دبي": "Dubai",
    "راس الخيمة": "Ras Al Khaimah",
    "رأس الخيمة": "Ras Al Khaimah",
}


def build_matching_guardrail_warnings(
    *,
    settings: Mapping[str, Any] | None = None,
    profile: Any | None = None,
) -> list[Warning]:
    """Return non-blocking warnings for matching inputs.

    These guardrails intentionally do not mutate values, block saves, or change the
    scoring algorithm. They only make risky matching inputs visible.
    """
    settings = settings or {}
    include_keywords = _as_list(settings.get("include_keywords"))
    exclude_keywords = _as_list(settings.get("exclude_keywords"))
    target_roles = _as_list(_profile_value(profile, "target_roles"))
    preferred_cities = _as_list(
        _profile_value(profile, "preferred_cities")
        or _profile_value(profile, "cities")
    )

    warnings: list[Warning] = []
    warnings.extend(_keyword_overlap_warnings(include_keywords, exclude_keywords))
    warnings.extend(_excluded_role_word_warnings(exclude_keywords, target_roles))

    min_score = _as_int(settings.get("min_score"))
    if min_score is not None and min_score > 60:
        warnings.append(
            _warning(
                code="minimum_fit_score_high",
                field="min_score",
                message=(
                    f"Minimum fit score is {min_score}%. Scores above 60% can "
                    "hide useful matches before Rico can explain the tradeoffs."
                ),
                suggestion="Use 60% or lower unless you only want a very narrow shortlist.",
                message_ar=(
                    f"الحد الادنى لدرجة الملاءمة هو {min_score}%. الدرجات فوق 60% "
                    "قد تخفي فرصا مناسبة قبل أن يشرح Rico المفاضلات."
                ),
                suggestion_ar="استخدم 60% أو أقل إلا إذا كنت تريد قائمة مختصرة جدا.",
            )
        )

    invalid_cities = [city for city in preferred_cities if not is_uae_city(city)]
    if invalid_cities:
        joined = ", ".join(invalid_cities)
        warnings.append(
            _warning(
                code="invalid_uae_city",
                field="preferred_cities",
                message=(
                    f"City value {joined!r} is not recognized as a UAE city, "
                    "so Rico may search the wrong market."
                ),
                suggestion="Choose a UAE city such as Dubai, Abu Dhabi, Sharjah, Ajman, or Al Ain.",
                message_ar=(
                    f"قيمة المدينة {joined!r} ليست مدينة إماراتية معروفة، "
                    "وقد يبحث Rico في سوق غير مناسب."
                ),
                suggestion_ar="اختر مدينة إماراتية مثل دبي أو أبو ظبي أو الشارقة أو عجمان أو العين.",
            )
        )

    if len(target_roles) > 3:
        warnings.append(
            _warning(
                code="too_many_target_roles",
                field="target_roles",
                message=(
                    f"You have {len(target_roles)} target roles. Too many roles "
                    "can make matching noisy and less focused."
                ),
                suggestion="Choose up to 3 primary roles and keep secondary ideas for later searches.",
                message_ar=(
                    f"لديك {len(target_roles)} أدوار مستهدفة. كثرة الادوار قد تجعل "
                    "المطابقة مشتتة واقل تركيزا."
                ),
                suggestion_ar="اختر حتى 3 أدوار اساسية واترك الافكار الثانوية لعمليات بحث لاحقة.",
            )
        )

    return _dedupe_warnings(warnings)


def is_uae_city(value: str) -> bool:
    return _normalize(value) in UAE_CITY_ALIASES


def _keyword_overlap_warnings(
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> list[Warning]:
    warnings: list[Warning] = []
    for excluded in exclude_keywords:
        excluded_norm = _normalize(excluded)
        if not excluded_norm:
            continue
        for included in include_keywords:
            included_norm = _normalize(included)
            if not included_norm:
                continue
            if _phrases_overlap(excluded_norm, included_norm):
                warnings.append(
                    _warning(
                        code="excluded_keyword_overlaps_included_keyword",
                        field="exclude_keywords",
                        message=(
                            f'Excluded keyword "{excluded}" overlaps included keyword '
                            f'"{included}", so Rico may hide jobs you asked it to prioritize.'
                        ),
                        suggestion=f'Remove "{excluded}" or make the included keyword more specific.',
                        message_ar=(
                            f'الكلمة المستبعدة "{excluded}" تتداخل مع الكلمة المضمنة '
                            f'"{included}"، وقد يخفي Rico وظائف طلبت منه تفضيلها.'
                        ),
                        suggestion_ar=f'احذف "{excluded}" أو اجعل الكلمة المضمنة أكثر تحديدا.',
                    )
                )
    return warnings


def _excluded_role_word_warnings(
    exclude_keywords: list[str],
    target_roles: list[str],
) -> list[Warning]:
    warnings: list[Warning] = []
    for excluded in exclude_keywords:
        excluded_norm = _normalize(excluded)
        if not excluded_norm:
            continue
        protected_terms = [
            term for term in CORE_ROLE_TERMS if _contains_phrase(excluded_norm, term)
        ]
        blocked_roles = [
            role for role in target_roles if _phrases_overlap(excluded_norm, _normalize(role))
        ]
        if blocked_roles:
            roles = ", ".join(blocked_roles[:3])
            warnings.append(
                _warning(
                    code="excluded_keyword_blocks_target_role",
                    field="exclude_keywords",
                    message=(
                        f'Excluded keyword "{excluded}" overlaps target role "{roles}" '
                        "and can hide roles that match your profile."
                    ),
                    suggestion=f'Remove "{excluded}" or replace it with a more precise exclusion.',
                    message_ar=(
                        f'الكلمة المستبعدة "{excluded}" تتداخل مع الدور المستهدف '
                        f'"{roles}" وقد تخفي وظائف مناسبة لملفك.'
                    ),
                    suggestion_ar=f'احذف "{excluded}" أو استبدلها باستبعاد أكثر دقة.',
                )
            )
        elif protected_terms:
            terms = ", ".join(protected_terms)
            warnings.append(
                _warning(
                    code="excluded_keyword_blocks_core_role_word",
                    field="exclude_keywords",
                    message=(
                        f'Excluded keyword "{excluded}" blocks core role wording '
                        f'({terms}) that appears in common Rico matches.'
                    ),
                    suggestion=(
                        "Avoid excluding broad role words like manager, environmental, "
                        "compliance, ESG, or HSE."
                    ),
                    message_ar=(
                        f'الكلمة المستبعدة "{excluded}" تحجب كلمات اساسية في المسميات '
                        f"الوظيفية ({terms}) تظهر في نتائج Rico الشائعة."
                    ),
                    suggestion_ar=(
                        "تجنب استبعاد كلمات عامة مثل manager أو environmental أو "
                        "compliance أو ESG أو HSE."
                    ),
                )
            )
    return warnings


def _profile_value(profile: Any, key: str) -> Any:
    if profile is None:
        return None
    if isinstance(profile, Mapping):
        return profile.get(key)
    return getattr(profile, key, None)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,;\n|/]+", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _phrases_overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return _contains_phrase(left, right) or _contains_phrase(right, left)


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
            text,
            re.IGNORECASE,
        )
    )


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


def _dedupe_warnings(warnings: list[Warning]) -> list[Warning]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Warning] = []
    for warning in warnings:
        key = (
            warning.get("code", ""),
            warning.get("field", ""),
            warning.get("message", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return deduped
