"use client";

import { AppShell } from "@/components/layout/AppShell";
import { JobCard } from "@/components/jobs/JobCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { SkeletonCard } from "@/components/shared/LoadingState";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import { useToast } from "@/hooks/useToast";
import { ApiError, createApplication, getJobs, logout as apiLogout, saveJob, skipJob, updateApplication } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import type { Job } from "@/types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const SCORE_THRESHOLDS = { HIGH: 85, MID: 65 };
const SUCCESS_STATUSES = ["applied", "success", "submitted", "saved"];
const TRACKED_STATUSES = ["saved", "skipped", "already_tracked"];

type Filter = "all" | "high" | "mid";
type SortKey = "score_desc" | "score_asc" | "company_asc" | "date_desc";

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
    const { language } = useLanguage();
    const t = useTranslation(language);

    const handleLogout = useCallback(async () => {
        try { await apiLogout(); } finally { router.push("/login"); }
    }, [router]);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [error, setError] = useState<"auth" | "other" | null>(null);
    const [filter, setFilter] = useState<Filter>("all");
    const [sort, setSort] = useState<SortKey>("score_desc");
    const [search, setSearch] = useState("");
    const [submittingId, setSubmittingId] = useState<string | null>(null);
    // Ref-based lock prevents the double-click race where two rapid clicks both
    // pass the submittingId state check before setSubmittingId completes.
    const _submittingRef = useRef(false);

    const PAGE_SIZE = 20;

    const fetchJobs = useCallback(async (pageNum = 1, append = false) => {
        if (!user) return;
        try {
            const response = await getJobs(pageNum, PAGE_SIZE);
            const incoming = response.jobs || [];
            setJobs((prev) => append ? [...prev, ...incoming] : incoming);
            setTotalPages(response.pages ?? 1);
            setPage(pageNum);
            setError(null);
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "other");
            toast(is401 ? "Session expired — please log in again" : "Could not load jobs", "error");
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, [user, toast]);

    useEffect(() => {
        if (!user) return;
        const timeoutId = window.setTimeout(() => {
            void fetchJobs(1, false);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [fetchJobs, user]);

    const handleLoadMore = useCallback(() => {
        if (loadingMore || page >= totalPages) return;
        setLoadingMore(true);
        void fetchJobs(page + 1, true);
    }, [fetchJobs, loadingMore, page, totalPages]);

    const handleRetry = useCallback(() => {
        setLoading(true);
        setError(null);
        void fetchJobs(1, false);
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
        if (!user || submittingId || _submittingRef.current) return;
        const job = jobs.find((j) => j.job_id === jobId);
        if (!job) return;
        _submittingRef.current = true;
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
                await createApplication({
                    job_id: job.job_id,
                    title: job.title,
                    company: job.company,
                    location: job.location,
                    url: jobLink,
                    status: "opened",
                    source: "manual",
                });

                if (jobLink) {
                    window.open(jobLink, "_blank");
                    toast("Application opened. Click 'Mark as applied' after submitting.", "success");
                } else {
                    toast("Lead saved. Verify the posting before applying.", "success");
                }
                return;
            }

            if (action === "mark_applied") {
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
            _submittingRef.current = false;
            setSubmittingId(null);
        }
    };

    const filterLabels: Record<Filter, string> = {
        all: t("jobsFilterAll"),
        high: t("jobsFilterHigh"),
        mid: t("jobsFilterMid"),
    };

    const sortLabels: Record<SortKey, string> = {
        score_desc: t("jobsSortScoreDesc"),
        score_asc: t("jobsSortScoreAsc"),
        company_asc: t("jobsSortCompanyAsc"),
        date_desc: t("jobsSortNewest"),
    };

    const filterBar = (
        <div className="flex flex-wrap items-center gap-2">
            <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("jobsSearchPlaceholder")}
                className="h-8 rounded-lg border border-border-soft bg-surface-elevated/60 px-3 text-xs text-text-primary placeholder:text-text-tertiary focus:border-gold/40 focus:outline-none focus:ring-1 focus:ring-gold/20 transition-all w-44"
                aria-label="Search jobs"
            />
            <nav className="flex gap-1.5" aria-label="Job filters">
                {(Object.keys(filterLabels) as Filter[]).map((f) => (
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
                        {filterLabels[f]}
                    </button>
                ))}
            </nav>
            <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="h-8 rounded-lg border border-border-soft bg-surface-elevated/60 px-2 text-xs text-text-secondary focus:border-gold/40 focus:outline-none focus:ring-1 focus:ring-gold/20 transition-all cursor-pointer"
                aria-label="Sort jobs"
            >
                {(Object.keys(sortLabels) as SortKey[]).map((s) => (
                    <option key={s} value={s}>{sortLabels[s]}</option>
                ))}
            </select>
        </div>
    );

    const hasMore = page < totalPages;
    const subtitle = loading
        ? t("jobsLoading")
        : filtered.length !== jobs.length
            ? `${filtered.length} ${t("jobsOf")} ${jobs.length} ${t("jobsRoles")}${hasMore ? "+" : ""}`
            : `${jobs.length}${hasMore ? "+" : ""} ${t("jobsRoles")}`;

    return (
        <AppShell
            title="Job Matches"
            subtitle={subtitle}
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
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {filtered.map((job) => (
                            <JobCard key={job.job_id} job={job} onAction={handleAction} isSubmitting={submittingId === job.job_id} />
                        ))}
                    </div>
                    {hasMore && (
                        <div className="mt-6 flex justify-center">
                            <button
                                onClick={handleLoadMore}
                                disabled={loadingMore}
                                className={cn(
                                    "px-6 py-2.5 rounded-xl text-sm font-semibold transition-all border",
                                    loadingMore
                                        ? "border-border-soft text-text-tertiary cursor-not-allowed"
                                        : "border-gold/30 text-gold bg-gold/5 hover:bg-gold/10"
                                )}
                            >
                                {loadingMore ? "Loading…" : `Load more (page ${page + 1} of ${totalPages})`}
                            </button>
                        </div>
                    )}
                </>
            ) : (
                <EmptyState
                    title={t("jobsEmptyTitle")}
                    description={t("jobsEmptyDesc")}
                    actionLabel={filter !== "all" ? t("jobsShowAll") : undefined}
                    onAction={filter !== "all" ? () => setFilter("all") : undefined}
                />
            )}
            <ToastContainer toasts={toasts} />
        </AppShell>
    );
}
