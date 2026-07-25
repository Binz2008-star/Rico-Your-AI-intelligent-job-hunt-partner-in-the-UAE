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

Retention / cleanup (why this is genuinely short-lived, not just
un-readable-after-TTL): an artifact holds the full parsed CV text of an
*unconfirmed* upload, so it must not accumulate. ``expires_at`` (default 3h)
gates readability, and every ``create_cv_upload_artifact`` call ALSO deletes
a bounded batch of already-expired rows in the same transaction
(``purge_expired_cv_upload_artifacts``). There is no background worker on
Render, so this opportunistic, amortized cleanup is the deletion mechanism:
each create adds one row and removes up to ``_PURGE_BATCH`` expired rows, so
the table converges to the live (unexpired) working set instead of growing
without bound. ``purge_expired_cv_upload_artifacts`` is also exposed for a
manual/cron sweep if one is ever added.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_DEFAULT_TTL_MINUTES = 180
# Max expired rows deleted per opportunistic purge. Bounded so a single
# create call can never turn into an unbounded table-wide DELETE; amortized
# across creates it still keeps the table near the live working set.
_PURGE_BATCH = 200


def _delete_expired_artifacts(cur, limit: int) -> int:
    """Delete up to ``limit`` already-expired rows using ``cur``. Returns the
    row count deleted. Uses an id-in-subquery-with-LIMIT so the DELETE is
    bounded and index-friendly (``idx_cv_upload_artifacts_user_expires``)."""
    cur.execute(
        """
        DELETE FROM cv_upload_artifacts
         WHERE id IN (
             SELECT id FROM cv_upload_artifacts
              WHERE expires_at < NOW()
              ORDER BY expires_at
              LIMIT %s
         )
        """,
        (limit,),
    )
    return cur.rowcount if (cur.rowcount and cur.rowcount > 0) else 0


