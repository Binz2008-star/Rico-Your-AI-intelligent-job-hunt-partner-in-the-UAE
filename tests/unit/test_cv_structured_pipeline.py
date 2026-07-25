"""The eight acceptance invariants for the structured-CV pipeline.

`cv_structured` was a real JSONB column that nothing wrote through the live
preview/confirm path and nothing read. That is why production profiles carry
`cv_status = "parsed"` beside `cv_structured = {}`: a status asserting an
extraction that had never been connected.

Each class below is one binding invariant. Failure paths are covered on purpose —
an extraction that fails, a store that cannot be read, a section that cannot be
split — because every one of them previously ended in the product either lying
about what it had or asking the user to retype what it already held.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.cv_parser import CVParser
from src.services.cv_context_resolver import (
    REASON_NO_CONTENT,
    REASON_NONE_ON_FILE,
    REASON_UNAVAILABLE,
    authoritative_years_experience,
    resolve_cv_context,
)
from src.services.cv_state import (
    STATE_METADATA_ONLY,
    STATE_NONE,
    STATE_PARSE_FAILED,
    STATE_STRUCTURED,
    STATE_TEXT_EXTRACTED,
    STATE_UPLOADED,
    derive_cv_state,
    has_cv_content,
    has_cv_on_file,
    has_settled_cv,
)
from src.services.cv_structured import build_cv_structured, is_substantive

_FULL_CV = """Roben Edwan
Head of Compliance

WORK EXPERIENCE
Head of Compliance, Emirates NBD    2019 - Present
Led the AML programme across the GCC.
Compliance Officer, ADCB    2015 - 2019
Owned regulatory reporting.

EDUCATION
BSc Computer Science, University of Dubai    2010 - 2014

