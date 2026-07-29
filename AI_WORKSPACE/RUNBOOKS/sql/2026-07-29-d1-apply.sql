\set ON_ERROR_STOP on

-- psql ignores any argument to \quit and would exit 0, so this stop is raised as
-- a real server-side error instead. With ON_ERROR_STOP that yields a non-zero
-- psql exit status, which is what an operator or wrapper must see.
\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  DO $$ BEGIN RAISE EXCEPTION 'target_principal is required'; END $$;
\endif

\if :{?commit}
\else
  \set commit false
\endif

BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';
SELECT pg_advisory_xact_lock(hashtextextended('rico:d1-single-cluster-consolidation:v1',0));

DO $$
DECLARE
  v_schema_count int;
  v_schema_hash text;
BEGIN
  SELECT count(*),
         md5(string_agg(
           table_name||'.'||column_name||':'||data_type,
           ',' ORDER BY table_name,column_name))
    INTO v_schema_count,v_schema_hash
  FROM information_schema.columns
  WHERE table_schema='public'
    AND column_name IN ('user_id','canonical_user_id','external_user_id');

  IF v_schema_count<>39 OR v_schema_hash<>'aa3df6507f6909ab9bbf33e31082ee36' THEN
    RAISE EXCEPTION 'Ownership schema drift: columns %, hash %',
      v_schema_count,v_schema_hash;
  END IF;
END $$;

