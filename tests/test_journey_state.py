"""Focused tests for journey snapshot derivation and daily-plan generation.

Pure unit tests — no I/O, no DB, no mocks, no clock. Tests are fully deterministic
and exercise only the public API.
"""
from __future__ import annotations

import inspect

import pytest
from src.agent.context.journey_state import (
    DailyActionPlan,
    JourneyState,
    STATES,
    derive_state,
    generate_daily_plan,
)


# ── State derivation ─────────────────────────────────────────────────────────

class TestDeriveState:
    def test_discovery_when_all_counts_zero(self):
        state = derive_state("u1")
        assert state.state == "discovery"
        assert state.saved_count == 0
        assert state.prepared_count == 0
        assert state.applied_count == 0
        assert state.follow_up_due_count == 0
        assert state.interviewing_count == 0
        assert state.offer_count == 0

    def test_searching_when_only_saved(self):
        assert derive_state("u1", saved_count=5).state == "searching"

    def test_prepared_only_derives_as_searching(self):
        """A user whose only active status is `prepared` must not derive as discovery."""
        state = derive_state("u1", prepared_count=3)
        assert state.state == "searching"
        assert state.prepared_count == 3

    def test_applying_when_applied_but_no_interviews(self):
        assert derive_state("u1", saved_count=5, applied_count=2).state == "applying"

    def test_follow_up_due_only_derives_as_applying(self):
        """A user whose only current status is `follow_up_due` must not derive as discovery."""
        state = derive_state("u1", follow_up_due_count=2)
        assert state.state == "applying"
        assert state.follow_up_due_count == 2

    def test_interviewing_takes_precedence_over_applied(self):
        assert derive_state("u1", saved_count=5, applied_count=3, interviewing_count=1).state == "interviewing"

    def test_interviewing_takes_precedence_over_searching(self):
        assert derive_state("u1", saved_count=10, interviewing_count=1).state == "interviewing"

    def test_applied_takes_precedence_over_searching(self):
        assert derive_state("u1", saved_count=10, applied_count=1).state == "applying"

    def test_offer_takes_precedence_over_everything(self):
        state = derive_state("u1", saved_count=5, applied_count=3, interviewing_count=2, offer_count=1)
        assert state.state == "offer"

    def test_offer_derives_from_canonical_offer_count(self):
        """`offer` maps to the canonical `offer` application status (VALID_STATUSES)."""
        assert derive_state("u1", offer_count=1).state == "offer"

    def test_user_id_preserved(self):
        assert derive_state("user-abc-123").user_id == "user-abc-123"

    def test_to_dict_roundtrip(self):
        d = derive_state("u1", saved_count=3, applied_count=1).to_dict()
        assert d == {
            "user_id": "u1",
            "state": "applying",
            "saved_count": 3,
            "prepared_count": 0,
            "applied_count": 1,
            "follow_up_due_count": 0,
            "interviewing_count": 0,
            "offer_count": 0,
        }

    def test_two_different_users_isolated(self):
        state_a = derive_state("user_a", saved_count=5)
        state_b = derive_state("user_b", saved_count=0)
        assert state_a.state == "searching"
        assert state_b.state == "discovery"
        assert state_a.user_id != state_b.user_id

    def test_deterministic_complete_object(self):
        """Same inputs produce equal complete objects — no timestamp/clock to ignore."""
        s1 = derive_state("u1", saved_count=5, prepared_count=2, applied_count=2, follow_up_due_count=1)
        s2 = derive_state("u1", saved_count=5, prepared_count=2, applied_count=2, follow_up_due_count=1)
        assert s1 == s2
        assert s1.to_dict() == s2.to_dict()

    def test_all_states_are_derivable(self):
        """Every declared journey state has a real derivation path from counts."""
        derivations = {
            "discovery": derive_state("u"),
            "searching": derive_state("u", saved_count=1),
            "applying": derive_state("u", applied_count=1),
            "interviewing": derive_state("u", interviewing_count=1),
            "offer": derive_state("u", offer_count=1),
        }
        for label, st in derivations.items():
            assert st.state == label
        assert set(derivations) == set(STATES)

    @pytest.mark.parametrize("bad_user_id", ["", "   ", None])
    def test_empty_user_id_rejected(self, bad_user_id):
        with pytest.raises(ValueError):
            derive_state(bad_user_id)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"saved_count": -1},
            {"prepared_count": -1},
            {"applied_count": -2},
            {"follow_up_due_count": -1},
            {"interviewing_count": -1},
            {"offer_count": -5},
        ],
    )
    def test_negative_counts_rejected(self, kwargs):
        with pytest.raises(ValueError):
            derive_state("u1", **kwargs)


# ── Daily plan generation ────────────────────────────────────────────────────

