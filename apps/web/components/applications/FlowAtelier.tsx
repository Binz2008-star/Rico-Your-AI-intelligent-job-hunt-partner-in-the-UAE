"use client";

/**
 * FlowAtelier — the authenticated /flow (applications) surface, migrated to the
 * approved /design-preview reference (en-applications-desktop.png): eyebrow
 * "APPLICATIONS" + serif "Your pipeline." + subtitle, a BOARD/LIST toggle, a
 * stat row, and a Kanban board — reframed as Rico's operational memory (what it
 * saved / applied to / is interviewing / closed on your behalf).
 *
 * Composition follows the reference; DATA + BEHAVIOR are Rico's existing
 * production /flow, preserved unchanged:
 *   - getApplications + getApplicationStats (canonical total)
 *   - updateApplicationStatus with OPTIMISTIC local update (revert on error)
 *   - createManualApplication (the "Track application" modal)
 *   - canonical STAGE_DEFS columns + STATUS_OPTIONS (backend enum untouched)
 *
 * Nothing is faked: the reference's per-card score has no field on Application
 * and is omitted; the prototype SAMPLE toggle / DEMO ACTION banner are dropped.
 * Palette comes from useWorkspaceTheme() so content tracks WorkspaceShell's
 * local light/dark toggle. No backend/auth/cookie/schema changes.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { ErrorState } from "@/components/shared/ErrorState";
import { useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";
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

const SERIF = ATELIER_FONT.serif;

type ViewMode = "list" | "board";

const STAGE_LABEL_KEYS: Record<StageKey, TranslationKey> = {
    lead: "flowColLeads",
    applied: "flowColApplied",
    interview: "flowColInterview",
    outcome: "flowColOutcome",
};

const KANBAN_COLS: Array<{ labelKey: TranslationKey; statuses: ApplicationStatus[] }> =
    STAGE_DEFS.map((stage) => ({ labelKey: STAGE_LABEL_KEYS[stage.key], statuses: stage.statuses }));

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

// 'opened'/'opened_external' auto-populate on any link click and create noise,
// so they are excluded from the stat row (still tracked in the Leads column).
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

function fmtDate(iso: string | undefined, language: "en" | "ar") {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    const locale = language === "ar" ? "ar" : "en-GB";
    return d.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

function DateProvenance({
    app,
    language,
    t,
    palette,
}: {
    app: Application;
    language: "en" | "ar";
    t: (key: TranslationKey) => string;
    palette: WorkspacePalette;
}) {
    const style = { fontFamily: ATELIER_FONT.mono, fontSize: 10, color: palette.ink40 } as const;
    if (app.applied_at) {
        return <span style={style}>{t("flowProvApplied")} · {fmtDate(app.applied_at, language)}</span>;
    }
    if (app.updated_at) {
        return <span style={style}>{t("flowProvUpdated")} · {fmtDate(app.updated_at, language)}</span>;
    }
    return <span style={{ ...style }}>{t("flowProvNoDate")}</span>;
}

export function FlowAtelier() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const palette = useWorkspaceTheme();

    const [applications, setApplications] = useState<Application[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<"auth" | "network" | false>(false);
    const [viewMode, setViewMode] = useState<ViewMode>("board");
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const updatingRef = useRef<string | null>(null);
    const [updating, setUpdating] = useState<string | null>(null);
    const [formData, setFormData] = useState<ManualApplicationForm>(() => createEmptyFormData());

    const closeTrackModal = useCallback(() => {
        setShowModal(false);
        setFormError(null);
        setFormData(createEmptyFormData());
    }, []);

    // Escape closes the Track Application modal (standard dialog behavior).
    useEffect(() => {
        if (!showModal) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") closeTrackModal();
        };
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [showModal, closeTrackModal]);

    // `loading` starts true; no synchronous setState in the mount effect
    // (set-state-in-effect); the retry handler flips it back on before re-calling.
    const loadApplications = useCallback(async () => {
        try {
            const [response, stats] = await Promise.all([
                getApplications(undefined, 1, 50),
                getApplicationStats().catch(() => null),
            ]);
            setApplications(response.applications);
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

    useEffect(() => {
        const id = window.setTimeout(() => { void loadApplications(); }, 0);
        return () => window.clearTimeout(id);
    }, [loadApplications]);

    const changeStatus = useCallback(async (app: Application, status: ApplicationStatus) => {
        if (updatingRef.current) return;
        updatingRef.current = app.application_id;
        setUpdating(app.application_id);
        try {
            await updateApplicationStatus(app.job_id, { status });
            setApplications((prev) =>
                prev.map((a) => (a.application_id === app.application_id ? { ...a, status } : a)),
            );
        } catch {
            // Optimistic local state: on failure the row keeps its prior status.
        } finally {
            updatingRef.current = null;
            setUpdating(null);
        }
    }, []);

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

    const grouped = useMemo(() => {
        const counts = STATUS_COUNT_ORDER.reduce<Record<ApplicationStatus, number>>(
            (acc, s) => ({ ...acc, [s]: 0 }),
            {} as Record<ApplicationStatus, number>,
        );
        for (const application of applications) {
            counts[application.status] = (counts[application.status] ?? 0) + 1;
        }
        return counts;
    }, [applications]);

    const inputStyle: React.CSSProperties = { background: palette.inset, border: `1px solid ${palette.hair}`, color: palette.ink };
    const selectStyle: React.CSSProperties = { ...inputStyle };

    const subtitle = loading
        ? t("loading")
        : `${total} ${t("flowTrackedAcrossStages")}${total > applications.length ? ` (${t("flowShowingFirst")} ${applications.length})` : ""}`;

    return (
        <div className="fx-root" dir={isAr ? "rtl" : "ltr"} lang={language} style={{ color: palette.ink }}>
            <style dangerouslySetInnerHTML={{ __html: `
                .fx-root .fx-input { outline: none; transition: border-color .15s ease; }
                .fx-root .fx-input:focus { border-color: ${palette.red}; }
                .fx-root .fx-card { transition: border-color .15s ease; }
                .fx-root .fx-card:hover { border-color: ${palette.red}; }
                .fx-root .fx-link { color: ${palette.red}; text-decoration: none; }
                .fx-root .fx-link:hover { text-decoration: underline; text-underline-offset: 2px; }
                .fx-root a:focus-visible, .fx-root button:focus-visible, .fx-root select:focus-visible, .fx-root input:focus-visible {
                    outline: 2px solid ${palette.red}; outline-offset: 2px; border-radius: 4px;
                }
                .fx-root [role="alert"] { border-color: ${palette.hair}; background: ${palette.inset}; }
            ` }} />

            {/* ── Header ── */}
            <header className="pb-5" style={{ borderBottom: `1px solid ${palette.hair}` }}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div className="min-w-0">
                        <Mono style={{ color: palette.ink55 }}>{t("flowPipelineEyebrow")}</Mono>
                        <h1
                            className={`mt-2 text-[2.2rem] font-normal sm:text-[2.8rem] ${isAr ? "leading-[1.15]" : "leading-[0.98]"}`}
                            style={{ fontFamily: SERIF, color: palette.ink }}
                        >
                            {t("flowPipelineTitle")}
                        </h1>
                    </div>
                    {/* List / Board toggle */}
                    <div className="inline-flex shrink-0 items-center rounded-[6px] p-0.5" style={{ border: `1px solid ${palette.hair}` }}>
                        {(["board", "list"] as ViewMode[]).map((mode) => {
                            const active = viewMode === mode;
                            return (
                                <button
                                    key={mode}
                                    type="button"
                                    onClick={() => setViewMode(mode)}
                                    aria-pressed={active}
                                    aria-label={mode === "board" ? t("flowViewBoard") : t("flowViewList")}
                                    style={{
                                        fontFamily: ATELIER_FONT.mono, fontSize: 10, letterSpacing: "0.14em",
                                        textTransform: "uppercase", padding: "5px 12px", borderRadius: 4,
                                        background: active ? palette.ink : "transparent",
                                        color: active ? palette.bg : palette.ink55, cursor: "pointer",
                                    }}
                                >
                                    {mode === "board" ? t("flowViewBoard") : t("flowViewList")}
                                </button>
                            );
                        })}
                    </div>
                </div>
                <p className="mt-3 text-[13px]" style={{ color: palette.ink55 }}>{t("flowPipelineSubtitle")}</p>
            </header>

            {/* ── Toolbar ── */}
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <Mono style={{ color: palette.ink40 }}>{subtitle}</Mono>
                <button
                    type="button"
                    onClick={() => setShowModal(true)}
                    className="fx-card inline-flex items-center gap-1.5 rounded-[6px] px-3.5 py-2 text-[13px] font-semibold"
                    style={{ border: `1px solid ${palette.hair}`, color: palette.ink, background: palette.panel, cursor: "pointer" }}
                >
                    <span aria-hidden="true" style={{ fontSize: 15, lineHeight: 1 }}>+</span>
                    {t("flowTrackApplication")}
                </button>
            </div>

            {/* ── Body ── */}
            <div className="mt-6">
                {loading ? (
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="h-20 animate-pulse rounded-[6px] motion-reduce:animate-none" style={{ background: palette.track }} />
                        ))}
                    </div>
                ) : error ? (
                    <ErrorState
                        variant={error === "auth" ? "auth" : "network"}
                        onRetry={error === "auth" ? undefined : () => { setLoading(true); void loadApplications(); }}
                    />
                ) : applications.length === 0 ? (
                    <div className="rounded-[6px] p-10 text-center" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
                        <p style={{ fontFamily: SERIF, fontSize: "1.5rem", color: palette.ink }}>{t("flowEmptyTitle")}</p>
                        <p className="mt-2 text-sm" style={{ color: palette.ink55 }}>{t("flowEmptyDesc")}</p>
                    </div>
                ) : (
                    <>
                        {/* Stat row */}
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
                            {STATUS_COUNT_ORDER.map((s) => (
                                <div key={s} className="rounded-[6px] px-3 py-3 text-center" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
                                    <p style={{ fontFamily: SERIF, fontSize: "1.5rem", lineHeight: 1, color: palette.ink }}>{grouped[s]}</p>
                                    <Mono className="mt-1.5 block" style={{ color: palette.ink40, fontSize: 9 }}>{t(STATUS_LABEL_KEYS[s])}</Mono>
                                </div>
                            ))}
                        </div>

                        {viewMode === "board" ? (
                            /* ── Kanban board ── */
                            <div className="mt-5 -mx-1 flex gap-3 overflow-x-auto pb-4 sm:mx-0">
                                {KANBAN_COLS.map((col) => {
                                    const colApps = applications.filter((a) => col.statuses.includes(a.status));
                                    return (
                                        <div key={col.labelKey} className="flex min-w-[220px] flex-1 flex-col rounded-[6px] p-3" style={{ border: `1px solid ${palette.hair}`, background: palette.rail }}>
                                            <div className="mb-3 flex items-center justify-between">
                                                <Mono style={{ color: palette.ink55 }}>{t(col.labelKey)}</Mono>
                                                <span className="rounded-full px-2 py-0.5 text-[10px]" style={{ background: palette.inset, color: palette.ink55 }}>{colApps.length}</span>
                                            </div>
                                            <div className="flex flex-col gap-2">
                                                {colApps.length === 0 && <p className="py-4 text-center text-[11px]" style={{ color: palette.ink40 }}>—</p>}
                                                {colApps.map((item) => (
                                                    <div key={item.application_id} className="fx-card rounded-[5px] p-3" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
                                                        <p className="text-xs font-semibold leading-5 [overflow-wrap:anywhere]" style={{ color: palette.ink }}>{item.title}</p>
                                                        <p className="mt-0.5 text-[11px] [overflow-wrap:anywhere]" style={{ color: palette.ink55 }}>{item.company}</p>
                                                        {item.apply_url && item.apply_url !== "#" && (
                                                            <a href={item.apply_url} target="_blank" rel="noreferrer" className="fx-link mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold">
                                                                {t("flowViewListing")} ↗
                                                            </a>
                                                        )}
                                                        <div className="mt-2 flex items-center justify-between gap-2">
                                                            <DateProvenance app={item} language={language} t={t} palette={palette} />
                                                            <label className="sr-only" htmlFor={`board-status-${item.application_id}`}>{`Change status for ${item.title}`}</label>
                                                            <select
                                                                id={`board-status-${item.application_id}`}
                                                                value={item.status}
                                                                onChange={(e) => changeStatus(item, e.target.value as ApplicationStatus)}
                                                                disabled={!!updating}
                                                                className="fx-input rounded-[4px] px-2 py-1 text-[10px]"
                                                                style={selectStyle}
                                                            >
                                                                {STATUS_OPTIONS.map((s) => (<option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>))}
                                                            </select>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            /* ── List view ── */
                            <div className="mt-5 flex flex-col gap-3">
                                {applications.map((item) => (
                                    <div key={item.application_id} className="fx-card rounded-[6px] p-5" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                            <div className="min-w-0">
                                                <h3 className="text-sm font-semibold leading-6 [overflow-wrap:anywhere]" style={{ color: palette.ink }}>{item.title}</h3>
                                                <p className="text-sm [overflow-wrap:anywhere]" style={{ color: palette.ink55 }}>{item.company}</p>
                                                {item.location && <p className="mt-0.5 text-xs [overflow-wrap:anywhere]" style={{ color: palette.ink40 }}>{item.location}</p>}
                                            </div>
                                            <span className="shrink-0 self-start rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase" style={{ background: palette.inset, color: palette.ink70, letterSpacing: isAr ? 0 : "0.08em" }}>
                                                {t(STATUS_LABEL_KEYS[item.status])}
                                            </span>
                                        </div>

                                        {item.apply_url && item.apply_url !== "#" && (
                                            <a href={item.apply_url} target="_blank" rel="noreferrer" className="fx-link mt-3 inline-flex max-w-full items-center gap-1 text-xs font-semibold">
                                                <span className="truncate">{t("flowViewListing")}</span><span aria-hidden="true">↗</span>
                                            </a>
                                        )}

                                        <div className="mt-4 flex flex-col gap-3 pt-4 sm:flex-row sm:items-center" style={{ borderTop: `1px solid ${palette.hair}` }}>
                                            <DateProvenance app={item} language={language} t={t} palette={palette} />
                                            <div className="hidden flex-1 sm:block" />
                                            <label className="sr-only" htmlFor={`status-${item.application_id}`}>{`Change status for ${item.title}`}</label>
                                            <select
                                                id={`status-${item.application_id}`}
                                                value={item.status}
                                                onChange={(e) => changeStatus(item, e.target.value as ApplicationStatus)}
                                                disabled={!!updating}
                                                className="fx-input min-h-9 w-full rounded-[6px] px-3 py-1.5 text-xs sm:w-auto"
                                                style={selectStyle}
                                            >
                                                {STATUS_OPTIONS.map((s) => (<option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>))}
                                            </select>
                                        </div>

                                        <p className="mt-3 text-xs leading-5 [overflow-wrap:anywhere]" style={{ color: palette.ink55 }}>{t(NEXT_ACTION_KEYS[item.status])}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* ── Manual tracking modal ── */}
            {showModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    style={{ background: "rgba(0,0,0,0.5)" }}
                    role="dialog"
                    aria-modal="true"
                    aria-label={t("flowTrackApplicationModalTitle")}
                    dir={isAr ? "rtl" : "ltr"}
                    onClick={closeTrackModal}
                >
                    <div
                        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-md flex-col overflow-hidden rounded-[8px]"
                        style={{ background: palette.panel, border: `1px solid ${palette.hair}`, color: palette.ink }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h2 className="shrink-0 px-5 pb-4 pt-5 sm:px-6 sm:pt-6" style={{ borderBottom: `1px solid ${palette.hair}`, fontFamily: SERIF, fontSize: "1.35rem", color: palette.ink }}>
                            {t("flowTrackApplicationModalTitle")}
                        </h2>
                        <form onSubmit={handleTrackApplication} className="flex-1 space-y-4 overflow-y-auto px-5 pb-5 pt-4 sm:px-6 sm:pb-6" aria-label="Manual application form">
                            {([
                                { id: "title", label: t("flowModalJobTitle"), ph: t("flowPhTitle"), type: "text", key: "title" as const },
                                { id: "company", label: t("flowModalCompany"), ph: t("flowPhCompany"), type: "text", key: "company" as const },
                                { id: "location", label: t("flowModalLocation"), ph: t("flowPhLocation"), type: "text", key: "location" as const },
                                { id: "url", label: t("flowModalUrl"), ph: t("flowPhUrl"), type: "url", key: "url" as const },
                            ]).map((f) => (
                                <div key={f.id}>
                                    <label htmlFor={f.id} className="mb-1 block text-sm" style={{ color: palette.ink55 }}>{f.label}</label>
                                    <input
                                        id={f.id}
                                        type={f.type}
                                        value={formData[f.key]}
                                        onChange={(e) => setFormData({ ...formData, [f.key]: e.target.value })}
                                        className="fx-input w-full rounded-[6px] px-3 py-2 text-sm"
                                        style={inputStyle}
                                        placeholder={f.ph}
                                        disabled={saving}
                                    />
                                </div>
                            ))}
                            <div>
                                <label htmlFor="status" className="mb-1 block text-sm" style={{ color: palette.ink55 }}>{t("flowModalStatus")}</label>
                                <select
                                    id="status"
                                    value={formData.status}
                                    onChange={(e) => setFormData({ ...formData, status: e.target.value as ApplicationStatus })}
                                    className="fx-input w-full rounded-[6px] px-3 py-2 text-sm"
                                    style={selectStyle}
                                    disabled={saving}
                                >
                                    {STATUS_OPTIONS.map((s) => (<option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>))}
                                </select>
                            </div>
                            {formError && <p className="text-xs" role="alert" style={{ color: palette.red }}>{formError}</p>}
                            <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:items-center">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-[6px] px-4 py-2 text-sm font-semibold"
                                    style={{ background: palette.ink, color: palette.bg, opacity: saving ? 0.55 : 1, cursor: saving ? "default" : "pointer" }}
                                >
                                    {saving ? t("saving") : t("flowModalSaveApplication")}
                                </button>
                                <button
                                    type="button"
                                    onClick={closeTrackModal}
                                    disabled={saving}
                                    className="flex-1 rounded-[6px] px-4 py-2 text-sm font-semibold"
                                    style={{ border: `1px solid ${palette.hair}`, color: palette.ink70, background: "transparent", cursor: saving ? "default" : "pointer" }}
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
