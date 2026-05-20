"""Reusable admin-route guard helpers.

These helpers keep role enforcement logic framework-light and testable. Routers
can call `require_admin_user(...)` directly, and the application middleware can
use `is_admin_path(...)` when centralizing enforcement for admin route prefixes.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException

ADMIN_ROUTE_PREFIXES = ("/api/v1/rico/admin/",)


def is_admin_path(path: str) -> bool:
    """Return True when the request path belongs to the Rico admin surface."""
    return any((path or "").startswith(prefix) for prefix in ADMIN_ROUTE_PREFIXES)


def require_admin_user(user: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Validate a hydrated user mapping has the admin role.

    Raises:
        HTTPException: 401 when no user is present; 403 when role is not admin.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return user
