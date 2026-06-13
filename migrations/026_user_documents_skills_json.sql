-- Migration 026: add skills_json to user_documents
-- Stores the full extracted skills list per document so that set-primary
-- can re-sync the profile's skills field when the active CV is switched.
ALTER TABLE user_documents
    ADD COLUMN IF NOT EXISTS skills_json JSONB DEFAULT '[]'::jsonb;
