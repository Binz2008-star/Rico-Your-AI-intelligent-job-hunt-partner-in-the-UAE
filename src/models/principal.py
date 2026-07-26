"""Principal kinds and the identity fields that only an authenticated principal owns.

A *principal* is whatever a caller presents as `user_id`. Two kinds matter here:

- **authenticated** — derived from a verified session (an email/subject or an internal id)
- **public** — a server-minted guest session, always carrying the ``public:`` prefix

The repository and identity layers must be able to tell them apart *without* importing
transport code. `src/api/public_identity.py` already has a validator, but it lives above
this layer; importing it here would invert the dependency direction. This module is a
leaf — it imports nothing from the application, service, or transport layers.

**Deliberately narrower than the transport validator.** `is_public_principal` tests the
prefix only, where the transport validator additionally checks the session-id charset.
That asymmetry is intentional and must not be "harmonised": as a write/ownership guard the
conservative test is the correct one. Anything that *looks* like a guest principal is
treated as one, including a malformed value that the transport validator would reject.
Narrowing this to match transport would open the guard to malformed input.
"""

from __future__ import annotations

# Every server-minted guest principal carries this prefix.
PUBLIC_PRINCIPAL_PREFIX = "public:"

# Contact columns on the user row that establish *who an account is*. They are how an
# authenticated caller is subsequently resolved, so a guest principal must never write
# them — a guest row carrying an account's contact value makes ownership ambiguous.
#
# `external_user_id` is deliberately NOT in this set. It is the row's own identity
# rather than a claim about somebody else: for a guest row it *is* the guest principal,
# so rejecting it would be meaningless. It was in an earlier revision of this set and
# was inert there — the caller's field filter removed it before the guard ran, while it
# was written unconditionally further down. A field that is listed but unenforceable is
# worse than an absent one, because it reads as a guarantee. Ownership of that column is
# enforced instead by excluding `public:` rows from authenticated resolution.
TRUSTED_IDENTITY_FIELDS = frozenset(
    {
        "email",
        "phone",
        "telegram_username",
        "telegram_chat_id",
    }
)


class IdentityOwnershipAmbiguous(RuntimeError):
    """Raised when an authenticated identifier resolves to more than one owner row.

    Fail closed. Returning one of several candidates would mean serving or mutating a
    row the caller may not own, so the caller gets an explicit error instead of a guess.
    Carries no identifier and no row content — it is safe to log and safe to surface.
    """

    def __init__(self, candidate_count: int) -> None:
        self.candidate_count = candidate_count
        super().__init__(
            f"identity resolves to {candidate_count} candidate owner rows; refusing to guess"
        )


def is_public_principal(user_id: str | None) -> bool:
    """True when the principal is a guest/public session rather than an account."""
    if not user_id:
        return False
    return str(user_id).startswith(PUBLIC_PRINCIPAL_PREFIX)


def rejected_trusted_identity_fields(user_id: str | None, updates: dict) -> set[str]:
    """Trusted identity fields a public principal attempted to write.

    Empty for an authenticated principal, and empty when a public principal touches only
    non-identity fields — guests legitimately write ordinary profile data.
    """
    if not is_public_principal(user_id) or not updates:
        return set()
    return {k for k in updates if k in TRUSTED_IDENTITY_FIELDS and updates.get(k) is not None}