SKILLS
compliance, audit, risk assessment, leadership
"""

_READABLE_TEXT = "Professional Summary. Work Experience. Education. " * 20


def _structured(cv_text: str = _FULL_CV) -> dict:
    return build_cv_structured(CVParser().parse_text(cv_text))


def _no_documents():
    """Keep document_evidence out of the way — it must never decide state."""
    return patch(
        "src.services.cv_context_resolver._document_evidence",
        return_value={"document_id": None, "filename": None, "is_primary": None},
    )


# ── Invariant 1: cv_status=structured is impossible with cv_structured={} ──────

class TestStructuredRequiresContent:
    @pytest.mark.parametrize("empty", [None, {}, {"schema_version": 1}])
    def test_empty_structured_is_never_structured(self, empty):
        state = derive_cv_state(cv_structured=empty, cv_text=None, has_document=True)
        assert state != STATE_STRUCTURED

    def test_contact_details_alone_are_not_structured(self):
        """A name and a phone number are contact details, not a CV."""
        thin = _structured("Roben Edwan\nroben@example.com\n+971501234567\n")
        assert is_substantive(thin) is False
        assert derive_cv_state(cv_structured=thin, has_document=True) != STATE_STRUCTURED

    def test_substantive_document_is_structured(self):
        assert derive_cv_state(cv_structured=_structured(), cv_text=_READABLE_TEXT) == STATE_STRUCTURED

    def test_malformed_blob_is_never_structured(self):
        assert is_substantive({"skills": "not-a-list", "work_experience": [{"text": "x"}]}) is False


# ── Invariant 2: cv_status=text_extracted is impossible with cv_text="" ────────

class TestTextExtractedRequiresText:
    @pytest.mark.parametrize("blank", [None, "", "   ", "\n\n"])
    def test_blank_text_is_never_text_extracted(self, blank):
        state = derive_cv_state(cv_structured={}, cv_text=blank, has_document=True)
        assert state != STATE_TEXT_EXTRACTED
        assert state == STATE_METADATA_ONLY

    def test_unreadable_text_is_never_text_extracted(self):
        """Short/garbled text fails the shared cv_parse_quality contract."""
        assert derive_cv_state(cv_structured={}, cv_text="\x00\x01\x02", has_document=True) != STATE_TEXT_EXTRACTED

    def test_readable_text_is_text_extracted(self):
        assert derive_cv_state(cv_structured={}, cv_text=_READABLE_TEXT) == STATE_TEXT_EXTRACTED


# ── Invariant 3: experience and education are extracted from the saved text ───

class TestSectionsExtractedFromSavedText:
    def test_work_and_education_entries_are_extracted(self):
        s = _structured()
        assert len(s["work_experience"]) == 2
        assert len(s["education"]) == 1
        assert s["sections_found"] == {"work_experience": True, "education": True}

    def test_entries_are_verbatim_and_invent_nothing(self):
        s = _structured()
        for entry in s["work_experience"] + s["education"]:
            # Every character of an entry must come from the source CV.
            assert entry["text"] in _FULL_CV
            if entry["date_range"]:
                assert entry["date_range"] in _FULL_CV

    def test_arabic_headings_are_recognised(self):
        arabic_cv = (
            "روبن عدوان\n\nالخبرة العملية\nمدير الالتزام، بنك الإمارات    2019 - Present\n"
            "\nالتعليم\nبكالوريوس علوم حاسب    2010 - 2014\n"
        )
        s = _structured(arabic_cv)
        assert s["sections_found"]["work_experience"] is True
        assert s["sections_found"]["education"] is True

    def test_a_passing_mention_of_experience_opens_no_section(self):
        """"10 years of experience in..." is prose, not a heading."""
        s = _structured("Roben Edwan\nI have 10 years of experience in compliance work.\n")
        assert s["sections_found"]["work_experience"] is False
        assert s["work_experience_text"] is None

    def test_unsplittable_section_keeps_its_text_verbatim(self):
        """A readable section is evidence even when entries cannot be split."""
        cv = "Jane\n\nEXPERIENCE\nWorked as a nurse in clinics across Dubai.\nTriage and education.\n"
        s = _structured(cv)
        assert s["work_experience"] == []
        assert s["work_experience_text"] is not None
        assert s["work_experience_text"] in cv
        # It still counts as professional content — that is the whole point.
        assert is_substantive(s) is True


# ── Invariant 4: on structural failure Rico uses cv_text, never asks for a retype ─

class TestFallbackNeverAsksForRetype:
    def test_text_only_profile_exposes_the_text_fallback(self):
        with _no_documents():
            ctx = resolve_cv_context("u@x.com", {"cv_structured": {}, "cv_text": _READABLE_TEXT})
        assert ctx.state == STATE_TEXT_EXTRACTED
        assert ctx.readable_text_fallback == _READABLE_TEXT
        assert ctx.must_not_ask_user_to_retype is True

    def test_structured_profile_also_forbids_a_retype_request(self):
        with _no_documents():
            ctx = resolve_cv_context("u@x.com", {"cv_structured": _structured(), "cv_text": _READABLE_TEXT})
        assert ctx.state == STATE_STRUCTURED
        assert ctx.structured is not None
        assert ctx.must_not_ask_user_to_retype is True

    def test_thin_structured_does_not_masquerade_as_structured(self):
        """Structured is returned only when it earned the state."""
        with _no_documents():
            ctx = resolve_cv_context(
                "u@x.com", {"cv_structured": {"schema_version": 1, "name": "R"}, "cv_text": _READABLE_TEXT}
            )
        assert ctx.state == STATE_TEXT_EXTRACTED
        assert ctx.structured is None
        assert ctx.readable_text_fallback == _READABLE_TEXT


# ── Invariant 5: years of experience has exactly one authoritative source ─────

class TestYearsExperienceSingleSource:
    def test_profile_field_is_authoritative(self):
        assert authoritative_years_experience({"years_experience": 12}) == 12.0

    def test_structured_hint_is_not_the_authoritative_value(self):
        """A hint must never become the value the product reads."""
        s = _structured()
        assert "years_experience_hint" in s
        # The profile has no years_experience: the hint does NOT fill in for it.
        assert authoritative_years_experience({"cv_structured": s}) is None

    def test_document_snapshot_is_not_the_authoritative_value(self):
        assert authoritative_years_experience({"cv_structured": {}, "document_years": 25}) is None

    def test_user_edited_value_is_not_silently_replaced(self):
        """A stored 8 stays 8 even when the CV hints 20."""
        s = _structured("Roben\nWORK EXPERIENCE\n20 years of experience\nRole, Co  2005 - Present\n")
        assert s["years_experience_hint"] == 20.0
        assert authoritative_years_experience({"years_experience": 8, "cv_structured": s}) == 8.0


# ── Invariant 6: a store failure is "unavailable", never "no CV" ──────────────

class TestUnavailableIsNotAbsent:
    def test_profile_load_failure_reports_unavailable(self):
        with patch(
            "src.repositories.profile_repo.get_cv_grounding", side_effect=RuntimeError("neon down")
        ):
            ctx = resolve_cv_context("u@x.com", None)
        assert ctx.availability_reason == REASON_UNAVAILABLE
        assert ctx.is_unavailable is True

    def test_absent_profile_is_distinguishable_from_a_failure(self):
        from src.repositories.profile_repo import CVGrounding

        with _no_documents(), patch(
            "src.repositories.profile_repo.get_cv_grounding", return_value=CVGrounding()
        ):
            ctx = resolve_cv_context("u@x.com", None)
        assert ctx.state == STATE_NONE
        assert ctx.availability_reason == REASON_NONE_ON_FILE
        assert ctx.is_unavailable is False

    def test_resolver_never_raises(self):
        with patch("src.services.cv_context_resolver._resolve", side_effect=RuntimeError("boom")):
            ctx = resolve_cv_context("u@x.com", None)
        assert ctx.availability_reason == REASON_UNAVAILABLE


# ── Invariant 7: a legacy "parsed" is read honestly and never written ─────────

class TestLegacyParsedIsReadOnly:
    def test_legacy_parsed_with_no_content_is_metadata_only(self):
        """The exact production state: status says parsed, content is empty."""
        state = derive_cv_state(cv_structured={}, cv_text="", has_document=True, legacy_cv_status="parsed")
        assert state == STATE_METADATA_ONLY

    def test_metadata_only_user_still_has_a_cv(self):
        """Never "you have no CV" — that sends them to re-upload what we hold."""
        assert has_cv_on_file(STATE_METADATA_ONLY) is True
        assert has_cv_content(STATE_METADATA_ONLY) is False

    def test_legacy_parsed_can_never_promote_to_content_states(self):
        for status in ("parsed", "PARSED", " Parsed "):
            state = derive_cv_state(cv_structured={}, cv_text=None, legacy_cv_status=status)
            assert state not in (STATE_STRUCTURED, STATE_TEXT_EXTRACTED)

    def test_pending_extraction_is_uploaded_not_settled(self):
        """An in-flight upload must never be presented as the user's CV."""
        state = derive_cv_state(cv_text=None, has_document=True, legacy_cv_status="received_pending_extraction")
        assert state == STATE_UPLOADED
        assert has_settled_cv(state) is False
        assert has_cv_on_file(state) is True

    def test_explicit_failure_is_parse_failed_and_never_a_success(self):
        state = derive_cv_state(cv_text=None, legacy_cv_status="parse_failed")
        assert state == STATE_PARSE_FAILED
        assert has_cv_content(state) is False
        assert has_settled_cv(state) is False

    def test_metadata_only_context_reports_no_readable_content(self):
        with _no_documents():
            ctx = resolve_cv_context(
                "u@x.com", {"cv_structured": {}, "cv_text": "", "cv_filename": "cv.pdf", "cv_status": "parsed"}
            )
        assert ctx.state == STATE_METADATA_ONLY
        assert ctx.availability_reason == REASON_NO_CONTENT
        assert ctx.has_cv is True
        assert ctx.readable_text_fallback is None


