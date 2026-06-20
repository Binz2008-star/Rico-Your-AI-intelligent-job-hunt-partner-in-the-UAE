'use client';

import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import {
    ApiError,
    createManualApplication,
    getApplications,
    logout,
    updateApplicationStatus,
} from '@/lib/api';
import type { Application, ApplicationStatus } from '@/types';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation, type TranslationKey } from '@/lib/translations';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

type ViewMode = 'list' | 'board';

const KANBAN_COLS: Array<{ labelKey: TranslationKey; statuses: ApplicationStatus[]; accent: string }> = [
    { labelKey: 'flowColLeads',     statuses: ['saved', 'opened', 'opened_external', 'prepared'], accent: 'border-text-tertiary/30' },
    { labelKey: 'flowColApplied',   statuses: ['applied', 'follow_up_due'],                       accent: 'border-sky-500/30' },
    { labelKey: 'flowColInterview', statuses: ['interview'],                                       accent: 'border-gold/40' },
    { labelKey: 'flowColOutcome',   statuses: ['offer', 'rejected', 'decision_made'],              accent: 'border-magenta/30' },
];

// Maps each canonical backend status to its display-label translation key.
// Backend values are never changed — only the rendered label is localized.
const STATUS_LABEL_KEYS: Record<ApplicationStatus, TranslationKey> = {
    applied: 'flowStatusApplied',
    interview: 'flowStatusInterview',
    offer: 'flowStatusOffer',
    rejected: 'flowStatusRejected',
    saved: 'flowStatusSaved',
    opened: 'flowStatusOpened',
    opened_external: 'flowStatusOpenedExternal',
    prepared: 'flowStatusPrepared',
    follow_up_due: 'flowStatusFollowUpDue',
    decision_made: 'flowStatusDecision',
};

const STATUS_OPTIONS: ApplicationStatus[] = [
    'saved', 'opened', 'opened_external', 'prepared',
    'applied', 'follow_up_due', 'interview', 'offer', 'rejected', 'decision_made',
];

const NEXT_ACTION_KEYS: Record<ApplicationStatus, TranslationKey> = {
    saved: 'flowNextSaved',
    opened: 'flowNextOpened',
    opened_external: 'flowNextOpenedExternal',
    prepared: 'flowNextPrepared',
    applied: 'flowNextApplied',
    follow_up_due: 'flowNextFollowUpDue',
    interview: 'flowNextInterview',
    offer: 'flowNextOffer',
    rejected: 'flowNextRejected',
    decision_made: 'flowNextDecision',
};

// 'opened' and 'opened_external' are excluded from the stat grid — they auto-populate
// on any link click and create noise (most items land here). They remain tracked in the
// Kanban "Leads" column but are not featured as top-line stats.
const STATUS_COUNT_ORDER: ApplicationStatus[] = [
    'applied', 'follow_up_due', 'interview', 'offer',
    'saved', 'prepared', 'rejected', 'decision_made',
];

type ManualApplicationForm = {
    title: string;
    company: string;
    location: string;
    url: string;
    status: ApplicationStatus;
};

function createEmptyFormData(): ManualApplicationForm {
    return {
        title: '',
        company: '',
        location: '',
        url: '',
        status: 'applied',
    };
}

function isLeadWithNoUrl(app: Application): boolean {
    return app.status === 'saved' && (!app.apply_url || app.apply_url === '#');
}