CREATE TEMP TABLE d1_params (target_principal text NOT NULL PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_params VALUES (lower(:'target_principal'));

CREATE TEMP TABLE d1_target (
  id uuid PRIMARY KEY,
  external_user_id text,
  email text NOT NULL,
  class text NOT NULL CHECK (class IN ('canonical','email_only','guest'))
) ON COMMIT DROP;

INSERT INTO d1_target(id,external_user_id,email,class)
SELECT u.id,u.external_user_id,u.email,
       CASE
         WHEN lower(u.external_user_id)=p.target_principal THEN 'canonical'
         WHEN u.external_user_id LIKE 'public:%' THEN 'guest'
         ELSE 'email_only'
       END
FROM rico_users u
JOIN d1_params p ON lower(u.email)=p.target_principal;

CREATE TEMP TABLE d1_aliases (alias text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_aliases(alias)
SELECT DISTINCT lower(v)
FROM d1_target t
CROSS JOIN LATERAL unnest(ARRAY[t.id::text,t.external_user_id,t.email]) v
WHERE v IS NOT NULL AND btrim(v)<>'';

DO $$
DECLARE
  v_total int;
  v_canonical int;
  v_guest int;
  v_email_only int;
  v int;
  v_canonical_id uuid;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE class='canonical'),
         count(*) FILTER (WHERE class='guest'),
         count(*) FILTER (WHERE class='email_only')
  INTO v_total,v_canonical,v_guest,v_email_only
  FROM d1_target;

  IF v_total<>5 OR v_canonical<>1 OR v_guest<>2 OR v_email_only<>2 THEN
    RAISE EXCEPTION 'Target fingerprint mismatch: total %, canonical %, guest %, email_only %',
      v_total,v_canonical,v_guest,v_email_only;
  END IF;

  SELECT id INTO v_canonical_id FROM d1_target WHERE class='canonical';

  SELECT count(*) INTO v FROM rico_profiles WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>5 THEN RAISE EXCEPTION 'Profiles expected 5, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_chat_history WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>1463 THEN RAISE EXCEPTION 'Chat expected 1463, got %',v; END IF;
  SELECT count(*) INTO v FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>24 THEN RAISE EXCEPTION 'Learning signals expected 24, got %',v; END IF;
  SELECT count(*) INTO v FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>13 THEN RAISE EXCEPTION 'Job context expected 13, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>5 THEN RAISE EXCEPTION 'Onboarding expected 5, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_agent_settings WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>1 THEN RAISE EXCEPTION 'Agent settings expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_agent_settings WHERE user_id=v_canonical_id;
  IF v<>1 THEN RAISE EXCEPTION 'Agent settings are not attached to canonical owner'; END IF;

  IF (SELECT count(DISTINCT profile->'skills') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM d1_target)
        AND profile ? 'skills' AND profile->'skills'<>'null'::jsonb)<>1
  THEN RAISE EXCEPTION 'Skills conflict or missing value'; END IF;
  IF (SELECT count(DISTINCT profile->'target_roles') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM d1_target)
        AND profile ? 'target_roles' AND profile->'target_roles'<>'null'::jsonb)<>1
  THEN RAISE EXCEPTION 'Target-role conflict or missing value'; END IF;
  IF (SELECT count(DISTINCT profile->'years_experience') FROM rico_profiles
      WHERE user_id IN (SELECT id FROM d1_target)
        AND profile ? 'years_experience' AND profile->'years_experience'<>'null'::jsonb)<>1
  THEN RAISE EXCEPTION 'Years-experience conflict or missing value'; END IF;

  SELECT count(*) INTO v FROM rico_profiles
  WHERE user_id IN (SELECT id FROM d1_target)
    AND ((cv_file_url IS NOT NULL AND btrim(cv_file_url)<>'')
      OR (cv_text IS NOT NULL AND btrim(cv_text)<>'')
      OR cv_structured<>'{}'::jsonb);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected authoritative CV columns: %',v; END IF;

  SELECT count(*) INTO v FROM rico_learning_signals WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected rico_learning_signals: %',v; END IF;
  SELECT count(*) INTO v FROM rico_alerts WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected rico_alerts: %',v; END IF;
  SELECT count(*) INTO v FROM rico_job_recommendations WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected rico_job_recommendations: %',v; END IF;
  SELECT count(*) INTO v FROM rico_saved_searches WHERE user_id IN (SELECT id FROM d1_target);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected rico_saved_searches: %',v; END IF;
  SELECT count(*) INTO v FROM rico_webhook_events
    WHERE user_id IN (SELECT id FROM d1_target)
       OR lower(external_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected rico_webhook_events: %',v; END IF;

  SELECT count(*) INTO v FROM application_drafts WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected application_drafts: %',v; END IF;
  SELECT count(*) INTO v FROM chat_operations WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected chat_operations: %',v; END IF;
  SELECT count(*) INTO v FROM cv_upload_artifacts WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected cv_upload_artifacts: %',v; END IF;
  SELECT count(*) INTO v FROM email_alert_log WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected email_alert_log: %',v; END IF;
  SELECT count(*) INTO v FROM email_unsubscribe_tokens WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected email_unsubscribe_tokens: %',v; END IF;
  SELECT count(*) INTO v FROM gmail_audit_events WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected gmail_audit_events: %',v; END IF;
  SELECT count(*) INTO v FROM gmail_connections WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected gmail_connections: %',v; END IF;
  SELECT count(*) INTO v FROM gmail_review_items WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected gmail_review_items: %',v; END IF;
  SELECT count(*) INTO v FROM gmail_sync_runs WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected gmail_sync_runs: %',v; END IF;
  SELECT count(*) INTO v FROM learning_signals_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected learning_signals_audit: %',v; END IF;
  SELECT count(*) INTO v FROM paddle_checkout_sessions WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected paddle_checkout_sessions: %',v; END IF;
  SELECT count(*) INTO v FROM paddle_customers WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected paddle_customers: %',v; END IF;
  SELECT count(*) INTO v FROM paddle_subscriptions WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected paddle_subscriptions: %',v; END IF;
  SELECT count(*) INTO v FROM paddle_webhook_events WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected paddle_webhook_events: %',v; END IF;
  SELECT count(*) INTO v FROM permission_check_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected permission_check_audit: %',v; END IF;
  SELECT count(*) INTO v FROM profile_hydration_audit WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected profile_hydration_audit: %',v; END IF;
  SELECT count(*) INTO v FROM search_context WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected search_context: %',v; END IF;
  SELECT count(*) INTO v FROM settings WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected settings: %',v; END IF;
  SELECT count(*) INTO v FROM subscription_events WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected subscription_events: %',v; END IF;
  SELECT count(*) INTO v FROM subscription_intents WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected subscription_intents: %',v; END IF;
  SELECT count(*) INTO v FROM telegram_alert_log WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected telegram_alert_log: %',v; END IF;
  SELECT count(*) INTO v FROM uploaded_document_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected uploaded_document_context: %',v; END IF;
  SELECT count(*) INTO v FROM user_avatars WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected user_avatars: %',v; END IF;
  SELECT count(*) INTO v FROM user_documents WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected user_documents: %',v; END IF;
  SELECT count(*) INTO v FROM user_subscriptions WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected user_subscriptions: %',v; END IF;
  SELECT count(*) INTO v FROM whatsapp_subscription_requests WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);
  IF v<>0 THEN RAISE EXCEPTION 'Unexpected whatsapp_subscription_requests: %',v; END IF;
END $$;

