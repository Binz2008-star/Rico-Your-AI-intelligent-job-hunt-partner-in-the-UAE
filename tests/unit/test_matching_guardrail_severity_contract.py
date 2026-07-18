"""Exhaustive contract tests for the matching-guardrail warning severity tiers.

The backend is the single source of truth for warning severity (Profile
Phase 4A). Every code the guardrail module can emit must:

- carry exactly one of the three approved severities
  (``blocking`` / ``important`` / ``recommendation``);
- map to its canonical editable field;
- keep the bilingual message contract (message / message_ar / suggestion /
  suggestion_ar all present and non-empty);
- never fall back to the retired ambiguous ``warning`` tier.

If a new warning code is added without registering severity + field in
``WARNING_SEVERITY_BY_CODE`` / ``WARNING_FIELD_BY_CODE``, these tests fail.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from src.services.matching_guardrails import (
    ALL_WARNING_CODES,
    WARNING_FIELD_BY_CODE,
    WARNING_SEVERITY_BY_CODE,
    WarningSeverity,
    build_matching_guardrail_warnings,
    severity_for_code,
)

APPROVED_SEVERITIES = {"blocking", "important", "recommendation"}

# Crafted inputs that make the module emit every declared warning code at once.
# `manager` as an exclusion overlaps the included keyword AND the target role;
# `esg` blocks a core role word without overlapping a role; min_score > 60,
# a non-UAE city, and 4 target roles trigger the remaining three codes.
_EMIT_ALL_SETTINGS = {
    "include_keywords": ["operation manager"],
    "exclude_keywords": ["manager", "esg"],
    "min_score": 80,
}
_EMIT_ALL_PROFILE = SimpleNamespace(
    target_roles=[
        "Operations Manager",
        "Compliance Officer",
        "HSE Officer",
        "Environmental Officer",
    ],
    preferred_cities=["Cairo"],
)


def _emit_all_warnings() -> list[dict[str, str]]:
    return build_matching_guardrail_warnings(
        settings=_EMIT_ALL_SETTINGS,
        profile=_EMIT_ALL_PROFILE,
    )


def test_crafted_inputs_emit_every_declared_code() -> None:
    """The scenario above is exhaustive: all declared codes actually fire."""
    emitted = {w["code"] for w in _emit_all_warnings()}
    assert emitted == set(ALL_WARNING_CODES), (
        "Contract scenario no longer triggers every declared code — update the "
        f"scenario or the contract. Missing: {set(ALL_WARNING_CODES) - emitted}; "
        f"unexpected: {emitted - set(ALL_WARNING_CODES)}"
    )


def test_contract_maps_are_complete_and_aligned() -> None:
    """Severity and field maps cover exactly the same code set."""
    assert set(WARNING_SEVERITY_BY_CODE) == set(WARNING_FIELD_BY_CODE)
    assert set(ALL_WARNING_CODES) == set(WARNING_SEVERITY_BY_CODE)
    assert len(ALL_WARNING_CODES) == len(set(ALL_WARNING_CODES))


def test_every_emitted_warning_has_an_approved_severity() -> None:
    for warning in _emit_all_warnings():
        assert warning["severity"] in APPROVED_SEVERITIES, warning["code"]
        # And it is exactly the registered contract value, not a recomputation.
        assert warning["severity"] == WARNING_SEVERITY_BY_CODE[warning["code"]].value


def test_no_warning_uses_the_retired_ambiguous_tier() -> None:
    for warning in _emit_all_warnings():
        assert warning["severity"] != "warning", (
            f"{warning['code']} still emits the retired ambiguous 'warning' tier"
        )


def test_every_emitted_warning_field_matches_the_contract() -> None:
    for warning in _emit_all_warnings():
        assert warning["field"] == WARNING_FIELD_BY_CODE[warning["code"]], (
            f"{warning['code']} emitted field {warning['field']!r}, contract says "
            f"{WARNING_FIELD_BY_CODE[warning['code']]!r}"
        )


def test_bilingual_message_contract_is_preserved() -> None:
    """code/field/message/message_ar/suggestion/suggestion_ar all present."""
    for warning in _emit_all_warnings():
        for key in ("code", "field", "message", "message_ar", "suggestion", "suggestion_ar"):
            value = warning.get(key)
            assert isinstance(value, str) and value.strip(), (
                f"{warning.get('code')}: {key} missing or empty"
            )


def test_specific_severity_assignments_are_pinned() -> None:
    """Re-tiering a warning is a product decision — pin the current contract."""
    assert WARNING_SEVERITY_BY_CODE == {
        "excluded_keyword_blocks_target_role": WarningSeverity.BLOCKING,
        "invalid_uae_city": WarningSeverity.BLOCKING,
        "excluded_keyword_overlaps_included_keyword": WarningSeverity.IMPORTANT,
        "excluded_keyword_blocks_core_role_word": WarningSeverity.IMPORTANT,
        "minimum_fit_score_high": WarningSeverity.IMPORTANT,
        "too_many_target_roles": WarningSeverity.RECOMMENDATION,
    }


def test_severity_enum_values_are_exactly_the_approved_set() -> None:
    assert {member.value for member in WarningSeverity} == APPROVED_SEVERITIES


def test_unknown_code_fails_safe_and_loudly(caplog) -> None:
    """An unmapped code must not crash: it logs and resolves to IMPORTANT."""
    with caplog.at_level(logging.ERROR, logger="src.services.matching_guardrails"):
        severity = severity_for_code("nonexistent_future_code")
    assert severity is WarningSeverity.IMPORTANT
    assert any("severity contract violation" in rec.message for rec in caplog.records)


def test_empty_inputs_emit_no_warnings() -> None:
    assert build_matching_guardrail_warnings(settings={}, profile=None) == []
