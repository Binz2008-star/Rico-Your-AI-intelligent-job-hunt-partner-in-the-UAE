"""src/services/identity_merge_service.py

Guest → authenticated identity merge service.

Handles migration of profile data when a public (guest) user signs up or logs in,
ensuring CV-extracted skills, experience, and preferences survive authentication.

Design rules:
- Pure merge functions have no DB side effects.
- DB functions are synchronous (psycopg2) matching the existing RicoDB style.
- No raw CV text migration by default.
- No new DB columns.
- Auth scalar values always win over guest values.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from src.api.public_identity import is_valid_public_user_id
from src.rico_db import RicoDB

logger = logging.getLogger(__name__)
_UTC = timezone.utc

# Keys allowed to migrate from guest profile → auth profile.
# Scalars: auth wins if already present.
# Lists: merged and deduplicated.
MERGEABLE_PROFILE_KEYS = {
    "email",
    "phone",
    "skills",
    "years_experience",
    "certifications",
    "languages",
    "target_roles",
    "normalized_roles",
    "preferred_cities",
    "industries",
    "cv_filename",
    "cv_status",
    "profile_creation_mode",
    "manual_profile_wizard_disabled",
    "salary_expectation_aed",
    "minimum_salary_aed",
    "deal_breakers",
    "current_role",
    "current_company",
    "visa_status",
    "notice_period",
    "english_level",
    "arabic_level",
    "linkedin_url",
    "portfolio_url",
    "green_flags",
    "red_flags",
}

# Tables confirmed to have a user_id column and be safe to migrate.
CONFIRMED_USER_SCOPED_TABLES = ["rico_saved_searches"]


def _merge_lock_key(public_user_id: str) -> int:
    """Deterministic 63-bit positive integer for PostgreSQL advisory xact lock.

    Keyed on the GUEST identity alone (#1070): two different accounts claiming
    the same guest must contend for the SAME lock, so exactly one claim can
    proceed at a time and the loser observes the committed claim marker. The
    previous pair-key let concurrent claims of one guest by two accounts run
    under different locks and both copy the guest data.
    """
    h = hashlib.sha256(f"guest-claim:{public_user_id}".encode()).hexdigest()
    return int(h[:16], 16) % (2**63 - 1)


def is_empty_value(value: Any) -> bool:
    """Return True for None, empty string, empty list, or empty dict."""
    if value is None:
        return True
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return True
    return False


def normalize_jsonb(data: Any) -> dict[str, Any]:
    """Coerce a JSONB value (dict, JSON string, or None) into a plain dict."""
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def merge_profile_data(
    auth_data: dict[str, Any],
    guest_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge guest profile data into authenticated profile data.

    Rules:
    - Only keys in MERGEABLE_PROFILE_KEYS are considered.
    - Auth scalar values win (not overwritten by guest).
    - Guest fills missing auth values.
    - Lists are merged and deduplicated (guest items appended after auth items).
    - Empty guest values are ignored.
    - Nested dicts are not recursively merged (treated as scalars).

    Returns a new dict; inputs are not mutated.
    """
    result = dict(auth_data)  # shallow copy

    for key, guest_value in guest_data.items():
        if key not in MERGEABLE_PROFILE_KEYS:
            continue
        if is_empty_value(guest_value):
            continue

        auth_value = auth_data.get(key)

        if is_empty_value(auth_value):
            # Auth missing → take guest value
            result[key] = guest_value
        elif isinstance(auth_value, list) and isinstance(guest_value, list):
            # Merge lists, dedupe, preserve auth order then append guest extras
            merged = list(auth_value)
            seen = set(str(v).lower() for v in merged if isinstance(v, str))
            for item in guest_value:
                if isinstance(item, str) and item.lower() not in seen:
                    merged.append(item)
                    seen.add(item.lower())
                elif not isinstance(item, str) and item not in merged:
                    merged.append(item)
            result[key] = merged
        else:
            # Scalar or mismatched types → auth wins, do nothing
            pass

    return result


def _table_exists(cur, table_name: str) -> bool:
    """Check whether a table exists in the public schema."""
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    """Check whether a column exists on a table."""
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def _get_db_user_id(cur, external_user_id: str) -> str | None:
    """Resolve external user_id (email or public:web-*) to internal UUID string."""
    cur.execute(
        """
        SELECT id::text FROM rico_users
        WHERE external_user_id = %s OR email = %s OR id::text = %s
        LIMIT 1
        """,
        (external_user_id, external_user_id, external_user_id),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _read_profile_jsonb(cur, db_user_id: str) -> dict[str, Any]:
    """Fetch profile JSONB for a user by internal UUID."""
    cur.execute(
        "SELECT profile FROM rico_profiles WHERE user_id = %s",
        (db_user_id,),
    )
    row = cur.fetchone()
    return normalize_jsonb(row["profile"] if row else None)


def _write_profile_jsonb(
    cur,
    db_user_id: str,
    data: dict[str, Any],
) -> None:
    """Upsert profile JSONB using the same || merge pattern as RicoDB."""
    cur.execute(
        """
        INSERT INTO rico_profiles (user_id, profile)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            profile = rico_profiles.profile || EXCLUDED.profile,
            updated_at = now()
        """,
        (db_user_id, Json(data)),
    )


def _mark_guest_profile_merged(
    cur,
    guest_db_user_id: str,
    auth_db_user_id: str,
) -> None:
    """Mark the guest profile as merged inside its JSONB data."""
    cur.execute(
        """
        INSERT INTO rico_profiles (user_id, profile)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            profile = rico_profiles.profile || EXCLUDED.profile,
            updated_at = now()
        """,
        (
            guest_db_user_id,
            Json(
                {
                    "profile_status": "merged",
                    "merged_into_user_id": auth_db_user_id,
                    "merged_at": datetime.now(_UTC).isoformat(),
                }
            ),
        ),
    )


def _migrate_user_scoped_rows(
    cur,
    from_db_user_id: str,
    to_db_user_id: str,
) -> None:
    """Migrate rows from confirmed user-scoped tables."""
    for table in CONFIRMED_USER_SCOPED_TABLES:
        if not _table_exists(cur, table):
            logger.debug("merge_skip_table table=%s reason=not_found", table)
            continue
        if not _column_exists(cur, table, "user_id"):
            logger.debug("merge_skip_table table=%s reason=no_user_id_column", table)
            continue
        # Use sql.Literal or psycopg2.sql to safely interpolate the table name
        from psycopg2 import sql as pg_sql

        query = pg_sql.SQL("UPDATE {} SET user_id = %s WHERE user_id = %s").format(
            pg_sql.Identifier(table)
        )
        cur.execute(query, (to_db_user_id, from_db_user_id))
        logger.info(
            "merge_table table=%s from=%s to=%s rows=%s",
            table,
            from_db_user_id,
            to_db_user_id,
            cur.rowcount,
        )


def merge_public_identity_into_auth(
    public_user_id: str | None,
    auth_user_id: str,
    guest_capability_token: str | None = None,
) -> bool:
    """
    Merge a public (guest) identity into an authenticated identity.

    Ownership contract (#1070, locked design): the MERGE SOURCE is the
    server-minted sid inside the browser's signed capability token — never the
    request body. ``public_user_id`` is the client's correlation-only value:
    it signals merge INTENT and is never accepted by the source-selection path
    — a mismatch with the token identity is logged (observable) and has no
    effect on which guest is merged. A missing/invalid token rejects the claim
    outright.

    The claim is one-time, account-bound, and DURABLE: a guest-scoped advisory
    lock serializes concurrent claims, and a row in ``guest_identity_claims``
    (PRIMARY KEY on the guest identity — DB-enforced single owner, migration
    044) is inserted inside the SAME transaction and connection as every data
    move. The profile marker remains as observability. A repeated claim by the
    same owner is an idempotent success; a claim by any other account is
    rejected; any failure rolls the claim and the data moves back together.

    Returns True on success, False on failure (failures remain retryable).
    """
    if not auth_user_id:
        logger.warning("merge_rejected reason=missing_auth_user")
        return False

    # 1. Ownership: the capability token IS the merge source.
    from src.api.public_identity import InvalidGuestCapability, parse_guest_capability

    try:
        token_sid = parse_guest_capability(guest_capability_token)
    except InvalidGuestCapability as exc:
        # Fixed reason code only — never token/SID/nonce/signature material.
        logger.warning(
            "merge_rejected reason=unproved_claim reason_code=%s",
            getattr(exc, "reason_code", "invalid"),
        )
        return False
    except Exception:  # GuestCapabilityUnavailable etc. — fail closed
        logger.error("merge_rejected reason=capability_unavailable")
        return False

    authoritative_public_id = f"public:{token_sid}"

    # 2. The client-supplied value is correlation-only: it can never select,
    #    rotate, or overwrite the server identity. A mismatch is expected
    #    (the browser cannot read the HttpOnly token) and is logged for
    #    observability; the merge source is the token identity regardless.
    if public_user_id and public_user_id != authoritative_public_id:
        logger.info("merge_correlation_mismatch (client value ignored)")

    public_user_id = authoritative_public_id
    if not is_valid_public_user_id(public_user_id):
        logger.warning("merge_rejected reason=not_public_source public_user_id=%s", public_user_id)
        return False
    if public_user_id == auth_user_id:
        logger.warning("merge_rejected reason=same_user_id")
        return False

    db = RicoDB()
    if not db.available:
        logger.warning("merge_rejected reason=db_unavailable")
        return False

    conn = db.connect()
    try:
        with conn.cursor() as cur:
            # Serialize concurrent claims of the SAME GUEST via a guest-scoped
            # advisory xact lock (released automatically on commit/rollback).
            # Two accounts claiming one guest contend here; the loser either
            # fails the try-lock (retryable) or sees the committed claim marker.
            lock_key = _merge_lock_key(public_user_id)
            cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (lock_key,))
            got_lock = cur.fetchone()["pg_try_advisory_xact_lock"]
            if not got_lock:
                logger.warning(
                    "merge_rejected reason=concurrent_merge_in_progress "
                    "public_user_id=%s auth_user_id=%s lock_key=%s",
                    public_user_id, auth_user_id, lock_key,
                )
                return False

            # Resolve external IDs to internal UUIDs
            guest_db_id = _get_db_user_id(cur, public_user_id)
            auth_db_id = _get_db_user_id(cur, auth_user_id)

            if not guest_db_id:
                logger.warning("merge_rejected reason=guest_not_found public_user_id=%s", public_user_id)
                return False
            if not auth_db_id:
                logger.warning("merge_rejected reason=auth_not_found auth_user_id=%s", auth_user_id)
                return False
            if guest_db_id == auth_db_id:
                logger.warning("merge_rejected reason=same_db_id")
                return False

            # Read profiles
            guest_profile = _read_profile_jsonb(cur, guest_db_id)
            auth_profile = _read_profile_jsonb(cur, auth_db_id)

            # One-time claim (CAS, enforced under the guest-scoped lock in the
            # same transaction as every data move): a guest already claimed by
            # ANOTHER account is never merged again; a replay by the SAME
            # owner is an idempotent no-op success.
            prior_owner = guest_profile.get("merged_into_user_id")
            if guest_profile.get("profile_status") == "merged":
                if str(prior_owner) == str(auth_db_id):
                    logger.info(
                        "merge_idempotent_replay public_user_id=%s auth_user_id=%s",
                        public_user_id, auth_user_id,
                    )
                    return True
                logger.warning(
                    "merge_rejected reason=already_claimed public_user_id=%s",
                    public_user_id,
                )
                return False

            # 3. DURABLE one-time claim (#1070 correction 4): guests can hold
            #    chat/upload/artifact data WITHOUT a rico_profiles row, so the
            #    profile marker above is observability, not the authority. The
            #    PRIMARY KEY on guest_identity_claims enforces a single owner
            #    unconditionally, inside this SAME transaction and connection
            #    as every data move below — a failed merge rolls the claim
            #    back with the data.
            try:
                cur.execute(
                    """
                    INSERT INTO guest_identity_claims (public_user_id, claimed_by_user_id)
                    VALUES (%s, %s)
                    ON CONFLICT (public_user_id) DO NOTHING
                    RETURNING claimed_by_user_id::text
                    """,
                    (public_user_id, auth_db_id),
                )
                claim_row = cur.fetchone()
            except Exception as exc:
                if getattr(exc, "pgcode", None) == "42P01":
                    logger.error(
                        "merge_rejected reason=claims_table_missing — apply "
                        "migrations/044_guest_identity_claims.sql before enabling merges"
                    )
                    conn.rollback()
                    return False
                raise
            if claim_row is None:
                cur.execute(
                    """
                    SELECT claimed_by_user_id::text AS claimed_by_user_id
                    FROM guest_identity_claims WHERE public_user_id = %s
                    """,
                    (public_user_id,),
                )
                owner_row = cur.fetchone()
                owner = owner_row["claimed_by_user_id"] if owner_row else None
                if owner == str(auth_db_id):
                    logger.info(
                        "merge_idempotent_replay public_user_id=%s auth_user_id=%s",
                        public_user_id, auth_user_id,
                    )
                    return True
                logger.warning(
                    "merge_rejected reason=already_claimed public_user_id=%s",
                    public_user_id,
                )
                return False

            # Merge
            merged = merge_profile_data(auth_profile, guest_profile)

            # Write merged profile to auth user
            _write_profile_jsonb(cur, auth_db_id, merged)

            # Mark guest as merged
            _mark_guest_profile_merged(cur, guest_db_id, auth_db_id)

            # Migrate confirmed user-scoped tables
            _migrate_user_scoped_rows(cur, guest_db_id, auth_db_id)

        conn.commit()
        logger.info(
            "merge_success public_user_id=%s auth_user_id=%s",
            public_user_id,
            auth_user_id,
        )
        return True

    except Exception:
        conn.rollback()
        logger.exception(
            "merge_failed public_user_id=%s auth_user_id=%s",
            public_user_id,
            auth_user_id,
        )
        return False
    finally:
        conn.close()
