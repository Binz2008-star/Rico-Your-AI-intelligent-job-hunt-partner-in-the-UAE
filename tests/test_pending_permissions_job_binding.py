"""
tests/test_pending_permissions_job_binding.py

Pure (no network, no DB) unit tests for the job-key binding added to the
pending-permissions store. A permission issued for a specific job must not be
consumable against a different job within the same action, while permissions
registered without a job_key keep their original job-agnostic behaviour.
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import src.services.pending_permissions as pp

_USER = "binding-test@rico.ai"


def _pid(prefix: str = "bind") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestJobBoundPermission:
    def test_matching_job_key_is_accepted_and_consumed(self):
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="job-abc")
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="job-abc") is True
        # one-time use: second attempt rejected
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="job-abc") is False

    def test_mismatched_job_key_is_rejected(self):
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="job-abc")
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="job-xyz") is False

    def test_mismatched_job_key_does_not_consume_permission(self):
        """A wrong-job probe must not burn the token — the real job can still approve."""
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="job-abc")
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="job-xyz") is False
        # legitimate job still works afterwards
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="job-abc") is True

    def test_missing_job_key_against_bound_permission_is_rejected(self):
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="job-abc")
        assert pp.validate_and_consume(pid, _USER, "apply") is False
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="") is False

    def test_user_and_action_still_enforced_on_bound_permission(self):
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="job-abc")
        # right job but wrong user
        assert pp.validate_and_consume(pid, "other@rico.ai", "apply", job_key="job-abc") is False
        # right job but wrong action
        assert pp.validate_and_consume(pid, _USER, "save", job_key="job-abc") is False


class TestUnboundPermissionBackCompat:
    def test_unbound_permission_accepts_any_job_key(self):
        """Registered without a job_key → job-agnostic (original behaviour)."""
        pid = _pid()
        pp.register(pid, _USER, "why")
        assert pp.validate_and_consume(pid, _USER, "why", job_key="anything") is True

    def test_unbound_permission_accepts_no_job_key(self):
        pid = _pid()
        pp.register(pid, _USER, "why")
        assert pp.validate_and_consume(pid, _USER, "why") is True

    def test_empty_job_key_at_registration_is_treated_as_unbound(self):
        pid = _pid()
        pp.register(pid, _USER, "apply", job_key="")
        # empty key normalises to None → job-agnostic
        assert pp.validate_and_consume(pid, _USER, "apply", job_key="whatever") is True
