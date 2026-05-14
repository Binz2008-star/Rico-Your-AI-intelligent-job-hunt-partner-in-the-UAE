"""CLI command to import complete Rico profile data from JSON file."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.repositories.profile_repo import upsert_profile
from src.repositories.onboarding_repo import mark_onboarding_complete
from src.services.profile_context_resolver import resolve_profile_context

logger = logging.getLogger(__name__)


def _load_json(path: str) -> dict[str, Any]:
    """Load and validate JSON profile file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Profile file not found: {path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Profile import file must contain a JSON object")

    return data


def _resolve_user_id(data: dict[str, Any], explicit_user_id: Optional[str]) -> str:
    """Resolve user_id from explicit flag or profile data."""
    user_id = (
        explicit_user_id
        or data.get("external_user_id")
        or data.get("email")
        or data.get("user_id")
    )

    if not user_id:
        raise ValueError("Missing user_id. Provide --user-id or email/external_user_id in file.")

    return str(user_id).strip().lower()


def _clean_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Clean profile data to only allowed fields."""
    allowed = {
        "email",
        "name",
        "phone",
        "location",
        "target_roles",
        "preferred_cities",
        "salary_expectation",
        "salary_expectation_aed",
        "minimum_salary_aed",
        "skills",
        "industries",
        "years_experience",
        "visa_status",
        "notice_period",
        "cv_text",
        "cv_structured",
        "telegram_chat_id",
        "telegram_username",
        "profile_creation_mode",
    }

    return {
        key: value
        for key, value in data.items()
        if key in allowed and value not in (None, "", [], {})
    }


def import_profile_file(
    *,
    file_path: str,
    user_id: Optional[str] = None,
    run_jobs: bool = False,
    send_telegram: bool = False,
) -> dict[str, Any]:
    """Import profile from JSON file and persist to database."""
    data = _load_json(file_path)
    resolved_user_id = _resolve_user_id(data, user_id)

    profile_updates = _clean_profile(data)
    profile_updates["profile_creation_mode"] = "file_import"

    upsert_profile(user_id=resolved_user_id, updates=profile_updates)
    mark_onboarding_complete(resolved_user_id)

    context = resolve_profile_context(resolved_user_id)

    result = {
        "ok": True,
        "user_id": resolved_user_id,
        "completeness_score": getattr(context, "completeness_score", None),
        "target_roles": getattr(context, "target_roles", None),
        "preferred_cities": getattr(context, "preferred_cities", None),
    }

    if run_jobs:
        # TODO: Connect to existing job pipeline entrypoint
        # from src.services.jobs_service import run_personalized_job_search
        # result["jobs"] = run_personalized_job_search(resolved_user_id)
        result["jobs"] = "TODO: connect existing job pipeline entrypoint"

    if send_telegram:
        # TODO: Connect to existing Telegram alert entrypoint
        # from src.services.telegram_service import send_clean_profile_import_alert
        # send_clean_profile_import_alert(resolved_user_id, result)
        result["telegram"] = "TODO: connect existing Telegram alert entrypoint"

    return result


def main() -> None:
    """CLI entry point for profile import."""
    parser = argparse.ArgumentParser(description="Import a complete Rico profile data file.")
    parser.add_argument("--file", required=True, help="Path to JSON profile file")
    parser.add_argument("--user-id", default=None, help="Override user id/email")
    parser.add_argument("--run-jobs", action="store_true", help="Run job pipeline after import")
    parser.add_argument("--send-telegram", action="store_true", help="Send Telegram alert after import")

    args = parser.parse_args()

    result = import_profile_file(
        file_path=args.file,
        user_id=args.user_id,
        run_jobs=args.run_jobs,
        send_telegram=args.send_telegram,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
