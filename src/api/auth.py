"""
src/api/auth.py
JWT authentication: login / logout endpoints + token utilities.

Config (env vars):
  ADMIN_EMAIL           — login email (default: admin@localhost)
  ADMIN_PASSWORD_HASH   — bcrypt hash: bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
  ADMIN_PASSWORD        — plaintext fallback when hash is absent (dev only)
  JWT_SECRET            — HS256 signing secret (32+ bytes recommended)
  JWT_TTL_HOURS         — token lifetime in hours (default: 24)
  COOKIE_SECURE         — set "true" in production (HTTPS only cookie)
  COOKIE_DOMAIN         — optional cookie domain (defaults to .ricohunt.com in production)

Token stored as an httpOnly cookie named "access_token".
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import bcrypt as _bcrypt
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from jose import JWTError, jwt

from src.api.rate_limit import LIMIT_LOGIN, LIMIT_PASSWORD_RESET, LIMIT_REGISTER, LIMIT_VERIFY_EMAIL, limiter
from src.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyEmailResponse,
)

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_COOKIE_NAME = "access_token"

# Pre-computed dummy hash used to normalize bcrypt timing when no hash is stored.
# Without this an attacker can distinguish "account doesn't exist" from "wrong password"
# by measuring response time (bcrypt skipped vs bcrypt run).
_DUMMY_HASH = _bcrypt.hashpw(b"_rico_timing_normalization_dummy_", _bcrypt.gensalt(12)).decode()


def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt(12)).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    # Always run bcrypt even when hashed is absent so response time is constant.
    reference = hashed if hashed else _DUMMY_HASH
    try:
        result = _bcrypt.checkpw(plain.encode(), reference.encode())
        return bool(hashed) and result
    except Exception:
        return False


# ── Config helpers ────────────────────────────────────────────────────────────

def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        if _is_production():
            raise RuntimeError(
                "JWT_SECRET is not set in production. "
                "Set a strong secret (32+ random bytes) in the environment before serving traffic."
            )
        if not hasattr(_jwt_secret, "_ephemeral"):
            _jwt_secret._ephemeral = secrets.token_hex(32)  # type: ignore[attr-defined]
            logger.warning(
                "JWT_SECRET is not set — using an ephemeral secret. "
                "Sessions will not survive process restarts. "
                "Set JWT_SECRET in .env before deploying."
            )
        return _jwt_secret._ephemeral  # type: ignore[attr-defined]
    return secret


def _ttl_hours() -> int:
    try:
        return int(os.getenv("JWT_TTL_HOURS", "24"))
    except ValueError:
        return 24


def _cookie_secure() -> bool:
    raw = os.getenv("COOKIE_SECURE", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        if _is_production():
            raise RuntimeError("COOKIE_SECURE must be true in production")
        return False
    return _is_production()


def _cookie_samesite() -> str:
    # All browser requests go through the same-origin /proxy rewrite, so Lax
    # is sufficient and prevents CSRF without breaking any first-party flow.
    return "lax"


def _cookie_domain() -> Optional[str]:
    explicit = os.getenv("COOKIE_DOMAIN", "").strip()
    if explicit:
        return explicit

    app_url = (
        os.getenv("APP_URL")
        or os.getenv("FRONTEND_URL")
        or os.getenv("NEXT_PUBLIC_APP_URL")
        or ""
    ).strip()
    if app_url:
        parsed = urlparse(app_url if "://" in app_url else f"https://{app_url}")
        hostname = (parsed.hostname or "").strip().lower()
        if hostname.endswith("ricohunt.com"):
            return ".ricohunt.com"

    if _is_production():
        return ".ricohunt.com"
    return None


def _cookie_set_kwargs(*, max_age: int) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": _cookie_samesite(),
        "max_age": max_age,
        "path": "/",
    }
    domain = _cookie_domain()
    if domain:
        kwargs["domain"] = domain
    return kwargs


def _cookie_delete_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": _cookie_samesite(),
        "path": "/",
    }
    domain = _cookie_domain()
    if domain:
        kwargs["domain"] = domain
    return kwargs


# ── Credential check ─────────────────────────────────────────────────────────

def verify_credentials(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user.

    Returns a dict with ``email`` and ``role`` on success, None on failure.

    Lookup order:
    1. users table in DB (when available)
    2. ADMIN_EMAIL / ADMIN_PASSWORD_HASH env vars (backward-compat fallback)
    3. ADMIN_EMAIL / ADMIN_PASSWORD plaintext (dev-only fallback)
    """
    email = email.strip().lower()

    # 1. DB-backed auth
    _db_error = False
    try:
        from src.repositories.users_repo import get_user_by_email
        user = get_user_by_email(email)
        if user is not None:
            if _verify_password(password, user.password_hash):
                return {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "email_verified": user.email_verified,
                }
            return None
    except Exception as exc:
        # Only treat infrastructure/connection failures as a fallback trigger.
        # Re-raise logic errors (AttributeError, TypeError, etc.) immediately.
        try:
            import psycopg2
            _is_db_exc = isinstance(exc, psycopg2.Error)
        except ImportError:
            _is_db_exc = True  # psycopg2 unavailable — treat any error as DB failure
        if not _is_db_exc:
            raise
        _db_error = True
        logger.exception("db_auth_error falling_back_to_env_vars")

    # In production, never silently fall back to env-var auth on a DB error.
    # Set ALLOW_ENV_AUTH_FALLBACK=true to override during an incident.
    _env = os.getenv("RICO_ENV", os.getenv("ENV", "")).lower()
    _is_prod = _env in ("production", "prod")
    _fallback_allowed = os.getenv("ALLOW_ENV_AUTH_FALLBACK", "").lower() in ("1", "true", "yes")
    if _db_error and _is_prod and not _fallback_allowed:
        logger.error("db_auth_error in production — env fallback disabled; rejecting login for %r", email)
        return None

    # 2. Env-var fallback (single admin; backward-compatible with existing deployments)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@localhost").strip().lower()
    if email != admin_email:
        return None

    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if password_hash:
        if _verify_password(password, password_hash):
            return {"email": email, "role": "admin"}
        return None

    plaintext = os.getenv("ADMIN_PASSWORD", "").strip()
    if plaintext:
        logger.warning("ADMIN_PASSWORD_HASH not set — using plaintext ADMIN_PASSWORD (dev only)")
        if secrets.compare_digest(password, plaintext):
            return {"email": email, "role": "admin"}
        return None

    logger.error("No admin password configured. Set ADMIN_PASSWORD_HASH in .env.")
    return None


