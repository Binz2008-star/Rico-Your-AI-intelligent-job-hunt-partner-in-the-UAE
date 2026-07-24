# -*- coding: utf-8 -*-
"""Offline multi-user chat harness.

Drives the REAL production entry point ``RicoChatAPI.process_message`` — the
same classify -> dispatch -> persist -> respond path the ``/api/v1/rico/chat``
handler uses — with every external dependency patched out:

  * profile store        -> an in-memory dict per user (real upsert -> get
                            round-trips, so persistence is genuinely exercised)
  * recent-context store -> an in-memory dict per user (multi-turn pending
                            state, e.g. the profile-update confirmation, survives
                            across turns even though each turn builds a fresh
                            ``RicoChatAPI`` — mirroring production's durable store)
  * job search           -> canned ``live_verified`` results (no JSearch)
  * AI provider          -> a deterministic, neutral responder (no DeepSeek /
                            OpenAI / HuggingFace; no network, no flaky fallbacks)
  * embeddings / gating  -> disabled

No live DB, no live provider, no credentials, no production data. This lets a
whole matrix of user states x conversation cases run in ``pytest`` deterministically.

The harness is deliberately thin and assertion-free: tests own the assertions.
"""
from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Any, Optional
from unittest.mock import PropertyMock, patch

from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile


# --- Seed profiles for the required user states --------------------------------
#
# Each factory returns the field overrides for one user state. ``None`` means
# "no profile row at all" (guest / never-onboarded), which the harness models by
# never seeding the user.

def _base_profile_fields(**over: Any) -> dict[str, Any]:
    fields = {
        "cv_status": "parsed",
        "cv_filename": "cv.pdf",
        "target_roles": ["Operations Manager"],
        "skills": ["operations", "logistics"],
        "years_experience": 6,
        "preferred_cities": ["Dubai"],
        "current_role": "Operations Manager",
        "current_company": "Eco Technology",
    }
    fields.update(over)
    return fields


#: state name -> profile field overrides (or None for "no profile row").
USER_STATES: dict[str, Optional[dict[str, Any]]] = {
    # 1. Existing profile with stale target_roles (the TC-2 starting point).
    "stale_roles": _base_profile_fields(target_roles=["Operations Manager"]),
    # 2. Profile with no target_roles yet.
    "empty_roles": _base_profile_fields(target_roles=[]),
    # 3. Profile already set to ESG / Compliance target_roles.
    "esg_compliance": _base_profile_fields(
        target_roles=["ESG Manager", "Compliance Manager"],
        skills=["compliance", "esg", "audit"],
    ),
    # 4. CV / profile context present (rich profile).
    "cv_present": _base_profile_fields(),
    # 5. No CV / no profile data (signed up, never onboarded).
    "no_cv": {
        "cv_status": "none",
        "cv_filename": "",
        "target_roles": [],
        "skills": [],
        "current_role": "",
    },
    # 6/7. Arabic and English message states reuse a normal profile — the
    #      difference is the message language, exercised by the tests.
    "arabic": _base_profile_fields(target_roles=["Operations Manager"]),
    "english": _base_profile_fields(target_roles=["Operations Manager"]),
    # 8. Guest / public-like: no profile row exists for this user at all.
    "guest": None,
}


