"use client";

import { fetchProfile, getApplicationStats, getMySubscription, getApplicationQueue } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

// Read-only career-status feed for the desktop sidebar workspace.
// Reuses existing API helpers only — no new endpoints, no backend changes.
// Each source fails independently and silently so a failure hides one module
// without ever breaking navigation or blocking render.

export interface SidebarReadiness {
    completeness: number | null; // 0–100
    targetRoles: number;
}

export interface SidebarPipeline {
    applied: number;
    interview: number;
    offer: number;
    saved: number;
    total: number;
}

export interface SidebarPlan {
    plan: "free" | "pro" | "premium";
    active: boolean;
}

export interface SidebarStatus {
    readiness: SidebarReadiness | null;
    pipeline: SidebarPipeline | null;
    plan: SidebarPlan | null;
    queueCount: number;
    loading: boolean;
    error: boolean;
    refresh: () => void;
}

type StatusData = Pick<SidebarStatus, "readiness" | "pipeline" | "plan" | "queueCount">;

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
const TTL_MS = 60_000;

// Module-level cache + in-flight dedupe so the reads are shared across every
// page that renders the sidebar. Only SUCCESSFUL loads are cached — a failed
// load is never stored, so the next mount retries instead of serving stuck
// empty widgets (the "blank grey boxes on navigate back" bug).
let cache: { at: number; data: StatusData } | null = null;
let inflight: Promise<StatusData> | null = null;

/** Drop the module-level sidebar cache so the next render fetches fresh stats.
 *  Call this after any action that changes pipeline counts (e.g. chat save). */
export function bustSidebarCache(): void {
    cache = null;
}

function clampPct(v: number | null | undefined): number | null {
    if (v == null) return null;
    const n = v > 1 ? v : v * 100; // accept 0–1 or 0–100
    return Math.max(0, Math.min(100, Math.round(n)));
}

async function loadStatus(): Promise<StatusData> {
    if (USE_MOCK) {
        return {
            readiness: { completeness: 72, targetRoles: 3 },
            pipeline: { applied: 5, interview: 2, offer: 1, saved: 3, total: 11 },
            plan: { plan: "free", active: false },
            queueCount: 2,
        };
    }

    // allSettled so one rejection only hides its own module.
    const [profileR, statsR, subR, queueR] = await Promise.allSettled([
        fetchProfile(),
        getApplicationStats(),
        getMySubscription(),
        getApplicationQueue(),
    ]);

    // A cold/unreachable backend fails every read at once. Throwing here keeps
    // getStatus() from caching an all-empty result, so navigating back retries
    // instead of showing stuck blank widgets.
    if (profileR.status === "rejected" && statsR.status === "rejected") {
        throw new Error("sidebar-status: core sources unavailable");
    }

    const profile = profileR.status === "fulfilled" ? profileR.value : null;
    const stats = statsR.status === "fulfilled" ? statsR.value : null;
    const sub = subR.status === "fulfilled" ? subR.value : null;
    const queue = queueR.status === "fulfilled" ? queueR.value : null;

    const readiness: SidebarReadiness | null =
        profile && profile.profile_exists
            ? {
                  completeness: clampPct(profile.completeness_score),
                  targetRoles: profile.target_roles?.length ?? 0,
              }
            : null;

    let pipeline: SidebarPipeline | null = null;
    if (stats) {
        const applied = stats.applied ?? 0;
        const interview = stats.interview ?? 0;
        const offer = stats.offer ?? 0;
        const saved = stats.saved ?? 0;
        const rejected = stats.rejected ?? 0;
        // Use the authoritative total from the backend (includes all statuses:
        // saved, opened, prepared, applied, follow_up_due, interview, offer,
        // rejected, decision_made) rather than summing the 5 explicit fields.
        const total = typeof stats.total === "number" ? stats.total
            : applied + interview + offer + saved + rejected;
        pipeline = {
            applied,
            interview,
            offer,
            saved,
            total,
        };
    }

    const plan: SidebarPlan | null = sub?.subscription
        ? { plan: sub.subscription.plan, active: sub.is_active }
        : null;

    const queueCount = Array.isArray(queue) ? queue.length : 0;

    return { readiness, pipeline, plan, queueCount };
}

function getStatus(force = false): Promise<StatusData> {
    if (!force && cache && Date.now() - cache.at < TTL_MS) return Promise.resolve(cache.data);
    if (inflight) return inflight;
    inflight = loadStatus()
        .then((data) => {
            cache = { at: Date.now(), data };
            return data;
        })
        .finally(() => {
            inflight = null;
        });
    return inflight;
}

/**
 * Read-only sidebar career status. `enabled` must be the authenticated-session
 * signal so logged-out users never trigger a fetch. Serves cached data
 * immediately and revalidates on mount, so navigating back to a page recovers
 * from an earlier failed/empty load (failures are never cached). `refresh()`
 * forces a TTL-bypassing reload (used by the error-state retry affordance).
 */
export function useSidebarStatus(enabled: boolean): SidebarStatus {
    const [state, setState] = useState<Omit<SidebarStatus, "refresh">>(() => ({
        readiness: cache?.data.readiness ?? null,
        pipeline: cache?.data.pipeline ?? null,
        plan: cache?.data.plan ?? null,
        queueCount: cache?.data.queueCount ?? 0,
        loading: enabled && !cache,
        error: false,
    }));

    // Bumped by refresh() to force a TTL-bypassing refetch.
    const [refreshTick, setRefreshTick] = useState(0);

    useEffect(() => {
        if (!enabled) return;
        let active = true;

        // Serve cached data instantly (no flicker); show the skeleton only when
        // there is nothing cached yet.
        if (cache) {
            setState({ ...cache.data, loading: false, error: false });
        } else {
            setState((s) => ({ ...s, loading: true, error: false }));
        }

        getStatus(refreshTick > 0)
            .then((data) => {
                if (active) setState({ ...data, loading: false, error: false });
            })
            .catch(() => {
                if (!active) return;
                // Surface the retry affordance only when there is nothing to
                // show; otherwise keep the data we already have on screen.
                setState((s) =>
                    s.readiness || s.pipeline
                        ? { ...s, loading: false, error: false }
                        : {
                              readiness: null,
                              pipeline: null,
                              plan: null,
                              queueCount: 0,
                              loading: false,
                              error: true,
                          }
                );
            });

        return () => {
            active = false;
        };
    }, [enabled, refreshTick]);

    const refresh = useCallback(() => setRefreshTick((n) => n + 1), []);

    return { ...state, refresh };
}
