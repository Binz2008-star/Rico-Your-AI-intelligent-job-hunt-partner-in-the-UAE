"""Behaviour pinned for the documents inventory contract.

Pure-value tests: no database, no HTTP, no repositories. Every document below
is synthetic.

The file has three parts:

1. the contract itself — what ``src.domain.documents`` guarantees;
2. adapter parity — the contract counts what the files surface counts today,
   so adopting it cannot move a user's quota numbers;
3. divergence — two places disagree today about the same user. Those are
   recorded as characterisation tests (what happens now, clearly labelled as
   observed behaviour and NOT as approved behaviour) plus one strict xfail
   stating the unified rule the CV slice has to make pass.
"""
from __future__ import annotations

import pytest

from src.domain.documents import (
    DocumentInventory,
    DocumentKind,
    DocumentOrigin,
    DocumentRecord,
    build_inventory,
    inventory_from_rows,
    legacy_cv_record,
    record_from_stored_row,
    records_from_stored_rows,
)


# ── builders (synthetic) ──────────────────────────────────────────────────

def _row(
    doc_id: str,
    doc_type: str = "cv",
    *,
    is_primary: bool = False,
    created_at: str | None = "2026-01-01T00:00:00+00:00",
    is_legacy: bool = False,
    label: str | None = None,
) -> dict:
    return {
        "id": doc_id,
        "user_id": "user-1",
        "filename": f"{doc_id}.pdf",
        "original_filename": f"{doc_id}.pdf",
        "doc_type": doc_type,
        "file_size": 1024,
        "label": label,
        "is_primary": is_primary,
        "is_legacy": is_legacy,
        "created_at": created_at,
        "updated_at": created_at,
    }


def _record(
    doc_id: str,
    kind: DocumentKind = DocumentKind.CV,
    *,
    is_primary: bool = False,
    created_at: str | None = "2026-01-01T00:00:00+00:00",
    origin: DocumentOrigin = DocumentOrigin.STORED,
) -> DocumentRecord:
    return DocumentRecord(
        document_id=doc_id,
        kind=kind,
        origin=origin,
        filename=f"{doc_id}.pdf",
        is_primary=is_primary,
        created_at=created_at,
    )


# ── 1. the contract ───────────────────────────────────────────────────────

class TestDocumentKind:
    def test_known_types_parse_to_their_kind(self):
        assert DocumentKind.parse("cv") is DocumentKind.CV
        assert DocumentKind.parse("cover_letter") is DocumentKind.COVER_LETTER
        assert DocumentKind.parse("identity_document") is DocumentKind.IDENTITY_DOCUMENT
        assert DocumentKind.parse("other") is DocumentKind.OTHER

    def test_case_and_whitespace_do_not_change_the_kind(self):
        assert DocumentKind.parse("  CV \n") is DocumentKind.CV

    def test_unknown_absent_and_empty_types_are_other_never_cv(self):
        for raw in (None, "", "   ", "resume", "passport", 7, object()):
            assert DocumentKind.parse(raw) is DocumentKind.OTHER

    def test_a_kind_parses_back_to_itself(self):
        assert DocumentKind.parse(DocumentKind.COVER_LETTER) is DocumentKind.COVER_LETTER

    def test_kind_serialises_as_the_stored_doc_type_string(self):
        assert DocumentKind.CV.value == "cv"
        assert DocumentKind.CV == "cv"


class TestActiveCv:
    def test_empty_inventory_has_no_active_cv(self):
        inventory = build_inventory([])
        assert inventory.active_cv is None
        assert inventory.has_cv is False

    def test_primary_stored_cv_wins_over_a_newer_non_primary_cv(self):
        older_primary = _record("cv-old", is_primary=True, created_at="2026-01-01T00:00:00+00:00")
        newer = _record("cv-new", created_at="2026-06-01T00:00:00+00:00")
        inventory = build_inventory([newer, older_primary])
        assert inventory.active_cv is older_primary

    def test_newest_stored_cv_wins_when_none_is_primary(self):
        older = _record("cv-old", created_at="2026-01-01T00:00:00+00:00")
        newer = _record("cv-new", created_at="2026-06-01T00:00:00+00:00")
        inventory = build_inventory([older, newer])
        assert inventory.active_cv is newer

    def test_a_stored_cv_wins_over_the_legacy_profile_projection(self):
        stored = _record("cv-stored", created_at="2026-01-01T00:00:00+00:00")
        legacy = legacy_cv_record(filename="profile.pdf")
        inventory = build_inventory([legacy, stored])
        assert inventory.active_cv is stored

    def test_legacy_projection_is_the_active_cv_when_no_cv_is_stored(self):
        legacy = legacy_cv_record(filename="profile.pdf")
        inventory = build_inventory([_record("other-1", DocumentKind.OTHER), legacy])
        assert inventory.active_cv is legacy
        assert inventory.has_cv is True

    def test_non_cv_documents_are_never_the_active_cv(self):
        inventory = build_inventory([
            _record("cover-1", DocumentKind.COVER_LETTER, is_primary=True),
            _record("id-1", DocumentKind.IDENTITY_DOCUMENT),
            _record("other-1", DocumentKind.OTHER),
        ])
        assert inventory.active_cv is None
        assert inventory.has_cv is False

    def test_an_unreadable_timestamp_does_not_hide_a_cv(self):
        broken = _record("cv-broken", created_at="not-a-timestamp")
        inventory = build_inventory([broken])
        assert inventory.active_cv is broken

    def test_caller_order_breaks_a_timestamp_tie(self):
        first = _record("cv-a", created_at="2026-01-01T00:00:00+00:00")
        second = _record("cv-b", created_at="2026-01-01T00:00:00+00:00")
        assert build_inventory([first, second]).active_cv is first
        assert build_inventory([second, first]).active_cv is second

    def test_naive_and_aware_timestamps_are_compared_not_rejected(self):
        naive_older = _record("cv-old", created_at="2026-01-01T00:00:00")
        aware_newer = _record("cv-new", created_at="2026-06-01T00:00:00+00:00")
        assert build_inventory([naive_older, aware_newer]).active_cv is aware_newer

    def test_primary_stored_cv_is_reported_separately_from_active_cv(self):
        newest = _record("cv-new", created_at="2026-06-01T00:00:00+00:00")
        inventory = build_inventory([newest])
        assert inventory.active_cv is newest
        assert inventory.primary_stored_cv is None


