"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ScheduledSearchCard } from "@/components/ScheduledSearchCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { StatusCard } from "@/components/StatusCard";
import { useAuth } from "@/hooks/useAuth";
import {
    fetchSavedSearches,
    fetchScheduledSearches,
    logout as apiLogout,
    type SavedSearch,
    type ScheduledSearch,
} from "@/lib/api";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function SavedSearchesPage() {
    const [searches, setSearches] = useState<SavedSearch[]>([]);
    const [scheduled, setScheduled] = useState<ScheduledSearch[]>([]);
    const [error, setError] = useState(false);
    const [loading, setLoading] = useState(true);
    const { user } = useAuth();
    const router = useRouter();

    const handleLogout = useCallback(async () => {
        try { await apiLogout(); } finally { router.push("/login"); }
    }, [router]);

    const loadSearches = useCallback(async () => {
        try {
            // Scheduled searches (#1249) render as first-class cards; plain
            // saved searches keep the simple list. The generic endpoint also
            // returns schedule rows, so they're filtered out of the plain list
            // to avoid double-rendering the same row.
            const [plain, sched] = await Promise.all([
                fetchSavedSearches(),
                fetchScheduledSearches().catch(
                    () => ({ schedules: [], total: 0 }),
                ),
            ]);
            const scheduledIds = new Set(
                sched.schedules.map((s) => s.id).filter(Boolean),
            );
            setSearches(plain.searches.filter((s) => !scheduledIds.has(s.id)));
            setScheduled(sched.schedules);
            setError(false);
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadSearches();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadSearches]);

    const handleRetry = useCallback(() => {
        setError(false);
        setLoading(true);
        void loadSearches();
    }, [loadSearches]);

    return (
        <AppShell
            title="Saved Searches"
            sidebarProps={{
                user: user ? { name: user.name, email: user.email } : undefined,
                onLogout: handleLogout,
            }}
        >
            <div className="max-w-2xl">
                {loading && <LoadingState variant="card" message="Loading saved searches…" />}

                {!loading && error && (
                    <ErrorState
                        variant="network"
                        onRetry={handleRetry}
                    />
                )}

                {!loading && !error && scheduled.length > 0 && (
                    <div className="mb-4 flex flex-col gap-3">
                        {scheduled.map((item) => (
                            <ScheduledSearchCard
                                key={item.id ?? item.query ?? "schedule"}
                                item={item}
                                onChanged={() => {
                                    void loadSearches();
                                }}
                            />
                        ))}
                    </div>
                )}

                {!loading && !error && scheduled.length === 0 && searches.length === 0 && (
                    <EmptyState
                        title="No saved searches yet"
                        description="Use the Rico chat to save a job search — or say “search daily for jobs in Dubai” to schedule one."
                        actionLabel="Open chat"
                        actionHref="/command"
                    />
                )}

                {!loading && !error && searches.length > 0 && (
                    <StatusCard
                        title="Saved searches"
                        badge="live"
                        value={String(searches.length)}
                    >
                        <ul className="mt-1 flex flex-col gap-2">
                            {searches.map((s) => (
                                <li
                                    key={s.id}
                                    className="flex items-start justify-between gap-3 rounded-lg bg-white/[0.03] px-3 py-2.5"
                                >
                                    <span className="text-sm text-rico-text break-all">
                                        {s.query}
                                    </span>
                                    <span className="shrink-0 text-xs text-rico-text-dim mt-0.5">
                                        {new Date(s.created_at).toLocaleDateString()}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </StatusCard>
                )}
            </div>
        </AppShell>
    );
}
