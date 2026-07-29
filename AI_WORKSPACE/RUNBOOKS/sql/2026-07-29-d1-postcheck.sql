\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
\endif

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY;
SET LOCAL statement_timeout='30s';
SET LOCAL lock_timeout='2s';

WITH
params AS (
  SELECT lower(:'target_principal')::text AS target_principal
),
canonical AS (
  SELECT u.id,u.external_user_id,u.email
  FROM rico_users u
  CROSS JOIN params p
  WHERE lower(u.external_user_id)=p.target_principal
    AND lower(u.email)=p.target_principal
),
schema_metrics AS (
  SELECT count(*)::bigint AS schema_count,
         md5(string_agg(
           table_name||'.'||column_name||':'||data_type,
           ',' ORDER BY table_name,column_name)) AS schema_hash
  FROM information_schema.columns
  WHERE table_schema='public'
    AND column_name IN ('user_id','canonical_user_id','external_user_id')
),
metrics AS (
  SELECT
    s.schema_count,
    s.schema_hash,
    (SELECT count(*) FROM canonical)::bigint AS canonical_rows,
    (SELECT count(*) FROM rico_users
      WHERE lower(email)=(SELECT target_principal FROM params))::bigint AS owner_rows,
    (SELECT count(*) FROM rico_profiles
      WHERE user_id IN (SELECT id FROM canonical))::bigint AS profiles,
    (SELECT count(*) FROM rico_chat_history
      WHERE user_id IN (SELECT id FROM canonical))::bigint AS chat_messages,
    (SELECT count(*) FROM learning_signals
      WHERE lower(canonical_user_id)=(SELECT target_principal FROM params))::bigint AS learning_signals,
    (SELECT count(*) FROM user_job_context
      WHERE lower(user_id)=(SELECT target_principal FROM params))::bigint AS job_context,
    (SELECT count(*) FROM rico_onboarding_states
      WHERE lower(user_id)=(SELECT target_principal FROM params)
        AND status='completed')::bigint AS onboarding,
    (SELECT count(*) FROM rico_agent_settings
      WHERE user_id IN (SELECT id FROM canonical))::bigint AS agent_settings,
    (SELECT count(*) FROM rico_profiles
      WHERE user_id IN (SELECT id FROM canonical)
        AND ((profile ? 'cv_filename') OR (profile ? 'cv_status')
          OR cv_file_url IS NOT NULL OR cv_text IS NOT NULL
          OR cv_structured<>'{}'::jsonb))::bigint AS stale_cv_claims,
    (SELECT count(*) FROM rico_profiles
      WHERE user_id IN (SELECT id FROM canonical)
        AND profile ? 'skills' AND profile->'skills'<>'null'::jsonb
        AND profile ? 'target_roles' AND profile->'target_roles'<>'null'::jsonb
        AND profile ? 'years_experience' AND profile->'years_experience'<>'null'::jsonb)::bigint AS career_complete_profiles
  FROM schema_metrics s
),
result AS (
  SELECT
    (
      schema_count=39
      AND coalesce(schema_hash='aa3df6507f6909ab9bbf33e31082ee36',false)
      AND canonical_rows=1
      AND owner_rows=1
      AND profiles=1
      AND chat_messages=1463
      AND learning_signals=24
      AND job_context=13
      AND onboarding=1
      AND agent_settings=1
      AND stale_cv_claims=0
      AND career_complete_profiles=1
    ) AS postcheck_ok,
    jsonb_build_object(
      'schema_count',schema_count,
      'schema_hash',schema_hash,
      'canonical_rows',canonical_rows,
      'owner_rows',owner_rows,
      'profiles',profiles,
      'chat_messages',chat_messages,
      'learning_signals',learning_signals,
      'job_context',job_context,
      'onboarding',onboarding,
      'agent_settings',agent_settings,
      'stale_cv_claims',stale_cv_claims,
      'career_complete_profiles',career_complete_profiles
    ) AS postcheck_result
  FROM metrics
)
SELECT postcheck_ok,postcheck_result FROM result
\gset d1_

\if :d1_postcheck_ok
  SELECT :'d1_postcheck_result'::jsonb AS d1_postcheck;
\else
  \echo 'ERROR: D1 postcheck failed; evaluate rollback immediately.'
  SELECT :'d1_postcheck_result'::jsonb AS d1_postcheck_failure;
  ROLLBACK;
  \quit 5
\endif

ROLLBACK;
