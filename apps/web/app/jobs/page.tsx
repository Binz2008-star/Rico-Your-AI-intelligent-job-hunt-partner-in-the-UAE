"use client";

import { AppShell } from "@/components/layout/AppShell";
import { JobCard } from "@/components/jobs/JobCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { SkeletonCard } from "@/components/shared/LoadingState";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { ApiError, createApplication, getJobs, logout as apiLogout, saveJob, skipJob, updateApplication } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import type { Job } from "@/types";
import { useCallback, useEffect, useMemo, useState } from "react";

const SCORE_THRESHOLDS = { HIGH: 85, MID: 65 };
const SUCCESS_STATUSES = ["applied", "success", "submitted", "saved"];
const TRACKED_STATUSES = ["saved", "skipped", "already_tracked"];

type Filter = "all" | "high" | "mid";
type SortKey = "score_desc" | "score_asc" | "company_asc" | "date_desc";

const FILTER_LABELS: Record<Filter, string> = {
    all: "All",
    high: "85%+ match",
    mid: "65–84%",
};

const SORT_LABELS: Record<SortKey, string> = {
    score_desc: "Score: High → Low",
    score_asc: "Score: Low → High",
    company_asc: "Company A–Z",
    date_desc: "Newest first",
};

function getJobLink(job: Job): string {
    const applyUrl = job.apply_url?.trim();
    if (applyUrl && applyUrl !== "#") return applyUrl;

    const sourceUrl = job.source_url?.trim();
    if (sourceUrl && sourceUrl !== "#") return sourceUrl;

    return "";
}