class ChatHarness:
    """A per-test conversation driver over the real ``RicoChatAPI``.

    Usage::

        h = ChatHarness()
        h.seed("u@test", target_roles=["Operations Manager"])
        res = h.say("u@test", "update my target roles to ESG Manager and Compliance Manager")
        res = h.say("u@test", "yes")
        assert h.profile("u@test").target_roles == ["ESG Manager", "Compliance Manager"]
    """

    def __init__(self) -> None:
        self._profiles: dict[str, RicoProfile] = {}
        self._rctx: dict[str, dict[str, Any]] = {}
        #: role passed to the (stubbed) live job search, most-recent last.
        self.searched_roles: list[str] = []
        #: prompt strings handed to the (stubbed) AI provider, most-recent last.
        self.ai_prompts: list[str] = []
        #: user_id -> list of document dicts (id, doc_type, is_primary,
        #: filename, years_experience, ...). Empty for every existing test
        #: that never calls seed_documents(), so this is purely additive.
        self._documents: dict[str, list[dict[str, Any]]] = {}

    # -- seeding -----------------------------------------------------------------

    def seed(self, user_id: str, **fields: Any) -> RicoProfile:
        """Create (or replace) an in-memory profile for ``user_id``."""
        profile = RicoProfile(user_id=user_id)
        for key, value in fields.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self._profiles[user_id] = profile
        return profile

    def seed_state(self, user_id: str, state: str) -> Optional[RicoProfile]:
        """Seed one of the named :data:`USER_STATES` (``None`` -> no profile row)."""
        overrides = USER_STATES[state]
        if overrides is None:
            self._profiles.pop(user_id, None)  # guest: ensure no row
            return None
        return self.seed(user_id, **overrides)

    def profile(self, user_id: str) -> Optional[RicoProfile]:
        return self._profiles.get(user_id)

    def seed_documents(self, user_id: str, docs: "list[dict[str, Any]]") -> None:
        """Seed synthetic ``user_documents`` rows (id, doc_type, is_primary,
        filename, years_experience, ...) for the active-CV switch tests.
        Each dict is stored as-is (mutated in place by _set_primary_document
        to flip is_primary), so pass fresh dicts per test."""
        self._documents[user_id] = list(docs)

    def documents(self, user_id: str) -> "list[dict[str, Any]]":
        return list(self._documents.get(user_id, []))

    # -- patched dependency implementations -------------------------------------

    def _get_profile(self, user_id: str) -> Optional[RicoProfile]:
        return self._profiles.get(user_id)

    def _upsert_profile(self, user_id: str, updates: dict[str, Any]) -> RicoProfile:
        profile = self._profiles.get(user_id)
        if profile is None:
            profile = RicoProfile(user_id=user_id)
            self._profiles[user_id] = profile
        for key, value in (updates or {}).items():
            if value is not None and hasattr(profile, key):
                setattr(profile, key, value)
        return profile

    def _onboarding_complete(self, user_id: str) -> bool:
        profile = self._profiles.get(user_id)
        if profile is None:
            return False
        return bool(
            getattr(profile, "target_roles", None)
            or getattr(profile, "cv_filename", None)
            or getattr(profile, "cv_status", None) == "parsed"
        )

    # recent-context store (bound-style: patched onto the class, so ``self`` here
    # is the RicoChatAPI instance, not the harness — we route to harness state via
    # the closure captured in :meth:`_patches`).

    def _collect_documents(self, user_id: str, _profile: Any) -> "list[dict[str, Any]]":
        return list(self._documents.get(user_id, []))

    def _activate_cv(self, user_id: str, doc_id: str) -> "dict[str, Any] | None":
        """Mirrors RicoDB.set_primary_document's exclusivity contract:
        exactly one CV row is_primary=True per user after a successful call,
        None if doc_id doesn't match a stored CV for this user."""
        docs = self._documents.get(user_id, [])
        target = next(
            (d for d in docs if str(d.get("id")) == str(doc_id) and d.get("doc_type") == "cv"),
            None,
        )
        if target is None:
            return None
        for d in docs:
            if d.get("doc_type") == "cv":
                d["is_primary"] = (str(d.get("id")) == str(doc_id))
        return dict(target)

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_roles.append(role)
        return FetchResult(
            items=[{
                "title": role or "Role",
                "company": "ACME",
                "apply_url": "https://acme.example/jobs/1",
                "location": "Dubai, UAE",
            }],
            provider="jsearch",
        )

    def _ai_respond(self, prompt: Any, user_context: Any = None,
                    language: Any = None, **_kw: Any) -> dict[str, Any]:
        # Neutral, deterministic reply. Intentionally free of "search"/"now"/
        # promise language so it never trips the promise-only-reply heuristic that
        # would arm a pending job search.
        self.ai_prompts.append(str(prompt))
        return {
            "message": "Here to help with your UAE career questions.",
            "response_source": "test-stub",
            "provider": "test",
        }

    # -- driving a turn ----------------------------------------------------------

    def say(self, user_id: str, message: str, language: Optional[str] = None) -> dict[str, Any]:
        """Send one user message through the real handler and return the response."""
        harness = self

        def _get_rctx(_self: Any, uid: str) -> dict[str, Any]:
            return dict(harness._rctx.get(uid) or {})

        def _store_rctx(_self: Any, uid: str, ctx: dict[str, Any]) -> None:
            harness._rctx[uid] = dict(ctx or {})

        from src.rico_chat_api import RicoChatAPI

        with ExitStack() as stack:
            p = stack.enter_context
            # Hermetic guarantee: force every repo path onto its in-memory
            # fallback by making RicoDB report unavailable. Repos gate on
            # ``RicoDB.available`` (== bool(DATABASE_URL and psycopg2)) and return
            # ``None`` / raise instantly when it is False. Without this, an ambient
            # or CI ``DATABASE_URL`` pointing at an unreachable Postgres makes
            # untouched paths (tracked-application lookup, chat history) attempt
            # real connections and hang on timeouts — turning "offline" tests into
            # 30s+ network-bound ones. Patching the property (not just the env) is
            # cache-proof: modules that captured the DSN at import time still see
            # the DB as unavailable. Also drop REDIS_URL so slowapi stays in-memory.
            # Rico has two independent DB layers, each with its own DSN gate:
            #   * src.rico_db.RicoDB  -> the ``available`` property
            #   * src.db              -> the module-level ``DB_ENABLED`` flag
            # Both must be forced off, or the untouched layer keeps calling
            # psycopg2.connect against the (unreachable) CI DSN.
            p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
            p(patch("src.db.DB_ENABLED", False))
            p(patch.dict("os.environ", {}, clear=False))
            os.environ.pop("REDIS_URL", None)
            p(patch("src.rico_chat_api.get_profile", side_effect=self._get_profile))
            p(patch("src.repositories.profile_repo.get_profile", side_effect=self._get_profile))
            p(patch("src.rico_chat_api.upsert_profile", side_effect=self._upsert_profile))
            p(patch("src.repositories.profile_repo.upsert_profile", side_effect=self._upsert_profile))
            p(patch("src.rico_chat_api.is_onboarding_complete", side_effect=self._onboarding_complete))
            p(patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=self._search))
            p(patch("src.rico_chat_api.RicoChatAPI._collect_documents_detailed", side_effect=self._collect_documents))
            p(patch("src.rico_chat_api.RicoChatAPI._activate_cv_document", side_effect=self._activate_cv))
            p(patch("src.rico_openai_agent.RicoOpenAIAgent.respond", side_effect=self._ai_respond))
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", _get_rctx))
            p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context", _store_rctx))
            p(patch("src.llm_scorer._embed", return_value=None))
            p(patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None))
            api = RicoChatAPI()
            return api.process_message(user_id, message, language=language)

    # -- convenience read side ---------------------------------------------------

    def resolve_search_role(self, user_id: str) -> tuple[Any, list[Any], str]:
        """Return ``_resolve_profile_search_role`` for the current profile.

        This is the deterministic seam a profile-first search uses to pick which
        role to search — the cleanest place to assert TC-2 propagation (which
        role(s) the NEXT search will target) without a live job provider.
        """
        from src.rico_chat_api import RicoChatAPI
        return RicoChatAPI._resolve_profile_search_role(RicoChatAPI(), self._profiles.get(user_id))