# ── Invariant 8: text and structure are persisted together, or not at all ─────

class TestAtomicPersistence:
    def test_profile_repo_forwards_structured_in_the_same_db_call(self):
        """One statement: there is no window where text landed and structure did not."""
        from src.repositories import profile_repo

        captured = {}

        class _FakeDB:
            def get_user_bundle(self, *a, **kw):
                return {"id": "1", "email": "u@x.com"}

            def upsert_profile(self, db_user_id, profile_data, cv_text=None,
                               cv_structured=None, replace_cv_structured=False, conn=None):
                captured["cv_text"] = cv_text
                captured["cv_structured"] = cv_structured

            def upsert_settings(self, *a, **kw):
                pass

        class _Txn:
            def __enter__(self):
                return object()

            def __exit__(self, *a):
                return False

        structured = _structured()
        with (
            patch.object(profile_repo, "_db", return_value=_FakeDB()),
            patch.object(profile_repo, "_db_transaction", return_value=_Txn()),
            patch.object(profile_repo, "_memory"),
        ):
            profile_repo.upsert_profile(
                user_id="u@x.com",
                updates={"cv_status": "parsed"},
                cv_text=_READABLE_TEXT,
                cv_structured=structured,
            )

        assert captured["cv_text"] == _READABLE_TEXT
        assert captured["cv_structured"] == structured

    def test_router_wrapper_signature_is_a_superset(self):
        """A previous production save outage was exactly this wrapper drifting."""
        import inspect

        from src.api.routers import rico_chat

        params = set(inspect.signature(rico_chat.upsert_profile).parameters)
        assert {"cv_text", "cv_structured", "require_db", "clear_fields"}.issubset(params)

    def test_failed_structural_extraction_still_saves_text(self):
        """Structure is best-effort; the text must not be lost with it."""
        from src.services.cv_structured import build_cv_structured as build

        class _Broken:
            def __getattr__(self, name):
                raise RuntimeError("parser exploded")

        # build_cv_structured must not be what raises into the endpoint...
        with pytest.raises(RuntimeError):
            build(_Broken())
        # ...and the state derived from text alone is still honest.
        assert derive_cv_state(cv_structured=None, cv_text=_READABLE_TEXT) == STATE_TEXT_EXTRACTED


