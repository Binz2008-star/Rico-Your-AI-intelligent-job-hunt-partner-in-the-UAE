"""
tests/test_ai_grounding_contract.py

Phase 1 of the AI Response Reliability & Performance epic — grounding and
evidence integrity.

The production defect this pins: asked for the user's strengths, Rico replied
"Your CV filename hints at a banking background." A filename is not career
evidence. Two independent context defects produced it, and both are covered
here:

  1. METADATA ISOLATION — ``career_context.active_cv_filename`` reached the
     model as a bare, unmarked filename. The system-prompt guard was written
     about ONE named field (``uploaded_documents[].filename_untrusted``), so a
     filename under any other key was outside the stated rule. The convention is
     now "any key ending ``_untrusted`` is a bare identifier, never evidence",
     and ``test_no_unguarded_filename_key_anywhere_in_context`` enforces it
     RECURSIVELY so a future filename field cannot quietly reappear.

  2. EVIDENCE STARVATION — the payload carried ``content_available: true``
     (derived from a stored ``skills_count``, not from the payload) while
     containing no CV content whatsoever. Told it held the CV and handed none,
     the model reached for the only career-shaped string left. ``verified_cv_
     evidence`` now carries the parsed CV facts, and ``content_available`` is
     true only when that block is actually present in the SAME payload.

Product Generalization Rule: every case below uses synthetic profiles and
synthetic CV data, and the suite covers a complete profile, a profile with no
CV, a guest/public session, Arabic and English input, and unrelated target
roles — the defect is global, not a property of the account that exposed it.

No database, no AI provider, no network.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.rico_identity import get_rico_system_prompt
from src.services.cv_context_resolver import CVContext


# ── Recursive naming-convention guard ────────────────────────────────────────

#: Key-name fragments that denote a file identifier. A key containing any of
#: these is metadata about a FILE, never evidence about a PERSON, and must
#: carry the ``_untrusted`` suffix that the system prompt governs.
#:
#: "title" is deliberately ABSENT: a job title inside ``verified_cv_evidence``
#: is exactly the kind of verified career fact this work exists to deliver.
FILENAME_KEY_FRAGMENTS = (
    "filename", "file_name", "fname", "document_name", "doc_name", "label",
)


def unguarded_filename_keys(node, path="ctx"):
    """Every filename-bearing key in *node* lacking the ``_untrusted`` suffix.

    Walks dicts and lists to unlimited depth: the original defect was a
    filename NESTED one level down (``career_context.active_cv_filename``),
    which a top-level-only check would have passed.
    """
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if any(f in lowered for f in FILENAME_KEY_FRAGMENTS) and not lowered.endswith("_untrusted"):
                found.append(f"{path}.{key}")
            found.extend(unguarded_filename_keys(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(unguarded_filename_keys(value, f"{path}[{index}]"))
    return found


# ── Synthetic fixtures ───────────────────────────────────────────────────────

#: A filename that NAMES A SECTOR the profile does not support. If any inference
#: leaks from metadata, "banking" is the word that proves it.
MISLEADING_CV_FILENAME = "Old_Banking_CV_2019_final_v3.pdf"


def _complete_profile():
    """A user whose real career is environmental compliance, not banking."""
    return {
        "name": "Synthetic Tester",
        "years_experience": 10,
        "skills": ["Environmental Compliance", "HSE", "Operations Management"],
        "industries": ["Environmental Services"],
        "target_roles": ["General Manager", "Operations Director"],
        "preferred_cities": ["Dubai"],
        "current_role": "Founder & General Manager",
        "current_company": "Synthetic Eco Co",
        "visa_status": "Employment Visa",
        "cv_filename": MISLEADING_CV_FILENAME,
        "cv_status": "parsed",
    }


def _substantive_cv_structured():
    return {
        "schema_version": 1,
        # A CV parse writing a TITLE LINE into the name field is the known
        # failure the identity-name guard exists for. It must not be re-admitted
        # through the evidence block.
        "name": "Vip Relationship Manager",
        "current_role": "Founder & General Manager",
        "skills": ["Environmental Compliance", "ISO 14001", "Waste Management"],
        "certifications": ["ISO 14001 Lead Auditor", "NEBOSH IGC"],
        "languages": ["Arabic", "English"],
        # A HINT by its own schema — career_context owns the authoritative
        # figure and suppresses it on conflict.
        "years_experience_hint": 8.0,
        "work_experience": [
            {"title": "Founder & General Manager", "company": "Synthetic Eco Co",
             "start": "2015", "end": "present"},
        ],
        "work_experience_text": "Founder & General Manager, 2015-present. "
                               "Environmental compliance operations, team and client leadership.",
        "education": [],
        "extraction_quality": "good",
        "extracted_chars": 8200,
    }


def _document_entries():
    return [{
        "id": "doc-cv-1",
        "file_size": 240000,
        "filename": MISLEADING_CV_FILENAME,
        "doc_type": "cv",
        "label": MISLEADING_CV_FILENAME,
        "is_primary": True,
        "skills_count": 12,
        "years_experience": 10,
    }]


def _resolved_career_context(filename=MISLEADING_CV_FILENAME):
    """A real CareerContext with an active CV — so the filename field is
    actually POPULATED. With the store unavailable the resolver degrades and
    returns None there, which would let the isolation tests pass vacuously."""
    from src.services.career_context import CareerContext

    ctx = CareerContext()
    ctx.active_cv = {"id": "doc-cv-1", "original_filename": filename,
                     "years_experience": 10.0, "is_primary": True}
    ctx.active_cv_source = "primary"
    ctx.identity_rows = 1
    ctx.profile_years = ctx.cv_years = ctx.display_years = 10.0
    ctx.years_source = "profile"
    ctx.name_value = "Synthetic Tester"
    ctx.name_trusted = True
    return ctx


def _build_context(profile, *, structured, user_id="synthetic@example.test", documents=None):
    """Build the real LLM context with every DB reader stubbed."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    # Seed the memoised CV context so no repository/database read happens.
    api._cv_ctx_memo = (user_id, CVContext(
        state="structured" if structured else "metadata_only",
        structured=structured,
        filename=MISLEADING_CV_FILENAME,
        availability_reason="structured_available" if structured else "no_readable_content",
    ))
    api._collect_uploaded_documents = lambda uid, prof: (
        _document_entries() if documents is None else documents
    )
    api._get_last_uploaded_document = lambda uid: None
    api._get_recent_context = lambda uid: {}
    api._get_recent_messages = lambda uid, limit=8: []
    api._recent_jobs_summary = lambda uid, limit=3: ""

    entries = _document_entries() if documents is None else documents
    filename = entries[0]["filename"] if entries else MISLEADING_CV_FILENAME
    with patch("src.services.career_context.resolve_career_context",
               return_value=_resolved_career_context(filename)):
        return api._build_openai_context(profile, user_id=user_id)


