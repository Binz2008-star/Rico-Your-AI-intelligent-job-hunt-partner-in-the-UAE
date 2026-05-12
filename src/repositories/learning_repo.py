"""src/repositories/learning_repo.py

Learning signals repository for Rico agent.

Stores and retrieves behavioral learning signals:
- Target role preferences (from job actions)
- Location preferences (from saved jobs)
- Skill relevance (from applied jobs)
- Company preferences (deal breakers, green flags)
- Feedback events (positive/negative feedback on matches)
- Interview preferences (types of roles, companies, locations)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from src.db import get_db_connection, is_db_available

logger = logging.getLogger(__name__)
_UTC = timezone.utc


@dataclass
class LearningSignal:
    """A single learning signal."""
    signal_type: str  # "role_preference", "location_preference", "skill_relevance", "company_sentiment", "feedback"
    signal_value: str  # The value (e.g., "Senior Engineer", "Dubai", "Python", "Google")
    signal_weight: float  # 0.0-1.0 confidence weight
    source: str  # "job_action", "chat", "jotform", "feedback"
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningProfile:
    """Aggregated learning signals for a user."""
    canonical_user_id: str
    role_preferences: Dict[str, float] = field(default_factory=dict)
    location_preferences: Dict[str, float] = field(default_factory=dict)
    skill_relevance: Dict[str, float] = field(default_factory=dict)
    company_sentiment: Dict[str, float] = field(default_factory=dict)  # -1.0 to 1.0
    feedback_events: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: Optional[datetime] = None


class LearningRepository:
    """
    Repository for storing and retrieving learning signals.

    Learning signals are behavioral cues extracted from user actions:
    - Applied to a job → positive signal for role, location, skills
    - Saved a job → positive signal for role, location
    - Skipped/ignored → weak negative signal
    - Blocked company → strong negative signal
    - Explicit feedback → direct signal
    """

    def __init__(self):
        self._cache: Dict[str, LearningProfile] = {}

    def record_signal(
        self,
        canonical_user_id: str,
        signal_type: str,
        signal_value: str,
        signal_weight: float = 0.5,
        source: str = "job_action",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a learning signal.

        Args:
            canonical_user_id: User ID from IdentityResolver
            signal_type: Type of signal (role_preference, location_preference, etc.)
            signal_value: The value being learned
            signal_weight: Confidence weight 0.0-1.0
            source: Where this signal came from
            metadata: Additional context

        Returns:
            True if signal was recorded successfully
        """
        signal = LearningSignal(
            signal_type=signal_type,
            signal_value=signal_value,
            signal_weight=signal_weight,
            source=source,
            timestamp=datetime.now(_UTC),
            metadata=metadata or {},
        )

        # Persist to database
        if is_db_available():
            try:
                self._db_write_signal(canonical_user_id, signal)
            except Exception:
                logger.exception("learning_signal_db_write_failed user=%s type=%s", canonical_user_id, signal_type)

        # Update cache
        if canonical_user_id not in self._cache:
            self._cache[canonical_user_id] = LearningProfile(canonical_user_id=canonical_user_id)

        profile = self._cache[canonical_user_id]
        profile.last_updated = datetime.now(_UTC)

        # Update appropriate field based on signal type
        if signal_type == "role_preference":
            self._update_weighted_dict(profile.role_preferences, signal_value, signal_weight)
        elif signal_type == "location_preference":
            self._update_weighted_dict(profile.location_preferences, signal_value, signal_weight)
        elif signal_type == "skill_relevance":
            self._update_weighted_dict(profile.skill_relevance, signal_value, signal_weight)
        elif signal_type == "company_sentiment":
            profile.company_sentiment[signal_value] = signal_weight
        elif signal_type == "feedback":
            profile.feedback_events.append({
                "value": signal_value,
                "weight": signal_weight,
                "source": source,
                "timestamp": signal.timestamp.isoformat(),
                "metadata": metadata,
            })

        logger.debug(
            "learning_signal_recorded user=%s type=%s value=%s weight=%.2f",
            canonical_user_id, signal_type, signal_value, signal_weight,
        )

        return True

    def get_learning_profile(self, canonical_user_id: str) -> LearningProfile:
        """
        Get aggregated learning profile for a user.

        Loads from database if not in cache.
        """
        if canonical_user_id in self._cache:
            return self._cache[canonical_user_id]

        # Load from database
        profile = LearningProfile(canonical_user_id=canonical_user_id)

        if is_db_available():
            try:
                profile = self._db_load_profile(canonical_user_id)
            except Exception:
                logger.exception("learning_profile_db_load_failed user=%s", canonical_user_id)

        self._cache[canonical_user_id] = profile
        return profile

    def infer_signals_from_job_action(
        self,
        canonical_user_id: str,
        action_type: str,
        job: Dict[str, Any],
    ) -> None:
        """
        Infer learning signals from a job action.

        Args:
            canonical_user_id: User ID
            action_type: "apply", "save", "skip", "block", "not_relevant"
            job: Job dict with title, company, location, description, skills
        """
        title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "") or job.get("city", "")
        description = job.get("description", "")

        # Extract role from title
        role = self._extract_role_from_title(title)
        if role:
            if action_type in ("apply", "save"):
                self.record_signal(
                    canonical_user_id,
                    "role_preference",
                    role,
                    signal_weight=0.8 if action_type == "apply" else 0.5,
                    source="job_action",
                    metadata={"action": action_type, "job_title": title},
                )
            elif action_type in ("skip", "not_relevant"):
                self.record_signal(
                    canonical_user_id,
                    "role_preference",
                    role,
                    signal_weight=-0.2,
                    source="job_action",
                    metadata={"action": action_type, "job_title": title},
                )

        # Extract location
        if location:
            if action_type in ("apply", "save"):
                self.record_signal(
                    canonical_user_id,
                    "location_preference",
                    location,
                    signal_weight=0.7 if action_type == "apply" else 0.4,
                    source="job_action",
                    metadata={"action": action_type, "location": location},
                )

        # Company sentiment
        if company:
            if action_type == "block":
                self.record_signal(
                    canonical_user_id,
                    "company_sentiment",
                    company,
                    signal_weight=-1.0,
                    source="job_action",
                    metadata={"action": action_type},
                )
            elif action_type == "apply":
                self.record_signal(
                    canonical_user_id,
                    "company_sentiment",
                    company,
                    signal_weight=0.5,
                    source="job_action",
                    metadata={"action": action_type},
                )

        # Extract skills from description
        skills = self._extract_skills_from_description(description)
        for skill in skills:
            if action_type == "apply":
                self.record_signal(
                    canonical_user_id,
                    "skill_relevance",
                    skill,
                    signal_weight=0.3,
                    source="job_action",
                    metadata={"action": action_type},
                )

    def get_top_preferences(
        self,
        canonical_user_id: str,
        preference_type: str,
        limit: int = 5,
    ) -> List[tuple[str, float]]:
        """
        Get top preferences for a given type.

        Args:
            canonical_user_id: User ID
            preference_type: "role_preference", "location_preference", "skill_relevance"
            limit: Max number of results

        Returns:
            List of (value, weight) tuples sorted by weight descending
        """
        profile = self.get_learning_profile(canonical_user_id)

        if preference_type == "role_preference":
            preferences = profile.role_preferences
        elif preference_type == "location_preference":
            preferences = profile.location_preferences
        elif preference_type == "skill_relevance":
            preferences = profile.skill_relevance
        else:
            return []

        # Sort by weight descending
        sorted_prefs = sorted(preferences.items(), key=lambda x: x[1], reverse=True)
        return sorted_prefs[:limit]

    def _update_weighted_dict(self, target_dict: Dict[str, float], key: str, weight: float) -> None:
        """Update a weighted dictionary using exponential moving average."""
        current = target_dict.get(key, 0.0)
        # EMA: new_value = alpha * new_weight + (1 - alpha) * old_value
        alpha = 0.3  # Learning rate
        target_dict[key] = alpha * weight + (1 - alpha) * current

    def _extract_role_from_title(self, title: str) -> Optional[str]:
        """Extract role from job title."""
        if not title:
            return None
        # Remove common prefixes/suffixes
        cleaned = title.strip()
        for prefix in ["Senior ", "Lead ", "Principal ", "Staff ", "Junior ", "Mid-level "]:
            cleaned = cleaned.replace(prefix, "")
        return cleaned[:50]  # Truncate if too long

    def _extract_skills_from_description(self, description: str) -> List[str]:
        """Extract skills from job description (simple keyword matching)."""
        if not description:
            return []

        # Common tech skills to look for
        skill_keywords = [
            "Python", "JavaScript", "React", "Node.js", "Java", "Go", "Rust",
            "AWS", "Azure", "GCP", "Docker", "Kubernetes", "SQL", "NoSQL",
            "Machine Learning", "Data Science", "DevOps", "CI/CD", "Git",
        ]

        desc_lower = description.lower()
        found_skills = []
        for skill in skill_keywords:
            if skill.lower() in desc_lower:
                found_skills.append(skill)

        return found_skills[:10]

    def _db_write_signal(self, canonical_user_id: str, signal: LearningSignal) -> None:
        """Write signal to database."""
        conn = get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'learning_signals'
                    )
                """)
                table_exists = cur.fetchone()[0]

                if not table_exists:
                    # Create table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS learning_signals (
                            id SERIAL PRIMARY KEY,
                            canonical_user_id VARCHAR(255) NOT NULL,
                            signal_type VARCHAR(100) NOT NULL,
                            signal_value TEXT NOT NULL,
                            signal_weight FLOAT NOT NULL,
                            source VARCHAR(50) NOT NULL,
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                            metadata JSONB,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_learning_signals_user
                        ON learning_signals(canonical_user_id, signal_type)
                    """)
                    conn.commit()

                # Insert signal
                import json
                cur.execute(
                    """
                    INSERT INTO learning_signals
                    (canonical_user_id, signal_type, signal_value, signal_weight, source, timestamp, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        canonical_user_id,
                        signal.signal_type,
                        signal.signal_value,
                        signal.signal_weight,
                        signal.source,
                        signal.timestamp,
                        json.dumps(signal.metadata),
                    ),
                )
                conn.commit()

        finally:
            conn.close()

    def _db_load_profile(self, canonical_user_id: str) -> LearningProfile:
        """Load learning profile from database."""
        profile = LearningProfile(canonical_user_id=canonical_user_id)

        conn = get_db_connection()
        if not conn:
            return profile

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT signal_type, signal_value, signal_weight, source, timestamp, metadata
                    FROM learning_signals
                    WHERE canonical_user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """,
                    (canonical_user_id,),
                )
                rows = cur.fetchall()

                for row in rows:
                    signal_type, signal_value, signal_weight, source, timestamp, metadata = row

                    if signal_type == "role_preference":
                        profile.role_preferences[signal_value] = signal_weight
                    elif signal_type == "location_preference":
                        profile.location_preferences[signal_value] = signal_weight
                    elif signal_type == "skill_relevance":
                        profile.skill_relevance[signal_value] = signal_weight
                    elif signal_type == "company_sentiment":
                        profile.company_sentiment[signal_value] = signal_weight
                    elif signal_type == "feedback":
                        profile.feedback_events.append({
                            "value": signal_value,
                            "weight": signal_weight,
                            "source": source,
                            "timestamp": timestamp.isoformat() if timestamp else None,
                            "metadata": metadata,
                        })

                if rows:
                    profile.last_updated = rows[0][4]

        finally:
            conn.close()

        return profile


# Module-level singleton
_learning_repository = LearningRepository()


def record_learning_signal(
    canonical_user_id: str,
    signal_type: str,
    signal_value: str,
    signal_weight: float = 0.5,
    source: str = "job_action",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Convenience function to record a learning signal."""
    return _learning_repository.record_signal(
        canonical_user_id=canonical_user_id,
        signal_type=signal_type,
        signal_value=signal_value,
        signal_weight=signal_weight,
        source=source,
        metadata=metadata,
    )


def get_learning_profile(canonical_user_id: str) -> LearningProfile:
    """Convenience function to get learning profile."""
    return _learning_repository.get_learning_profile(canonical_user_id)


def infer_signals_from_job_action(
    canonical_user_id: str,
    action_type: str,
    job: Dict[str, Any],
) -> None:
    """Convenience function to infer signals from job action."""
    _learning_repository.infer_signals_from_job_action(
        canonical_user_id=canonical_user_id,
        action_type=action_type,
        job=job,
    )
