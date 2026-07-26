#!/usr/bin/env python3
"""Fail when a test file exists but no workflow ever runs it.

The pytest jobs in this repository do not run ``tests/``. They run enumerated
lists of explicit paths. A list is only as complete as the last person who
remembered to append to it, and a test file nobody remembered is not a failing
test — it is an invisible one. CI goes green, the file looks like coverage in
the tree, and the invariant it was written to protect is unguarded.

That has now happened repeatedly: fail-closed invariants landed in files that
were never added to the list, and each was caught by hand, after merge. This
guard exists so the next one is caught by CI instead.

What it does
------------
Discovers every test file under ``tests/``, extracts the ``tests/...`` paths
from every pytest invocation in every workflow, and fails if a discovered file
is reachable from none of them. A directory token such as ``tests/unit/``
covers everything beneath it, which is how pytest itself treats it.

Deliberate exclusions go in the allowlist, and every entry must carry a
reason. An unexplained exclusion is how this disease comes back: it looks like
a decision and behaves like an oversight, and six months later nobody can say
which it was.

Fail-closed
-----------
Every error path exits non-zero. If the workflow directory is missing, if a
workflow cannot be read, if no pytest invocation can be found where one is
expected, or if the allowlist is malformed, this guard fails. A guard that
passes when it cannot see what it is checking is worse than no guard, because
it produces a green tick that means nothing.

This script never writes to a workflow. It reads them.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ALLOWLIST = REPO_ROOT / ".github" / "test-enumeration-allowlist.txt"

# The reason text reserved for the baseline. It may never appear in the
# allowlist: a new file must state its own reason rather than inherit this one.
BASELINE_SENTINEL = "baseline gap at main@1c13147f"

# High-water mark for the frozen baseline. It may only ever be lowered, and
# lowering it is the visible record of debt actually paid. A change that raises
# it fails the guard, so the backlog cannot quietly grow back.
BASELINE_HIGH_WATER = 213

# The frozen baseline: the exact set of test files reachable by no pytest
# invocation at main@1c13147f45365c10d518356a429f757c740f3a06, measured by
# running this guard with no exemptions at all.
#
# These are RECORDED, NOT EXCUSED. The distinction the allowlist alone could
# not express is the whole point of freezing them here: an entry in this set
# means "nobody has looked at this yet", while an entry in the allowlist means
# "somebody decided this stays out, and said why". Collapsing those two into
# one list is what turned a recorded debt into a standing permission.
#
# This set is frozen in code so a NEW file cannot join it. To exclude a new
# file you must add it to the allowlist with its own reason, in a diff a
# reviewer can see. Removing a path from here — because it is enumerated now —
# is the only edit that does not fail the guard.
FROZEN_BASELINE = frozenset((
    "tests/integration/test_chat_cv_job_workflow.py",
    "tests/integration/test_chat_routing_phase1.py",
    "tests/integration/test_cv_parse_quality_gate_postgres.py",
    "tests/integration/test_jotform_webhook_to_chat_flow.py",
    "tests/integration/test_live_chat_role_parsing_path.py",
    "tests/integration/test_operation_multiworker_postgres.py",
    "tests/integration/test_operation_ownership_postgres.py",
    "tests/test_1101_private_response_cache.py",
    "tests/test_1249_scheduled_search.py",
    "tests/test_1262_conversational.py",
    "tests/test_1336_cv_search_continuity_transcript.py",
    "tests/test_1336_state_truth_profile_confirmation.py",
    "tests/test_354_apply_link_verification.py",
    "tests/test_acknowledgement_intent.py",
    "tests/test_action_endpoint.py",
    "tests/test_admin_guard.py",
    "tests/test_admin_subscribers.py",
    "tests/test_adversarial_qa.py",
    "tests/test_agent_chat_idempotency_user_scope.py",
    "tests/test_agent_privileged_authz.py",
    "tests/test_agentic_ui_composer.py",
    "tests/test_agentic_ui_contracts.py",
    "tests/test_agentic_ui_schema.py",
    "tests/test_application_board_persistence.py",
    "tests/test_application_drafts_activation.py",
    "tests/test_application_lifecycle.py",
    "tests/test_applied_screenshot_ocr_fallback.py",
    "tests/test_apply_approval_gate.py",
    "tests/test_apply_subscription_gate.py",
    "tests/test_apply_tracking_and_freshness.py",
    "tests/test_arabic_context_retention.py",
    "tests/test_arabic_jobsearch_vs_cv_status.py",
    "tests/test_atomic_draft_decisions.py",
    "tests/test_attachment_canonical_context.py",
    "tests/test_attachment_provenance_latest_wins.py",
    "tests/test_attachment_provenance_review_corrections.py",
    "tests/test_authenticated_save_no_legacy_json.py",
    "tests/test_avatar_endpoints.py",
    "tests/test_bare_role_gate.py",
    "tests/test_billing_hardening.py",
    "tests/test_billing_mode.py",
    "tests/test_billing_ops_no_stripe.py",
    "tests/test_billing_quota_fail_open.py",
    "tests/test_bug03_source_url_fallback.py",
    "tests/test_bug04_profile_mutation.py",
    "tests/test_bug05_confirmation_loop.py",
    "tests/test_bug08_city_declaration.py",
    "tests/test_bug09_keyword_filter_bleed.py",
    "tests/test_bug10_data_quality_display.py",
    "tests/test_bug11_name_casing.py",
    "tests/test_bug12_arabic_search_locale.py",
    "tests/test_bug14_jobs_service_dedup.py",
    "tests/test_bug17_pipeline_reset.py",
    "tests/test_bug19_application_evidence.py",
    "tests/test_bug2_keyword_include_exclude.py",
    "tests/test_bulk_apply_safety.py",
    "tests/test_career_memory_production_activation.py",
    "tests/test_chat_archive_user_job_context.py",
    "tests/test_chat_bulk_archive_confirmation.py",
    "tests/test_chat_card_save_board_visibility.py",
    "tests/test_chat_history_persistence.py",
    "tests/test_chat_identity_contamination.py",
    "tests/test_chat_regression.py",
    "tests/test_chat_skip_card_action.py",
    "tests/test_chat_uploaded_documents_context.py",
    "tests/test_checkout_attribution_atomic.py",
    "tests/test_city_reject_confirmation_words.py",
    "tests/test_city_validation.py",
    "tests/test_clear_chat_history.py",
    "tests/test_continuation_intent.py",
    "tests/test_conversation_state.py",
    "tests/test_core_path_real_wrappers.py",
    "tests/test_cover_letter_generation.py",
    "tests/test_cover_letter_intent_routing.py",
    "tests/test_cover_letter_slot_extraction.py",
    "tests/test_cover_letter_writer.py",
    "tests/test_cv_activation_resync.py",
    "tests/test_cv_generate_from_profile.py",
    "tests/test_cv_generation_continuity.py",
    "tests/test_deepseek_jotform_integration.py",
    "tests/test_defect1_explicit_role_precedence.py",
    "tests/test_delete_saved_jobs_chat.py",
    "tests/test_development_supervisor_contract.py",
    "tests/test_document_action_routing.py",
    "tests/test_document_storage_quotas.py",
    "tests/test_document_upload_context.py",
    "tests/test_docx_bomb_guard.py",
    "tests/test_eligibility_filter.py",
    "tests/test_email_alert_service.py",
    "tests/test_email_notifications.py",
    "tests/test_email_verification_scanner_safe.py",
    "tests/test_employer_url_passthrough.py",
    "tests/test_engineering_review_mode.py",
    "tests/test_file_list_intent.py",
    "tests/test_files_cv_fallback_rename_upload.py",
    "tests/test_files_delete_purges_cv_grounding.py",
    "tests/test_follow_up_intent.py",
    "tests/test_followup_reminders.py",
    "tests/test_format_match_links.py",
    "tests/test_free_provider_mode.py",
    "tests/test_gmail_connector_m0.py",
    "tests/test_gmail_legacy_disabled.py",
    "tests/test_gmail_pagination_bounds.py",
    "tests/test_guest_provider_degraded.py",
    "tests/test_hardening_proxy_timing_pipeline.py",
    "tests/test_identity_email_overwrite_containment.py",
    "tests/test_identity_flow_mapper.py",
    "tests/test_import_profile_command.py",
    "tests/test_issue_135_production_verification.py",
    "tests/test_job_action_isolation.py",
    "tests/test_job_card_trust.py",
    "tests/test_job_context_foundation.py",
    "tests/test_job_doc_actions.py",
    "tests/test_job_lifecycle.py",
    "tests/test_job_providers.py",
    "tests/test_job_search_action_contract.py",
    "tests/test_job_url_validation.py",
    "tests/test_jotform_e2e.py",
    "tests/test_jsearch_client.py",
    "tests/test_jsearch_uae_wide_query.py",
    "tests/test_legacy_db_transactions.py",
    "tests/test_letter_choice_routing.py",
    "tests/test_link_verifier_dns_fail_closed.py",
    "tests/test_location_intent_fix.py",
    "tests/test_manual_application_tracking.py",
    "tests/test_match_explanation.py",
    "tests/test_me_is_owner.py",
    "tests/test_medium3_rate_limits.py",
    "tests/test_message_limit_warning.py",
    "tests/test_minimum_profile_gate.py",
    "tests/test_mission_service.py",
    "tests/test_multiuser_chat_matrix.py",
    "tests/test_mutation_confirmation_guard.py",
    "tests/test_no_text_pdf_routing.py",
    "tests/test_notification_consent_durable.py",
    "tests/test_onboarding_repo_readonly.py",
    "tests/test_onboarding_status_endpoint.py",
    "tests/test_p0_context_bugs.py",
    "tests/test_p0_job_link_trust.py",
    "tests/test_p0_mutation_trust_guard.py",
    "tests/test_paddle_webhook_body_cap.py",
    "tests/test_password_reset.py",
    "tests/test_password_reset_repo.py",
    "tests/test_pasted_cv_detection.py",
    "tests/test_pending_permissions_job_binding.py",
    "tests/test_permission_execute.py",
    "tests/test_pipeline_save_count_correctness.py",
    "tests/test_placeholder_role_filter.py",
    "tests/test_plan_copy_truth.py",
    "tests/test_profile_city_write_boundary.py",
    "tests/test_profile_context_resolver.py",
    "tests/test_profile_cv_fallback.py",
    "tests/test_profile_inline_edit.py",
    "tests/test_profile_module_rename_regression.py",
    "tests/test_profile_persistence.py",
    "tests/test_profile_query_intent.py",
    "tests/test_provider_cascade_cancellation.py",
    "tests/test_public_chat_no_profile_loop.py",
    "tests/test_public_identity.py",
    "tests/test_rate_limiting.py",
    "tests/test_response_formatting.py",
    "tests/test_rico_chat_empty_message.py",
    "tests/test_rico_chat_openai_integration.py",
    "tests/test_rico_chat_response_source.py",
    "tests/test_rico_db_connect.py",
    "tests/test_rico_hf_router.py",
    "tests/test_rico_identity.py",
    "tests/test_rico_identity_guardrails.py",
    "tests/test_rico_jotform_identity.py",
    "tests/test_rico_openai_runtime.py",
    "tests/test_rico_runtime_emergency.py",
    "tests/test_rico_webhook_security.py",
    "tests/test_role_confirmation_wiring.py",
    "tests/test_role_confirmation_yes_loop.py",
    "tests/test_role_noun_city_rejection.py",
    "tests/test_safety_document_followup_scope.py",
    "tests/test_save_card_honest_failure.py",
    "tests/test_save_city_to_profile_routing.py",
    "tests/test_saved_search_upsert_fallback.py",
    "tests/test_score_normalization.py",
    "tests/test_search_attempts_provenance.py",
    "tests/test_search_confirmation_routing.py",
    "tests/test_search_dedup.py",
    "tests/test_search_routing_location_cb.py",
    "tests/test_search_title_relevance_floor.py",
    "tests/test_security_hardening_scan.py",
    "tests/test_set_active_cv_pending_confirmation.py",
    "tests/test_smoke_scripts_no_hardcoded_credentials.py",
    "tests/test_source_quality.py",
    "tests/test_sse_done_total_encoder.py",
    "tests/test_sse_stream_headers.py",
    "tests/test_subscription_api.py",
    "tests/test_subscription_expiry.py",
    "tests/test_subscription_intent_hardening.py",
    "tests/test_target_role_evidence_guard.py",
    "tests/test_tc7_structured_tracking_text.py",
    "tests/test_telegram_audience_routing.py",
    "tests/test_telegram_demo_mode.py",
    "tests/test_telegram_inline.py",
    "tests/test_telegram_notifications.py",
    "tests/test_telegram_roster_row_decode.py",
    "tests/test_upload_document_intelligence.py",
    "tests/test_upload_size_limits.py",
    "tests/test_uploaded_image_ai_context.py",
    "tests/test_user_documents_ddl.py",
    "tests/test_user_isolation.py",
    "tests/test_user_job_context_interaction.py",
    "tests/test_user_profiles.py",
    "tests/test_users_auth.py",
    "tests/test_users_scheduler.py",
    "tests/test_whatsapp_repo_connection_close.py",
    "tests/test_whatsapp_subscription.py",
    "tests/test_zoho_mail.py",
))

# Workflows expected to contain at least one pytest invocation. If one of these
# stops invoking pytest the guard fails rather than silently measuring less:
# a workflow that quietly stopped running tests is exactly the failure mode
# this script exists to catch.
WORKFLOWS_EXPECTED_TO_RUN_TESTS = (
    "qa-tests.yml",
    "log-privacy-ratchet.yml",
)


class GuardError(Exception):
    """Raised for any condition that must fail the guard rather than pass it."""


def discover_test_files() -> list[str]:
    """Every test file pytest would collect under ``tests/``."""
    if not TESTS_DIR.is_dir():
        raise GuardError(f"tests directory not found at {TESTS_DIR}")
    found = [
        str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        for p in TESTS_DIR.glob("**/*.py")
        if p.name.startswith("test_") or p.name.endswith("_test.py")
    ]
    if not found:
        raise GuardError(
            "no test files discovered under tests/ — refusing to report "
            "'nothing unenumerated' from an empty discovery"
        )
    return sorted(found)


def _pytest_path_tokens(text: str) -> set[str]:
    """``tests/...`` tokens from every pytest invocation in one workflow.

    Only tokens inside a pytest command are taken. A path named in a comment or
    in prose is not something CI runs, and treating it as coverage would let a
    file be 'enumerated' by being mentioned.
    """
    tokens: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # A pytest invocation, or a continuation line beneath one.
        tokens.update(re.findall(r"(?<![\w/.-])(tests/[\w./-]+)", stripped))
    return tokens


def enumerated_paths() -> tuple[set[str], set[str]]:
    """(files, directories) reachable from the workflows' pytest invocations."""
    if not WORKFLOWS_DIR.is_dir():
        raise GuardError(f"workflow directory not found at {WORKFLOWS_DIR}")

    workflows = sorted(
        list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    )
    if not workflows:
        raise GuardError(f"no workflow files found in {WORKFLOWS_DIR}")

    tokens: set[str] = set()
    seen_pytest_in: set[str] = set()
    for wf in workflows:
        try:
            text = wf.read_text(encoding="utf-8")
        except OSError as exc:
            raise GuardError(f"cannot read workflow {wf.name}: {exc}") from exc
        if "pytest" in text:
            seen_pytest_in.add(wf.name)
        tokens.update(_pytest_path_tokens(text))

    for expected in WORKFLOWS_EXPECTED_TO_RUN_TESTS:
        if expected not in seen_pytest_in:
            raise GuardError(
                f"{expected} was expected to invoke pytest and does not — "
                "either it stopped running tests, or it was renamed and this "
                "guard's expectations are stale. Both must be looked at."
            )
    if not tokens:
        raise GuardError(
            "no tests/ paths found in any pytest invocation — refusing to "
            "report every file as unenumerated from a failed parse"
        )

    files = {t for t in tokens if t.endswith(".py")}
    dirs = {t.rstrip("/") + "/" for t in tokens if not t.endswith(".py")}
    return files, dirs


