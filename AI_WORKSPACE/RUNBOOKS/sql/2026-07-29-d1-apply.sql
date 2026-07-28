\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
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

UPDATE rico_onboarding_states
SET status='completed',
    completed_at=(SELECT min(completed_at) FROM rico_onboarding_states
                  WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)),
    updated_at=(SELECT max(updated_at) FROM rico_onboarding_states
                WHERE lower(user_id) IN (SELECT alias FROM d1_aliases))
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

  SELECT count(*) INTO v FROM rico_onboarding_states
    WHERE lower(user_id)=v_principal AND status='completed';
  IF v<>1 THEN RAISE EXCEPTION 'Post onboarding expected one completed row'; END IF;
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
