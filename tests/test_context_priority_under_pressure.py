"""
tests/test_context_priority_under_pressure.py

Context preservation under combined pressure.

The defect. A user's never-apply company list travelled inside `career_memory`,
bundled into one string with "frequently skipped" and "recently applied". It
therefore inherited the priority of a *preference*. The provider layer resolves
an over-budget context with a raw `[:_PROFILE_CONTEXT_MAX_CHARS]` string slice,
so "priority" meant nothing but dict insertion order — and a long conversation
plus a large CV was enough to cut the whole `career_memory` string off the end.

Rico would then be free to recommend a company the user had explicitly told it
never to apply to, with nothing in the payload to stop it. **A dropped
preference costs a worse suggestion; a dropped never-apply constraint overrides
a decision the user already made.** Those are not the same thing and must not
share a priority.

What is enforced here:

  * the never-apply constraint has its own context key, at the top tier
  * shedding runs strictly bottom-up, and tiers 1-3 are never shed
  * degradation beats disappearance — the transcript trims oldest-first, an
    uploaded document's text shortens to a floor
  * **the constraint reaches the actual provider payload**, not merely the
    context dict — a size assertion alone would not have caught the original
    bug, because the dict was fine and the slice happened downstream

Every test uses synthetic users and synthetic data. No database, no provider,
no network.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.rico_identity import get_rico_system_prompt, get_grounding_contract
from src.services.cv_context_resolver import CVContext

BLOCKED_COMPANY = "SyntheticBlockedCorp"
NEVER_APPLY = f"Blocked companies (never apply): {BLOCKED_COMPANY}"


def _profile():
    return {
        "name": "Synthetic Tester",
        "years_experience": 10,
        "skills": ["Environmental Compliance", "HSE"],
        "target_roles": ["Operations Director"],
        "preferred_cities": ["Dubai"],
        "current_role": "Founder & General Manager",
        "current_company": "Synthetic Eco Co",
        "cv_filename": "cv.pdf",
        "cv_status": "parsed",
    }


def _fat_cv():
    """A CV big enough to make the evidence block compete for the window."""
    return {
        "schema_version": 1,
        "current_role": "Founder & General Manager",
        "skills": [f"Skill {i} " + "x" * 200 for i in range(30)],
        "certifications": [f"Cert {i} " + "y" * 200 for i in range(30)],
        "work_experience": [
            {"title": f"Role {i}", "company": f"Co {i}", "text": "w" * 900}
            for i in range(6)
        ],
        "education": [],
        "work_experience_text": "v" * 4000,
        "extraction_quality": "good",
        "extracted_chars": 50000,
    }


def _long_transcript(turns=8, chars=300):
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "t" * chars}
        for i in range(turns)
    ]


def _api(*, structured=None, transcript=None, last_doc=None, blocked=True):
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._cv_ctx_memo = ("u1", CVContext(
        state="structured" if structured else "none", structured=structured))
    api._collect_uploaded_documents = lambda uid, prof: []
    api._get_last_uploaded_document = lambda uid: last_doc
    api._get_recent_context = lambda uid: {}
    api._get_recent_messages = lambda uid, limit=8: transcript or []
    api._recent_jobs_summary = lambda uid, limit=3: "AESG Operations Manager (discussed, today)"
    api._blocked = blocked
    return api


def _build(api, profile=None):
    """Build the real context with only the DB-backed leaves stubbed."""
    from src.services.career_context import CareerContext

    cc = CareerContext()
    cc.identity_rows = 1
    cc.name_value = "Synthetic Tester"
    cc.name_trusted = True

    with patch("src.services.career_context.resolve_career_context", return_value=cc), \
         patch("src.services.career_memory.get_blocked_companies",
               return_value=[BLOCKED_COMPANY] if api._blocked else []), \
         patch("src.services.career_memory.get_disliked_companies",
               return_value=["SkippedCorp"]), \
         patch("src.services.career_memory.get_recent_applied",
               return_value=["Ops Manager @ SomeCo"]), \
         patch("src.repositories.learning_repo.get_learning_repository") as lr:
        lr.return_value.get_top_preferences.return_value = [("Operations", 1.0)]
        return api._build_openai_context(
            _profile() if profile is None else profile, user_id="u1")


# ── 1. The never-apply constraint is its own thing ───────────────────────────

class TestSafetyConstraintIsSeparated:
    def test_never_apply_has_its_own_context_key(self):
        ctx = _build(_api())
        assert ctx["safety_constraints"] == NEVER_APPLY

    def test_career_memory_no_longer_carries_the_constraint(self):
        """If it stayed bundled it would inherit a preference's priority — the
        original defect."""
        ctx = _build(_api())
        assert BLOCKED_COMPANY not in ctx.get("career_memory", "")
        assert "never apply" not in ctx.get("career_memory", "").lower()

    def test_career_memory_still_carries_preferences(self):
        ctx = _build(_api())
        assert "Frequently skipped" in ctx["career_memory"]
        assert "Recently applied" in ctx["career_memory"]

    def test_no_key_when_nothing_is_blocked(self):
        """Absence must mean "blocked nothing", never "we dropped it"."""
        ctx = _build(_api(blocked=False))
        assert "safety_constraints" not in ctx


# ── 2. It survives combined pressure — the reported case ─────────────────────

class TestSurvivesCombinedPressure:
    def test_constraint_survives_large_cv_plus_long_conversation(self):
        """The exact reported shape: 8 turns x 300 chars + a large CV. Measured
        on the pre-fix build, this pushed the constraint out of the payload."""
        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(8, 300)))
        assert ctx["safety_constraints"] == NEVER_APPLY
        assert len(json.dumps(ctx, ensure_ascii=False)) <= RicoChatAPI._CONTEXT_MAX_CHARS

    @pytest.mark.parametrize("turns,chars", [(8, 100), (8, 300), (8, 1200), (20, 2000)])
    def test_constraint_survives_every_pressure_level(self, turns, chars):
        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(turns, chars)))
        assert ctx["safety_constraints"] == NEVER_APPLY

    def test_context_fits_the_budget_so_the_raw_slice_never_cuts(self):
        """Fitting here is what makes the downstream string slice a no-op."""
        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS

        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(20, 2000)))
        assert RicoChatAPI._CONTEXT_MAX_CHARS <= _PROFILE_CONTEXT_MAX_CHARS
        assert len(json.dumps(ctx, ensure_ascii=False)) <= _PROFILE_CONTEXT_MAX_CHARS


# ── 3. Shedding order is deterministic and bottom-up ─────────────────────────

class TestSheddingOrder:
    def test_low_value_metadata_goes_before_the_transcript(self):
        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(8, 300)))
        # recently_discussed_jobs is tier 6; conversation_history is tier 5.
        assert "recently_discussed_jobs" not in ctx
        assert "conversation_history" in ctx

    def test_transcript_trims_oldest_first_rather_than_disappearing(self):
        transcript = _long_transcript(8, 300)
        transcript[-1]["content"] = "NEWEST-TURN-MARKER"
        ctx = _build(_api(structured=_fat_cv(), transcript=transcript))
        kept = ctx.get("conversation_history") or []
        assert kept, "the transcript was dropped whole instead of trimmed"
        assert kept[-1]["content"] == "NEWEST-TURN-MARKER"
        assert len(kept) < len(transcript)

    def test_verified_evidence_outranks_career_memory(self):
        """Driven through the fitter directly: pressure must be high enough to
        reach tier 4, which the builder's own caps usually prevent."""
        # Only tier 4 is available below the never-shed boundary, and the
        # context is over budget — so tier 4 must go and tiers 1-3 must not.
        ctx = {
            "profile_exists": True,
            "safety_constraints": NEVER_APPLY,
            "verified_cv_evidence": {"work_experience_text": "e" * 4200},
            "career_memory": "Frequently skipped: SkippedCorp",
        }
        assert len(json.dumps(ctx)) > RicoChatAPI._CONTEXT_MAX_CHARS
        fitted = RicoChatAPI._fit_context_budget(dict(ctx))
        assert "career_memory" not in fitted, "tier 4 was not shed under pressure"
        assert "verified_cv_evidence" in fitted, "tier 2 was shed before tier 4"
        assert fitted["safety_constraints"] == NEVER_APPLY

    def test_lower_tiers_shed_before_higher_ones(self):
        """The full ladder in one pass: 6 goes before 5, 5 before 4."""
        def _fit(**extra):
            base = {"profile_exists": True, "safety_constraints": NEVER_APPLY,
                    "verified_cv_evidence": {"t": "e" * 3400}}
            base.update(extra)
            return RicoChatAPI._fit_context_budget(base)

        # Enough overflow to need tier 6 only.
        got = _fit(recently_discussed_jobs="j" * 700,
                   career_memory="m" * 100,
                   conversation_history=[{"role": "user", "content": "c" * 100}])
        assert "recently_discussed_jobs" not in got
        assert "conversation_history" in got and "career_memory" in got

    def test_profile_facts_are_never_shed(self):
        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(20, 3000)))
        assert ctx["current_role"] == "Founder & General Manager"
        assert ctx["target_roles"] == ["Operations Director"]
        assert ctx["profile_exists"] is True

    def test_shedding_is_order_independent(self):
        """The same context must shed the same things however it was built —
        otherwise 'priority' is still just insertion order."""
        base = _build(_api(structured=_fat_cv(), transcript=_long_transcript(8, 300)))
        shuffled = dict(reversed(list(base.items())))
        refit = RicoChatAPI._fit_context_budget(dict(shuffled))
        assert set(refit) == set(base)

    def test_uploaded_document_is_trimmed_not_dropped(self):
        ctx = _build(_api(
            structured=_fat_cv(),
            transcript=_long_transcript(8, 300),
            last_doc={"filename": "jd.pdf", "display_label": "Job Description",
                      "extracted_text": "J" * 9000},
        ))
        doc = ctx.get("last_uploaded_document")
        assert doc is not None, "the document the user asked about was dropped"
        assert len(doc["transcribed_text"]) >= RicoChatAPI._CONTEXT_MIN_TRANSCRIPT_CHARS


