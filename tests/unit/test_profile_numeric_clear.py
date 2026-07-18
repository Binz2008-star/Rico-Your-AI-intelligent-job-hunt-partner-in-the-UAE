"""Explicit-null clearing of nullable numeric profile fields (Profile track).

The PATCH /rico/profile chain previously made clearing impossible at three
layers: Pydantic collapsed explicit null into the omitted default, the repo
stripped None values, and the memory mirror skipped None. These tests pin the
new EXPLICIT clear channel:

- ``upsert_profile(..., clear_fields=...)`` writes JSON null into the profile
  JSONB for allowlisted numeric fields only (the ``||`` merge overwrites the
  key), and propagates the clear to the memory mirror;
- non-allowlisted names are ignored (defense in depth);
- plain None values in ``updates`` keep meaning "unchanged" for every
  existing caller;
- ``RicoMemoryStore.upsert_profile_from_dict(..., clear_fields=...)`` clears
  exactly the named fields on the mirrored profile.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.rico_agent import RicoProfile
from src.rico_memory import RicoMemoryStore
from src.repositories import profile_repo


def _run_upsert(updates, *, clear_fields=(), require_db=False):
    """Drive profile_repo.upsert_profile with a fully mocked DB + memory."""
    db = MagicMock()
    db.get_user_bundle.return_value = {"id": "db-uuid-1", "email": "user@x.com"}
    conn = MagicMock()

    @contextmanager
    def _fake_txn():
        yield conn

    mem = MagicMock()
    mem.upsert_profile_from_dict.return_value = MagicMock()

    with patch.object(profile_repo, "_db", return_value=db), \
         patch.object(profile_repo, "_db_transaction", _fake_txn), \
         patch.object(profile_repo, "_memory", return_value=mem):
        profile_repo.upsert_profile(
            "user@x.com", updates, require_db=require_db, clear_fields=clear_fields,
        )
    return db, mem


def test_clear_fields_write_json_null_for_each_numeric_field():
    for field in ("salary_expectation_aed", "minimum_salary_aed", "years_experience"):
        db, _ = _run_upsert({}, clear_fields=[field])
        assert db.upsert_profile.called, f"{field}: DB profile upsert must run"
        args, _kwargs = db.upsert_profile.call_args
        profile_data = args[1]
        assert field in profile_data and profile_data[field] is None, (
            f"{field}: expected explicit JSON null in profile_data, got {profile_data!r}"
        )


def test_clear_combines_with_regular_updates():
    db, _ = _run_upsert({"current_role": "Analyst"}, clear_fields=["years_experience"])
    args, _ = db.upsert_profile.call_args
    profile_data = args[1]
    assert profile_data["current_role"] == "Analyst"
    assert profile_data["years_experience"] is None


def test_non_allowlisted_clear_names_are_ignored():
    # "name" is a user-table field; "exclude_keywords" is a settings field;
    # "nonexistent" is garbage — none may produce a null write.
    db, mem = _run_upsert(
        {"current_role": "Analyst"},
        clear_fields=["name", "exclude_keywords", "nonexistent"],
    )
    args, _ = db.upsert_profile.call_args
    profile_data = args[1]
    assert "name" not in profile_data
    assert "exclude_keywords" not in profile_data
    assert "nonexistent" not in profile_data
    assert None not in profile_data.values()
    # and the mirror receives no clears either
    _, mkwargs = mem.upsert_profile_from_dict.call_args
    assert set(mkwargs.get("clear_fields") or ()) == set()


def test_plain_none_values_in_updates_still_mean_unchanged():
    db, _ = _run_upsert(
        {"salary_expectation_aed": None, "current_role": "Analyst"},
    )
    args, _ = db.upsert_profile.call_args
    profile_data = args[1]
    # None value WITHOUT the explicit clear channel is dropped, not written
    assert "salary_expectation_aed" not in profile_data


def test_clears_propagate_to_memory_mirror_after_require_db_commit():
    _, mem = _run_upsert({}, clear_fields=["minimum_salary_aed"], require_db=True)
    assert mem.upsert_profile_from_dict.called
    _, kwargs = mem.upsert_profile_from_dict.call_args
    assert set(kwargs.get("clear_fields") or ()) == {"minimum_salary_aed"}


def test_memory_mirror_clears_named_fields_only():
    store = RicoMemoryStore()
    seeded = RicoProfile(
        user_id="user@x.com",
        years_experience=8,
        salary_expectation_aed=20000,
        minimum_salary_aed=15000,
        current_role="Analyst",
    )
    with patch.object(store, "load_profile", return_value=seeded), \
         patch.object(store, "save_profile") as save_spy:
        result = store.upsert_profile_from_dict(
            "user@x.com",
            {"current_role": "Senior Analyst"},
            clear_fields=["years_experience"],
        )
    assert result.years_experience is None
    assert result.salary_expectation_aed == 20000  # untouched
    assert result.minimum_salary_aed == 15000  # untouched
    assert result.current_role == "Senior Analyst"
    assert save_spy.called


def test_memory_mirror_none_in_updates_still_means_unchanged():
    store = RicoMemoryStore()
    seeded = RicoProfile(user_id="user@x.com", years_experience=8)
    with patch.object(store, "load_profile", return_value=seeded), \
         patch.object(store, "save_profile"):
        result = store.upsert_profile_from_dict(
            "user@x.com", {"years_experience": None},
        )
    assert result.years_experience == 8
