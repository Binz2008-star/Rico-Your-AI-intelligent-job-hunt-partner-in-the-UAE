"""Rico Evaluation Framework - Phase 1 MVP.

This package provides:
- Golden scenarios for testing Rico chat behavior
- Scenario-driven conversation simulator
- Relevancy evaluator with sub-checks breakdown
- Report generation and analysis

Usage:
    from tests.evaluation import run_phase1_evaluation
    report = run_phase1_evaluation()
    
Or from command line:
    python tests/evaluation/run_phase1.py --mock
"""

from .run_phase1 import run_phase1_evaluation

__all__ = ["run_phase1_evaluation"]
