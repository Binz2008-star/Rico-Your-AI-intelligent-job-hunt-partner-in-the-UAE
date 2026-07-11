"""Fail-closed login gate for Rico's opt-in pre-launch mode.

The normal FastAPI access middleware can authorize authenticated requests from
JWT state, but login happens before a JWT exists. This ASGI middleware inspects
and replays only the login request body so a non-allowlisted account is rejected
before credential verification side effects or an auth cookie can be issued.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.services.launch_mode import is_internal_email, is_waitlist_mode

_LOGIN_PATH = "/api/v1/auth/login"


class PrelaunchLoginGateMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope.get("type") != "http"
            or not is_waitlist_mode()
            or scope.get("method", "GET").upper() != "POST"
            or scope.get("path") != _LOGIN_PATH
        ):
            await self.app(scope, receive, send)
            return

        messages: list[Message] = []
        body_parts: list[bytes] = []
        while True:
            message = await receive()
            messages.append(message)
            if message.get("type") == "http.request":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            else:
                break

        email: str | None = None
        try:
            payload: Any = json.loads(b"".join(body_parts) or b"{}")
            if isinstance(payload, dict) and payload.get("email") is not None:
                email = str(payload["email"])
        except (TypeError, ValueError, UnicodeDecodeError):
            # Invalid bodies are replayed to FastAPI so the existing validation
            # contract (usually 422) remains authoritative.
            pass

        if email is not None and not is_internal_email(email):
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": "Rico is currently available by private invitation.",
                    "code": "prelaunch_access_required",
                },
            )
            await response(scope, receive, send)
            return

        iterator = iter(messages)

        async def replay_receive() -> Message:
            try:
                return next(iterator)
            except StopIteration:
                return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)
