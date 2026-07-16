"""
src/services/gmail_sync_service.py
Per-user Gmail read-only sync for the connector M0.

Reuses the pure query/extract/classify/match helpers from the existing
single-user CLI importer (src/gmail_importer.py) — those functions take the
Gmail service / data as parameters and touch no CLI or file I/O, so the CLI
importer's behavior is untouched. What this service replaces is everything
around them:

  * Credentials come from the user's Fernet-encrypted refresh token
    (gmail_connections), NOT root-level credentials.json/token.json.
  * Results are written to per-user DB tables (gmail_sync_runs,
    gmail_review_items, gmail_audit_events), NOT data/gmail_review_queue.json.
  * Classifier statuses are normalized to the SaaS application vocabulary
    (interview_scheduled→interview, offer_extended→offer) so an approved
    review item can feed applications_repo.update_status directly.
  * M0 is deliberately conservative: EVERY classified email becomes a pending
    review item — no automatic application updates, matching the design doc's
    "propose first" rule. ``updates_applied`` stays 0 until a later milestone.
  * Bounded work: per-user lookback clamp, message cap, and time budget so one
    mailbox can never block the fleet sweep (no Redis/queue in production).

Everything is gated behind RICO_ENABLE_GMAIL_SYNC (default false).
No email bodies are persisted — subject/sender/snippet-derived fields only.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from src.repositories import gmail_repo
from src.services.gmail_oauth import credentials_from_refresh_token
from src.services.token_crypto import TokenCryptoError, decrypt_token

logger = logging.getLogger(__name__)

# ── Feature flag ──────────────────────────────────────────────────────────────

FLAG_ENV_NAME = "RICO_ENABLE_GMAIL_SYNC"


def gmail_sync_enabled() -> bool:
    """Master kill-switch. Default OFF — Gmail sync must be explicitly enabled."""
    return (os.getenv(FLAG_ENV_NAME, "false").strip().lower()
            in {"1", "true", "yes", "on"})


# ── Status normalization ──────────────────────────────────────────────────────
# The keyword classifier (src/gmail_importer.py) emits legacy statuses; the
# SaaS application API uses applications_repo._VALID_STATUSES.

STATUS_NORMALIZATION = {
    "interview_scheduled": "interview",
    "offer_extended": "offer",
}


def normalize_status(status: Optional[str]) -> Optional[str]:
    """Map classifier statuses onto the SaaS application vocabulary."""
    if not status:
        return status
    return STATUS_NORMALIZATION.get(status, status)


# ── Bounds (M0 defaults — conservative, overridable per call) ────────────────

DEFAULT_LOOKBACK_DAYS = 14
MAX_LOOKBACK_DAYS = 30
DEFAULT_MESSAGE_CAP = 50
DEFAULT_TIME_BUDGET_SECONDS = 60
SWEEP_MESSAGE_CAP = 25
SWEEP_TIME_BUDGET_SECONDS = 30
SWEEP_MAX_USERS = 200

# Pagination bounds for the Gmail message-list phase.
# These are independent of the per-message processing budget above and
# prevent one large mailbox from monopolizing sync-all via unbounded
# list pagination.
MAX_LIST_PAGES = 10          # hard cap on Gmail API list requests
MAX_CANDIDATE_MESSAGES = 500  # hard cap on candidate messages collected during listing
LIST_PAGE_SIZE = 100          # maxResults per list request (Gmail API max is 500)


def _clamp_lookback(lookback_days: Optional[int]) -> int:
    try:
        days = int(lookback_days) if lookback_days else DEFAULT_LOOKBACK_DAYS
    except (TypeError, ValueError):
        days = DEFAULT_LOOKBACK_DAYS
    return max(1, min(days, MAX_LOOKBACK_DAYS))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_received_at(date_header: str) -> Optional[datetime]:
    try:
        return parsedate_to_datetime(date_header) if date_header else None
    except Exception:
        return None


def _load_user_applications(user_id: str) -> List[Dict[str, Any]]:
    """User-scoped applications for matching. Failure → no matches (queue only)."""
    try:
        from src.repositories import applications_repo

        return applications_repo.get_all(user_id=user_id) or []
    except Exception:
        logger.warning("gmail_sync_applications_unavailable user_id=%s", user_id)
        return []


def _build_gmail_service(credentials: Any) -> Any:
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _refresh_credentials(credentials: Any) -> None:
    """Mint a short-lived access token from the refresh token (never persisted)."""
    from google.auth.transport.requests import Request

    credentials.refresh(Request())


def _is_refresh_error(exc: Exception) -> bool:
    try:
        from google.auth.exceptions import RefreshError

        return isinstance(exc, RefreshError)
    except Exception:
        return False


# ── Bounded message listing ───────────────────────────────────────────────────


def _fetch_messages_bounded(
    service: Any,
    lookback_days: int,
    deadline: float,
    max_pages: int = MAX_LIST_PAGES,
    max_candidates: int = MAX_CANDIDATE_MESSAGES,
    page_size: int = LIST_PAGE_SIZE,
) -> tuple[List[Dict[str, Any]], str]:
    """Bounded Gmail message listing with deadline and pagination caps.

    Reuses the same Gmail query and thread-dedup logic as
    ``src.gmail_importer._fetch_messages`` but adds:
      * deadline check before every list request
      * explicit max page count
      * explicit max candidate-message count
      * repeated/invalid page-token loop prevention

    Returns ``(messages, stop_reason)`` where stop_reason is one of:
      ``done`` — no more pages
      ``deadline`` — time budget expired before listing completed
      ``page_cap`` — hit MAX_LIST_PAGES
      ``candidate_cap`` — hit MAX_CANDIDATE_MESSAGES
    """
    from datetime import datetime, timedelta

    from src.gmail_importer import _GMAIL_QUERY

    after = int((datetime.now() - timedelta(days=lookback_days)).timestamp())
    query = f"{_GMAIL_QUERY} after:{after}"

    messages: List[Dict[str, Any]] = []
    seen_threads: set = set()
    page_token: Optional[str] = None
    seen_page_tokens: set = set()

    for page_idx in range(max_pages):
        if time.monotonic() >= deadline:
            return messages, "deadline"

        kwargs: Dict[str, Any] = {
            "userId": "me",
            "q": query,
            "maxResults": page_size,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            resp = service.users().messages().list(**kwargs).execute()
        except Exception:
            logger.warning("gmail_list_page_failed page=%d", page_idx, exc_info=True)
            return messages, "list_error"

        batch = resp.get("messages", [])
        for msg in batch:
            thread_id = msg.get("threadId")
            if thread_id and thread_id not in seen_threads:
                seen_threads.add(thread_id)
                messages.append(msg)
                if len(messages) >= max_candidates:
                    return messages, "candidate_cap"

        next_token = resp.get("nextPageToken")
        if not next_token:
            return messages, "done"

        # Guard against repeated/invalid page tokens causing an infinite loop.
        if next_token in seen_page_tokens:
            logger.warning("gmail_list_repeated_page_token — stopping pagination")
            return messages, "repeated_token"
        seen_page_tokens.add(next_token)
        page_token = next_token

    return messages, "page_cap"


# ── Per-user sync ─────────────────────────────────────────────────────────────


def run_user_sync(
    user_id: str,
    mode: str = "manual",
    lookback_days: Optional[int] = None,
    message_cap: int = DEFAULT_MESSAGE_CAP,
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
) -> Dict[str, Any]:
    """Run one bounded read-only sync for a single user.

    Returns a summary dict (never raises): status is one of
    disabled | not_connected | needs_reauth | error | completed | partial.
    """
    if not gmail_sync_enabled():
        return {"status": "disabled", "user_id": user_id}

    connection = gmail_repo.get_connection(user_id)
    if not connection:
        return {"status": "not_connected", "user_id": user_id}
    if connection.get("status") == "needs_reauth":
        return {"status": "needs_reauth", "user_id": user_id}

    lookback = _clamp_lookback(lookback_days)

    # Decrypt the refresh token — fail closed, never proceed with plaintext gaps.
    try:
        refresh_token = decrypt_token(connection.get("encrypted_refresh_token") or "")
    except TokenCryptoError:
        logger.warning("gmail_sync_token_unavailable user_id=%s", user_id)
        gmail_repo.insert_audit_event(
            user_id, "token_refresh", "error",
            connection_id=connection.get("id"),
            metadata={"reason": "decrypt_failed"},
        )
        return {"status": "error", "error_code": "token_unavailable", "user_id": user_id}

    credentials = credentials_from_refresh_token(refresh_token)
    try:
        _refresh_credentials(credentials)
    except Exception as exc:
        if _is_refresh_error(exc):
            # Consent revoked / token expired at Google → mark, keep history.
            gmail_repo.mark_connection_status(
                user_id, "needs_reauth", last_error="refresh_rejected"
            )
            gmail_repo.insert_audit_event(
                user_id, "token_refresh", "error",
                connection_id=connection.get("id"),
                metadata={"reason": "refresh_rejected"},
            )
            return {"status": "needs_reauth", "user_id": user_id}
        logger.warning("gmail_sync_refresh_failed user_id=%s", user_id, exc_info=True)
        gmail_repo.insert_audit_event(
            user_id, "token_refresh", "error",
            connection_id=connection.get("id"),
            metadata={"reason": type(exc).__name__},
        )
        return {"status": "error", "error_code": "refresh_failed", "user_id": user_id}

    gmail_repo.insert_audit_event(
        user_id, "sync_started", "ok",
        connection_id=connection.get("id"), metadata={"mode": mode},
    )
    run_id = gmail_repo.create_sync_run(
        user_id, connection.get("id"), mode=mode, lookback_days=lookback
    )

    counters = {
        "messages_fetched": 0,
        "messages_classified": 0,
        "messages_skipped": 0,
        "updates_applied": 0,   # M0: always 0 — propose-only, no auto-updates
        "queued_for_review": 0,
    }
    started = time.monotonic()
    status = "completed"
    error_code: Optional[str] = None

    try:
        # Pure helpers reused from the CLI importer — parametrized by service/data.
        from src.gmail_importer import (
            _BLOCKED_SENDER_DOMAINS,
            _BLOCKED_SUBJECT_PATTERNS,
            ClassifiedEmail,
            _build_application_index,
            _classify,
            _extract_body,
            _extract_company_hint,
            _extract_header,
            _extract_links,
            _get_message_detail,
            _match_email_to_application,
        )

        service = _build_gmail_service(credentials)

        # Bounded listing: the deadline is shared between listing and processing.
        # The listing phase gets the full budget; the processing loop checks the
        # same deadline per message. This prevents one large mailbox from
        # monopolizing sync-all via unbounded list pagination.
        list_deadline = started + time_budget_seconds
        raw_messages, list_stop_reason = _fetch_messages_bounded(
            service, lookback, deadline=list_deadline,
        )
        # Apply the per-user message cap on top of the listing caps.
        cap = max(1, int(message_cap))
        if len(raw_messages) > cap:
            raw_messages = raw_messages[:cap]
        counters["messages_fetched"] = len(raw_messages)

        # If listing was cut short by a bound (not "done"), record it honestly.
        if list_stop_reason not in ("done",):
            if status == "completed":
                status = "partial"
            if not error_code:
                error_code = f"list_{list_stop_reason}"

        applications = _load_user_applications(user_id)
        index = _build_application_index(applications)

        for msg_meta in raw_messages:
            if time.monotonic() - started > time_budget_seconds:
                status = "partial"
                error_code = "time_budget_exceeded"
                break

            detail = _get_message_detail(service, msg_meta["id"])
            if not detail:
                counters["messages_skipped"] += 1
                continue

            headers = detail.get("payload", {}).get("headers", [])
            subject = _extract_header(headers, "Subject")
            sender = _extract_header(headers, "From")
            date = _extract_header(headers, "Date")
            body = _extract_body(detail.get("payload", {}))
            links = _extract_links(body)
            company = _extract_company_hint(sender, subject)

            # Same early filters as the CLI importer.
            if len(subject.strip()) < 10:
                counters["messages_skipped"] += 1
                continue
            sender_lower = sender.lower()
            if any(d in sender_lower for d in _BLOCKED_SENDER_DOMAINS):
                counters["messages_skipped"] += 1
                continue
            subject_lower = subject.lower()
            if any(p in subject_lower for p in _BLOCKED_SUBJECT_PATTERNS):
                counters["messages_skipped"] += 1
                continue

            classified_status, cls_conf = _classify(subject, body)
            if cls_conf < 0.30:
                counters["messages_skipped"] += 1
                continue
            counters["messages_classified"] += 1

            email = ClassifiedEmail(
                message_id=msg_meta["id"],
                subject=subject,
                sender=sender,
                date=date,
                snippet=(detail.get("snippet") or "")[:200],
                body_text="",  # body text is used for classification only — never stored
                status=classified_status,
                classification_confidence=cls_conf,
                links_found=links,
                company_hint=company,
            )
            matched_app, match_conf, match_reason = _match_email_to_application(
                email, index, applications
            )

            inserted = gmail_repo.insert_review_item(
                {
                    "user_id": user_id,
                    "sync_run_id": run_id,
                    "gmail_message_id": msg_meta["id"],
                    "gmail_thread_id": msg_meta.get("threadId"),
                    "subject_snippet": subject[:200],
                    "sender": sender[:200],
                    "received_at": _parse_received_at(date),
                    "classified_status": normalize_status(classified_status),
                    "classification_confidence": round(cls_conf, 4),
                    "company_hint": company or None,
                    "matched_job_id": (matched_app or {}).get("job_id"),
                    "matched_company": (matched_app or {}).get("company"),
                    "matched_title": (matched_app or {}).get("title"),
                    "match_confidence": round(match_conf, 4),
                    "match_reason": match_reason,
                    "proposed_status": normalize_status(classified_status),
                }
            )
            if inserted:
                counters["queued_for_review"] += 1
    except Exception as exc:
        logger.exception("gmail_sync_failed user_id=%s", user_id)
        status = "error"
        error_code = type(exc).__name__

    if run_id:
        gmail_repo.finish_sync_run(run_id, status, counters, error_code=error_code)
    if status in ("completed", "partial"):
        gmail_repo.touch_last_sync(user_id)
    gmail_repo.insert_audit_event(
        user_id,
        "sync_completed" if status in ("completed", "partial") else "sync_failed",
        "ok" if status in ("completed", "partial") else "error",
        connection_id=connection.get("id"),
        sync_run_id=run_id,
        metadata={"mode": mode, **counters},
    )

    return {"status": status, "user_id": user_id, "run_id": run_id,
            "error_code": error_code, **counters}


# ── Fleet sweep (cron) ────────────────────────────────────────────────────────


def run_fleet_sweep(
    lookback_days: Optional[int] = None,
    message_cap: int = SWEEP_MESSAGE_CAP,
    time_budget_seconds: float = SWEEP_TIME_BUDGET_SECONDS,
) -> Dict[str, Any]:
    """Bounded sweep over active connections that OPTED IN to recurring sync
    (cron-guarded endpoint).

    Consent gate (BLOCKER 2): list_active_connections only returns rows with
    recurring_sync_consent granted — the OAuth read grant alone is never treated
    as consent to recurring background sync. Manual, user-initiated sync
    (run_user_sync) does not consult this and is unaffected.

    Per-user failures are isolated — one broken mailbox never stops the fleet.
    """
    if not gmail_sync_enabled():
        return {"status": "disabled", "users_processed": 0}

    connections = gmail_repo.list_active_connections(limit=SWEEP_MAX_USERS)
    summary: Dict[str, Any] = {
        "status": "completed",
        "users_processed": 0,
        "users_completed": 0,
        "users_needs_reauth": 0,
        "users_errored": 0,
        "queued_for_review": 0,
    }
    for connection in connections:
        user_id = connection.get("user_id")
        if not user_id:
            continue
        summary["users_processed"] += 1
        try:
            result = run_user_sync(
                user_id,
                mode="sweep",
                lookback_days=lookback_days,
                message_cap=message_cap,
                time_budget_seconds=time_budget_seconds,
            )
        except Exception:
            # run_user_sync shouldn't raise, but the fleet must never die on one user.
            logger.exception("gmail_sweep_user_failed user_id=%s", user_id)
            summary["users_errored"] += 1
            continue
        if result.get("status") in ("completed", "partial"):
            summary["users_completed"] += 1
            summary["queued_for_review"] += int(result.get("queued_for_review") or 0)
        elif result.get("status") == "needs_reauth":
            summary["users_needs_reauth"] += 1
        else:
            summary["users_errored"] += 1
    return summary
