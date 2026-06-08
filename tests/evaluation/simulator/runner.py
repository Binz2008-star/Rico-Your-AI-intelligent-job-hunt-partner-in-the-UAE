"""Scenario-driven conversation simulator for Rico evaluation."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Result of running a scenario simulation."""
    scenario_id: str
    success: bool
    conversation: List[Dict[str, str]]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScenarioRunner:
    """
    Run golden scenarios against Rico API.
    
    This simulator:
    1. Loads scenarios from goldens/
    2. Runs each turn through Rico chat API
    3. Captures responses
    4. Returns full conversation history for evaluation
    """
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        user_email: str = "eval@rico.ai",
        use_mock: bool = True,
    ):
        self.api_base_url = api_base_url
        self.user_email = user_email
        self.use_mock = use_mock
        self.session_id = str(uuid.uuid4())
        
        # Import RicoChatAPI if available
        self._rico_api = None
        if not use_mock:
            try:
                from src.rico_chat_api import RicoChatAPI
                self._rico_api = RicoChatAPI()
            except ImportError:
                logger.warning("RicoChatAPI not available, falling back to mock mode")
                self.use_mock = True
    
    def load_scenario(self, scenario_path: str) -> List[Dict[str, Any]]:
        """Load scenarios from JSONL file."""
        scenarios = []
        try:
            with open(scenario_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        scenarios.append(json.loads(line))
        except FileNotFoundError:
            logger.error(f"Scenario file not found: {scenario_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in scenario file: {e}")
        
        return scenarios
    
    def run_scenario(self, scenario: Dict[str, Any]) -> SimulationResult:
        """
        Run a single scenario through Rico.
        
        Args:
            scenario: Golden scenario with persona, goal, and turns
            
        Returns:
            SimulationResult with conversation history
        """
        scenario_id = scenario.get("id", "unknown")
        turns = scenario.get("turns", [])
        
        if not turns:
            return SimulationResult(
                scenario_id=scenario_id,
                success=False,
                conversation=[],
                error="No turns in scenario",
            )
        
        conversation = []
        
        try:
            for i, turn in enumerate(turns):
                user_msg = turn.get("user", "")
                if not user_msg:
                    continue
                
                # Get response from Rico (or mock)
                if self.use_mock:
                    assistant_msg = self._mock_response(turn, conversation)
                else:
                    assistant_msg = self._call_rico_api(user_msg, conversation)
                
                # Record the turn
                conversation.append({
                    "turn": i + 1,
                    "user": user_msg,
                    "assistant": assistant_msg,
                    "expected_intent": turn.get("expected_intent"),
                })
                
                logger.debug(f"Turn {i+1}: user='{user_msg[:50]}...' -> assistant='{assistant_msg[:50]}...'")
            
            return SimulationResult(
                scenario_id=scenario_id,
                success=True,
                conversation=conversation,
                metadata={
                    "turn_count": len(turns),
                    "scenario_type": scenario.get("type"),
                    "persona": scenario.get("persona"),
                }
            )
            
        except Exception as e:
            logger.exception(f"Simulation failed for scenario {scenario_id}")
            return SimulationResult(
                scenario_id=scenario_id,
                success=False,
                conversation=conversation,
                error=str(e),
            )
    
    def run_all(
        self,
        scenarios: List[Dict[str, Any]],
        stop_on_error: bool = False,
    ) -> List[SimulationResult]:
        """Run all scenarios and return results."""
        results = []
        
        for scenario in scenarios:
            result = self.run_scenario(scenario)
            results.append(result)
            
            if not result.success and stop_on_error:
                logger.error(f"Stopping on error in scenario: {result.scenario_id}")
                break
        
        return results
    
    def _mock_response(self, turn: Dict[str, Any], conversation: List[Dict]) -> str:
        """Generate mock response for testing without Rico API."""
        expected_intent = turn.get("expected_intent", "")
        expected_contains = turn.get("expected_contains", [])
        scenario_type = turn.get("type", "")
        
        # Generate contextual mock responses
        if expected_intent == "job_search_explicit":
            return f"I found 5 software jobs in Dubai with match scores from 72% to 91%. Would you like me to show the top matches?"
        
        elif expected_intent == "explain_match_score":
            return "This job has an 87% match because your Python and React skills align perfectly with the requirements. You also have 3 years of relevant experience."
        
        elif expected_intent == "update_settings":
            return "I've updated your settings to disable auto-apply. You'll now need to confirm each application manually."
        
        elif expected_intent == "schedule_followup":
            days = turn.get("expected_entities", {}).get("days", 3)
            return f"I'll remind you about this job in {days} days. Is there anything specific you want me to check when I follow up?"
        
        elif expected_intent == "open_apply_link":
            return "I'll open the apply link for you. The application is at https://company.com/careers/job123"
        
        elif expected_intent == "save_job":
            return "I've saved this HSE Manager job at AESG for you. You can find it in your saved jobs."
        
        elif expected_intent == "help_general":
            return "I can help you with job search, CV optimization, application tracking, and career advice. What would you like to do?"
        
        elif expected_intent == "cv_uploaded":
            return "I've received your CV. I can see some of your skills and experience. To give you better job matches, could you also tell me about your target roles and preferred locations?"
        
        elif expected_intent == "out_of_scope":
            return "I can help you with job search and career-related questions. For weather updates, I'd recommend checking a weather app or website."
        
        elif expected_intent == "bulk_apply_unsafe":
            return "I can't automatically apply to all jobs without your review. I can help you review each job individually and apply with your confirmation. Would you like to see the first job?"
        
        else:
            # Generic response with expected keywords
            if expected_contains:
                return f"I understand. Let me help you with that. This involves: {', '.join(expected_contains[:3])}."
            return "I understand your request. Let me help you with that."
    
    def _call_rico_api(self, user_msg: str, conversation: List[Dict]) -> str:
        """Call actual Rico chat API."""
        if self._rico_api is None:
            raise RuntimeError("Rico API not initialized")
        
        # Build context from conversation history
        context = {
            "session_id": self.session_id,
            "user_email": self.user_email,
            "conversation_history": [
                {"role": "user" if i % 2 == 0 else "assistant", "content": turn["user" if i % 2 == 0 else "assistant"]}
                for i, turn in enumerate(conversation)
            ]
        }
        
        # Call Rico API
        # Note: This is a simplified version - actual implementation would need
        # to match Rico's API signature
        try:
            result = self._rico_api.process_message(
                user_id=self.user_email,
                message=user_msg,
                context=context,
            )
            return result.get("message", "")
        except Exception as e:
            logger.exception("Rico API call failed")
            return f"[Error: {str(e)}]"


def run_simulation(
    scenario_file: str = "tests/evaluation/goldens/scenarios.jsonl",
    use_mock: bool = True,
) -> Tuple[List[SimulationResult], List[Dict[str, Any]]]:
    """
    Convenience function to run simulation.
    
    Returns:
        Tuple of (results, scenarios)
    """
    runner = ScenarioRunner(use_mock=use_mock)
    scenarios = runner.load_scenario(scenario_file)
    results = runner.run_all(scenarios)
    return results, scenarios