-- Strict onboarding pre-state gate.
-- The approved contract is five COMPLETED rows with non-null completed_at.
-- Row count alone is not sufficient: without this gate an in_progress row, or a
-- completed row that lost completed_at, would still reach the mutation below,
-- where the canonical row is forced to 'completed' and the aliases are deleted.
-- An unexpected onboarding state must abort, never be silently coerced.
DO $$
DECLARE
  v_rows int;
  v_completed int;
  v_completed_at_non_null int;
  v_non_completed int;
  v_completed_at_null int;
  v_canonical_rows int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE status='completed'),
         count(*) FILTER (WHERE completed_at IS NOT NULL),
         count(*) FILTER (WHERE status IS DISTINCT FROM 'completed'),
         count(*) FILTER (WHERE status='completed' AND completed_at IS NULL)
    INTO v_rows,v_completed,v_completed_at_non_null,v_non_completed,v_completed_at_null
  FROM rico_onboarding_states
  WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);

  IF v_rows<>5
     OR v_completed<>5
     OR v_completed_at_non_null<>5
     OR v_non_completed<>0
     OR v_completed_at_null<>0
  THEN
    RAISE EXCEPTION
      'Onboarding pre-state mismatch: rows %, completed %, completed_at_non_null %, non_completed %, completed_at_null %',
      v_rows,v_completed,v_completed_at_non_null,v_non_completed,v_completed_at_null;
  END IF;

  SELECT count(*) INTO v_canonical_rows
  FROM rico_onboarding_states
  WHERE lower(user_id)=(SELECT target_principal FROM d1_params);
  IF v_canonical_rows<>1 THEN
    RAISE EXCEPTION 'Canonical onboarding row expected 1, got %',v_canonical_rows;
  END IF;
END $$;

DO $$
BEGIN
  PERFORM 1 FROM rico_users WHERE id IN (SELECT id FROM d1_target) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_profiles WHERE user_id IN (SELECT id FROM d1_target) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_chat_history WHERE user_id IN (SELECT id FROM d1_target) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_learning_signals WHERE user_id IN (SELECT id FROM d1_target) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_agent_settings WHERE user_id IN (SELECT id FROM d1_target) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases) ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM d1_aliases) ORDER BY user_id FOR UPDATE;
END $$;

WITH values_to_merge AS (
  SELECT
    (array_agg(profile->'skills') FILTER (
      WHERE profile ? 'skills' AND profile->'skills'<>'null'::jsonb))[1] AS skills,
    (array_agg(profile->'target_roles') FILTER (
      WHERE profile ? 'target_roles' AND profile->'target_roles'<>'null'::jsonb))[1] AS target_roles,
    (array_agg(profile->'years_experience') FILTER (
      WHERE profile ? 'years_experience' AND profile->'years_experience'<>'null'::jsonb))[1] AS years_experience
  FROM rico_profiles
  WHERE user_id IN (SELECT id FROM d1_target)
), merged AS (
  SELECT p.id,
    jsonb_set(
      jsonb_set(
        jsonb_set(
          p.profile-'cv_filename'-'cv_status',
          '{skills}',
          CASE WHEN NOT(p.profile?'skills') OR p.profile->'skills'='null'::jsonb
               THEN v.skills ELSE p.profile->'skills' END,
          true),
        '{target_roles}',
        CASE WHEN NOT(p.profile?'target_roles') OR p.profile->'target_roles'='null'::jsonb
             THEN v.target_roles ELSE p.profile->'target_roles' END,
        true),
      '{years_experience}',
      CASE WHEN NOT(p.profile?'years_experience') OR p.profile->'years_experience'='null'::jsonb
           THEN v.years_experience ELSE p.profile->'years_experience' END,
      true) AS profile
  FROM rico_profiles p
  CROSS JOIN values_to_merge v
  WHERE p.user_id=(SELECT id FROM d1_target WHERE class='canonical')
)
UPDATE rico_profiles p
SET profile=m.profile,
    cv_file_url=NULL,
    cv_text=NULL,
    cv_structured='{}'::jsonb,
    updated_at=now()
FROM merged m
WHERE p.id=m.id;

UPDATE rico_chat_history
SET user_id=(SELECT id FROM d1_target WHERE class='canonical')
WHERE user_id IN (SELECT id FROM d1_target WHERE class<>'canonical');

UPDATE rico_learning_signals
SET user_id=(SELECT id FROM d1_target WHERE class='canonical')
WHERE user_id IN (SELECT id FROM d1_target WHERE class<>'canonical');

UPDATE learning_signals
SET canonical_user_id=(SELECT target_principal FROM d1_params)
WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases);

UPDATE user_job_context
SET user_id=(SELECT target_principal FROM d1_params)
WHERE lower(user_id) IN (SELECT alias FROM d1_aliases);

-- Merge rule, enforced by the onboarding pre-state gate above:
--   completed_at = earliest completed_at across the five approved completed rows;
--   updated_at   = latest updated_at across the same five rows.
-- Both aggregates are filtered to completed rows with a non-null completed_at so
-- the merge can never silently derive a value from an unexpected row state.
UPDATE rico_onboarding_states
SET status='completed',
    completed_at=(SELECT min(completed_at) FROM rico_onboarding_states
                  WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)
                    AND status='completed' AND completed_at IS NOT NULL),
    updated_at=(SELECT max(updated_at) FROM rico_onboarding_states
                WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)
                  AND status='completed' AND completed_at IS NOT NULL)
