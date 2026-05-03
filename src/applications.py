import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

APPLIED_JOBS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "applied_jobs.json")


def load_applied_jobs() -> List[Dict[str, Any]]:
    """Load applied jobs from JSON file."""
    try:
        with open(APPLIED_JOBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_applied_jobs(jobs: List[Dict[str, Any]]) -> None:
    """Save applied jobs to JSON file."""
    with open(APPLIED_JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def get_job_id(job: Dict[str, Any]) -> str:
    """Generate unique job ID for tracking."""
    title = job.get('title', '').strip()
    company = job.get('company', '').strip()
    location = job.get('location', '').strip()
    return f"{title}_{company}_{location}".lower().replace(' ', '_')


def mark_applied(job: Dict[str, Any], status: str = "applied") -> bool:
    """Mark a job as applied with status."""
    applied_jobs = load_applied_jobs()
    job_id = get_job_id(job)
    
    # Check if already applied
    for applied_job in applied_jobs:
        if applied_job.get('job_id') == job_id:
            print(f"Job already marked as applied: {job.get('title', '')}")
            return False
    
    # Add new applied job
    applied_job_entry = {
        "job_id": job_id,
        "title": job.get('title', ''),
        "company": job.get('company', ''),
        "location": job.get('location', ''),
        "link": job.get('link', ''),
        "score": job.get('score', 0),
        "status": status,
        "date_applied": datetime.now().isoformat(),
        "date_updated": datetime.now().isoformat(),
        "notes": "",
        "interview_date": None,
        "rejection_reason": None
    }
    
    applied_jobs.append(applied_job_entry)
    save_applied_jobs(applied_jobs)
    
    print(f"✅ Marked as applied: {job.get('title', '')} - {job.get('company', '')}")
    return True


def is_applied(job: Dict[str, Any]) -> bool:
    """Check if a job has already been applied to."""
    job_id = get_job_id(job)
    applied_jobs = load_applied_jobs()
    
    for applied_job in applied_jobs:
        if applied_job.get('job_id') == job_id:
            return True
    
    return False


def update_application_status(job: Dict[str, Any], status: str, notes: str = "") -> bool:
    """Update application status (applied/interview/rejected)."""
    applied_jobs = load_applied_jobs()
    job_id = get_job_id(job)
    
    for applied_job in applied_jobs:
        if applied_job.get('job_id') == job_id:
            applied_job['status'] = status
            applied_job['date_updated'] = datetime.now().isoformat()
            
            if notes:
                applied_job['notes'] = notes
            
            if status == "interview" and not applied_job.get('interview_date'):
                applied_job['interview_date'] = datetime.now().isoformat()
            
            if status == "rejected" and notes:
                applied_job['rejection_reason'] = notes
            
            save_applied_jobs(applied_jobs)
            print(f"✅ Updated status to {status}: {job.get('title', '')}")
            return True
    
    print(f"❌ Applied job not found: {job.get('title', '')}")
    return False


def get_applied_jobs() -> List[Dict[str, Any]]:
    """Get all applied jobs."""
    return load_applied_jobs()


def get_application_stats() -> Dict[str, Any]:
    """Get application statistics."""
    applied_jobs = load_applied_jobs()
    
    if not applied_jobs:
        return {
            "total_applied": 0,
            "status_breakdown": {},
            "interviews_scheduled": 0,
            "rejections": 0,
            "pending": 0,
            "success_rate": 0.0
        }
    
    status_counts = {}
    interviews = 0
    rejections = 0
    pending = 0
    
    for job in applied_jobs:
        status = job.get('status', 'applied')
        status_counts[status] = status_counts.get(status, 0) + 1
        
        if status == "interview":
            interviews += 1
        elif status == "rejected":
            rejections += 1
        elif status == "applied":
            pending += 1
    
    success_rate = (interviews / len(applied_jobs)) * 100 if applied_jobs else 0.0
    
    return {
        "total_applied": len(applied_jobs),
        "status_breakdown": status_counts,
        "interviews_scheduled": interviews,
        "rejections": rejections,
        "pending": pending,
        "success_rate": round(success_rate, 1)
    }


def filter_unapplied_jobs(jobs_with_scores: List[tuple]) -> List[tuple]:
    """Filter out jobs that have already been applied to."""
    unapplied = []
    
    for job, score in jobs_with_scores:
        if not is_applied(job):
            unapplied.append((job, score))
    
    return unapplied


def mark_job_interactive(job: Dict[str, Any]) -> None:
    """Interactive function to mark a job as applied."""
    title = job.get('title', 'N/A')
    company = job.get('company', 'N/A')
    
    print(f"\n📝 Mark Job as Applied")
    print(f"Title: {title}")
    print(f"Company: {company}")
    
    status_options = ["applied", "interview", "rejected"]
    print(f"Status options: {', '.join(status_options)}")
    
    status = input("Enter status (default: applied): ").strip().lower()
    if not status:
        status = "applied"
    
    if status not in status_options:
        print("❌ Invalid status. Using 'applied'.")
        status = "applied"
    
    notes = input("Add notes (optional): ").strip()
    
    if mark_applied(job, status):
        if notes:
            update_application_status(job, status, notes)
        print(f"✅ Job marked as {status}")
    else:
        print("❌ Failed to mark job as applied")


def main():
    """Test application tracking functions."""
    print("🧪 Testing Application Tracking")
    
    # Test with sample job
    sample_job = {
        'title': 'Executive Assistant to CEO',
        'company': 'Test Company',
        'location': 'Dubai, UAE',
        'link': 'https://example.com/job1',
        'score': 75
    }
    
    # Test marking as applied
    print("\n1. Testing mark_applied():")
    mark_applied(sample_job)
    
    # Test checking if applied
    print("\n2. Testing is_applied():")
    print(f"Is applied: {is_applied(sample_job)}")
    
    # Test getting stats
    print("\n3. Testing get_application_stats():")
    stats = get_application_stats()
    print(f"Stats: {stats}")
    
    # Test filtering unapplied jobs
    print("\n4. Testing filter_unapplied_jobs():")
    jobs_with_scores = [
        (sample_job, 75),
        ({
            'title': 'Chief of Staff',
            'company': 'Tech Startup',
            'location': 'Abu Dhabi, UAE',
            'link': 'https://example.com/job2',
            'score': 68
        }, 68)
    ]
    
    unapplied = filter_unapplied_jobs(jobs_with_scores)
    print(f"Unapplied jobs: {len(unapplied)}")


if __name__ == "__main__":
    main()
