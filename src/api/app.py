"""
src/api/app.py
Main FastAPI application for the Job Automation Platform API.

Startup:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

All API endpoints live under /api/v1/.
The legacy control_server.py is preserved separately for backward compat.

Required env vars (see .env.example):
    ADMIN_EMAIL, ADMIN_PASSWORD or ADMIN_PASSWORD_HASH, JWT_SECRET (optional but recommended)
    DATABASE_URL (optional — JSON fallback active when absent)
"""
from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.models.principal import IdentityOwnershipAmbiguous
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.auth import decode_access_token, router as auth_router
from src.api.rate_limit import limiter, rate_limit_exceeded_handler
from src.api.routers.actions import router as actions_router
from src.api.routers.agent import router as agent_router
from src.api.routers.applications import router as applications_router
from src.api.routers.integrations_gmail import router as integrations_gmail_router
from src.api.routers.link_verification import router as link_verification_router
from src.api.routers.rico_chat import router as rico_chat_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.onboarding import router as onboarding_router
from src.api.routers.pipeline import router as pipeline_router
from src.api.routers.settings import router as settings_router
from src.api.routers.email_alerts import router as email_alerts_router
from src.api.routers.stats import router as stats_router
from src.api.routers.journey import router as journey_router
from src.api.routers.subscription import router as subscription_router
from src.api.routers.admin_subscriptions import router as admin_subscriptions_router
from src.api.routers.admin_subscribers import router as admin_subscribers_router
from src.api.routers.admin_ops import router as admin_ops_router
from src.api.routers.job_lifecycle import router as job_lifecycle_router
from src.api.routers.apply_queue import router as apply_queue_router
from src.api.routers.mission import router as mission_router
from src.api.routers.user import router as user_router
from src.api.routers.avatar import router as avatar_router
from src.api.routers.files import router as files_router
from src.api.routers.paddle_billing import paddle_billing_router
from src.api.routers.billing_whatsapp import billing_whatsapp_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


# Captured at import time — every deploy restarts the process, so this is a
# trustworthy "this build went live no earlier than" signal. The env-driven
# deployed_at below is a static var that operators rarely update; verifying a
# deploy against it alone is misleading (it once lagged main by six weeks).
from datetime import datetime, timezone as _tz
_PROCESS_STARTED_AT = datetime.now(_tz.utc).isoformat()

_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _revision_result(sha: str, source: str) -> Dict[str, Any]:
    """Build a revision result dict from a SHA and its source identifier."""
    verified = bool(sha and _COMMIT_SHA_RE.match(sha))
    return {
        "commit": sha if sha else "unknown",
        "commit_source": source,
        "commit_verified": verified,
    }


def _resolve_deployment_revision() -> Dict[str, Any]:
    """Resolve the deployed source revision with platform-aware precedence.

    Platform-native variables (Railway, Vercel, Render) are authoritative
    on their respective platforms. Generic/static variables are used only
    when no known platform is detected, preventing stale manually-configured
    values from impersonating the deployed revision.

    Railway detection uses RAILWAY_REPLICA_ID (always set for running
    deployments). Vercel detection uses VERCEL_ENV. Render detection uses
    RENDER. Once a platform is detected, only its native SHA variable is
    accepted — a stale generic variable on the same platform is never used.
    """
    if os.getenv("RAILWAY_REPLICA_ID", "").strip():
        sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()
        if sha:
            return _revision_result(sha, "RAILWAY_GIT_COMMIT_SHA")
        return _revision_result("", "unknown")

    if os.getenv("VERCEL_ENV", "").strip():
        sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip()
        if sha:
            return _revision_result(sha, "VERCEL_GIT_COMMIT_SHA")
        return _revision_result("", "unknown")

    if os.getenv("RENDER", "").strip():
        sha = os.getenv("RENDER_GIT_COMMIT", "").strip()
        if sha:
            return _revision_result(sha, "RENDER_GIT_COMMIT")
        return _revision_result("", "unknown")

    sha = _first_env("GIT_COMMIT", "COMMIT_SHA", "SOURCE_VERSION", default="")
    if sha:
        return _revision_result(sha, "generic_env")
    return _revision_result("", "unknown")