class TestDailyPlan:
    def test_discovery_plan_has_search_action(self):
        plan = generate_daily_plan(derive_state("u1"))
        assert plan.state == "discovery"
        assert any(a["action"] == "search" for a in plan.actions)

    def test_searching_plan_with_matches_has_review(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5), new_matches_count=3)
        assert any(a["action"] == "review_matches" for a in plan.actions)

    def test_searching_plan_with_saved_but_no_applied_or_followup_has_apply(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5, applied_count=0))
        assert any(a["action"] == "apply" for a in plan.actions)

    def test_prepared_only_plan_is_searching_not_follow_up(self):
        """A prepared-only user derives as searching and gets a non-follow-up plan."""
        plan = generate_daily_plan(derive_state("u1", prepared_count=3))
        assert plan.state == "searching"
        assert not any(a["action"] == "follow_up" for a in plan.actions)

    def test_follow_up_due_only_plan_has_follow_up_action(self):
        """A follow_up_due-only user must receive a follow-up action, not discovery/search."""
        plan = generate_daily_plan(derive_state("u1", follow_up_due_count=2))
        assert plan.state == "applying"
        assert any(a["action"] == "follow_up" for a in plan.actions)
        assert not any(a["action"] == "search" for a in plan.actions)

    def test_applying_plan_with_followups_has_follow_up(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5, applied_count=3, follow_up_due_count=2))
        assert any(a["action"] == "follow_up" for a in plan.actions)

    def test_applying_plan_with_drafts_has_review_drafts(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5, applied_count=3), drafts_ready_count=2)
        assert any(a["action"] == "review_drafts" for a in plan.actions)

    def test_interviewing_plan_has_interview_prep(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5, applied_count=3, interviewing_count=1))
        assert any(a["action"] == "interview_prep" for a in plan.actions)

    def test_interviewing_plan_with_followups_has_follow_up(self):
        plan = generate_daily_plan(
            derive_state("u1", saved_count=5, applied_count=3, interviewing_count=1, follow_up_due_count=1),
        )
        assert any(a["action"] == "follow_up" for a in plan.actions)

    def test_offer_plan_has_review_offer(self):
        plan = generate_daily_plan(derive_state("u1", offer_count=1))
        assert plan.state == "offer"
        assert any(a["action"] == "review_offer" for a in plan.actions)

    def test_all_actions_have_required_fields(self):
        plan = generate_daily_plan(
            derive_state("u1", saved_count=5, applied_count=3, interviewing_count=1),
            new_matches_count=2, drafts_ready_count=1,
        )
        for action in plan.actions:
            assert "action" in action
            assert "message" in action
            assert "priority" in action
            assert action["priority"] in {"high", "medium", "low"}

    def test_plan_to_dict_roundtrip(self):
        plan = generate_daily_plan(derive_state("u1", saved_count=5), new_matches_count=3)
        d = plan.to_dict()
        assert d["user_id"] == "u1"
        assert d["state"] == "searching"
        assert isinstance(d["actions"], list)
        assert len(d["actions"]) > 0

    def test_deterministic_for_same_inputs(self):
        state = derive_state("u1", saved_count=5, applied_count=3, follow_up_due_count=1)
        plan1 = generate_daily_plan(state, new_matches_count=2, drafts_ready_count=1)
        plan2 = generate_daily_plan(state, new_matches_count=2, drafts_ready_count=1)
        assert plan1 == plan2

    def test_plan_always_has_at_least_one_action(self):
        plan = generate_daily_plan(derive_state("u1"))
        assert len(plan.actions) >= 1


# ── Identity isolation + fail-fast validation ────────────────────────────────

class TestPlanIdentityAndValidation:
    def test_plan_is_built_for_the_state_owner(self):
        """Identity comes only from state.user_id — a plan is always the owner's."""
        plan = generate_daily_plan(derive_state("user_a", saved_count=5))
        assert plan.user_id == "user_a"

    def test_cannot_build_cross_user_plan(self):
        """Two users' states yield two owner-scoped plans; no id-override argument exists."""
        plan_a = generate_daily_plan(derive_state("user_a", saved_count=5), new_matches_count=3)
        plan_b = generate_daily_plan(derive_state("user_b"))
        assert plan_a.user_id == "user_a"
        assert plan_b.user_id == "user_b"
        assert "user_id" not in inspect.signature(generate_daily_plan).parameters

    def test_empty_user_id_rejected(self):
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="", state="discovery"))

    def test_unknown_state_rejected(self):
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="u1", state="bogus"))

    def test_negative_input_count_rejected(self):
        with pytest.raises(ValueError):
            generate_daily_plan(derive_state("u1", saved_count=5), new_matches_count=-1)

    def test_negative_follow_up_due_in_state_rejected(self):
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="u1", state="applying", follow_up_due_count=-1))

    def test_inconsistent_state_and_counts_rejected(self):
        """A state label that does not match its counts is rejected, not silently handled."""
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="u1", state="offer", offer_count=0))
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="u1", state="interviewing", saved_count=2))
        with pytest.raises(ValueError):
            generate_daily_plan(JourneyState(user_id="u1", state="applying", follow_up_due_count=0, applied_count=0))

    def test_followups_due_count_argument_removed(self):
        """The duplicate `followups_due_count` argument no longer exists."""
        assert "followups_due_count" not in inspect.signature(generate_daily_plan).parameters