class TestIdentityOnly:
    def test_identity_documents_without_a_cv_are_reported(self):
        inventory = build_inventory([_record("id-1", DocumentKind.IDENTITY_DOCUMENT)])
        assert inventory.has_only_identity_documents is True

    def test_no_documents_at_all_is_not_identity_only(self):
        assert build_inventory([]).has_only_identity_documents is False

    def test_a_cv_alongside_an_identity_document_is_not_identity_only(self):
        inventory = build_inventory([
            _record("id-1", DocumentKind.IDENTITY_DOCUMENT),
            _record("cv-1"),
        ])
        assert inventory.has_only_identity_documents is False

    def test_other_documents_without_an_identity_document_are_not_identity_only(self):
        inventory = build_inventory([_record("other-1", DocumentKind.OTHER)])
        assert inventory.has_only_identity_documents is False


class TestQuotaCounts:
    def test_cv_and_non_cv_stored_rows_are_counted_apart(self):
        inventory = build_inventory([
            _record("cv-1"),
            _record("cv-2"),
            _record("cover-1", DocumentKind.COVER_LETTER),
            _record("other-1", DocumentKind.OTHER),
        ])
        counts = inventory.quota_counts
        assert (counts.cv, counts.other, counts.total) == (2, 2, 4)

    def test_the_legacy_projection_occupies_no_quota(self):
        inventory = build_inventory([legacy_cv_record(filename="profile.pdf")])
        counts = inventory.quota_counts
        assert (counts.cv, counts.other, counts.total) == (0, 0, 0)
        # …and it is still a document the user can see.
        assert inventory.has_cv is True

    def test_an_unknown_doc_type_is_counted_as_other_not_as_a_cv(self):
        inventory = inventory_from_rows([_row("doc-1", "something_new")])
        counts = inventory.quota_counts
        assert (counts.cv, counts.other) == (0, 1)


class TestRecordShape:
    def test_records_keep_the_order_they_were_given(self):
        ids = ["c", "a", "b"]
        inventory = build_inventory([_record(i) for i in ids])
        assert [r.document_id for r in inventory.records] == ids

    def test_display_name_prefers_label_then_filename_then_id(self):
        labelled = DocumentRecord("d1", DocumentKind.CV, label="My CV", filename="f.pdf")
        named = DocumentRecord("d2", DocumentKind.CV, filename="f.pdf")
        bare = DocumentRecord("d3", DocumentKind.CV)
        assert labelled.display_name == "My CV"
        assert named.display_name == "f.pdf"
        assert bare.display_name == "d3"

    def test_records_are_immutable(self):
        with pytest.raises(Exception):
            _record("cv-1").is_primary = True  # type: ignore[misc]

    def test_inventory_is_a_value(self):
        assert build_inventory([]) == DocumentInventory(records=())


# ── 2. adapter parity with the files surface ──────────────────────────────

