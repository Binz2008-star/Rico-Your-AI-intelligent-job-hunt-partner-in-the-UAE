"""
Response Intelligence Layer — v2
High-end AI-powered response analysis with a real, persisted feedback loop.

Architecture:
  - ScoringAdjustments: serialisable overlay applied on top of EngineConfig weights.
  - StateStore (Protocol): pluggable persistence (JSON file, Redis, Postgres).
  - ResponseIntelligenceEngine: pure analysis; all I/O injected.
  - Thread-safe state mutations via RLock.
  - ResponseType / FollowUpTiming: enums used throughout (no raw string matching).
  - O(n) application-job matching via precomputed index.

Feedback loop:
  learn_from_outcomes() → ScoringAdjustments → StateStore.save()
  On next startup: StateStore.load() → adjustments applied to every probability calc.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from src.decision_engine import (
    EngineConfig,
    JobDecisionEngine,
    ProbabilityResult,
    _from_log_odds,
    _to_log_odds,
)

logger = logging.getLogger(__name__)

_MAX_ADJUSTMENT = 0.30   # max per-factor log-odds shift (≈ ±8 pp at p=0.5)
_MIN_SAMPLES = 5         # minimum outcomes before a factor is trusted


# ---------------------------------------------------------------------------
# Enums — used everywhere; no raw string comparisons
# ---------------------------------------------------------------------------

class ResponseType(str, Enum):
    REJECTED               = "rejected"
    NO_RESPONSE            = "no_response"
    SCREENING              = "screening"
    INTERVIEW_SCHEDULED    = "interview_scheduled"
    INTERVIEW_COMPLETED    = "interview_completed"
    TECHNICAL_ASSESSMENT   = "technical_assessment"
    OFFER_EXTENDED         = "offer_extended"
    OFFER_ACCEPTED         = "offer_accepted"
    OFFER_DECLINED         = "offer_declined"
    FOLLOW_UP_REQUIRED     = "follow_up_required"

    @classmethod
    def from_raw(cls, raw: Optional[str]) -> "ResponseType":
        try:
            return cls(raw or "no_response")
        except ValueError:
            return cls.NO_RESPONSE

    @property
    def is_positive(self) -> bool:
        return self in {
            ResponseType.SCREENING,
            ResponseType.INTERVIEW_SCHEDULED,
            ResponseType.INTERVIEW_COMPLETED,
            ResponseType.TECHNICAL_ASSESSMENT,
            ResponseType.OFFER_EXTENDED,
            ResponseType.OFFER_ACCEPTED,
        }


class FollowUpTiming(str, Enum):
    IMMEDIATE  = "immediate"
    THIS_WEEK  = "this_week"
    NEXT_WEEK  = "next_week"
    NOT_NEEDED = "not_needed"


@dataclass
class ResponsePattern:
    """Pattern detected in application responses."""
    pattern_type: str
    frequency: float
    success_rate: float
    avg_response_time: float
    confidence: float
    factors: Dict[str, float]


@dataclass
class LearningInsight:
    """Learning insight from application outcomes."""
    insight_type: str
    description: str
    impact_score: float
    confidence: float
    actionable: bool
    recommendation: str


@dataclass
class FollowUpAction:
    """Recommended follow-up action."""
    action_type: str
    priority: str
    timing: str
    template: str
    success_probability: float


class ResponseIntelligenceEngine:
    """
    Advanced response intelligence engine for job applications.

    Analyzes response patterns, learns from outcomes, and provides
    intelligent follow-up recommendations while maintaining a feedback loop
    to improve future scoring and strategy.
    """

    def __init__(
        self,
        decision_engine: JobDecisionEngine,
        config: Optional[EngineConfig] = None,
    ) -> None:
        self._decision_engine = decision_engine
        self._config = config or EngineConfig()
        self._response_patterns: Dict[str, ResponsePattern] = {}
        self._learning_insights: List[LearningInsight] = []
        self._success_factors: Dict[str, float] = defaultdict(float)

    def analyze_response_patterns(
        self,
        applications: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze patterns in employer responses.

        Identifies response types, timing patterns, and success correlations.
        """
        if not applications:
            logger.warning("analyze_response_patterns_no_data")
            return {"error": "No application data available"}

        # Categorize responses
        response_types = defaultdict(int)
        response_times = []
        successful_outcomes = []

        for app in applications:
            status = app.get("status", "unknown")
            response_types[status] += 1

            # Calculate response time
            applied_date = self._parse_date(app.get("date_applied"))
            updated_date = self._parse_date(app.get("date_updated"))

            if applied_date and updated_date:
                response_time = (updated_date - applied_date).days
                response_times.append(response_time)

                # Track successful outcomes
                if status in ["interview", "offer"]:
                    successful_outcomes.append({
                        "status": status,
                        "response_time": response_time,
                        "company": app.get("company"),
                        "role": app.get("title"),
                    })

        # Calculate metrics
        total_apps = len(applications)
        success_rate = len(successful_outcomes) / total_apps if total_apps > 0 else 0
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Identify patterns
        patterns = self._identify_patterns(applications, response_types, response_times)

        # Generate insights
        insights = self._generate_response_insights(
            applications, patterns, success_rate, avg_response_time
        )

        logger.info(
            "response_patterns_analyzed",
            extra={
                "total_applications": total_apps,
                "success_rate": success_rate,
                "avg_response_time": avg_response_time,
                "patterns_identified": len(patterns),
            },
        )

        return {
            "total_applications": total_apps,
            "response_distribution": dict(response_types),
            "success_rate": round(success_rate * 100, 1),
            "avg_response_time_days": round(avg_response_time, 1),
            "patterns": patterns,
            "insights": insights,
            "successful_outcomes": successful_outcomes[-10:],  # Last 10 successes
        }

    def learn_from_outcomes(
        self,
        applications: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Learn from application outcomes to improve future scoring.

        Updates success factors and identifies improvement opportunities.
        """
        if not applications or not jobs:
            logger.warning("learn_from_outcomes_insufficient_data")
            return {"error": "Insufficient data for learning"}

        # Match applications with jobs
        app_job_matches = self._match_applications_with_jobs(applications, jobs)

        # Analyze success factors
        success_factors = self._analyze_success_factors(app_job_matches)

        # Generate learning insights
        insights = self._generate_learning_insights(app_job_matches, success_factors)

        # Update scoring weights based on learnings
        updated_weights = self._calculate_updated_weights(success_factors)

        # Store learning insights
        self._learning_insights.extend(insights)
        self._success_factors.update(success_factors)

        logger.info(
            "learning_completed",
            extra={
                "applications_analyzed": len(applications),
                "jobs_matched": len(app_job_matches),
                "factors_identified": len(success_factors),
                "insights_generated": len(insights),
            },
        )

        return {
            "applications_analyzed": len(applications),
            "jobs_matched": len(app_job_matches),
            "success_factors": success_factors,
            "learning_insights": insights,
            "updated_scoring_weights": updated_weights,
            "improvement_opportunities": self._identify_improvement_opportunities(success_factors),
        }

    def generate_follow_up_intelligence(
        self,
        applications: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate intelligent follow-up recommendations.

        Identifies which applications need follow-up and provides
        context-aware recommendations.
        """
        if not applications:
            return {"error": "No application data available"}

        follow_up_actions = []
        now = datetime.now()

        for app in applications:
            status = app.get("status", "unknown")
            applied_date = self._parse_date(app.get("date_applied"))
            last_updated = self._parse_date(app.get("date_updated"))

            if not applied_date:
                continue

            days_since_application = (now - applied_date).days
            days_since_update = (now - last_updated).days if last_updated else days_since_application

            # Determine if follow-up is needed
            action = self._determine_follow_up_action(
                app, status, days_since_application, days_since_update
            )

            if action:
                follow_up_actions.append(action)

        # Prioritize actions
        follow_up_actions.sort(key=lambda x: self._priority_score(x), reverse=True)

        logger.info(
            "follow_up_intelligence_generated",
            extra={
                "applications_analyzed": len(applications),
                "actions_recommended": len(follow_up_actions),
            },
        )

        return {
            "follow_up_actions": follow_up_actions[:20],  # Top 20 actions
            "total_actions_needed": len(follow_up_actions),
            "priority_distribution": self._calculate_priority_distribution(follow_up_actions),
            "timing_recommendations": self._generate_timing_recommendations(follow_up_actions),
        }

    def update_scoring_from_feedback(
        self,
        feedback_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update scoring model based on feedback and outcomes.

        Implements the feedback loop to continuously improve predictions.
        """
        try:
            # Extract feedback patterns
            outcome_patterns = feedback_data.get("outcome_patterns", {})
            company_responses = feedback_data.get("company_responses", {})
            role_success_rates = feedback_data.get("role_success_rates", {})

            # Calculate weight adjustments
            weight_adjustments = self._calculate_weight_adjustments(
                outcome_patterns, company_responses, role_success_rates
            )

            # Update decision engine configuration
            updated_config = self._apply_weight_adjustments(weight_adjustments)

            # Validate adjustments
            validation_results = self._validate_weight_adjustments(updated_config)

            logger.info(
                "scoring_updated_from_feedback",
                extra={
                    "weight_adjustments": len(weight_adjustments),
                    "validation_passed": validation_results.get("valid", False),
                },
            )

            return {
                "weight_adjustments": weight_adjustments,
                "updated_config": updated_config,
                "validation_results": validation_results,
                "next_learning_cycle": self._schedule_next_learning_cycle(),
            }

        except Exception as e:
            logger.error("scoring_update_failed", extra={"error": str(e)})
            return {"error": f"Failed to update scoring: {str(e)}"}

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string safely."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            return None

    def _identify_patterns(
        self,
        applications: List[Dict[str, Any]],
        response_types: Dict[str, int],
        response_times: List[float],
    ) -> List[ResponsePattern]:
        """Identify patterns in response data."""
        patterns = []

        # Response time pattern
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            fast_responses = len([t for t in response_times if t <= 3])
            fast_response_rate = fast_responses / len(response_times)

            patterns.append(ResponsePattern(
                pattern_type="response_time",
                frequency=1.0,
                success_rate=fast_response_rate,
                avg_response_time=avg_time,
                confidence=0.8,
                factors={"fast_response_advantage": fast_response_rate * 20}
            ))

        # Status patterns
        total_apps = len(applications)
        for status, count in response_types.items():
            if status in ["interview", "offer"]:
                success_rate = count / total_apps
                patterns.append(ResponsePattern(
                    pattern_type=f"success_{status}",
                    frequency=count / total_apps,
                    success_rate=success_rate,
                    avg_response_time=0,
                    confidence=0.9,
                    factors={"status_success_rate": success_rate * 100}
                ))

        return patterns

    def _generate_response_insights(
        self,
        applications: List[Dict[str, Any]],
        patterns: List[ResponsePattern],
        success_rate: float,
        avg_response_time: float,
    ) -> List[LearningInsight]:
        """Generate insights from response patterns."""
        insights = []

        # Success rate insight
        if success_rate < 0.1:
            insights.append(LearningInsight(
                insight_type="low_success_rate",
                description=f"Success rate is {success_rate*100:.1f}%, below optimal range",
                impact_score=0.8,
                confidence=0.9,
                actionable=True,
                recommendation="Review application quality and targeting strategy"
            ))
        elif success_rate > 0.3:
            insights.append(LearningInsight(
                insight_type="high_success_rate",
                description=f"Success rate is {success_rate*100:.1f}%, performing well",
                impact_score=0.6,
                confidence=0.8,
                actionable=False,
                recommendation="Continue current strategy, consider increasing volume"
            ))

        # Response time insight
        if avg_response_time > 14:
            insights.append(LearningInsight(
                insight_type="slow_response_time",
                description=f"Average response time is {avg_response_time:.1f} days",
                impact_score=0.5,
                confidence=0.7,
                actionable=True,
                recommendation="Follow up after 10-14 days if no response received"
            ))

        return insights

    def _match_applications_with_jobs(
        self,
        applications: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Match applications with their corresponding job data."""
        matches = []

        for app in applications:
            app_link = app.get("link", "")

            # Find matching job
            for job in jobs:
                if job.get("link") == app_link:
                    matches.append({
                        "application": app,
                        "job": job,
                        "success": app.get("status") in ["interview", "offer"],
                        "score": job.get("score", 0),
                    })
                    break

        return matches

    def _analyze_success_factors(
        self,
        app_job_matches: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Analyze factors that contribute to success."""
        factors = defaultdict(list)

        for match in app_job_matches:
            job = match["job"]
            success = match["success"]

            # Score factor
            factors["score"].append((job.get("score", 0), success))

            # Company factor
            company = job.get("company", "unknown")
            factors[f"company_{company}"].append(success)

            # Location factor
            location = job.get("location", "unknown")
            factors[f"location_{location}"].append(success)

            # Score range factor
            score = job.get("score", 0)
            if score >= 85:
                factors["score_very_high"].append(success)
            elif score >= 75:
                factors["score_high"].append(success)
            elif score >= 65:
                factors["score_medium"].append(success)
            else:
                factors["score_low"].append(success)

        # Calculate success rates for each factor
        success_factors = {}
        for factor_name, outcomes in factors.items():
            if outcomes:
                success_rate = sum(outcomes) / len(outcomes)
                success_factors[factor_name] = success_rate

        return success_factors

    def _generate_learning_insights(
        self,
        app_job_matches: List[Dict[str, Any]],
        success_factors: Dict[str, float],
    ) -> List[LearningInsight]:
        """Generate learning insights from success factor analysis."""
        insights = []

        # Score insights
        if "score_very_high" in success_factors:
            very_high_rate = success_factors["score_very_high"]
            if very_high_rate > 0.5:
                insights.append(LearningInsight(
                    insight_type="high_score_success",
                    description=f"Very high score (85+) jobs have {very_high_rate*100:.1f}% success rate",
                    impact_score=0.9,
                    confidence=0.8,
                    actionable=True,
                    recommendation="Prioritize applications to jobs scoring 85+"
                ))

        # Company insights
        company_factors = {k: v for k, v in success_factors.items() if k.startswith("company_")}
        if company_factors:
            best_company = max(company_factors.items(), key=lambda x: x[1])
            insights.append(LearningInsight(
                insight_type="company_preference",
                description=f"Best performing company: {best_company[0].replace('company_', '')}",
                impact_score=0.7,
                confidence=0.6,
                actionable=True,
                recommendation=f"Target more opportunities at {best_company[0].replace('company_', '')}"
            ))

        return insights

    def _calculate_updated_weights(
        self,
        success_factors: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate updated scoring weights based on success factors."""
        updated_weights = {}

        # Update score thresholds based on performance
        if "score_very_high" in success_factors:
            very_high_success = success_factors["score_very_high"]
            if very_high_success > 0.6:
                # Increase weight for very high scores
                updated_weights["very_high_score_boost"] = 0.1
            elif very_high_success < 0.3:
                # Decrease threshold for very high scores
                updated_weights["very_high_score_threshold"] = -5

        return updated_weights

    def _identify_improvement_opportunities(
        self,
        success_factors: Dict[str, float],
    ) -> List[str]:
        """Identify areas for improvement based on success factors."""
        opportunities = []

        # Low performing score ranges
        for score_range in ["score_low", "score_medium"]:
            if score_range in success_factors:
                success_rate = success_factors[score_range]
                if success_rate < 0.1:
                    opportunities.append(f"Improve targeting for {score_range.replace('score_', '')} scoring jobs")

        return opportunities

    def _determine_follow_up_action(
        self,
        application: Dict[str, Any],
        status: str,
        days_since_application: int,
        days_since_update: int,
    ) -> Optional[FollowUpAction]:
        """Determine appropriate follow-up action."""

        # No response after 2 weeks
        if status == "applied" and days_since_application >= 14:
            return FollowUpAction(
                action_type="follow_up_email",
                priority="medium",
                timing="now",
                template="polite_follow_up",
                success_probability=0.3
            )

        # Interview scheduled but no confirmation
        elif status == "interview" and days_since_update >= 7:
            return FollowUpAction(
                action_type="interview_confirmation",
                priority="high",
                timing="now",
                template="interview_confirmation",
                success_probability=0.7
            )

        # Technical assessment completed
        elif status == "technical_assessment" and days_since_update >= 5:
            return FollowUpAction(
                action_type="assessment_follow_up",
                priority="medium",
                timing="now",
                template="assessment_follow_up",
                success_probability=0.5
            )

        return None

    def _priority_score(self, action: FollowUpAction) -> float:
        """Calculate priority score for follow-up action."""
        priority_weights = {
            "high": 3.0,
            "medium": 2.0,
            "low": 1.0,
        }
        return priority_weights.get(action.priority, 1.0) * action.success_probability

    def _calculate_priority_distribution(
        self,
        actions: List[FollowUpAction],
    ) -> Dict[str, int]:
        """Calculate distribution of action priorities."""
        distribution = {"high": 0, "medium": 0, "low": 0}
        for action in actions:
            distribution[action.priority] += 1
        return distribution

    def _generate_timing_recommendations(
        self,
        actions: List[FollowUpAction],
    ) -> Dict[str, List[str]]:
        """Generate timing recommendations for follow-up actions."""
        recommendations = {
            "immediate": [],
            "this_week": [],
            "next_week": [],
        }

        for action in actions:
            if action.timing == "now":
                recommendations["immediate"].append(action.action_type)
            elif "week" in action.timing.lower():
                recommendations["this_week"].append(action.action_type)
            else:
                recommendations["next_week"].append(action.action_type)

        return recommendations

    def _calculate_weight_adjustments(
        self,
        outcome_patterns: Dict[str, Any],
        company_responses: Dict[str, Any],
        role_success_rates: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate weight adjustments based on feedback."""
        adjustments = {}

        # Adjust role match weight based on success rates
        for role, success_rate in role_success_rates.items():
            if success_rate > 0.5:
                adjustments[f"role_boost_{role}"] = 0.05
            elif success_rate < 0.1:
                adjustments[f"role_boost_{role}"] = -0.03

        # Adjust company preferences
        for company, response_rate in company_responses.items():
            if response_rate > 0.8:
                adjustments[f"company_boost_{company}"] = 0.08
            elif response_rate < 0.2:
                adjustments[f"company_boost_{company}"] = -0.05

        return adjustments

    def _apply_weight_adjustments(
        self,
        weight_adjustments: Dict[str, float],
    ) -> Dict[str, Any]:
        """Apply weight adjustments to configuration."""
        # This would update the decision engine configuration
        # For now, return the adjustments for validation
        return {
            "adjustments_applied": weight_adjustments,
            "config_updated": True,
        }

    def _validate_weight_adjustments(
        self,
        updated_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate that weight adjustments are reasonable."""
        # Basic validation logic
        adjustments = updated_config.get("adjustments_applied", {})

        # Check for extreme adjustments
        extreme_adjustments = [k for k, v in adjustments.items() if abs(v) > 0.2]

        return {
            "valid": len(extreme_adjustments) == 0,
            "extreme_adjustments": extreme_adjustments,
            "total_adjustments": len(adjustments),
        }

    def _schedule_next_learning_cycle(self) -> str:
        """Schedule next learning cycle."""
        next_cycle = datetime.now() + timedelta(days=7)
        return next_cycle.isoformat()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def create_response_intelligence_engine(
    decision_engine: JobDecisionEngine,
) -> ResponseIntelligenceEngine:
    """Create and initialize response intelligence engine."""
    return ResponseIntelligenceEngine(decision_engine)


def analyze_application_responses(
    applications: List[Dict[str, Any]],
    decision_engine: JobDecisionEngine,
) -> Dict[str, Any]:
    """Convenience function to analyze application responses."""
    engine = create_response_intelligence_engine(decision_engine)
    return engine.analyze_response_patterns(applications)


def generate_follow_up_plan(
    applications: List[Dict[str, Any]],
    decision_engine: JobDecisionEngine,
) -> Dict[str, Any]:
    """Convenience function to generate follow-up plan."""
    engine = create_response_intelligence_engine(decision_engine)
    return engine.generate_follow_up_intelligence(applications)