def purge_expired_cv_upload_artifacts(limit: int = _PURGE_BATCH) -> int:
    """Delete up to ``limit`` expired artifacts. Best-effort, never raises.

    Called opportunistically from ``create_cv_upload_artifact`` (there is no
    background worker on Render) and usable standalone from a future
    manual/cron sweep or a test. Returns the number of rows deleted (0 when
    the DB is unavailable or on any error).
    """
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            deleted = _delete_expired_artifacts(cur, limit)
        conn.commit()
        if deleted:
            logger.debug("cv_upload_artifact_repo: purged %d expired artifact(s)", deleted)
        return deleted
    except Exception:
        logger.exception("cv_upload_artifact_repo_purge_failed")
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _triple_lock_key(user_id: str, doc_type: str, content_hash: str) -> int:
    """A stable 64-bit advisory-lock key for one `(user_id, doc_type,
    content_hash)`.

    Serialises concurrent uploads of the SAME bytes by the same user without
    locking any table or blocking unrelated uploads. Two different triples
    could theoretically collide on this key; the only consequence would be one
    upload briefly waiting for another, never a wrong result.
    """
    digest = hashlib.sha256(
        f"{user_id}\x00{doc_type or 'cv'}\x00{content_hash}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def saved_document_exists(user_id: str, doc_type: str, content_hash: str) -> bool:
    """Whether this exact CV is ALREADY a saved document for this user.

    Answers the triple key `(user_id, doc_type, content_hash)` — the same
    identity confirm writes and `get_latest_pending_cv_upload` derives
    `already_saved` from, so the three cannot disagree about what "this CV"
    means. Best-effort: a store that cannot be read returns False, because a
    failed read is not evidence that a document exists.
    """
    if not (user_id and content_hash):
        return False
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_documents
                 WHERE user_id = %s AND doc_type = %s AND content_hash = %s
                 LIMIT 1
                """,
                (user_id, doc_type or "cv", content_hash),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("cv_upload_artifact_repo_saved_lookup_failed user=%s", user_id)
        return False
    finally:
        conn.close()


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
        _doc_type = doc_type or "cv"
        with conn.cursor() as cur:
            # ONE artifact per (user_id, doc_type, content_hash), enforced here
            # rather than by a unique index because adding one is a schema
            # change and this table holds full CV text: re-uploading the same
            # file — which users do while trying to make a stuck flow work —
            # otherwise retains another complete copy of their CV per attempt.
            #
            # The advisory lock is what makes it correct under concurrency. A
            # read-then-insert would let two simultaneous uploads of the same
            # bytes both see "no existing row" and both insert; this serialises
            # the whole decision for that one triple, and releases at commit or
            # rollback (xact-scoped, so no leak on the error path). It blocks
            # only other uploads of the SAME file by the SAME user.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_triple_lock_key(user_id, _doc_type, content_hash),))
            # Refresh the newest existing artifact for this triple instead of
            # adding a sibling. Returning its id keeps a confirm already issued
            # against it valid, so a second tab is corrected rather than broken.
            cur.execute(
                """
                UPDATE cv_upload_artifacts
                   SET filename = %s, file_size = %s, cv_text = %s, expires_at = %s
                 WHERE id = (
                     SELECT id FROM cv_upload_artifacts
                      WHERE user_id = %s AND doc_type = %s AND content_hash = %s
                      ORDER BY created_at DESC
                      LIMIT 1
                 )
                RETURNING id
                """,
                (filename, file_size or 0, cv_text, expires_at, user_id, _doc_type, content_hash),
            )
            row = cur.fetchone()
            if row:
                # Collapse any historical duplicates for this triple, so a table
                # that already accumulated copies converges to one row as those
                # files are re-uploaded.
                cur.execute(
                    """
                    DELETE FROM cv_upload_artifacts
                     WHERE user_id = %s AND doc_type = %s AND content_hash = %s AND id <> %s
                    """,
                    (user_id, _doc_type, content_hash, row[0]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO cv_upload_artifacts
                        (user_id, filename, doc_type, content_hash, file_size, cv_text, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, filename, _doc_type, content_hash, file_size or 0, cv_text, expires_at),
                )
                row = cur.fetchone()
            # Opportunistic bounded cleanup of expired artifacts, in the SAME
            # transaction — the deletion mechanism that keeps this table
            # short-lived without a background worker (there is none on
            # Render). Never let cleanup failure abort a valid insert: on any
            # purge error, roll back to the successful insert via a SAVEPOINT.
            try:
                cur.execute("SAVEPOINT purge_expired")
                _delete_expired_artifacts(cur, _PURGE_BATCH)
                cur.execute("RELEASE SAVEPOINT purge_expired")
            except Exception:
                logger.exception("cv_upload_artifact_repo_inline_purge_failed user=%s", user_id)
                cur.execute("ROLLBACK TO SAVEPOINT purge_expired")
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


def artifact_store_reachable() -> bool:
    """Whether the artifact store can be reached at all.

    Distinguishes "no usable store in this environment" from "a write was
    attempted and failed" — the two must produce different answers, because only
    the second is a broken promise. Called ONLY after a creation attempt has
    already returned nothing, so it costs nothing on the normal path.

    A configured DSN is not sufficient: a non-production platform routinely
    carries a DSN pointing at no server, which is still "no usable store".
    """
    from src.db import get_db_connection

    conn = get_db_connection()
    if conn is None:
        return False
    try:
        conn.close()
    except Exception:
        pass
    return True


class ArtifactStoreUnavailable(Exception):
    """The artifact store could not be read.

    Distinct from "no pending upload" on purpose: a caller must be able to say
    "we couldn't load your pending review" instead of "your upload doesn't
    exist". Telling a user their upload is gone during an outage is the failure
    this whole area exists to prevent.
    """


def get_latest_pending_cv_upload(user_id: str) -> Optional[dict[str, Any]]:
    """Return the newest artifact that is still genuinely PENDING, or ``None``.

    Pending is DERIVED, not stored: an artifact is pending only while no
    ``user_documents`` row exists for the same ``(user_id, doc_type,
    content_hash)``. All three, so a file saved under a DIFFERENT doc_type with
    the same bytes cannot cancel a pending CV review, or the reverse. Once
    confirm has saved the document, the artifact stops being pending
    immediately — with no consumption step, no deletion, and no schema change.

    Expired rows are RETURNED with ``expired=True`` rather than filtered away:
    "your preview lapsed, upload again" and "you have no upload" are different
    facts, and collapsing them tells a user who did upload that they never did.

    That matters for two opposite failure modes at once. Without it, a user who
    already confirmed would be shown a "review required — not saved yet" card for
    a CV that IS saved: the inverse of the lie this work removes. And deleting or
    expiring the artifact instead would break confirm's idempotency, because
    ``resolve_cv_upload_artifact`` requires an unexpired row — a second confirm
    would be told to upload again rather than "already saved".

    Raises ``ArtifactStoreUnavailable`` when the store cannot be read. Returns
    ``None`` only for a definite absence.
    """
    if not user_id:
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        raise ArtifactStoreUnavailable("database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.filename, a.doc_type, a.cv_text, a.expires_at,
                       (a.expires_at <= NOW()) AS is_expired,
                       EXISTS (
                         SELECT 1 FROM user_documents d
                          WHERE d.user_id = a.user_id
                            AND d.doc_type = a.doc_type
                            AND d.content_hash = a.content_hash
                       ) AS is_saved
                  FROM cv_upload_artifacts a
                 WHERE a.user_id = %s
                 ORDER BY a.created_at DESC
                 LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "upload_id": str(row[0]),
            "filename": row[1],
            "doc_type": row[2] or "cv",
            # Internal-only: used to rebuild the preview, never returned to a client.
            "cv_text": row[3] or "",
            # Deliberately part of the contract: temporary retention is only
            # acceptable if the person whose data it is can see how long it lasts.
            "expires_at": row[4],
            # Reported, never filtered away. "Your preview lapsed" and "you never
            # uploaded" are different facts.
            "expired": bool(row[5]),
            # The triple key decides this, so "saved" and "nothing pending" can
            # never be collapsed into one answer.
            "already_saved": bool(row[6]),
        }
    except Exception as exc:
        logger.exception("cv_upload_artifact_repo_pending_failed user=%s", user_id)
        raise ArtifactStoreUnavailable(str(exc)) from exc
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