# ── 1. Metadata isolation ────────────────────────────────────────────────────

class TestFilenameIsolation:
    """No filename may reach the model except under an ``_untrusted`` key."""

    def test_no_unguarded_filename_key_anywhere_in_context(self):
        """The recursive convention guard — the regression net for this epic.

        A NEW filename field added anywhere in the context, at any depth, fails
        this test until it carries the suffix the system prompt governs.
        """
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        assert unguarded_filename_keys(ctx) == []

    def test_convention_guard_actually_catches_a_violation(self):
        """The guard must fail on a real violation, or it proves nothing.

        Without this, a walker that silently returned [] would pass every case
        above while enforcing nothing.
        """
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        ctx["career_context"]["active_cv_filename"] = MISLEADING_CV_FILENAME
        assert unguarded_filename_keys(ctx) == ["ctx.career_context.active_cv_filename"]

    def test_career_context_filename_carries_untrusted_suffix(self):
        """The exact field that produced the production defect."""
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        career = ctx["career_context"]
        assert "active_cv_filename" not in career
        assert career["active_cv_filename_untrusted"] == MISLEADING_CV_FILENAME

    def test_last_uploaded_document_transcript_path_guards_filename(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(state="none"))
        api._collect_uploaded_documents = lambda uid, prof: []
        api._get_last_uploaded_document = lambda uid: {
            "filename": "offer_from_bank.pdf",
            "display_label": "Offer Letter",
            "extracted_text": "Salary: 25,000 AED per month",
        }
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""

        ctx = api._build_openai_context(None, user_id="u1")
        doc = ctx["last_uploaded_document"]
        assert "filename" not in doc
        assert doc["filename_untrusted"] == "offer_from_bank.pdf"
        assert unguarded_filename_keys(ctx) == []

    def test_metadata_only_note_does_not_restate_the_filename(self):
        """Isolating a filename under a key and then narrating it back in prose
        defeats the isolation — the note is where it reads most like a
        description of the document's contents."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(state="none"))
        api._collect_uploaded_documents = lambda uid, prof: []
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {"last_uploaded_document": {
            "document_type": "offer_letter",
            "display_label": "Offer Letter",
            "filename": "emaar_banking_offer.pdf",
            "confidence": 0.87,
        }}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""

        ctx = api._build_openai_context(None, user_id="u1")
        doc = ctx["last_uploaded_document"]
        assert doc["filename_untrusted"] == "emaar_banking_offer.pdf"
        assert "emaar_banking_offer.pdf" not in doc["note"]
        assert "Offer Letter" in doc["note"]
        assert "87%" in doc["note"]
        assert unguarded_filename_keys(ctx) == []


# ── 2. content_available truthfulness ────────────────────────────────────────

class TestContentAvailableTruthfulness:
    """``content_available`` describes THIS payload, never the stored document.

    The system prompt tells the model this flag means the CV's content is
    available to it. A true it cannot cash is what forced the filename
    inference.
    """

    def test_true_only_when_evidence_is_in_the_same_payload(self):
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        assert "verified_cv_evidence" in ctx
        assert ctx["uploaded_documents"][0]["content_available"] is True

    def test_false_when_parsed_document_has_no_readable_structured_content(self):
        """The exact production shape: cv_status='parsed', skills_count=12, and
        an empty cv_structured. Previously reported content_available=true."""
        ctx = _build_context(_complete_profile(), structured=None)
        assert "verified_cv_evidence" not in ctx
        doc = ctx["uploaded_documents"][0]
        assert doc["content_available"] is False
        # The stored document was still parsed — the two fields are independent.
        assert doc["parse_status"] == "parsed"

    def test_thin_structured_document_is_not_evidence(self):
        """Contact details are not a CV. A document that fails is_substantive
        must not flip content_available on."""
        thin = {"schema_version": 1, "name": "Someone", "skills": ["excel"]}
        ctx = _build_context(_complete_profile(), structured=thin)
        assert "verified_cv_evidence" not in ctx
        assert ctx["uploaded_documents"][0]["content_available"] is False

    def test_projection_fails_closed_by_default(self):
        """A caller that cannot prove content is in the payload may only claim
        metadata. The default must never be the optimistic one."""
        docs = RicoChatAPI._documents_for_llm(_document_entries())
        assert docs[0]["content_available"] is False
        assert docs[0]["parse_status"] == "parsed"

    def test_only_the_active_cv_can_claim_content(self):
        entries = _document_entries() + [{
            "id": "doc-cl-1", "file_size": 45000, "filename": "cover_letter.pdf",
            "doc_type": "cover_letter", "label": None, "is_primary": False,
            "skills_count": 0, "years_experience": None,
        }]
        docs = RicoChatAPI._documents_for_llm(entries, evidence_available=True)
        by_type = {d["doc_type"]: d for d in docs}
        assert by_type["cv"]["content_available"] is True
        assert by_type["cover_letter"]["content_available"] is False

    def test_zero_byte_artifact_still_excluded(self):
        """Layer 1 of the pre-existing identity guard is preserved."""
        entries = [{
            "id": "doc-empty", "file_size": 0, "filename": "Someone_Emirates_ID.pdf",
            "doc_type": "cv", "label": "Someone_Emirates_ID.pdf", "is_primary": True,
        }]
        assert RicoChatAPI._documents_for_llm(entries, evidence_available=True) == []


# ── 3. Verified evidence ─────────────────────────────────────────────────────

class TestVerifiedCvEvidence:
    """The facts that were missing: work history, certifications, real role."""

    def test_evidence_carries_the_verified_career_facts(self):
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        evidence = ctx["verified_cv_evidence"]
        assert evidence["current_role"] == "Founder & General Manager"
        assert evidence["work_experience"][0]["company"] == "Synthetic Eco Co"
        assert evidence["work_experience"][0]["start"] == "2015"
        assert "ISO 14001 Lead Auditor" in evidence["certifications"]
        assert "NEBOSH IGC" in evidence["certifications"]
        assert "environmental compliance" in evidence["work_experience_text"].lower()
        assert evidence["source"] == "parsed_cv_structured"

    def test_evidence_excludes_the_untrusted_cv_name(self):
        """CV parses write title lines into the name field. The identity-name
        guard must not be reopened through the evidence block."""
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        assert "name" not in ctx["verified_cv_evidence"]
        assert "Vip Relationship Manager" not in json.dumps(ctx, ensure_ascii=False)

    def test_evidence_excludes_the_years_hint(self):
        """career_context owns years and suppresses the figure on conflict. A
        second, unreconciled number would let the model state what the resolver
        deliberately withheld."""
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        assert "years_experience_hint" not in ctx["verified_cv_evidence"]

    def test_absent_sections_are_omitted_not_emptied(self):
        """Only evidence actually present is sent — an empty list reads as a
        verified absence the CV never established."""
        ctx = _build_context(_complete_profile(), structured=_substantive_cv_structured())
        evidence = ctx["verified_cv_evidence"]
        assert "education" not in evidence          # fixture has none
        assert "education_text" not in evidence

    def test_evidence_precedes_conversation_history(self):
        """The serialized context is truncated at 4000 chars and dict order is
        preserved, so evidence placed after the history would be cut first."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(
            state="structured", structured=_substantive_cv_structured(),
            filename=MISLEADING_CV_FILENAME, availability_reason="structured_available"))
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: [
            {"role": "user", "content": "long turn " * 200} for _ in range(8)
        ]
        api._recent_jobs_summary = lambda uid, limit=3: ""

        ctx = api._build_openai_context(_complete_profile(), user_id="u1")
        keys = list(ctx)
        assert keys.index("verified_cv_evidence") < keys.index("conversation_history")

        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS
        truncated = json.dumps(ctx, ensure_ascii=False)[:_PROFILE_CONTEXT_MAX_CHARS]
        assert "NEBOSH IGC" in truncated
        assert "parsed_cv_structured" in truncated

    def test_resolver_failure_fails_closed(self):
        """A CV read that raises must yield no evidence and no content claim —
        never an optimistic flag over content we could not read."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""
        with patch.object(RicoChatAPI, "_cv_context", side_effect=RuntimeError("store down")):
            ctx = api._build_openai_context(_complete_profile(), user_id="u1")
        assert "verified_cv_evidence" not in ctx
        assert ctx["uploaded_documents"][0]["content_available"] is False


# ── 4. Profile-state coverage (Product Generalization Rule) ──────────────────

class TestAcrossProfileStates:
    """One user's bug is the product's bug. Every state gets the same contract."""

    def test_no_profile_means_no_cv_resolver_call_at_all(self):
        """A profile row is where cv_structured lives, so a user without one
        has no evidence to find. The resolver must not be called merely to
        return None — a guest turn pays nothing for this feature."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._collect_uploaded_documents = lambda uid, prof: []
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""
        with patch.object(RicoChatAPI, "_cv_context") as resolver:
            ctx = api._build_openai_context(None, user_id="guest:abc")
        resolver.assert_not_called()
        assert "verified_cv_evidence" not in ctx

    def test_user_with_no_profile_or_cv(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(state="none"))
        api._collect_uploaded_documents = lambda uid, prof: []
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""

        ctx = api._build_openai_context(None, user_id="u1")
        assert ctx["profile_exists"] is False
        assert "verified_cv_evidence" not in ctx
        assert unguarded_filename_keys(ctx) == []

    def test_guest_public_session_has_no_user_id_context(self):
        """A guest turn passes user_id=None: no document reads, no evidence,
        and nothing to leak."""
        ctx = RicoChatAPI.__new__(RicoChatAPI)._build_openai_context(None, user_id=None)
        assert ctx == {"profile_exists": False}
        assert unguarded_filename_keys(ctx) == []

    def test_profile_with_cv_but_unrelated_target_roles(self):
        """The saved target roles must not become the evidence for strengths —
        they are an aspiration, not a career fact."""
        profile = _complete_profile()
        profile["target_roles"] = ["Data Scientist", "Chef", "Flight Attendant"]
        ctx = _build_context(profile, structured=_substantive_cv_structured())
        assert ctx["verified_cv_evidence"]["current_role"] == "Founder & General Manager"
        assert unguarded_filename_keys(ctx) == []

    @pytest.mark.parametrize("name,filename", [
        ("english", "Old_Banking_CV_2019.pdf"),
        ("arabic", "سيرة_ذاتية_مصرفية_2019.pdf"),
    ])
    def test_filename_guarded_regardless_of_script(self, name, filename):
        """An Arabic-script filename is exactly as untrusted as a Latin one."""
        profile = _complete_profile()
        profile["cv_filename"] = filename
        documents = [dict(_document_entries()[0], filename=filename, label=filename)]
        ctx = _build_context(
            profile, structured=_substantive_cv_structured(), documents=documents,
        )
        assert unguarded_filename_keys(ctx) == []
        assert ctx["uploaded_documents"][0]["filename_untrusted"] == filename


