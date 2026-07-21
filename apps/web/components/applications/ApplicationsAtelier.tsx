"use client";

/**
 * ApplicationsAtelier — the /applications content rebuilt to the approved
 * /design-preview workspace reference (en-applications-desktop.png), Atelier
 * migration M1 (TASK-20260713-002).
 *
 * Behavior is a 1:1 port of the legacy /flow page: same API calls
 * (getApplications / getApplicationStats / updateApplicationStatus /
 * createManualApplication), same canonical status taxonomy and board columns
 * (lib/applicationStatus.ts, BUG-6), and the same flow* translation keys —
 * only the presentation moves to the Atelier system. The reference's SAMPLE
 * toggle and five sample columns are prototype artifacts and are not shipped;
 * columns come from STAGE_DEFS so list and board can never disagree.
 *
 * Visual system: shared atelier-kit tokens + Mono primitive; theme colors come
 * from WorkspaceShell via useWorkspaceTheme so the light/dark island stays
 * consistent with the shell chrome. Command v5 PR 3 applies the v5
 * Applications mode treatment (coral/amber accents, card surfaces, skeleton
 * loading, presence-aware empty state) to the LIGHT island only — the dark
 * island keeps its existing language; every API call, status taxonomy,
 * translation key, testid and aria contract is unchanged.
 */

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { V5, V5_GRADIENT, V5_MODE_ACCENTS } from "@/components/workspace/v5/tokens";
import { RicoPresence } from "@/components/workspace/v5/RicoPresence";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    ApiError,
    createManualApplication,
    getApplications,
    getApplicationStats,
    updateApplicationStatus,
} from "@/lib/api";
import { APPLICATION_STATUSES, STAGE_DEFS, type StageKey } from "@/lib/applicationStatus";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import type { Application, ApplicationStatus } from "@/types";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type ViewMode = "list" | "board";

const SERIF = ATELIER_FONT.serif;

// Reference-specific editorial strings (eyebrow / headline / intro) follow the
// DashboardAtelier inline-T precedent; every functional string reuses the
// existing flow* keys so wording stays identical to the legacy page.
/* Artifact applications hero (MODE_THEME.applications) */
const T: Record<"en" | "ar", { eyebrow: string; lead: string; word: string; sub: string }> = {
    en: {
        eyebrow: "Live pipeline",
        lead: "Your career pipeline",
        word: "is moving",
        sub: "Every stage, every signal — Rico pushes applications forward and flags whatever has gone quiet.",
    },
    ar: {
        eyebrow: "مسار حي",
        lead: "مسار مسيرتك",
        word: "يتحرّك",
        sub: "كل مرحلة وكل إشارة — يدفع ريكو الطلبات ويشير إلى ما توقّف.",
    },
};

// Board column labels, keyed by the canonical stage (lib/applicationStatus.ts).
const STAGE_LABEL_KEYS: Record<StageKey, TranslationKey> = {
    lead: "flowColLeads",
    applied: "flowColApplied",
    interview: "flowColInterview",
    outcome: "flowColOutcome",
};

const KANBAN_COLS: Array<{ key: StageKey; labelKey: TranslationKey; statuses: ApplicationStatus[] }> =
    STAGE_DEFS.map((stage) => ({
        key: stage.key,
        labelKey: STAGE_LABEL_KEYS[stage.key],
        statuses: stage.statuses,
    }));

// Maps each canonical backend status to its display-label translation key.
const STATUS_LABEL_KEYS: Record<ApplicationStatus, TranslationKey> = {
    applied: "flowStatusApplied",
    interview: "flowStatusInterview",
    offer: "flowStatusOffer",
    rejected: "flowStatusRejected",
    saved: "flowStatusSaved",
    opened: "flowStatusOpened",
    opened_external: "flowStatusOpenedExternal",
    prepared: "flowStatusPrepared",
    follow_up_due: "flowStatusFollowUpDue",
    decision_made: "flowStatusDecision",
};

const STATUS_OPTIONS: ApplicationStatus[] = APPLICATION_STATUSES;

const NEXT_ACTION_KEYS: Record<ApplicationStatus, TranslationKey> = {
    saved: "flowNextSaved",
    opened: "flowNextOpened",
    opened_external: "flowNextOpenedExternal",
    prepared: "flowNextPrepared",
    applied: "flowNextApplied",
    follow_up_due: "flowNextFollowUpDue",
    interview: "flowNextInterview",
    offer: "flowNextOffer",
    rejected: "flowNextRejected",
    decision_made: "flowNextDecision",
};

