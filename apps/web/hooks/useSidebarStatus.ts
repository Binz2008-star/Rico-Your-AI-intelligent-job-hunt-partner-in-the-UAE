"use client";

import { fetchProfile, getApplicationStats, getMySubscription, getApplicationQueue } from "@/lib/api";
import { useEffect, useState } from "react";

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
}

type StatusData = Omit<SidebarStatus, "loading">;

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
const TTL_MS = 60_000;

// Module-level cache + in-flight dedupe so the three reads happen once per
// session and are shared across every page that renders the sidebar.
let cache: { at: number; data: StatusData } | null = null;
let inflight: Promise<StatusData> | null = null;

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

    // Isolated so one rejection only hides its own module.
    const [profile, stats, sub, queue] = await Promise.all([
        fetchProfile().catch(() => null),
        getApplicationStats().catch(() => null),
        getMySubscription().catch(() => null),
        getApplicationQueue().catch(() => null),
    ]);

    const readiness: SidebarReadiness | null =
        profile && profile.profile_exists
            ? {
                  completeness: clampPct(profile.completeness_score),
                  targetRoles: profile.target_roles?.length ?? 0,
              }
            : null;

    let pipeline: SidebarPipeline | null = null;
    if (stats) {
        const total = Object.values(stats).reduce((a, b) => a + (b ?? 0), 0);
        pipeline = {
            applied: stats.applied ?? 0,
            interview: stats.interview ?? 0,
            offer: stats.offer ?? 0,
            saved: stats.saved ?? 0,
            total,
        };
    }

    const plan: SidebarPlan | null = sub?.subscription
        ? { plan: sub.subscription.plan, active: sub.is_active }
        : null;

    const queueCount = Array.isArray(queue) ? queue.length : 0;

    return { readiness, pipeline, plan, queueCount };
}

function getStatus(): Promise<StatusData> {
    if (cache && Date.now() - cache.at < TTL_MS) return Promise.resolve(cache.data);
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
 * immediately and revalidates in the background (stale-while-revalidate).
 */
export function useSidebarStatus(enabled: boolean): SidebarStatus {
    const [state, setState] = useState<SidebarStatus>(() => ({
        readiness: cache?.data.readiness ?? null,
        pipeline: cache?.data.pipeline ?? null,
        plan: cache?.data.plan ?? null,
        queueCount: cache?.data.queueCount ?? 0,
        loading: enabled && !cache,
    }));

    useEffect(() => {
        if (!enabled) return; // never fetch for logged-out users
        let active = true;

        if (cache) {
            setState({ ...cache.data, loading: false });
        } else {
            setState((s) => ({ ...s, loading: true }));
        }

        getStatus()
            .then((data) => {
                if (active) setState({ ...data, loading: false });
            })
            .catch(() => {
                if (active) setState((s) => ({ ...s, loading: false }));
            });

        return () => {
            active = false;
        };
    }, [enabled]);

    return state;
}