# ── 5. Prompt contract ───────────────────────────────────────────────────────

class TestSystemPromptEvidenceContract:
    """Isolating the data is half the fix; the model must be told the rule."""

    def test_untrusted_suffix_rule_is_stated_as_a_class(self):
        prompt = get_rico_system_prompt()
        assert "_untrusted" in prompt
        low = prompt.lower()
        # Governs the convention, not one hard-coded field name.
        assert "any context field whose name ends in" in low
        assert "never evidence" in low

    def test_prompt_names_the_specific_fields_that_leaked(self):
        prompt = get_rico_system_prompt()
        assert "career_context.active_cv_filename_untrusted" in prompt
        assert "last_uploaded_document.filename_untrusted" in prompt

    def test_prompt_forbids_sector_inference_from_a_filename(self):
        low = get_rico_system_prompt().lower()
        assert "banking background" in low   # the exact production fabrication
        assert "sector" in low

    def test_prompt_states_the_three_way_evidence_split(self):
        prompt = get_rico_system_prompt()
        assert "VERIFIED FACT" in prompt
        assert "GENERAL MARKET CONTEXT" in prompt
        assert "MISSING OR UNVERIFIED" in prompt

    def test_prompt_requires_naming_missing_evidence(self):
        low = get_rico_system_prompt().lower()
        assert "a stated gap is a correct answer" in low
        assert "never bridge a gap with a guess" in low

    def test_prompt_separates_parse_status_from_content_available(self):
        low = get_rico_system_prompt().lower()
        assert "answer different questions" in low
        assert "verified_cv_evidence" in low

    def test_prompt_retains_prior_identity_guardrails(self):
        """Rule 9 and the documents projection contract must survive intact."""
        prompt = get_rico_system_prompt()
        low = prompt.lower()
        assert "identity integrity" in low
        assert "emirates id" in low
        assert "ask the user" in low
        for field in ("document_id", "doc_type", "is_primary",
                      "parse_status", "content_available", "filename_untrusted"):
            assert field in prompt


