"use client";

/**
 * useMissionSummary — single cached read of GET /api/v1/mission/current for
 * the shared WorkspaceShell chrome (rail goal-mini + applications nav count,
 * PR-V4-2a, DEC-20260719-002).
 *
 * Fetch discipline (the PR-V4-2b fold-in evidence):
 *  - ONE request per session window: a module-level cache (60s TTL) with
 *    in-flight promise dedupe means every shell consumer — and repeated
 *    route-to-route shell mounts — share a single GET. The applications
 *    count rides the same response (`applications_sent`), so the nav chip
 *    adds ZERO additional requests.
 *  - Non-blocking: the shell renders immediately; mission data fills in
 *    when (and only if) the request succeeds.
 *  - Fail-hidden: loading, error, and disabled all return null — consumers
 *    render nothing and the shell stays byte-identical to today.
 *  - `enabled=false` (app-variant shells, /dashboard where the goal panel
 *    already shows the same data) never fires a request at all.
 */

import { useEffect, useState } from "react";
import { getMission, type MissionState } from "@/lib/api";

const TTL_MS = 60_000;

let cache: { value: MissionState; at: number } | null = null;
let inflight: Promise<MissionState> | null = null;

/** Test-only: clear the module cache between cases. */
export function _resetMissionSummaryCache(): void {
    cache = null;
    inflight = null;
}

function freshCache(): MissionState | null {
    return cache && Date.now() - cache.at < TTL_MS ? cache.value : null;
}

export function useMissionSummary(enabled: boolean): MissionState | null {
    const [mission, setMission] = useState<MissionState | null>(() =>
        enabled ? freshCache() : null,
    );

    useEffect(() => {
        if (!enabled) return;
        const cached = freshCache();
        if (cached) {
            setMission(cached);
            return;
        }
        let cancelled = false;
        let request = inflight;
        if (!request) {
            // Fail-hidden covers synchronous throws too (e.g. a partially
            // mocked api module in tests) — the shell must never crash for
            // this optional chrome data.
            try {
                request = inflight = getMission().finally(() => {
                    inflight = null;
                });
            } catch {
                return;
            }
        }
        request
            .then((m) => {
                cache = { value: m, at: Date.now() };
                if (!cancelled) setMission(m);
            })
            .catch(() => {
                /* fail-hidden — consumers render nothing */
            });
        return () => {
            cancelled = true;
        };
    }, [enabled]);

    return enabled ? mission : null;
}