def version_metadata() -> Dict[str, Any]:
    """Deployment metadata shared by legacy and versioned routes.

    Key fields for deploy verification:

      commit (str)
          The resolved deployed-source revision. Either a trustworthy
          platform-native SHA, a generic/env fallback, or 'unknown'.
          This is NOT the same as started_at — a process restart can
          happen without a new deploy (e.g. platform health-replacement
          of a failed replica), so started_at does not prove which code
          revision is running. Only the commit field identifies the
          source revision.

      commit_source (str)
          Which environment variable supplied the commit value, e.g.
          'RAILWAY_GIT_COMMIT_SHA', 'VERCEL_GIT_COMMIT_SHA',
          'RENDER_GIT_COMMIT', 'generic_env', or 'unknown'.

      commit_verified (bool)
          True only when commit is a trustworthy full 40-character hex
          SHA from a platform-native variable. Shortened, malformed,
          or blank values are unverified. A verified commit paired with
          started_at establishes both identity and recency.

      started_at (str, ISO-8601)
          Process boot time. Every deploy restarts the process, so this
          is a trustworthy 'no earlier than' signal. It is NOT source
          identity — a platform replica replacement restarts the
          process without changing the deployed code. Use commit to
          identify the source revision.
    """
    revision = _resolve_deployment_revision()
    return {
        "app": "ricohunt",
        "version": app.version,
        "commit": revision["commit"],
        "commit_source": revision["commit_source"],
        "commit_verified": revision["commit_verified"],
        "environment": _first_env(
            "RICO_ENV",
            "ENV",
            "ENVIRONMENT",
            "VERCEL_ENV",
            default="production" if os.getenv("RENDER") else "development",
        ),
        "deployed_at": _first_env("DEPLOYED_AT", "BUILD_TIME", "BUILD_TIMESTAMP"),
        "started_at": _PROCESS_STARTED_AT,
    }


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        from src.log_privacy import sentry_before_send

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("RICO_ENV", "production")),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[FastApiIntegration()],
            # #1076: scrub credentials/contact values/document text from every
            # exported event — logs must not widen through the error exporter.
            before_send=sentry_before_send,
        )
        logger.info("sentry_initialized environment=%s", os.getenv("SENTRY_ENVIRONMENT", os.getenv("RICO_ENV", "production")))
    except Exception:
        logger.exception("sentry_init_failed")


# #1076: production refuses to boot with any token-logging/debug-PII flag on
# (e.g. RESET_TOKEN_LOG) — a debug override that writes recovery credentials
# into live logs is not an acceptable production path.
from src.log_privacy import enforce_production_log_safety

enforce_production_log_safety()

init_sentry()

_CRITICAL_TABLES = frozenset({
    "users",
    "action_audit_log",
    "password_reset_tokens",
    "user_subscriptions",
    "subscription_events",
    "rico_users",
})


def _require_critical_tables_readonly() -> None:
    """Strict read-only schema verification — used only when
    RICO_RUN_STARTUP_MIGRATIONS=false.

    A deployment that intentionally skips migrations must never silently
    serve traffic against a database it hasn't verified is actually usable.
    Every failure mode here aborts startup: missing DATABASE_URL, a failed
    connection, a failed query, or missing critical tables. No write-capable
    call is made anywhere in this path.
    """
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError(
            "RICO_RUN_STARTUP_MIGRATIONS=false requires DATABASE_URL — "
            "startup migrations are disabled, so a working database is not optional"
        )

    from src.db import get_db_connection
    conn = get_db_connection()
    if not conn:
        raise RuntimeError(
            "RICO_RUN_STARTUP_MIGRATIONS=false: database connection failed — "
            "refusing to serve traffic against an unverified schema"
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(_CRITICAL_TABLES),),
            )
            found = {row[0] for row in cur.fetchall()}
    except Exception as exc:
        raise RuntimeError(
            f"RICO_RUN_STARTUP_MIGRATIONS=false: critical-tables query failed: {exc}"
        ) from exc
    finally:
        conn.close()

    missing = _CRITICAL_TABLES - found
    if missing:
        raise RuntimeError(
            f"RICO_RUN_STARTUP_MIGRATIONS=false: missing critical tables {sorted(missing)} — "
            "refusing to serve traffic against an incomplete schema"
        )

    logger.info("startup_check: critical tables present (migrations disabled, read-only verification)")


