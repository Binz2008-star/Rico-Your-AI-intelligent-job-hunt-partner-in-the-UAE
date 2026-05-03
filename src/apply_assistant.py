import webbrowser
import time
from src.message_generator import generate_message
from src.applications import is_applied, mark_applied, filter_unapplied_jobs, get_application_stats


def open_job_links(top_jobs):
    """Open top job links in browser and display application messages."""
    if not top_jobs:
        print("No jobs to apply for.")
        return

    # Filter out already applied jobs
    unapplied_jobs = filter_unapplied_jobs(top_jobs)

    if not unapplied_jobs:
        print("All top jobs have already been applied to.")
        stats = get_application_stats()
        print(f"📊 Application Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")
        return

    print(f"\n🚀 APPLY ASSISTANT - Top {len(unapplied_jobs)} Unapplied Jobs")
    print("=" * 60)

    for i, (job, score) in enumerate(unapplied_jobs[:5], 1):
        title = job.get('title', 'N/A')
        company = job.get('company', 'N/A')
        location = job.get('location', 'N/A')
        link = job.get('link', '')
        score = job.get('score', score)

        print(f"\n📌 JOB #{i}")
        print(f"Title: {title}")
        print(f"Company: {company}")
        print(f"Location: {location}")
        print(f"Score: {score}")
        print(f"Link: {link}")

        # Generate application message
        app_message = generate_message(job)
        print(f"\n📝 APPLICATION MESSAGE:")
        print("-" * 40)
        print(app_message)
        print("-" * 40)

        # Open in browser
        if link and link.startswith('http'):
            try:
                print(f"\n🌐 Opening job application in browser...")
                webbrowser.open(link)
                time.sleep(2)  # Brief pause between openings
            except Exception as e:
                print(f"⚠️ Could not open link: {e}")
        else:
            print("⚠️ No valid link available")

        # Ask if user applied
        if i < len(unapplied_jobs[:5]):  # Don't wait after last job
            response = input(f"\n✅ Did you apply to this job? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                mark_applied(job)
                print("✅ Job marked as applied")
            else:
                print("⏭️ Job not marked as applied")

    print(f"\n✅ Apply assistant completed!")
    print("💡 Tips:")
    print("   - Review each application carefully before submitting")
    print("   - Customize the message as needed")
    print("   - Check for additional requirements in the job description")
    stats = get_application_stats()
    print(f"\n📊 Application Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")


def get_confidence_level(score):
    """Calculate confidence level based on job score."""
    if score >= 85:
        return "Very High", "⭐⭐⭐⭐⭐"
    elif score >= 75:
        return "High", "⭐⭐⭐⭐"
    elif score >= 65:
        return "Medium", "⭐⭐⭐"
    elif score >= 50:
        return "Low", "⭐⭐"
    else:
        return "Very Low", "⭐"


def show_top_jobs_with_confidence(matches):
    """Show top 3 BEST jobs with confidence levels and explanations."""
    if not matches:
        print("No jobs to display.")
        return []

    # Sort by score and take top 3
    top_jobs = sorted(matches, key=lambda x: x[1], reverse=True)[:3]

    print(f"\n🎯 TOP 3 BEST JOBS")
    print("=" * 60)

    selected_jobs = []

    for i, (job, score) in enumerate(top_jobs, 1):
        title = job.get('title', 'N/A')
        company = job.get('company', 'N/A')
        location = job.get('location', 'N/A')
        link = job.get('link', '')

        confidence, stars = get_confidence_level(score)
        explanation = job.get('profile_explanation', 'Relevant executive operations experience')

        print(f"\n📌 JOB #{i} - {confidence} Confidence {stars}")
        print(f"Title: {title}")
        print(f"Company: {company}")
        print(f"Location: {location}")
        print(f"Score: {score}")
        print(f"Why it matches: {explanation}")
        print(f"Link: {link}")

        # Ask user if they want to apply
        response = input(f"\n🤔 Apply to this job? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            selected_jobs.append((job, score))
            print("✅ Added to application list")
        else:
            print("⏭️ Skipped")

    return selected_jobs


def run_apply_assistant(matches):
    """Run apply assistant with top scored jobs."""
    if not matches:
        print("No high-quality matches to apply for.")
        return

    # Show top 3 jobs with confidence levels
    selected_jobs = show_top_jobs_with_confidence(matches)

    if not selected_jobs:
        print("No jobs selected for application.")
        return

    print(f"\n🚀 APPLY ASSISTANT - {len(selected_jobs)} Selected Jobs")
    print("=" * 60)

    # Filter out already applied jobs
    unapplied_jobs = filter_unapplied_jobs(selected_jobs)

    if not unapplied_jobs:
        print("All selected jobs have already been applied to.")
        stats = get_application_stats()
        print(f"📊 Application Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")
        return

    for i, (job, score) in enumerate(unapplied_jobs, 1):
        title = job.get('title', 'N/A')
        company = job.get('company', 'N/A')
        location = job.get('location', 'N/A')
        link = job.get('link', '')

        print(f"\n📌 APPLICATION #{i}")
        print(f"Title: {title}")
        print(f"Company: {company}")
        print(f"Score: {score}")

        # Generate application message
        app_message = generate_message(job)
        print(f"\n📝 APPLICATION MESSAGE:")
        print("-" * 40)
        print(app_message)
        print("-" * 40)

        # Open in browser
        if link and link.startswith('http'):
            try:
                print(f"\n🌐 Opening job application in browser...")
                webbrowser.open(link)
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ Could not open link: {e}")
        else:
            print("⚠️ No valid link available")

        # Ask if user applied
        if i < len(unapplied_jobs):
            response = input(f"\n✅ Did you apply to this job? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                mark_applied(job)
                print("✅ Job marked as applied")
            else:
                print("⏭️ Job not marked as applied")

    print(f"\n✅ Apply assistant completed!")
    stats = get_application_stats()
    print(f"\n📊 Application Stats: {stats['total_applied']} applied, {stats['interviews_scheduled']} interviews")
