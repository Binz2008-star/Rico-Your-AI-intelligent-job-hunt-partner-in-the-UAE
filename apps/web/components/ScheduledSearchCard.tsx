"use client";

/**
 * ScheduledSearchCard (#1249 step 3) — the Saved Search / Job Alert card.
 *
 * Shows each scheduled search's criteria (city, minimum AED salary, cadence),
 * enabled state, last run and next expected run, plus the latest in-app
 * results delivered by the sweep (real source links, match score and reason;
 * unknown salary is explicitly labeled, never invented). Pause/resume is a
 * single click; delete is destructive and requires an inline confirm step.
 *
 * Bilingual: copy follows the app-wide "rico-language" localStorage flag the
 * root layout uses to set lang/dir (RTL is inherited from <html dir="rtl">).
 */

import {
    deleteSavedSearch,
    setScheduledSearchEnabled,
    type ScheduledSearch,
} from "@/lib/api";
import { useCallback, useState, useSyncExternalStore } from "react";

const DAY_MS = 24 * 60 * 60 * 1000;

// Language flag: static per page load (the root layout applies lang/dir the
// same way), read via useSyncExternalStore so the server snapshot stays EN and
// the client snapshot comes from localStorage without an effect-driven rerender.
const noopSubscribe = () => () => {};
function readArabic(): boolean {
    try {
        return localStorage.getItem("rico-language") === "ar";
    } catch {
        return false;
    }
}

interface Copy {
    title: string;
    enabled: string;
    paused: string;
    daily: string;
    allUae: string;
    anySalary: string;
    minSalary: (n: number) => string;
    lastRun: string;
    neverRan: string;
    nextRun: string;
    whenEnabled: string;
    newLastRun: (n: number) => string;
    latestResults: string;
    noResultsYet: string;
    salaryNotStated: string;
    salaryAed: (n: number) => string;
    score: string;
    view: string;
    pause: string;
    resume: string;
    del: string;
    confirmDel: string;
    cancel: string;
    editHint: string;
}

const EN: Copy = {
    title: "Daily job search",
    enabled: "Active",
    paused: "Paused",
    daily: "Daily",
    allUae: "All UAE",
    anySalary: "Any salary",
    minSalary: (n) => `AED ${n.toLocaleString()}+`,
    lastRun: "Last run",
    neverRan: "Not run yet",
    nextRun: "Next run",
    whenEnabled: "when resumed",
    newLastRun: (n) => `${n} new`,
    latestResults: "Latest matches",
    noResultsYet: "No matches delivered yet — results will appear here after the next run.",
    salaryNotStated: "Salary not stated",
    salaryAed: (n) => `AED ${n.toLocaleString()}`,
    score: "match",
    view: "View job",
    pause: "Pause",
    resume: "Resume",
    del: "Delete",
    confirmDel: "Delete this scheduled search?",
    cancel: "Cancel",
    editHint: "To change city or salary, tell Rico in chat — e.g. “search daily for jobs in Abu Dhabi”.",
};

const AR: Copy = {
    title: "البحث اليومي عن الوظائف",
    enabled: "مفعّل",
    paused: "متوقف",
    daily: "يومي",
    allUae: "كل الإمارات",
    anySalary: "أي راتب",
    minSalary: (n) => `${n.toLocaleString("ar-AE")}+ درهم`,
    lastRun: "آخر تشغيل",
    neverRan: "لم يعمل بعد",
    nextRun: "التشغيل القادم",
    whenEnabled: "عند الاستئناف",
    newLastRun: (n) => `${n} جديدة`,
    latestResults: "أحدث الوظائف المطابقة",
    noResultsYet: "لا نتائج بعد — ستظهر هنا بعد التشغيل القادم.",
    salaryNotStated: "الراتب غير معلن",
    salaryAed: (n) => `${n.toLocaleString("ar-AE")} درهم`,
    score: "تطابق",
    view: "عرض الوظيفة",
    pause: "إيقاف مؤقت",
    resume: "استئناف",
    del: "حذف",
    confirmDel: "حذف هذا البحث المجدول؟",
    cancel: "إلغاء",
    editHint: "لتغيير المدينة أو الراتب، اطلب من ريكو في المحادثة — مثال: «ابحث يوميًا عن وظائف في أبوظبي».",
};

function formatWhen(iso: string | null | undefined, arabic: boolean): string | null {
    if (!iso) return null;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString(arabic ? "ar-AE" : "en-GB", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    });
}