# ── 6. Context budget (ported from PR #1462's bounding design) ───────────────

class TestEvidenceBudget:
    """Counting entries is not bounding them.

    The parser writes each work entry as ``{"text": <verbatim entry body>}``
    (``src/cv_parser.py``), so capping the entry COUNT while copying entry dicts
    wholesale leaves the same verbatim prose unbounded. Measured on the
    unbounded version: six entries produced 14,972 characters against a
    4,000-character budget, and an ordinary four-job CV was enough to evict
    ``career_memory`` — the blocked-companies list — from the prompt.
    """

    @staticmethod
    def _fat_structured(entries=6, entry_chars=4000):
        """A CV shaped like the parser really emits: verbatim prose per entry."""
        return {
            "schema_version": 1,
            "current_role": "Founder & General Manager",
            "skills": [f"Skill {i} " + "x" * 400 for i in range(40)],
            "certifications": [f"Cert {i} " + "y" * 400 for i in range(40)],
            "languages": [f"Lang {i} " + "z" * 400 for i in range(40)],
            "work_experience": [
                {"title": f"Role {i}", "company": f"Co {i}", "date_range": "2015-2020",
                 "text": "w" * entry_chars}
                for i in range(entries)
            ],
            "education": [
                {"institution": f"Uni {i}", "text": "e" * entry_chars} for i in range(entries)
            ],
            "work_experience_text": "v" * 6000,
            "education_text": "u" * 6000,
            "extraction_quality": "good",
            "extracted_chars": 90000,
        }

    def test_every_string_leaf_is_capped(self):
        evidence = RicoChatAPI._verified_cv_evidence(
            CVContext(state="structured", structured=self._fat_structured())
        )
        for entry in evidence.get("work_experience", []) + evidence.get("education", []):
            for key, value in entry.items():
                if isinstance(value, str):
                    assert len(value) <= RicoChatAPI._EVIDENCE_MAX_ENTRY_VALUE_CHARS, key
        for key in ("skills", "certifications", "languages"):
            for item in evidence.get(key, []):
                assert len(item) <= RicoChatAPI._EVIDENCE_MAX_ITEM_CHARS, key

    def test_worst_case_block_fits_the_budget(self):
        evidence = RicoChatAPI._verified_cv_evidence(
            CVContext(state="structured", structured=self._fat_structured())
        )
        size = len(json.dumps(evidence, ensure_ascii=False))
        assert size <= RicoChatAPI._EVIDENCE_MAX_TOTAL_CHARS, f"evidence block {size} chars"

    def test_budget_shedding_keeps_the_load_bearing_facts(self):
        """Degrade, don't collapse: identity of the current role, provenance,
        and at least the most recent entry always survive."""
        evidence = RicoChatAPI._verified_cv_evidence(
            CVContext(state="structured", structured=self._fat_structured())
        )
        assert evidence["current_role"] == "Founder & General Manager"
        assert evidence["source"] == "parsed_cv_structured"
        assert len(evidence["work_experience"]) >= 1
        assert evidence["work_experience"][0]["title"] == "Role 0"  # most recent kept

    def test_realistic_four_job_cv_leaves_room_for_later_context(self):
        """The case that actually shipped broken: four jobs at ~220 chars each.

        Everything ordered AFTER conversation_history is delivered only through
        this JSON blob, so it is what gets silently dropped — including
        career_memory, which carries "Blocked companies (never apply)".
        """
        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS

        structured = {
            "schema_version": 1,
            "current_role": "Founder & General Manager",
            "skills": ["Environmental Compliance", "ISO 14001", "Waste Management"],
            "certifications": ["ISO 14001 Lead Auditor", "NEBOSH IGC"],
            "work_experience": [
                {"title": f"Role {i}", "company": f"Company {i}",
                 "date_range": "2015-2020", "text": "d" * 220}
                for i in range(4)
            ],
            "education": [],
            "extraction_quality": "good",
            "extracted_chars": 20000,
        }
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(state="structured", structured=structured))
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: [
            {"role": "user", "content": "find me operations roles in dubai"} for _ in range(8)
        ]
        api._recent_jobs_summary = lambda uid, limit=3: "AESG Operations Manager (discussed, today)"
        with patch("src.services.career_context.resolve_career_context",
                   return_value=_resolved_career_context()), \
             patch("src.services.career_memory.build_memory_context",
                   return_value="Blocked companies (never apply): BadCorp, WorseCorp"):
            ctx = api._build_openai_context(_complete_profile(), user_id="u1")

        assert ctx["career_memory"].startswith("Blocked companies")
        truncated = json.dumps(ctx, ensure_ascii=False)[:_PROFILE_CONTEXT_MAX_CHARS]
        # The blocked-companies memory must survive the runtime truncation.
        assert "Blocked companies" in truncated
        assert "parsed_cv_structured" in truncated

    def test_large_evidence_beside_a_full_transcribed_text(self):
        """A 4000-char uploaded-document transcript is the other big consumer.

        Both can be present on the same turn; the evidence block must stay
        bounded regardless of what else is competing for the window.
        """
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(
            state="structured", structured=self._fat_structured()))
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: {
            "filename": "job_ad.pdf", "display_label": "Job Description",
            "extracted_text": "J" * 9000,
        }
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""
        with patch("src.services.career_context.resolve_career_context",
                   return_value=_resolved_career_context()):
            ctx = api._build_openai_context(_complete_profile(), user_id="u1")

        assert len(ctx["last_uploaded_document"]["transcribed_text"]) == 4000
        evidence_size = len(json.dumps(ctx["verified_cv_evidence"], ensure_ascii=False))
        assert evidence_size <= RicoChatAPI._EVIDENCE_MAX_TOTAL_CHARS
        assert unguarded_filename_keys(ctx) == []


