\set ON_ERROR_STOP on

\if :{?commit}
\else
  \set commit false
\endif

-- Run only when a rollback condition in the runbook is met.
-- ./secure-d1-backup must contain the private export from the exact
-- pre-repair Neon backup branch.

BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='60s';
SET LOCAL lock_timeout='2s';
SELECT pg_advisory_xact_lock(hashtextextended('rico:d1-single-cluster-consolidation:v1',0));

CREATE TEMP TABLE d1_restore_target (
  id uuid PRIMARY KEY,
  external_user_id text,
  email text NOT NULL,
  class text NOT NULL CHECK (class IN ('canonical','email_only','guest'))
) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_users (LIKE rico_users INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_profiles (LIKE rico_profiles INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_chat_ownership (id uuid PRIMARY KEY,user_id uuid) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_rico_learning_ownership (id uuid PRIMARY KEY,user_id uuid) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_learning_ownership (id integer PRIMARY KEY,canonical_user_id varchar) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_job_context_ownership (id integer PRIMARY KEY,user_id text NOT NULL) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_onboarding (LIKE rico_onboarding_states INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_agent_settings (LIKE rico_agent_settings INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE d1_restore_manifest (
  owner_rows bigint,profiles bigint,chat_messages bigint,
  rico_learning_signals bigint,learning_signals bigint,
  job_context bigint,onboarding bigint,
  onboarding_completed bigint,onboarding_completed_at_non_null bigint,
  onboarding_non_completed bigint,onboarding_completed_at_null bigint,
  agent_settings bigint
) ON COMMIT DROP;

\copy d1_restore_target FROM './secure-d1-backup/target.csv' CSV HEADER
\copy d1_restore_users FROM './secure-d1-backup/rico_users.csv' CSV HEADER
\copy d1_restore_profiles FROM './secure-d1-backup/rico_profiles.csv' CSV HEADER
\copy d1_restore_chat_ownership FROM './secure-d1-backup/rico_chat_ownership.csv' CSV HEADER
\copy d1_restore_rico_learning_ownership FROM './secure-d1-backup/rico_learning_ownership.csv' CSV HEADER
\copy d1_restore_learning_ownership FROM './secure-d1-backup/learning_ownership.csv' CSV HEADER
\copy d1_restore_job_context_ownership FROM './secure-d1-backup/job_context_ownership.csv' CSV HEADER
\copy d1_restore_onboarding FROM './secure-d1-backup/onboarding.csv' CSV HEADER
\copy d1_restore_agent_settings FROM './secure-d1-backup/agent_settings.csv' CSV HEADER
\copy d1_restore_manifest FROM './secure-d1-backup/manifest.csv' CSV HEADER

CREATE TEMP TABLE d1_restore_aliases(alias text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO d1_restore_aliases(alias)
SELECT DISTINCT lower(v)
FROM d1_restore_target t
CROSS JOIN LATERAL unnest(ARRAY[t.id::text,t.external_user_id,t.email]) v
WHERE v IS NOT NULL AND btrim(v)<>'';

DO $$
DECLARE v int; v_canonical uuid; v_principal text;
BEGIN
  IF (SELECT count(*) FROM d1_restore_manifest)<>1 THEN RAISE EXCEPTION 'Manifest row count mismatch'; END IF;
  IF (SELECT count(*) FROM d1_restore_target)<>5 THEN RAISE EXCEPTION 'Restore target expected 5'; END IF;
  IF (SELECT count(*) FROM d1_restore_target WHERE class='canonical')<>1 THEN RAISE EXCEPTION 'Restore canonical expected 1'; END IF;
  IF (SELECT count(*) FROM d1_restore_target WHERE class='email_only')<>2 THEN RAISE EXCEPTION 'Restore email-only expected 2'; END IF;
  IF (SELECT count(*) FROM d1_restore_target WHERE class='guest')<>2 THEN RAISE EXCEPTION 'Restore guests expected 2'; END IF;
  IF (SELECT count(*) FROM d1_restore_users)<>5 THEN RAISE EXCEPTION 'Restore users expected 5'; END IF;
  IF (SELECT count(*) FROM d1_restore_profiles)<>5 THEN RAISE EXCEPTION 'Restore profiles expected 5'; END IF;
  IF (SELECT count(*) FROM d1_restore_chat_ownership)<>1463 THEN RAISE EXCEPTION 'Restore chat mapping expected 1463'; END IF;
  IF (SELECT count(*) FROM d1_restore_rico_learning_ownership)<>0 THEN RAISE EXCEPTION 'Restore UUID learning expected 0'; END IF;
  IF (SELECT count(*) FROM d1_restore_learning_ownership)<>24 THEN RAISE EXCEPTION 'Restore learning mapping expected 24'; END IF;
  IF (SELECT count(*) FROM d1_restore_job_context_ownership)<>13 THEN RAISE EXCEPTION 'Restore job mapping expected 13'; END IF;
  IF (SELECT count(*) FROM d1_restore_onboarding)<>5 THEN RAISE EXCEPTION 'Restore onboarding expected 5'; END IF;
  IF (SELECT count(*) FROM d1_restore_agent_settings)<>1 THEN RAISE EXCEPTION 'Restore settings expected 1'; END IF;

  -- The private backup must itself carry the approved onboarding pre-state.
  -- Restoring from an export that was taken in an unexpected state would
  -- reinstate that state as if it had been approved.
  IF (SELECT count(*) FROM d1_restore_onboarding WHERE status='completed')<>5
     OR (SELECT count(*) FROM d1_restore_onboarding WHERE completed_at IS NOT NULL)<>5
     OR (SELECT count(*) FROM d1_restore_onboarding WHERE status IS DISTINCT FROM 'completed')<>0
     OR (SELECT count(*) FROM d1_restore_onboarding WHERE status='completed' AND completed_at IS NULL)<>0
  THEN
    RAISE EXCEPTION 'Backup onboarding state is not the approved five completed rows';
  END IF;

  IF (SELECT onboarding FROM d1_restore_manifest)<>5
     OR (SELECT onboarding_completed FROM d1_restore_manifest)<>5
     OR (SELECT onboarding_completed_at_non_null FROM d1_restore_manifest)<>5
     OR (SELECT onboarding_non_completed FROM d1_restore_manifest)<>0
     OR (SELECT onboarding_completed_at_null FROM d1_restore_manifest)<>0
  THEN
    RAISE EXCEPTION 'Manifest onboarding invariants do not match the approved pre-state';
  END IF;

  SELECT id,lower(email) INTO v_canonical,v_principal
  FROM d1_restore_target WHERE class='canonical';

  SELECT count(*) INTO v FROM rico_users WHERE lower(email)=v_principal;
  IF v<>1 THEN RAISE EXCEPTION 'Rollback precondition owner count expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_profiles WHERE user_id=v_canonical;
  IF v<>1 THEN RAISE EXCEPTION 'Rollback precondition profile expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_chat_history WHERE user_id=v_canonical;
  IF v<>1463 THEN RAISE EXCEPTION 'Rollback precondition chat expected 1463, got %',v; END IF;
  SELECT count(*) INTO v FROM learning_signals WHERE lower(canonical_user_id)=v_principal;
  IF v<>24 THEN RAISE EXCEPTION 'Rollback precondition learning expected 24, got %',v; END IF;
  SELECT count(*) INTO v FROM user_job_context WHERE lower(user_id)=v_principal;
  IF v<>13 THEN RAISE EXCEPTION 'Rollback precondition jobs expected 13, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states WHERE lower(user_id)=v_principal;
  IF v<>1 THEN RAISE EXCEPTION 'Rollback precondition onboarding expected 1, got %',v; END IF;
  SELECT count(*) INTO v FROM rico_onboarding_states
    WHERE lower(user_id)=v_principal AND status='completed' AND completed_at IS NOT NULL;
  IF v<>1 THEN
    RAISE EXCEPTION 'Rollback precondition: canonical onboarding row is not completed with a non-null completed_at';
  END IF;

  SELECT count(*) INTO v
  FROM rico_users u JOIN d1_restore_users b
    ON u.external_user_id=b.external_user_id AND u.id<>b.id
  WHERE b.external_user_id IS NOT NULL;
  IF v<>0 THEN RAISE EXCEPTION 'External-user-id collision: %',v; END IF;
END $$;

DO $$
BEGIN
  PERFORM 1 FROM rico_users
    WHERE lower(email)=(SELECT lower(email) FROM d1_restore_target WHERE class='canonical')
    ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_profiles
    WHERE user_id=(SELECT id FROM d1_restore_target WHERE class='canonical')
    ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_chat_history
    WHERE id IN (SELECT id FROM d1_restore_chat_ownership)
    ORDER BY id FOR UPDATE;
  PERFORM 1 FROM learning_signals
    WHERE id IN (SELECT id FROM d1_restore_learning_ownership)
    ORDER BY id FOR UPDATE;
  PERFORM 1 FROM user_job_context
    WHERE id IN (SELECT id FROM d1_restore_job_context_ownership)
    ORDER BY id FOR UPDATE;
  PERFORM 1 FROM rico_onboarding_states
    WHERE lower(user_id) IN (SELECT alias FROM d1_restore_aliases)
    ORDER BY user_id FOR UPDATE;
END $$;

INSERT INTO rico_users(
  id,external_user_id,name,email,phone,telegram_username,telegram_chat_id,
  source,created_at,updated_at,telegram_notifications_enabled)
SELECT
  id,external_user_id,name,email,phone,telegram_username,telegram_chat_id,
  source,created_at,updated_at,telegram_notifications_enabled
FROM d1_restore_users
ON CONFLICT(id) DO UPDATE SET
  external_user_id=EXCLUDED.external_user_id,
  name=EXCLUDED.name,
  email=EXCLUDED.email,
  phone=EXCLUDED.phone,
  telegram_username=EXCLUDED.telegram_username,
  telegram_chat_id=EXCLUDED.telegram_chat_id,
  source=EXCLUDED.source,
  created_at=EXCLUDED.created_at,
  updated_at=EXCLUDED.updated_at,
  telegram_notifications_enabled=EXCLUDED.telegram_notifications_enabled;

DELETE FROM rico_profiles
WHERE user_id IN (SELECT id FROM d1_restore_target);
INSERT INTO rico_profiles(
  id,user_id,profile,cv_file_url,cv_text,cv_structured,created_at,updated_at)
SELECT id,user_id,profile,cv_file_url,cv_text,cv_structured,created_at,updated_at
FROM d1_restore_profiles;

UPDATE rico_chat_history h
SET user_id=b.user_id
FROM d1_restore_chat_ownership b
WHERE h.id=b.id;

UPDATE rico_learning_signals l
SET user_id=b.user_id
FROM d1_restore_rico_learning_ownership b
WHERE l.id=b.id;

UPDATE learning_signals l
SET canonical_user_id=b.canonical_user_id
FROM d1_restore_learning_ownership b
WHERE l.id=b.id;

UPDATE user_job_context j
SET user_id=b.user_id
FROM d1_restore_job_context_ownership b
WHERE j.id=b.id;

DELETE FROM rico_onboarding_states
WHERE lower(user_id) IN (SELECT alias FROM d1_restore_aliases);
INSERT INTO rico_onboarding_states(user_id,status,completed_at,updated_at)
SELECT user_id,status,completed_at,updated_at
FROM d1_restore_onboarding;

DELETE FROM rico_agent_settings
WHERE user_id IN (SELECT id FROM d1_restore_target);
INSERT INTO rico_agent_settings(id,user_id,settings,created_at,updated_at)
SELECT id,user_id,settings,created_at,updated_at
FROM d1_restore_agent_settings;

DO $$
DECLARE v int;
BEGIN
  SELECT count(*) INTO v FROM (
    (SELECT u.* FROM rico_users u WHERE u.id IN (SELECT id FROM d1_restore_target))
    EXCEPT (SELECT * FROM d1_restore_users)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Restored users differ: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_users)
    EXCEPT (SELECT u.* FROM rico_users u WHERE u.id IN (SELECT id FROM d1_restore_target))
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Restored users missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT p.* FROM rico_profiles p WHERE p.user_id IN (SELECT id FROM d1_restore_target))
    EXCEPT (SELECT * FROM d1_restore_profiles)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Restored profiles differ: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_profiles)
    EXCEPT (SELECT p.* FROM rico_profiles p WHERE p.user_id IN (SELECT id FROM d1_restore_target))
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Restored profiles missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT h.id,h.user_id FROM rico_chat_history h JOIN d1_restore_chat_ownership b ON b.id=h.id)
    EXCEPT (SELECT * FROM d1_restore_chat_ownership)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Chat ownership differs: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_chat_ownership)
    EXCEPT (SELECT h.id,h.user_id FROM rico_chat_history h JOIN d1_restore_chat_ownership b ON b.id=h.id)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Chat ownership rows missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT l.id,l.user_id FROM rico_learning_signals l JOIN d1_restore_rico_learning_ownership b ON b.id=l.id)
    EXCEPT (SELECT * FROM d1_restore_rico_learning_ownership)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'UUID learning ownership differs: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_rico_learning_ownership)
    EXCEPT (SELECT l.id,l.user_id FROM rico_learning_signals l JOIN d1_restore_rico_learning_ownership b ON b.id=l.id)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'UUID learning rows missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT l.id,l.canonical_user_id FROM learning_signals l JOIN d1_restore_learning_ownership b ON b.id=l.id)
    EXCEPT (SELECT * FROM d1_restore_learning_ownership)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Learning ownership differs: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_learning_ownership)
    EXCEPT (SELECT l.id,l.canonical_user_id FROM learning_signals l JOIN d1_restore_learning_ownership b ON b.id=l.id)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Learning rows missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT j.id,j.user_id FROM user_job_context j JOIN d1_restore_job_context_ownership b ON b.id=j.id)
    EXCEPT (SELECT * FROM d1_restore_job_context_ownership)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Job-context ownership differs: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_job_context_ownership)
    EXCEPT (SELECT j.id,j.user_id FROM user_job_context j JOIN d1_restore_job_context_ownership b ON b.id=j.id)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Job-context rows missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT o.* FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_restore_aliases))
    EXCEPT (SELECT * FROM d1_restore_onboarding)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Onboarding differs: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_onboarding)
    EXCEPT (SELECT o.* FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_restore_aliases))
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Onboarding rows missing: %',v; END IF;

  SELECT count(*) INTO v FROM (
    (SELECT s.* FROM rico_agent_settings s WHERE s.user_id IN (SELECT id FROM d1_restore_target))
    EXCEPT (SELECT * FROM d1_restore_agent_settings)
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Agent settings differ: %',v; END IF;
  SELECT count(*) INTO v FROM (
    (SELECT * FROM d1_restore_agent_settings)
    EXCEPT (SELECT s.* FROM rico_agent_settings s WHERE s.user_id IN (SELECT id FROM d1_restore_target))
  ) q;
  IF v<>0 THEN RAISE EXCEPTION 'Agent settings missing: %',v; END IF;
END $$;

SELECT jsonb_build_object(
  'owner_rows',(SELECT count(*) FROM rico_users u JOIN d1_restore_target t ON t.id=u.id),
  'profiles',(SELECT count(*) FROM rico_profiles p JOIN d1_restore_target t ON t.id=p.user_id),
  'chat_mapping_differences',0,
  'learning_mapping_differences',0,
  'job_mapping_differences',0,
  'onboarding',(SELECT count(*) FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_restore_aliases)),
  'onboarding_completed',(SELECT count(*) FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_restore_aliases) AND o.status='completed'),
  'onboarding_completed_at_non_null',(SELECT count(*) FROM rico_onboarding_states o WHERE lower(o.user_id) IN (SELECT alias FROM d1_restore_aliases) AND o.completed_at IS NOT NULL),
  'agent_settings',(SELECT count(*) FROM rico_agent_settings s JOIN d1_restore_target t ON t.id=s.user_id),
  'requested_commit',:'commit'
) AS d1_rollback_result;

\if :commit
  COMMIT;
\else
  ROLLBACK;
\endif
