"""
src/services/agentic_ui_composer.py

Maps RuntimeResult → RicoAgenticUi.

Single authoritative place for all Career OS UI artifact mappings. Called from
_finalize() in rico_chat_api.py so no other code path needs to know about the
agentic_ui schema.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compose(result: Any) -> Any | None:
    """Return a RicoAgenticUi if the result carries UI artifacts, else None."""
    if result is None:
        return None

    data = getattr(result, "data", {}) or {}
    components: dict[str, Any] = {}

    if pr := data.get("permission_request"):
        components["permission_request"] = pr

    if actions := data.get("actions"):
        components["actions"] = actions

    if proposed := data.get("proposed_changes"):
        components["proposed_changes"] = proposed

    if attachment := data.get("attachment_analysis"):
        components["attachment_analysis"] = attachment

    if progress := data.get("progress"):
        components["progress"] = progress

    if not components:
        return None

    try:
        from src.schemas.chat import RicoAgenticUi
        return RicoAgenticUi(**components)
    except Exception:
        logger.debug("agentic_ui_composer: failed to build RicoAgenticUi", exc_info=True)
        return None
