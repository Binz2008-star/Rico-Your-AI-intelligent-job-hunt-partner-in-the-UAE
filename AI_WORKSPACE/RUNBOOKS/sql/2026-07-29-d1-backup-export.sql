\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
\endif

-- Run only against the fresh pre-repair Neon backup branch.
-- The working directory must be an owner-controlled encrypted location.
-- The relative directory ./secure-d1-backup must already exist.

BEGIN TRANSACTION READ ONLY ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='60s';
SET LOCAL lock_timeout='2s';

CREATE TEMP TABLE d1_params(target_principal text NOT NULL PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_params VALUES(lower(:'target_principal'));

CREATE TEMP TABLE d1_target ON COMMIT DROP AS
SELECT u.id,u.external_user_id,u.email,
       CASE
         WHEN lower(u.external_user_id)=p.target_principal THEN 'canonical'
         WHEN u.external_user_id LIKE 'public:%' THEN 'guest'
         ELSE 'email_only'
       END AS class
FROM rico_users u
JOIN d1_params p ON lower(u.email)=p.target_principal;

CREATE TEMP TABLE d1_aliases ON COMMIT DROP AS
SELECT DISTINCT lower(v) AS alias
FROM d1_target t
CROSS JOIN LATERAL unnest(ARRAY[t.id::text,t.external_user_id,t.email]) v
WHERE v IS NOT NULL AND btrim(v)<>'';

DO $$
BEGIN
  IF (SELECT count(*) FROM d1_target)<>5 THEN RAISE EXCEPTION 'Target count mismatch'; END IF;
  IF (SELECT count(*) FROM d1_target WHERE class='canonical')<>1 THEN RAISE EXCEPTION 'Canonical count mismatch'; END IF;
  IF (SELECT count(*) FROM d1_target WHERE class='email_only')<>2 THEN RAISE EXCEPTION 'Email-only count mismatch'; END IF;
  IF (SELECT count(*) FROM d1_target WHERE class='guest')<>2 THEN RAISE EXCEPTION 'Guest count mismatch'; END IF;
  IF (SELECT count(*) FROM rico_profiles WHERE user_id IN (SELECT id FROM d1_target))<>5 THEN RAISE EXCEPTION 'Profile count mismatch'; END IF;
  IF (SELECT count(*) FROM rico_chat_history WHERE user_id IN (SELECT id FROM d1_target))<>1463 THEN RAISE EXCEPTION 'Chat count mismatch'; END IF;
  IF (SELECT count(*) FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases))<>24 THEN RAISE EXCEPTION 'Learning count mismatch'; END IF;
  IF (SELECT count(*) FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases))<>13 THEN RAISE EXCEPTION 'Job-context count mismatch'; END IF;
  IF (SELECT count(*) FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM d1_aliases))<>5 THEN RAISE EXCEPTION 'Onboarding count mismatch'; END IF;
  IF (SELECT count(*) FROM rico_agent_settings WHERE user_id IN (SELECT id FROM d1_target))<>1 THEN RAISE EXCEPTION 'Agent-settings count mismatch'; END IF;
END $$;

\copy (SELECT * FROM d1_target ORDER BY class,id) TO './secure-d1-backup/target.csv' CSV HEADER
\copy (SELECT u.* FROM rico_users u JOIN d1_target t ON t.id=u.id ORDER BY u.id) TO './secure-d1-backup/rico_users.csv' CSV HEADER
\copy (SELECT p.* FROM rico_profiles p JOIN d1_target t ON t.id=p.user_id ORDER BY p.id) TO './secure-d1-backup/rico_profiles.csv' CSV HEADER
\copy (SELECT h.id,h.user_id FROM rico_chat_history h JOIN d1_target t ON t.id=h.user_id ORDER BY h.id) TO './secure-d1-backup/rico_chat_ownership.csv' CSV HEADER
\copy (SELECT l.id,l.user_id FROM rico_learning_signals l JOIN d1_target t ON t.id=l.user_id ORDER BY l.id) TO './secure-d1-backup/rico_learning_ownership.csv' CSV HEADER
\copy (SELECT l.id,l.canonical_user_id FROM learning_signals l WHERE lower(l.canonical_user_id) IN (SELECT alias FROM d1_aliases) ORDER BY l.id) TO './secure-d1-backup/learning_ownership.csv' CSV HEADER
\copy (SELECT j.id,j.user_id FROM user_job_context j WHERE lower(j.user_id) IN (SELECT alias FROM d1_aliases) ORDER BY j.id) TO './secure-d1-backup/job_context_ownership.csv' CSV HEADER
\copy (SELECT o.* FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_aliases) ORDER BY o.user_id) TO './secure-d1-backup/onboarding.csv' CSV HEADER
\copy (SELECT s.* FROM rico_agent_settings s JOIN d1_target t ON t.id=s.user_id ORDER BY s.id) TO './secure-d1-backup/agent_settings.csv' CSV HEADER
\copy (SELECT 5::bigint owner_rows,5::bigint profiles,1463::bigint chat_messages,0::bigint rico_learning_signals,24::bigint learning_signals,13::bigint job_context,5::bigint onboarding,1::bigint agent_settings) TO './secure-d1-backup/manifest.csv' CSV HEADER

SELECT jsonb_build_object(
  'target_rows',(SELECT count(*) FROM d1_target),
  'profiles',(SELECT count(*) FROM rico_profiles WHERE user_id IN (SELECT id FROM d1_target)),
  'chat_messages',(SELECT count(*) FROM rico_chat_history WHERE user_id IN (SELECT id FROM d1_target)),
  'learning_signals',(SELECT count(*) FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases)),
  'job_context',(SELECT count(*) FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)),
  'onboarding',(SELECT count(*) FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)),
  'agent_settings',(SELECT count(*) FROM rico_agent_settings WHERE user_id IN (SELECT id FROM d1_target))
) AS private_export_manifest;

ROLLBACK;
