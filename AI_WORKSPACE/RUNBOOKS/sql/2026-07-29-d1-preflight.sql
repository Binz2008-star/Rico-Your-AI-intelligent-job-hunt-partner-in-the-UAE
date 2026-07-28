\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
\endif

BEGIN TRANSACTION READ ONLY ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';

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

INSERT INTO d1_target(id, external_user_id, email, class)
SELECT u.id, u.external_user_id, u.email,
       CASE
         WHEN lower(u.external_user_id) = p.target_principal THEN 'canonical'
         WHEN u.external_user_id LIKE 'public:%' THEN 'guest'
         ELSE 'email_only'
       END
FROM rico_users u
JOIN d1_params p ON lower(u.email) = p.target_principal;

CREATE TEMP TABLE d1_aliases (alias text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_aliases(alias)
SELECT DISTINCT lower(v)
FROM d1_target t
CROSS JOIN LATERAL unnest(ARRAY[t.id::text, t.external_user_id, t.email]) AS v
WHERE v IS NOT NULL AND btrim(v) <> '';

DO $$
DECLARE
  v_total int;
  v_canonical int;
  v_guest int;
  v_email_only int;
  v int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE class='canonical'),
         count(*) FILTER (WHERE class='guest'),
         count(*) FILTER (WHERE class='email_only')
    INTO v_total, v_canonical, v_guest, v_email_only
  FROM d1_target;

  IF v_total<>5 OR v_canonical<>1 OR v_guest<>2 OR v_email_only<>2 THEN
    RAISE EXCEPTION 'Target fingerprint mismatch: total %, canonical %, guest %, email_only %',
      v_total, v_canonical, v_guest, v_email_only;
  END IF;

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

SELECT jsonb_build_object(
  'owner_rows',(SELECT count(*) FROM d1_target),
  'canonical_rows',(SELECT count(*) FROM d1_target WHERE class='canonical'),
  'email_only_rows',(SELECT count(*) FROM d1_target WHERE class='email_only'),
  'guest_rows',(SELECT count(*) FROM d1_target WHERE class='guest'),
  'profiles',(SELECT count(*) FROM rico_profiles WHERE user_id IN (SELECT id FROM d1_target)),
  'chat_messages',(SELECT count(*) FROM rico_chat_history WHERE user_id IN (SELECT id FROM d1_target)),
  'learning_signals',(SELECT count(*) FROM learning_signals WHERE lower(canonical_user_id) IN (SELECT alias FROM d1_aliases)),
  'job_context',(SELECT count(*) FROM user_job_context WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)),
  'onboarding',(SELECT count(*) FROM rico_onboarding_states WHERE lower(user_id) IN (SELECT alias FROM d1_aliases)),
  'agent_settings',(SELECT count(*) FROM rico_agent_settings WHERE user_id IN (SELECT id FROM d1_target))
) AS d1_preflight;

ROLLBACK;
