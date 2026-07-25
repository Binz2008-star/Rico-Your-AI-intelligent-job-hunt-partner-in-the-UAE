"""The pending-CV-upload contract: reach the confirm card without lying either way.

A CV uploaded from the Vault surface produced a server-side artifact that nobody
could reach: the confirm card is a chat message built only by an in-chat upload,
`cv=ready` fetched nothing, and no endpoint existed to read a pending artifact.
The file sat in the database for its whole TTL, was never saved, and was purged —
silent data loss on a timer, while chat behaved as though a CV existed.

Restoring the card is only half the job. Two opposite lies have to stay closed at
the same time:

  * before confirm — the product must not act as though it has the CV;
  * after confirm — the product must not keep showing "review required, not saved
    yet" for a CV that IS saved.

Both are covered below, and so is every failure path: expired, absent, store
down, preview unrebuildable, bad auth.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.repositories.cv_upload_artifact_repo import ArtifactStoreUnavailable
from src.services.cv_preview import build_cv_preview, build_preview_from_text

_AUTH_UID = "owner@rico.ai"
_UPLOAD_ID = "11111111-2222-3333-4444-555555555555"
_CV_TEXT = """Roben Edwan
Head of Compliance

WORK EXPERIENCE
Head of Compliance, Emirates NBD    2019 - Present
Led the AML programme across the GCC.

EDUCATION
BSc Computer Science, University of Dubai    2010 - 2014

