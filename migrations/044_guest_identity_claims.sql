-- migrations/044_guest_identity_claims.sql
-- #1070 — durable single-owner invariant for public→auth guest merges.
--
-- A guest can hold chat rows (rico_chat_history), upload artifacts
-- (cv_upload_artifacts), and saved searches WITHOUT ever having a
-- rico_profiles row, so the profile-JSONB "merged" marker alone cannot be the
-- uniqueness authority. This table makes the claim durable and DB-enforced:
-- the PRIMARY KEY guarantees at most ONE owning account per guest identity,
-- unconditionally — independent of advisory locks or marker state.
--
-- The claim row is inserted inside the SAME transaction (and connection) as
-- every merge data move; a failed merge rolls the claim back with the data.
--
-- ADDITIVE ONLY. Safe to re-run (IF NOT EXISTS).
--
-- Apply BEFORE deploying the #1070 merge change:
--   psql $DATABASE_URL -f migrations/044_guest_identity_claims.sql
-- If the table is missing at runtime, merges FAIL CLOSED (no data copied,
-- login/registration itself unaffected) and log the missing-migration error.

CREATE TABLE IF NOT EXISTS guest_identity_claims (
    public_user_id     TEXT        PRIMARY KEY,   -- 'public:<server-minted sid>'
    claimed_by_user_id UUID        NOT NULL,      -- rico_users.id of the owning account
    claimed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guest_identity_claims_owner
    ON guest_identity_claims (claimed_by_user_id);

-- Rollback (manual, owner-approved only): DROP TABLE guest_identity_claims;
-- merges revert to failing closed until re-applied.
