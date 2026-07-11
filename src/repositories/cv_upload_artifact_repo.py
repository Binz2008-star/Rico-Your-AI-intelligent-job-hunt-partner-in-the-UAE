"""
src/repositories/cv_upload_artifact_repo.py
Short-lived, server-side CV upload artifact bridging upload-cv (parse) and
confirm-cv-profile (confirm) — see migrations/038_cv_upload_artifacts.sql.

The client is handed only the opaque `id` (upload_id) returned by
`create_cv_upload_artifact`. The SHA-256 content hash and full parsed text are
computed/stashed server-side at upload time and re-read server-side at
confirm time via `resolve_cv_upload_artifact`, scoped to the resolved
`user_id` and a freshness window — never trusted from the client and never
routed through the JSON RicoMemoryStore (a no-op under
RICO_MEMORY_BACKEND=postgres, the production backend).

One row per upload (not one row per user), so concurrent/multi-tab uploads
never collide and a confirm always resolves the exact upload it was issued
for. Never raises — failures are logged and swallowed so upload/confirm is
never blocked by this bridge; a resolve miss degrades to the caller's
no-artifact path rather than an error.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_DEFAULT_TTL_MINUTES = 180


def create_cv_upload_artifact(
    user_id: str,
    *,
    filename: str,
    doc_type: str,
    content_hash: str,
    file_size: int,
    cv_text: str | None,
    ttl_minutes: int = _DEFAULT_TTL_MINUTES,
) -> Optional[str]:
    """Persist a short-lived upload artifact and return its id (upload_id).

    Returns ``None`` (never raises) when the DB is unavailable, inputs are
    incomplete, or the write fails — callers must treat a ``None`` return as
    "no artifact available" and degrade gracefully, never as an error.
    """
    if not (user_id and filename and content_hash):
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.debug("cv_upload_artifact_repo: DB unavailable, skipping create user=%s", user_id)
        return None
    try:
        expires_at = datetime.now(_UTC) + timedelta(minutes=ttl_minutes)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cv_upload_artifacts
                    (user_id, filename, doc_type, content_hash, file_size, cv_text, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, filename, doc_type or "cv", content_hash, file_size or 0, cv_text, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
        artifact_id = str(row[0]) if row else None
        logger.debug(
            "cv_upload_artifact_repo: created user=%s id=%s chars=%d",
            user_id, artifact_id, len(cv_text or ""),
        )
        return artifact_id
    except Exception:
        logger.exception("cv_upload_artifact_repo_create_failed user=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def resolve_cv_upload_artifact(user_id: str, upload_id: str) -> Optional[dict[str, Any]]:
    """Return the artifact for `upload_id` scoped to `user_id`, or ``None``.

    Scoped by BOTH id and the server-derived user_id — a valid upload_id for
    a different user never resolves, so a guessed/leaked id cannot be
    replayed against another account. Only unexpired rows resolve (see
    migration 038 for the short-lived-by-design rationale). Never raises.
    """
    if not (user_id and upload_id):
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename, doc_type, content_hash, file_size, cv_text
                  FROM cv_upload_artifacts
                 WHERE id = %s AND user_id = %s AND expires_at > NOW()
                 LIMIT 1
                """,
                (upload_id, user_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "filename": row[0],
            "doc_type": row[1] or "cv",
            "content_hash": row[2],
            "file_size": row[3] or 0,
            "cv_text": row[4] or "",
        }
    except Exception:
        logger.exception("cv_upload_artifact_repo_resolve_failed user=%s upload_id=%s", user_id, upload_id)
        return None
    finally:
        conn.close()