export default function JobsPage() {
    const { user } = useAuth();
    const { toasts, toast } = useToast();
    const router = useRouter();

    const handleLogout = useCallback(async () => {
        try { await apiLogout(); } finally { router.push("/login"); }
    }, [router]);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<"auth" | "other" | null>(null);
    const [filter, setFilter] = useState<Filter>("all");
    const [sort, setSort] = useState<SortKey>("score_desc");
    const [search, setSearch] = useState("");
    const [submittingId, setSubmittingId] = useState<string | null>(null);

    const fetchJobs = useCallback(async () => {
        if (!user) return;
        try {
            const response = await getJobs();
            setJobs(response.jobs || []);
            setError(null);
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "other");
            toast(is401 ? "Session expired — please log in again" : "Could not load jobs", "error");
        } finally {
            setLoading(false);
        }
    }, [user, toast]);

    useEffect(() => {
        if (!user) return;
        const timeoutId = window.setTimeout(() => {
            void fetchJobs();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [fetchJobs, user]);

    const handleRetry = useCallback(() => {
        setLoading(true);
        setError(null);
        void fetchJobs();
    }, [fetchJobs]);

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        let list = jobs.filter((j) =>
            filter === "high"
                ? j.score >= SCORE_THRESHOLDS.HIGH
                : filter === "mid"
                    ? j.score >= SCORE_THRESHOLDS.MID && j.score < SCORE_THRESHOLDS.HIGH
                    : true
        );
        if (q) {
            list = list.filter(
                (j) =>
                    j.title?.toLowerCase().includes(q) ||
                    j.company?.toLowerCase().includes(q) ||
                    j.location?.toLowerCase().includes(q)
            );
        }
        list = [...list].sort((a, b) => {
            if (sort === "score_asc") return a.score - b.score;
            if (sort === "company_asc") return (a.company ?? "").localeCompare(b.company ?? "");
            if (sort === "date_desc") {
                const ad = a.posted_at ?? "";
                const bd = b.posted_at ?? "";
                return bd.localeCompare(ad);
            }
            return b.score - a.score;
        });
        return list;
    }, [jobs, filter, sort, search]);

    const handleAction = async (jobId: string, action: string) => {
        if (!user || submittingId) return;
        const job = jobs.find((j) => j.job_id === jobId);
        if (!job) return;
        setSubmittingId(jobId);
        const jobLink = getJobLink(job);

        const payload = {
            job: {
                link: jobLink,
                title: job.title,
                company: job.company,
                location: job.location,
                score: job.score,
            },
        };

        try {
            if (action === "apply") {
                // Create application record with status "opened" (mapped from opened_external)
                await createApplication({
                    job_id: job.job_id,
                    title: job.title,
                    company: job.company,
                    location: job.location,
                    url: jobLink,
                    status: "opened",
                    source: "manual",
                });

                // Open external URL
                if (jobLink) {
                    window.open(jobLink, "_blank");
                    toast("Application opened. Click 'Mark as applied' after submitting.", "success");
                } else {
                    toast("Lead saved. Verify the posting before applying.", "success");
                }
                return;
            }

            if (action === "mark_applied") {
                // Update application status to "applied"
                try {
                    await updateApplication(jobId, { status: "applied" });
                    toast("Application marked as applied", "success");
                    setJobs((prev) => prev.filter((item) => item.job_id !== jobId));
                } catch (err) {
                    if (err instanceof ApiError && err.statusCode === 404) {
                        toast("Application no longer tracked", "error");
                        setJobs((prev) => prev.filter((item) => item.job_id !== jobId));
                    } else {
                        toast("Failed to mark as applied", "error");
                    }
                }
                return;
            }

            if (action === "save") {
                const result = await saveJob(jobId, payload);
                if (!TRACKED_STATUSES.includes(String(result.status ?? "").toLowerCase())) {
                    throw new Error(result.message || "Could not save this job.");
                }
                toast(
                    result.status === "already_tracked" ? "Job was already tracked" : "Job saved",
                    "success"
                );
                return;
            }

            if (action === "ignore") {
                const result = await skipJob(jobId, payload);
                if (!TRACKED_STATUSES.includes(String(result.status ?? "").toLowerCase())) {
                    throw new Error(result.message || "Could not ignore this job.");
                }
                toast(
                    result.status === "already_tracked" ? "Job was already tracked" : "Job ignored",
                    "success"
                );
                setJobs((prev) => prev.filter((item) => item.job_id !== jobId));
                return;
            }

            throw new Error(`Unsupported job action: ${action}`);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Action failed. Please try again.";
            toast(errorMessage, "error");
        } finally {
            setSubmittingId(null);
        }
    };

    const filterBar = (
        <div className="flex flex-wrap items-center gap-2">
            <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search title, company…"
                className="h-8 rounded-lg border border-border-soft bg-surface-elevated/60 px-3 text-xs text-text-primary placeholder:text-text-tertiary focus:border-gold/40 focus:outline-none focus:ring-1 focus:ring-gold/20 transition-all w-44"
                aria-label="Search jobs"
            />
            <nav className="flex gap-1.5" aria-label="Job filters">
                {(Object.keys(FILTER_LABELS) as Filter[]).map((f) => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={cn(
                            "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                            filter === f
                                ? "bg-gold/10 text-gold border border-gold/30"
                                : "text-rico-text-dim hover:text-rico-text hover:bg-white/[0.04]"
                        )}
                    >
                        {FILTER_LABELS[f]}
                    </button>
                ))}
            </nav>
            <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="h-8 rounded-lg border border-border-soft bg-surface-elevated/60 px-2 text-xs text-text-secondary focus:border-gold/40 focus:outline-none focus:ring-1 focus:ring-gold/20 transition-all cursor-pointer"
                aria-label="Sort jobs"
            >
                {(Object.keys(SORT_LABELS) as SortKey[]).map((s) => (
                    <option key={s} value={s}>{SORT_LABELS[s]}</option>
                ))}
            </select>
        </div>
    );

    return (
        <AppShell
            title="Job Matches"
            subtitle={loading ? "Loading…" : filtered.length !== jobs.length ? `${filtered.length} of ${jobs.length} roles` : `${jobs.length} roles matched your profile`}
            sidebarProps={{
                user: user ? { name: user.name, email: user.email } : undefined,
                onLogout: handleLogout,
            }}
            topbarProps={{ actions: filterBar }}
        >
            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <SkeletonCard key={i} />
                    ))}
                </div>
            ) : error ? (
                <ErrorState
                    variant={error === "auth" ? "auth" : "network"}
                    onRetry={handleRetry}
                />
            ) : filtered.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filtered.map((job) => (
                        <JobCard key={job.job_id} job={job} onAction={handleAction} isSubmitting={submittingId === job.job_id} />
                    ))}
                </div>
            ) : (
                <EmptyState
                    title="No matches in this range"
                    description="Try the 'All' filter, or Rico will surface more matches in the next scan."
                    actionLabel={filter !== "all" ? "Show all jobs" : undefined}
                    onAction={filter !== "all" ? () => setFilter("all") : undefined}
                />
            )}
            <ToastContainer toasts={toasts} />
        </AppShell>
    );
}
