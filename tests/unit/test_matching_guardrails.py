from types import SimpleNamespace

from src.services.matching_guardrails import (
    build_matching_guardrail_warnings,
    is_uae_city,
)


def _codes(warnings: list[dict[str, str]]) -> set[str]:
    return {warning["code"] for warning in warnings}


def test_warns_when_excluded_keyword_overlaps_included_keyword() -> None:
    warnings = build_matching_guardrail_warnings(
        settings={
            "include_keywords": ["operation manager"],
            "exclude_keywords": ["manager"],
            "min_score": 50,
        },
        profile=SimpleNamespace(target_roles=[], preferred_cities=["Dubai"]),
    )

    assert "excluded_keyword_overlaps_included_keyword" in _codes(warnings)


def test_warns_when_excluded_keyword_blocks_target_role_words() -> None:
    warnings = build_matching_guardrail_warnings(
        settings={
            "include_keywords": [],
            "exclude_keywords": ["manager", "HSE", "compliance"],
            "min_score": 50,
        },
        profile=SimpleNamespace(
            target_roles=["Operations Manager", "HSE Manager"],
            preferred_cities=["Dubai"],
        ),
    )

    codes = _codes(warnings)
    assert "excluded_keyword_blocks_target_role" in codes
    assert any("Operations Manager" in warning["message"] for warning in warnings)
    assert any("HSE" in warning["message"] for warning in warnings)


def test_warns_when_minimum_fit_score_is_above_sixty() -> None:
    warnings = build_matching_guardrail_warnings(
        settings={"min_score": 80},
        profile=SimpleNamespace(target_roles=["Environmental Manager"], preferred_cities=["Dubai"]),
    )

    assert "minimum_fit_score_high" in _codes(warnings)


def test_warns_when_city_is_invalid_or_not_uae_city() -> None:
    warnings = build_matching_guardrail_warnings(
        settings={"min_score": 50},
        profile=SimpleNamespace(target_roles=["Environmental Manager"], preferred_cities=["نعم"]),
    )

    assert "invalid_uae_city" in _codes(warnings)
    assert is_uae_city("Dubai")
    assert is_uae_city("دبي")
    assert not is_uae_city("نعم")


def test_warns_when_target_roles_exceed_three() -> None:
    warnings = build_matching_guardrail_warnings(
        settings={"min_score": 50},
        profile=SimpleNamespace(
            target_roles=[
                "Environmental Manager",
                "ESG Manager",
                "HSE Manager",
                "Compliance Manager",
            ],
            preferred_cities=["Abu Dhabi"],
        ),
    )

    assert "too_many_target_roles" in _codes(warnings)
    assert any("up to 3 primary roles" in warning["suggestion"] for warning in warnings)
