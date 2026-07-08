"""Mutation confirmation guard for user-facing success copy.

Issue #764: Rico must never claim that a mutation succeeded unless the write
reported success and the changed state is visible through the product's read
path.

The guard is intentionally persistence-agnostic. Callers perform the write,
construct a MutationResult, and provide a read-after-write verifier callback
that checks the same path the user will later read from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass(frozen=True)
class MutationResult:
    """Result of a mutation before user-facing confirmation is emitted.

    success:
        Whether the underlying write operation reported success.
    affected_count:
        Optional row/object count for UPDATE/DELETE style mutations. When
        supplied it must be greater than zero to allow success copy.
    persisted_ids:
        Optional identifiers returned by the write path for diagnostics/tests.
    error:
        Optional error text for logs or future structured response handling.
    """

    success: bool
    affected_count: Optional[int] = None
    persisted_ids: List[str] = field(default_factory=list)
    error: Optional[str] = None


class MutationConfirmationGuard:
    """Gate success/failure copy for persisted mutations.

    Success copy is allowed only when all required checks pass:
    1. The write reported success.
    2. affected_count is absent or greater than zero.
    3. The verifier confirms read-after-write visibility.

    The verifier must use the correct product read path. For example:
    - saved job -> saved/applications read path finds the job
    - delete saved job -> read path confirms absence
    - mark applied -> read path confirms status == "applied"
    - profile update -> profile read path returns the expected value
    """

    def confirm(
        self,
        result: MutationResult,
        verifier: Callable[[], bool],
        success_en: str,
        success_ar: str,
        failure_en: str,
        failure_ar: str,
        lang: str = "en",
    ) -> str:
        """Return success copy only after write + affected-count + read-back.

        The method deliberately catches verifier exceptions and treats them as
        confirmation failure. A broken read-back path must never produce success
        language for the user.
        """

        failure = failure_ar if lang == "ar" else failure_en
        success = success_ar if lang == "ar" else success_en

        if not result.success:
            return failure

        if result.affected_count is not None and result.affected_count <= 0:
            return failure

        try:
            if not verifier():
                return failure
        except Exception:
            return failure

        return success
