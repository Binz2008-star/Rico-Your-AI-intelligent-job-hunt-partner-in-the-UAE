import pytest

from src.api.public_identity import (
    is_safe_public_session_id,
    is_valid_public_user_id,
    make_public_user_id,
    normalize_public_email,
)


def test_normalize_public_email_accepts_valid_address():
    assert normalize_public_email("  ROBEN@example.COM ") == "roben@example.com"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-an-email",
        "missing-domain@",
        "missing-tld@example",
        "white space@example.com",
        "@example.com",
    ],
)
def test_normalize_public_email_rejects_invalid_addresses(value):
    with pytest.raises(ValueError):
        normalize_public_email(value)


def test_normalize_public_email_allows_none_for_anonymous_sessions():
    assert normalize_public_email(None) is None


@pytest.mark.parametrize(
    "value",
    [
        "abcdefgh",
        "abc_1234",
        "abc-1234",
        "A1_b2-C3",
    ],
)
def test_safe_public_session_id_accepts_allowed_values(value):
    assert is_safe_public_session_id(value) is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        "short",
        "has space 123",
        "has/slash/123",
        "has.dot.123",
        "x" * 65,
    ],
)
def test_safe_public_session_id_rejects_unsafe_values(value):
    assert is_safe_public_session_id(value) is False


def test_make_public_user_id_canonicalizes_valid_session():
    assert make_public_user_id("abc_12345") == "public:abc_12345"


def test_make_public_user_id_rejects_invalid_session():
    with pytest.raises(ValueError):
        make_public_user_id("bad session")


@pytest.mark.parametrize(
    "value",
    [
        "public:abcdefgh",
        "public:abc_1234",
        "public:abc-1234",
    ],
)
def test_valid_public_user_id_accepts_canonical_values(value):
    assert is_valid_public_user_id(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "abcdefgh",
        "PUBLIC:abcdefgh",
        "public:short",
        "public:has space",
        "public:has/slash",
        None,
    ],
)
def test_valid_public_user_id_rejects_noncanonical_values(value):
    assert is_valid_public_user_id(value) is False
