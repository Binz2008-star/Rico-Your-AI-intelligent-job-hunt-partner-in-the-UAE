"""
src/apply_assistant.py
Human-in-the-loop apply assistant — LOCAL INTERACTIVE MODE ONLY.

All functions in this module are no-ops unless RICO_INTERACTIVE_APPLY=1 is set.
In cloud/CI/Docker/cron environments this variable must not be set.
"""
from __future__ import annotations

import logging
import os
import time
import webbrowser
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

RICO_INTERACTIVE_APPLY = os.getenv("RICO_INTERACTIVE_APPLY", "").strip().lower() in {"1", "true", "yes", "on"}


def open_job_links(top_jobs: List[Tuple[Dict[str, Any], int]]) -> None:
    """Open top job links in browser and collect apply confirmations (local only)."""
    if not RICO_INTERACTIVE_APPLY:
        logger.info("open_job_links_skipped interactive_mode_disabled")
        return
    if not top_jobs:
        print("No jobs to apply for.")
        return

    from src.message_generator import generate_message
    from src.applications import is_applied, mark_applied, filter_unapplied_jobs, get_application_stats

    unapplied_jobs = filter_unapplied_jobs(top_jobs)
    if not unapplied_jobs:
        stats = get_application_stats()
        print(f"All top jobs already applied. Stats: {stats['total_applied']} applied.")
        return

    print(f"\n APPLY ASSISTANT - Top {len(unapplied_jobs)} Unapplied Jobs")
    print("=" * 60)

    for i, (job, score) in enumerate(unapplied_jobs[:5], 1):
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        location = job.get("location", "N/A")
        link = job.get("link", "")
        score = job.get("score", score)

        print(f"\n JOB #{i}: {title} @ {company} ({location}) — score {score}")
        app_message = generate_message(job)
        print(f"\nApplication message:\n{'-'*40}\n{app_message}\n{'-'*40}")

        if link and link.startswith("http"):
            try:
                print(f"\nOpening in browser: {link}")
                webbrowser.open(link)
                time.sleep(2)
            except Exception as exc:
                logger.warning("webbrowser_open_failed: %s", exc)
        else:
            print(" No valid link")

        if i < len(unapplied_jobs[:5]):
            response = input("\n Did you apply? (y/n): ").lower().strip()
            if response in ("y", "yes"):
                mark_applied(job)
                print(" Marked as applied")
            else:
                print(" Skipped")

    stats = get_application_stats()
    print(f"\nDone. Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")


def get_confidence_level(score: int) -> Tuple[str, str]:
    if score >= 85:
        return "Very High", "*****"
    if score >= 75:
        return "High", "****"
    if score >= 65:
        return "Medium", "***"
    if score >= 50:
        return "Low", "**"
    return "Very Low", "*"


def show_top_jobs_with_confidence(matches: List[Tuple[Dict[str, Any], int]]) -> List[Tuple[Dict[str, Any], int]]:
    """Interactively present top 3 jobs and return the ones user confirms. Local only."""
    if not RICO_INTERACTIVE_APPLY:
        logger.info("show_top_jobs_skipped interactive_mode_disabled")
        return []
    if not matches:
        print("No jobs to display.")
        return []

    top_jobs = sorted(matches, key=lambda x: x[1], reverse=True)[:3]
    print(f"\n TOP 3 BEST JOBS")
    print("=" * 60)

    selected = []
    for i, (job, score) in enumerate(top_jobs, 1):
        confidence, stars = get_confidence_level(score)
        print(f"\n JOB #{i} — {confidence} {stars}")
        print(f"Title:   {job.get('title', 'N/A')}")
        print(f"Company: {job.get('company', 'N/A')}")
        print(f"Score:   {score}")
        print(f"Why:     {job.get('profile_explanation', 'Relevant experience')}")
        print(f"Link:    {job.get('link', '')}")

        response = input("\n Apply to this job? (y/n): ").lower().strip()
        if response in ("y", "yes"):
            selected.append((job, score))
            print(" Added to application list")
        else:
            print(" Skipped")

    return selected


def run_apply_assistant(matches: List[Tuple[Dict[str, Any], int]]) -> None:
    """Run the interactive apply assistant. No-op unless RICO_INTERACTIVE_APPLY=1."""
    if not RICO_INTERACTIVE_APPLY:
        logger.info("run_apply_assistant_skipped interactive_mode_disabled")
        return
    if not matches:
        print("No high-quality matches.")
        return

    from src.applications import filter_unapplied_jobs, mark_applied, get_application_stats
    from src.message_generator import generate_message

    selected_jobs = show_top_jobs_with_confidence(matches)
    if not selected_jobs:
        print("No jobs selected.")
        return

    unapplied_jobs = filter_unapplied_jobs(selected_jobs)
    if not unapplied_jobs:
        stats = get_application_stats()
        print(f"All selected jobs already applied. Stats: {stats['total_applied']} applied.")
        return

    print(f"\n APPLYING TO {len(unapplied_jobs)} SELECTED JOBS")
    print("=" * 60)

    for i, (job, score) in enumerate(unapplied_jobs, 1):
        link = job.get("link", "")
        print(f"\n APPLICATION #{i}: {job.get('title','N/A')} @ {job.get('company','N/A')} — score {score}")

        app_message = generate_message(job)
        print(f"\nMessage:\n{'-'*40}\n{app_message}\n{'-'*40}")

        if link and link.startswith("http"):
            try:
                webbrowser.open(link)
                time.sleep(2)
            except Exception as exc:
                logger.warning("webbrowser_open_failed: %s", exc)

        if i < len(unapplied_jobs):
            response = input("\n Did you apply? (y/n): ").lower().strip()
            if response in ("y", "yes"):
                mark_applied(job)
                print(" Marked as applied")
            else:
                print(" Skipped")

    stats = get_application_stats()
    print(f"\nDone. Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")
