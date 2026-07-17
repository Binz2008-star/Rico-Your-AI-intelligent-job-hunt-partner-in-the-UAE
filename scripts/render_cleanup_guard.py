#!/usr/bin/env python3
"""#1084 — validation gate for the Render mutation workflow.

The cleanup workflow may DELETE Render services. This guard replaces the old
"delete everything except one name" negative filter with a fail-closed,
positive allowlist contract:

* Targets are EXPLICIT service ids (``srv-…``) supplied by the operator.
* A second confirmation input must repeat the exact same id list — the
  confirmation is bound to the rendered target set, not a bare "yes".
* The production service is resolved live BY NAME. If it cannot be found
  (deleted, renamed, API shape change) the guard refuses to authorize ANY
  mutation — so a renamed production service can never fall through into a
  deletion set.
* Every target must exist in the live service list at validation time; a
  stale or mistyped id refuses the whole set (no partial deletes).

The guard never prints tokens or authenticated response bodies — its only
input is the parsed service list (id/name metadata) and the operator inputs.

Exit codes: 0 = validated (preview printed), 2 = refused (reason code printed).
"""

from __future__ import annotations

import json
import re
import sys

PRODUCTION_SERVICE_NAME = "rico-job-automation-api"
_SERVICE_ID_RE = re.compile(r"^srv-[A-Za-z0-9]+$")


class GuardError(Exception):
    """Refusal with a stable, log-safe reason code."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(code)


def parse_service_list(data) -> list[tuple[str, str]]:
    """Normalize the Render /v1/services response into (id, name) pairs."""
    services = []
    if not isinstance(data, list):
        raise GuardError("unexpected_service_list_shape")
    for item in data:
        s = item.get("service", item) if isinstance(item, dict) else {}
        sid = s.get("id", "")
        name = s.get("name", "")
        if sid:
            services.append((sid, name))
    return services


def _parse_id_list(raw: str) -> list[str]:
    return [t for t in re.split(r"[,\s]+", (raw or "").strip()) if t]


def validate(
    services: list[tuple[str, str]],
    targets_raw: str,
    confirm_raw: str,
) -> tuple[list[str], list[str]]:
    """Validate the operator-supplied target set against the live services.

    Returns (validated_target_ids, preview_lines) or raises GuardError.
    """
    targets = _parse_id_list(targets_raw)
    confirm = _parse_id_list(confirm_raw)

    if not targets:
        raise GuardError("empty_target_set")
    for t in targets:
        if not _SERVICE_ID_RE.match(t):
            raise GuardError("invalid_service_id", t)
    if len(set(targets)) != len(targets):
        raise GuardError("duplicate_target")
    # Second confirmation is bound to the EXACT target set (same ids, same
    # order) — a generic "yes" or a stale paste refuses the run.
    if confirm != targets:
        raise GuardError("confirmation_mismatch")

    by_id = dict(services)

    # Fail closed if production cannot be identified by its canonical name:
    # a renamed production service must make the workflow refuse entirely,
    # never become an implicit deletion candidate.
    production_ids = [sid for sid, name in services if name == PRODUCTION_SERVICE_NAME]
    if len(production_ids) != 1:
        raise GuardError("production_service_not_found")
    production_id = production_ids[0]

    if production_id in targets:
        raise GuardError("production_service_targeted", production_id)

    for t in targets:
        if t not in by_id:
            # Unknown OR no-longer-present id: the operator's set is stale or
            # mistyped — refuse the whole run rather than delete a subset.
            raise GuardError("unknown_target", t)

    preview = [f"{t} | {by_id[t]}" for t in targets]
    return targets, preview


def main(argv: list[str]) -> int:
    import os

    if len(argv) < 2:
        print("usage: render_cleanup_guard.py <services.json>")
        return 2
    try:
        with open(argv[1]) as f:
            data = json.load(f)
    except Exception:
        # Never echo the body of an authenticated response — status only.
        print("GUARD REFUSED: unparseable_service_list (body suppressed)")
        return 2

    try:
        services = parse_service_list(data)
        targets, preview = validate(
            services,
            os.environ.get("TARGET_SERVICE_IDS", ""),
            os.environ.get("CONFIRM_SERVICE_IDS", ""),
        )
    except GuardError as exc:
        detail = f" ({exc.detail})" if exc.detail else ""
        print(f"GUARD REFUSED: {exc.code}{detail}")
        return 2

    print(f"GUARD OK: {len(targets)} validated deletion target(s):")
    for line in preview:
        print("  DELETE", line)
    print(f"  KEEP   (production, by name) {PRODUCTION_SERVICE_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
