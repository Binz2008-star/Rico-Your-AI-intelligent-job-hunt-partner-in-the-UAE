from src.job_sources import get_jobs
from src.scoring import score_job, get_profile_explanation
from src.message_generator import generate_message
from src.filter import filter_new_jobs
from src.notifier import send_email, format_jobs_email
from src.telegram_bot import send_telegram_message, format_telegram_jobs
from src.job_history import add_jobs_to_history
from src.apply_assistant import run_apply_assistant
from src.db import init_db, save_job, get_seen_links, is_db_available


def run_pipeline():
    """Execute the complete job hunting pipeline: fetch, filter, score, notify."""
    # Initialize database if available
    if is_db_available():
        print("🗄️ Database available, initializing...")
        if init_db():
            print("✅ Database ready")
        else:
            print("⚠️ Database initialization failed, using JSON fallback")

    jobs = get_jobs()
    jobs = filter_new_jobs(jobs)
    print(f"Found {len(jobs)} new jobs after filtering")
    matches = []
    all_scored_jobs = []

    for job in jobs:
        score = score_job(job)
        all_scored_jobs.append((job, score))
        if score >= 65:  # Increased threshold for Roben's profile
            matches.append((job, score))

        # Save to database if available
        if is_db_available():
            save_job(job, score)

    matches.sort(key=lambda x: x[1], reverse=True)

    print(f"Found {len(matches)} high-quality matches")

    for job, score in matches[:20]:
        print("\n=== JOB MATCH ===")
        print(job.get("title"), "-", job.get("company"))
        print("Location:", job.get("location"))
        print("Score:", score)
        print("Why it matches:", get_profile_explanation(job))
        print("Apply:", job.get("link"))
        print(generate_message(job))

    # Save to JSON history (backup)
    add_jobs_to_history(all_scored_jobs)

    # Send email notification (optional)
    try:
        email_content = format_jobs_email(matches)
        email_subject = "Job Hunting Daily Report" if matches else "No New Jobs Today"
        if send_email(email_subject, email_content):
            print("✅ Email notification sent successfully")
        else:
            print("⚠️ Email notification failed (continuing with Telegram)")
    except Exception as e:
        print(f"⚠️ Email notification error: {e} (continuing with Telegram)")

    # Send Telegram notification
    try:
        telegram_content = format_telegram_jobs(matches)
        if send_telegram_message(telegram_content):
            print("✅ Telegram notification sent successfully")
        else:
            print("⚠️ Telegram notification failed")
    except Exception as e:
        print(f"⚠️ Telegram notification error: {e}")

    # Apply assistant for top jobs
    if matches:
        try:
            run_apply_assistant(matches)
        except Exception as e:
            print(f"⚠️ Apply assistant error: {e}")
    else:
        print("No matches for apply assistant.")


def main():
    run_pipeline()


if __name__ == "__main__":
    main()
