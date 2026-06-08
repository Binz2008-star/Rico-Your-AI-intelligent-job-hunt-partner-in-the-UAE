"""Pytest configuration for Rico evaluation framework.

Fixtures:
- scenarios: Load all golden scenarios
- evaluator: Pre-configured relevancy evaluator
- runner: Scenario runner instance
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from simulator.runner import ScenarioRunner
from evaluators.relevancy import RelevancyEvaluator


@pytest.fixture(scope="session")
def scenarios_path() -> Path:
    """Path to golden scenarios file."""
    return Path(__file__).parent / "goldens" / "scenarios.jsonl"


@pytest.fixture(scope="session")
def scenarios(scenarios_path: Path) -> List[Dict[str, Any]]:
    """Load all golden scenarios."""
    if not scenarios_path.exists():
        pytest.fail(f"Scenarios file not found: {scenarios_path}")
    
    loaded = []
    with open(scenarios_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                loaded.append(json.loads(line))
    
    return loaded


@pytest.fixture
def evaluator() -> RelevancyEvaluator:
    """Pre-configured relevancy evaluator."""
    return RelevancyEvaluator(threshold=0.75)


@pytest.fixture
def mock_runner() -> ScenarioRunner:
    """Scenario runner in mock mode."""
    return ScenarioRunner(use_mock=True)


@pytest.fixture
def reports_dir() -> Path:
    """Reports output directory."""
    path = Path(__file__).parent / "reports"
    path.mkdir(exist_ok=True)
    return path
