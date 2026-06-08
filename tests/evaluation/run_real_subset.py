"""Real Rico Backend Test - 5 Key Scenarios

Tests the 3 weak scenarios + 2 strong ones against actual Rico API.
"""
from __future__ import annotations

import json
import os
import requests
import time
from datetime import datetime
from typing import Any, Dict, List

# Rico API endpoint - configurable via env var for local testing
RICO_API = os.environ.get("RICO_API_BASE_URL", "https://rico-job-automation-api.onrender.com")
TEST_USER = "eval@rico.ai"

def call_rico_chat(message: str, session_id: str, user_email: str = None, history: List = None) -> Dict[str, Any]:
    """Call Rico chat API."""
    url = f"{RICO_API}/api/v1/rico/chat"

    # Use public endpoint if no auth
    if user_email is None:
        url = f"{RICO_API}/api/v1/rico/chat/public"
        payload = {
            "message": message,
            "session_id": session_id,
            "email": None,
            "operation_id": f"eval_{int(time.time() * 1000)}",
            "language": "en"
        }
    else:
        # For authenticated calls, we'd need JWT
        # For now, use public endpoint
        url = f"{RICO_API}/api/v1/rico/chat/public"
        payload = {
            "message": message,
            "session_id": session_id,
            "email": user_email,
            "operation_id": f"eval_{int(time.time() * 1000)}",
            "language": "en" if not any('\u0600' <= c <= '\u06FF' for c in message) else "ar"
        }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "message": f"API Error: {str(e)}"}


def run_scenario_real(scenario: Dict) -> Dict[str, Any]:
    """Run a single scenario against real Rico."""
    sid = scenario["id"]
    turns = scenario["turns"]
    session_id = f"eval_{sid}_{int(time.time())}"

    print(f"\n{'='*60}")
    print(f"🎯 Scenario: {sid} ({scenario.get('type', 'unknown')})")
    print(f"   Goal: {scenario.get('goal', 'N/A')}")
    print(f"{'='*60}")

    conversation = []
    all_responses = []

    for i, turn in enumerate(turns):
        user_msg = turn.get("user", "")
        print(f"\n📝 Turn {i+1}:")
        print(f"   User: {user_msg[:80]}...")

        # Call Rico
        response = call_rico_chat(
            message=user_msg,
            session_id=session_id,
            user_email=TEST_USER,
            history=conversation
        )

        assistant_msg = response.get("message", "")
        all_responses.append(assistant_msg)

        print(f"   Rico: {assistant_msg[:100]}...")
        print(f"   Response type: {response.get('type', 'unknown')}")
        print(f"   Source: {response.get('response_source', 'unknown')}")

        conversation.append({
            "turn": i+1,
            "user": user_msg,
            "assistant": assistant_msg,
            "expected_intent": turn.get("expected_intent"),
        })

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    return {
        "scenario_id": sid,
        "conversation": conversation,
        "all_responses": all_responses,
        "session_id": session_id,
    }


def main():
    print("=" * 70)
    print("🚀 Rico Real Backend Test - 5 Critical Scenarios")
    print("=" * 70)
    print(f"API: {RICO_API}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    # Check health first
    try:
        health = requests.get(f"{RICO_API}/health", timeout=10)
        print(f"✅ Rico Health: {health.json()}")
    except Exception as e:
        print(f"❌ Rico unavailable: {e}")
        return

    # Load subset
    scenarios = []
    with open("tests/evaluation/goldens/real_test_subset.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                scenarios.append(json.loads(line))

    print(f"\n📋 Loaded {len(scenarios)} scenarios for real test")

    # Run each scenario
    results = []
    for scenario in scenarios:
        result = run_scenario_real(scenario)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Complete - Summary")
    print("=" * 70)

    for r in results:
        sid = r["scenario_id"]
        print(f"\n✅ {sid}: {len(r['conversation'])} turns completed")

    # Save raw results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"tests/evaluation/reports/real_test_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api": RICO_API,
            "scenarios_tested": len(scenarios),
            "results": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Raw results saved to: {report_path}")
    print("\n⚠️  NOTE: Manual evaluation needed - compare responses to expected_contains")
    print("   in scenarios.jsonl to assess quality.")


if __name__ == "__main__":
    main()
