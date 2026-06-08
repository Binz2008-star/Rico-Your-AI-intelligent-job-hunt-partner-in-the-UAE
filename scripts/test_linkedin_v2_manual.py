#!/usr/bin/env python3
"""
Manual test for LinkedIn Easy Apply V2 with realistic job URLs
This script uses pre-defined LinkedIn job URLs for testing
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

from src.auto_apply_v2 import run_auto_apply_v2

# Realistic LinkedIn job URLs (HSE-related roles in UAE)
# These are example URLs - user can replace with actual job URLs
REALISTIC_JOBS = [
    {
        "title": "HSE Manager",
        "company": "Construction Company",
        "link": "https://www.linkedin.com/jobs/view/1234567890",
        "score": 85,
        "description": "HSE Manager role with 5+ years experience in construction",
        "location": "Dubai, UAE",
    },
    {
        "title": "QHSE Manager",
        "company": "Oil & Gas Company",
        "link": "https://www.linkedin.com/jobs/view/0987654321",
        "score": 90,
        "description": "QHSE Manager for offshore operations",
        "location": "Abu Dhabi, UAE",
    },
    {
        "title": "EHS Manager",
        "company": "Engineering Firm",
        "link": "https://www.linkedin.com/jobs/view/1122334455",
        "score": 88,
        "description": "EHS Manager for industrial projects",
        "location": "Sharjah, UAE",
    },
]

def main():
    print("=" * 70)
    print("LINKEDIN EASY APPLY V2 - MANUAL TEST")
    print("=" * 70)
    
    print("\nThis test uses realistic LinkedIn job URLs.")
    print("You can replace the URLs in the script with actual job URLs.")
    print()
    
    print("Test Jobs:")
    for i, job in enumerate(REALISTIC_JOBS, 1):
        print(f"  {i}. {job['title']} at {job['company']} - Score: {job['score']}")
        print(f"     URL: {job['link']}")
    
    print("\n" + "=" * 70)
    print("RUNNING LINKEDIN EASY APPLY V2")
    print("=" * 70)
    print(f"Mode: DRY-RUN (safe)")
    print(f"Jobs to process: {len(REALISTIC_JOBS)}")
    print()
    
    try:
        results = run_auto_apply_v2(REALISTIC_JOBS, max_applies=2, headless=False)
        
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
        
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Replace the job URLs in this script with actual LinkedIn job URLs")
        print("2. Set AUTO_APPLY_DRY_RUN=false in .env for live testing")
        print("3. Run: python scripts/test_linkedin_v2_manual.py")
        print("4. Monitor results in data/auto_apply_metrics_v2.json")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during LinkedIn V2: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
