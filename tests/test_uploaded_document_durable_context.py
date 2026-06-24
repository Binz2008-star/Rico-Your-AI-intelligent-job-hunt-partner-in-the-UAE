"""
Durable persistence of the uploaded image/document transcript.

Production runs RICO_MEMORY_BACKEND=postgres, where RicoMemoryStore.set_context is
a no-op, and Render's disk is ephemeral. So the OCR transcript stored at upload
time must live in a durable DB table to survive to the follow-up chat turn — both
button clicks ("Extract key information") and typed questions ("what do you think
of this job?").

DB is mocked — no live Neon.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.repositories import uploaded_document_repo as repo
from src.rico_chat_api import RicoChatAPI


# ── Fake psycopg2 connection ──────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, fetch_row=None):
        self.executed = []
        self._fetch_row = fetch_row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetch_row


class _FakeConn:
    def __init__(self, fetch_row=None):
        self.cur = _FakeCursor(fetch_row)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def _patch_db(conn):
    return patch("src.db.get_db_connection", return_value=conn)


# ── Repo: write ───────────────────────────────────────────────────────────────

def test_set_upserts_transcript():
    conn = _FakeConn()
    with _patch_db(conn):
        repo.set_last_uploaded_document(
            "u@test", extracted_text="Regional GM, Middle East — Yalla Pizza. Ajman.",
            filename="IMG_1793.png", document_type="job_description",
            display_label="Job Description", source="image", request_ref="ERR-1",
        )
    assert conn.committed and conn.closed
    sql, params = conn.cur.executed[0]
    assert "INSERT INTO uploaded_document_context" in sql
    assert "ON CONFLICT (user_id)" in sql
    assert params[0] == "u@test"
    assert "Yalla Pizza" in params[5]  # extracted_text param


def test_set_noop_without_text():
    conn = _FakeConn()
    with _patch_db(conn):
        repo.set_last_uploaded_document("u@test", extracted_text="   ")
    assert conn.cur.executed == []  # never touched the DB


def test_set_noop_without_db():
    with _patch_db(None):
        repo.set_last_uploaded_document("u@test", extracted_text="hello")  # no crash


# ── Repo: read ────────────────────────────────────────────────────────────────

def test_get_maps_row():
    row = ("IMG.png", "job_description", "Job Description", "image",
           "Regional GM at Yalla Pizza", "ERR-1", "2026-06-23T12:00:00Z")
    with _patch_db(_FakeConn(fetch_row=row)):
        doc = repo.get_last_uploaded_document("u@test")
    assert doc["extracted_text"] == "Regional GM at Yalla Pizza"
    assert doc["document_type"] == "job_description"
    assert doc["display_label"] == "Job Description"
    assert doc["filename"] == "IMG.png"


def test_get_none_when_no_row():
    with _patch_db(_FakeConn(fetch_row=None)):
        assert repo.get_last_uploaded_document("u@test") is None


def test_get_none_without_db():
    with _patch_db(None):
        assert repo.get_last_uploaded_document("u@test") is None


# ── RicoChatAPI: durable read integration (postgres-mode simulation) ──────────

def _api():
    return RicoChatAPI(persist=False)


def test_get_last_uploaded_document_falls_back_to_durable():
    """Ephemeral context empty (postgres mode) → durable store supplies the doc."""
    api = _api()
    durable = {"extracted_text": "Yalla Pizza GM role", "display_label": "Job Description", "filename": "x.png"}
    with (
        patch.object(api, "_get_recent_context", return_value={}),
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document", return_value=durable),
    ):
        doc = api._get_last_uploaded_document("u@test")
    assert doc is durable


def test_get_last_uploaded_document_prefers_ephemeral():
    """When the in-process context has it (json/local mode), don't hit the DB."""
    api = _api()
    ephemeral = {"last_uploaded_document": {"extracted_text": "fast path", "filename": "y.png"}}
    with (
        patch.object(api, "_get_recent_context", return_value=ephemeral),
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document",
              side_effect=AssertionError("durable store should not be consulted")),
    ):
        doc = api._get_last_uploaded_document("u@test")
    assert doc["extracted_text"] == "fast path"


# ── Follow-up button uses the durable transcript ──────────────────────────────

def _run_followup(api, message, user_id, durable):
    captured = {}

    def _fake_ai(uid, msg, profile, *, save_user_message, language=None, prompt_override=None):
        captured["override"] = prompt_override
        captured["uid"] = uid
        return {"type": "ai", "message": "Key info: Regional GM at Yalla Pizza, Ajman.", "success": True}

    with (
        patch.object(api, "_get_recent_context", return_value={}),  # ephemeral empty (postgres)
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document", return_value=durable),
        patch.object(api, "_resolve_profile", return_value=None),
        patch.object(api, "_answer_with_ai_fallback", side_effect=_fake_ai),
    ):
        res = api._handle_uploaded_document_followup(user_id, message, None)
    return res, captured


def test_button_extract_uses_durable_transcript():
    api = _api()
    durable = {"extracted_text": "Regional GM, Middle East at Yalla Pizza. Ajman, Ras Al Khaimah.",
               "display_label": "Job Description", "filename": "IMG_1793.png"}
    res, captured = _run_followup(api, "Extract the most important information from this document.", "u@test", durable)
    assert "Yalla Pizza" in captured["override"]            # transcript fed to the AI
    assert "Yalla Pizza" in res["message"]


def test_button_summarize_uses_durable_transcript():
    api = _api()
    durable = {"extracted_text": "Regional GM at Yalla Pizza.", "display_label": "Job Description"}
    _res, captured = _run_followup(api, "Summarize this document for me.", "u@test", durable)
    assert "Yalla Pizza" in captured["override"]


def test_public_user_session_durable_transcript():
    """Public web sessions (public:web-*) must retrieve their own durable transcript."""
    api = _api()
    durable = {"extracted_text": "Public session job text", "display_label": "Job Description"}
    _res, captured = _run_followup(api, "Summarize this document for me.", "public:web-abc123", durable)
    assert captured["uid"] == "public:web-abc123"
    assert "Public session job text" in captured["override"]


# ── Typed open-ended question is grounded via the durable transcript ──────────

def test_typed_question_grounded_by_durable_transcript():
    """'what do you think of this job?' is open-ended → AI path; _build_openai_context
    must inject the durable transcript so the AI answers from the screenshot."""
    api = _api()
    durable = {"extracted_text": "Regional GM at Yalla Pizza, Ajman.",
               "display_label": "Job Description", "filename": "IMG_1793.png"}
    with (
        patch.object(api, "_collect_uploaded_documents", return_value=[]),
        patch.object(api, "_get_recent_messages", return_value=[]),
        patch.object(api, "_recent_jobs_summary", return_value=None),
        patch.object(api, "_get_recent_context", return_value={}),  # ephemeral empty
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document", return_value=durable),
    ):
        ctx = api._build_openai_context(None, user_id="u@test")
    assert ctx["last_uploaded_document"]["transcribed_text"] == "Regional GM at Yalla Pizza, Ajman."
    assert ctx["last_uploaded_document"]["type"] == "Job Description"


def test_low_confidence_unknown_still_uses_text():
    """Acceptance #9: classification unknown/0% but extracted_text present → still used."""
    api = _api()
    durable = {"extracted_text": "Job listing text here", "display_label": "Document", "document_type": "unknown"}
    _res, captured = _run_followup(api, "Extract the most important information from this document.", "u@test", durable)
    assert "Job listing text here" in captured["override"]
