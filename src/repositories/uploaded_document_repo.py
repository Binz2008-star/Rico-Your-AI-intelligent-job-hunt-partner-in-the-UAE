"""
src/repositories/uploaded_document_repo.py
Neon-backed persistence for the most recently uploaded image/document transcript
per user.

The JSON memory store (``RicoMemoryStore``) is a no-op under
``RICO_MEMORY_BACKEND=postgres`` and is wiped by Render restarts / multiple
instances, so the OCR transcript a user just uploaded would not survive to the
follow-up chat turn. This table keeps the latest transcript per user durably so
"summarize this", "extract key information", and typed questions ("what do you
think of this job?") can always retrieve it.

One row per user_id (latest upload upserts). Keyed by the resolved user id or
public-session key, so authenticated and public sessions are both covered.

Never raises — failures are logged and swallowed so chat/upload is unaffected.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_MAX_TEXT_CHARS = 4000
_DEFAULT_MAX_AGE_MIN = 180


def set_last_uploaded_document(
    user_id: str,
    *,
    extracted_text: str,
    filename: str | None = None,
    document_type: str | None = None,
    display_label: str | None = None,
    source: str = "image",
    request_ref: str | None = None,
) -> None:
    """Upsert the latest uploaded-document transcript for a user (one row per user).

    No-op when there is no user_id or no extracted text. Never raises.
    """
    text = (extracted_text or "").strip()
    if not user_id or not text:
        return
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.debug("uploaded_document_repo: DB unavailable, skipping set user=%s", user_id)
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO uploaded_document_context
                    (user_id, filename, document_type, display_label, source,
                     extracted_text, request_ref, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    filename       = EXCLUDED.filename,
                    document_type  = EXCLUDED.document_type,
                    display_label  = EXCLUDED.display_label,
                    source         = EXCLUDED.source,
                    extracted_text = EXCLUDED.extracted_text,
                    request_ref    = EXCLUDED.request_ref,
                    updated_at     = NOW()
                """,
                (
                    user_id,
                    filename,
                    document_type,
                    display_label,
                    source or "image",
                    text[:_MAX_TEXT_CHARS],
                    request_ref,
                ),
            )
        conn.commit()
        logger.debug("uploaded_document_repo: stored transcript user=%s chars=%d", user_id, len(text))
    except Exception:
        logger.exception("uploaded_document_repo_set_failed user=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def get_last_uploaded_document(
    user_id: str, max_age_minutes: int = _DEFAULT_MAX_AGE_MIN
) -> Optional[dict[str, Any]]:
    """Return the latest uploaded-document transcript for a user, or ``None``.

    Honors a freshness window (``max_age_minutes``) so a stale transcript from a
    much earlier upload is not reused. Never raises.
    """
    if not user_id:
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    cutoff = datetime.now(_UTC) - timedelta(minutes=max_age_minutes)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename, document_type, display_label, source,
                       extracted_text, request_ref, updated_at
                  FROM uploaded_document_context
                 WHERE user_id = %s AND updated_at >= %s
                 LIMIT 1
                """,
                (user_id, cutoff),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "filename":       row[0],
            "document_type":  row[1],
            "display_label":  row[2],
            "source":         row[3] or "image",
            "extracted_text": row[4] or "",
            "request_ref":    row[5],
            "updated_at":     row[6],
        }
    except Exception:
        logger.exception("uploaded_document_repo_get_failed user=%s", user_id)
        return None
    finally:
        conn.close()


def clear_last_uploaded_document(user_id: str) -> None:
    """Remove a user's stored transcript (best-effort). Never raises."""
    if not user_id:
        return
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM uploaded_document_context WHERE user_id = %s", (user_id,))
        conn.commit()
    except Exception:
        logger.exception("uploaded_document_repo_clear_failed user=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
