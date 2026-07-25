"""CV confirm must return real save evidence and one server-derived principal.

Closed with read-only production evidence on 2026-07-25, not against a
hypothesis. One `cv_upload_artifacts` row, owned by a real authenticated email
principal, filename `Roben_Edwan_CV.pdf`. A pre-existing `user_documents` row
with the SAME content hash and size, canonical filename
`Roben_Edwan_Executive_Leadership_CV`. Confirm ran a real primary promotion
inside the authenticated owner's account — the previous primary was demoted at
the identical millisecond — even though the query string carried
`user_id=public:web-...`. No cross-user bypass, no deploy skew, no data loss.

Three defects, all of them about what the endpoint reports rather than what it
does:

  1. `get_or_create_user_document` dedupes on `(user_id, doc_type,
     content_hash)`, returns the existing row and keeps its old canonical
     filename, so the user's newly chosen name was silently discarded.
  2. The endpoint threw the returned row away entirely, so the response carried
     no `document_id`, no canonical filename and no `inserted` flag — nothing a
     client could verify a save against.
  3. `rico_profiles.profile->>'cv_filename'` WAS written with the new name while
     `user_documents` kept the old one, so the profile and My Files disagreed
     about the same file and the UI announced success from its local copy.

The artifact check (id AND user_id AND expiry, uniform rejection, zero side
effects on rejection) was already correct and is pinned here rather than
altered.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.api.routers.rico_chat import _derive_parse_status

_AUTH_UID = "owner@rico.ai"
_QUERY_PUBLIC_UID = "public:web-deployedfrontend1"

# The stored row's canonical name, older than the name now being confirmed.
_STORED_FILENAME = "Roben_Edwan_Executive_Leadership_CV"
_NEW_FILENAME = "Roben_Edwan_CV.pdf"
_CONTENT_HASH = "c82b6591" + "a" * 56

_ARTIFACT = {
    "filename": _NEW_FILENAME,
    "doc_type": "cv",
    "content_hash": _CONTENT_HASH,
    "file_size": 55519,
    "cv_text": (
        "Roben Edwan. Professional Summary: Executive leader. Work Experience: "
        "Head of Compliance at a UAE bank 2015-2025. Education: BSc. "
        "Skills: compliance, aml, governance."
    ),
}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


def _confirm_payload(*, filename=_NEW_FILENAME, upload_id="artifact-1"):
    return {
        "preview": {
            "name": "Roben Edwan",
            "current_role": "Head of Compliance",
            "experience_years": 10,
            "skills_detected": ["compliance", "aml"],
            "target_roles": ["Compliance Manager"],
            "certifications": [],
            "languages": ["english"],
        },
        "filename": filename,
        "doc_type": "cv",
        "upload_id": upload_id,
    }


def _fake_ricodb(doc_result: dict, recorder: MagicMock):
    """A RicoDB whose get_or_create_user_document returns a fixed stored row.

    The row is what the DATABASE would hand back, which is the whole point: the
    endpoint must report from it and never from the request it was given.
    """
    class _FakeRicoDB:
        available = True

        def __init__(self, *a, **kw):
            pass

        def get_or_create_user_document(self, **kwargs):
            recorder(**kwargs)
            return dict(doc_result)

        def save_user_document(self, **kwargs):
            raise AssertionError("legacy save_user_document must never be called")

    return _FakeRicoDB


def _post_confirm(
    client,
    *,
    doc_result: dict,
    resolve_return=_ARTIFACT,
    query_user_id: str = _QUERY_PUBLIC_UID,
    payload=None,
):
    recorder = MagicMock()
    upsert_mock = MagicMock()
    with (
        patch("src.api.routers.rico_chat.upsert_profile", upsert_mock),
        patch("src.api.routers.rico_chat.get_profile", return_value=None),
        patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
        patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
        patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
        patch("src.services.subscription_gating.record_profile_optimization_usage"),
        # A valid JWT resolves to the owner. The query parameter below is what
        # the deployed frontend really sends; the resolver never reads it.
        patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
        patch(
            "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
            return_value=resolve_return,
        ) as resolve_mock,
        patch("src.rico_db.RicoDB", _fake_ricodb(doc_result, recorder)),
    ):
        r = client.post(
            f"/api/v1/rico/confirm-cv-profile?user_id={query_user_id}",
            json=payload if payload is not None else _confirm_payload(),
        )
    return r, recorder, upsert_mock, resolve_mock, set_status_mock


# ── 1. Duplicate hash: same bytes, different filename ─────────────────────────

_DEDUPED_ROW = {
    "id": "34a86f49-0000-0000-0000-000000000000",
    # rename_on_match adopts the newly confirmed name onto the existing row, so
    # the row the DB hands back already carries the new name.
    "filename": _NEW_FILENAME,
    "doc_type": "cv",
    "is_primary": True,
    "skills_count": 2,
    "years_experience": 10,
    "inserted": False,
}


class TestDuplicateHashConfirm:
    def test_no_new_row_and_inserted_is_false(self, client):
        r, recorder, _upsert, _resolve, _status = _post_confirm(client, doc_result=_DEDUPED_ROW)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["document"]["inserted"] is False
        # Exactly one dedupe call, and it asked for the rename behaviour.
        recorder.assert_called_once()
        assert recorder.call_args.kwargs["rename_on_match"] is True
        assert recorder.call_args.kwargs["content_hash"] == _CONTENT_HASH

    def test_response_carries_the_canonical_name_not_the_request(self, client):
        r, _rec, _upsert, _resolve, _status = _post_confirm(client, doc_result=_DEDUPED_ROW)
        assert r.json()["document"]["filename"] == _DEDUPED_ROW["filename"]
        assert r.json()["document"]["document_id"] == _DEDUPED_ROW["id"]

    def test_profile_and_documents_agree_afterwards(self, client):
        """The defect: profile said one name, My Files said another."""
        r, _rec, upsert_mock, _resolve, _status = _post_confirm(client, doc_result=_DEDUPED_ROW)
        assert r.status_code == 200, r.text
        persisted_updates = upsert_mock.call_args.kwargs["updates"]
        assert persisted_updates["cv_filename"] == _DEDUPED_ROW["filename"]
        assert persisted_updates["cv_filename"] == r.json()["document"]["filename"]

    def test_profile_name_comes_from_the_row_even_when_it_differs_from_the_request(self, client):
        """If the stored row keeps an older name, the PROFILE adopts that name.

        Pins the direction of truth: the document row wins, never the request.
        Without this, a row that declined the rename would still leave the
        profile asserting a filename that no stored document has.
        """
        stale_row = dict(_DEDUPED_ROW, filename=_STORED_FILENAME)
        r, _rec, upsert_mock, _resolve, _status = _post_confirm(client, doc_result=stale_row)
        assert r.status_code == 200, r.text
        assert upsert_mock.call_args.kwargs["updates"]["cv_filename"] == _STORED_FILENAME
        assert r.json()["document"]["filename"] == _STORED_FILENAME


# ── 2. Compatibility: owner JWT + public query user_id ────────────────────────

_INSERTED_ROW = {
    "id": "11111111-0000-0000-0000-000000000000",
    "filename": _NEW_FILENAME,
    "doc_type": "cv",
    "is_primary": True,
    "skills_count": 2,
    "years_experience": 10,
    "inserted": True,
}


class TestPrincipalCompatibility:
    def test_owner_jwt_wins_over_query_user_id(self, client):
        """The deployed frontend sends ?user_id=public:web-... on every confirm.

        Rejecting that with a 400 would be an outage, so it is ignored: the
        document is written for the JWT owner and the artifact resolves against
        the owner, not the guest id in the query string.
        """
        r, recorder, upsert_mock, resolve_mock, _status = _post_confirm(
            client, doc_result=_INSERTED_ROW, query_user_id=_QUERY_PUBLIC_UID
        )
        assert r.status_code == 200, r.text
        resolve_mock.assert_called_once_with(_AUTH_UID, "artifact-1")
        assert recorder.call_args.kwargs["user_id"] == _AUTH_UID
        assert upsert_mock.call_args.kwargs["user_id"] == _AUTH_UID

    def test_response_carries_full_evidence(self, client):
        r, _rec, _upsert, _resolve, _status = _post_confirm(client, doc_result=_INSERTED_ROW)
        assert r.status_code == 200, r.text
        assert r.json()["document"] == {
            "document_id": _INSERTED_ROW["id"],
            "filename": _NEW_FILENAME,
            "doc_type": "cv",
            "is_primary": True,
            "parse_status": "parsed",
            "inserted": True,
        }

    def test_ignore_is_recorded_without_personal_data(self, client, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="src.api.routers.rico_chat"):
            r, _rec, _upsert, _resolve, _status = _post_confirm(
                client, doc_result=_INSERTED_ROW, query_user_id=_QUERY_PUBLIC_UID
            )
        assert r.status_code == 200, r.text
        line = next(
            (m for m in caplog.messages if "principal=server_derived" in m), None
        )
        assert line is not None, caplog.messages
        assert "reason=query_user_id_ignored" in line
        assert "authenticated=True" in line
        assert "query_present=True" in line
        assert "query_mismatch=True" in line
        # Never the raw email, the guest uuid, the upload_id or the filename.
        for secret in (_AUTH_UID, _QUERY_PUBLIC_UID, "artifact-1", _NEW_FILENAME):
            assert secret not in line

    def test_no_query_user_id_is_recorded_as_such(self, client, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="src.api.routers.rico_chat"):
            _post_confirm(client, doc_result=_INSERTED_ROW, query_user_id="")
        line = next((m for m in caplog.messages if "principal=server_derived" in m), None)
        assert line is not None, caplog.messages
        assert "reason=no_query_user_id" in line
        assert "query_present=False" in line
        assert "query_mismatch=False" in line


# ── 3. Foreign / expired artifact: uniform rejection, zero side effects ───────

class TestArtifactRejectionUnchanged:
    @pytest.mark.parametrize("resolve_return", [None])
    def test_foreign_or_expired_artifact_is_rejected_uniformly(self, client, resolve_return):
        r, recorder, upsert_mock, _resolve, set_status_mock = _post_confirm(
            client, doc_result=_INSERTED_ROW, resolve_return=resolve_return
        )
        assert r.status_code == 409, r.text
        assert r.json() == {
            "ok": False,
            "status": "cv_confirmation_required",
            "message": "Please upload the CV again before confirming.",
        }
        assert "document" not in r.json()
        recorder.assert_not_called()
        upsert_mock.assert_not_called()
        set_status_mock.assert_not_called()

    def test_filename_mismatch_is_rejected_with_no_side_effects(self, client):
        """The artifact resolves but is for a different filename."""
        r, recorder, upsert_mock, _resolve, set_status_mock = _post_confirm(
            client,
            doc_result=_INSERTED_ROW,
            payload=_confirm_payload(filename="someone_else_cv.pdf"),
        )
        assert r.status_code == 409, r.text
        recorder.assert_not_called()
        upsert_mock.assert_not_called()
        set_status_mock.assert_not_called()

    def test_missing_upload_id_is_rejected_with_no_side_effects(self, client):
        r, recorder, upsert_mock, _resolve, set_status_mock = _post_confirm(
            client, doc_result=_INSERTED_ROW, payload=_confirm_payload(upload_id=None)
        )
        assert r.status_code == 409, r.text
        recorder.assert_not_called()
        upsert_mock.assert_not_called()
        set_status_mock.assert_not_called()


# ── parse_status must never assert an extraction that did not happen ──────────

class TestParseStatusHonesty:
    def test_parsed_requires_real_extracted_content(self):
        assert _derive_parse_status(
            {"doc_type": "cv", "is_primary": True, "skills_count": 3, "years_experience": None}
        ) == "parsed"
        assert _derive_parse_status(
            {"doc_type": "cv", "is_primary": True, "skills_count": 0, "years_experience": 8}
        ) == "parsed"

    def test_row_existence_alone_is_never_parsed(self):
        """A production profile carried cv_status="parsed" with an empty
        cv_structured. This response must not inherit that shape of claim."""
        assert _derive_parse_status(
            {"doc_type": "cv", "is_primary": True, "skills_count": 0, "years_experience": None}
        ) == "metadata_only"

    def test_non_primary_or_non_cv_is_metadata_only(self):
        assert _derive_parse_status(
            {"doc_type": "cv", "is_primary": False, "skills_count": 5, "years_experience": 8}
        ) == "metadata_only"
        assert _derive_parse_status(
            {"doc_type": "cover_letter", "is_primary": True, "skills_count": 5, "years_experience": 8}
        ) == "metadata_only"

    def test_missing_keys_degrade_to_metadata_only(self):
        assert _derive_parse_status({}) == "metadata_only"

    def test_endpoint_reports_metadata_only_for_a_contentless_row(self, client):
        contentless = dict(_INSERTED_ROW, skills_count=0, years_experience=None)
        r, _rec, _upsert, _resolve, _status = _post_confirm(client, doc_result=contentless)
        assert r.status_code == 200, r.text
        assert r.json()["document"]["parse_status"] == "metadata_only"


# ── 4. Primary flip: exactly one demotion ────────────────────────────────────

class _FakeCursor:
    """Records every statement so the promotion can be counted, not assumed."""

    def __init__(self, existing_row):
        self._existing = existing_row
        self.statements: list[tuple[str, tuple]] = []
        self._last = None

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        upper = sql.upper()
        if "SELECT ID, FILENAME" in upper:
            self._last = self._existing
        elif "RETURNING" in upper and "INSERT" in upper:
            self._last = None
        else:
            self._last = None

    def fetchone(self):
        return self._last

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run_get_or_create(existing_row, **kwargs):
    from src.rico_db import RicoDB

    cur = _FakeCursor(existing_row)
    db = RicoDB.__new__(RicoDB)
    from contextlib import contextmanager

    @contextmanager
    def _txn():
        yield _FakeConn(cur)

    db._transaction = _txn
    result = RicoDB.get_or_create_user_document(
        db,
        user_id=_AUTH_UID,
        filename=_NEW_FILENAME,
        original_filename=_NEW_FILENAME,
        content_hash=_CONTENT_HASH,
        doc_type="cv",
        **kwargs,
    )
    return result, cur


class TestPrimaryFlipAndRename:
    def _existing(self, *, is_primary: bool, filename: str = _STORED_FILENAME):
        return {
            "id": "34a86f49-0000-0000-0000-000000000000",
            "filename": filename,
            "doc_type": "cv",
            "is_primary": is_primary,
            "skills_count": 2,
            "years_experience": 10,
        }

    def test_promoting_demotes_the_previous_primary_exactly_once(self):
        result, cur = _run_get_or_create(
            self._existing(is_primary=False), is_primary=True, rename_on_match=True
        )
        demotions = [s for s, _ in cur.statements if "SET IS_PRIMARY = FALSE" in s.upper()]
        promotions = [s for s, _ in cur.statements if "SET IS_PRIMARY = TRUE" in s.upper()]
        assert len(demotions) == 1, cur.statements
        assert len(promotions) == 1, cur.statements
        assert result["is_primary"] is True
        assert result["inserted"] is False

    def test_already_primary_row_is_not_re_promoted(self):
        _result, cur = _run_get_or_create(
            self._existing(is_primary=True), is_primary=True, rename_on_match=True
        )
        assert not [s for s, _ in cur.statements if "SET IS_PRIMARY = FALSE" in s.upper()]
        assert not [s for s, _ in cur.statements if "SET IS_PRIMARY = TRUE" in s.upper()]

    def test_rename_on_match_adopts_the_new_name_and_leaves_original_alone(self):
        result, cur = _run_get_or_create(
            self._existing(is_primary=True), is_primary=True, rename_on_match=True
        )
        renames = [(s, p) for s, p in cur.statements if "SET FILENAME" in s.upper()]
        assert len(renames) == 1, cur.statements
        assert renames[0][1][0] == _NEW_FILENAME
        assert "ORIGINAL_FILENAME" not in renames[0][0].upper()
        assert result["filename"] == _NEW_FILENAME
        assert result["inserted"] is False

    def test_default_leaves_the_generic_upload_contract_untouched(self):
        """files.py and every other caller must be unaffected by this change."""
        result, cur = _run_get_or_create(self._existing(is_primary=True), is_primary=False)
        assert not [s for s, _ in cur.statements if "SET FILENAME" in s.upper()]
        assert result["filename"] == _STORED_FILENAME
        assert result["inserted"] is False

    def test_rename_is_skipped_when_the_name_already_matches(self):
        _result, cur = _run_get_or_create(
            self._existing(is_primary=True, filename=_NEW_FILENAME),
            is_primary=True,
            rename_on_match=True,
        )
        assert not [s for s, _ in cur.statements if "SET FILENAME" in s.upper()]

    def test_returned_row_carries_the_content_signals(self):
        result, _cur = _run_get_or_create(
            self._existing(is_primary=True), is_primary=True, rename_on_match=True
        )
        assert result["skills_count"] == 2
        assert result["years_experience"] == 10
        assert _derive_parse_status(result) == "parsed"