# ── 7. Value-side filename guard (ported from PR #1462) ─────────────────────

class TestFilenameNotInStringValues:
    """The key-side walker cannot see a filename interpolated into a VALUE —
    which is literally the second half of the defect (the prose `note`)."""

    def test_filename_appears_only_under_untrusted_keys(self):
        def string_leaves(node, path="ctx", key=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield from string_leaves(v, f"{path}.{k}", str(k))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    yield from string_leaves(v, f"{path}[{i}]", key)
            elif isinstance(node, str):
                yield path, key, node

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._cv_ctx_memo = ("u1", CVContext(
            state="structured", structured=_substantive_cv_structured()))
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {"last_uploaded_document": {
            "document_type": "cv", "display_label": "CV",
            "filename": MISLEADING_CV_FILENAME, "confidence": 0.9,
        }}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""
        with patch("src.services.career_context.resolve_career_context",
                   return_value=_resolved_career_context()):
            ctx = api._build_openai_context(_complete_profile(), user_id="u1")

        offenders = [
            path for path, key, value in string_leaves(ctx)
            if MISLEADING_CV_FILENAME in value and not key.lower().endswith("_untrusted")
        ]
        assert offenders == [], f"filename leaked into free text at: {offenders}"


# ── 8. One CV resolver call per instance (ported from PR #1462) ─────────────

class TestResolverCallBudget:
    def test_repeated_context_builds_resolve_the_cv_once(self):
        """`_cv_context` is memoised per request instance. Nothing asserted it,
        so a refactor could turn one read per turn into N without failing."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._collect_uploaded_documents = lambda uid, prof: _document_entries()
        api._get_last_uploaded_document = lambda uid: None
        api._get_recent_context = lambda uid: {}
        api._get_recent_messages = lambda uid, limit=8: []
        api._recent_jobs_summary = lambda uid, limit=3: ""

        with patch("src.services.cv_context_resolver.resolve_cv_context",
                   return_value=CVContext(state="structured",
                                          structured=_substantive_cv_structured())) as resolver, \
             patch("src.services.career_context.resolve_career_context",
                   return_value=_resolved_career_context()):
            for _ in range(3):
                ctx = api._build_openai_context(_complete_profile(), user_id="u1")

        assert resolver.call_count == 1, (
            f"resolved the CV {resolver.call_count} times for one request instance"
        )
        assert "verified_cv_evidence" in ctx
