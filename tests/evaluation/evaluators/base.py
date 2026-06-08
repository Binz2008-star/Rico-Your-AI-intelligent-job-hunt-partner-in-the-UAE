"""Base evaluator with sub-checks breakdown for Rico evaluation framework."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SubCheck:
    """Individual sub-check with score and reasoning."""
    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    reasoning: str
    weight: float = 1.0  # Weight for overall calculation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "passed": self.passed,
            "reasoning": self.reasoning,
            "weight": self.weight,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result with breakdown."""
    metric_name: str
    overall_score: float  # 0.0 to 1.0
    passed: bool
    sub_checks: List[SubCheck]
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "overall_score": round(self.overall_score, 3),
            "passed": self.passed,
            "sub_checks": [
                {
                    "name": sc.name,
                    "score": round(sc.score, 3),
                    "passed": sc.passed,
                    "reasoning": sc.reasoning,
                    "weight": sc.weight,
                }
                for sc in self.sub_checks
            ],
            "raw_data": self.raw_data,
        }


class BaseEvaluator(ABC):
    """Base class for all Rico evaluators."""

    def __init__(self, threshold: float = 0.8, hard_fail: bool = False):
        self.threshold = threshold
        self.hard_fail = hard_fail
        self.metric_name = self.__class__.__name__.replace("Evaluator", "").lower()

    @abstractmethod
    def evaluate(self, scenario: Dict[str, Any], conversation: List[Dict[str, Any]]) -> EvaluationResult:
        """
        Evaluate a scenario against conversation history.

        Args:
            scenario: The golden scenario definition
            conversation: List of turns with user/assistant messages

        Returns:
            EvaluationResult with sub-checks breakdown
        """
        pass

    def _calculate_overall(self, sub_checks: List[SubCheck]) -> float:
        """Calculate weighted overall score from sub-checks."""
        if not sub_checks:
            return 0.0

        total_weight = sum(sc.weight for sc in sub_checks)
        weighted_sum = sum(sc.score * sc.weight for sc in sub_checks)

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _check_threshold(self, score: float) -> bool:
        """Check if score meets threshold."""
        return score >= self.threshold

    def get_summary(self, result: EvaluationResult) -> str:
        """Get human-readable summary of evaluation."""
        status = "✅ PASS" if result.passed else "❌ FAIL"
        if self.hard_fail and not result.passed:
            status = "🛑 HARD FAIL"

        lines = [
            f"{status} {self.metric_name}: {result.overall_score:.2f}/1.0",
            f"  Threshold: {self.threshold}",
        ]

        for sc in result.sub_checks:
            check_status = "✅" if sc.passed else "❌"
            lines.append(f"  {check_status} {sc.name}: {sc.score:.2f} - {sc.reasoning}")

        return "\n".join(lines)