SKILLS
compliance, audit, risk assessment
"""


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


def _artifact(cv_text=_CV_TEXT, filename="Roben_Edwan_CV.pdf"):
    return {
        "upload_id": _UPLOAD_ID,
        "filename": filename,
        "doc_type": "cv",
        "cv_text": cv_text,
        "expires_at": None,
        "expired": False,
        "already_saved": False,
    }


def _get(client, *, pending=None, raises=None, profile=None):
    target = "src.repositories.cv_upload_artifact_repo.get_latest_pending_cv_upload"
    kw = {"side_effect": raises} if raises else {"return_value": pending}
    with (
        patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
        patch("src.api.routers.rico_chat.get_profile", return_value=profile),
        patch(target, **kw),
    ):
        return client.get("/api/v1/rico/pending-cv-upload")


# ── The four response states, kept distinct ──────────────────────────────────

class TestFourDistinctStates:
    def test_definite_absence_is_200_pending_false(self, client):
        r = _get(client, pending=None)
        assert r.status_code == 200, r.text
        assert r.json() == {"pending": False, "state": "absent"}

    def test_real_pending_upload_returns_the_preview(self, client):
        r = _get(client, pending=_artifact())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pending"] is True
        assert body["preview_available"] is True
        assert body["upload_id"] == _UPLOAD_ID
        assert body["filename"] == "Roben_Edwan_CV.pdf"
        assert body["preview"]["current_role"] or body["preview"]["skills_detected"]

    def test_unrebuildable_preview_is_pending_true_not_false(self, client):
        """The upload is real; only the replay failed.

        Reporting pending=false here would tell the user their upload vanished.
        """
        r = _get(client, pending=_artifact(cv_text=""))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pending"] is True
        assert body["preview_available"] is False
        assert body["upload_id"] == _UPLOAD_ID
        assert "preview" not in body

    def test_store_failure_is_503_with_a_stable_code_and_never_denies_the_upload(self, client):
        r = _get(client, raises=ArtifactStoreUnavailable("neon down"))
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["error_code"] == "pending_upload_unavailable"
        assert body.get("pending") is not False
        # Must not tell the user the upload does not exist.
        assert "doesn" not in body["message"].lower() or "exist" not in body["message"].lower()


# ── Nothing internal may leak ────────────────────────────────────────────────

class TestNoInternalFieldsLeak:
    def test_response_carries_no_raw_text_or_hash_or_db_columns(self, client):
        r = _get(client, pending=_artifact())
        raw = r.text
        body = r.json()
        assert "cv_text" not in body
        assert "content_hash" not in body
        assert "file_size" not in body
        assert "user_id" not in body
        # The CV's own sentences must not appear anywhere in the payload.
        assert "Emirates NBD" not in raw
        assert "University of Dubai" not in raw

    def test_cache_control_forbids_intermediary_storage(self, client):
        r = _get(client, pending=_artifact())
        assert r.headers.get("Cache-Control") == "private, no-store"

    def test_store_failure_response_is_also_uncacheable(self, client):
        r = _get(client, raises=ArtifactStoreUnavailable("down"))
        assert r.headers.get("Cache-Control") == "private, no-store"


# ── Authentication: no guest fallback ────────────────────────────────────────

class TestAuthIsNotDowngraded:
    def test_invalid_token_propagates_and_never_falls_back_to_guest(self, client):
        from fastapi import HTTPException

        with patch(
            "src.api.routers.rico_chat._resolve_upload_user_id",
            side_effect=HTTPException(status_code=401, detail="Invalid token"),
        ), patch(
            "src.repositories.cv_upload_artifact_repo.get_latest_pending_cv_upload"
        ) as pending:
            r = client.get("/api/v1/rico/pending-cv-upload")
        assert r.status_code in (401, 403)
        pending.assert_not_called()

    def test_guest_session_has_nothing_pending_by_construction(self, client):
        with patch(
            "src.api.routers.rico_chat._resolve_upload_user_id",
            return_value="public:web-guest12345",
        ), patch(
            "src.repositories.cv_upload_artifact_repo.get_latest_pending_cv_upload"
        ) as pending:
            r = client.get("/api/v1/rico/pending-cv-upload")
        assert r.status_code == 200
        assert r.json() == {"pending": False, "state": "absent"}
        pending.assert_not_called()


# ── The inverse lie: a confirmed CV must stop being "pending" ────────────────

class TestConfirmedCvIsNoLongerPending:
    """Fails before the fix.

    The artifact stays alive for its whole TTL after a successful confirm. Without
    deriving "pending" from the absence of a saved document, a later visit would
    show "review required — not saved yet" for a CV that IS saved: the exact
    inverse of the lie this work removes.
    """

    def _run_sql(self, saved_hashes):
        """Drive the real repository query against a fake cursor."""
        from src.repositories import cv_upload_artifact_repo as repo

        captured = {}

        class _Cur:
            def execute(self, sql, params=()):
                captured["sql"] = " ".join(sql.split())
                captured["params"] = params

            def fetchone(self):
                # The query itself excludes already-saved hashes; the fake mirrors
                # that by returning nothing when a matching document exists.
                # id, filename, doc_type, cv_text, expires_at, is_expired, is_saved
                return (
                    _UPLOAD_ID, "cv.pdf", "cv", _CV_TEXT, None, False, bool(saved_hashes)
                )

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Conn:
            def cursor(self):
                return _Cur()

            def close(self):
                pass

        with patch.object(repo, "get_db_connection", create=True):
            with patch("src.db.get_db_connection", return_value=_Conn()):
                result = repo.get_latest_pending_cv_upload(_AUTH_UID)
        return result, captured

    def test_query_reports_saved_state_instead_of_hiding_the_artifact(self):
        """Hiding a saved artifact is what collapsed already_saved into absent."""
        _result, captured = self._run_sql(saved_hashes=False)
        sql = captured["sql"].upper()
        assert "EXISTS (" in sql
        assert "NOT EXISTS" not in sql
        assert "USER_DOCUMENTS" in sql
        assert "CONTENT_HASH" in sql

    def test_query_reports_expiry_instead_of_filtering_it_out(self):
        """Expired rows must still be visible, or an expired upload would be
        indistinguishable from never having uploaded."""
        _result, captured = self._run_sql(saved_hashes=False)
        sql = captured["sql"].upper()
        assert "EXPIRES_AT <= NOW()" in sql
        assert "AND A.EXPIRES_AT > NOW()" not in sql

    def test_saved_document_is_visible_so_it_can_be_reported(self):
        """It must NOT vanish: the endpoint needs it to say already_saved."""
        result, _ = self._run_sql(saved_hashes=True)
        assert result is not None
        assert result["already_saved"] is True

    def test_endpoint_shows_no_card_once_the_cv_is_saved(self, client):
        """End of the chain: a confirmed user reopens cv=ready and sees no card,
        and is told the CV is saved rather than that nothing was pending."""
        r = _get(client, pending=dict(_artifact(), already_saved=True))
        assert r.status_code == 200
        body = r.json()
        assert body["pending"] is False
        assert body["state"] == "already_saved"
        assert "not saved" not in r.text.lower()


# ── Pending content stays out of quota and My Files ─────────────────────────

class TestPendingIsNotCountedAnywhere:
    def test_quota_does_not_look_at_artifacts(self):
        import inspect

        from src.services import subscription_gating

        assert "cv_upload_artifacts" not in inspect.getsource(subscription_gating)

    def test_my_files_does_not_look_at_artifacts(self):
        import inspect

        from src.api.routers import files

        assert "cv_upload_artifacts" not in inspect.getsource(files)


# ── One preview builder, not two ────────────────────────────────────────────

class TestSinglePreviewBuilder:
    def test_upload_route_uses_the_shared_builder(self):
        import inspect

        from src.api.routers import rico_chat

        source = inspect.getsource(rico_chat)
        assert "build_cv_preview" in source
        # The inline dict that used to build a second preview is gone.
        assert '"skills_detected": detected_skills' not in source

    def test_replay_and_upload_produce_the_same_shape(self):
        from src.cv_parser import CVParser

        parsed = CVParser().parse_text(_CV_TEXT).to_dict()
        direct = build_cv_preview(parsed, existing_skills=[], target_roles=[])
        replayed = build_preview_from_text(_CV_TEXT, existing_skills=[])
        assert replayed is not None
        assert set(direct) == set(replayed)
        assert direct["skills_detected"] == replayed["skills_detected"]

    def test_replay_returns_none_for_unusable_text(self):
        assert build_preview_from_text("") is None
        assert build_preview_from_text("   ") is None


# ── Upload must not promise a review it cannot honour ───────────────────────

class TestUploadDoesNotPromiseAReviewItCannotHonour:
    def test_artifact_failure_returns_storage_error_not_preview_ready(self):
        """A preview with no artifact behind it can never be confirmed."""
        import inspect

        from src.api.routers import rico_chat

        source = inspect.getsource(rico_chat.rico_upload_cv)
        assert "cv_storage_unavailable" in source
        assert "upload_artifact_unavailable" in source
        # The guard must sit before the preview_ready return.
        assert source.index("cv_storage_unavailable") < source.index('"status": "preview_ready"')


# ── The template that invented missing sections for everyone ────────────────

class TestUnparsedSectionsAreNotFabricated:
    """Fails before the fix.

    _handle_cv_generate_from_profile read `work_experience` and `education` off
    RicoProfile. Neither field exists on that model, so both always read as
    absent and the reply told EVERY user — including one whose CV was confirmed
    and fully structured — that Work Experience and Education were "not yet
    available from your parsed CV", then asked them to paste their work history
    by hand. Manual work demanded to fix a gap that does not exist.
    """

    def _structured(self, *, with_work=True, with_education=True):
        doc = {"schema_version": 1, "skills": ["compliance", "audit", "risk assessment"]}
        if with_work:
            doc["work_experience"] = [
                {"text": "Head of Compliance, Emirates NBD", "date_range": "2019 - Present"}
            ]
            doc["work_experience_text"] = "Head of Compliance, Emirates NBD 2019 - Present"
        if with_education:
            doc["education"] = [{"text": "BSc Computer Science", "date_range": "2010 - 2014"}]
            doc["education_text"] = "BSc Computer Science 2010 - 2014"
        return doc

    def _reply(self, structured):
        from src.rico_chat_api import RicoChatAPI
        from src.services.cv_context_resolver import CVContext

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._append_chat = MagicMock()
        profile = {
            "name": "Roben Edwan",
            "current_role": "Head of Compliance",
            "years_experience": 10,
            "skills": ["compliance", "audit"],
            "target_roles": ["Compliance Manager"],
            "preferred_cities": ["Dubai"],
            "certifications": ["iso"],
            "industries": ["banking"],
        }
        ctx = CVContext(
            state="structured" if structured else "none",
            structured=structured,
            availability_reason="structured_available",
        )
        with patch.object(RicoChatAPI, "_cv_context", return_value=ctx):
            return RicoChatAPI._handle_cv_generate_from_profile(api, "u@x.com", profile, "build my cv")

    def test_structured_cv_is_not_told_its_sections_are_missing(self):
        result = self._reply(self._structured())
        assert result["unparsed_sections"] == [], result["unparsed_sections"]
        message = result["message"]
        assert "Work Experience" not in message.split("**Key Skills**")[-1] or "not yet available" not in message
        assert "not yet available" not in message

    def test_structured_cv_is_never_asked_to_paste_work_history(self):
        """The forbidden request: manual work for a gap that does not exist."""
        message = self._reply(self._structured())["message"]
        assert "paste" not in message.lower()
        assert "الصق" not in message

    def test_a_genuinely_missing_section_is_still_reported(self):
        """Honest in the other direction — no section is hidden."""
        result = self._reply(self._structured(with_education=False))
        assert "Education" in result["unparsed_sections"]
        assert "Work Experience" not in result["unparsed_sections"]

    def test_both_missing_sections_are_reported_when_both_are_absent(self):
        result = self._reply(self._structured(with_work=False, with_education=False))
        assert set(result["unparsed_sections"]) == {"Work Experience", "Education"}


# ── Expiry is its own honest state ──────────────────────────────────────────

class TestExpiredIsDistinctFromAbsent:
    def test_expired_upload_says_so_and_does_not_deny_the_upload(self, client):
        r = _get(client, pending=dict(_artifact(), expired=True))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pending"] is False
        assert body["state"] == "expired"
        assert body["filename"] == "Roben_Edwan_CV.pdf"
        assert "expired" in body["message"].lower()
        # Must never claim the user has no CV / never uploaded.
        assert "no cv" not in body["message"].lower()
        assert "haven't uploaded" not in body["message"].lower()

    def test_absent_is_not_reported_as_expired(self, client):
        body = _get(client, pending=None).json()
        assert body == {"pending": False, "state": "absent"}
        assert "expired" not in body

    def test_expired_response_carries_no_preview_and_no_internal_fields(self, client):
        r = _get(client, pending=dict(_artifact(), expired=True))
        body = r.json()
        assert "preview" not in body
        assert "cv_text" not in body
        assert "Emirates NBD" not in r.text

    def test_repository_reports_expiry_rather_than_hiding_it(self):
        import inspect

        from src.repositories import cv_upload_artifact_repo as repo

        sql = inspect.getsource(repo.get_latest_pending_cv_upload)
        assert "expires_at <= NOW()" in sql
        # The triple key: a same-hash file of another type must not cancel a CV.
        assert "d.doc_type = a.doc_type" in sql
        assert "d.content_hash = a.content_hash" in sql
        assert "d.user_id = a.user_id" in sql


# ── Confirm stays idempotent after the document is saved ────────────────────

class TestSecondConfirmIsHonestNotAnError:
    """A second confirm of the same upload_id must say "already saved".

    The artifact is not consumed, so it still resolves; the duplicate content
    hash makes get_or_create_user_document return inserted=False. The response
    must carry the same document evidence — never 409, never "no CV", never
    "upload not found".
    """

    def test_duplicate_confirm_returns_inserted_false_with_the_same_document(self, client):
        from src.rico_chat_api import RicoChatAPI  # noqa: F401  (import parity)

        artifact = {
            "filename": "Roben_Edwan_CV.pdf",
            "doc_type": "cv",
            "content_hash": "c82b6591" + "a" * 56,
            "file_size": 55519,
            "cv_text": _CV_TEXT,
        }
        saved_row = {
            "id": "34a86f49-0000-0000-0000-000000000000",
            "filename": "Roben_Edwan_CV.pdf",
            "doc_type": "cv",
            "is_primary": True,
            "skills_count": 3,
            "years_experience": 10,
            "inserted": False,          # the duplicate-hash outcome
        }

        class _FakeRicoDB:
            available = True

            def __init__(self, *a, **kw):
                pass

            def get_or_create_user_document(self, **kwargs):
                return dict(saved_row)

        payload = {
            "preview": {"name": "Roben Edwan", "skills_detected": ["compliance"]},
            "filename": "Roben_Edwan_CV.pdf",
            "doc_type": "cv",
            "upload_id": _UPLOAD_ID,
        }
        with (
            patch("src.api.routers.rico_chat.upsert_profile", MagicMock()),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status"),
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=artifact,
            ),
            patch("src.rico_db.RicoDB", _FakeRicoDB),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_AUTH_UID}", json=payload
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["document"]["inserted"] is False
        assert body["document"]["document_id"] == saved_row["id"]
        assert body["document"]["filename"] == "Roben_Edwan_CV.pdf"
        # Explicitly NOT an error, and not a denial of the CV.
        assert r.status_code != 409
        assert "cv_confirmation_required" not in r.text
        assert "upload the CV again" not in r.text


# ── Five named states: "saved" is never reported as "nothing pending" ────────

class TestFiveNamedStates:
    """`absent` used to swallow `already_saved`.

    A user who uploaded and confirmed got the same answer as one who never
    uploaded: "nothing pending". Technically true, practically a lie — it reads
    as "your upload went nowhere". The triple key knows the difference, so
    collapsing them was never justified.
    """

    def test_saved_artifact_reports_already_saved_not_absent(self, client):
        r = _get(client, pending=dict(_artifact(), already_saved=True))
        body = r.json()
        assert body["state"] == "already_saved"
        assert body["pending"] is False
        assert "My Files" in body["message"]
        # The two answers it must never be confused with.
        assert body["state"] != "absent"
        assert "nothing pending" not in body["message"].lower()

    def test_never_uploaded_reports_absent(self, client):
        assert _get(client, pending=None).json()["state"] == "absent"

    def test_pending_reports_pending(self, client):
        assert _get(client, pending=_artifact()).json()["state"] == "pending"

    def test_expired_reports_expired(self, client):
        assert _get(client, pending=dict(_artifact(), expired=True)).json()["state"] == "expired"

    def test_store_failure_reports_unavailable(self, client):
        r = _get(client, raises=ArtifactStoreUnavailable("down"))
        assert r.json()["state"] == "unavailable"

    def test_saved_wins_over_expired(self, client):
        """A saved CV whose preview also lapsed is SAVED — that is what matters."""
        r = _get(client, pending=dict(_artifact(), already_saved=True, expired=True))
        assert r.json()["state"] == "already_saved"

    def test_all_five_states_are_distinct_values(self, client):
        seen = {
            _get(client, pending=None).json()["state"],
            _get(client, pending=_artifact()).json()["state"],
            _get(client, pending=dict(_artifact(), expired=True)).json()["state"],
            _get(client, pending=dict(_artifact(), already_saved=True)).json()["state"],
            _get(client, raises=ArtifactStoreUnavailable("x")).json()["state"],
        }
        assert seen == {"absent", "pending", "expired", "already_saved", "unavailable"}


class TestTripleKeyDistinguishesReuploads:
    def test_same_bytes_same_type_is_already_saved(self):
        import inspect

        from src.repositories import cv_upload_artifact_repo as repo

        sql = inspect.getsource(repo.get_latest_pending_cv_upload)
        # EXISTS with all three columns is what makes already_saved possible.
        assert "EXISTS (" in sql
        assert "d.user_id = a.user_id" in sql
        assert "d.doc_type = a.doc_type" in sql
        assert "d.content_hash = a.content_hash" in sql
        # The old NOT EXISTS filter hid saved artifacts entirely.
        assert "NOT EXISTS" not in sql

    def test_edited_copy_with_a_different_hash_stays_pending(self, client):
        """A different hash means no matching document, so it is independently
        pending — the triple key does not spill across versions."""
        r = _get(client, pending=dict(_artifact(), already_saved=False))
        assert r.json()["state"] == "pending"


class TestPendingCardDisclosesExpiry:
    """Temporary retention is only acceptable if its owner can see its duration."""

    def test_pending_response_carries_the_expiry_timestamp(self, client):
        from datetime import datetime, timezone

        when = datetime(2026, 7, 25, 18, 30, tzinfo=timezone.utc)
        r = _get(client, pending=dict(_artifact(), expires_at=when))
        body = r.json()
        assert body["expires_at"] == when.isoformat()

    def test_missing_expiry_degrades_to_null_not_an_error(self, client):
        r = _get(client, pending=_artifact())
        assert r.status_code == 200
        assert r.json()["expires_at"] is None


# ── Compensating happy-path cover, and the four cause branches ──────────────

_PDF = b"%PDF-1.4 fake"
_PARSED = {
    "text": _CV_TEXT,
    "skills": ["compliance", "audit"],
    "emails": ["roben@example.com"],
    "phones": ["+971500000000"],
    "years_experience_hint": 10,
    "certifications": ["iso"],
    "languages": ["english"],
    "extraction_quality": "good",
    "extracted_chars": len(_CV_TEXT),
    "name": "Roben Edwan",
    "current_role": "Head of Compliance",
}


def _upload(client, *, created_id, reachable, production=False, raises_env=False):
    """Drive POST /upload-cv with the artifact-creation outcome under control."""
    import src.api.routers.rico_chat as mod

    def _fake_is_production():
        if raises_env:
            raise RuntimeError("environment undeterminable")
        return production

    with (
        patch("src.services.chat_service.parse_cv", return_value=_PARSED),
        patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
        patch("src.api.routers.rico_chat.get_profile", return_value=None),
        patch("src.cv_parser.CVParser", return_value=type(
            "Parser", (), {"detect_document_type": lambda self, text: "cv"}
        )()),
        patch("src.repositories.cv_upload_artifact_repo.create_cv_upload_artifact", return_value=created_id),
        patch("src.repositories.cv_upload_artifact_repo.artifact_store_reachable", return_value=reachable),
        patch.object(mod, "_is_production", _fake_is_production),
    ):
        return client.post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.pdf", __import__("io").BytesIO(_PDF), "application/pdf")},
        )


class TestUploadArtifactBranches:
    """Four branches, decided by CAUSE. The happy path is covered here because
    the stale assertions it used to live behind were corrected in the route
    tests — without this, an endpoint that never emits preview_ready would ship
    unnoticed."""

    def test_happy_path_emits_preview_ready_with_a_retrievable_upload_id(self, client):
        r = _upload(client, created_id=_UPLOAD_ID, reachable=True)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_ready"
        # The id returned is the one actually created, and it is the key confirm
        # resolves by — a preview whose id cannot be resolved is the whole defect.
        assert body["upload_id"] == _UPLOAD_ID
        assert body["preview"]["current_role"] == "Head of Compliance"

    def test_write_failed_while_store_reachable_is_503(self, client):
        r = _upload(client, created_id=None, reachable=True)
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["error_code"] == "upload_artifact_unavailable"
        assert "preview_ready" not in body.values()
        assert "preview" not in body

    def test_no_usable_store_outside_production_is_degraded_200(self, client):
        r = _upload(client, created_id=None, reachable=False, production=False)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_not_persistable"
        assert body["persistable"] is False
        # Absent, not false.
        assert "preview_ready" not in body.values()
        assert body["upload_id"] is None
        # The extraction is still returned — the parse genuinely succeeded.
        assert body["preview"]["current_role"] == "Head of Compliance"

    def test_no_usable_store_in_production_is_503(self, client):
        r = _upload(client, created_id=None, reachable=False, production=True)
        assert r.status_code == 503, r.text
        assert "preview_ready" not in r.json().values()

    def test_undeterminable_environment_fails_closed_to_503(self, client):
        """The degraded 200 is a licence granted on proof, not the default."""
        r = _upload(client, created_id=None, reachable=False, raises_env=True)
        assert r.status_code == 503, r.text
        assert "preview_ready" not in r.json().values()