// 'opened' and 'opened_external' are excluded from the stat grid — they
// auto-populate on any link click and create noise. They remain tracked in the
// board's "Leads" column but are not featured as top-line stats.
const STATUS_COUNT_ORDER: ApplicationStatus[] = [
    "applied", "follow_up_due", "interview", "offer",
    "saved", "prepared", "rejected", "decision_made",
];

type ManualApplicationForm = {
    title: string;
    company: string;
    location: string;
    url: string;
    status: ApplicationStatus;
};

function createEmptyFormData(): ManualApplicationForm {
    return { title: "", company: "", location: "", url: "", status: "applied" };
}

function isLeadWithNoUrl(app: Application): boolean {
    return app.status === "saved" && (!app.apply_url || app.apply_url === "#");
}

function fmtDate(iso: string | undefined, language: "en" | "ar") {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    const locale = language === "ar" ? "ar" : "en-GB";
    return d.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

type Palette = ReturnType<typeof useWorkspaceTheme>;

function DateProvenance({
    app,
    language,
    t,
    c,
}: {
    app: Application;
    language: "en" | "ar";
    t: (key: TranslationKey) => string;
    c: Palette;
}) {
    if (app.applied_at) {
        return <Mono style={{ color: c.ink40 }}>{t("flowProvApplied")} · {fmtDate(app.applied_at, language)}</Mono>;
    }
    if (app.updated_at) {
        return <Mono style={{ color: c.ink40 }}>{t("flowProvUpdated")} · {fmtDate(app.updated_at, language)}</Mono>;
    }
    return <Mono style={{ color: c.ink40 }}>{t("flowProvNoDate")}</Mono>;
}

function StatusSelect({
    id,
    app,
    disabled,
    onChange,
    t,
    c,
}: {
    id: string;
    app: Application;
    disabled: boolean;
    onChange: (status: ApplicationStatus) => void;
    t: (key: TranslationKey) => string;
    c: Palette;
}) {
    return (
        <>
            <label className="sr-only" htmlFor={id}>{`Change status for ${app.title}`}</label>
            <select
                id={id}
                value={app.status}
                onChange={(e) => onChange(e.target.value as ApplicationStatus)}
                disabled={disabled}
                className="rounded-[4px] px-2 py-1.5 text-[12px] outline-none disabled:opacity-40"
                style={{ background: c.panel, border: `1px solid ${c.hair}`, color: c.ink, fontFamily: ATELIER_FONT.body }}
            >
                {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>
                ))}
            </select>
        </>
    );
}