def _check_critical_tables() -> None:
    from src.db import get_db_connection
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(_CRITICAL_TABLES),),
            )
            found = {row[0] for row in cur.fetchall()}
        missing = _CRITICAL_TABLES - found
        if missing:
            logger.error(
                "startup_check: missing tables %s — run pending migrations before serving traffic",
                sorted(missing),
            )
        else:
            logger.info("startup_check: critical tables present")
    except Exception as exc:
        logger.warning("startup_check: could not verify tables: %s", exc)
    finally:
        conn.close()


def _apply_sql_migration(label: str, sql: str) -> None:
    """Run a raw SQL migration idempotently (IF NOT EXISTS guards in each statement)."""
    from src.db import get_db_connection
    conn = get_db_connection()
    if not conn:
        logger.warning("migration_skipped label=%s (no DB connection)", label)
        return
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        logger.info("migration_ok label=%s", label)
    except Exception as exc:
        conn.rollback()
        logger.warning("migration_failed label=%s: %s", label, exc)
    finally:
        conn.close()


def _apply_performance_indexes() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "migrations", "028_performance_indexes.sql"
    )
    sql_path = os.path.normpath(sql_path)
    if not os.path.exists(sql_path):
        logger.warning("performance_indexes_migration not found at %s", sql_path)
        return
    with open(sql_path) as f:
        sql = f.read()
    _apply_sql_migration("028_performance_indexes", sql)


def _apply_audit_helper_tables() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "migrations", "031_audit_helper_tables.sql"
    )
    sql_path = os.path.normpath(sql_path)
    if not os.path.exists(sql_path):
        logger.warning("audit_helper_tables_migration not found at %s", sql_path)
        return
    with open(sql_path) as f:
        sql = f.read()
    _apply_sql_migration("031_audit_helper_tables", sql)


def _apply_uploaded_document_context() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "migrations", "032_uploaded_document_context.sql"
    )
    sql_path = os.path.normpath(sql_path)
    if not os.path.exists(sql_path):
        logger.warning("uploaded_document_context_migration not found at %s", sql_path)
        return
    with open(sql_path) as f:
        sql = f.read()
    _apply_sql_migration("032_uploaded_document_context", sql)


def _apply_cv_upload_artifacts() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "migrations", "038_cv_upload_artifacts.sql"
    )
    sql_path = os.path.normpath(sql_path)
    if not os.path.exists(sql_path):
        logger.warning("cv_upload_artifacts_migration not found at %s", sql_path)
        return
    with open(sql_path) as f:
        sql = f.read()
    _apply_sql_migration("038_cv_upload_artifacts", sql)


