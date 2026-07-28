\set ON_ERROR_STOP on

\if :{?target_principal}
\else
  \echo 'ERROR: target_principal is required and must be supplied privately.'
  \quit 3
\endif

BEGIN TRANSACTION READ ONLY ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='30s';
SET LOCAL lock_timeout='2s';

CREATE TEMP TABLE d1_params(target_principal text NOT NULL PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_params VALUES(lower(:'target_principal'));

CREATE TEMP TABLE d1_canonical ON COMMIT DROP AS
SELECT u.id,u.external_user_id,u.email
FROM rico_users u
JOIN d1_params p
  ON lower(u.external_user_id)=p.target_principal
 AND lower(u.email)=p.target_principal;

DO $$
DECLARE v int; c uuid; p text;
BEGIN
  SELECT target_principal INTO p FROM d1_params;
  IF (SELECT count(*) FROM d1_canonical)<>1 THEN RAISE EXCEPTION 'Canonical owner expected 1'; END IF;
  SELECT id INTO c FROM d1_canonical;

  SELECT count(*) INTO v FROM rico_users WHERE lower(email)=p;
  IF v<>1 THEN RAISE EXCEPTION 'Owner rows expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_profiles WHERE user_id=c;
  IF v<>1 THEN RAISE EXCEPTION 'Profile rows expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_chat_history WHERE user_id=c;
  IF v<>1463 THEN RAISE EXCEPTION 'Chat messages expected 1463, got %',v; END IF;
  SELECT count(*) INTO v FROM learning_signals WHERE lower(canonical_user_id)=p;
  IF v<>24 THEN RAISE EXCEPTION 'Learning signals expected 24, got %',v; END IF;
  SELECT count(*) INTO v FROM user_job_context WHERE lower(user_id)=p;
  IF v<>13 THEN RAISE EXCEPTION 'Job context expected 13, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states WHERE lower(user_id)=p AND status='completed';
  IF v<>1 THEN RAISE EXCEPTION 'Completed onboarding expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_agent_settings WHERE user_id=c;
  IF v<>1 THEN RAISE EXCEPTION 'Agent settings expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_profiles
  WHERE user_id=c
    AND ((profile ? 'cv_filename') OR (profile ? 'cv_status')
      OR cv_file_url IS NOT NULL OR cv_text IS NOT NULL
      OR cv_structured<>'{}'::jsonb);
  IF v<>0 THEN RAISE EXCEPTION 'Stale CV claims remain: %',v; END IF;
  SELECT count(*) INTO v FROM rico_profiles
  WHERE user_id=c
    AND profile->'skills'<>'null'::jsonb
    AND profile->'target_roles'<>'null'::jsonb
    AND profile->'years_experience'<>'null'::jsonb;
  IF v<>1 THEN RAISE EXCEPTION 'Canonical career fields incomplete'; END IF;
END $$;

SELECT jsonb_build_object(
  'owner_rows',(SELECT count(*) FROM rico_users WHERE lower(email)=(SELECT target_principal FROM d1_params)),
  'canonical_rows',(SELECT count(*) FROM d1_canonical),
  'profiles',(SELECT count(*) FROM rico_profiles WHERE user_id=(SELECT id FROM d1_canonical)),
  'chat_messages',(SELECT count(*) FROM rico_chat_history WHERE user_id=(SELECT id FROM d1_canonical)),
  'learning_signals',(SELECT count(*) FROM learning_signals WHERE lower(canonical_user_id)=(SELECT target_principal FROM d1_params)),
  'job_context',(SELECT count(*) FROM user_job_context WHERE lower(user_id)=(SELECT target_principal FROM d1_params)),
  'onboarding',(SELECT count(*) FROM rico_onboarding_states WHERE lower(user_id)=(SELECT target_principal FROM d1_params) AND status='completed'),
  'agent_settings',(SELECT count(*) FROM rico_agent_settings WHERE user_id=(SELECT id FROM d1_canonical)),
  'stale_cv_claims',0
) AS d1_postcheck;

ROLLBACK;
