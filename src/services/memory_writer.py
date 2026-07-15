"""
src/services/memory_writer.py
Career Memory Engine — single writer (ADR-001 M1).

The ONLY module allowed to write career_memory_events / career_memory_facts.
Routers and features never write memory directly (ADR §4); action paths call
this service — in M1 exclusively as a shadow write from
agent_runtime.handle_action(), mirroring the legacy career_memory write while
no reader consumes the rows.

Policy enforced here (storage lives in src/repositories/career_memory_repo.py):

- Feature flag: RICO_MEMORY_ENGINE_ENABLED (default false — M1 ships dark).
- Kill switch: RICO_MEMORY_ENGINE_KILL=true hard-disables writes regardless of
  the enable flag, plus an in-process circuit breaker that opens after
  consecutive database failures so a broken engine can never degrade actions.
- Canonical identity: every write is keyed by the immutable rico_users.id UUID,
  resolved at this boundary from whatever external identity the caller holds
  (email, telegram id, public session id). Email is provenance, never the key
  (ADR §3). Public sessions ('public:*') resolve only to their own exact row —
  never implicitly into an account (ADR §3: merging requires an explicit,
  audited step that does not exist in M1).
- Mandatory provenance (ADR §6): source tier, actor, confidence in [0,1],
  occurred_at, and at least one of source_record_id / source_uri.
- Trust hierarchy (ADR §7): a lower tier never supersedes a higher tier;
  verified_only fact classes accept only verified_event writes (the
  "queued as unverified" path is M6 scope — rejected + counted here).
- Exclusion filter (ADR §8): payloads carrying secret/credential/payment/
  document-copy material are rejected and logged, never stored.
- Metrics: thread-safe counters for every outcome, including legacy↔engine
  drift observed on shadow writes. Snapshot via metrics_snapshot().

Every public method is safe under the repository's "fire-and-forget" calling
convention: record_job_action_shadow() never raises; record_event() /
record_fact() raise only MemoryWriteRejected (caller bug: bad provenance /
policy violation) — database trouble is absorbed into the result status.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.rico_env import env_bool

logger = logging.getLogger(__name__)

# Provenance vocabulary (ADR §6) — mirrored by CHECK constraints in migration 042.
SOURCE_TIERS = ("user_stated", "verified_event", "cv_extracted", "inferred")
# Higher rank = higher trust. user_stated and verified_event both carry
# confidence 1.0; user_stated wins conflicts (explicit statement beats record).
_TIER_RANK = {"inferred": 0, "cv_extracted": 1, "verified_event": 2, "user_stated": 3}
ACTORS = ("user", "rico_agent", "pipeline", "webhook")
FACT_CLASSES = ("replaceable", "set_valued", "time_bound", "verified_only")
RETENTION_CLASSES = ("core_fact", "episode", "bulk_text", "derived", "referenced")

# Exclusion filter (ADR §8; owner M1 rule: no billing/security/document payload
# copies). Any payload key matching this pattern rejects the whole write —
# never a silently altered payload.
_EXCLUDED_KEY_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|authorization|bearer|credential"
    r"|card|cvv|iban|swift|account[_-]?number|payment|billing|document[_-]?(text|body|content))",
    re.IGNORECASE,
)

# Circuit breaker: after this many consecutive repo failures the writer stops
# trying for _BREAKER_COOLDOWN_S seconds. Protects the action path (and the
# database) from a persistently broken engine without any deploy.
_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_S = 300

# Actions mirrored by the M1 shadow write — identical to the legacy
# career_memory set in agent_runtime (step 11).
SHADOW_ACTIONS = frozenset({"apply", "save", "skip", "block", "not_relevant"})


class MemoryWriteRejected(ValueError):
    """A write violated provenance or policy rules — caller-side defect."""


@dataclass
class MemoryWriteResult:
    status: str                      # written | duplicate | skipped_* | rejected_* | failed
    account_id: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in ("written", "duplicate")


class MemoryWriter:
    """Single writer for the Career Memory Engine. Module-level singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0
        self._metrics: Dict[str, int] = {
            "written": 0,
            "duplicate": 0,
            "failed": 0,
            "skipped_disabled": 0,
            "skipped_breaker_open": 0,
            "skipped_no_account": 0,
            "rejected_excluded": 0,
            "rejected_provenance": 0,
            "rejected_lower_tier": 0,
            "rejected_unverified_tier": 0,
            "breaker_trips": 0,
            "drift_engine_miss": 0,   # legacy wrote, engine did not
            "drift_legacy_miss": 0,   # engine wrote, legacy did not
        }

    # ── Flag / kill switch / breaker ─────────────────────────────────────────

    def enabled(self) -> bool:
        """True when the engine may write. Kill switch beats the enable flag."""
        if env_bool("RICO_MEMORY_ENGINE_KILL", False):
            return False
        return env_bool("RICO_MEMORY_ENGINE_ENABLED", False)

    def _breaker_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._breaker_open_until

    def _record_failure(self) -> None:
        with self._lock:
            self._metrics["failed"] += 1
            self._consecutive_failures += 1
            if self._consecutive_failures >= _BREAKER_THRESHOLD:
                self._breaker_open_until = time.monotonic() + _BREAKER_COOLDOWN_S
                self._consecutive_failures = 0
                self._metrics["breaker_trips"] += 1
                logger.error(
                    "memory_engine_breaker_open cooldown_s=%d — memory writes "
                    "suspended after repeated failures",
                    _BREAKER_COOLDOWN_S,
                )

    def _record_success(self, status: str) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._metrics[status] = self._metrics.get(status, 0) + 1

    def _count(self, key: str) -> None:
        with self._lock:
            self._metrics[key] = self._metrics.get(key, 0) + 1

    def metrics_snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._metrics)

    # ── Identity (ADR §3) ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_account_id(external_user_id: str) -> Optional[str]:
        """Map any external identity to the canonical rico_users.id UUID.

        Resolution only — the writer never creates identity rows as a side
        effect. Public sessions must resolve to their own exact row; anything
        else would be an implicit public→account merge, which ADR §3 forbids.
        """
        identity = (external_user_id or "").strip()
        if not identity:
            return None
        try:
            from src.rico_db import RicoDB

            db = RicoDB()
            if not db.available:
                return None
            bundle = db.get_user_bundle(identity)
            if not bundle:
                return None
            if identity.startswith("public:"):
                resolved_external = str(bundle.get("external_user_id") or "")
                if resolved_external != identity:
                    logger.warning(
                        "memory_engine_public_merge_blocked identity=%r resolved=%r",
                        identity, resolved_external,
                    )
                    return None
            account_id = str(bundle.get("id") or "").strip()
            return account_id or None
        except Exception:
            logger.debug("memory_engine: account resolution failed", exc_info=True)
            return None

    # ── Validation ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_provenance(
        *, source: str, actor: str, confidence: float,
        occurred_at: datetime,
        source_record_id: Optional[str], source_uri: Optional[str],
    ) -> None:
        if source not in SOURCE_TIERS:
            raise MemoryWriteRejected(f"invalid source tier: {source!r}")
        if actor not in ACTORS:
            raise MemoryWriteRejected(f"invalid actor: {actor!r}")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise MemoryWriteRejected(f"confidence out of range: {confidence!r}")
        if not isinstance(occurred_at, datetime):
            raise MemoryWriteRejected("occurred_at must be a datetime")
        if not source_record_id and not source_uri:
            raise MemoryWriteRejected(
                "provenance requires source_record_id and/or source_uri"
            )

    @classmethod
    def _check_exclusion(cls, payload: Any, _path: str = "") -> Optional[str]:
        """Return the offending key path when payload carries excluded material."""
        if isinstance(payload, dict):
            for key, value in payload.items():
                key_path = f"{_path}.{key}" if _path else str(key)
                if _EXCLUDED_KEY_RE.search(str(key)):
                    return key_path
                found = cls._check_exclusion(value, key_path)
                if found:
                    return found
        elif isinstance(payload, list):
            for i, item in enumerate(payload):
                found = cls._check_exclusion(item, f"{_path}[{i}]")
                if found:
                    return found
        return None

    # ── Writes ───────────────────────────────────────────────────────────────

    def record_event(
        self,
        *,
        external_user_id: str,
        event_type: str,
        idempotency_key: str,
        occurred_at: datetime,
        actor: str,
        source: str,
        confidence: float,
        payload: Dict[str, Any],
        source_record_id: Optional[str] = None,
        source_uri: Optional[str] = None,
        retention_class: str = "episode",
        version: int = 1,
    ) -> MemoryWriteResult:
        """Append one episode for the resolved canonical account."""
        self._validate_provenance(
            source=source, actor=actor, confidence=confidence,
            occurred_at=occurred_at,
            source_record_id=source_record_id, source_uri=source_uri,
        )
        if retention_class not in RETENTION_CLASSES:
            raise MemoryWriteRejected(f"invalid retention class: {retention_class!r}")
        if not event_type or not idempotency_key:
            raise MemoryWriteRejected("event_type and idempotency_key are required")

        if not self.enabled():
            self._count("skipped_disabled")
            return MemoryWriteResult(status="skipped_disabled")
        if self._breaker_open():
            self._count("skipped_breaker_open")
            return MemoryWriteResult(status="skipped_breaker_open")

        offending = self._check_exclusion(payload)
        if offending:
            self._count("rejected_excluded")
            logger.warning(
                "memory_engine_excluded_payload event_type=%s key=%s — write dropped",
                event_type, offending,
            )
            return MemoryWriteResult(status="rejected_excluded")

        account_id = self._resolve_account_id(external_user_id)
        if not account_id:
            self._count("skipped_no_account")
            return MemoryWriteResult(status="skipped_no_account")

        try:
            from src.repositories import career_memory_repo

            status = career_memory_repo.insert_event(
                account_id=account_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
                actor=actor,
                source=source,
                confidence=float(confidence),
                payload=payload,
                source_record_id=source_record_id,
                source_uri=source_uri,
                retention_class=retention_class,
                version=version,
            )
        except Exception:
            logger.warning("memory_engine_event_write_failed type=%s", event_type,
                           exc_info=True)
            self._record_failure()
            return MemoryWriteResult(status="failed", account_id=account_id)

        self._record_success(status)
        logger.debug("memory_engine_event status=%s type=%s", status, event_type)
        return MemoryWriteResult(status=status, account_id=account_id)

    def record_fact(
        self,
        *,
        external_user_id: str,
        fact_key: str,
        fact_class: str,
        value: Any,
        idempotency_key: str,
        occurred_at: datetime,
        actor: str,
        source: str,
        confidence: float,
        source_record_id: Optional[str] = None,
        source_uri: Optional[str] = None,
        retention_class: str = "core_fact",
        effective_from: Optional[datetime] = None,
        effective_to: Optional[datetime] = None,
    ) -> MemoryWriteResult:
        """Write one fact with history semantics (ADR §7).

        M1 notes: time_bound overlap detection and the verified_only
        "queue as unverified" path are M6 scope (conflict-resolution UX) —
        here an unverified write to a verified_only fact is rejected and
        counted, never silently stored.
        """
        self._validate_provenance(
            source=source, actor=actor, confidence=confidence,
            occurred_at=occurred_at,
            source_record_id=source_record_id, source_uri=source_uri,
        )
        if fact_class not in FACT_CLASSES:
            raise MemoryWriteRejected(f"invalid fact class: {fact_class!r}")
        if retention_class not in RETENTION_CLASSES:
            raise MemoryWriteRejected(f"invalid retention class: {retention_class!r}")
        if not fact_key or not idempotency_key:
            raise MemoryWriteRejected("fact_key and idempotency_key are required")

        if not self.enabled():
            self._count("skipped_disabled")
            return MemoryWriteResult(status="skipped_disabled")
        if self._breaker_open():
            self._count("skipped_breaker_open")
            return MemoryWriteResult(status="skipped_breaker_open")

        offending = self._check_exclusion({fact_key: value})
        if offending:
            self._count("rejected_excluded")
            logger.warning(
                "memory_engine_excluded_payload fact_key=%s key=%s — write dropped",
                fact_key, offending,
            )
            return MemoryWriteResult(status="rejected_excluded")

        if fact_class == "verified_only" and source != "verified_event":
            self._count("rejected_unverified_tier")
            logger.info(
                "memory_engine_unverified_rejected fact_key=%s source=%s "
                "(verified_only accepts verified_event; queue path is M6)",
                fact_key, source,
            )
            return MemoryWriteResult(status="rejected_unverified_tier")

        account_id = self._resolve_account_id(external_user_id)
        if not account_id:
            self._count("skipped_no_account")
            return MemoryWriteResult(status="skipped_no_account")

        try:
            from src.repositories import career_memory_repo

            # Trust hierarchy: a lower tier never supersedes the current value
            # of a higher tier (ADR §7).
            if fact_class in ("replaceable", "verified_only"):
                current = career_memory_repo.get_current_fact(
                    account_id=account_id, fact_key=fact_key
                )
                if current and _TIER_RANK[source] < _TIER_RANK.get(
                    str(current.get("source")), 0
                ):
                    self._count("rejected_lower_tier")
                    logger.info(
                        "memory_engine_lower_tier_rejected fact_key=%s new=%s current=%s",
                        fact_key, source, current.get("source"),
                    )
                    return MemoryWriteResult(
                        status="rejected_lower_tier", account_id=account_id
                    )

            status = career_memory_repo.insert_fact(
                account_id=account_id,
                fact_key=fact_key,
                fact_class=fact_class,
                value=value,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
                actor=actor,
                source=source,
                confidence=float(confidence),
                source_record_id=source_record_id,
                source_uri=source_uri,
                retention_class=retention_class,
                effective_from=effective_from,
                effective_to=effective_to,
            )
        except Exception:
            logger.warning("memory_engine_fact_write_failed key=%s", fact_key,
                           exc_info=True)
            self._record_failure()
            return MemoryWriteResult(status="failed", account_id=account_id)

        self._record_success(status)
        logger.debug("memory_engine_fact status=%s key=%s", status, fact_key)
        return MemoryWriteResult(status=status, account_id=account_id)

    # ── M1 shadow integration (agent_runtime step 11b) ───────────────────────

    def record_job_action_shadow(
        self,
        *,
        external_user_id: str,
        action: str,
        job: Dict[str, Any],
        action_id: str,
        surface: str,
        legacy_write_ok: bool,
    ) -> None:
        """Mirror one job action into the engine alongside the legacy
        career_memory write. Fire-and-forget: NEVER raises, never changes any
        user-visible behavior (M1 contract).

        Idempotency: the runtime's action_id is stable for user+action+job, and
        the audit dedup window re-admits the same action after 1 hour — a
        legitimate new episode. The hour bucket keeps racing duplicate calls
        (seconds apart, same action_id) collapsed by the unique constraint
        while >1-hour re-executions land as distinct episodes.
        """
        try:
            if action not in SHADOW_ACTIONS:
                return
            if not self.enabled():
                self._count("skipped_disabled")
                return

            occurred_at = datetime.now(timezone.utc)
            payload = {
                # Mirrors exactly what the legacy store keeps (title, company,
                # job key, action) — payload minimization per ADR §8.
                "action": action,
                "title": str(job.get("title") or ""),
                "company": str(job.get("company") or ""),
                "job_key": str(job.get("id") or job.get("job_key") or ""),
                "surface": str(surface or ""),
            }
            result = self.record_event(
                external_user_id=external_user_id,
                event_type=f"job_action.{action}",
                idempotency_key=f"job_action:{action_id}:{occurred_at:%Y%m%dT%H}",
                occurred_at=occurred_at,
                actor="user",
                source="verified_event",
                confidence=1.0,
                payload=payload,
                # Provenance link to the authoritative audit record for this
                # execution (action_audit_log.action_id).
                source_record_id=f"action_audit_log:{action_id}",
                retention_class="episode",
            )

            # Drift metrics (ADR §M1): compare per-write outcomes of the legacy
            # store and the engine while both are written in parallel.
            engine_ok = result.ok
            if legacy_write_ok and not engine_ok:
                self._count("drift_engine_miss")
                logger.warning(
                    "memory_drift engine_miss action=%s status=%s", action, result.status
                )
            elif engine_ok and not legacy_write_ok:
                self._count("drift_legacy_miss")
                logger.warning("memory_drift legacy_miss action=%s", action)
        except Exception:
            # M1 contract: the shadow write may never affect the action path.
            logger.debug("memory_engine: shadow write failed", exc_info=True)


# Module-level singleton — import and use directly:
#   from src.services.memory_writer import memory_writer
memory_writer = MemoryWriter()
