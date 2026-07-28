"""My Files must not render an unreadable document store as an empty account.

``GET /api/v1/user/files`` answers a question about stored user data, so it is
bound by the Journey-1 D3 invariant generalised in ``AI_WORKSPACE/ARCHITECTURE.md``:

    READ FAILURE != VERIFIED ABSENCE.

Today the route collapses both of these into ``{"files": [], "total": 0}``:

* the document store is marked unavailable, so no read happened at all;
* a successful, authoritative read proving the account holds nothing.

Only the second is evidence. The first is the absence of evidence, and rendering
it as an empty inventory is what makes the product tell a user their files are
gone during an outage — and then invite them to upload their "first" CV.

These tests pin the four states apart. Hermetic: the router function is called
directly with its collaborators patched, so no database, network or account is
involved, and the assertions are about the response contract itself rather than
about any transport detail.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers import files as files_router


USER_EMAIL = "u@test"

STORED_DOCS = [
    {
        "id": "doc-1",
        "user_id": USER_EMAIL,
        "filename": "Roudain Mosleh 2026.pdf",
        "original_filename": "Roudain Mosleh 2026.pdf",
        "doc_type": "cv",
        "file_size": 1024,
        "is_primary": True,
    },
]


def _plan_stub() -> SimpleNamespace:
    """A faithful plan/entitlement stub.

    The route resolves the plan to attach quota to the response. Stubbing it
    keeps these tests about the inventory contract instead of about billing.
    """
    return SimpleNamespace(
        subscription=SimpleNamespace(
            plan=SimpleNamespace(value="free"),
            entitlements=SimpleNamespace(cv_storage_limit=1, other_document_limit=3),
        )
    )


class _Db:
    """A document store whose availability and read behaviour are chosen per test."""

    def __init__(self, *, available: bool, docs=None, raises: Exception | None = None):
        self.available = available
        self._docs = docs if docs is not None else []
        self._raises = raises
        self.read_calls = 0

    def list_user_documents(self, user_id: str):
        self.read_calls += 1
        if self._raises is not None:
            raise self._raises
        return list(self._docs)


@pytest.fixture
def call_list_files(monkeypatch):
    """Call ``list_files`` with a chosen store, everything else neutralised."""

    def _call(db: _Db, *, profile_cv=None):
        monkeypatch.setattr(files_router, "_db", db)
        monkeypatch.setattr(
            files_router, "get_current_user", lambda _request: {"email": USER_EMAIL}
        )
        monkeypatch.setattr(
            files_router, "build_profile_cv_record", lambda _uid: profile_cv
        )
        monkeypatch.setattr(
            files_router, "resolve_effective_user_plan", lambda _uid: _plan_stub()
        )
        return files_router.list_files(SimpleNamespace())

    return _call


def _detail_of(exc_info) -> dict:
    detail = exc_info.value.detail
    assert isinstance(detail, dict), f"expected a machine-readable body, got {detail!r}"
    return detail


# ── 1. Unavailable store ─────────────────────────────────────────────────────

class TestUnavailableStoreIsNotAnEmptyInventory:

    def test_store_marked_unavailable_is_not_a_successful_empty_inventory(
        self, call_list_files
    ):
        db = _Db(available=False)
        with pytest.raises(HTTPException) as exc_info:
            call_list_files(db)

        assert exc_info.value.status_code == 503
        detail = _detail_of(exc_info)
        assert detail["type"] == "files_unavailable"
        assert detail["state"] == "unavailable"
        assert detail["retryable"] is True
        # No read was attempted, so there is nothing to report about the account.
        assert db.read_calls == 0

    def test_store_read_exception_is_not_a_successful_empty_inventory(
        self, call_list_files
    ):
        db = _Db(available=True, raises=RuntimeError("connection pool exhausted"))
        with pytest.raises(HTTPException) as exc_info:
            call_list_files(db)

        assert exc_info.value.status_code == 503
        detail = _detail_of(exc_info)
        assert detail["type"] == "files_unavailable"
        assert detail["state"] == "unavailable"
        assert detail["retryable"] is True
        assert db.read_calls == 1

    def test_unavailable_body_never_carries_an_inventory_claim(self, call_list_files):
        """The body must not contain the very fields that state what the user has.

        A ``files``/``total`` pair in an error body is the same lie one layer
        down: a client that reads it defensively would render absence again.
        """
        for db in (
            _Db(available=False),
            _Db(available=True, raises=RuntimeError("boom")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                call_list_files(db)
            detail = _detail_of(exc_info)
            assert "files" not in detail
            assert "total" not in detail

    def test_unavailable_body_leaks_nothing_about_the_user_or_the_failure(
        self, call_list_files
    ):
        """No exception text, provider detail, identifiers or filenames."""
        secret = "postgres://rico:hunter2@db.internal:5432/rico"
        db = _Db(
            available=True,
            raises=RuntimeError(f"could not connect to {secret} for {USER_EMAIL}"),
        )
        with pytest.raises(HTTPException) as exc_info:
            call_list_files(db)

        rendered = repr(_detail_of(exc_info))
        for leak in (secret, "hunter2", "postgres", USER_EMAIL, "RuntimeError",
                     "Traceback", "Roudain"):
            assert leak not in rendered, f"unavailable body leaked {leak!r}"

    def test_unavailable_is_reported_without_falling_back_to_the_profile_cv(
        self, call_list_files
    ):
        """A synthetic legacy record must not paper over an unreadable store.

        The profile projection is a copy of grounding, not an inventory read.
        Returning it during an outage would claim the store was read.
        """
        legacy = {
            "id": "profile-cv",
            "doc_type": "cv",
            "filename": "legacy.pdf",
            "is_primary": True,
            "is_legacy": True,
        }
        with pytest.raises(HTTPException) as exc_info:
            call_list_files(_Db(available=False), profile_cv=legacy)
        assert exc_info.value.status_code == 503
        assert "legacy.pdf" not in repr(_detail_of(exc_info))


# ── 2. Successful reads are unchanged ────────────────────────────────────────

class TestSuccessfulReadsAreUnchanged:

    def test_genuine_empty_read_stays_a_200_empty_inventory(self, call_list_files):
        payload = call_list_files(_Db(available=True, docs=[]))

        assert payload["files"] == []
        assert payload["total"] == 0
        # The success shape carries no unavailable marker.
        assert payload.get("state") != "unavailable"
        assert "quota" in payload

    def test_non_empty_read_is_returned_as_before(self, call_list_files):
        payload = call_list_files(_Db(available=True, docs=STORED_DOCS))

        assert payload["total"] == 1
        assert [d["id"] for d in payload["files"]] == ["doc-1"]
        assert payload["quota"]["cv_used"] == 1

    def test_legacy_profile_cv_is_still_surfaced_on_a_successful_read(
        self, call_list_files
    ):
        """The pre-existing fallback behaviour is untouched by this fix."""
        legacy = {
            "id": "profile-cv",
            "doc_type": "cv",
            "filename": "legacy.pdf",
            "is_primary": True,
            "is_legacy": True,
        }
        payload = call_list_files(_Db(available=True, docs=[]), profile_cv=legacy)

        assert [d["id"] for d in payload["files"]] == ["profile-cv"]
        assert payload["total"] == 1
        # A projection occupies no storage.
        assert payload["quota"]["cv_used"] == 0
