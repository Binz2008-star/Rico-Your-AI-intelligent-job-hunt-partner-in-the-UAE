"""
Job Search Decision Engine
AI-powered analytics and decision support for optimal job hunting strategies.
Provides predictive insights, competitive analysis, and strategic recommendations.
"""

import os
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Dict, List, Any, Tuple, Optional
import re

from src.db import get_top_jobs, get_application_stats, is_db_available, get_seen_links
from src.job_history import load_job_history
from src.applications import get_applied_jobs
from src.profile import get_candidate_profile, get_target_roles


class JobDecisionEngine:
    """Advanced decision engine for job search optimization."""
    
    def __init__(self):
        self.profile = get_candidate_profile()
        self.target_roles = get_target_roles()
        self.candidate_level = self._determine_candidate_level()
        
    def _determine_candidate_level(self) -> str:
        """Determine candidate experience level from profile."""
        years = self.profile.get("experience_years", 0)
        if years >= 10:
            return "Executive"
        elif years >= 7:
            return "Senior"
        elif years >= 4:
            return "Mid"
        else:
            return "Junior"
    
    def calculate_success_probability(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate probability of success for a specific job application."""
        score = job.get("score", 0)
        title = job.get("title", "").lower()
        company = job.get("company", "")
        location = job.get("location", "")
        
        # Base probability from score
        base_prob = min(score / 100, 0.95)
        
        # Role match bonus
        role_bonus = 0
        for target_role in self.target_roles:
            if target_role.lower() in title:
                role_bonus = 0.15
                break
        
        # Experience level match
        exp_keywords = ["senior", "executive", "lead", "principal", "head", "chief"]
        exp_match = any(kw in title for kw in exp_keywords)
        exp_bonus = 0.1 if exp_match and self.candidate_level in ["Executive", "Senior"] else 0
        
        # Company size factor (simplified)
        company_size_factor = self._estimate_company_size_factor(company)
        
        # Location preference
        uae_keywords = ["dubai", "abu dhabi", "uae"]
        location_bonus = 0.05 if any(kw in location.lower() for kw in uae_keywords) else 0
        
        # Calculate final probability
        probability = base_prob + role_bonus + exp_bonus + company_size_factor + location_bonus
        probability = min(probability, 0.95)  # Cap at 95%
        
        # Determine confidence level
        if probability >= 0.8:
            confidence = "Very High"
            recommendation = "Apply immediately - excellent match"
        elif probability >= 0.65:
            confidence = "High"
            recommendation = "Strong candidate - apply with confidence"
        elif probability >= 0.5:
            confidence = "Medium"
            recommendation = "Good fit - consider applying"
        else:
            confidence = "Low"
            recommendation = "Consider other opportunities"
        
        return {
            "probability": round(probability * 100, 1),
            "confidence": confidence,
            "recommendation": recommendation,
            "factors": {
                "base_score": round(base_prob * 100, 1),
                "role_match": round(role_bonus * 100, 1),
                "experience_match": round(exp_bonus * 100, 1),
                "company_factor": round(company_size_factor * 100, 1),
                "location_bonus": round(location_bonus * 100, 1)
            }
        }
    
    def _estimate_company_size_factor(self, company: str) -> float:
        """Estimate company size factor for success probability."""
        # Simplified heuristic based on company name patterns
        if not company:
            return 0.0
        
        company_lower = company.lower()
        
        # Large corporations (easier to get in, more positions)
        large_corps = ["etihad", "emirates", "dnata", "mubadala", "adnoc", "dp world", "du", "etisalat"]
        if any(corp in company_lower for corp in large_corps):
            return 0.1
        
        # Mid-sized companies
        mid_keywords = ["group", "holding", "international", "global"]
        if any(kw in company_lower for kw in mid_keywords):
            return 0.05
        
        # Startups (harder to get in, but potentially better growth)
        startup_keywords = ["startup", "tech", "innovate", "ventures"]
        if any(kw in company_lower for kw in startup_keywords):
            return -0.05
        
        return 0.0
    
    def analyze_market_trends(self, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze job market trends and patterns."""
        if not jobs:
            return {"error": "No jobs data available"}
        
        # Time-based analysis
        now = datetime.now()
        recent_jobs = [j for j in jobs if self._parse_date(j.get("date_found")) and 
                      (now - self._parse_date(j.get("date_found"))).days <= 30]
        
        # Score trends
        scores = [j.get("score", 0) for j in jobs if j.get("score")]
        recent_scores = [j.get("score", 0) for j in recent_jobs if j.get("score")]
        
        # Company frequency analysis
        company_counts = Counter(j.get("company", "Unknown") for j in jobs)
        top_companies = company_counts.most_common(10)
        
        # Location analysis
        location_counts = Counter(j.get("location", "Unknown") for j in jobs)
        
        # Role analysis
        role_patterns = self._analyze_role_patterns(jobs)
        
        # Quality distribution
        quality_dist = self._analyze_quality_distribution(scores)
        
        # Market health indicators
        market_health = self._calculate_market_health(recent_jobs, recent_scores)
        
        return {
            "market_overview": {
                "total_jobs": len(jobs),
                "recent_jobs": len(recent_jobs),
                "avg_score": round(mean(scores), 1) if scores else 0,
                "recent_avg_score": round(mean(recent_scores), 1) if recent_scores else 0,
                "score_trend": "improving" if recent_scores and mean(recent_scores) > mean(scores) else "declining"
            },
            "top_companies": [{"name": name, "count": count, "market_share": round(count/len(jobs)*100, 1)} 
                             for name, count in top_companies],
            "location_analysis": dict(location_counts.most_common(10)),
            "role_patterns": role_patterns,
            "quality_distribution": quality_dist,
            "market_health": market_health,
            "recommendations": self._generate_market_recommendations(market_health, quality_dist)
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string safely."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
    
    def _analyze_role_patterns(self, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze role patterns and trends."""
        role_keywords = defaultdict(int)
        seniority_levels = defaultdict(int)
        
        for job in jobs:
            title = job.get("title", "").lower()
            
            # Extract role keywords
            for target_role in self.target_roles:
                if target_role.lower() in title:
                    role_keywords[target_role] += 1
            
            # Extract seniority levels
            if any(word in title for word in ["executive", "senior", "lead", "principal"]):
                seniority_levels["Senior+"] += 1
            elif any(word in title for word in ["manager", "supervisor", "head"]):
                seniority_levels["Management"] += 1
            else:
                seniority_levels["Other"] += 1
        
        return {
            "target_role_frequency": dict(role_keywords),
            "seniority_distribution": dict(seniority_levels),
            "most_common_role": max(role_keywords.items(), key=lambda x: x[1])[0] if role_keywords else "None"
        }
    
    def _analyze_quality_distribution(self, scores: List[int]) -> Dict[str, Any]:
        """Analyze job quality distribution."""
        if not scores:
            return {}
        
        very_high = len([s for s in scores if s >= 85])
        high = len([s for s in scores if 75 <= s < 85])
        medium = len([s for s in scores if 65 <= s < 75])
        low = len([s for s in scores if 40 <= s < 65])
        very_low = len([s for s in scores if s < 40])
        
        total = len(scores)
        
        return {
            "very_high": {"count": very_high, "percentage": round(very_high/total*100, 1)},
            "high": {"count": high, "percentage": round(high/total*100, 1)},
            "medium": {"count": medium, "percentage": round(medium/total*100, 1)},
            "low": {"count": low, "percentage": round(low/total*100, 1)},
            "very_low": {"count": very_low, "percentage": round(very_low/total*100, 1)},
            "median_score": median(scores)
        }
    
    def _calculate_market_health(self, recent_jobs: List[Dict[str, Any]], recent_scores: List[int]) -> Dict[str, Any]:
        """Calculate market health indicators."""
        if not recent_jobs:
            return {"health_score": 0, "status": "No data"}
        
        # Job availability score
        job_availability = min(len(recent_jobs) / 10, 1.0)  # Normalize to 0-1
        
        # Quality score
        avg_quality = mean(recent_scores) / 100 if recent_scores else 0
        
        # Competition score (inverse of application rate)
        applications = get_applied_jobs()
        competition_factor = 1.0 - min(len(applications) / max(len(recent_jobs), 1), 0.8)
        
        # Overall health score
        health_score = (job_availability * 0.4 + avg_quality * 0.4 + competition_factor * 0.2) * 100
        
        if health_score >= 80:
            status = "Excellent"
        elif health_score >= 60:
            status = "Good"
        elif health_score >= 40:
            status = "Fair"
        else:
            status = "Poor"
        
        return {
            "health_score": round(health_score, 1),
            "status": status,
            "job_availability": round(job_availability * 100, 1),
            "quality_score": round(avg_quality * 100, 1),
            "competition_factor": round(competition_factor * 100, 1)
        }
    
    def _generate_market_recommendations(self, market_health: Dict[str, Any], quality_dist: Dict[str, Any]) -> List[str]:
        """Generate market-specific recommendations."""
        recommendations = []
        
        health_status = market_health.get("status", "Unknown")
        
        if health_status == "Excellent":
            recommendations.append("Market conditions are optimal - increase application rate")
            recommendations.append("Focus on very high-quality matches (85+ score)")
        elif health_status == "Good":
            recommendations.append("Good market conditions - maintain current strategy")
            recommendations.append("Target high-quality matches (75+ score)")
        elif health_status == "Fair":
            recommendations.append("Market is competitive - be more selective")
            recommendations.append("Focus on roles with 65+ score")
        else:
            recommendations.append("Market conditions challenging - expand search criteria")
            recommendations.append("Consider roles with 50+ score")
        
        # Quality-based recommendations
        if quality_dist.get("very_high", {}).get("percentage", 0) > 20:
            recommendations.append("Many high-quality opportunities available - be selective")
        elif quality_dist.get("very_high", {}).get("percentage", 0) < 5:
            recommendations.append("Few high-quality jobs - consider broader search")
        
        return recommendations
    
    def generate_application_strategy(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate personalized application strategy."""
        if not jobs:
            return {"error": "No jobs data available"}
        
        # Analyze current application patterns
        app_stats = get_application_stats()
        success_rate = app_stats.get("success_rate", 0)
        
        # Calculate optimal application rate
        high_quality_jobs = [j for j in jobs if j.get("score", 0) >= 65]
        optimal_apply_rate = min(len(high_quality_jobs) * 0.3, 5)  # Apply to 30% of high-quality jobs, max 5 per day
        
        # Priority scoring for jobs
        prioritized_jobs = []
        for job in jobs:
            score = job.get("score", 0)
            success_analysis = self.calculate_success_probability(job)
            
            priority_score = score * 0.6 + success_analysis["probability"] * 0.4
            
            prioritized_jobs.append({
                "job": job,
                "priority_score": round(priority_score, 1),
                "success_probability": success_analysis["probability"],
                "recommendation": success_analysis["recommendation"],
                "apply_today": priority_score >= 70 and len([j for j in prioritized_jobs if j["priority_score"] >= 70]) < optimal_apply_rate
            })
        
        # Sort by priority score
        prioritized_jobs.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Strategy recommendations
        strategy_recommendations = []
        
        if success_rate < 10:
            strategy_recommendations.append("Low success rate - focus on very high-quality matches only")
            strategy_recommendations.append("Consider improving resume/cover letter")
        elif success_rate > 30:
            strategy_recommendations.append("High success rate - can be more selective")
            strategy_recommendations.append("Target only the best opportunities")
        else:
            strategy_recommendations.append("Moderate success rate - maintain current strategy")
        
        if len(high_quality_jobs) > 10:
            strategy_recommendations.append(f"Many opportunities - apply to {optimal_apply_rate} top matches today")
        elif len(high_quality_jobs) < 3:
            strategy_recommendations.append("Few high-quality matches - expand search criteria")
        
        return {
            "daily_strategy": {
                "optimal_applications": int(optimal_apply_rate),
                "high_quality_available": len(high_quality_jobs),
                "current_success_rate": success_rate
            },
            "prioritized_jobs": prioritized_jobs[:10],  # Top 10 recommendations
            "strategy_recommendations": strategy_recommendations,
            "timing_advice": self._generate_timing_advice(),
            "application_tips": self._generate_application_tips()
        }
    
    def _generate_timing_advice(self) -> Dict[str, Any]:
        """Generate timing advice for applications."""
        now = datetime.now()
        
        # Best days to apply (weekday vs weekend)
        if now.weekday() >= 5:  # Weekend
            timing_tip = "Weekend - prepare applications for Monday morning"
            urgency = "Low"
        elif now.weekday() == 0:  # Monday
            timing_tip = "Monday morning - high competition, apply to top matches only"
            urgency = "High"
        elif now.weekday() <= 3:  # Tuesday-Thursday
            timing_tip = "Mid-week - optimal time for applications"
            urgency = "Medium"
        else:  # Friday
            timing_tip = "Friday - apply before weekend, follow up next week"
            urgency = "Medium"
        
        # Time of day advice
        hour = now.hour
        if 9 <= hour <= 11:
            time_tip = "Morning - recruiters are active"
        elif 14 <= hour <= 16:
            time_tip = "Afternoon - good time for applications"
        else:
            time_tip = "Outside business hours - applications will be reviewed tomorrow"
        
        return {
            "day_advice": timing_tip,
            "urgency": urgency,
            "time_advice": time_tip
        }
    
    def _generate_application_tips(self) -> List[str]:
        """Generate application tips based on profile."""
        tips = []
        
        # Experience-based tips
        if self.candidate_level == "Executive":
            tips.append("Emphasize leadership experience and strategic impact")
            tips.append("Focus on C-suite and senior management roles")
        elif self.candidate_level == "Senior":
            tips.append("Highlight 7+ years of relevant experience")
            tips.append("Target senior and lead positions")
        
        # Location-based tips
        tips.append("Leverage UAE market experience as competitive advantage")
        tips.append("Emphasize understanding of local business culture")
        
        # Role-specific tips
        tips.append("Customize applications for each target role")
        tips.append("Use Roben-specific profile keywords in applications")
        
        return tips
    
    def generate_competitive_analysis(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate competitive analysis for job applications."""
        if not jobs:
            return {"error": "No jobs data available"}
        
        # Analyze competition by score ranges
        score_ranges = {
            "Very High (85+)": [j for j in jobs if j.get("score", 0) >= 85],
            "High (75-84)": [j for j in jobs if 75 <= j.get("score", 0) < 85],
            "Medium (65-74)": [j for j in jobs if 65 <= j.get("score", 0) < 75],
            "Low (<65)": [j for j in jobs if j.get("score", 0) < 65]
        }
        
        # Competition intensity by role
        role_competition = {}
        for target_role in self.target_roles:
            role_jobs = [j for j in jobs if target_role.lower() in j.get("title", "").lower()]
            if role_jobs:
                avg_score = mean(j.get("score", 0) for j in role_jobs)
                competition_level = "High" if avg_score > 70 else "Medium" if avg_score > 50 else "Low"
                role_competition[target_role] = {
                    "avg_score": round(avg_score, 1),
                    "competition_level": competition_level,
                    "opportunities": len(role_jobs)
                }
        
        # Application success analysis
        app_success = {}
        for app in applications:
            status = app.get("status", "unknown")
            app_success[status] = app_success.get(status, 0) + 1
        
        # Recommendations based on competition
        recommendations = []
        
        for role, data in role_competition.items():
            if data["competition_level"] == "High":
                recommendations.append(f"{role}: High competition - only apply to 75+ score jobs")
            elif data["competition_level"] == "Medium":
                recommendations.append(f"{role}: Moderate competition - apply to 65+ score jobs")
            else:
                recommendations.append(f"{role}: Low competition - good opportunity")
        
        return {
            "score_competition": {range_name: len(jobs) for range_name, jobs in score_ranges.items()},
            "role_competition": role_competition,
            "application_success": app_success,
            "competitive_advantage": self._identify_competitive_advantages(),
            "recommendations": recommendations
        }
    
    def _identify_competitive_advantages(self) -> List[str]:
        """Identify candidate's competitive advantages."""
        advantages = []
        
        # Experience advantage
        if self.candidate_level == "Executive":
            advantages.append("Executive-level experience (10+ years)")
        elif self.candidate_level == "Senior":
            advantages.append("Senior-level experience (7+ years)")
        
        # Location advantage
        advantages.append("UAE market experience and local knowledge")
        
        # Skills advantage
        profile = get_candidate_profile()
        for skill_category, skill_data in profile["skills"].items():
            if skill_data["weight"] >= 12:  # High-weight skills
                advantages.append(f"Strong {skill_category} expertise")
        
        # Role-specific advantages
        advantages.append("Targeted focus on executive operations roles")
        advantages.append("CV-aware scoring optimization")
        
        return advantages


def generate_decision_insights() -> Dict[str, Any]:
    """Generate comprehensive decision insights."""
    engine = JobDecisionEngine()
    
    # Load data
    if is_db_available():
        jobs = get_top_jobs(100)
        applications = get_applied_jobs()
    else:
        jobs = load_job_history()
        applications = load_json(Path("data/applied_jobs.json"), [])
    
    # Generate all insights
    insights = {
        "market_analysis": engine.analyze_market_trends(jobs),
        "application_strategy": engine.generate_application_strategy(jobs, applications),
        "competitive_analysis": engine.generate_competitive_analysis(jobs, applications),
        "candidate_profile": {
            "level": engine.candidate_level,
            "target_roles": engine.target_roles,
            "competitive_advantages": engine._identify_competitive_advantages()
        },
        "generated_at": datetime.now().isoformat(),
        "data_source": "database" if is_db_available() else "json"
    }
    
    return insights


def load_json(path: Path, default):
    """Load JSON file with fallback."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


if __name__ == "__main__":
    # Test decision engine
    insights = generate_decision_insights()
    print("✅ Decision Engine Insights Generated")
    print(f"📊 Market Health: {insights['market_analysis']['market_health']['status']}")
    print(f"🎯 Optimal Daily Applications: {insights['application_strategy']['daily_strategy']['optimal_applications']}")
    print(f"📈 Competitive Advantages: {len(insights['candidate_profile']['competitive_advantages'])}")