WHERE lower(user_id)=(SELECT target_principal FROM d1_params);

DELETE FROM rico_onboarding_states
WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)
  AND lower(user_id)<>(SELECT target_principal FROM d1_params);

DELETE FROM rico_profiles
WHERE user_id IN (SELECT id FROM d1_target WHERE class<>'canonical');

DELETE FROM rico_users
WHERE id IN (SELECT id FROM d1_target WHERE class<>'canonical');

DO $$
DECLARE
  v int;
  v_canonical uuid;
  v_principal text;
BEGIN
  SELECT id INTO v_canonical FROM d1_target WHERE class='canonical';
  SELECT target_principal INTO v_principal FROM d1_params;

  SELECT count(*) INTO v FROM rico_users WHERE lower(email)=v_principal;
  IF v<>1 THEN RAISE EXCEPTION 'Post owners expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_users
    WHERE id=v_canonical AND lower(external_user_id)=v_principal;
  IF v<>1 THEN RAISE EXCEPTION 'Canonical owner missing'; END IF;

  SELECT count(*) INTO v FROM rico_profiles WHERE user_id=v_canonical;
  IF v<>1 THEN RAISE EXCEPTION 'Post profile expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_profiles
    WHERE user_id=v_canonical
      AND ((profile ? 'cv_filename') OR (profile ? 'cv_status')
        OR cv_file_url IS NOT NULL OR cv_text IS NOT NULL
        OR cv_structured<>'{}'::jsonb);
  IF v<>0 THEN RAISE EXCEPTION 'Stale CV claims remain'; END IF;
  SELECT count(*) INTO v FROM rico_profiles
    WHERE user_id=v_canonical
      AND profile->'skills'<>'null'::jsonb
      AND profile->'target_roles'<>'null'::jsonb
      AND profile->'years_experience'<>'null'::jsonb;
  IF v<>1 THEN RAISE EXCEPTION 'Career fields incomplete'; END IF;

  SELECT count(*) INTO v FROM rico_chat_history WHERE user_id=v_canonical;
  IF v<>1463 THEN RAISE EXCEPTION 'Post chat expected 1463, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_chat_history
    WHERE user_id IN (SELECT id FROM d1_target WHERE class<>'canonical');
  IF v<>0 THEN RAISE EXCEPTION 'Chat remains on duplicate owners'; END IF;

  SELECT count(*) INTO v FROM learning_signals WHERE lower(canonical_user_id)=v_principal;
  IF v<>24 THEN RAISE EXCEPTION 'Post learning expected 24, got %',v; END IF;
  SELECT count(*) INTO v FROM learning_signals
    WHERE lower(canonical_user_id) IN (
      SELECT alias FROM d1_aliases WHERE alias<>v_principal);
  IF v<>0 THEN RAISE EXCEPTION 'Learning aliases remain'; END IF;

  SELECT count(*) INTO v FROM user_job_context WHERE lower(user_id)=v_principal;
  IF v<>13 THEN RAISE EXCEPTION 'Post job context expected 13, got %',v; END IF;
  SELECT count(*) INTO v FROM user_job_context
    WHERE lower(user_id) IN (SELECT alias FROM d1_aliases WHERE alias<>v_principal);
  IF v<>0 THEN RAISE EXCEPTION 'Job-context aliases remain'; END IF;

  SELECT count(*) INTO v FROM rico_onboarding_states WHERE lower(user_id)=v_principal;
  IF v<>1 THEN RAISE EXCEPTION 'Post onboarding expected exactly one canonical row, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states
    WHERE lower(user_id)=v_principal AND status='completed' AND completed_at IS NOT NULL;
  IF v<>1 THEN
    RAISE EXCEPTION 'Post onboarding canonical row is not completed with a non-null completed_at';
  END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states
    WHERE lower(user_id) IN (SELECT alias FROM d1_aliases WHERE alias<>v_principal);
  IF v<>0 THEN RAISE EXCEPTION 'Onboarding aliases remain'; END IF;

  SELECT count(*) INTO v FROM rico_agent_settings WHERE user_id=v_canonical;
  IF v<>1 THEN RAISE EXCEPTION 'Canonical settings missing'; END IF;
END $$;

SELECT jsonb_build_object(
  'owner_rows',1,
  'profiles',1,
  'chat_messages',1463,
  'learning_signals',24,
  'job_context',13,
  'onboarding',1,
  'agent_settings',1,
  'stale_cv_claims',0,
  'requested_commit',:'commit'
) AS d1_apply_result;

\if :commit
  COMMIT;
\else
  ROLLBACK;
\endif