def read_allowlist() -> dict[str, str]:
    """``{path: reason}`` for deliberately excluded files.

    Format is one entry per line, ``path  # reason``. A blank reason fails:
    the reason is the whole point of the entry.
    """
    if not ALLOWLIST.exists():
        return {}
    try:
        raw = ALLOWLIST.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read allowlist {ALLOWLIST}: {exc}") from exc

    entries: dict[str, str] = {}
    unexplained: list[str] = []
    borrowed: list[str] = []
    for number, line in enumerate(raw.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path, _, reason = stripped.partition("#")
        path, reason = path.strip(), reason.strip()
        if not path:
            raise GuardError(f"{ALLOWLIST.name} line {number}: no path")
        if not reason:
            unexplained.append(f"{ALLOWLIST.name} line {number}: {path}")
            continue
        if BASELINE_SENTINEL in reason:
            borrowed.append(f"{ALLOWLIST.name} line {number}: {path}")
            continue
        entries[path] = reason
    if unexplained:
        raise GuardError(
            "allowlist entries without a reason — an unexplained exclusion is "
            "indistinguishable from an oversight:\n  "
            + "\n  ".join(unexplained)
        )
    if borrowed:
        raise GuardError(
            "allowlist entries reusing the frozen baseline's reason — the "
            "baseline excuse belongs to the paths measured at that commit and "
            "cannot be inherited by a new file. State why THIS file is "
            "excluded:\n  " + "\n  ".join(borrowed)
        )
    return entries


def unenumerated(
    discovered: list[str], files: set[str], dirs: set[str]
) -> list[str]:
    def covered(rel: str) -> bool:
        return rel in files or any(rel.startswith(d) for d in dirs)

    return [rel for rel in discovered if not covered(rel)]


def main() -> int:
    try:
        discovered = discover_test_files()
        files, dirs = enumerated_paths()
        allowed = read_allowlist()
        missing = unenumerated(discovered, files, dirs)
    except GuardError as exc:
        print(f"FAIL: test-enumeration guard could not complete: {exc}")
        print("\nThe guard fails closed. It does not pass when it cannot see "
              "what it is checking.")
        return 1

    missing_set = set(missing)
    baseline_remaining = sorted(FROZEN_BASELINE & missing_set)
    baseline_stale = sorted(FROZEN_BASELINE - missing_set)
    allow_stale = sorted(set(allowed) - missing_set)
    unexplained_gap = [
        rel for rel in missing if rel not in allowed and rel not in FROZEN_BASELINE
    ]

    # (c) The debt is printed on every run. A number buried in a file is a
    # number nobody reads; a number in the log is one somebody has to look at.
    print(f"discovered test files under tests/ : {len(discovered)}")
    print(f"enumerated file paths in workflows : {len(files)}")
    print(f"enumerated directory paths         : {len(dirs)}")
    print(f"reachable by no pytest invocation  : {len(missing)}")
    print(f"  frozen baseline still unrun      : {len(baseline_remaining)}"
          f"  (high-water {BASELINE_HIGH_WATER})")
    print(f"  allowlisted with a stated reason : {len(allowed)}")
    print(f"  unexplained                      : {len(unexplained_gap)}")
    print(
        f"\nDEBT: {len(baseline_remaining)} of {BASELINE_HIGH_WATER} baseline "
        "files are still run by no workflow. This number may only go down."
    )

    failures = False

    # (b) One-way ratchet. The baseline is frozen in code, so growth can only
    # happen by editing it, and editing it upward is the thing being forbidden.
    if len(FROZEN_BASELINE) > BASELINE_HIGH_WATER:
        failures = True
        print(
            f"\nFAIL: the frozen baseline holds {len(FROZEN_BASELINE)} paths "
            f"but the high-water mark is {BASELINE_HIGH_WATER}. The baseline "
            "may only shrink. A file added to it is a new gap wearing an old "
            "excuse — give it its own allowlist reason, or enumerate it."
        )

    # (d) A stale exemption is a false record of intent, so it fails rather
    # than sits. Applies to both mechanisms.
    if baseline_stale:
        failures = True
        print(
            f"\nFAIL: {len(baseline_stale)} frozen-baseline path"
            f"{'' if len(baseline_stale) == 1 else 's'} are enumerated now. "
            "Delete them from FROZEN_BASELINE and lower BASELINE_HIGH_WATER to "
            f"{len(FROZEN_BASELINE) - len(baseline_stale)} — that edit is how "
            "paid-down debt gets recorded:"
        )
        for rel in baseline_stale:
            print(f"  {rel}")

    if allow_stale:
        failures = True
        print(
            f"\nFAIL: {len(allow_stale)} allowlist entr"
            f"{'y is' if len(allow_stale) == 1 else 'ies are'} no longer "
            "needed — the file is enumerated now, so the exclusion is stale "
            "and must be removed rather than left to rot into a false record "
            "of intent:"
        )
        for rel in allow_stale:
            print(f"  {rel}")

    # A baseline path whose file no longer exists is also a false record.
    vanished = sorted(p for p in FROZEN_BASELINE if p not in set(discovered))
    if vanished:
        failures = True
        print(
            f"\nFAIL: {len(vanished)} frozen-baseline path"
            f"{'' if len(vanished) == 1 else 's'} no longer exist as test "
            "files. Delete them and lower the high-water mark:"
        )
        for rel in vanished:
            print(f"  {rel}")

    if unexplained_gap:
        failures = True
        print(
            f"\nFAIL: {len(unexplained_gap)} test file"
            f"{'' if len(unexplained_gap) == 1 else 's'} exist but no pytest "
            "invocation in any workflow runs them. A test nobody runs is not "
            "coverage:"
        )
        for rel in unexplained_gap:
            print(f"  {rel}")
        print(
            "\nAdd the path to the pytest invocation that should run it, or "
            f"add it to {ALLOWLIST.name} with a one-line reason of its own. "
            "The frozen baseline is closed — a new file cannot join it."
        )

    if failures:
        return 1
    print("\nOK: every test file under tests/ is reachable from a pytest "
          "invocation, recorded in the frozen baseline, or allowlisted with a "
          "stated reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
