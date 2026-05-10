"""Environment validation for Rico AI.

This module validates the runtime environment without failing the legacy daily
pipeline. Rico server/worker entrypoints can call it to show clear readiness
status for cloud deployment.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, asdict
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class EnvCheck:
    name: str
    required: bool
    present: bool
    purpose: str


@dataclass
class RicoEnvReport:
    ready_for_api: bool
    ready_for_db: bool
    ready_for_telegram: bool
    ready_for_openai: bool
    ready_for_jotform: bool
    checks: List[EnvCheck]

    def to_dict(self) -> Dict[str, object]:
        return {
            "ready_for_api": self.ready_for_api,
            "ready_for_db": self.ready_for_db,
            "ready_for_telegram": self.ready_for_telegram,
            "ready_for_openai": self.ready_for_openai,
            "ready_for_jotform": self.ready_for_jotform,
            "checks": [asdict(check) for check in self.checks],
        }


ENV_SPECS = [
    ("DATABASE_URL", True, "Neon/PostgreSQL persistence for Rico memory and profiles"),
    ("TELEGRAM_BOT_TOKEN", False, "Telegram bot messages and webhook replies"),
    ("TELEGRAM_CHAT_ID", False, "Legacy/default Telegram notification target"),
    ("OPENAI_API_KEY", False, "AI tool-calling, message generation, and advanced reasoning"),
    ("RICO_AI_PROVIDER", False, "AI provider: none|openai (default: none)"),
    ("JOTFORM_API_KEY", False, "Jotform onboarding CV/file retrieval"),
    ("JOTFORM_FORM_ID", False, "Rico onboarding form ID"),
    ("JOTFORM_WEBHOOK_SECRET", False, "Webhook verification when enabled"),
    ("REDIS_URL", False, "Background jobs, reminders, and alert queues"),
    ("RICO_ENABLE_AUTO_APPLY", False, "Feature flag; should default to false"),
    ("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", False, "Feature flag; should default to true"),
]


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_ai_provider() -> str:
    """Get the AI provider from environment.

    Returns:
        str: "none" or "openai". Defaults to "none" if not set or invalid.
    """
    provider = os.getenv("RICO_AI_PROVIDER", "none").strip().lower()
    if provider not in {"none", "openai"}:
        logger.warning(f"Invalid RICO_AI_PROVIDER value: {provider}. Using 'none'.")
        return "none"
    return provider


def get_rico_env_report() -> RicoEnvReport:
    checks = [
        EnvCheck(name=name, required=required, present=bool(os.getenv(name)), purpose=purpose)
        for name, required, purpose in ENV_SPECS
    ]
    present = {check.name: check.present for check in checks}
    return RicoEnvReport(
        ready_for_api=True,
        ready_for_db=present.get("DATABASE_URL", False),
        ready_for_telegram=present.get("TELEGRAM_BOT_TOKEN", False),
        ready_for_openai=present.get("OPENAI_API_KEY", False) or bool(os.getenv("OPEN_AI_API")),
        ready_for_jotform=(present.get("JOTFORM_FORM_ID", False) and present.get("JOTFORM_WEBHOOK_SECRET", False)),
        checks=checks,
    )


def safe_feature_defaults() -> Dict[str, bool]:
    return {
        "auto_apply_enabled": env_bool("RICO_ENABLE_AUTO_APPLY", False),
        "approval_required_for_applications": env_bool("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", True),
        "telegram_enabled": env_bool("RICO_ENABLE_TELEGRAM", True),
        "learning_enabled": env_bool("RICO_ENABLE_LEARNING", True),
    }