# ── Token utilities ───────────────────────────────────────────────────────────

def create_access_token(data: Dict[str, Any]) -> str:
    payload = dict(data)
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=_ttl_hours())
    return jwt.encode(payload, _jwt_secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[_ALGORITHM])
    except JWTError:
        return None


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit(LIMIT_LOGIN)
def login(request: Request, req: LoginRequest, response: Response) -> LoginResponse:
    user_info = verify_credentials(req.email, req.password)
    if user_info is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user_info.get("email_verified", True):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before continuing. Check your inbox.",
        )

    # Only record the login timestamp once the account is fully cleared to log in.
    if user_info.get("id"):
        from src.repositories.users_repo import update_last_login
        update_last_login(user_info["id"])

    token = create_access_token({"sub": user_info["email"], "role": user_info["role"]})
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        **_cookie_set_kwargs(max_age=_ttl_hours() * 3600),
    )
    # Merge guest profile into authenticated account if requested
    if req.public_user_id_to_merge:
        try:
            from src.services.identity_merge_service import merge_public_identity_into_auth
            merged = merge_public_identity_into_auth(
                public_user_id=req.public_user_id_to_merge,
                auth_user_id=user_info["email"],
            )
            if merged:
                logger.info("public_profile_merged public_user_id=%s", req.public_user_id_to_merge)
            else:
                logger.warning("public_profile_merge_skipped public_user_id=%s", req.public_user_id_to_merge)
        except Exception:
            logger.exception("public_profile_merge_failed public_user_id=%s", req.public_user_id_to_merge)

    logger.info("login_success email=%r role=%s", user_info["email"], user_info["role"])
    return LoginResponse(message="Logged in", email=user_info["email"])


@router.post("/logout")
def logout(response: Response) -> Dict[str, str]:
    response.delete_cookie(
        key=_COOKIE_NAME,
        **_cookie_delete_kwargs(),
    )
    return {"message": "Logged out"}


