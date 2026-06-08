#!/usr/bin/env python3
"""
Test script for LinkedIn job scraper.

⚠️  CRITICAL PRODUCTION WARNING ⚠️
This script is for LOCAL MANUAL TESTING ONLY.

LinkedIn Compliance Risks:
- LinkedIn prohibits scraping and automation without explicit permission
- Using this script may result in account restriction or termination
- robots.txt explicitly disallows automated access
- NOT SUITABLE for production integration or CI/CD pipelines

Usage:
- Local manual testing only
- Never run in production environments
- Never integrate into automated job pipelines
- Use at your own risk with personal accounts only

Version: 2.0.0
Status: SANDBOX/PROOF-OF-CONCEPT ONLY
"""

import sys
import os
import logging
import signal
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.linkedin_job_scraper import scrape_linkedin_jobs

# Configure structured production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("scraper_test")

def execute_scraper_test(config: Dict[str, Any]) -> int:
    """
    Executes the LinkedIn scraping pipeline test under strict environment isolation.

    ⚠️  WARNING: This is for local manual testing only. LinkedIn prohibits automated scraping.

    Args:
        config: Configuration dictionary containing search parameters and browser state.
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    logger.info("Initializing LinkedIn Scraper validation suite (SANDBOX MODE ONLY).")

    # Capture original environment state for rollback safety
    original_email = os.environ.get("LINKEDIN_EMAIL")
    original_password = os.environ.get("LINKEDIN_PASSWORD")

    # Set timeout for safety (5 minutes max)
    TIMEOUT_SECONDS = 300

    def timeout_handler(signum, frame):
        logger.error("Scraping timeout reached after %d seconds", TIMEOUT_SECONDS)
        raise TimeoutError("Scraping operation timed out")

    # Set signal handler for timeout
    signal.signal(signal.SIGALRM, timeout_handler)

    try:
        # Set timeout
        signal.alarm(TIMEOUT_SECONDS)

        # Enforce manual sandbox mode by clearing credentials in a localized runtime scope
        if config.get("force_manual_login", True):
            logger.info("Sandbox mode active: Temporarily suppressing auto-login credentials.")
            os.environ["LINKEDIN_EMAIL"] = ""
            os.environ["LINKEDIN_PASSWORD"] = ""

        # Execute core scraping engine
        jobs: List[Dict[str, Any]] = scrape_linkedin_jobs(
            keywords=config["keywords"],
            location=config["location"],
            max_jobs=config["max_jobs"],
            easy_apply_only=config["easy_apply_only"],
            headless=config["headless"]
        )

        # Cancel timeout on success
        signal.alarm(0)

        # Evaluate and log response structure
        if not jobs:
            logger.error("Scraping execution finished with empty results dataset.")
            print("\n❌ No jobs found. Verify UI elements alignment or CAPTCHA blocks.")
            return 1

        print("\n" + "=" * 70)
        print(f"✅ SUCCESSFULLY SCRAPED {len(jobs)} JOBS")
        print("=" * 70)

        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job.get('title', 'Unknown Title')}")
            print(f"   Company: {job.get('company', 'N/A')}")
            print(f"   Location: {job.get('location', 'N/A')}")
            print(f"   Link: {job.get('link', 'N/A')}")
            print(f"   Applicants: {job.get('applicants', 'N/A')}")
            desc = job.get('description', '')
            print(f"   Description Summary: {desc[:100]}..." if len(desc) > 100 else f"   Description: {desc}")
            print("-" * 50)

        return 0

    except TimeoutError as e:
        logger.error("Scraping operation timed out: %s", str(e))
        print("\n❌ Scraping timed out. Browser may need manual cleanup.")
        return 1
    except Exception as err:
        logger.error("Pipeline failure detected during scraping testing phase: %s", str(err), exc_info=True)
        return 1
    finally:
        # Cancel any pending timeout
        signal.alarm(0)

        # CRITICAL: Revert environment state mutations to prevent side effects in CI platforms
        if config.get("force_manual_login", True):
            logger.info("Restoring original environmental identity states.")
            if original_email is not None:
                os.environ["LINKEDIN_EMAIL"] = original_email
            else:
                os.environ.pop("LINKEDIN_EMAIL", None)
            if original_password is not None:
                os.environ["LINKEDIN_PASSWORD"] = original_password
            else:
                os.environ.pop("LINKEDIN_PASSWORD", None)


def main() -> int:
    """Main execution orchestrator."""
    # Centralized testing configuration matrix
    test_config = {
        "keywords": ["HSE Manager", "QHSE Manager", "EHS Manager"],
        "location": "United Arab Emirates",
        "max_jobs": 5,
        "easy_apply_only": True,
        "headless": False,          # Visible browser mode for manual validation
        "force_manual_login": True  # Set to False to test automated production flows
    }

    print("=" * 70)
    print("LINKEDIN JOB SCRAPER - ISOLATED ENVIRONMENT TEST")
    print("=" * 70)
    print(f"Target Configuration Parameters:")
    print(f" - Scope Keywords: {test_config['keywords']}")
    print(f" - Region Location: {test_config['location']}")
    print(f" - Concurrency Target Max Jobs: {test_config['max_jobs']}")
    print("=" * 70)
    print("⚠️  ACTION REQUIRED: Browser will open. Please execute manual login if prompt appears.")
    print("=" * 70 + "\n")

    return execute_scraper_test(test_config)

if __name__ == "__main__":
    sys.exit(main())
