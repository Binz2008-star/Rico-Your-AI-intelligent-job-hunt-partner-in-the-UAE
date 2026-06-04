"use client";

import { AppShell } from "@/components/layout/AppShell";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { ApplicationDraftCard } from "@/components/queue/ApplicationDraftCard";
import {
    getApplicationQueue,
    approveApplication,
    rejectApplication,
    logout,
    type ApplicationDraft,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function QueuePage() {
    const { user, ready, logout: doLogout } = useAuth();
    const router = useRouter();
    const [drafts, setDrafts] = useState<ApplicationDraft[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!ready) return;
        if (!user) {
            router.push("/login");
            return;
        }
        const ctrl = new AbortController();
        setLoading(true);
        getApplicationQueue(ctrl.signal)
            .then((data) => {
                setDrafts(data);
                setError(null);
            })
            .catch((err) => {
                if (err.name !== "AbortError") setError("Could not load your queue. Try refreshing.");
            })
            .finally(() => setLoading(false));
        return () => ctrl.abort();
    }, [ready, user, router]);

    const handleApprove = useCallback(async (id: string) => {
        await approveApplication(id);
        setDrafts((prev) => prev.filter((d) => d.id !== id));
    }, []);

    const handleReject = useCallback(async (id: string) => {
        await rejectApplication(id);
        setDrafts((prev) => prev.filter((d) => d.id !== id));
    }, []);

    const handleLogout = useCallback(async () => {
        await doLogout();
    }, [doLogout]);

    return (
        <AppShell
            title="Apply Queue"
            subtitle="AI-prepared applications ready for your approval"
            sidebarProps={{ user: user ?? undefined, onLogout: handleLogout }}
        >
            {loading ? (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className="h-64 animate-pulse rounded-xl border border-overlay/10 bg-surface-subtle/40 motion-reduce:animate-none"
                        />
                    ))}
                </div>
            ) : error ? (
                <div className="flex flex-col items-center gap-3 py-20 text-center">
                    <MaterialIcon icon="error_outline" size={40} className="text-text-tertiary" />
                    <p className="text-text-secondary">{error}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="mt-2 rounded-lg border border-overlay/10 px-4 py-2 text-sm text-text-secondary hover:bg-surface-subtle"
                    >
                        Retry
                    </button>
                </div>
            ) : drafts.length === 0 ? (
                <div className="flex flex-col items-center gap-4 py-24 text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gold/10">
                        <MaterialIcon icon="rocket_launch" size={32} className="text-gold" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-text-primary">Queue is empty</h2>
                        <p className="mt-1 max-w-sm text-sm text-text-secondary">
                            Ask Rico to prepare applications for jobs in your Pipeline. Rico will tailor your CV and write a cover letter — you approve before anything is sent.
                        </p>
                    </div>
                    <a
                        href="/command"
                        className="mt-2 flex items-center gap-2 rounded-lg bg-gold px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                    >
                        <MaterialIcon icon="auto_awesome" size={16} />
                        Ask Rico to prepare applications
                    </a>
                </div>
            ) : (
                <div className="space-y-5">
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-text-secondary">
                            <span className="font-semibold text-text-primary">{drafts.length}</span>{" "}
                            application{drafts.length === 1 ? "" : "s"} ready for review
                        </p>
                    </div>
                    {drafts.map((draft) => (
                        <ApplicationDraftCard
                            key={draft.id}
                            draft={draft}
                            onApprove={handleApprove}
                            onReject={handleReject}
                        />
                    ))}
                </div>
            )}
        </AppShell>
    );
}