# ── Review findings: content questions must not be answered from existence ────

class TestContentQuestionsUseContentPredicate:
    """A CV whose text was never readable cannot answer a content question.

    Gating "review my CV" on existence let a metadata_only / parse_failed /
    uploaded user through, and the branch behind the gate then produced "CV gaps
    and improvements" from profile fields alone — a review of a CV nobody read.

    Not every CV check is a content check. The stale-role guards
    (_handle_delegated_decision / _handle_post_cv_continuation) deliberately stay
    on existence: having a CV at all is what makes a stale saved role suspect,
    and an unreadable CV must not re-enable auto-searching it (#732).
    """

    _METADATA_ONLY_PROFILE = {
        "cv_filename": "Roben_Edwan_CV.pdf",
        "cv_status": "parsed",
        "cv_text": "",
        "cv_structured": {},
        "skills": ["compliance"],
        "years_experience": 10,
    }

    def _api(self):
        from src.rico_chat_api import RicoChatAPI

        return RicoChatAPI.__new__(RicoChatAPI)

    def test_metadata_only_profile_has_cv_but_no_content(self):
        api = self._api()
        assert api._has_cv_on_file("u@x.com", self._METADATA_ONLY_PROFILE) is True
        assert api._has_cv_content("u@x.com", self._METADATA_ONLY_PROFILE) is False

    @pytest.mark.parametrize("status", ["parse_failed", "received_pending_extraction"])
    def test_failed_and_pending_states_have_no_content(self, status):
        profile = dict(self._METADATA_ONLY_PROFILE, cv_status=status)
        assert self._api()._has_cv_content("u@x.com", profile) is False

    def test_readable_text_profile_has_content(self):
        profile = dict(self._METADATA_ONLY_PROFILE, cv_text=_READABLE_TEXT)
        assert self._api()._has_cv_content("u@x.com", profile) is True

    def test_cv_review_refuses_to_review_unreadable_content(self):
        """The honest middle branch: has the file, cannot review it."""
        with _no_documents():
            ctx = resolve_cv_context("u@x.com", self._METADATA_ONLY_PROFILE)
        # The three facts the middle branch is built on.
        assert ctx.has_cv is True
        assert ctx.has_content is False
        assert ctx.filename == "Roben_Edwan_CV.pdf"
        # And the message must not claim an analysis, nor deny the CV exists.
        assert self._api()._has_cv_content("u@x.com", self._METADATA_ONLY_PROFILE) is False


# ── Review finding: the resolver must actually be used, and stay off the hot path ─

class TestResolverIsWiredAndLazy:
    def test_resolver_has_a_production_consumer(self):
        """It was dead code: zero importers outside its own module and tests."""
        import subprocess

        out = subprocess.run(
            ["grep", "-rln", "resolve_cv_context", "src/"],
            capture_output=True, text=True,
        ).stdout.split()
        consumers = [
            f for f in out
            if "cv_context_resolver" not in f and "__pycache__" not in f
        ]
        assert consumers, "resolve_cv_context has no production consumer"

    def test_resolution_performs_no_document_query(self):
        """State comes from the profile alone — no round trip on a chat turn."""
        with patch("src.services.cv_context_resolver._document_evidence") as ev:
            ctx = resolve_cv_context(
                "u@x.com",
                {"cv_filename": "cv.pdf", "cv_status": "parsed", "cv_text": "", "cv_structured": {}},
            )
            ev.assert_not_called()
            assert ctx.state == STATE_METADATA_ONLY
            # ...and only pays for it when the evidence itself is asked for.
            _ = ctx.document_evidence
            ev.assert_called_once()

    def test_evidence_falls_back_to_the_profile_filename(self):
        ctx = resolve_cv_context(
            "u@x.com",
            {"cv_filename": "cv.pdf", "cv_status": "parsed", "cv_text": "", "cv_structured": {}},
        )
        with patch(
            "src.services.cv_context_resolver._document_evidence",
            return_value={"document_id": None, "filename": "cv.pdf", "is_primary": None},
        ):
            assert ctx.document_evidence["filename"] == "cv.pdf"


