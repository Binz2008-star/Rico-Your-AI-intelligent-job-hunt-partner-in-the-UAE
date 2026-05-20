import pytest
from fastapi import HTTPException

from src.api.admin_guard import is_admin_path, require_admin_user


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/rico/admin/health/ai-provider",
        "/api/v1/rico/admin/users",
        "/api/v1/rico/admin/system/status",
    ],
)
def test_is_admin_path_accepts_admin_prefixes(path):
    assert is_admin_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/rico/chat",
        "/api/v1/rico/profile",
        "/health",
        "",
    ],
)
def test_is_admin_path_rejects_non_admin_paths(path):
    assert is_admin_path(path) is False


def test_require_admin_user_accepts_admin_role():
    user = {"email": "admin@example.com", "role": "admin"}
    assert require_admin_user(user) == user


@pytest.mark.parametrize(
    "user,expected_status",
    [
        (None, 401),
        ({"email": "user@example.com", "role": "user"}, 403),
        ({"email": "viewer@example.com", "role": "viewer"}, 403),
        ({"email": "missing-role@example.com"}, 403),
    ],
)
def test_require_admin_user_rejects_non_admins(user, expected_status):
    with pytest.raises(HTTPException) as exc:
        require_admin_user(user)

    assert exc.value.status_code == expected_status
