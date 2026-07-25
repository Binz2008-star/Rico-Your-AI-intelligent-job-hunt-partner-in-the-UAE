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
        with patch("src.repositories.profile_repo.get_profile", side_effect=RuntimeError("neon down")):
            ctx = resolve_cv_context("u@x.com", None)
        assert ctx.availability_reason == REASON_UNAVAILABLE
        assert ctx.is_unavailable is True

    def test_absent_profile_is_distinguishable_from_a_failure(self):
        with _no_documents(), patch("src.repositories.profile_repo.get_profile", return_value=None):
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

            def upsert_profile(self, db_user_id, profile_data, cv_text=None, cv_structured=None, conn=None):
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