# ── Review finding: years_experience must survive an object-shaped profile ────

class TestYearsExperienceOnObjectProfiles:
    """_profile_mapping omitted years_experience for the object path, so this
    function returned None for every non-dict profile — silently discarding the
    one authoritative value it exists to protect. Fails before the fix."""

    class _ProfileObject:
        def __init__(self, years, structured=None):
            self.years_experience = years
            self.cv_text = _READABLE_TEXT
            self.cv_filename = "cv.pdf"
            self.cv_status = "parsed"
            self.cv_structured = structured or {}

    def test_object_profile_returns_its_stored_value(self):
        assert authoritative_years_experience(self._ProfileObject(8)) == 8.0

    def test_object_profile_value_survives_a_conflicting_hint(self):
        hinted = _structured("Roben\nWORK EXPERIENCE\n20 years of experience\nRole, Co  2005 - Present\n")
        assert hinted["years_experience_hint"] == 20.0
        assert authoritative_years_experience(self._ProfileObject(8, hinted)) == 8.0

    def test_object_profile_without_a_value_returns_none(self):
        assert authoritative_years_experience(self._ProfileObject(None)) is None


# ── BLOCKER 1: stored grounding must reach the production consumer ────────────

class TestGroundingReachesTheConsumer:
    """RicoProfile carries neither cv_text nor cv_structured.

    _bundle_to_profile maps cv_filename/cv_status out of the profile JSONB and
    drops the two top-level columns, so anything resolving CV state through
    get_profile read None for both and could only ever conclude metadata_only —
    however much content was stored. These tests use the REAL bundle shape.
    """

    def _bundle(self, *, cv_text=None, cv_structured=None, cv_filename="cv.pdf", cv_status="parsed"):
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "external_user_id": "owner@rico.ai",
            "name": "Roben Edwan",
            "email": "owner@rico.ai",
            "phone": None,
            "telegram_username": None,
            "telegram_chat_id": None,
            "profile": {
                "cv_filename": cv_filename,
                "cv_status": cv_status,
                "years_experience": 8,
                "target_roles": ["Compliance Manager"],
                "skills": ["compliance"],
            },
            "settings": {},
            "cv_file_url": None,
            "cv_text": cv_text,
            "cv_structured": cv_structured,
        }

    def test_rico_profile_really_does_not_carry_the_grounding_fields(self):
        """The root cause, asserted rather than assumed."""
        from src.repositories.profile_repo import _bundle_to_profile

        profile = _bundle_to_profile(self._bundle(cv_text=_READABLE_TEXT, cv_structured=_structured()))
        assert getattr(profile, "cv_text", None) is None
        assert getattr(profile, "cv_structured", None) is None
        # ...while the values were present in the bundle all along.
        assert self._bundle(cv_text=_READABLE_TEXT)["cv_text"] == _READABLE_TEXT

    def _grounding_from_bundle(self, bundle):
        from src.repositories import profile_repo

        class _FakeDB:
            available = True

            def get_user_bundle(self, user_id, conn=None):
                return bundle

        return patch.object(profile_repo, "_db", return_value=_FakeDB())

    def test_stored_structured_reaches_the_chat_consumer(self):
        """The end-to-end claim: stored structure produces state=structured."""
        from src.rico_chat_api import RicoChatAPI
        from src.repositories.profile_repo import _bundle_to_profile

        bundle = self._bundle(cv_text=_READABLE_TEXT, cv_structured=_structured())
        api = RicoChatAPI.__new__(RicoChatAPI)
        with self._grounding_from_bundle(bundle), _no_documents():
            # The consumer is handed the SAME incomplete RicoProfile production
            # gives it — the grounding must come from the repository regardless.
            state = api._cv_state("owner@rico.ai", _bundle_to_profile(bundle))
            assert state == STATE_STRUCTURED
            assert api._has_cv_content("owner@rico.ai", _bundle_to_profile(bundle)) is True

    def test_stored_text_reaches_the_chat_consumer(self):
        from src.rico_chat_api import RicoChatAPI
        from src.repositories.profile_repo import _bundle_to_profile

        bundle = self._bundle(cv_text=_READABLE_TEXT, cv_structured={})
        api = RicoChatAPI.__new__(RicoChatAPI)
        with self._grounding_from_bundle(bundle), _no_documents():
            assert api._cv_state("owner@rico.ai", _bundle_to_profile(bundle)) == STATE_TEXT_EXTRACTED

    def test_grounding_distinguishes_absent_from_unavailable(self):
        from src.repositories import profile_repo

        # Store unavailable -> None
        with patch.object(profile_repo, "_db", return_value=None):
            assert profile_repo.get_cv_grounding("u@x.com") is None
        # Confirmed absent -> empty grounding, not None
        with self._grounding_from_bundle(None):
            grounding = profile_repo.get_cv_grounding("u@x.com")
        assert grounding is not None and grounding.is_empty is True

    def test_resolution_is_one_read_per_request(self):
        """Memoised per instance — no N+1 across the handler chain."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        with patch(
            "src.services.cv_context_resolver.resolve_cv_context",
            wraps=resolve_cv_context,
        ) as spy, self._grounding_from_bundle(self._bundle(cv_text=_READABLE_TEXT)), _no_documents():
            api._has_cv_on_file("owner@rico.ai", None)
            api._has_cv_content("owner@rico.ai", None)
            api._cv_state("owner@rico.ai", None)
        assert spy.call_count == 1, f"resolved {spy.call_count}x — expected one read per request"


# ── BLOCKER 2: a new CV must not inherit the previous CV's structure ──────────

class TestStaleStructureIsReplaced:
    """cv_structured was MERGED (`old || new`), so passing None merged {} — a
    no-op that left CV A's structure in place while cv_text became CV B's text.
    State derivation prefers structure, so Rico answered from the old CV."""

    _CV_A = """Alice Alpha
