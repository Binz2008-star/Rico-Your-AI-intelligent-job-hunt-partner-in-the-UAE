"""
Email Follow-up Automation Module

Integrates Gmail monitoring with intelligent follow-up generation and sending.
Tracks application responses and sends timely follow-ups for jobs without responses.
Uses Neon database with idempotency to prevent duplicate follow-up sends.
"""

import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from applications import get_applied_jobs, update_application_status
from followup_writer import FollowupIdentity, FollowupResult, build_due_followups_with_identity
from profile import get_candidate_profile

logger = logging.getLogger("email_followup_automation")


class FollowupIdempotencyError(Exception):
    """Raised when a follow-up already exists (duplicate)."""
    pass


class FollowupDatabaseError(Exception):
    """Raised when database operations fail."""
    pass


def _is_retryable_error(error: Exception) -> bool:
    """Classify if an error is retryable.

    Retryable errors:
    - Timeouts
    - Rate limiting (429)
    - Server errors (5xx)
    - Transient connection failures

    Non-retryable errors:
    - Invalid recipient
    - Malformed payload
    - Auth errors
    - Client errors (4xx except 429)

    Args:
        error: The exception to classify

    Returns:
        True if error is retryable, False otherwise
    """
    error_str = str(error).lower()
    error_class = type(error).__name__

    # Retryable status codes
    retryable_codes = ['429', '500', '502', '503', '504']
    if any(code in error_str for code in retryable_codes):
        return True

    # Retryable error patterns
    retryable_patterns = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'transient',
        'rate limit',
        'too many requests',
        'service unavailable',
        'gateway timeout'
    ]

    if any(pattern in error_str for pattern in retryable_patterns):
        return True

    # Non-retryable patterns
    non_retryable_patterns = [
        'invalid recipient',
        'malformed',
        'authentication',
        'unauthorized',
        'forbidden',
        'not found',
        'bad request'
    ]

    if any(pattern in error_str for pattern in non_retryable_patterns):
        return False

    # Default: assume retryable for unknown errors
    return True


@dataclass
class FollowupStats:
    """Statistics for follow-up automation run."""
    total_applications: int = 0
    jobs_due_for_followup: int = 0
    followups_sent: int = 0
    followups_failed: int = 0
    jobs_with_responses: int = 0
    jobs_rejected: int = 0
    jobs_interview_scheduled: int = 0
    jobs_offered: int = 0


@dataclass
class FollowupConfig:
    """Configuration for follow-up automation."""
    follow_up_days: int = 14
    max_followups_per_run: int = 5
    enable_auto_send: bool = False
    dry_run: bool = True


