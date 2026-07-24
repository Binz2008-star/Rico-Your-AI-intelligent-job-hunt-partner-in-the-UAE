"use client";

import {
    fetchMe,
    fetchSubscribers,
    fetchSubscribersSummary,
    type AdminSubscriberRow,
    type AdminSubscribersList,
    type AdminSubscribersSummary,
    type AdminUsagePair,
} from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { planLabel, statusLabel, subscribersStrings, type SubStrings } from "./i18n";

const POLL_MS = 60_000;

const FILTERS: { key: string; labelKey: keyof SubStrings }[] = [
    { key: "all", labelKey: "filterAll" },
    { key: "free", labelKey: "planFree" },
    { key: "active", labelKey: "statusActive" },
    { key: "past_due", labelKey: "statusPastDue" },
    { key: "canceling", labelKey: "statusCanceling" },
    { key: "canceled", labelKey: "statusCanceled" },
    { key: "expired", labelKey: "statusExpired" },
    { key: "payment_failed", labelKey: "statusPaymentFailed" },
    { key: "needs_reconciliation", labelKey: "statusNeedsReconciliation" },
    { key: "inactive_7d", labelKey: "filterInactive7" },
    { key: "inactive_30d", labelKey: "filterInactive30" },
];

function fmt(iso: string | null | undefined, language: string, fallback: string): string {
    if (!iso) return fallback;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return fallback;
    return d.toLocaleString(language === "ar" ? "ar" : "en-AE", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function fmtTime(d: Date | null, language: string, fallback: string): string {
    if (!d) return fallback;
    return d.toLocaleTimeString(language === "ar" ? "ar" : "en-AE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function usageText(p: AdminUsagePair | undefined, s: SubStrings): string {
    if (!p || (p.used == null && p.allowance == null)) return s.notAvailable;
    const used = p.used == null ? s.notAvailable : String(p.used);
    const allowance = p.allowance == null ? "∞" : String(p.allowance);
    return `${used} / ${allowance}`;
}

function StatusPill({ status, s }: { status: string; s: SubStrings }) {
    // Textual label is authoritative (never color alone). A neutral dot adds a
    // secondary cue only.
    const emphatic = ["payment_failed", "needs_reconciliation", "past_due"].includes(status);
    return (
        <span className="inline-flex items-center gap-1.5">
            <span
                aria-hidden="true"
                className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    status === "active" || status === "trialing"
                        ? "bg-success"
                        : emphatic
                          ? "bg-gold"
                          : "bg-text-tertiary/60",
                )}
            />
            <span className="text-text-primary">{statusLabel(s, status)}</span>
        </span>
    );
}

export default function AdminSubscribersPage() {
    const router = useRouter();
    const { language } = useLanguage();
    const s = subscribersStrings(language);
    const isRtl = language === "ar";

    const [authorized, setAuthorized] = useState<boolean | null>(null);
    const [summary, setSummary] = useState<AdminSubscribersSummary | null>(null);
    const [list, setList] = useState<AdminSubscribersList | null>(null);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

    const [filter, setFilter] = useState("all");
    const [searchInput, setSearchInput] = useState("");
    const [search, setSearch] = useState("");

    // One in-flight controller at a time — aborting the previous request before
    // starting a new one prevents duplicate/overlapping calls (poll + filter).
    const inFlight = useRef<AbortController | null>(null);
    const pausedRef = useRef(false);

    // ── Owner gate: server decides via /me.is_owner; this only routes the UI. ──
    useEffect(() => {
        let alive = true;
        fetchMe()
            .then((me) => {
                if (!alive) return;
                if (!me.authenticated) {
                    router.replace("/login");
                    return;
                }
                if (!me.is_owner) {
                    router.replace("/dashboard");
                    return;
                }
                setAuthorized(true);
            })
            .catch(() => {
                if (alive) router.replace("/login");
            });
        return () => {
            alive = false;
        };
    }, [router]);

    const load = useCallback(
        async (opts: { filter: string; search: string }) => {
            // Supersede any in-flight request (no duplicates).
            if (inFlight.current) inFlight.current.abort();
            const controller = new AbortController();
            inFlight.current = controller;
            setRefreshing(true);
            try {
                const [summaryRes, listRes] = await Promise.all([
                    fetchSubscribersSummary(controller.signal),
                    fetchSubscribers(
                        { filter: opts.filter, search: opts.search, limit: 200, offset: 0 },
                        controller.signal,
                    ),
                ]);
                if (controller.signal.aborted) return;
                setSummary(summaryRes);
                setList(listRes);
                setError(false);
                setLastRefresh(new Date());
            } catch (e) {
                if (controller.signal.aborted) return;
                // Preserve previously loaded data; just flag the failure.
                setError(true);
            } finally {
                if (inFlight.current === controller) {
                    inFlight.current = null;
                    setRefreshing(false);
                }
            }
        },
        [],
    );

    // Debounce the search box into the applied `search`.
    useEffect(() => {
        const t = setTimeout(() => setSearch(searchInput.trim()), 400);
        return () => clearTimeout(t);
    }, [searchInput]);

    // Reload whenever authorized/filter/search changes. Deferred to a microtask
    // so the fetch (and its `refreshing` setState) does not run synchronously
    // inside the effect body (react-hooks/set-state-in-effect).
    useEffect(() => {
        if (!authorized) return;
        let cancelled = false;
        queueMicrotask(() => {
            if (!cancelled) void load({ filter, search });
        });
        return () => {
            cancelled = true;
        };
    }, [authorized, filter, search, load]);

    // 60s polling, paused while the tab is hidden.
    useEffect(() => {
        if (!authorized) return;
        const tick = () => {
            if (document.visibilityState === "hidden") return;
            void load({ filter, search });
        };
        const interval = window.setInterval(tick, POLL_MS);

        const onVisibility = () => {
            const hidden = document.visibilityState === "hidden";
            pausedRef.current = hidden;
            if (!hidden) {
                // Refresh immediately on return so the view isn't stale.
                void load({ filter, search });
            }
        };
        document.addEventListener("visibilitychange", onVisibility);
        return () => {
            window.clearInterval(interval);
            document.removeEventListener("visibilitychange", onVisibility);
        };
    }, [authorized, filter, search, load]);

    if (authorized === null) {
        return (
            <div className="flex min-h-[100dvh] items-center justify-center bg-background">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-gold border-t-transparent motion-reduce:animate-none" />
            </div>
        );
    }

    const rows = list?.subscribers ?? [];
    const firstLoading = !list && !error;
    const stale = error && list != null;
    const failed = error && list == null;
    const usagePartial = (summary && !summary.usage_available) || (list && !list.usage_available);
    const truncated = summary?.truncated || list?.truncated;

    return (
        <div dir={isRtl ? "rtl" : "ltr"} className="min-h-[100dvh] bg-background px-4 py-6 text-text-primary sm:px-6 lg:px-10">
            <div className="mx-auto w-full max-w-7xl">
                {/* Header */}
                <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-gold">
                            {s.ownerOnly}
                        </p>
                        <h1 className="mt-1 text-2xl font-bold text-text-primary">{s.title}</h1>
                        <p className="mt-1 max-w-xl text-sm text-text-secondary">{s.subtitle}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <button
                            type="button"
                            onClick={() => void load({ filter, search })}
                            disabled={refreshing}
                            className="inline-flex items-center gap-2 rounded-lg border border-border-soft bg-surface px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-subtle hover:text-text-primary disabled:opacity-60"
                        >
                            {refreshing ? s.refreshing : s.refresh}
                        </button>
                        <div className="text-end text-[11px] leading-relaxed text-text-tertiary">
                            <div aria-live="polite">
                                {s.lastRefresh}: {fmtTime(lastRefresh, language, s.notAvailable)}
                            </div>
                            <div>
                                {s.lastSynced}:{" "}
                                {fmt(summary?.last_billing_sync ?? list?.last_billing_sync, language, s.neverSynced)}
                            </div>
                            <div className="mt-0.5">
                                <span
                                    className={cn(
                                        "inline-flex items-center gap-1",
                                        refreshing ? "text-gold" : "text-text-tertiary",
                                    )}
                                >
                                    <span
                                        aria-hidden="true"
                                        className={cn(
                                            "h-1.5 w-1.5 rounded-full",
                                            refreshing ? "bg-gold" : "bg-success",
                                        )}
                                    />
                                    {s.autoRefreshLive}
                                </span>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Banners */}
                {stale && (
                    <div role="status" className="mb-4 rounded-lg border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-text-primary">
                        {s.stale}
                    </div>
                )}
                {usagePartial && !failed && (
                    <div role="status" className="mb-4 rounded-lg border border-border-soft bg-surface-subtle px-4 py-3 text-sm text-text-secondary">
                        {s.partialUsage}
                    </div>
                )}
                {truncated && (
                    <div className="mb-4 rounded-lg border border-border-soft bg-surface-subtle px-4 py-3 text-sm text-text-secondary">
                        {s.truncated}
                    </div>
                )}

                {/* Summary */}
                {summary && (
                    <section aria-label={s.title} className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                        <SummaryCard label={s.totalUsers} value={summary.summary.total_users} />
                        <SummaryCard label={s.freeUsers} value={summary.summary.free_users} />
                        <SummaryCard label={s.active} value={summary.summary.active_subscribers} accent />
                        <SummaryCard label={s.pastDue} value={summary.summary.past_due_subscribers} />
                        <SummaryCard label={s.canceling} value={summary.summary.canceling_subscribers} />
                        <SummaryCard label={s.canceled} value={summary.summary.canceled_subscribers} />
                        <SummaryCard label={s.expired} value={summary.summary.expired_subscribers} />
                        <SummaryCard label={s.paymentFailed} value={summary.summary.payment_failed_subscribers} />
                        <SummaryCard label={s.needsReconciliation} value={summary.summary.needs_reconciliation} />
                        <SummaryCard label={s.newThisMonth} value={summary.summary.new_subscriptions_this_month} />
                        <SummaryCard label={s.cancellationsThisMonth} value={summary.summary.cancellations_this_month} />
                        <SummaryCard
                            label={`${s.mrr} (${s.approx})`}
                            value={`$${summary.summary.approximate_mrr_usd.toLocaleString(language === "ar" ? "ar" : "en-AE")}`}
                            accent
                        />
                    </section>
                )}

                {/* Controls */}
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap gap-1.5">
                        {FILTERS.map((f) => (
                            <button
                                key={f.key}
                                type="button"
                                onClick={() => setFilter(f.key)}
                                aria-pressed={filter === f.key}
                                className={cn(
                                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                                    filter === f.key
                                        ? "border-gold/40 bg-gold/15 text-gold"
                                        : "border-border-soft bg-surface text-text-secondary hover:bg-surface-subtle hover:text-text-primary",
                                )}
                            >
                                {s[f.labelKey]}
                            </button>
                        ))}
                    </div>
                    <label className="relative block w-full sm:w-72">
                        <span className="sr-only">{s.search}</span>
                        <input
                            type="search"
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            placeholder={s.search}
                            className="w-full rounded-lg border border-border-soft bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-gold/50 focus:outline-none"
                        />
                    </label>
                </div>

                {/* Body */}
                {firstLoading ? (
                    <div className="flex items-center justify-center gap-3 rounded-xl border border-border-soft bg-surface py-16 text-sm text-text-secondary">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-gold border-t-transparent motion-reduce:animate-none" />
                        {s.loading}
                    </div>
                ) : failed ? (
                    <div className="rounded-xl border border-gold/30 bg-gold/10 px-5 py-10 text-center">
                        <p className="text-sm text-text-primary">{s.failed}</p>
                        <button
                            type="button"
                            onClick={() => void load({ filter, search })}
                            className="mt-4 rounded-lg border border-border-soft bg-surface px-4 py-2 text-sm text-text-secondary hover:bg-surface-subtle hover:text-text-primary"
                        >
                            {s.retry}
                        </button>
                    </div>
                ) : rows.length === 0 ? (
                    <div className="rounded-xl border border-border-soft bg-surface px-5 py-16 text-center text-sm text-text-tertiary">
                        {s.empty}
                    </div>
                ) : (
                    <>
                        {/* Desktop table */}
                        <div className="hidden overflow-x-auto rounded-xl border border-border-soft md:block">
                            <table className="w-full text-sm">
                                <caption className="sr-only">{s.title}</caption>
                                <thead>
                                    <tr className="border-b border-border-soft bg-surface-subtle text-start">
                                        {[
                                            s.colName,
                                            s.colEmail,
                                            s.colUserId,
                                            s.colPlan,
                                            s.colStatus,
                                            s.colPaddle,
                                            s.colRenewal,
                                            s.colCancelEffective,
                                            s.colAiUsage,
                                            s.colSavedUsage,
                                            s.colDocUsage,
                                            s.colLastActivity,
                                            s.colLastSync,
                                            s.colReconciliation,
                                        ].map((h) => (
                                            <th
                                                key={h}
                                                scope="col"
                                                className="whitespace-nowrap px-3 py-3 text-start font-mono text-[10px] uppercase tracking-widest text-text-tertiary"
                                            >
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((r) => (
                                        <tr key={r.email ?? r.user_id_masked} className="border-b border-border-subtle hover:bg-surface-subtle">
                                            <td className="px-3 py-3 text-text-primary">{r.name ?? s.notAvailable}</td>
                                            <td className="px-3 py-3 text-text-secondary">{r.email ?? s.notAvailable}</td>
                                            <td className="px-3 py-3 font-mono text-xs text-text-tertiary">{r.user_id_masked ?? s.notAvailable}</td>
                                            <td className="px-3 py-3 text-text-secondary">{planLabel(s, r.plan)}</td>
                                            <td className="px-3 py-3"><StatusPill status={r.status} s={s} /></td>
                                            <td className="px-3 py-3 font-mono text-xs text-text-tertiary">{r.paddle_subscription_ref ?? s.notAvailable}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{fmt(r.next_renewal, language, s.notAvailable)}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{fmt(r.cancellation_effective, language, s.notAvailable)}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{usageText(r.usage?.ai_messages, s)}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{usageText(r.usage?.saved_jobs, s)}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">
                                                {usageText(r.usage?.cv_documents, s)}
                                                <span className="mx-1 text-text-tertiary">·</span>
                                                {usageText(r.usage?.other_documents, s)}
                                            </td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{fmt(r.last_activity, language, s.notAvailable)}</td>
                                            <td className="px-3 py-3 text-xs text-text-secondary">{fmt(r.last_billing_sync, language, s.notAvailable)}</td>
                                            <td className="px-3 py-3 text-xs">
                                                <span className={r.reconciliation === "needs_review" ? "text-gold" : "text-text-tertiary"}>
                                                    {r.reconciliation === "needs_review" ? s.reconNeedsReview : s.reconOk}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Mobile cards */}
                        <ul className="space-y-3 md:hidden">
                            {rows.map((r) => (
                                <li key={r.email ?? r.user_id_masked} className="rounded-xl border border-border-soft bg-surface p-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <p className="truncate font-medium text-text-primary">{r.name ?? r.email ?? s.notAvailable}</p>
                                            <p className="truncate text-xs text-text-secondary">{r.email ?? s.notAvailable}</p>
                                        </div>
                                        <StatusPill status={r.status} s={s} />
                                    </div>
                                    <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                                        <MobileField label={s.colPlan} value={planLabel(s, r.plan)} />
                                        <MobileField label={s.colUserId} value={r.user_id_masked ?? s.notAvailable} mono />
                                        <MobileField label={s.colRenewal} value={fmt(r.next_renewal, language, s.notAvailable)} />
                                        <MobileField label={s.colCancelEffective} value={fmt(r.cancellation_effective, language, s.notAvailable)} />
                                        <MobileField label={s.colPaddle} value={r.paddle_subscription_ref ?? s.notAvailable} mono />
                                        <MobileField label={s.colAiUsage} value={usageText(r.usage?.ai_messages, s)} />
                                        <MobileField label={s.colSavedUsage} value={usageText(r.usage?.saved_jobs, s)} />
                                        <MobileField label={s.colDocUsage} value={`${usageText(r.usage?.cv_documents, s)} · ${usageText(r.usage?.other_documents, s)}`} />
                                        <MobileField label={s.colLastActivity} value={fmt(r.last_activity, language, s.notAvailable)} />
                                        <MobileField label={s.colLastSync} value={fmt(r.last_billing_sync, language, s.notAvailable)} />
                                        <MobileField
                                            label={s.colReconciliation}
                                            value={r.reconciliation === "needs_review" ? s.reconNeedsReview : s.reconOk}
                                        />
                                    </dl>
                                </li>
                            ))}
                        </ul>

                        {list && (
                            <p className="mt-4 text-center text-xs text-text-tertiary">
                                {rows.length} / {list.filtered_total}
                            </p>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

function SummaryCard({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
    return (
        <div className="rounded-xl border border-border-soft bg-surface px-4 py-3">
            <p className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">{label}</p>
            <p className={cn("mt-2 text-2xl font-bold", accent ? "text-gold" : "text-text-primary")}>{value}</p>
        </div>
    );
}

function MobileField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
    return (
        <div className="min-w-0">
            <dt className="text-[10px] uppercase tracking-wide text-text-tertiary">{label}</dt>
            <dd className={cn("truncate text-text-secondary", mono && "font-mono text-[11px]")}>{value}</dd>
        </div>
    );
}
