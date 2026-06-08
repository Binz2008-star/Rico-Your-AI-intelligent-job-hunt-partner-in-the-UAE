#!/usr/bin/env python3
"""
Live test for LinkedIn Easy Apply V2 with real jobs
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set dry-run mode initially for safety
os.environ["AUTO_APPLY_ENABLED"] = "true"
os.environ["AUTO_APPLY_DRY_RUN"] = "true"
os.environ["AUTO_APPLY_MAX_PER_RUN"] = "2"

from src.job_sources import get_jobs
from src.scoring import score_job
from src.auto_apply_v2 import run_auto_apply_v2
from src.profile import get_target_roles

def main():
    print("=" * 70)
    print("LINKEDIN EASY APPLY V2 - LIVE TEST WITH REAL JOBS")
    print("=" * 70)
    
    # Get target roles from profile
    target_roles = get_target_roles()
    print(f"\nTarget roles: {target_roles}")
    
    # Fetch real jobs
    print("\nFetching jobs from job sources...")
    try:
        jobs = get_jobs(target_roles=target_roles)
        print(f"Fetched {len(jobs)} jobs")
    except Exception as e:
        print(f"❌ Error fetching jobs: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    if not jobs:
        print("❌ No jobs found")
        return 1
    
    # Filter for LinkedIn jobs only
    linkedin_jobs = [j for j in jobs if "linkedin.com/jobs/view" in j.get("link", "")]
    print(f"LinkedIn jobs: {len(linkedin_jobs)}")
    
    if not linkedin_jobs:
        print("❌ No LinkedIn jobs found")
        return 1
    
    # Score jobs
    print("\nScoring jobs...")
    for job in linkedin_jobs:
        try:
            score = score_job(job)
            job["score"] = score
        except Exception as e:
            print(f"Warning: Error scoring job: {e}")
            job["score"] = 0
    
    # Filter by score threshold
    score_threshold = 75
    high_score_jobs = [j for j in linkedin_jobs if j.get("score", 0) >= score_threshold]
    print(f"Jobs with score >= {score_threshold}: {len(high_score_jobs)}")
    
    if not high_score_jobs:
        print(f"❌ No jobs with score >= {score_threshold}")
        return 1
    
    # Take top jobs
    top_jobs = sorted(high_score_jobs, key=lambda x: x.get("score", 0), reverse=True)[:5]
    print(f"\nTop {len(top_jobs)} jobs:")
    for i, job in enumerate(top_jobs, 1):
        print(f"  {i}. {job.get('title')} at {job.get('company')} - Score: {job.get('score')}")
    
    # Run LinkedIn V2
    print("\n" + "=" * 70)
    print("RUNNING LINKEDIN EASY APPLY V2")
    print("=" * 70)
    print(f"Mode: DRY-RUN (safe)")
    print(f"Jobs to process: {len(top_jobs)}")
    print()
    
    try:
        results = run_auto_apply_v2(top_jobs, max_applies=2, headless=False)
        
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        
        for i, result in enumerate(results, 1):
            print(f"\nJob {i}:")
            print(f"  Title: {result.title}")
            print(f"  Company: {result.company}")
            print(f"  Status: {result.status.value}")
            print(f"  Message: {result.message}")
            print(f"  Score: {result.score}")
        
        print("\n" + "=" * 70)
        print(f"Total jobs processed: {len(results)}")
        print(f"Success: {sum(1 for r in results if r.status.value == 'success')}")
        print(f"Failed: {sum(1 for r in results if r.status.value == 'failed')}")
        print(f"Skipped: {sum(1 for r in results if r.status.value == 'dry_run')}")
        print(f"Rate limited: {sum(1 for r in results if r.status.value == 'rate_limited')}")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during LinkedIn V2: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