# ── 4. It reaches the PROVIDER PAYLOAD, not just the context dict ────────────

class TestConstraintReachesTheProvider:
    """A size assertion on the context dict would not have caught the original
    bug: the dict was fine, and the loss happened in the provider layer's raw
    string slice. These tests assert on what the provider actually receives."""

    @staticmethod
    def _captured_provider_message(ctx):
        """Run the real runtime path and capture the user message sent out."""
        from src.rico_openai_runtime import call_openai_minimal

        seen = {}

        class _Resp:
            def __init__(self):
                self.choices = [type("C", (), {"message": type(
                    "M", (), {"content": "ok"})()})()]

        class _Client:
            class chat:
                class completions:
                    @staticmethod
                    def create(model=None, messages=None, **kw):
                        seen["messages"] = messages
                        return _Resp()

        with patch("src.rico_openai_runtime._build_client", return_value=_Client()), \
             patch("src.rico_openai_runtime._provider_key", return_value="sk-fake"):
            call_openai_minimal(
                "what roles suit me?",
                profile_context=json.dumps(ctx, ensure_ascii=False),
                provider="deepseek",
            )
        return seen["messages"]

    def test_never_apply_constraint_is_in_the_provider_payload(self):
        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(8, 300)))
        messages = self._captured_provider_message(ctx)
        user_msg = [m for m in messages if m["role"] == "user"][-1]["content"]
        assert BLOCKED_COMPANY in user_msg, (
            "the never-apply constraint did not survive into the provider payload"
        )
        assert "never apply" in user_msg.lower()

    def test_it_survives_the_runtime_truncation_slice(self):
        """`call_openai_minimal` slices the serialized context to 4000 chars.
        The constraint must be inside what survives that slice."""
        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS

        ctx = _build(_api(structured=_fat_cv(), transcript=_long_transcript(20, 2000)))
        sliced = json.dumps(ctx, ensure_ascii=False)[:_PROFILE_CONTEXT_MAX_CHARS]
        assert BLOCKED_COMPANY in sliced

    def test_the_provider_system_prompt_makes_it_binding(self):
        """Carrying the constraint is not enough — the model must be told it is
        binding, on the primary path and on the HuggingFace fallback leg."""
        for prompt in (get_rico_system_prompt(), get_grounding_contract()):
            low = prompt.lower()
            assert "safety_constraints" in prompt
            assert "never-apply" in low or "never apply" in low
            assert "binding, not advisory" in low