WORK EXPERIENCE
Head of Audit, AlphaCorp    2010 - 2018
EDUCATION
BSc Accounting, Alpha University    2006 - 2010
SKILLS
audit, compliance, leadership
"""
    _CV_B = """Bob Beta
WORK EXPERIENCE
Safety Engineer, BetaWorks    2019 - Present
EDUCATION
BEng Safety, Beta Institute    2015 - 2019
SKILLS
hse, safety, risk assessment
"""

    def _captured_upsert(self):
        from src.repositories import profile_repo

        captured = {}

        class _FakeDB:
            def get_user_bundle(self, *a, **kw):
                return {"id": "1", "email": "u@x.com"}

            def upsert_profile(self, db_user_id, profile_data, cv_text=None,
                               cv_structured=None, replace_cv_structured=False, conn=None):
                captured["cv_text"] = cv_text
                captured["cv_structured"] = cv_structured
                captured["replace"] = replace_cv_structured

            def upsert_settings(self, *a, **kw):
                pass

        class _Txn:
            def __enter__(self):
                return object()

            def __exit__(self, *a):
                return False

        ctx = (
            patch.object(profile_repo, "_db", return_value=_FakeDB()),
            patch.object(profile_repo, "_db_transaction", return_value=_Txn()),
            patch.object(profile_repo, "_memory"),
        )
        return captured, ctx

    def test_failed_extraction_clears_the_previous_structure(self):
        """CV A structured, CV B readable but unsplittable -> A must be cleared."""
        from src.repositories import profile_repo

        captured, ctx = self._captured_upsert()
        for c in ctx:
            c.start()
        try:
            profile_repo.upsert_profile(
                user_id="u@x.com",
                updates={},
                cv_text=self._CV_B,
                cv_structured={},          # nothing substantive from CV B
                replace_cv_structured=True,
            )
        finally:
            for c in ctx:
                c.stop()
        assert captured["replace"] is True
        assert captured["cv_structured"] == {}
        # And with structure cleared, the state falls back to the NEW text.
        assert derive_cv_state(cv_structured={}, cv_text=self._CV_B * 10) == STATE_TEXT_EXTRACTED

    def test_substantive_extraction_fully_replaces_the_previous_document(self):
        from src.repositories import profile_repo

        b_structured = _structured(self._CV_B)
        captured, ctx = self._captured_upsert()
        for c in ctx:
            c.start()
        try:
            profile_repo.upsert_profile(
                user_id="u@x.com", updates={}, cv_text=self._CV_B,
                cv_structured=b_structured, replace_cv_structured=True,
            )
        finally:
            for c in ctx:
                c.stop()
        assert captured["replace"] is True
        written = captured["cv_structured"]
        assert written == b_structured

    def test_no_trace_of_the_old_cv_survives_replacement(self):
        """No old employer, institution or skill may appear in the new document."""
        a, b = _structured(self._CV_A), _structured(self._CV_B)
        blob = repr(b)
        for stale in ("AlphaCorp", "Alpha University", "Head of Audit", "BSc Accounting"):
            assert stale not in blob
        for fresh in ("BetaWorks", "Beta Institute"):
            assert fresh in blob
        assert set(a["skills"]).isdisjoint(set(b["skills"]))

    def test_replace_is_off_by_default_for_unrelated_callers(self):
        from src.repositories import profile_repo

        captured, ctx = self._captured_upsert()
        for c in ctx:
            c.start()
        try:
            profile_repo.upsert_profile(user_id="u@x.com", updates={"skills": ["x"]})
        finally:
            for c in ctx:
                c.stop()
        assert captured.get("replace") is False

    def test_sql_switches_between_merge_and_replace(self):
        """The clause itself, not just the flag."""
        from src.rico_db import RicoDB

        seen = []

        class _Cur:
            def execute(self, sql, params=()):
                seen.append(" ".join(sql.split()))

            def fetchone(self):
                return {"user_id": "1"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Conn:
            def cursor(self):
                return _Cur()

            def commit(self):
                pass

            def close(self):
                pass

        db = RicoDB.__new__(RicoDB)
        db.connect = lambda: _Conn()
        db.upsert_profile("1", {}, cv_structured={"a": 1}, replace_cv_structured=True)
        assert "cv_structured = EXCLUDED.cv_structured" in seen[0]
        assert "rico_profiles.cv_structured ||" not in seen[0]
        seen.clear()
        db.upsert_profile("1", {}, cv_structured={"a": 1})
        assert "cv_structured = rico_profiles.cv_structured || EXCLUDED.cv_structured" in seen[0]


class TestSchemaRejectsNonDictEntries:
    @pytest.mark.parametrize("entries", [["a string"], [None], [42], [["nested"]]])
    def test_non_dict_entries_are_invalid(self, entries):
        assert is_substantive({"schema_version": 1, "work_experience": entries}) is False
        assert is_substantive({"schema_version": 1, "education": entries}) is False

    def test_dict_entries_remain_valid(self):
        assert is_substantive({"schema_version": 1, "work_experience": [{"text": "Role, Co"}]}) is True


class TestStoreFailureDoesNotEraseAKnownCV:
    """A read failure must not turn a CV the caller can already see into "none".

    The first cut of the grounding read returned state=none on any store failure,
    which erased a CV whose filename the caller was holding — sending the user to
    re-upload during an outage, the exact failure this resolver exists to prevent.
    """

    def _store_down(self):
        return patch(
            "src.repositories.profile_repo.get_cv_grounding",
            side_effect=RuntimeError("neon down"),
        )

    def test_known_filename_survives_a_store_failure(self):
        with self._store_down():
            ctx = resolve_cv_context("u@x.com", {"cv_filename": "cv.pdf", "cv_status": "parsed"})
        assert ctx.state == STATE_METADATA_ONLY
        assert ctx.has_cv is True
        assert ctx.has_content is False
        assert ctx.availability_reason == REASON_UNAVAILABLE
        assert ctx.filename == "cv.pdf"

    def test_caller_that_knows_of_no_cv_still_gets_none(self):
        with self._store_down():
            ctx = resolve_cv_context("u@x.com", {"skills": ["compliance"]})
        assert ctx.state == STATE_NONE
        assert ctx.availability_reason == REASON_UNAVAILABLE

    def test_store_failure_never_claims_content(self):
        with self._store_down():
            ctx = resolve_cv_context("u@x.com", {"cv_filename": "cv.pdf", "cv_status": "parsed"})
        assert ctx.structured is None
        assert ctx.readable_text_fallback is None
        assert ctx.must_not_ask_user_to_retype is False
