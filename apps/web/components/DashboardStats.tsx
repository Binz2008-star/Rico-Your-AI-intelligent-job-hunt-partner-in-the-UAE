"use client";

import { StatusCard } from "@/components/StatusCard";
import {
    ApiError,
    getApplications,
    getApplicationStats,
    getJobs,
    getSettings,
} from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

interface Stats {
    jobsTotal: number;
    appsTotal: number;
    applied: number;
    interview: number;
    offer: number;
    rejected: number;
    maxDaily: number;
    jobsAvailable: boolean;
    applicationsAvailable: boolean;
    applicationStatsAvailable: boolean;
    settingsAvailable: boolean;
    jobsError: string | null;
    applicationsError: string | null;
    settingsError: string | null;
}

const DASHBOARD_REQUEST_TIMEOUT_MS = 5000;

const EMPTY_STATS: Stats = {
    jobsTotal: 0,
    appsTotal: 0,
    applied: 0,
    interview: 0,
    offer: 0,
    rejected: 0,
    maxDaily: 0,
    jobsAvailable: false,
    applicationsAvailable: false,
    applicationStatsAvailable: false,
    settingsAvailable: false,
    jobsError: null,
    applicationsError: null,
    settingsError: null,
};

type LoadResult<T> =
    | { status: "fulfilled"; value: T }
    | { status: "rejected"; reason: unknown };

