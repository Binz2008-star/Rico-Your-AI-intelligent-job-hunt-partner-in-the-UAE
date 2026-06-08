"""Evaluators for Rico conversation quality.

Available evaluators:
- RelevancyEvaluator: Check if responses are relevant and safe

All evaluators inherit from BaseEvaluator and provide:
- Sub-checks breakdown for diagnosis
- Weighted scoring
- Pass/fail determination
"""

from .base import BaseEvaluator, EvaluationResult, SubCheck
from .relevancy import RelevancyEvaluator

__all__ = [
    "BaseEvaluator",
    "EvaluationResult", 
    "SubCheck",
    "RelevancyEvaluator",
]
