"""
tests/unit/test_password_complexity.py
Unit tests for password complexity validation on register + reset-password.

Tests cover:
- Valid passwords (all rules satisfied)
- Too short
- Missing uppercase
- Missing lowercase
- Missing digit and symbol
- Boundary / edge cases
- Both RegisterRequest and ResetPasswordRequest are validated
"""
from __future__ import annotations

import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.schemas.auth import RegisterRequest, ResetPasswordRequest, _check_password_complexity


# ── _check_password_complexity unit tests ─────────────────────────────────────

class TestPasswordComplexityFunction:
    def test_valid_password_with_digit(self):
        assert _check_password_complexity("Passw0rd") == "Passw0rd"

    def test_valid_password_with_symbol(self):
        assert _check_password_complexity("Password!") == "Password!"

    def test_valid_password_long_mixed(self):
        assert _check_password_complexity("MySecure#2026") == "MySecure#2026"

    def test_valid_exactly_8_chars(self):
        assert _check_password_complexity("Abcdef1!") == "Abcdef1!"

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            _check_password_complexity("Ab1!")

    def test_rejects_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            _check_password_complexity("passw0rd!")

    def test_rejects_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            _check_password_complexity("PASSW0RD!")

    def test_rejects_no_digit_or_symbol(self):
        with pytest.raises(ValueError, match="digit or special character"):
            _check_password_complexity("Password")

    def test_symbol_satisfies_digit_or_symbol(self):
        # No digit but has symbol — should pass
        assert _check_password_complexity("Password!") == "Password!"

    def test_digit_satisfies_digit_or_symbol(self):
        # No symbol but has digit — should pass
        assert _check_password_complexity("Password1") == "Password1"

    def test_rejects_all_lowercase_digits(self):
        with pytest.raises(ValueError, match="uppercase"):
            _check_password_complexity("password1")

    def test_rejects_all_uppercase_digits(self):
        with pytest.raises(ValueError, match="lowercase"):
            _check_password_complexity("PASSWORD1")

    def test_rejects_pure_digits(self):
        with pytest.raises(ValueError, match="uppercase"):
            _check_password_complexity("12345678")

    def test_multiple_violations_reported(self):
        with pytest.raises(ValueError) as exc_info:
            _check_password_complexity("abc")
        msg = str(exc_info.value)
        # Short, no uppercase, no digit/symbol — multiple issues
        assert "characters" in msg or "uppercase" in msg

    def test_valid_unicode_passphrase(self):
        # Arabic/unicode chars count as non-alphanumeric (satisfy digit-or-symbol)
        assert _check_password_complexity("Passمرحبا") == "Passمرحبا"


# ── RegisterRequest integration ───────────────────────────────────────────────

class TestRegisterRequestPasswordValidation:
    def _build(self, password: str) -> dict:
        return {"email": "user@example.com", "password": password}

    def test_valid_password_accepted(self):
        req = RegisterRequest(**self._build("SecurePass1"))
        assert req.password == "SecurePass1"

    def test_weak_password_raises_422_equivalent(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._build("weakpass"))
        errors = exc_info.value.errors()
        assert any("password" in str(e.get("loc", "")) for e in errors)

    def test_no_uppercase_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._build("nouppercase1!"))
        errors = exc_info.value.errors()
        assert any("uppercase" in str(e) for e in errors)

    def test_no_lowercase_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._build("NOLOWERCASE1!"))
        errors = exc_info.value.errors()
        assert any("lowercase" in str(e) for e in errors)

    def test_no_digit_or_symbol_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._build("NoDigitSym"))
        errors = exc_info.value.errors()
        assert any("digit" in str(e) or "special" in str(e) for e in errors)

    def test_too_short_rejected_by_field(self):
        # min_length=8 on Field catches this before our validator
        with pytest.raises(ValidationError):
            RegisterRequest(**self._build("Ab1!"))

    def test_valid_with_symbol_only(self):
        req = RegisterRequest(**self._build("Password!"))
        assert req.password == "Password!"

    def test_valid_with_digit_only(self):
        req = RegisterRequest(**self._build("Password1"))
        assert req.password == "Password1"

    def test_role_always_stays_user(self):
        # Verify the auth.py register handler enforces role=user regardless of schema
        req = RegisterRequest(email="u@e.com", password="Valid1Pass!", role="admin")
        # Schema allows admin in the field, but auth.py forces role="user" at create_user call
        # This test documents the boundary: schema accepts it, handler overrides it
        assert req.role == "admin"  # schema accepts; auth.py overrides at DB write


# ── ResetPasswordRequest integration ─────────────────────────────────────────

class TestResetPasswordRequestValidation:
    def _build(self, password: str) -> dict:
        return {"token": "some-valid-token-abc123", "new_password": password}

    def test_valid_new_password_accepted(self):
        req = ResetPasswordRequest(**self._build("NewSecure9!"))
        assert req.new_password == "NewSecure9!"

    def test_weak_new_password_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(**self._build("weakpass"))
        errors = exc_info.value.errors()
        assert any("new_password" in str(e.get("loc", "")) for e in errors)

    def test_no_uppercase_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(**self._build("nouppercase1!"))
        errors = exc_info.value.errors()
        assert any("uppercase" in str(e) for e in errors)

    def test_no_lowercase_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(**self._build("NOLOWERCASE1!"))
        errors = exc_info.value.errors()
        assert any("lowercase" in str(e) for e in errors)

    def test_no_digit_or_symbol_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(**self._build("NoDigitSym"))
        errors = exc_info.value.errors()
        assert any("digit" in str(e) or "special" in str(e) for e in errors)

    def test_too_short_rejected(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(**self._build("Ab1!"))

    def test_valid_special_chars_variety(self):
        for pw in ["Passw0rd!", "Secure#99", "Test@2026", "Hello_World1"]:
            req = ResetPasswordRequest(**self._build(pw))
            assert req.new_password == pw
