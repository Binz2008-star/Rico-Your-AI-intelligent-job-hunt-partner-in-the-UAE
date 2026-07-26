"""The documents contract must not change what the chat file-list answer says.

The chat "which files do I have" answer is deterministic and reads the file
store directly (``RicoChatAPI._collect_uploaded_documents`` ->
``_handle_file_list_query``). The files surface reads the same rows and, since
the documents contract landed, derives its quota split from
``src.domain.documents``. Two readers, one underlying inventory — so the
question "did the contract move the chat answer" has to be answered by
execution, not by reading the diff.

These tests answer it three ways:

1. **Sabotage.** Make every contract entry point raise, then run the chat
   answer. Identical output proves the chat path does not consult the contract
   today. If a later change wires it in, this test fails and forces the
   behaviour question to be asked out loud.
2. **Structure.** Neither the chat module nor the routing gates import the
   contract.
3. **Agreement.** Over the same rows, what the contract says the user has —
   the document set, and what the storage limits count — matches what the chat
   lists. Where the two deliberately differ (the legacy projection is shown to
   the user but occupies no storage), that asymmetry is asserted rather than
   left implicit.

All rows are synthetic; no database, no AI provider, no profile of a real user.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.domain.documents import DocumentKind, inventory_from_rows, legacy_cv_record
from src.rico_chat_api import RicoChatAPI

_FILE_LIST_QUESTION = "show me my uploaded files"


# ── synthetic fixtures ────────────────────────────────────────────────────

def _row(doc_id: str, doc_type: str, *, is_primary: bool = False, size: int = 2048) -> dict:
    return {
        "id": doc_id,
        "user_id": "user-1",
        "filename": f"{doc_id}.pdf",
        "original_filename": f"{doc_id}.pdf",
        "doc_type": doc_type,
        "file_size": size,
        "label": None,
        "is_primary": is_primary,
        "skills_count": 4 if doc_type == "cv" else 0,
        "years_experience": 3 if doc_type == "cv" else None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


STORED_ONLY = [
    _row("cv-primary", "cv", is_primary=True),
    _row("cover-1", "cover_letter"),
    _row("other-1", "other"),
]

STORED_WITHOUT_ACTIVE_CV = [
    _row("cover-1", "cover_letter"),
    _row("id-1", "identity_document"),
]

PROFILE_WITH_CV = SimpleNamespace(
    cv_filename="profile-cv.pdf",
    cv_text="synthetic parsed text",
    cv_status="parsed",
    cv_extracted_at="2026-01-01T00:00:00+00:00",
    skills=["a", "b"],
    years_experience=3,
    current_role="analyst",
)


def _api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._memory = MagicMock()
    return api


def _chat_file_list(rows, profile=None) -> dict:
    """Run the real chat file-list path over synthetic rows.

    Only the store and the profile read are mocked, so the projection and the
    rendering under test are the production ones.
    """
    fake_db = MagicMock()
    fake_db.available = True
    fake_db.list_user_documents.return_value = list(rows)

    api = _api()
    with patch("src.rico_db.RicoDB", return_value=fake_db), \
         patch("src.rico_chat_api.get_profile", return_value=profile), \
         patch.object(api, "_append_chat"):
        result = api._handle_file_list_query("user-1", _FILE_LIST_QUESTION)
    assert result is not None, "the fixture question must reach the file-list handler"
    return result


# ── 1. sabotage: the contract cannot influence the chat answer ────────────

def _raise(*_args, **_kwargs):  # pragma: no cover - only reached on regression
    raise AssertionError("the chat file-list path must not consult the documents contract")


class TestContractCannotMoveTheChatAnswer:
    @pytest.mark.parametrize(
        "rows,profile",
        [
            (STORED_ONLY, None),
            (STORED_WITHOUT_ACTIVE_CV, PROFILE_WITH_CV),
            ([], PROFILE_WITH_CV),
            ([], None),
        ],
    )
    def test_answer_is_identical_with_every_contract_entry_point_broken(self, rows, profile):
        baseline = _chat_file_list(rows, profile)

        with patch("src.domain.documents.inventory.build_inventory", _raise), \
             patch("src.domain.documents.adapters.inventory_from_rows", _raise), \
             patch("src.domain.documents.adapters.record_from_stored_row", _raise), \
             patch("src.domain.documents.adapters.records_from_stored_rows", _raise):
            sabotaged = _chat_file_list(rows, profile)

        assert sabotaged == baseline

    def test_the_rendered_message_text_is_identical_too(self):
        baseline = _chat_file_list(STORED_ONLY)
        with patch("src.domain.documents.inventory.build_inventory", _raise):
            sabotaged = _chat_file_list(STORED_ONLY)
        assert sabotaged["message"] == baseline["message"]
        assert sabotaged["type"] == "file_list" == baseline["type"]


# ── 2. structure: no import edge exists ───────────────────────────────────

class TestNoImportEdge:
    @pytest.mark.parametrize(
        "module_path",
        ["src/rico_chat_api.py", "src/rico/intent/gates.py"],
    )
    def test_chat_and_gate_modules_do_not_import_the_contract(self, module_path):
        source = Path(module_path).read_text(encoding="utf-8")
        assert "domain.documents" not in source, (
            f"{module_path} now reaches into the documents contract; the chat "
            "file-list answer would no longer be independent of it"
        )


# ── 3. agreement: same rows, same documents ───────────────────────────────

class TestChatAndContractDescribeTheSameInventory:
    def test_same_documents_in_the_same_order(self):
        chat = _chat_file_list(STORED_ONLY)
        inventory = inventory_from_rows(STORED_ONLY)

        assert [f["filename"] for f in chat["files"]] == [
            r.filename for r in inventory.records
        ]
        assert [f["doc_type"] for f in chat["files"]] == [
            r.kind.value for r in inventory.records
        ]

    def test_the_cv_the_chat_marks_active_is_the_contract_active_cv(self):
        chat = _chat_file_list(STORED_ONLY)
        inventory = inventory_from_rows(STORED_ONLY)

        chat_active = [f for f in chat["files"] if f["doc_type"] == "cv" and f["is_primary"]]
        assert len(chat_active) == 1
        assert inventory.active_cv is not None
        assert chat_active[0]["filename"] == inventory.active_cv.filename

    def test_quota_counts_match_the_stored_files_the_chat_lists(self):
        chat = _chat_file_list(STORED_ONLY)
        counts = inventory_from_rows(STORED_ONLY).quota_counts

        listed_stored = [f for f in chat["files"] if not f.get("is_legacy")]
        assert counts.cv == sum(1 for f in listed_stored if f["doc_type"] == "cv")
        assert counts.other == sum(1 for f in listed_stored if f["doc_type"] != "cv")
        assert counts.total == len(listed_stored)

    def test_identity_only_users_are_described_the_same_way(self):
        rows = [_row("id-1", "identity_document")]
        chat = _chat_file_list(rows)
        inventory = inventory_from_rows(rows)

        assert inventory.has_only_identity_documents is True
        assert inventory.has_cv is False
        # The chat answer says so in words; assert the substantive claim, not
        # the wording, so copy edits do not fail this test.
        assert len(chat["files"]) == 1
        assert chat["files"][0]["doc_type"] == "identity_document"

    def test_the_legacy_projection_is_listed_to_the_user_but_never_counted(self):
        """The one deliberate asymmetry between the two readers.

        The chat lists the profile-grounded CV so the user sees their active
        CV; the contract excludes it from quota because no row occupies
        storage. Asserted here so neither side can drift into the other's
        answer unnoticed.
        """
        chat = _chat_file_list(STORED_WITHOUT_ACTIVE_CV, PROFILE_WITH_CV)

        legacy_entries = [f for f in chat["files"] if f.get("is_legacy")]
        assert len(legacy_entries) == 1
        assert legacy_entries[0]["doc_type"] == "cv"

        # The contract, given the same projection, agrees it is the active CV…
        inventory = inventory_from_rows(STORED_WITHOUT_ACTIVE_CV)
        with_legacy = inventory_from_rows(STORED_WITHOUT_ACTIVE_CV)
        combined = type(with_legacy)(
            records=(legacy_cv_record(filename="profile-cv.pdf"),) + with_legacy.records
        )
        assert combined.active_cv is not None
        assert combined.active_cv.kind is DocumentKind.CV
        assert combined.active_cv.filename == "profile-cv.pdf"

        # …and still counts only what is stored.
        assert combined.quota_counts == inventory.quota_counts
        assert combined.quota_counts.total == len(STORED_WITHOUT_ACTIVE_CV)