export function ApplicationsAtelier() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const tt = T[language];
    const [applications, setApplications] = useState<Application[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<"auth" | "network" | false>(false);
    const [viewMode, setViewMode] = useState<ViewMode>("list");
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [updating, setUpdating] = useState<string | null>(null);
    const [formData, setFormData] = useState<ManualApplicationForm>(() => createEmptyFormData());

    const closeTrackModal = useCallback(() => {
        setShowModal(false);
        setFormError(null);
        setFormData(createEmptyFormData());
    }, []);

    // Escape closes the Track Application modal, matching standard dialog behavior.
    useEffect(() => {
        if (!showModal) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") closeTrackModal();
        };
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [showModal, closeTrackModal]);

    const loadApplications = useCallback(async () => {
        try {
            const [response, stats] = await Promise.all([
                getApplications(undefined, 1, 50),
                getApplicationStats().catch(() => null),
            ]);
            setApplications(response.applications);
            // Header total must match the canonical, deduped count from the
            // backend — the same source the chat summary reads.
            const canonicalTotal = typeof stats?.total === "number" ? stats.total : response.total;
            setTotal(canonicalTotal);
            setError(false);
        } catch (err: unknown) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "network");
        } finally {
            setLoading(false);
        }
    }, []);

    const changeStatus = useCallback(async (app: Application, status: ApplicationStatus) => {
        if (updating) return;
        setUpdating(app.application_id);
        try {
            await updateApplicationStatus(app.job_id, { status });
            setApplications((prev) =>
                prev.map((a) => (a.application_id === app.application_id ? { ...a, status } : a))
            );
        } catch {
            // status reverts automatically since we use optimistic local state
        } finally {
            setUpdating(null);
        }
    }, [updating]);

    const handleTrackApplication = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.title.trim() || !formData.company.trim()) {
            setFormError(t("flowModalTitleRequired"));
            return;
        }
        setSaving(true);
        setFormError(null);
        try {
            await createManualApplication({
                title: formData.title.trim(),
                company: formData.company.trim(),
                location: formData.location.trim(),
                url: formData.url.trim(),
                status: formData.status,
            });
            setShowModal(false);
            setFormData(createEmptyFormData());
            setLoading(true);
            await loadApplications();
        } catch (err: unknown) {
            setFormError(err instanceof Error ? err.message : t("flowModalFailedTrack"));
        } finally {
            setSaving(false);
        }
    }, [formData, loadApplications, t]);

    useEffect(() => {
        const id = window.setTimeout(() => { void loadApplications(); }, 0);
        return () => window.clearTimeout(id);
    }, [loadApplications]);

    const grouped = useMemo(() => {
        const counts = STATUS_COUNT_ORDER.reduce<Record<ApplicationStatus, number>>(
            (acc, s) => ({ ...acc, [s]: 0 }),
            {} as Record<ApplicationStatus, number>
        );
        for (const application of applications) {
            counts[application.status] = (counts[application.status] ?? 0) + 1;
        }
        return counts;
    }, [applications]);

    const fieldStyle: React.CSSProperties = {
        background: c.bg,
        border: `1px solid ${c.hair}`,
        color: c.ink,
        fontFamily: ATELIER_FONT.body,
    };

    // v5 Applications mode (light island only) — coral/amber accent triple.
    const v5 = !c.dark;
    const acc = V5_MODE_ACCENTS.applications;

    return (
        <div>
            {/* Header */}
            <div>
                <span className="flex items-center gap-2.5">
                    <span className="wsx5-breathe-dot" style={{ background: v5 ? acc.modeA : c.red }} aria-hidden="true" />
                    <Mono style={{ color: v5 ? acc.modeAText : c.red }}>{tt.eyebrow}</Mono>
                </span>
                <h1 className="wsx5-display mt-3 text-[2.2rem] sm:text-[2.9rem]" style={{ fontFamily: SERIF, color: c.ink }}>
                    {tt.lead} <em style={v5 ? undefined : { background: "none", color: c.red }}>{tt.word}</em>
                </h1>
            </div>
            <p className="mt-4 max-w-2xl text-[1.02rem] leading-[1.62]" style={{ color: c.ink70 }}>{tt.sub}</p>

            {loading && (
                <div className="mt-10" aria-busy="true">
                    <p style={{ color: c.ink40 }}>{t("flowLoadingState")}</p>
                    {v5 && (
                        <div className="mt-6 flex flex-col gap-3" aria-hidden="true">
                            <div className="wsx5-skel" style={{ height: 120 }} />
                            <div className="wsx5-skel" style={{ height: 120 }} />
                            <div className="wsx5-skel" style={{ height: 120 }} />
                        </div>
                    )}
                </div>
            )}

            {!loading && error && (
                <div className={`mt-10 p-6 ${v5 ? "wsx5-card" : "rounded-[4px]"}`} style={{ background: c.panel, border: `1px solid ${c.hair}` }} role="alert">
                    {v5 && <RicoPresence state="warning" size="sm" decorative className="mb-3" />}
                    <p style={{ color: c.ink }}>{error === "auth" ? t("flowErrAuth") : t("flowErrNetwork")}</p>
                    {error === "auth" ? (
                        <Link href="/login?next=%2Fapplications" className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: c.ink, borderBottom: `1px solid ${c.ink}`, textDecoration: "none", paddingBottom: 1 }}>
                            {t("login")} <span aria-hidden="true">{language === "ar" ? "←" : "→"}</span>
                        </Link>
                    ) : (
                        <button
                            type="button"
                            onClick={() => { setLoading(true); void loadApplications(); }}
                            className="wsx-action mt-4 rounded-[6px] px-4 py-2 text-[13px] font-semibold"
                            style={{ border: `1px solid ${c.hair}`, color: c.ink, background: "transparent", cursor: "pointer" }}
                        >
                            {t("retry")}
                        </button>
                    )}
                </div>
            )}

            {!loading && !error && (
                <>
                    {/* Controls row: tracked count · view toggle · track action */}
                    <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" data-wsx5-anim="rise" style={{ "--i": 1 } as React.CSSProperties}>
                        <div className="flex min-w-0 flex-wrap items-center gap-3">
                            <Mono style={{ color: c.ink55 }}>{total} {t("flowTrackedAcrossStages")}</Mono>
                            {total > applications.length && (
                                <Mono style={{ color: c.ink40 }}>{t("flowShowingFirst")} {applications.length}</Mono>
                            )}
                        </div>
                        <div className="flex items-center gap-2.5">
                            {/* List / Board toggle — reference chip row */}
                            <span className="inline-flex items-center rounded-[3px] overflow-hidden" style={{ border: `1px solid ${c.hair}` }}>
                                <button
                                    type="button"
                                    onClick={() => setViewMode("list")}
                                    aria-pressed={viewMode === "list"}
                                    aria-label={t("flowViewList")}
                                    style={{ fontFamily: language === "ar" ? ATELIER_FONT.body : ATELIER_FONT.mono, fontSize: 10, letterSpacing: language === "ar" ? 0 : "0.14em", textTransform: "uppercase", padding: "5px 10px", background: viewMode === "list" ? c.ink : "transparent", color: viewMode === "list" ? c.bg : c.ink55, cursor: "pointer" }}
                                >
                                    {t("flowViewList")}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setViewMode("board")}
                                    aria-pressed={viewMode === "board"}
                                    aria-label={t("flowViewBoard")}
                                    style={{ fontFamily: language === "ar" ? ATELIER_FONT.body : ATELIER_FONT.mono, fontSize: 10, letterSpacing: language === "ar" ? 0 : "0.14em", textTransform: "uppercase", padding: "5px 10px", background: viewMode === "board" ? c.ink : "transparent", color: viewMode === "board" ? c.bg : c.ink55, cursor: "pointer" }}
                                >
                                    {t("flowViewBoard")}
                                </button>
                            </span>
                            <button
                                type="button"
                                onClick={() => setShowModal(true)}
                                className="rounded-[6px] px-4 py-2 text-[13px] font-semibold"
                                style={
                                    v5
                                        ? { background: V5_GRADIENT.emberButton, color: V5.onEmber, border: "none", borderRadius: 999, cursor: "pointer" }
                                        : { background: c.ink, color: c.bg, border: `1px solid ${c.ink}`, cursor: "pointer" }
                                }
                            >
                                {t("flowTrackApplication")}
                            </button>
                        </div>
                    </div>

                    {/* Status count plates */}
                    {applications.length > 0 && (
                        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8" data-wsx5-anim="rise" style={{ "--i": 2 } as React.CSSProperties}>
                            {STATUS_COUNT_ORDER.map((s) => (
                                <div key={s} className={`${v5 ? "wsx5-card" : "rounded-[4px]"} p-3 text-center`} style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                                    <p style={{ fontFamily: SERIF, fontSize: "1.5rem", lineHeight: 1.1, color: v5 && grouped[s] > 0 ? acc.modeAText : c.ink }}>{grouped[s]}</p>
                                    <Mono className="mt-1 block [overflow-wrap:anywhere]" style={{ color: c.ink55, fontSize: 9.5 }}>
                                        {t(STATUS_LABEL_KEYS[s])}
                                    </Mono>
                                </div>
                            ))}
                        </div>
                    )}

                    {applications.length === 0 ? (
                        <div className={`mt-6 p-8 text-center ${v5 ? "wsx5-card" : "rounded-[4px]"}`} style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
                            {v5 && (
                                <span className="mb-4 inline-flex">
                                    <RicoPresence state="ready" size="lg" decorative />
                                </span>
                            )}
                            <h2 className="text-[1.4rem] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>{t("flowEmptyTitle")}</h2>
                            <p className="mx-auto mt-2 max-w-md text-[0.95rem] leading-relaxed" style={{ color: c.ink55 }}>{t("flowEmptyDesc")}</p>
                        </div>
                    ) : viewMode === "board" ? (
                        /* ── Board ── */
                        <div className="mt-6 overflow-x-hidden" data-wsx5-anim="rise" style={{ "--i": 3 } as React.CSSProperties}>
                            <div className="-mx-1 flex gap-3 overflow-x-auto pb-4 sm:mx-0">
                                {KANBAN_COLS.map((col) => {
                                    const colApps = applications.filter((a) => col.statuses.includes(a.status));
                                    return (
                                        <div
                                            key={col.key}
                                            className="flex min-w-[220px] flex-1 flex-col p-3 sm:min-w-[200px]"
                                            style={{ background: c.inset, border: `1px solid ${c.hair}`, borderRadius: v5 ? 14 : 4 }}
                                        >
                                            <div className="mb-3 flex items-center justify-between">
                                                <h3 className="font-normal">
                                                    <Mono style={{ color: c.ink55 }}>{t(col.labelKey)}</Mono>
                                                </h3>
                                                <span style={{ fontFamily: ATELIER_FONT.mono, fontSize: 11, color: v5 && colApps.length > 0 ? acc.modeAText : c.ink40 }}>{colApps.length}</span>
                                            </div>
                                            <div className="flex flex-col gap-2">
                                                {colApps.length === 0 && (
                                                    <p className="py-4 text-center text-[11px]" style={{ color: c.ink40 }}>—</p>
                                                )}
                                                {colApps.map((item) => (
                                                    <div
                                                        key={item.application_id}
                                                        className={`wsx-action ${v5 ? "wsx5-card" : "rounded-[4px]"} p-3`}
                                                        style={{ background: c.panel, border: `1px solid ${c.hair}`, ...(v5 ? { borderRadius: 12 } : {}) }}
                                                    >
                                                        <p className="text-[0.95rem] leading-snug [overflow-wrap:anywhere]" style={{ fontFamily: SERIF, color: c.ink }}>
                                                            {item.title}
                                                        </p>
                                                        <p className="mt-0.5 text-[12px] [overflow-wrap:anywhere]" style={{ color: c.ink55 }}>
                                                            {item.company}
                                                        </p>
                                                        {item.apply_url && item.apply_url !== "#" && (
                                                            <a
                                                                href={item.apply_url}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-semibold"
                                                                style={{ color: v5 ? acc.modeAText : c.red, textDecoration: "none" }}
                                                            >
                                                                {t("flowViewListing")} ↗
                                                            </a>
                                                        )}
                                                        <div className="mt-2 flex items-center justify-between gap-2">
                                                            <DateProvenance app={item} language={language} t={t} c={c} />
                                                            <StatusSelect
                                                                id={`board-status-${item.application_id}`}
                                                                app={item}
                                                                disabled={!!updating}
                                                                onChange={(status) => changeStatus(item, status)}
                                                                t={t}
                                                                c={c}
                                                            />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ) : (
                        /* ── List ── */
                        <div className="mt-6 flex flex-col gap-3" data-wsx5-anim="rise" style={{ "--i": 3 } as React.CSSProperties}>
                            {applications.map((item) => (
                                <div
                                    key={item.application_id}
                                    className={`wsx-action ${v5 ? "wsx5-card" : "rounded-[4px]"} p-5 sm:p-6`}
                                    style={{ background: c.panel, border: `1px solid ${c.hair}` }}
                                >
                                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                        <div className="min-w-0">
                                            <h3 className="text-[1.25rem] font-normal leading-snug [overflow-wrap:anywhere]" style={{ fontFamily: SERIF, color: c.ink }}>
                                                {item.title}
                                            </h3>
                                            <p className="text-[0.95rem] [overflow-wrap:anywhere]" style={{ color: c.ink70 }}>{item.company}</p>
                                            {item.location && (
                                                <p className="mt-0.5 text-[12px] [overflow-wrap:anywhere]" style={{ color: c.ink40 }}>{item.location}</p>
                                            )}
                                        </div>
                                        <div className="shrink-0 self-start">
                                            <span
                                                className="inline-flex px-2 py-1"
                                                style={
                                                    v5
                                                        ? { border: `1px solid ${c.hair}`, background: `${acc.modeA}14`, borderRadius: 999 }
                                                        : { border: `1px solid ${c.hair}`, background: c.inset, borderRadius: 3 }
                                                }
                                            >
                                                <Mono style={{ color: c.ink70 }}>{t(STATUS_LABEL_KEYS[item.status])}</Mono>
                                            </span>
                                        </div>
                                    </div>

                                    {isLeadWithNoUrl(item) && (
                                        <p className="mt-3 text-[12.5px]" style={{ color: v5 ? acc.modeAText : c.red }}>
                                            {t("flowNoApplyLink")}
                                        </p>
                                    )}

                                    {item.apply_url && item.apply_url !== "#" && (
                                        <a
                                            href={item.apply_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="mt-3 inline-flex max-w-full items-center gap-1 text-[13px] font-semibold"
                                            style={{ color: v5 ? acc.modeAText : c.red, textDecoration: "none" }}
                                        >
                                            <span className="truncate">{t("flowViewListing")}</span>
                                            <span aria-hidden="true">↗</span>
                                        </a>
                                    )}

                                    <div className="mt-4 flex flex-col gap-3 pt-4 sm:flex-row sm:items-center" style={{ borderTop: `1px solid ${c.hair}` }}>
                                        <DateProvenance app={item} language={language} t={t} c={c} />
                                        <div className="hidden flex-1 sm:block" />
                                        <StatusSelect
                                            id={`status-${item.application_id}`}
                                            app={item}
                                            disabled={!!updating}
                                            onChange={(status) => changeStatus(item, status)}
                                            t={t}
                                            c={c}
                                        />
                                    </div>

                                    <p className="mt-3 text-[13px] leading-relaxed [overflow-wrap:anywhere]" style={{ color: c.ink55 }}>
                                        {t(NEXT_ACTION_KEYS[item.status])}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            {/* Manual tracking modal */}
            {showModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    role="dialog"
                    aria-modal="true"
                    aria-label={t("flowTrackApplicationModalTitle")}
                    style={{ background: "rgba(31,27,21,0.45)" }}
                    onClick={closeTrackModal}
                >
                    <div
                        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-md flex-col overflow-hidden"
                        style={{ background: c.panel, border: `1px solid ${c.hair}`, borderRadius: v5 ? 18 : 4 }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h2 className="shrink-0 px-5 pb-4 pt-5 text-[1.35rem] font-normal sm:px-6 sm:pt-6" style={{ fontFamily: SERIF, color: c.ink, borderBottom: `1px solid ${c.hair}` }}>
                            {t("flowTrackApplicationModalTitle")}
                        </h2>
                        <form onSubmit={handleTrackApplication} className="flex-1 space-y-4 overflow-y-auto px-5 pb-5 pt-4 sm:px-6 sm:pb-6" aria-label="Manual application form">
                            <div>
                                <label htmlFor="title" className="mb-1 block text-[13px]" style={{ color: c.ink70 }}>{t("flowModalJobTitle")}</label>
                                <input
                                    id="title"
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full rounded-[4px] px-3 py-2 text-sm outline-none"
                                    style={fieldStyle}
                                    placeholder={t("flowPhTitle")}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="company" className="mb-1 block text-[13px]" style={{ color: c.ink70 }}>{t("flowModalCompany")}</label>
                                <input
                                    id="company"
                                    type="text"
                                    value={formData.company}
                                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                                    className="w-full rounded-[4px] px-3 py-2 text-sm outline-none"
                                    style={fieldStyle}
                                    placeholder={t("flowPhCompany")}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="location" className="mb-1 block text-[13px]" style={{ color: c.ink70 }}>{t("flowModalLocation")}</label>
                                <input
                                    id="location"
                                    type="text"
                                    value={formData.location}
                                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                                    className="w-full rounded-[4px] px-3 py-2 text-sm outline-none"
                                    style={fieldStyle}
                                    placeholder={t("flowPhLocation")}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="url" className="mb-1 block text-[13px]" style={{ color: c.ink70 }}>{t("flowModalUrl")}</label>
                                <input
                                    id="url"
                                    type="url"
                                    value={formData.url}
                                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                                    className="w-full rounded-[4px] px-3 py-2 text-sm outline-none"
                                    style={fieldStyle}
                                    placeholder={t("flowPhUrl")}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="status" className="mb-1 block text-[13px]" style={{ color: c.ink70 }}>{t("flowModalStatus")}</label>
                                <select
                                    id="status"
                                    value={formData.status}
                                    onChange={(e) => setFormData({ ...formData, status: e.target.value as ApplicationStatus })}
                                    className="w-full rounded-[4px] px-3 py-2 text-sm outline-none"
                                    style={fieldStyle}
                                    disabled={saving}
                                >
                                    {STATUS_OPTIONS.map((s) => (
                                        <option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>
                                    ))}
                                </select>
                            </div>
                            {formError && <p className="text-[12.5px]" style={{ color: c.red }} role="alert">{formError}</p>}
                            <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:items-center">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-[6px] px-4 py-2 text-sm font-semibold disabled:opacity-60"
                                    style={
                                        v5
                                            ? { background: V5_GRADIENT.emberButton, color: V5.onEmber, border: "none", borderRadius: 999, cursor: "pointer" }
                                            : { background: c.ink, color: c.bg, border: `1px solid ${c.ink}`, cursor: "pointer" }
                                    }
                                >
                                    {saving ? t("saving") : t("flowModalSaveApplication")}
                                </button>
                                <button
                                    type="button"
                                    onClick={closeTrackModal}
                                    disabled={saving}
                                    className="wsx-action flex-1 rounded-[6px] px-4 py-2 text-sm font-semibold disabled:opacity-60"
                                    style={{ border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer" }}
                                >
                                    {t("cancel")}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