class TestAdapterParity:
    def test_a_stored_row_maps_field_for_field(self):
        record = record_from_stored_row(
            _row("doc-1", "cover_letter", is_primary=True, label="Cover")
        )
        assert record.document_id == "doc-1"
        assert record.kind is DocumentKind.COVER_LETTER
        assert record.origin is DocumentOrigin.STORED
        assert record.filename == "doc-1.pdf"
        assert record.label == "Cover"
        assert record.is_primary is True
        assert record.created_at == "2026-01-01T00:00:00+00:00"

    def test_an_is_legacy_row_maps_to_the_profile_projection(self):
        record = record_from_stored_row(_row("profile-cv", "cv", is_legacy=True))
        assert record.origin is DocumentOrigin.PROFILE_LEGACY
        assert record.counts_against_quota is False

    def test_a_row_without_an_id_is_still_counted(self):
        row = _row("doc-1")
        row["id"] = None
        record = record_from_stored_row(row)
        assert record.document_id == ""
        assert record.counts_against_quota is True

    def test_a_row_without_created_at_maps_to_no_timestamp(self):
        record = record_from_stored_row(_row("doc-1", created_at=None))
        assert record.created_at is None

    def test_rows_map_in_order(self):
        records = records_from_stored_rows([_row("a"), _row("b")])
        assert [r.document_id for r in records] == ["a", "b"]

    @pytest.mark.parametrize(
        "rows",
        [
            [],
            [_row("cv-1", "cv", is_primary=True)],
            [_row("cv-1"), _row("cover-1", "cover_letter"), _row("other-1", "other")],
            [_row("profile-cv", "cv", is_legacy=True), _row("other-1", "other")],
            [_row("doc-1", "something_new")],
        ],
    )
    def test_quota_counts_match_the_current_files_surface_arithmetic(self, rows):
        """The counts the files list computes inline today, recomputed.

        Parity is the point: adopting the contract must not move a user's
        quota numbers. Mirrors ``list_files`` in ``src/api/routers/files.py``.
        """
        stored = [d for d in rows if not d.get("is_legacy")]
        expected_cv = sum(1 for d in stored if d.get("doc_type") == "cv")
        expected_other = sum(1 for d in stored if d.get("doc_type") != "cv")

        counts = inventory_from_rows(rows).quota_counts

        assert (counts.cv, counts.other) == (expected_cv, expected_other)


# ── 3. divergence between the surfaces ────────────────────────────────────
#
# CHARACTERISATION — the assertions below record what the code does TODAY.
# They are evidence, not an approved contract. The strict xfail after them
# states the behaviour the CV slice must deliver; when it starts passing,
# the characterisation tests above it are the ones to delete.

def _profile(cv_filename: str | None, cv_text: str | None, cv_status: str | None):
    from types import SimpleNamespace

    return SimpleNamespace(
        cv_filename=cv_filename,
        cv_text=cv_text,
        cv_status=cv_status,
        cv_extracted_at="2026-01-01T00:00:00+00:00",
        skills=[],
        years_experience=None,
        current_role=None,
    )


class TestSurfaceDivergence:
    """Two readers of the same profile CV grounding, two answers."""

    def test_characterisation_files_surface_projects_an_unsettled_profile_cv(self):
        """Observed today: the files surface needs only a filename."""
        from unittest.mock import patch

        from src.api.routers.files import build_profile_cv_record

        profile = _profile("cv.pdf", cv_text=None, cv_status="uploaded")
        with patch("src.repositories.profile_repo.get_profile", return_value=profile):
            record = build_profile_cv_record("user-1")

        assert record is not None
        assert record["doc_type"] == "cv"
        assert record["is_primary"] is True

    def test_characterisation_cv_resolution_rejects_the_same_unsettled_profile_cv(self):
        """Observed today: CV resolution also requires a settled extraction."""
        from unittest.mock import patch

        from src.services.document_resolver import resolve_user_cv

        profile = _profile("cv.pdf", cv_text=None, cv_status="uploaded")
        with patch(
            "src.services.document_resolver.get_user_documents", return_value=[]
        ):
            assert resolve_user_cv("user-1", profile) is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known divergence, owned by the CV slice: the files surface projects a "
            "profile CV from a filename alone, while CV resolution requires a "
            "settled extraction. One user, two answers. Unifying the rule is the "
            "next slice; this test is the acceptance check for it."
        ),
    )
    def test_both_surfaces_agree_on_an_unsettled_profile_cv(self):
        from unittest.mock import patch

        from src.api.routers.files import build_profile_cv_record
        from src.services.document_resolver import resolve_user_cv

        profile = _profile("cv.pdf", cv_text=None, cv_status="uploaded")

        with patch("src.repositories.profile_repo.get_profile", return_value=profile):
            files_answer = build_profile_cv_record("user-1")
        with patch(
            "src.services.document_resolver.get_user_documents", return_value=[]
        ):
            resolver_answer = resolve_user_cv("user-1", profile)

        assert (files_answer is None) == (resolver_answer is None)

    def test_characterisation_files_surface_projects_a_legacy_cv_beside_stored_cvs(self):
        """Observed today: a non-primary stored CV does not suppress the projection.

        The contract answers this case differently — see
        ``test_a_stored_cv_wins_over_the_legacy_profile_projection`` — because a
        stored CV supersedes the profile copy. Recorded here so the difference
        is visible rather than discovered later.
        """
        from src.api.routers.files import has_active_cv_document

        stored_non_primary_cv = _row("cv-1", "cv", is_primary=False)
        assert has_active_cv_document([stored_non_primary_cv]) is False

        inventory = inventory_from_rows([stored_non_primary_cv])
        assert inventory.active_cv is not None
        assert inventory.active_cv.origin is DocumentOrigin.STORED
