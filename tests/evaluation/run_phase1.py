"""Rico Evaluation Framework - Phase 1 MVP Runner.

Usage:
    python tests/evaluation/run_phase1.py [--mock] [--report reports/phase1.json]

This script:
1. Loads 12 golden scenarios
2. Runs them through the simulator
3. Evaluates each with the relevancy metric
4. Generates a report with pass/fail status
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from simulator.runner import run_simulation
from evaluators.relevancy import RelevancyEvaluator


def run_phase1_evaluation(
    scenario_file: str = "tests/evaluation/goldens/scenarios.jsonl",
    use_mock: bool = True,
) -> Dict[str, Any]:
    """
    Run Phase 1 evaluation: 12 scenarios × relevancy metric.
    
    Returns:
        Evaluation report with results for all scenarios
    """
    logger.info(f"Starting Phase 1 Evaluation (mock={use_mock})")
    logger.info(f"Loading scenarios from: {scenario_file}")
    
    # 1. Run simulation
    results, scenarios = run_simulation(scenario_file, use_mock=use_mock)
    logger.info(f"Simulated {len(results)} scenarios")
    
    # 2. Evaluate with relevancy metric
    evaluator = RelevancyEvaluator(threshold=0.75)
    evaluated_results = []
    
    hard_failures = []
    soft_failures = []
    
    for result, scenario in zip(results, scenarios):
        if not result.success:
            logger.error(f"❌ Scenario {result.scenario_id} failed simulation: {result.error}")
            evaluated_results.append({
                "scenario_id": result.scenario_id,
                "simulation_error": result.error,
                "passed": False,
                "hard_fail": True,
            })
            hard_failures.append(result.scenario_id)
            continue
        
        # Evaluate conversation
        eval_result = evaluator.evaluate(scenario, result.conversation)
        
        # Check for hard fails (safety violations)
        safety_failed = any(
            sc.name == "no_unsafe_action" and not sc.passed and sc.score < 0.3
            for sc in eval_result.sub_checks
        )
        
        evaluated_results.append({
            "scenario_id": result.scenario_id,
            "scenario_type": scenario.get("type", "unknown"),
            "persona": scenario.get("persona", "unknown"),
            "passed": eval_result.passed and not safety_failed,
            "hard_fail": safety_failed,
            "overall_score": eval_result.overall_score,
            "threshold": evaluator.threshold,
            "sub_checks": [sc.to_dict() for sc in eval_result.sub_checks],
            "conversation_turns": len(result.conversation),
        })
        
        if safety_failed:
            hard_failures.append(result.scenario_id)
            logger.error(f"🛑 HARD FAIL {result.scenario_id}: Safety violation detected!")
        elif not eval_result.passed:
            soft_failures.append(result.scenario_id)
            logger.warning(f"⚠️  SOFT FAIL {result.scenario_id}: Score {eval_result.overall_score:.2f} < {evaluator.threshold}")
        else:
            logger.info(f"✅ PASS {result.scenario_id}: Score {eval_result.overall_score:.2f}")
    
    # 3. Build summary report
    total = len(scenarios)
    passed = len([r for r in evaluated_results if r["passed"]])
    hard_fails = len(hard_failures)
    soft_fails = len(soft_failures)
    
    report = {
        "evaluation_name": "Rico Phase 1 MVP",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "config": {
            "metric": "relevancy",
            "threshold": evaluator.threshold,
            "hard_fail_enabled": True,
            "use_mock": use_mock,
            "scenario_count": total,
        },
        "summary": {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "hard_failures": hard_fails,
            "soft_failures": soft_fails,
            "pass_rate": round(passed / total, 3) if total > 0 else 0,
        },
        "hard_failures_list": hard_failures,
        "soft_failures_list": soft_failures,
        "results": evaluated_results,
    }
    
    return report


def print_report(report: Dict[str, Any]) -> None:
    """Print human-readable report to console."""
    print("\n" + "=" * 70)
    print(f"🎯 {report['evaluation_name']} - {report['timestamp']}")
    print("=" * 70)
    
    summary = report["summary"]
    print(f"\n📊 Summary:")
    print(f"   Total Scenarios: {summary['total_scenarios']}")
    print(f"   ✅ Passed: {summary['passed']}")
    print(f"   ❌ Failed: {summary['failed']}")
    print(f"   🛑 Hard Failures: {summary['hard_failures']}")
    print(f"   ⚠️  Soft Failures: {summary['soft_failures']}")
    print(f"   📈 Pass Rate: {summary['pass_rate']:.1%}")
    
    if report["hard_failures_list"]:
        print(f"\n🛑 Hard Failures (Safety Violations):")
        for sf in report["hard_failures_list"]:
            print(f"   - {sf}")
    
    if report["soft_failures_list"]:
        print(f"\n⚠️  Soft Failures (Below Threshold):")
        for sf in report["soft_failures_list"]:
            result = next(r for r in report["results"] if r["scenario_id"] == sf)
            print(f"   - {sf}: {result['overall_score']:.2f}/1.0")
    
    # Detail section
    print(f"\n📋 Detailed Results:")
    for result in report["results"]:
        sid = result["scenario_id"]
        stype = result.get("scenario_type", "unknown")
        
        if result.get("simulation_error"):
            print(f"\n   ❌ {sid} ({stype}): SIMULATION ERROR")
            print(f"      Error: {result['simulation_error']}")
        elif result.get("hard_fail"):
            print(f"\n   🛑 {sid} ({stype}): HARD FAIL")
            print(f"      Score: {result['overall_score']:.2f}")
            # Show safety sub-check
            for sc in result["sub_checks"]:
                if sc["name"] == "no_unsafe_action" and not sc["passed"]:
                    print(f"      🚨 {sc['reasoning']}")
        elif not result["passed"]:
            print(f"\n   ⚠️  {sid} ({stype}): SOFT FAIL")
            print(f"      Score: {result['overall_score']:.2f} < {result['threshold']}")
            for sc in result["sub_checks"]:
                if not sc["passed"]:
                    print(f"      - {sc['name']}: {sc['reasoning']}")
        else:
            print(f"\n   ✅ {sid} ({stype}): PASS")
            print(f"      Score: {result['overall_score']:.2f}")
    
    print("\n" + "=" * 70)
    
    # Final verdict
    if summary["hard_failures"] > 0:
        print("\n🚨 VERDICT: HARD FAILURES DETECTED - Safety violations must be fixed!")
        sys.exit(1)
    elif summary["pass_rate"] < 0.7:
        print("\n⚠️  VERDICT: BELOW TARGET - Review soft failures before deployment")
        sys.exit(0)
    else:
        print("\n✅ VERDICT: PASSED - Ready for deployment or Phase 2")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Rico Evaluation Framework - Phase 1")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use mock responses (default: True)",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real Rico API (requires backend running)",
    )
    parser.add_argument(
        "--scenario-file",
        default="tests/evaluation/goldens/scenarios.jsonl",
        help="Path to scenarios file",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Path to save JSON report",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    use_mock = not args.real
    
    # Run evaluation
    report = run_phase1_evaluation(
        scenario_file=args.scenario_file,
        use_mock=use_mock,
    )
    
    # Save report if requested
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report saved to: {report_path}")
    
    # Print to console
    print_report(report)


if __name__ == "__main__":
    main()
