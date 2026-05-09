"""Persistent memory store for Rico AI.

This file gives Rico a lightweight multi-user memory layer before a full
PostgreSQL profile service is added. It stores user profiles, preferences,
chat history, agent permissions, and learning signals in JSON files so Rico
can behave like a real agent immediately.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rico_agent import RicoAgentSettings, RicoProfile

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RICO_MEMORY_DIR = DATA_DIR / "rico"
RICO_MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class RicoMemoryStore:
    """JSON-backed Rico memory store."""

    def _profile_path(self, user_id: str) -> Path:
        return RICO_MEMORY_DIR / f"profile_{user_id}.json"

    def _chat_path(self, user_id: str) -> Path:
        return RICO_MEMORY_DIR / f"chat_{user_id}.json"

    def _signals_path(self, user_id: str) -> Path:
        return RICO_MEMORY_DIR / f"signals_{user_id}.json"

    def save_profile(self, profile: RicoProfile) -> None:
        payload = asdict(profile)
        payload["updated_at"] = datetime.utcnow().isoformat()
        self._profile_path(profile.user_id).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_profile(self, user_id: str) -> Optional[RicoProfile]:
        path = self._profile_path(user_id)
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        settings_data = data.pop("settings", {}) or {}
        data.pop("updated_at", None)
        settings = RicoAgentSettings(**settings_data)
        return RicoProfile(**data, settings=settings)

    def upsert_profile_from_dict(self, user_id: str, updates: Dict[str, Any]) -> RicoProfile:
        profile = self.load_profile(user_id)
        if profile is None:
            profile = RicoProfile(user_id=user_id)

        settings_updates = updates.pop("settings", None)
        for key, value in updates.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        if settings_updates:
            for key, value in settings_updates.items():
                if hasattr(profile.settings, key) and value is not None:
                    setattr(profile.settings, key, value)

        self.save_profile(profile)
        return profile

    def append_chat_message(self, user_id: str, role: str, message: str) -> None:
        history = self.load_chat_history(user_id)
        history.append({
            "role": role,
            "message": message,
            "created_at": datetime.utcnow().isoformat(),
        })
        self._chat_path(user_id).write_text(
            json.dumps(history[-200:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._chat_path(user_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def record_learning_signal(self, user_id: str, job_id: str, action: str) -> None:
        signals = self.load_learning_signals(user_id)
        signals.append({
            "job_id": job_id,
            "action": action,
            "created_at": datetime.utcnow().isoformat(),
        })
        self._signals_path(user_id).write_text(
            json.dumps(signals[-500:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_learning_signals(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._signals_path(user_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def list_profiles(self) -> List[str]:
        return [p.stem.replace("profile_", "") for p in RICO_MEMORY_DIR.glob("profile_*.json")]