_STARTUP_MIGRATIONS_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_STARTUP_MIGRATIONS_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def _startup_migrations_enabled() -> bool:
    """Gate for write-capable startup DB initialization (#railway-startup-safety).

    Defaults to true (unset) so existing Render/main behavior is unchanged.
    Set RICO_RUN_STARTUP_MIGRATIONS=false to connect to an existing, already-
    initialized Neon database without the process issuing any startup DDL —
    for standing up an additional deployment target (e.g. a second platform)
    against a database that another deployment already owns and migrates.

    Parsing is intentionally strict: an unrecognized explicit value must
    never silently fall through to either "run migrations" or "skip
    migrations" by guessing — it raises before any DB call is made (see
    lifespan(), which calls this before anything else), aborting startup
    rather than booting into an ambiguous configuration.
    """
    raw = os.getenv("RICO_RUN_STARTUP_MIGRATIONS", "").strip().lower()
    if not raw:
        return True
    if raw in _STARTUP_MIGRATIONS_TRUE_VALUES:
        return True
    if raw in _STARTUP_MIGRATIONS_FALSE_VALUES:
        return False
    raise ValueError(
        f"RICO_RUN_STARTUP_MIGRATIONS={raw!r} is not a recognized value — "
        f"expected one of {sorted(_STARTUP_MIGRATIONS_TRUE_VALUES | _STARTUP_MIGRATIONS_FALSE_VALUES)} "
        "or unset. Refusing to start rather than guess."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Evaluated first, before any DB call: an invalid explicit value aborts
    # startup right here — RicoDB().init(), init_db(), the four _apply_*
    # migrations, and the read-only schema check are all unreached.
    migrations_enabled = _startup_migrations_enabled()

    if not migrations_enabled:
        logger.info(
            "startup_migrations_disabled: RICO_RUN_STARTUP_MIGRATIONS=false — "
            "skipping RicoDB().init(), init_db(), and all _apply_* migrations; "
            "performing a strict read-only schema check instead"
        )
        _require_critical_tables_readonly()
    else:
        try:
            from src.rico_db import RicoDB
            RicoDB().init()
            logger.info("rico_db_init OK")
        except Exception:
            logger.warning("rico_db_init skipped (DB unavailable or tables already exist)")

        try:
            from src.db import init_db
            init_db()
            logger.info("settings_migration OK")
        except Exception as exc:
            logger.warning("settings_migration failed: %s", exc)

        _check_critical_tables()
        _apply_performance_indexes()
        _apply_audit_helper_tables()
        _apply_uploaded_document_context()
        _apply_cv_upload_artifacts()

    try:
        # Kick the reasoning /models pre-check on a daemon thread: probes once now,
        # then refreshes on a background interval. Non-blocking — it NEVER delays
        # startup and no inbound request ever triggers an upstream probe.
        from src.rico_openai_runtime import start_model_precheck_background
        start_model_precheck_background()
        logger.info("reasoning_models_precheck started")
    except Exception as exc:
        logger.warning("reasoning_models_precheck start skipped: %s", exc)

    yield


app = FastAPI(
    title="Rico API",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Rico AI — UAE career intelligence platform. "
        "Authenticated endpoints require a JWT in an httpOnly cookie. "
        "Public endpoints are session-based and rate-limited."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


def identity_ownership_ambiguous_handler(request, exc):
    """Map ambiguous account ownership to one deterministic, non-identifying response.

    Identity resolution fails closed rather than guessing between candidate rows. That
    refusal must not surface as an unhandled 500, and it must not look like "no user
    found" — several call paths respond to a missing user by creating one, which would
    turn the refusal into an additional ambiguous row.

    409 Conflict with a stable reason code. No address, no identifier, no row content.
    """
    logger.warning(
        "identity_ownership_conflict reason=%s candidates=%s",
        "ambiguous_account_ownership",
        getattr(exc, "candidate_count", "unknown"),
    )
    return JSONResponse(
        status_code=409,
        content={
            "ok": False,
            "error": "ambiguous_account_ownership",
            "message": "This account could not be resolved unambiguously. Please contact support.",
        },
    )


app.add_exception_handler(IdentityOwnershipAmbiguous, identity_ownership_ambiguous_handler)
app.add_middleware(SlowAPIMiddleware)

# Ingress request-body cap (#1080): rejects oversized declared lengths before
# the body is pulled AND counts received bytes so chunked/missing/false
# Content-Length payloads stop at the cap. The request body is only pulled
# (lazily) through this middleware's wrapped `receive`, so the cap applies
# before Starlette's multipart parser can spool an unbounded payload.
from src.api.upload_limits import BodySizeLimitMiddleware  # noqa: E402
app.add_middleware(BodySizeLimitMiddleware)

_DEFAULT_CORS_ORIGINS = ",".join(
    [
        "http://localhost:3000",
        "https://ricohunt.com",
        "https://www.ricohunt.com",
    ]
)
_origins_raw = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
_origins_list = [o.strip() for o in _origins_raw.split(",") if o.strip()]
_wildcard = _origins_list == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _wildcard else _origins_list,
    allow_credentials=False if _wildcard else True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Private-response cache boundary (#1101): registered LAST so it is the
# outermost layer and stamps the final headers of every response (including
# CORS's Vary: Origin merge). Routes that set their own Cache-Control (the
# SSE stream) are left untouched.
from src.api.cache_privacy import PrivateCacheHeadersMiddleware  # noqa: E402
app.add_middleware(PrivateCacheHeadersMiddleware)


@app.middleware("http")
async def hydrate_request_auth_context(request: Request, call_next):
    request.state.current_user = None
    request.state.user_id = None
    request.state.access_token_present = False
    request.state.auth_cookie_invalid = False

    token = request.cookies.get("access_token")
    if token:
        request.state.access_token_present = True
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            user = {
                "email": payload["sub"],
                "role": payload.get("role", "user"),
            }
            request.state.current_user = user
            request.state.user_id = user["email"]
        else:
            request.state.auth_cookie_invalid = True

    return await call_next(request)


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(files_router)
app.include_router(avatar_router)
app.include_router(actions_router)
app.include_router(agent_router)
app.include_router(rico_chat_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(link_verification_router)
app.include_router(stats_router)
app.include_router(journey_router)
app.include_router(settings_router)
app.include_router(email_alerts_router)
app.include_router(integrations_gmail_router)
app.include_router(onboarding_router)
app.include_router(pipeline_router)
app.include_router(subscription_router)
app.include_router(admin_subscriptions_router)
app.include_router(admin_subscribers_router)
app.include_router(admin_ops_router)
app.include_router(job_lifecycle_router)
app.include_router(apply_queue_router)
app.include_router(mission_router)
app.include_router(paddle_billing_router)
app.include_router(billing_whatsapp_router)


@app.get("/health")
@app.head("/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint for load balancers and monitoring.

    Includes a job-provider health indicator (configured/degraded only — never
    secret values) so quota/rate-limit issues are observable without log diving.
    """
    payload: Dict[str, Any] = {"status": "ok", "service": "Job Automation Platform API"}
    try:
        from src import job_providers
        payload["job_providers"] = job_providers.provider_health()
    except Exception:
        # Health must never fail because of the provider indicator.
        pass
    try:
        # Reasoning-provider (core AI) health — names/categories/status codes and
        # model identifiers only, never secret values. A dead core AI with no
        # fallback flips the whole platform to "degraded" so it can't hide behind
        # healthy job providers.
        from src.rico_openai_runtime import get_reasoning_health
        reasoning = get_reasoning_health()
        payload["reasoning_provider"] = reasoning
        if reasoning.get("degraded"):
            payload["status"] = "degraded"
    except Exception:
        pass
    return payload


@app.get("/ready")
@app.head("/ready")
def readiness_check() -> JSONResponse:
    """Readiness probe (distinct from /health, which is Render's liveness probe).

    Returns HTTP 503 when core reasoning has NO reachable valid model (provider
    not configured, or a fresh /models probe lists none of the resolved chain, or
    a persistent unusable failure with no backup); HTTP 200 otherwise. /health
    stays 200 always so a transient provider blip never restart-loops the process.

    Cache-only: answers from the SAME cached provider state as /health and makes
    NO per-request upstream call, so it cannot be looped to burn the provider
    balance. The /models cache is refreshed only by the background daemon.
    """
    body: Dict[str, Any] = {"ready": True, "service": "Job Automation Platform API"}
    status = 200
    try:
        from src.rico_openai_runtime import get_readiness
        readiness = get_readiness()
        body = readiness
        status = 200 if readiness.get("ready") else 503
    except Exception:
        # Never crash the probe: a computation error is not evidence of unreadiness.
        body = {"ready": True, "error": "readiness_indeterminate"}
        status = 200
    return JSONResponse(content=body, status_code=status)


@app.get("/version")
def version() -> Dict[str, Any]:
    """Version endpoint for deployment tracking."""
    return version_metadata()


@app.get("/api/v1/version")
def api_version() -> Dict[str, Any]:
    """Versioned deployment metadata endpoint."""
    return version_metadata()


@app.get("/")
@app.head("/")
def root() -> Dict[str, str]:
    """Root endpoint — confirms the API is reachable."""
    return {"status": "ok", "service": "Job Automation Platform API", "docs": "/api/docs"}