function asCount(value: unknown): number {
    return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

async function loadWithTimeout<T>(
    loader: (signal: AbortSignal) => Promise<T>,
    timeoutMs = DASHBOARD_REQUEST_TIMEOUT_MS
): Promise<LoadResult<T>> {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
        const value = await loader(controller.signal);
        return { status: "fulfilled", value };
    } catch (reason) {
        return { status: "rejected", reason };
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function getLoadError(label: string, reason: unknown): string {
    if (reason instanceof ApiError) {
        return `${label} request failed (${reason.statusCode}).`;
    }

    if (reason instanceof Error && reason.name === "AbortError") {
        return `${label} request timed out after 5s.`;
    }

    if (reason instanceof Error && reason.message) {
        return `${label} unavailable: ${reason.message}`;
    }

    return `${label} unavailable right now.`;
}

function getJobsCopy(stats: Stats): string {
    if (stats.jobsError) return stats.jobsError;
    if (!stats.jobsAvailable) return "Match count unavailable right now.";
    if (stats.jobsTotal === 0) return "No matches yet — Rico will scan soon.";
    return "Active job recommendations";
}

function getApplicationsCopy(stats: Stats): string {
    if (stats.applicationsError) {
        return stats.applicationsError;
    }
    if (!stats.applicationsAvailable && !stats.applicationStatsAvailable) {
        return "Application flow unavailable right now.";
    }
    if (stats.appsTotal === 0) return "No tracked applications yet.";

    const parts: string[] = [];

    if (stats.applied > 0) parts.push(`${stats.applied} applied`);
    if (stats.interview > 0) parts.push(`${stats.interview} interview`);
    if (stats.offer > 0) parts.push(`${stats.offer} offer`);
    if (stats.rejected > 0) parts.push(`${stats.rejected} rejected`);

    return parts.length > 0 ? parts.join(" · ") : "Tracking active applications.";
}

function getDailyLimitCopy(stats: Stats): string {
    if (stats.settingsError) return stats.settingsError;
    if (!stats.settingsAvailable) return "Apply pacing unavailable right now.";
    if (stats.maxDaily > 0) return `Apply pacing limit: ${stats.maxDaily}`;
    return "Apply pacing not set yet.";
}

export function DashboardStats() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<"auth" | null>(null);

    const loadData = useCallback(async () => {
        try {
            const [jobsResult, appsResult, statsResult, settingsResult] =
                await Promise.all([
                    loadWithTimeout((signal) => getJobs(1, 1, 0, undefined, signal)),
                    loadWithTimeout((signal) => getApplications(undefined, 1, 1, signal)),
                    loadWithTimeout((signal) => getApplicationStats(signal)),
                    loadWithTimeout((signal) => getSettings(signal)),
                ]);

            const authFailure = [jobsResult, appsResult, statsResult, settingsResult].some(
                (result) =>
                    result.status === "rejected" &&
                    result.reason instanceof ApiError &&
                    result.reason.statusCode === 401
            );

            if (authFailure) {
                setError("auth");
                return;
            }

            const jobsRes = jobsResult.status === "fulfilled" ? jobsResult.value : null;
            const appsRes = appsResult.status === "fulfilled" ? appsResult.value : null;
            const statsRes = statsResult.status === "fulfilled" ? statsResult.value : null;
            const settingsRes = settingsResult.status === "fulfilled" ? settingsResult.value : null;
            const jobsError = jobsResult.status === "rejected" ? getLoadError("Jobs", jobsResult.reason) : null;
            const appsError = appsResult.status === "rejected" ? getLoadError("Applications", appsResult.reason) : null;
            const statsError = statsResult.status === "rejected" ? getLoadError("Application stats", statsResult.reason) : null;
            const settingsError = settingsResult.status === "rejected" ? getLoadError("Settings", settingsResult.reason) : null;

            setError(null);
            setStats({
                jobsTotal: jobsRes?.total ?? 0,
                appsTotal: appsRes?.total ?? 0,
                applied: asCount(statsRes?.applied),
                interview: asCount(statsRes?.interview),
                offer: asCount(statsRes?.offer),
                rejected: asCount(statsRes?.rejected),
                maxDaily: asCount(settingsRes?.max_daily_applies),
                jobsAvailable: jobsRes !== null,
                applicationsAvailable: appsRes !== null,
                applicationStatsAvailable: statsRes !== null,
                settingsAvailable: settingsRes !== null,
                jobsError,
                applicationsError: appsError ?? statsError,
                settingsError,
            });
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : null);
            setStats(EMPTY_STATS);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadData();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadData]);

    if (loading) return <StatsSkeleton />;

    if (error === "auth") return <ErrorMessage message="Session expired — please log in again." icon="🔒" />;

    if (!stats) return <ErrorMessage message="Could not load dashboard stats." icon="⚠️" />;

    return (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatusCard
                title="Scored opportunities"
                badge={stats.jobsAvailable ? "live" : "placeholder"}
                value={String(stats.jobsTotal)}
                href={stats.jobsError ? undefined : "/jobs"}
            >
                <p className="text-sm text-on-surface-variant">
                    {getJobsCopy(stats)}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                    {stats.jobsError ? (
                        <button
                            type="button"
                            onClick={() => {
                                setLoading(true);
                                void loadData();
                            }}
                            className="rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1.5 text-[12px] font-semibold text-cyan transition-colors hover:bg-cyan/15"
                        >
                            Retry jobs
                        </button>
                    ) : (
                        <span className="text-[12px] font-semibold text-cyan">Review matches</span>
                    )}
                </div>
            </StatusCard>
            <StatusCard
                title="Applications in flow"
                badge={stats.applicationsAvailable || stats.applicationStatsAvailable ? "live" : "placeholder"}
                value={String(stats.appsTotal)}
                href="/flow"
            >
                <p className="text-sm text-on-surface-variant">
                    {getApplicationsCopy(stats)}
                </p>
                <span className="mt-3 inline-flex text-[12px] font-semibold text-cyan">Open Flow</span>
            </StatusCard>
            <StatusCard
                title="Apply pacing"
                badge={stats.settingsAvailable && stats.maxDaily > 0 ? "live" : "placeholder"}
                value={stats.maxDaily > 0 ? String(stats.maxDaily) : "—"}
                href="/settings"
            >
                <p className="text-sm text-on-surface-variant">{getDailyLimitCopy(stats)}</p>
                <span className="mt-3 inline-flex text-[12px] font-semibold text-cyan">Review settings</span>
            </StatusCard>
        </div>
    );
}

function StatsSkeleton() {
    return (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
                <div
                    key={i}
                    className="glass-panel h-28 rounded-[24px] border border-white/10 animate-pulse motion-reduce:animate-none transition-all duration-300"
                />
            ))}
        </div>
    );
}

function ErrorMessage({ message, icon }: { message: string; icon: string }) {
    return (
        <div className="glass-panel rounded-[24px] border border-white/10 p-5 text-center">
            <span className="text-2xl block mb-2">{icon}</span>
            <p className="text-sm font-medium text-on-surface-variant">{message}</p>
        </div>
    );
}