export function ScheduledSearchCard({
    item,
    onChanged,
}: {
    item: ScheduledSearch;
    onChanged: () => void;
}) {
    const arabic = useSyncExternalStore(noopSubscribe, readArabic, () => false);
    const [busy, setBusy] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [failed, setFailed] = useState(false);

    const t = arabic ? AR : EN;
    const sched = item.schedule;
    const lastRun = formatWhen(sched.last_run_at, arabic);
    const nextRun = sched.enabled
        ? formatWhen(
            sched.last_run_at
                ? new Date(new Date(sched.last_run_at).getTime() + DAY_MS).toISOString()
                : null,
            arabic,
        )
        : null;

    const toggle = useCallback(async () => {
        if (!item.id || busy) return;
        setBusy(true);
        setFailed(false);
        try {
            await setScheduledSearchEnabled(item.id, !sched.enabled);
            onChanged();
        } catch {
            setFailed(true);
        } finally {
            setBusy(false);
        }
    }, [item.id, sched.enabled, busy, onChanged]);

    const doDelete = useCallback(async () => {
        if (!item.id || busy) return;
        setBusy(true);
        setFailed(false);
        try {
            await deleteSavedSearch(item.id);
            onChanged();
        } catch {
            setFailed(true);
        } finally {
            setBusy(false);
            setConfirming(false);
        }
    }, [item.id, busy, onChanged]);

    return (
        <div
            data-testid="scheduled-search-card"
            className="rounded-xl border border-white/10 bg-white/[0.03] p-4"
        >
            <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-rico-text">{t.title}</h3>
                <span
                    data-testid="scheduled-search-state"
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                        sched.enabled
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-amber-500/15 text-amber-300"
                    }`}
                >
                    {sched.enabled ? t.enabled : t.paused}
                </span>
            </div>

            <p data-testid="scheduled-search-criteria" className="mt-1 text-sm text-rico-text-dim">
                {t.daily} · {sched.city || t.allUae} ·{" "}
                {sched.min_salary_aed ? t.minSalary(sched.min_salary_aed) : t.anySalary}
            </p>

            <p className="mt-1 text-xs text-rico-text-dim">
                {t.lastRun}: {lastRun ?? t.neverRan}
                {lastRun ? ` — ${t.newLastRun(sched.last_run_new)}` : ""}
                {" · "}
                {t.nextRun}: {sched.enabled ? (nextRun ?? "~24h") : t.whenEnabled}
            </p>

            <div className="mt-3">
                <h4 className="text-xs font-medium uppercase tracking-wide text-rico-text-dim">
                    {t.latestResults}
                </h4>
                {sched.last_results.length === 0 ? (
                    <p data-testid="scheduled-search-empty" className="mt-1 text-sm text-rico-text-dim">
                        {t.noResultsYet}
                    </p>
                ) : (
                    <ul className="mt-1 flex flex-col gap-2">
                        {sched.last_results.map((r) => (
                            <li
                                key={`${r.title}|${r.company}`}
                                data-testid="scheduled-search-result"
                                className="rounded-lg bg-white/[0.03] px-3 py-2.5"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <span className="text-sm text-rico-text">
                                        {r.title} — {r.company}
                                    </span>
                                    <span className="shrink-0 text-xs text-rico-text-dim">
                                        {r.score}% {t.score}
                                    </span>
                                </div>
                                <div className="mt-0.5 text-xs text-rico-text-dim">
                                    {r.location ? `${r.location} · ` : ""}
                                    <span data-testid="scheduled-search-salary">
                                        {r.salary_known && r.salary_aed != null
                                            ? t.salaryAed(r.salary_aed)
                                            : t.salaryNotStated}
                                    </span>
                                </div>
                                {r.why ? (
                                    <p className="mt-0.5 text-xs text-rico-text-dim">{r.why}</p>
                                ) : null}
                                <a
                                    href={r.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="mt-1 inline-block text-xs text-rico-accent underline"
                                >
                                    {t.view}
                                </a>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="mt-3 flex items-center gap-2">
                <button
                    type="button"
                    data-testid="scheduled-search-toggle"
                    onClick={() => void toggle()}
                    disabled={busy || !item.id}
                    className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs text-rico-text hover:bg-white/[0.1] disabled:opacity-50"
                >
                    {sched.enabled ? t.pause : t.resume}
                </button>

                {confirming ? (
                    <span className="flex items-center gap-2" data-testid="scheduled-search-confirm">
                        <span className="text-xs text-rico-text-dim">{t.confirmDel}</span>
                        <button
                            type="button"
                            data-testid="scheduled-search-confirm-delete"
                            onClick={() => void doDelete()}
                            disabled={busy}
                            className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/30 disabled:opacity-50"
                        >
                            {t.del}
                        </button>
                        <button
                            type="button"
                            onClick={() => setConfirming(false)}
                            disabled={busy}
                            className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs text-rico-text disabled:opacity-50"
                        >
                            {t.cancel}
                        </button>
                    </span>
                ) : (
                    <button
                        type="button"
                        data-testid="scheduled-search-delete"
                        onClick={() => setConfirming(true)}
                        disabled={busy || !item.id}
                        className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs text-rico-text hover:bg-red-500/20 hover:text-red-300 disabled:opacity-50"
                    >
                        {t.del}
                    </button>
                )}
            </div>

            {failed ? (
                <p data-testid="scheduled-search-error" className="mt-2 text-xs text-red-300">
                    {arabic ? "تعذّر تنفيذ الإجراء — حاول مجددًا." : "That action failed — please try again."}
                </p>
            ) : null}

            <p className="mt-2 text-xs text-rico-text-dim/80">{t.editHint}</p>
        </div>
    );
}
