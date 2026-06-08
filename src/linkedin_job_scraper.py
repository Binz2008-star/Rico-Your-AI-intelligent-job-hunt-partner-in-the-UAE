"""
LinkedIn Job Scraper Module

Scrapes LinkedIn job search pages to extract job information including URLs,
titles, companies, locations, and descriptions. Integrates with the existing job pipeline.

Usage:
    from src.linkedin_job_scraper import scrape_linkedin_jobs

    jobs = scrape_linkedin_jobs(
        keywords=["HSE Manager", "QHSE Manager"],
        location="United Arab Emirates",
        max_jobs=20
    )
"""

import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("linkedin_job_scraper")

# LinkedIn credentials
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")


@dataclass
class LinkedInJob:
    """LinkedIn job data structure."""
    title: str
    company: str
    location: str
    link: str
    description: str
    posted_date: Optional[str] = None
    applicants: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format compatible with job pipeline."""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "link": self.link,
            "description": self.description,
            "source": "linkedin",
            "posted_date": self.posted_date,
            "applicants": self.applicants,
        }


class LinkedInJobScraper:
    """LinkedIn job scraper using Playwright."""

    def __init__(self, headless: bool = True):
        """Initialize the scraper.

        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self._browser = None
        self._page = None

    def __enter__(self):
        """Context manager entry."""
        self._init_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._close_browser()

    def _init_browser(self):
        """Initialize Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()

            # Launch browser with stealth settings
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )

            # Create context with realistic user agent
            context = self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            self._page = context.new_page()
            logger.info("linkedin_scraper_browser_initialized")

        except ImportError:
            logger.error("playwright_not_installed install with: pip install playwright")
            raise
        except Exception as e:
            logger.error(f"linkedin_scraper_browser_init_failed error={e}")
            raise

    def _close_browser(self):
        """Close browser and cleanup."""
        try:
            if self._page:
                self._page.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            logger.info("linkedin_scraper_browser_closed")
        except Exception as e:
            logger.warning(f"linkedin_scraper_browser_close_error error={e}")

    def _login(self) -> bool:
        """Login to LinkedIn.

        Returns:
            True if login successful, False otherwise
        """
        if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
            logger.error("linkedin_credentials_missing LINKEDIN_EMAIL or LINKEDIN_PASSWORD not set")
            logger.info("linkedin_manual_login_required browser will stay open for manual login")

            # Navigate to login page and wait for manual login
            try:
                self._page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
                logger.info("linkedin_login_page_opened please login manually within 120 seconds")

                # Wait 120 seconds for manual login
                self._page.wait_for_timeout(120000)

                # Check if login successful
                current_url = self._page.url
                if "feed" in current_url or "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                    logger.info(f"linkedin_manual_login_success url={current_url}")
                    return True
                else:
                    logger.error(f"linkedin_manual_login_failed url={current_url}")
                    return False

            except Exception as e:
                logger.error(f"linkedin_manual_login_error error={e}")
                return False

        try:
            # Navigate to login page
            self._page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)

            # Wait for page to load
            self._page.wait_for_timeout(2000)

            # Try multiple selector patterns for username field
            username_selectors = [
                "input#username",
                "input[name='session_key']",
                "#username",
            ]

            username_filled = False
            for selector in username_selectors:
                try:
                    if self._page.query_selector(selector):
                        self._page.fill(selector, LINKEDIN_EMAIL, timeout=5000)
                        username_filled = True
                        logger.info(f"linkedin_username_filled selector={selector}")
                        break
                except:
                    continue

            if not username_filled:
                logger.error("linkedin_username_field_not_found")
                return False

            # Try multiple selector patterns for password field
            password_selectors = [
                "input#password",
                "input[name='session_password']",
                "#password",
            ]

            password_filled = False
            for selector in password_selectors:
                try:
                    if self._page.query_selector(selector):
                        self._page.fill(selector, LINKEDIN_PASSWORD, timeout=5000)
                        password_filled = True
                        logger.info(f"linkedin_password_filled selector={selector}")
                        break
                except:
                    continue

            if not password_filled:
                logger.error("linkedin_password_field_not_found")
                return False

            # Try multiple selector patterns for login button
            button_selectors = [
                "button[type='submit']",
                "button[aria-label='Sign in']",
                ".login__form_action_container button",
            ]

            button_clicked = False
            for selector in button_selectors:
                try:
                    if self._page.query_selector(selector):
                        self._page.click(selector, timeout=5000)
                        button_clicked = True
                        logger.info(f"linkedin_button_clicked selector={selector}")
                        break
                except:
                    continue

            if not button_clicked:
                logger.error("linkedin_login_button_not_found")
                return False

            # Wait for navigation
            self._page.wait_for_load_state("networkidle", timeout=30000)

            # Check if login successful
            current_url = self._page.url
            if "feed" in current_url or "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                logger.info(f"linkedin_login_success url={current_url}")
                return True
            else:
                # Check for CAPTCHA
                if "captcha" in current_url.lower() or "challenge" in current_url.lower():
                    logger.error("linkedin_captcha_detected")
                else:
                    logger.error(f"linkedin_login_failed url={current_url}")
                return False

        except Exception as e:
            logger.error(f"linkedin_login_error error={e}")
            return False

    def scrape_jobs(
        self,
        keywords: List[str],
        location: str = "United Arab Emirates",
        max_jobs: int = 20,
        easy_apply_only: bool = True,
    ) -> List[LinkedInJob]:
        """Scrape LinkedIn jobs for given keywords and location.

        Args:
            keywords: List of job keywords to search
            location: Location filter (default: UAE)
            max_jobs: Maximum number of jobs to return
            easy_apply_only: Only return jobs with Easy Apply

        Returns:
            List of LinkedInJob objects
        """
        jobs = []

        try:
            # Login first
            if not self._login():
                logger.error("linkedin_scrape_failed login_required")
                return jobs

            # Search for each keyword
            for keyword in keywords:
                if len(jobs) >= max_jobs:
                    break

                keyword_jobs = self._search_keyword(
                    keyword=keyword,
                    location=location,
                    remaining=max_jobs - len(jobs),
                    easy_apply_only=easy_apply_only,
                )

                jobs.extend(keyword_jobs)
                logger.info(f"linkedin_scrape_keyword keyword={keyword} found={len(keyword_jobs)}")

            logger.info(f"linkedin_scrape_complete total={len(jobs)}")
            return jobs

        except Exception as e:
            logger.error(f"linkedin_scrape_error error={e}")
            return jobs

    def _search_keyword(
        self,
        keyword: str,
        location: str,
        remaining: int,
        easy_apply_only: bool,
    ) -> List[LinkedInJob]:
        """Search LinkedIn for a specific keyword.

        Args:
            keyword: Search keyword
            location: Location filter
            remaining: Remaining jobs to fetch
            easy_apply_only: Only Easy Apply jobs

        Returns:
            List of LinkedInJob objects
        """
        jobs = []

        try:
            # Build search URL
            search_url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={keyword.replace(' ', '%20')}"
                f"&location={location.replace(' ', '%20')}"
                f"&f_E=1"  # Easy Apply filter
                if easy_apply_only else ""
            )

            logger.info(f"linkedin_search_url url={search_url}")

            # Navigate to search page
            self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # Wait for job cards to load
            self._page.wait_for_selector(".job-card-container", timeout=15000)

            # Scroll to load more jobs
            self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._page.wait_for_timeout(2000)

            # Extract job cards
            job_cards = self._page.query_all(".job-card-container")

            for card in job_cards[:remaining]:
                try:
                    job = self._extract_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"linkedin_extract_card_error error={e}")
                    continue

            return jobs

        except Exception as e:
            logger.error(f"linkedin_search_error keyword={keyword} error={e}")
            return jobs

    def _extract_job_card(self, card) -> Optional[LinkedInJob]:
        """Extract job information from a job card element.

        Args:
            card: Playwright element for job card

        Returns:
            LinkedInJob object or None if extraction fails
        """
        try:
            # Extract title
            title_elem = card.query_selector(".job-card-list__title--link")
            title = title_elem.inner_text().strip() if title_elem else "Unknown"

            # Extract company
            company_elem = card.query_selector(".job-card-container__company-name")
            company = company_elem.inner_text().strip() if company_elem else "Unknown"

            # Extract location
            location_elem = card.query_selector(".job-card-container__metadata-item")
            location = location_elem.inner_text().strip() if location_elem else "Unknown"

            # Extract link
            link = title_elem.get_attribute("href") if title_elem else ""
            if link and not link.startswith("http"):
                link = f"https://www.linkedin.com{link}"

            # Extract posted date
            posted_elem = card.query_selector(".job-card-container__metadata-item time")
            posted = posted_elem.get_attribute("datetime") if posted_elem else None

            # Extract applicants count
            applicants_elem = card.query_selector(".job-card-container__applicant-count")
            applicants = applicants_elem.inner_text().strip() if applicants_elem else None

            # Get job description (requires navigation to job page)
            description = self._get_job_description(link) if link else ""

            return LinkedInJob(
                title=title,
                company=company,
                location=location,
                link=link,
                description=description,
                posted_date=posted,
                applicants=applicants,
            )

        except Exception as e:
            logger.warning(f"linkedin_extract_card_error error={e}")
            return None

    def _get_job_description(self, job_url: str) -> str:
        """Get job description by navigating to job page.

        Args:
            job_url: LinkedIn job URL

        Returns:
            Job description text
        """
        try:
            # Navigate to job page
            self._page.goto(job_url, wait_until="domcontentloaded", timeout=20000)

            # Wait for description to load
            self._page.wait_for_selector(".show-more-less-html__markup", timeout=10000)

            # Extract description
            desc_elem = self._page.query_selector(".show-more-less-html__markup")
            description = desc_elem.inner_text().strip() if desc_elem else ""

            # Go back to search results
            self._page.go_back(wait_until="domcontentloaded", timeout=20000)

            return description

        except Exception as e:
            logger.warning(f"linkedin_get_description_error url={job_url} error={e}")
            return ""


def scrape_linkedin_jobs(
    keywords: List[str],
    location: str = "United Arab Emirates",
    max_jobs: int = 20,
    easy_apply_only: bool = True,
    headless: bool = True,
) -> List[Dict[str, Any]]:
    """Scrape LinkedIn jobs and return in pipeline-compatible format.

    Args:
        keywords: List of job keywords to search
        location: Location filter (default: UAE)
        max_jobs: Maximum number of jobs to return
        easy_apply_only: Only return jobs with Easy Apply
        headless: Whether to run browser in headless mode

    Returns:
        List of job dictionaries compatible with job pipeline
    """
    jobs = []

    try:
        with LinkedInJobScraper(headless=headless) as scraper:
            linkedin_jobs = scraper.scrape_jobs(
                keywords=keywords,
                location=location,
                max_jobs=max_jobs,
                easy_apply_only=easy_apply_only,
            )

            # Convert to pipeline format
            jobs = [job.to_dict() for job in linkedin_jobs]

            logger.info(f"linkedin_scrape_success jobs={len(jobs)}")

    except Exception as e:
        logger.error(f"linkedin_scrape_failed error={e}")

    return jobs


if __name__ == "__main__":
    # Test the scraper
    import sys
    from pathlib import Path

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.profile import get_target_roles

    # Get target roles from profile
    target_roles = get_target_roles()

    print(f"Scraping LinkedIn for: {target_roles[:3]}")

    # Scrape jobs
    jobs = scrape_linkedin_jobs(
        keywords=target_roles[:3],
        location="United Arab Emirates",
        max_jobs=5,
        easy_apply_only=True,
        headless=False,  # Show browser for testing
    )

    print(f"\nFound {len(jobs)} jobs:")
    for i, job in enumerate(jobs, 1):
        print(f"\n{i}. {job['title']} at {job['company']}")
        print(f"   Location: {job['location']}")
        print(f"   Link: {job['link']}")
        print(f"   Applicants: {job.get('applicants', 'N/A')}")