function fmtDate(iso: string | undefined, language: 'en' | 'ar') {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    const locale = language === 'ar' ? 'ar' : 'en-GB';
    return d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function FlowPage() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const router = useRouter();
    const isRTL = language === 'ar';
    const [applications, setApplications] = useState<Application[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<'auth' | 'network' | false>(false);
    const [viewMode, setViewMode] = useState<ViewMode>('list');
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [updating, setUpdating] = useState<string | null>(null);
    const [formData, setFormData] = useState<ManualApplicationForm>(() => createEmptyFormData());

    const loadApplications = useCallback(async () => {
        try {
            const response = await getApplications(undefined, 1, 50);
            setApplications(response.applications);
            setTotal(response.total);
            setError(false);
        } catch (err: unknown) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? 'auth' : 'network');
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
            setFormError(t('flowModalTitleRequired'));
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
            setFormError(err instanceof Error ? err.message : t('flowModalFailedTrack'));
        } finally {
            setSaving(false);
        }
    }, [formData, loadApplications, t]);

    useEffect(() => {
        const id = window.setTimeout(() => { void loadApplications(); }, 0);
        return () => window.clearTimeout(id);
    }, [loadApplications]);

    const handleLogout = useCallback(async () => {
        try {
            await logout();
        } finally {
            router.push('/login');
        }
    }, [router]);

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

    return (
        <AppShell
            title={t('flowTitle')}
            subtitle={loading ? t('loading') : `${total} ${t('flowTrackedAcrossStages')}${total > applications.length ? ` (${t('flowShowingFirst')} ${applications.length})` : ''}`}
            sidebarProps={{
                onLogout: handleLogout,
            }}
        >
            <div
                dir={isRTL ? 'rtl' : 'ltr'}
                className="flex w-full max-w-6xl flex-col gap-5 text-start sm:gap-6"
            >
                {!loading && (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <Badge variant="secondary" className="text-[11px]">
                                {total} {t('flowTrackedAcrossStages')}
                            </Badge>
                            {total > applications.length && (
                                <Badge variant="ghost" className="text-[11px]">
                                    {t('flowShowingFirst')} {applications.length}
                                </Badge>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            {/* List / Board toggle */}
                            <div className="flex items-center rounded-lg border border-overlay/10 bg-surface-elevated/60 p-0.5">
                                <button
                                    onClick={() => setViewMode('list')}
                                    aria-pressed={viewMode === 'list'}
                                    aria-label={t('flowViewList')}
                                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 ${viewMode === 'list' ? 'bg-gold/10 text-gold' : 'text-text-tertiary hover:text-text-secondary'}`}
                                >
                                    <MaterialIcon icon="format_list_bulleted" size={14} />
                                    <span className="hidden sm:inline">{t('flowViewList')}</span>
                                </button>
                                <button
                                    onClick={() => setViewMode('board')}
                                    aria-pressed={viewMode === 'board'}
                                    aria-label={t('flowViewBoard')}
                                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 ${viewMode === 'board' ? 'bg-gold/10 text-gold' : 'text-text-tertiary hover:text-text-secondary'}`}
                                >
                                    <MaterialIcon icon="view_kanban" size={14} />
                                    <span className="hidden sm:inline">{t('flowViewBoard')}</span>
                                </button>
                            </div>
                            <button
                                onClick={() => setShowModal(true)}
                                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-gold/25 bg-gold/[0.06] px-4 py-2 text-xs font-semibold text-gold transition-colors hover:bg-gold/15 sm:w-auto"
                            >
                                <MaterialIcon icon="add" className="text-sm" />
                                {t('flowTrackApplication')}
                            </button>
                        </div>
                    </div>
                )}

                {loading ? (
                    <LoadingState variant="card" message={t('flowLoadingState')} />
                ) : error ? (
                    <ErrorState
                        variant={error === 'auth' ? 'auth' : 'network'}
                        message={error === 'auth' ? t('flowErrAuth') : t('flowErrNetwork')}
                        onRetry={error === 'auth' ? undefined : loadApplications}
                    />
                ) : (
                    <>
                        {applications.length > 0 && (
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-7">
                                {STATUS_COUNT_ORDER.map((s) => (
                                    <Card
                                        key={s}
                                        className="min-h-[76px] bg-surface-elevated/65 p-3 text-center transition-colors hover:border-gold/20 hover:shadow-[0_4px_20px_rgba(245,166,35,0.05)]"
                                    >
                                        <p className="text-xl font-black tracking-tight text-text-primary">
                                            {grouped[s]}
                                        </p>
                                        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-secondary [overflow-wrap:anywhere]">
                                            {t(STATUS_LABEL_KEYS[s])}
                                        </p>
                                    </Card>
                                ))}
                            </div>
                        )}

                        {applications.length === 0 ? (
                            <EmptyState
                                title={t('flowEmptyTitle')}
                                description={t('flowEmptyDesc')}
                            />
                        ) : viewMode === 'board' ? (
                            /* ── Kanban Board ── */
                            <div className="overflow-x-hidden">
                            <div className="-mx-1 flex gap-3 overflow-x-auto pb-4 sm:mx-0">
                                {KANBAN_COLS.map((col) => {
                                    const colApps = applications.filter((a) => col.statuses.includes(a.status));
                                    return (
                                        <div
                                            key={col.labelKey}
                                            className={`flex min-w-[220px] flex-1 flex-col rounded-xl border ${col.accent} bg-surface-elevated/40 p-3 sm:min-w-[200px]`}
                                        >
                                            <div className="mb-3 flex items-center justify-between">
                                                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
                                                    {t(col.labelKey)}
                                                </h3>
                                                <span className="rounded-full bg-overlay/10 px-1.5 py-0.5 text-[10px] font-bold text-text-tertiary">
                                                    {colApps.length}
                                                </span>
                                            </div>
                                            <div className="flex flex-col gap-2">
                                                {colApps.length === 0 && (
                                                    <p className="py-4 text-center text-[11px] text-text-tertiary">—</p>
                                                )}
                                                {colApps.map((item) => (
                                                    <div
                                                        key={item.application_id}
                                                        className="rounded-lg border border-overlay/10 bg-surface/70 p-3 transition-colors hover:border-gold/20"
                                                    >
                                                        <p className="text-xs font-semibold leading-5 text-text-primary [overflow-wrap:anywhere]">
                                                            {item.title}
                                                        </p>
                                                        <p className="mt-0.5 text-[11px] text-text-secondary [overflow-wrap:anywhere]">
                                                            {item.company}
                                                        </p>
                                                        {item.apply_url && item.apply_url !== '#' && (
                                                            <a
                                                                href={item.apply_url}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold text-gold hover:underline"
                                                            >
                                                                {t('flowViewListing')} ↗
                                                            </a>
                                                        )}
                                                        <div className="mt-2 flex items-center justify-between gap-2">
                                                            <span className="text-[10px] text-text-tertiary">
                                                                {fmtDate(item.applied_at, language) ?? ''}
                                                            </span>
                                                            <label className="sr-only" htmlFor={`board-status-${item.application_id}`}>
                                                                {`Change status for ${item.title}`}
                                                            </label>
                                                            <select
                                                                id={`board-status-${item.application_id}`}
                                                                value={item.status}
                                                                onChange={(e) => changeStatus(item, e.target.value as ApplicationStatus)}
                                                                disabled={!!updating}
                                                                className="rounded-md border border-border-soft bg-surface px-2 py-1 text-[10px] text-text-primary outline-none transition-colors focus:border-gold/40 disabled:opacity-40"
                                                            >
                                                                {STATUS_OPTIONS.map((s) => (
                                                                    <option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>
                                                                ))}
                                                            </select>
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
                            /* ── List View ── */
                            <div className="space-y-3">
                                {applications.map((item) => (
                                    <Card
                                        key={item.application_id}
                                        className="bg-surface-elevated/70 transition-all hover:border-gold/20 hover:shadow-[0_8px_32px_rgba(0,0,0,0.25)]"
                                    >
                                        <CardContent className="p-5">
                                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                                <div className="min-w-0">
                                                    <h3 className="text-sm font-semibold leading-6 text-text-primary [overflow-wrap:anywhere]">
                                                        {item.title}
                                                    </h3>
                                                    <p className="text-sm text-text-secondary [overflow-wrap:anywhere]">{item.company}</p>
                                                    {item.location && (
                                                        <p className="mt-0.5 text-xs text-text-tertiary [overflow-wrap:anywhere]">{item.location}</p>
                                                    )}
                                                </div>
                                                <div className="shrink-0 self-start">
                                                    <StatusBadge status={item.status} label={t(STATUS_LABEL_KEYS[item.status])} />
                                                </div>
                                            </div>

                                            {isLeadWithNoUrl(item) && (
                                                <p className="mt-3 flex items-start gap-1.5 text-xs text-rico-amber">
                                                    <MaterialIcon icon="warning" className="mt-0.5 text-xs" />
                                                    <span>{t('flowNoApplyLink')}</span>
                                                </p>
                                            )}

                                            {item.apply_url && item.apply_url !== '#' && (
                                                <a
                                                    href={item.apply_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="mt-3 inline-flex max-w-full items-center gap-1 text-xs font-semibold text-gold hover:text-gold-hover"
                                                >
                                                    <span className="truncate">{t('flowViewListing')}</span>
                                                    <span aria-hidden="true">↗</span>
                                                </a>
                                            )}

                                            <div className="mt-4 flex flex-col gap-3 border-t border-border-subtle pt-4 sm:flex-row sm:items-center">
                                                <span className="text-xs text-text-tertiary">
                                                    {fmtDate(item.applied_at, language) ?? t('flowNoDate')}
                                                </span>
                                                <div className="hidden flex-1 sm:block" />
                                                <label className="sr-only" htmlFor={`status-${item.application_id}`}>
                                                    {`Change status for ${item.title}`}
                                                </label>
                                                <select
                                                    id={`status-${item.application_id}`}
                                                    value={item.status}
                                                    onChange={(e) => changeStatus(item, e.target.value as ApplicationStatus)}
                                                    disabled={!!updating}
                                                    className="min-h-9 w-full rounded-lg border border-border-soft bg-surface px-3 py-1.5 text-xs text-text-primary outline-none transition-colors focus:border-gold/40 disabled:opacity-40 sm:w-auto"
                                                >
                                                    {STATUS_OPTIONS.map((s) => (
                                                        <option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>
                                                    ))}
                                                </select>
                                            </div>

                                            <p className="mt-3 text-xs leading-5 text-text-secondary [overflow-wrap:anywhere]">
                                                {t(NEXT_ACTION_KEYS[item.status])}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Manual tracking modal */}
            {showModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
                    role="dialog"
                    aria-label={t('flowTrackApplicationModalTitle')}
                    dir={isRTL ? 'rtl' : 'ltr'}
                >
                    <Card className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto bg-surface-elevated">
                        <CardContent className="p-5 sm:p-6">
                        <h2 className="font-semibold text-on-surface mb-4">{t('flowTrackApplicationModalTitle')}</h2>
                        <form onSubmit={handleTrackApplication} className="space-y-4" aria-label="Manual application form">
                            <div>
                                <label htmlFor="title" className="block text-sm text-on-surface-variant mb-1">{t('flowModalJobTitle')}</label>
                                <input
                                    id="title"
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder={t('flowPhTitle')}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="company" className="block text-sm text-on-surface-variant mb-1">{t('flowModalCompany')}</label>
                                <input
                                    id="company"
                                    type="text"
                                    value={formData.company}
                                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder={t('flowPhCompany')}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="location" className="block text-sm text-on-surface-variant mb-1">{t('flowModalLocation')}</label>
                                <input
                                    id="location"
                                    type="text"
                                    value={formData.location}
                                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder={t('flowPhLocation')}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="url" className="block text-sm text-on-surface-variant mb-1">{t('flowModalUrl')}</label>
                                <input
                                    id="url"
                                    type="url"
                                    value={formData.url}
                                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder={t('flowPhUrl')}
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="status" className="block text-sm text-on-surface-variant mb-1">{t('flowModalStatus')}</label>
                                <select
                                    id="status"
                                    value={formData.status}
                                    onChange={(e) => setFormData({ ...formData, status: e.target.value as ApplicationStatus })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    disabled={saving}
                                >
                                    {STATUS_OPTIONS.map((s) => (
                                        <option key={s} value={s}>{t(STATUS_LABEL_KEYS[s])}</option>
                                    ))}
                                </select>
                            </div>
                            {formError && <p className="text-xs text-red-400" role="alert">{formError}</p>}
                            <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:items-center">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-60"
                                >
                                    {saving ? t('saving') : t('flowModalSaveApplication')}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowModal(false);
                                        setFormError(null);
                                        setFormData(createEmptyFormData());
                                    }}
                                    disabled={saving}
                                    className="flex-1 rounded-lg border border-border-soft px-4 py-2 text-sm font-semibold text-on-surface-variant transition-colors hover:border-white/20 hover:text-on-surface disabled:opacity-60"
                                >
                                    {t('cancel')}
                                </button>
                            </div>
                        </form>
                        </CardContent>
                    </Card>
                </div>
            )}
        </AppShell>
    );
}
