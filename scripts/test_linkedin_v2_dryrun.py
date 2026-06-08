#!/usr/bin/env python3
"""
Dry-run test for LinkedIn Easy Apply V2
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set dry-run mode
os.environ["AUTO_APPLY_ENABLED"] = "true"
os.environ["AUTO_APPLY_DRY_RUN"] = "true"
os.environ["AUTO_APPLY_MAX_PER_RUN"] = "2"

from src.auto_apply_v2 import run_auto_apply_v2

# Create mock jobs
mock_jobs = [
    {
        "title": "HSE Manager",
        "company": "Test Company 1",
        "link": "https://www.linkedin.com/jobs/view/123456789",
        "score": 85,
        "description": "Test job description",
        "location": "Dubai, UAE",
    },
    {
        "title": "QHSE Manager",
        "company": "Test Company 2",
        "link": "https://www.linkedin.com/jobs/view/987654321",
        "score": 90,
        "description": "Test job description",
        "location": "Abu Dhabi, UAE",
    },
]

print("Starting LinkedIn Easy Apply V2 Dry-Run Test...")
print(f"Jobs to process: {len(mock_jobs)}")
print(f"Dry-run mode: ENABLED")
print()

try:
    results = run_auto_apply_v2(mock_jobs, max_applies=2, headless=False)
    
    print("\n" + "=" * 70)
    print("DRY-RUN TEST RESULTS")
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
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error during dry-run test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
