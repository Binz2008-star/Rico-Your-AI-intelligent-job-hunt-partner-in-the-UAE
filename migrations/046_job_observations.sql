-- Migration 046: job_observations — append-only posting-history archive.
--
-- Records every FRESH provider sighting of a job posting (cache hits are the
-- same response re-served, so they are never recorded). Longitudinal posting
-- data (first seen, re-posts, delistings, posting velocity) can only accrue
-- from the day recording starts — it cannot be backfilled — which is why this
-- table exists before any product feature consumes it.
--
-- Contract:
--   * APPEND-ONLY: rows are never updated or deleted by application code.
--   * No direct user identifiers or raw query text. No user_id, no session,
--     no request identity. Query context is stored ONLY as a keyed,
--     non-reversible HMAC-SHA256 (`query_context_hmac`) for longitudinal
--     grouping: query text can embed profile-derived terms (target roles,
--     preferred cities) and the query space is small enough for dictionary
--     attacks against an unkeyed hash, so a plain hash is NOT sufficient.
--     The key is RICO_ARCHIVE_HMAC_KEY — dedicated to the archive (never
--     JWT_SECRET or any shared secret) and never stored in the database.
--     When the key is absent the application skips archive writes entirely
--     (fail-closed; search is unaffected) — it never falls back to an
--     unkeyed hash.
--   * `fingerprint` is the versioned canonical job identity
--     (sha256 over normalized company|title|city, see
--     src/repositories/job_observations_repo.py). `fingerprint_version` allows
--     the normalization algorithm to evolve without corrupting history.
--   * `claimed_posted_at` is the provider's own claim and is NOT trusted;
--     `observed_at` (Rico's clock) is the only authoritative timestamp.
--   * Description text is never stored — only its sha256 and length, enough
--     for repost/similarity detection without the storage cost.

CREATE TABLE IF NOT EXISTS job_observations (
    id                  BIGSERIAL PRIMARY KEY,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider            VARCHAR(32) NOT NULL,
    query_context_hmac  CHAR(64) NOT NULL DEFAULT '',
    provider_job_id     VARCHAR(512) NOT NULL DEFAULT '',
    fingerprint         CHAR(64) NOT NULL,
    fingerprint_version SMALLINT NOT NULL DEFAULT 1,
    title               VARCHAR(512) NOT NULL,
    company             VARCHAR(512) NOT NULL DEFAULT '',
    location            VARCHAR(512) NOT NULL DEFAULT '',
    country             VARCHAR(8) NOT NULL DEFAULT 'ae',
    claimed_posted_at   TIMESTAMPTZ NULL,
    salary_string       VARCHAR(256) NOT NULL DEFAULT '',
    employment_type     VARCHAR(64) NOT NULL DEFAULT '',
    description_hash    CHAR(64) NOT NULL DEFAULT '',
    description_len     INTEGER NOT NULL DEFAULT 0,
    apply_domain        VARCHAR(256) NOT NULL DEFAULT ''
);

-- Longitudinal lookups: "when was this exact job seen before?"
CREATE INDEX IF NOT EXISTS idx_job_observations_fingerprint_observed
    ON job_observations (fingerprint, observed_at DESC);

-- Time-window scans and retention housekeeping.
CREATE INDEX IF NOT EXISTS idx_job_observations_observed_at
    ON job_observations (observed_at);
