"""Regression coverage for production Career Memory activation.

The public runtime passes external identities (usually email addresses), while
``rico_agent_settings.user_id`` is a UUID foreign key. These tests prove that
Career Memory resolves the canonical UUID before writing and preserves the
existing bounded, per-user JSONB history.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.services import career_memory


class FakeRicoDB:
    available = True

    def __init__(self) -> None:
        self.aliases = {
            "alice@example.com": "11111111-1111-1111-1111-111111111111",
            "alice-external": "11111111-1111-1111-1111-111111111111",
            "bob@example.com": "22222222-2222-2222-2222-222222222222",
        }
        self.settings = {
            self.aliases["alice@example.com"]: {"communication_style": "concise"},
            self.aliases["bob@example.com"]: {"communication_style": "professional"},
        }
        self.upsert_calls: list[tuple[str, dict]] = []

    def get_user_bundle(self, identity: str):
        db_user_id = self.aliases.get(identity, identity if identity in self.settings else None)
        if not db_user_id:
            return None
        return {
            "id": db_user_id,
            "settings": deepcopy(self.settings.get(db_user_id, {})),
        }

    def upsert_settings(self, db_user_id: str, settings: dict):
        if db_user_id not in self.settings:
            raise AssertionError("write did not use a canonical Rico user UUID")
        self.upsert_calls.append((db_user_id, deepcopy(settings)))
        self.settings[db_user_id] = {
            **self.settings[db_user_id],
            **deepcopy(settings),
        }
        return {"user_id": db_user_id, "settings": deepcopy(self.settings[db_user_id])}


@pytest.fixture
def fake_db() -> FakeRicoDB:
    return FakeRicoDB()


def _record(fake_db: FakeRicoDB, identity: str, *, action: str = "save") -> bool:
    with (
        patch.object(career_memory, "_new_db", return_value=fake_db),
        patch.object(
            career_memory,
            "time",
            SimpleNamespace(time=lambda: 1_750_000_000),
        ),
    ):
        return career_memory.record_action(
            identity,
            action,
            {
                "id": "job-123",
                "title": "HSE Manager",
                "company": "Acme",
            },
        )


@pytest.mark.parametrize("identity", ["alice@example.com", "alice-external"])
def test_record_action_resolves_external_identity_to_uuid(fake_db: FakeRicoDB, identity: str):
    assert _record(fake_db, identity) is True

    assert fake_db.upsert_calls == [
        (
            "11111111-1111-1111-1111-111111111111",
            {
                "_cm": [{
                    "ts": 1_750_000_000,
                    "a": "save",
                    "co": "Acme",
                    "ti": "HSE Manager",
                    "jk": "job-123",
                }],
            },
        ),
    ]


def test_read_after_write_uses_same_canonical_user(fake_db: FakeRicoDB):
    assert _record(fake_db, "alice@example.com", action="apply") is True

    with patch("src.rico_db.RicoDB", return_value=fake_db):
        memory = career_memory.get_memory("alice@example.com")

    assert memory == [{
        "ts": 1_750_000_000,
        "a": "apply",
        "co": "Acme",
        "ti": "HSE Manager",
        "jk": "job-123",
    }]


def test_record_action_merges_history_without_overwriting_other_settings(fake_db: FakeRicoDB):
    alice_id = fake_db.aliases["alice@example.com"]
    fake_db.settings[alice_id]["_cm"] = [{
        "ts": 1,
        "a": "skip",
        "co": "Old Co",
        "ti": "Old Role",
        "jk": "old-job",
    }]

    assert _record(fake_db, "alice@example.com") is True

    assert fake_db.settings[alice_id]["communication_style"] == "concise"
    assert [entry["jk"] for entry in fake_db.settings[alice_id]["_cm"]] == [
        "old-job",
        "job-123",
    ]


def test_record_action_keeps_only_latest_200_entries(fake_db: FakeRicoDB):
    alice_id = fake_db.aliases["alice@example.com"]
    fake_db.settings[alice_id]["_cm"] = [
        {"ts": i, "a": "save", "co": "Co", "ti": "Role", "jk": f"job-{i}"}
        for i in range(200)
    ]

    assert _record(fake_db, "alice@example.com") is True

    memory = fake_db.settings[alice_id]["_cm"]
    assert len(memory) == 200
    assert memory[0]["jk"] == "job-1"
    assert memory[-1]["jk"] == "job-123"


def test_record_action_is_isolated_per_user(fake_db: FakeRicoDB):
    assert _record(fake_db, "alice@example.com") is True

    alice_id = fake_db.aliases["alice@example.com"]
    bob_id = fake_db.aliases["bob@example.com"]
    assert len(fake_db.settings[alice_id]["_cm"]) == 1
    assert "_cm" not in fake_db.settings[bob_id]

    assert _record(fake_db, "bob@example.com", action="skip") is True
    assert fake_db.settings[alice_id]["_cm"][0]["a"] == "save"
    assert fake_db.settings[bob_id]["_cm"][0]["a"] == "skip"


def test_write_failure_is_reported_without_raising(fake_db: FakeRicoDB, caplog):
    def fail_write(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    fake_db.upsert_settings = fail_write
    with caplog.at_level(logging.WARNING, logger="src.services.career_memory"):
        assert _record(fake_db, "alice@example.com") is False

    assert "career_memory: memory write failed" in caplog.text
    assert "alice@example.com" not in caplog.text


def test_missing_user_is_reported_without_creating_one(fake_db: FakeRicoDB, caplog):
    with (
        patch.object(career_memory, "_new_db", return_value=fake_db),
        caplog.at_level(logging.WARNING, logger="src.services.career_memory"),
    ):
        assert career_memory.record_action("missing@example.com", "save", {}) is False

    assert fake_db.upsert_calls == []
    assert "canonical user resolution returned no row" in caplog.text
    assert "missing@example.com" not in caplog.text
