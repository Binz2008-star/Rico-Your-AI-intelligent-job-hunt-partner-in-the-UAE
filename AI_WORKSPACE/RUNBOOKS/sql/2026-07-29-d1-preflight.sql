\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
\endif

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';

WITH
params AS (
  SELECT lower(:'target_principal')::text AS target_principal
),
target AS (
  SELECT u.id,u.external_user_id,u.email,
         CASE
           WHEN lower(u.external_user_id)=p.target_principal THEN 'canonical'
           WHEN u.external_user_id LIKE 'public:%' THEN 'guest'
           ELSE 'email_only'
         END AS class
  FROM rico_users u
  CROSS JOIN params p
  WHERE lower(u.email)=p.target_principal
),
aliases AS (
  SELECT DISTINCT lower(v) AS alias
  FROM target t
  CROSS JOIN LATERAL unnest(ARRAY[t.id::text,t.external_user_id,t.email]) v
  WHERE v IS NOT NULL AND btrim(v)<>''
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
    (SELECT count(*) FROM target)::bigint AS owner_rows,
    (SELECT count(*) FROM target WHERE class='canonical')::bigint AS canonical_rows,
    (SELECT count(*) FROM target WHERE class='email_only')::bigint AS email_only_rows,
    (SELECT count(*) FROM target WHERE class='guest')::bigint AS guest_rows,
    (SELECT count(*) FROM rico_profiles WHERE user_id IN (SELECT id FROM target))::bigint AS profiles,
    (SELECT count(*) FROM rico_chat_history WHERE user_id IN (SELECT id FROM target))::bigint AS chat_messages,
    (SELECT count(*) FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM aliases))::bigint AS learning_signals,
    (SELECT count(*) FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM aliases))::bigint AS job_context,
    (SELECT count(*) FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM aliases))::bigint AS onboarding,
    (SELECT count(*) FROM rico_agent_settings WHERE user_id IN (SELECT id FROM target))::bigint AS agent_settings,
    (SELECT count(*) FROM rico_agent_settings WHERE user_id IN (SELECT id FROM target WHERE class='canonical'))::bigint AS canonical_agent_settings,
    (SELECT count(DISTINCT profile->'skills') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM target)
        AND profile ? 'skills' AND profile->'skills'<>'null'::jsonb)::bigint AS skills_distinct,
    (SELECT count(DISTINCT profile->'target_roles') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM target)
        AND profile ? 'target_roles' AND profile->'target_roles'<>'null'::jsonb)::bigint AS target_roles_distinct,
    (SELECT count(DISTINCT profile->'years_experience') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM target)
        AND profile ? 'years_experience' AND profile->'years_experience'<>'null'::jsonb)::bigint AS years_experience_distinct,
    (SELECT count(*) FROM rico_profiles
      WHERE user_id IN (SELECT id FROM target)
        AND ((cv_file_url IS NOT NULL AND btrim(cv_file_url)<>'')
          OR (cv_text IS NOT NULL AND btrim(cv_text)<>'')
          OR cv_structured<>'{}'::jsonb))::bigint AS authoritative_cv_rows,
    (
      (SELECT count(*) FROM rico_learning_signals WHERE user_id IN (SELECT id FROM target))
      +(SELECT count(*) FROM rico_alerts WHERE user_id IN (SELECT id FROM target))
      +(SELECT count(*) FROM rico_job_recommendations WHERE user_id IN (SELECT id FROM target))
      +(SELECT count(*) FROM rico_saved_searches WHERE user_id IN (SELECT id FROM target))
      +(SELECT count(*) FROM rico_webhook_events
          WHERE user_id IN (SELECT id FROM target)
             OR lower(external_user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM application_drafts WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM chat_operations WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM cv_upload_artifacts WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM email_alert_log WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM email_unsubscribe_tokens WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM gmail_audit_events WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM gmail_connections WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM gmail_review_items WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM gmail_sync_runs WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM learning_signals_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM paddle_checkout_sessions WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM paddle_customers WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM paddle_subscriptions WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM paddle_webhook_events WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM permission_check_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM profile_hydration_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM search_context WHERE lower(canonical_user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM settings WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM subscription_events WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM subscription_intents WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM telegram_alert_log WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM uploaded_document_context WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM user_avatars WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM user_documents WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM user_subscriptions WHERE lower(user_id) IN (SELECT alias FROM aliases))
      +(SELECT count(*) FROM whatsapp_subscription_requests WHERE lower(user_id) IN (SELECT alias FROM aliases))
    )::bigint AS unexpected_domain_rows
  FROM schema_metrics s
),
result AS (
  SELECT
    (
      schema_count=39
      AND coalesce(schema_hash='aa3df6507f6909ab9bbf33e31082ee36',false)
      AND owner_rows=5
      AND canonical_rows=1
      AND email_only_rows=2
      AND guest_rows=2
      AND profiles=5
      AND chat_messages=1463
      AND learning_signals=24
      AND job_context=13
      AND onboarding=5
      AND agent_settings=1
      AND canonical_agent_settings=1
      AND skills_distinct=1
      AND target_roles_distinct=1
      AND years_experience_distinct=1
      AND authoritative_cv_rows=0
      AND unexpected_domain_rows=0
    ) AS preflight_ok,
    jsonb_build_object(
      'schema_count',schema_count,
      'schema_hash',schema_hash,
      'owner_rows',owner_rows,
      'canonical_rows',canonical_rows,
      'email_only_rows',email_only_rows,
      'guest_rows',guest_rows,
      'profiles',profiles,
      'chat_messages',chat_messages,
      'learning_signals',learning_signals,
      'job_context',job_context,
      'onboarding',onboarding,
      'agent_settings',agent_settings,
      'canonical_agent_settings',canonical_agent_settings,
      'skills_distinct',skills_distinct,
      'target_roles_distinct',target_roles_distinct,
      'years_experience_distinct',years_experience_distinct,
      'authoritative_cv_rows',authoritative_cv_rows,
      'unexpected_domain_rows',unexpected_domain_rows
    ) AS preflight_result
  FROM metrics
)
SELECT preflight_ok,preflight_result FROM result
\gset d1_

\if :d1_preflight_ok
  SELECT :'d1_preflight_result'::jsonb AS d1_preflight;
\else
  \echo 'ERROR: D1 preflight failed; transaction will roll back.'
  SELECT :'d1_preflight_result'::jsonb AS d1_preflight_failure;
  ROLLBACK;
  \quit 4
\endif

ROLLBACK;
