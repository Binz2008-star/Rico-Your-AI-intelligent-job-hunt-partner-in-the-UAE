"""src/agent/context/resolver.py

Profile context resolver for Rico agent.

Loads user profile from DB, hydrates from CV/Jotform/chat/actions,
computes missing fields, and prevents repeated questions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.rico_agent import RicoProfile, RicoAgentSettings
from src.repositories.profile_repo import get_profile, upsert_profile
from src.repositories.audit_repo import get_recent

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# Fields that should never be asked about if already present
_REQUIRED_FIELDS: Set[str] = {
    "email",
    "target_roles",
    "preferred_cities",
    "skills",
}

# Fields that are nice to have but optional
_OPTIONAL_FIELDS: Set[str] = {
    "years_experience",
    "salary_expectation_aed",
    "visa_status",
    "notice_period",
    "linkedin_url",
    "portfolio_url",
}

# Fields that should be inferred from behavior rather than asked
_INFERRED_FIELDS: Set[str] = {
    "deal_breakers",
    "green_flags",
    "red_flags",
}


@dataclass
class ProfileContext:
    """Enriched profile context with hydration metadata."""
    profile: Optional[RicoProfile]
    canonical_user_id: str
    completeness_score: float  # 0.0-1.0
    missing_required: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)
    hydration_sources: List[str] = field(default_factory=list)
    last_hydrated_at: Optional[datetime] = None
    question_history: Dict[str, datetime] = field(default_factory=dict)
    behavior_signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for AI context."""
        return {
            "profile": self.profile.__dict__ if self.profile else None,
            "completeness_score": self.completeness_score,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "hydration_sources": self.hydration_sources,
            "should_ask_for": self._compute_questions_to_ask(),
        }

    def _compute_questions_to_ask(self) -> List[str]:
        """
        Compute which fields should be asked about now.

        Rules:
        - Never ask about fields already present
        - Never ask about fields asked in the last 24 hours
        - Prioritize required fields over optional
        - Skip fields that can be inferred from behavior
        """
        now = datetime.now(_UTC)
        to_ask: List[str] = []

        for field in sorted(self.missing_required):
            # Skip if asked recently
            last_asked = self.question_history.get(field)
            if last_asked and (now - last_asked).total_seconds() < 86400:  # 24 hours
                continue
            to_ask.append(field)

        # Only ask optional fields if required are satisfied
        if not to_ask:
            for field in sorted(self.missing_optional):
                last_asked = self.question_history.get(field)
                if last_asked and (now - last_asked).total_seconds() < 86400:
                    continue
                to_ask.append(field)

        return to_ask


