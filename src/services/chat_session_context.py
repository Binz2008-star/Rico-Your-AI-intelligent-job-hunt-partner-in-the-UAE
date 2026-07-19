"""
src/services/chat_session_context.py

Ambient chat-session (thread) context for multi-session conversations (#1193).

One user can hold many parallel chat threads. Rather than threading a
session_id argument through the ~60 legacy ``_append_chat`` call sites in
``rico_chat_api.py``, the API router sets the active session for the current
request here, and the single DB write funnel (``chat_service.db_append_chat``)
plus the DB history reader (``chat_service.get_chat_history``) consult it.

Semantics:
  * ``DEFAULT_SESSION`` ("default") — the legacy thread. Writes store
    session_id NULL, reads filter ``session_id IS NULL``. Every message
    written before multi-session existed lives here.
  * A UUID string — a named thread. Writes stamp the UUID, reads filter on it.
  * Unset (None) — pre-session behavior: NULL writes, unfiltered reads.
    Public/guest chat and any old client that never sends a session_id land
    here, unchanged.

Streaming caveat: Starlette drives sync response generators through a
threadpool that copies the *ASGI task's* context per ``next()`` call, so a
ContextVar set in the endpoint function does NOT survive into (or across)
generator segments. ``run_generator_with_session`` pins one
``contextvars.Context`` and resumes the wrapped generator inside it every
time, so the active session holds for every segment of an SSE stream.
"""
from __future__ import annotations

import contextvars
import re
import uuid
from typing import Any, Generator, Iterator, Optional

DEFAULT_SESSION = "default"

_MAX_SESSION_ID_LEN = 64

_active_chat_session: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "active_chat_session", default=None
)


def normalize_chat_session_id(value: Optional[str]) -> Optional[str]:
    """Validate and canonicalize a client-supplied chat session id.

    Returns ``DEFAULT_SESSION``, a canonical lowercase UUID string, or None
    for missing input. Raises ValueError for anything else — the id is used
    in SQL filters (parameterized, but a UUID column comparison against a
    non-UUID string would error) and must never be attacker-shaped.
    """
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) > _MAX_SESSION_ID_LEN:
        raise ValueError("session_id too long")
    if candidate.lower() == DEFAULT_SESSION:
        return DEFAULT_SESSION
    try:
        return str(uuid.UUID(candidate))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("session_id must be 'default' or a UUID")


def set_active_chat_session(session_id: Optional[str]) -> contextvars.Token:
    """Set the active session for the current execution context.

    Callers should hold the returned token and call
    ``reset_active_chat_session`` in a finally block (request-scoped use).
    """
    return _active_chat_session.set(session_id)


def reset_active_chat_session(token: contextvars.Token) -> None:
    try:
        _active_chat_session.reset(token)
    except ValueError:
        # Token from another context (e.g. threadpool hop) — nothing to undo:
        # that context is gone along with its variable assignment.
        pass


def get_active_chat_session() -> Optional[str]:
    return _active_chat_session.get()


def run_generator_with_session(
    inner: Generator[Any, None, None], session_id: Optional[str]
) -> Iterator[Any]:
    """Drive ``inner`` so every resumption runs with the session var set.

    A plain ContextVar set before returning a StreamingResponse does not reach
    the generator (each segment executes in a fresh copy of the ASGI task's
    context). Here one Context is created up front and every ``next()`` — and
    the final ``close()`` — runs inside it, so writes performed mid-stream
    (user turn before the provider call, assistant turn in the finally block)
    are stamped with the correct thread.
    """
    ctx = contextvars.copy_context()
    ctx.run(_active_chat_session.set, session_id)
    try:
        while True:
            try:
                yield ctx.run(inner.__next__)
            except StopIteration:
                return
    finally:
        try:
            ctx.run(inner.close)
        except Exception:
            pass


_SESSION_TITLE_MAX = 80
_WS_RE = re.compile(r"\s+")


def derive_session_title(first_user_message: Optional[str]) -> Optional[str]:
    """Trimmed, whitespace-collapsed first user turn — the thread's title.

    Pure and deliberately dumb: never invents content, returns None when the
    thread has no real user turn (the frontend shows its own fallback label).
    """
    if not first_user_message:
        return None
    title = _WS_RE.sub(" ", str(first_user_message)).strip()
    if not title:
        return None
    if len(title) > _SESSION_TITLE_MAX:
        title = title[: _SESSION_TITLE_MAX - 1].rstrip() + "…"
    return title