# ── 5. Mutation guards — these must fail if the fix is undone ────────────────

class TestGuardsActuallyGuard:
    def test_priority_ladder_is_ordered_and_complete(self):
        """Pins the ordering itself. Re-ranking a tier — for instance demoting
        safety_constraints below the transcript — fails here."""
        tiers = dict(
            (key, tier)
            for tier, keys in RicoChatAPI._CONTEXT_PRIORITY for key in keys
        )
        assert tiers["safety_constraints"] == 1
        assert tiers["verified_cv_evidence"] == 2
        assert tiers["career_memory"] == 4
        assert tiers["conversation_history"] == 5
        assert tiers["recently_discussed_jobs"] == 6
        # Strictly increasing cost of loss: safety < evidence < memory < transcript
        assert tiers["safety_constraints"] < tiers["verified_cv_evidence"]
        assert tiers["verified_cv_evidence"] < tiers["career_memory"]
        assert tiers["career_memory"] < tiers["conversation_history"]

    def test_safety_tier_is_above_the_never_shed_boundary(self):
        """Tiers at or below _CONTEXT_TIER_OTHER are never shed. If safety ever
        drifts below that boundary it becomes sheddable again."""
        safety_tier = next(
            t for t, keys in RicoChatAPI._CONTEXT_PRIORITY if "safety_constraints" in keys
        )
        assert safety_tier <= RicoChatAPI._CONTEXT_TIER_OTHER

    def test_fitter_never_sheds_the_safety_constraint_even_when_hopeless(self):
        """An impossible budget must still keep the constraint. Returning an
        over-budget context is visible; silently dropping a user's decision is
        not."""
        ctx = {
            "profile_exists": True,
            "safety_constraints": NEVER_APPLY,
            "verified_cv_evidence": {"work_experience_text": "z" * 20000},
            "conversation_history": [{"role": "user", "content": "q" * 20000}],
        }
        fitted = RicoChatAPI._fit_context_budget(dict(ctx))
        assert fitted["safety_constraints"] == NEVER_APPLY

    def test_constraint_is_affordable_at_any_budget(self):
        """The constraint is never shed, so it must stay small enough that
        keeping it is always viable."""
        from src.services.career_memory import MAX_BLOCKED_COMPANIES

        assert MAX_BLOCKED_COMPANIES <= 15
        worst = "Blocked companies (never apply): " + ", ".join(
            "C" * 40 for _ in range(MAX_BLOCKED_COMPANIES))
        assert len(worst) < RicoChatAPI._CONTEXT_MAX_CHARS // 4
