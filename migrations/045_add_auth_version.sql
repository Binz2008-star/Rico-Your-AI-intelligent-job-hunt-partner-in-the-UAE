-- migrations/045_add_auth_version.sql
-- #1072 — stale-JWT invalidation via a per-user auth version.
--
-- Every issued JWT carries the user's auth_version at login time (claim "av").
-- Authenticated requests compare the token's "av" against this column; any
-- mismatch rejects the token. Incrementing the column therefore revokes every
-- previously issued token for that user at once.
--
-- Increment triggers: password reset (atomic with the password UPDATE),
-- "log out all devices" (POST /api/v1/auth/logout-all), and any future
-- deactivation/role-change tooling.
--
-- Tokens minted before this migration have no "av" claim and are treated as
-- av=1, which matches the DEFAULT — nobody is logged out by applying this.
--
-- ADDITIVE ONLY. Safe to re-run (IF NOT EXISTS).
--
-- Apply BEFORE deploying the #1072 auth change:
--   psql $DATABASE_URL -f migrations/045_add_auth_version.sql
-- If the column is missing at runtime the code falls back to version 1 and
-- logs a loud error: sessions keep working, but revocation is inert until
-- the migration is applied (logout-all reports 503 rather than lying).

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 1;

-- Rollback (manual, owner-approved only):
--   ALTER TABLE users DROP COLUMN auth_version;
