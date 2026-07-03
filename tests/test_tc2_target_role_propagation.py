"""Regression tests for TC-2 target-role propagation.

Root cause (2026-07-03 live QA): confirming new target roles in chat did not
change the next search. Two defects in the live path:

  1. Classifier: `_PROFILE_UPDATE_RE` matched only the singular `role`/`title`.
     "update my target roles to ESG Manager and Compliance Manager" fell through
     to `unknown`, so it never reached the profile-update handler.
  2. Extractor + persist: the router emitted a singular `target_role` key, which
     is not a field on `RicoProfile` (canonical field is `target_roles`, a list)
     and is therefore silently dropped by `upsert_profile`'s field whitelist —
     so even a correctly-classified singular update persisted nothing.

Fix: recognize plural target-role updates and always emit the canonical
`target_roles` list (supporting multiple roles).

These tests exercise the real classifier + router + the whitelist rule, no DB.
"""

from dataclasses import fields

from src.agent.intelligence.intent_classifier import classify_intent
from src.rico_intent_router import route as _route, _split_target_roles
from src.rico_agent import RicoProfile


def _intent(msg: str) -> str:
    r = classify_intent(msg)
    return str(getattr(r, "intent", r))


def _prefs(msg: str) -> dict:
    r = _route(msg, user_id="u", context={})
    return getattr(r, "tool_args", {}).get("preferences", {})


_PROFILE_FIELDS = {f.name for f in fields(RicoProfile)}


def _persisted(prefs: dict) -> dict:
    """Mirror upsert_profile's field-whitelist filter."""
    return {k: v for k, v in prefs.items() if k in _PROFILE_FIELDS and v is not None}


# --- 1. Classifier routes plural target-role updates to profile_update ----------

def test_plural_target_roles_update_classifies_as_profile_update():
    assert _intent("update my target roles to ESG Manager and Compliance Manager") == "profile_update"
    assert _intent("change my target roles to ESG Manager and Compliance Manager") == "profile_update"


def test_singular_target_role_update_still_classifies_as_profile_update():
    assert _intent("set my target role to ESG Manager") == "profile_update"
    assert _intent("update my target role to Compliance Manager") == "profile_update"


def test_multi_role_search_intent_is_not_hijacked():
    # "I want to target X and Y roles" is a search, not a profile update — the
    # profile-update regex requires an update/change/set verb, so this is unchanged.
    assert _intent("I want to target ESG Manager and Compliance Manager roles") == "job_search_multi_role"


# --- 2. Extractor emits the canonical target_roles list (both roles) ------------

def test_extractor_captures_both_target_roles():
    prefs = _prefs("update my target roles to ESG Manager and Compliance Manager")
    assert "target_roles" in prefs
    assert [r.lower() for r in prefs["target_roles"]] == ["esg manager", "compliance manager"]
    # Never the singular key that the whitelist drops.
    assert "target_role" not in prefs


def test_extractor_handles_three_roles_comma_and_and():
    prefs = _prefs("change my target roles to ESG Manager, Compliance Manager and Sustainability Lead")
    assert [r.lower() for r in prefs["target_roles"]] == [
        "esg manager", "compliance manager", "sustainability lead",
    ]


def test_singular_update_emits_one_item_list_not_singular_key():
    prefs = _prefs("set my target role to ESG Manager")
    assert "target_role" not in prefs
    assert [r.lower() for r in prefs["target_roles"]] == ["esg manager"]


# --- 3. The emitted prefs survive the upsert field whitelist --------------------

def test_target_roles_survives_whitelist_singular_key_would_not():
    prefs = _prefs("update my target roles to ESG Manager and Compliance Manager")
    persisted = _persisted(prefs)
    assert persisted.get("target_roles"), "target_roles must persist"
    # Guard: the canonical list field exists; the singular one does not.
    assert "target_roles" in _PROFILE_FIELDS
    assert "target_role" not in _PROFILE_FIELDS


# --- 4. Splitter unit behavior --------------------------------------------------

def test_split_target_roles_variants():
    assert _split_target_roles("ESG Manager and Compliance Manager") == ["Esg Manager", "Compliance Manager"]
    assert _split_target_roles("ESG Manager, Compliance Manager") == ["Esg Manager", "Compliance Manager"]
    assert _split_target_roles("ESG Manager & Compliance Manager roles") == ["Esg Manager", "Compliance Manager"]
    assert _split_target_roles("") == []
    # De-dupes case-insensitively.
    assert _split_target_roles("ESG Manager and esg manager") == ["Esg Manager"]
