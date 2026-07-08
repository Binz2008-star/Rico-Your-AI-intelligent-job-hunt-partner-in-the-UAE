from __future__ import annotations

from src.mutation_guard import MutationConfirmationGuard, MutationResult


SUCCESS_EN = "Saved successfully."
SUCCESS_AR = "تم الحفظ بنجاح."
FAIL_EN = "I understood your request but could not complete it. Your data still appears unchanged in the backend."
FAIL_AR = "فهمت طلبك لكن لم أستطع تنفيذ التغيير، البيانات ما زالت كما هي في النظام."


def _guard() -> MutationConfirmationGuard:
    return MutationConfirmationGuard()


def test_success_copy_requires_write_success_and_readback() -> None:
    message = _guard().confirm(
        MutationResult(success=True, affected_count=1, persisted_ids=["job-1"]),
        verifier=lambda: True,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == SUCCESS_EN


def test_write_failure_returns_honest_failure_copy() -> None:
    message = _guard().confirm(
        MutationResult(success=False, affected_count=1),
        verifier=lambda: True,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == FAIL_EN
    assert "success" not in message.lower()


def test_zero_affected_rows_returns_failure_even_if_verifier_passes() -> None:
    message = _guard().confirm(
        MutationResult(success=True, affected_count=0),
        verifier=lambda: True,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == FAIL_EN


def test_readback_failure_returns_failure_even_if_write_succeeds() -> None:
    message = _guard().confirm(
        MutationResult(success=True, affected_count=1),
        verifier=lambda: False,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == FAIL_EN


def test_verifier_exception_returns_failure_not_success() -> None:
    def broken_verifier() -> bool:
        raise RuntimeError("read path unavailable")

    message = _guard().confirm(
        MutationResult(success=True, affected_count=1),
        verifier=broken_verifier,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == FAIL_EN


def test_arabic_failure_copy_is_used_for_failed_readback() -> None:
    message = _guard().confirm(
        MutationResult(success=True, affected_count=1),
        verifier=lambda: False,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
        lang="ar",
    )

    assert message == FAIL_AR
    assert "تم الحفظ" not in message


def test_affected_count_is_optional_for_create_upsert_paths() -> None:
    message = _guard().confirm(
        MutationResult(success=True),
        verifier=lambda: True,
        success_en=SUCCESS_EN,
        success_ar=SUCCESS_AR,
        failure_en=FAIL_EN,
        failure_ar=FAIL_AR,
    )

    assert message == SUCCESS_EN