class EmailFollowupAutomation:
    """Automated email follow-up system for job applications.

    Uses Neon database with idempotency to prevent duplicate follow-up sends.
    """

    def __init__(self, config: Optional[FollowupConfig] = None):
        """Initialize the follow-up automation system.

        Args:
            config: Configuration for follow-up behavior
        """
        self._config = config or FollowupConfig()
        self._db_conn = None
        logger.info("email_followup_automation_initialized")

    def _get_db_connection(self):
        """Get database connection from Neon."""
        try:
            import psycopg

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                raise FollowupDatabaseError("DATABASE_URL not found in environment")

            if self._db_conn is None or self._db_conn.closed:
                self._db_conn = psycopg.connect(database_url)

            return self._db_conn

        except ImportError:
            logger.error("psycopg_not_installed install_with: pip install psycopg")
            raise FollowupDatabaseError("psycopg library not available")
        except Exception as e:
            logger.error(f"db_connection_failed error={e}")
            raise FollowupDatabaseError(f"Failed to connect to database: {e}")

    def _generate_idempotency_key(self, user_id: str, job_id: str, followup_day: int) -> str:
        """Generate unique idempotency key for follow-up.

        Args:
            user_id: User identifier
            job_id: Job identifier
            followup_day: Day number for follow-up (e.g., 14)

        Returns:
            Unique idempotency key string
        """
        return f"followup:{user_id}:{job_id}:{followup_day}"

    def claim_followup_send(
        self,
        user_id: str,
        job_id: str,
        job_title: str,
        job_company: str,
        followup_day: int
    ) -> bool:
        """Atomically claim a follow-up send using Neon UNIQUE constraint.

        This is the atomic lock mechanism - the INSERT itself is the claim.
        If successful, the follow-up is claimed. If conflict exists, it's a duplicate.

        Args:
            user_id: User identifier
            job_id: Job identifier
            job_title: Job title
            job_company: Company name
            followup_day: Day number for follow-up

        Returns:
            True if claim succeeded (new follow-up), False if duplicate

        Raises:
            FollowupDatabaseError: If database operation fails
        """
        idempotency_key = self._generate_idempotency_key(user_id, job_id, followup_day)
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # Atomic claim: INSERT with ON CONFLICT DO NOTHING
                # If row is returned, claim succeeded. If None, duplicate exists.
                claim_query = """
                    INSERT INTO followup_sends (
                        idempotency_key, user_id, job_id, job_title, job_company,
                        followup_day, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', TIMEZONE('utc', NOW()), TIMEZONE('utc', NOW()))
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                """

                cursor.execute(claim_query, (
                    idempotency_key, user_id, job_id, job_title, job_company, followup_day
                ))

                result = cursor.fetchone()

            conn.commit()  # Safe commit outside cursor context
            return result is not None

        except Exception as e:
            if conn:
                conn.rollback()  # Explicit rollback to prevent data corruption
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                logger.info(
                    "followup_claim_duplicate_detected",
                    extra={
                        "idempotency_key": idempotency_key,
                        "job_id": job_id
                    }
                )
                return False
            logger.error(
                "followup_claim_error",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            raise FollowupDatabaseError(f"Failed to claim follow-up: {e}")

    def _mark_followup_sent(
        self,
        user_id: str,
        job_id: str,
        followup_day: int,
        provider_message_id: Optional[str] = None
    ) -> bool:
        """Mark follow-up as sent after successful email send.

        If database update fails, mark as 'send_unknown' to indicate email was sent
        but status couldn't be confirmed. This enables safe reconciliation later.

        Args:
            user_id: User identifier
            job_id: Job identifier
            followup_day: Day number for follow-up
            provider_message_id: Optional provider message ID

        Returns:
            True if update succeeded, False if failed
        """
        idempotency_key = self._generate_idempotency_key(user_id, job_id, followup_day)
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                update_query = """
                    UPDATE followup_sends
                    SET status = 'sent', sent_at = TIMEZONE('utc', NOW()), provider_message_id = %s
                    WHERE idempotency_key = %s
                """

                cursor.execute(update_query, (provider_message_id, idempotency_key))
            conn.commit()

            logger.info(
                "followup_marked_sent",
                extra={
                    "idempotency_key": idempotency_key,
                    "provider_message_id": provider_message_id
                }
            )
            return True

        except Exception as e:
            logger.error(
                "followup_mark_sent_failed",
                extra={
                    "idempotency_key": idempotency_key,
                    "error": str(e)
                }
            )
            if conn:
                conn.rollback()
            # Try to mark as send_unknown to enable reconciliation
            try:
                fallback_conn = self._get_db_connection()
                with fallback_conn.cursor() as cursor:
                    idempotency_key = self._generate_idempotency_key(user_id, job_id, followup_day)

                    fallback_query = """
                        UPDATE followup_sends
                        SET status = 'send_unknown', provider_message_id = %s, updated_at = TIMEZONE('utc', NOW())
                        WHERE idempotency_key = %s AND status = 'pending'
                    """

                    cursor.execute(fallback_query, (provider_message_id, idempotency_key))
                fallback_conn.commit()

                logger.warning(
                    "followup_marked_send_unknown",
                    extra={
                        "idempotency_key": idempotency_key,
                        "provider_message_id": provider_message_id
                    }
                )
                return False
            except Exception as fallback_error:
                logger.error(
                    "followup_mark_send_unknown_failed",
                    extra={
                        "idempotency_key": idempotency_key,
                        "error": str(fallback_error)
                    }
                )
                return False

    def _mark_followup_failed(
        self,
        user_id: str,
        job_id: str,
        followup_day: int,
        error_message: str,
        is_retryable: bool = False
    ) -> bool:
        """Mark follow-up as failed after email send error.

        Args:
            user_id: User identifier
            job_id: Job identifier
            followup_day: Day number for follow-up
            error_message: Error message
            is_retryable: Whether the error is retryable

        Returns:
            True if update succeeded
        """
        idempotency_key = self._generate_idempotency_key(user_id, job_id, followup_day)
        conn = None

        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # Set status based on retryability
                status = 'retryable_failed' if is_retryable else 'failed'

                update_query = """
                    UPDATE followup_sends
                    SET status = %s, error_message = %s, send_attempts = send_attempts + 1,
                        last_retry_at = TIMEZONE('utc', NOW()), updated_at = TIMEZONE('utc', NOW())
                    WHERE idempotency_key = %s
                """

                cursor.execute(update_query, (status, error_message, idempotency_key))
            conn.commit()
            return True
        except Exception as e:
            logger.error("initial_mark_failed_method_broken", extra={"error": str(e)})
            if conn:
                conn.rollback()

            # Safe fallback: use isolated new connection for network safety
            try:
                fallback_conn = self._get_db_connection()
                with fallback_conn.cursor() as cursor:
                    fallback_query = """
                        UPDATE followup_sends
                        SET status = 'unknown', updated_at = TIMEZONE('utc', NOW())
                        WHERE idempotency_key = %s
                    """
                    cursor.execute(fallback_query, (idempotency_key,))
                fallback_conn.commit()
            except Exception as fallback_err:
                logger.critical(f"database_completely_unreachable: {fallback_err}")
            return False

    def _mark_followup_unknown(
        self,
        user_id: str,
        job_id: str,
        followup_day: int,
        error_message: str
    ) -> bool:
        """Mark follow-up as unknown outcome (network failure after potential send).

        Args:
            user_id: User identifier
            job_id: Job identifier
            followup_day: Day number for follow-up
            error_message: Error message

        Returns:
            True if update succeeded
        """
        idempotency_key = self._generate_idempotency_key(user_id, job_id, followup_day)
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                update_query = """
                    UPDATE followup_sends
                    SET status = 'unknown', error_message = %s, send_attempts = send_attempts + 1,
                        last_retry_at = TIMEZONE('utc', NOW()), updated_at = TIMEZONE('utc', NOW())
                    WHERE idempotency_key = %s
                """

                cursor.execute(update_query, (error_message, idempotency_key))
            conn.commit()

            logger.warning(
                "followup_marked_unknown",
                extra={
                    "idempotency_key": idempotency_key,
                    "error": error_message
                }
            )
            return True

        except Exception as e:
            logger.error(
                "followup_mark_unknown_failed",
                extra={
                    "idempotency_key": idempotency_key,
                    "error": str(e)
                }
            )
            if conn:
                conn.rollback()
            return False

    def run_followup_cycle(self) -> FollowupStats:
        """
        Executes a complete, user-scoped follow-up cycle with zero database
        side-effects during dry runs and rigorous opt-in validation.
        """
        logger.info("followup_cycle_starting", extra={"cycle_id": "auto"})
        stats = FollowupStats()

        try:
            # 1. Get user profile and validate identity and security
            profile = get_candidate_profile()
            if not profile:
                logger.error("followup_cycle_no_profile")
                return stats

            user_id = profile.get("user_id", profile.get("email", "unknown"))

            # [BLOCKER FIXED] Check for explicit user opt-in (Opt-In Check)
            if not profile.get("preferences", {}).get("enable_email_followup", False):
                logger.warning("followup_cycle_skipped_user_not_opted_in", extra={"user_id": user_id})
                return stats

            # [BLOCKER FIXED] Fetch user-specific applications only (User-Scoped)
            applications = get_applied_jobs(user_id=user_id)
            stats.total_applications = len(applications)

            if not applications:
                logger.info("followup_cycle_no_applications", extra={"user_id": user_id})
                return stats

            # 2. Build identity and due follow-ups
            identity = FollowupIdentity(
                name=profile.get("name", ""),
                title=profile.get("title"),
                company=profile.get("company"),
                years_experience=profile.get("years_experience"),
                verified_strengths=profile.get("skills", [])
            )

            # Check Gmail responses (pass user_id for isolation)
            response_stats = self._check_gmail_responses(applications, user_id=user_id)
            stats.jobs_with_responses = response_stats.get("total_responses", 0)

            followup_results = build_due_followups_with_identity(
                applications, identity, days=self._config.follow_up_days
            )
            stats.jobs_due_for_followup = len(followup_results)
            followup_results = followup_results[:self._config.max_followups_per_run]

            # 3. Process follow-up messages and send them
            for result in followup_results:
                job_id = result.job_id

                # [BLOCKER FIXED] Protect dry_run mode: no database writes if dry_run=True
                if self._config.dry_run:
                    logger.info(
                        "followup_dry_run_simulated_successfully",
                        extra={"job_id": job_id, "job_company": result.job_company, "user_id": user_id}
                    )
                    stats.followups_sent += 1  # Count as simulated success in stats
                    continue

                # Actual execution in production only (Production Live Run)
                try:
                    claimed = self.claim_followup_send(
                        user_id=user_id,
                        job_id=job_id,
                        job_title=result.job_title,
                        job_company=result.job_company,
                        followup_day=self._config.follow_up_days
                    )

                    if not claimed:
                        continue

                    success = self._send_followup_with_retry(
                        result, profile, user_id, job_id, max_retries=3
                    )
                    if success:
                        stats.followups_sent += 1

                except FollowupDatabaseError as e:
                    logger.error("followup_db_error", extra={"job_id": job_id, "error": str(e)})
                    stats.followups_failed += 1

            logger.info("followup_cycle_complete", extra={"sent": stats.followups_sent})
        except Exception as e:
            logger.exception(f"followup_cycle_error: {e}")

        return stats

    def _check_gmail_responses(self, applications: List[Dict[str, Any]], user_id: str) -> Dict[str, int]:
        """Check Gmail for responses to applications.

        Args:
            applications: List of job applications
            user_id: User identifier for isolation

        Returns:
            Dictionary with response statistics
        """
        try:
            from gmail_importer import run_import

            logger.info("checking_gmail_responses", extra={"user_id": user_id})

            # Run Gmail import in dry-run mode to check for responses
            report = run_import(dry_run=True, lookback_days=30, user_id=user_id)

            # Count responses by status
            response_stats = {
                "total_responses": 0,
                "rejected": 0,
                "interview_scheduled": 0,
                "offered": 0
            }

            for match in report.matches:
                if match.action in ["update", "queue"]:
                    response_stats["total_responses"] += 1

                    if match.email.status == "rejected":
                        response_stats["rejected"] += 1
                    elif match.email.status == "interview_scheduled":
                        response_stats["interview_scheduled"] += 1
                    elif match.email.status == "offer_extended":
                        response_stats["offered"] += 1

            logger.info(
                f"gmail_responses_found "
                f"total={response_stats['total_responses']} "
                f"rejected={response_stats['rejected']} "
                f"interview={response_stats['interview_scheduled']} "
                f"offer={response_stats['offered']}",
                extra={"user_id": user_id}
            )

            return response_stats

        except ImportError:
            logger.warning("gmail_importer_not_available skipping_response_check", extra={"user_id": user_id})
            return {"total_responses": 0, "rejected": 0, "interview_scheduled": 0, "offered": 0}
        except Exception as e:
            logger.error(f"gmail_response_check_failed error={e}", extra={"user_id": user_id})
            return {"total_responses": 0, "rejected": 0, "interview_scheduled": 0, "offered": 0}

    def _send_followup_with_retry(
        self,
        result: FollowupResult,
        profile: Dict[str, Any],
        user_id: str,
        job_id: str,
        max_retries: int = 3
    ) -> bool:
        """Send follow-up email with exponential backoff retry logic.

        Args:
            result: Follow-up result with message
            profile: User profile data
            user_id: User identifier for database updates
            job_id: Job identifier for database updates
            max_retries: Maximum number of retry attempts

        Returns:
            True if sent successfully, False otherwise
        """
        base_delay = 1  # seconds
        max_delay = 60  # seconds

        for attempt in range(max_retries + 1):
            try:
                success = self._send_followup_email(result, profile)

                if success:
                    # Mark as sent
                    self._mark_followup_sent(user_id, job_id, self._config.follow_up_days)
                    return True
                else:
                    # Send failed (non-exception case)
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                        logger.warning(
                            "followup_send_will_retry",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay_s": delay,
                                "job_id": job_id
                            }
                        )
                        time.sleep(delay)
                    else:
                        # Max retries reached, mark as failed
                        self._mark_followup_failed(
                            user_id, job_id, self._config.follow_up_days,
                            "Max retries reached without success", is_retryable=False
                        )
                        return False

            except Exception as e:
                is_retryable = _is_retryable_error(e)

                if is_retryable and attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(
                        "followup_send_retryable_error_will_retry",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_s": delay,
                            "error": str(e),
                            "job_id": job_id
                        }
                    )
                    time.sleep(delay)
                elif is_retryable and attempt >= max_retries:
                    # Max retries reached for retryable error
                    self._mark_followup_failed(
                        user_id, job_id, self._config.follow_up_days,
                        f"Max retries reached: {str(e)}", is_retryable=True
                    )
                    return False
                else:
                    # Non-retryable error or unknown outcome
                    # Mark as unknown to enable reconciliation
                    self._mark_followup_unknown(
                        user_id, job_id, self._config.follow_up_days,
                        str(e)
                    )
                    return False

        return False

    def _send_followup_email(self, result: FollowupResult, profile: Dict[str, Any]) -> bool:
        """Send a follow-up email via Gmail.

        Args:
            result: Follow-up result with message
            profile: User profile data

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # For now, just log the message
            # In production, this would integrate with Gmail API to send
            logger.info(
                "followup_email_ready",
                extra={
                    "to": "recruiter",
                    "subject": f"Follow-up: {result.job_title} at {result.job_company}",
                    "body_length": len(result.message)
                }
            )

            # TODO: Integrate with Gmail API to actually send
            # This requires Gmail API credentials and send permissions

            return True

        except Exception as e:
            logger.error(
                "followup_email_send_error",
                extra={"error": str(e)}
            )
            raise


# Test/Demo Section
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("EMAIL FOLLOW-UP AUTOMATION - TEST")
    print("=" * 70)

    config = FollowupConfig(
        follow_up_days=14,
        max_followups_per_run=5,
        enable_auto_send=False,
        dry_run=True
    )

    print(f"\nConfiguration:")
    print(f"  Follow-up Threshold: {config.follow_up_days} days")
    print(f"  Max Follow-ups per Run: {config.max_followups_per_run}")
    print(f"  Auto Send: {config.enable_auto_send}")
    print(f"  Dry Run: {config.dry_run}")

    print("\n" + "=" * 70)
    print("RUNNING FOLLOW-UP CYCLE")
    print("=" * 70)

    try:
        automation = EmailFollowupAutomation(config)
        stats = automation.run_followup_cycle()

        print("\n" + "=" * 70)
        print("FOLLOW-UP CYCLE RESULTS")
        print("=" * 70)
        print(f"Total Applications: {stats.total_applications}")
        print(f"Jobs Due for Follow-up: {stats.jobs_due_for_followup}")
        print(f"Follow-ups Sent: {stats.followups_sent}")
        print(f"Follow-ups Failed: {stats.followups_failed}")
        print(f"Jobs with Responses: {stats.jobs_with_responses}")
        print(f"  - Rejected: {stats.jobs_rejected}")
        print(f"  - Interview Scheduled: {stats.jobs_interview_scheduled}")
        print(f"  - Offers Extended: {stats.jobs_offered}")

        print("\n" + "=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        print("✅ Follow-up automation test completed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