class ProfileContextResolver:
    """
    Resolves and hydrates profile context from multiple sources.

    Hydration sources (in priority order):
    1. Database profile (canonical truth)
    2. CV extraction (high-confidence structured data)
    3. Jotform submission (user-provided structured data)
    4. Chat history (natural language extraction)
    5. Action history (behavioral inference)
    """

    def __init__(self):
        self._cache: Dict[str, ProfileContext] = {}
        self._question_cooldown_seconds = 86400  # 24 hours

    def resolve(
        self,
        canonical_user_id: str,
        *,
        cv_data: Optional[Dict[str, Any]] = None,
        jotform_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        force_refresh: bool = False,
    ) -> ProfileContext:
        """
        Resolve profile context for a user.

        Args:
            canonical_user_id: Resolved user ID from IdentityResolver
            cv_data: Extracted data from CV parsing
            jotform_data: Normalized Jotform submission payload
            chat_history: Recent chat messages for context extraction
            force_refresh: Bypass cache and rehydrate

        Returns:
            ProfileContext with hydrated profile and metadata
        """
        # Check cache first
        if not force_refresh and canonical_user_id in self._cache:
            cached = self._cache[canonical_user_id]
            # Reuse if hydrated within last hour
            if cached.last_hydrated_at:
                age = (datetime.now(_UTC) - cached.last_hydrated_at).total_seconds()
                if age < 3600:
                    return cached

        # Load base profile
        profile = get_profile(canonical_user_id)

        # Hydrate from available sources
        hydration_sources: List[str] = []
        if profile is None:
            profile = RicoProfile(user_id=canonical_user_id)
            hydration_sources.append("created_blank")

        # CV hydration (highest priority after DB)
        if cv_data:
            profile = self._hydrate_from_cv(profile, cv_data)
            hydration_sources.append("cv")

        # Jotform hydration
        if jotform_data:
            profile = self._hydrate_from_jotform(profile, jotform_data)
            hydration_sources.append("jotform")

        # Chat history hydration (extract preferences from conversation)
        if chat_history:
            profile = self._hydrate_from_chat(profile, chat_history)
            hydration_sources.append("chat")

        # Action history hydration (infer preferences from behavior)
        profile = self._hydrate_from_actions(profile, canonical_user_id)
        if profile.behavior_signals:  # type: ignore
            hydration_sources.append("actions")

        # Persist hydrated profile
        try:
            upsert_profile(user_id=canonical_user_id, updates=profile.__dict__)
        except Exception:
            logger.exception("profile_hydration_persist_failed user=%s", canonical_user_id)

        # Compute completeness and missing fields
        completeness, missing_required, missing_optional = self._compute_completeness(profile)

        # Load question history from audit log (what has been asked)
        question_history = self._load_question_history(canonical_user_id)

        # Load behavior signals
        behavior_signals = self._load_behavior_signals(canonical_user_id)

        context = ProfileContext(
            profile=profile,
            canonical_user_id=canonical_user_id,
            completeness_score=completeness,
            missing_required=missing_required,
            missing_optional=missing_optional,
            hydration_sources=hydration_sources,
            last_hydrated_at=datetime.now(_UTC),
            question_history=question_history,
            behavior_signals=behavior_signals,
        )

        # Cache the result
        self._cache[canonical_user_id] = context

        logger.info(
            "profile_context_resolved user=%s completeness=%.2f sources=%s missing_required=%d",
            canonical_user_id,
            completeness,
            hydration_sources,
            len(missing_required),
        )

        return context

    def _hydrate_from_cv(self, profile: RicoProfile, cv_data: Dict[str, Any]) -> RicoProfile:
        """Hydrate profile from CV extraction results."""
        updates: Dict[str, Any] = {}

        # Direct field mappings
        if cv_data.get("emails") and not profile.email:
            updates["email"] = cv_data["emails"][0]
        if cv_data.get("phones") and not profile.phone:
            updates["phone"] = cv_data["phones"][0]
        if cv_data.get("skills") and not profile.skills:
            updates["skills"] = cv_data["skills"]
        if cv_data.get("years_experience_hint") and not profile.years_experience:
            updates["years_experience"] = cv_data["years_experience_hint"]

        # Infer target roles from experience section
        if not profile.target_roles and cv_data.get("experience"):
            roles = self._extract_roles_from_experience(cv_data["experience"])
            if roles:
                updates["target_roles"] = roles

        # Apply updates to profile
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        return profile

    def _hydrate_from_jotform(self, profile: RicoProfile, jotform_data: Dict[str, Any]) -> RicoProfile:
        """Hydrate profile from Jotform submission."""
        answers = jotform_data.get("pretty", jotform_data)

        # Direct field mappings
        if answers.get("email") and not profile.email:
            profile.email = answers["email"]
        if answers.get("phone") and not profile.phone:
            profile.phone = answers.get("phone") or answers.get("Phone Number")
        if answers.get("telegram_username") and not profile.telegram_username:
            profile.telegram_username = answers["telegram_username"]
        if answers.get("target_roles") and not profile.target_roles:
            profile.target_roles = self._as_list(answers["target_roles"])
        if answers.get("preferred_cities") and not profile.preferred_cities:
            profile.preferred_cities = self._as_list(answers["preferred_cities"])
        if answers.get("skills") and not profile.skills:
            profile.skills = self._as_list(answers["skills"])
        if answers.get("visa_status") and not profile.visa_status:
            profile.visa_status = answers["visa_status"]
        if answers.get("notice_period") and not profile.notice_period:
            profile.notice_period = answers["notice_period"]
        if answers.get("years_experience") and not profile.years_experience:
            profile.years_experience = self._parse_years(answers["years_experience"])
        if answers.get("salary_expectation_aed") and not profile.salary_expectation_aed:
            profile.salary_expectation_aed = self._parse_salary(answers["salary_expectation_aed"])

        # Settings from Jotform
        if answers.get("autonomy_level"):
            profile.settings.autonomy_level = answers["autonomy_level"]
        if answers.get("communication_style"):
            profile.settings.communication_style = answers["communication_style"]
        if answers.get("match_strictness"):
            profile.settings.match_strictness = answers["match_strictness"]

        return profile

    def _hydrate_from_chat(self, profile: RicoProfile, chat_history: List[Dict[str, Any]]) -> RicoProfile:
        """Extract preferences from chat history."""
        # This is a simple implementation - could be enhanced with NLP
        recent_messages = [m for m in chat_history if m.get("role") == "user"][-10:]

        for msg in recent_messages:
            text = msg.get("content", "").lower()

            # Simple pattern matching for common preferences
            if "remote" in text and "remote" not in (profile.preferred_cities or []):
                if not profile.preferred_cities:
                    profile.preferred_cities = []
                profile.preferred_cities.append("Remote")

            if "dubai" in text and "dubai" not in (profile.preferred_cities or []):
                if not profile.preferred_cities:
                    profile.preferred_cities = []
                profile.preferred_cities.append("Dubai")

        return profile

    def _hydrate_from_actions(self, profile: RicoProfile, canonical_user_id: str) -> RicoProfile:
        """Infer preferences from action history."""
        try:
            recent_actions = get_recent(limit=50)

            # Filter actions for this user
            user_actions = [a for a in recent_actions if a.get("user_email") == canonical_user_id]

            # Infer deal breakers from skipped jobs with certain patterns
            skipped_companies: Set[str] = set()
            for action in user_actions:
                if action.get("action_type") == "skip":
                    company = action.get("job_company")
                    if company:
                        skipped_companies.add(company)

            # If user consistently skips certain companies, mark as deal breakers
            if len(skipped_companies) >= 3:
                profile.deal_breakers = list(skipped_companies)[:10]

        except Exception:
            logger.exception("action_hydration_failed user=%s", canonical_user_id)

        return profile

    def _compute_completeness(self, profile: RicoProfile) -> tuple[float, List[str], List[str]]:
        """Compute profile completeness score and missing fields."""
        present = 0
        total = len(_REQUIRED_FIELDS) + len(_OPTIONAL_FIELDS)
        missing_required: List[str] = []
        missing_optional: List[str] = []

        for field in _REQUIRED_FIELDS:
            value = getattr(profile, field, None)
            if value and (not isinstance(value, list) or value):
                present += 1
            else:
                missing_required.append(field)

        for field in _OPTIONAL_FIELDS:
            value = getattr(profile, field, None)
            if value and (not isinstance(value, list) or value):
                present += 1
            else:
                missing_optional.append(field)

        completeness = present / total if total > 0 else 0.0
        return completeness, missing_required, missing_optional

    def _load_question_history(self, canonical_user_id: str) -> Dict[str, datetime]:
        """Load which questions have been asked to this user."""
        # This would query an audit log for profile questions
        # For now, return empty dict
        return {}

    def _load_behavior_signals(self, canonical_user_id: str) -> Dict[str, Any]:
        """Load behavioral signals from action history."""
        signals: Dict[str, Any] = {}

        try:
            recent_actions = get_recent(limit=100)
            user_actions = [a for a in recent_actions if a.get("user_email") == canonical_user_id]

            signals["total_actions"] = len(user_actions)
            signals["applied_count"] = len([a for a in user_actions if a.get("action_type") == "apply"])
            signals["saved_count"] = len([a for a in user_actions if a.get("action_type") == "save"])
            signals["skipped_count"] = len([a for a in user_actions if a.get("action_type") == "skip"])

        except Exception:
            logger.exception("behavior_signals_load_failed user=%s", canonical_user_id)

        return signals

    def _extract_roles_from_experience(self, experience: List[Dict[str, Any]]) -> List[str]:
        """Extract target roles from CV experience section."""
        roles: Set[str] = set()
        for exp in experience:
            title = exp.get("title", "")
            if title:
                roles.add(title)
        return list(roles)[:5]

    def _as_list(self, value: Any) -> List[str]:
        """Convert value to list if not already."""
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            return [value]
        return []

    def _parse_years(self, value: Any) -> Optional[float]:
        """Parse years of experience from various formats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        return None

    def _parse_salary(self, value: Any) -> Optional[int]:
        """Parse salary expectation from various formats."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # Extract digits
            import re
            match = re.search(r"\d+", value.replace(",", ""))
            if match:
                return int(match.group())
        return None

    def mark_question_asked(self, canonical_user_id: str, field: str) -> None:
        """Record that a question about a field was asked."""
        if canonical_user_id in self._cache:
            self._cache[canonical_user_id].question_history[field] = datetime.now(_UTC)


# Module-level singleton
_profile_context_resolver = ProfileContextResolver()


def resolve_profile_context(
    canonical_user_id: str,
    *,
    cv_data: Optional[Dict[str, Any]] = None,
    jotform_data: Optional[Dict[str, Any]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    force_refresh: bool = False,
) -> ProfileContext:
    """
    Convenience function to resolve profile context.

    Uses the singleton ProfileContextResolver instance.
    """
    return _profile_context_resolver.resolve(
        canonical_user_id=canonical_user_id,
        cv_data=cv_data,
        jotform_data=jotform_data,
        chat_history=chat_history,
        force_refresh=force_refresh,
    )
