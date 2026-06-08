"""Conversation simulator for Rico evaluation.

Provides:
- ScenarioRunner: Run golden scenarios against Rico
- SimulationResult: Captured conversation data
- Mock mode for testing without backend
"""

from .runner import ScenarioRunner, SimulationResult, run_simulation

__all__ = ["ScenarioRunner", "SimulationResult", "run_simulation"]