@router.get("/me")
def me(request: Request) -> Dict[str, Any]:
    # Deferred import avoids circular dependency (deps imports from this module)
    from src.api.deps import get_current_user

    try:
        user = get_current_user(request)
        return {"email": user["email"], "role": user.get("role", "user"), "authenticated": True}
    except HTTPException as e:
        # Return guest-friendly response for unauthenticated requests
        # This allows public/guest users to use the app without being forced to login
        if e.status_code == 401:
            return {
                "email": None,
                "role": "guest",
                "authenticated": False,
                "guest": True
            }
        raise


def _reset_base_url() -> str:
    return os.getenv("RESET_BASE_URL", "http://localhost:3000").rstrip("/")


def _is_production() -> bool:
    env = (
        os.getenv("RICO_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).lower()
    return env in ("production", "prod")


def _dispatch_password_reset_email(email: str) -> None:
    """Look up user, create a reset token, and email it — all in a background task.

    Both the DB lookup and the SMTP send run here so /forgot-password always returns
    at the same time regardless of whether the email is registered (closes the
    timing-based enumeration oracle that existed when the lookup was synchronous).
    """
    from src.repositories.users_repo import get_user_by_email
    from src.repositories.password_reset_repo import create_reset_token

    user = get_user_by_email(email)
    if user is None:
        logger.info("password_reset_request email=%r user_not_found", email)
        return

    try:
        token = create_reset_token(email)
    except Exception:
        logger.exception("password_reset_token_creation_failed email=%r", email)
        return

    reset_url    = f"{_reset_base_url()}/reset-password?token={token}"
    _prod        = _is_production()
    _token_log   = os.getenv("RESET_TOKEN_LOG", "").lower() in ("1", "true", "yes")

    if not _prod or _token_log:
        logger.info("password_reset_url email=%r url=%s", email, reset_url)
    else:
        logger.info(
            "password_reset_requested email=%r (token suppressed in production)",
            email,
        )

    # Best-effort delivery; failures logged but never exposed to the user.
    from src.services.password_reset_email import send_password_reset_email
    if not send_password_reset_email(email, token):
        logger.warning("password_reset_email_failed")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit(LIMIT_PASSWORD_RESET)
def forgot_password(
    request: Request,
    req: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
) -> ForgotPasswordResponse:
    """
    Initiate password reset. Always returns generic success to prevent email enumeration.
    Token creation + email delivery are deferred to a background task so the response time
    does not depend on whether the email is registered.
    Dev/local: logs reset URL to stdout. Production: token suppressed unless RESET_TOKEN_LOG=true.
    """
    email = req.email.strip().lower()
    # Always schedule the background task — DB lookup and SMTP run inside it so
    # this endpoint returns at the same time for registered and unregistered emails.
    background_tasks.add_task(_dispatch_password_reset_email, email)
    return ForgotPasswordResponse(
        message="If that email is registered, a reset link has been sent."
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit(LIMIT_PASSWORD_RESET)
def reset_password(request: Request, req: ResetPasswordRequest) -> ResetPasswordResponse:
    """Validate the reset token and set a new password."""
    from src.repositories.password_reset_repo import consume_reset_token
    from src.repositories.users_repo import update_password

    email = consume_reset_token(req.token)
    if email is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, or already used reset token",
        )

    new_hash = _hash_password(req.new_password)
    ok = update_password(email, new_hash)
    if not ok:
        logger.error("password_reset_update_failed email=%r", email)
        raise HTTPException(
            status_code=503,
            detail="Password update failed — please try again",
        )

    logger.info("password_reset_success email=%r", email)
    return ResetPasswordResponse(
        message="Password updated. You can now sign in with your new password."
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
@limiter.limit(LIMIT_REGISTER)
def register(
    request: Request,
    req: RegisterRequest,
    response: Response,
    background_tasks: BackgroundTasks,
) -> RegisterResponse:
    """
    Self-signup: create a new user account (public, no auth required).

    Role is always forced to "user" — admin accounts must be created via DB.
    Rate-limited to 3/minute per IP. Returns 409 if email already registered.
    """
    from src.repositories.users_repo import create_user, get_user_by_email

    email = req.email.strip().lower()
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = _hash_password(req.password)
    user = create_user(email, password_hash, role="user")  # always user, never admin
    if user is None:
        raise HTTPException(
            status_code=503,
            detail="Registration unavailable — please try again shortly",
        )

    # No cookie set — user must verify email before logging in.

    # Schedule verification email (best-effort, never fails registration)
    try:
        from src.repositories.email_verification_repo import create_verification_token
        from src.services.verification_email import send_verification_email
        verification_token = create_verification_token(user.email)
        background_tasks.add_task(send_verification_email, user.email, verification_token)
    except Exception:
        logger.exception(
            "verification_email_schedule_failed user_id=%s",
            getattr(user, "id", "unknown"),
        )

    # Merge guest profile into authenticated account if requested
    if req.public_user_id_to_merge:
        try:
            from src.services.identity_merge_service import merge_public_identity_into_auth
            merged = merge_public_identity_into_auth(
                public_user_id=req.public_user_id_to_merge,
                auth_user_id=user.email,
            )
            if merged:
                logger.info("public_profile_merged public_user_id=%s", req.public_user_id_to_merge)
            else:
                logger.warning("public_profile_merge_skipped public_user_id=%s", req.public_user_id_to_merge)
        except Exception:
            logger.exception("public_profile_merge_failed public_user_id=%s", req.public_user_id_to_merge)

    # Persist display name to rico_users if provided (best-effort, never fails registration)
    display_name = req.name.strip() if req.name and req.name.strip() else None
    if display_name:
        try:
            from src.db import get_db_connection
            conn2 = get_db_connection()
            if conn2:
                try:
                    with conn2.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO rico_users (external_user_id, email, name, source)
                            VALUES (%s, %s, %s, 'web')
                            ON CONFLICT (external_user_id) DO UPDATE
                            SET email = EXCLUDED.email,
                                name  = COALESCE(EXCLUDED.name, rico_users.name)
                            """,
                            (user.email, user.email, display_name),
                        )
                    conn2.commit()
                except Exception:
                    logger.exception("register_rico_users_upsert_failed email=%s", email)
                    conn2.rollback()
                finally:
                    conn2.close()
        except Exception:
            logger.exception("register_name_persist_failed email=%s", email)

    try:
        from src.services.signup_notifications import send_admin_signup_notification
        background_tasks.add_task(send_admin_signup_notification, user=user, name=display_name, plan="free")
    except Exception:
        logger.exception(
            "signup_notification_schedule_failed user_id=%s",
            getattr(user, "id", "unknown"),
        )

    logger.info("register_success email=%r", user.email)
    return RegisterResponse(
        email=user.email,
        role=user.role,
        created=True,
        email_verification_required=True,
    )


@router.get("/verify-email", response_model=VerifyEmailResponse)
@limiter.limit(LIMIT_VERIFY_EMAIL)
def verify_email(request: Request, token: str) -> VerifyEmailResponse:
    """Validate a verification token and mark the user's email as verified.

    Intentionally does NOT set an auth cookie — the user must sign in explicitly
    after verification.  This prevents link-scanner prefetches from issuing a
    session cookie before the real user opens the link.
    """
    from src.repositories.email_verification_repo import consume_verification_token
    from src.repositories.users_repo import mark_email_verified

    email = consume_verification_token(token)
    if email is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, or already used verification link.",
        )

    ok = mark_email_verified(email)
    if not ok:
        logger.error("email_verification_mark_failed email=%r", email)
        raise HTTPException(
            status_code=503,
            detail="Verification failed — please try again.",
        )

    logger.info("email_verified email=%r", email)
    return VerifyEmailResponse(message="Email verified. Welcome to RicoHunt!", email=email)


@router.post("/resend-verification", response_model=ResendVerificationResponse)
@limiter.limit(LIMIT_VERIFY_EMAIL)
def resend_verification(
    request: Request,
    req: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
) -> ResendVerificationResponse:
    """Resend verification email. Always returns generic success to prevent enumeration."""
    from src.repositories.email_verification_repo import create_verification_token
    from src.repositories.users_repo import get_user_by_email
    from src.services.verification_email import send_verification_email

    _generic = ResendVerificationResponse(
        message="If that email is registered and unverified, a new verification link has been sent."
    )

    email = req.email.strip().lower()
    user = get_user_by_email(email)
    if user is None or user.email_verified:
        # User not found or already verified — don't reveal which
        return _generic

    try:
        verification_token = create_verification_token(email)
        background_tasks.add_task(send_verification_email, email, verification_token)
    except Exception:
        logger.exception("resend_verification_failed email=%r", email)

    return _generic
