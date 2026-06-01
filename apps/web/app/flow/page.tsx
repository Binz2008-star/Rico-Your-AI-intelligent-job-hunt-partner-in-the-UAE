'use client';

import { DashboardShell } from '@/components/DashboardShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import {
    ApiError,
    createManualApplication,
    getApplications,
    updateApplicationStatus,
} from '@/lib/api';
import type { Application, ApplicationStatus } from '@/types';
import { useCallback, useEffect, useState } from 'react';

const STATUS_LABELS: Record<ApplicationStatus, string> = {
    applied: 'Applied',
    interview: 'Interview',
    offer: 'Offer',
    rejected: 'Rejected',
    saved: 'Saved',
    opened: 'Link opened',
    decision_made: 'Decision',
};

const STATUS_OPTIONS: ApplicationStatus[] = [
    'saved', 'opened', 'applied', 'interview', 'offer', 'rejected', 'decision_made',
];

const NEXT_ACTION: Record<ApplicationStatus, string> = {
    saved: 'Verify the listing. Apply when ready.',
    opened: 'Did you apply? Mark it as Applied.',
    applied: 'No reply in 5–7 days? Send a follow-up.',
    interview: 'Prep your talking points. Review the job description.',
    offer: 'Review terms carefully. Accept, negotiate, or decline.',
    rejected: 'Request feedback if useful. Move on.',
    decision_made: 'Closed. No further action needed.',
};

const STATUS_COUNT_ORDER: ApplicationStatus[] = [
    'applied', 'interview', 'offer', 'saved', 'opened', 'rejected', 'decision_made',
];

function isLeadWithNoUrl(app: Application): boolean {
    return app.status === 'saved' && (!app.apply_url || app.apply_url === '#');
}

function fmtDate(iso?: string) {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function FlowPage() {
    const [applications, setApplications] = useState<Application[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<'auth' | 'network' | false>(false);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [updating, setUpdating] = useState<string | null>(null);
    const [formData, setFormData] = useState({
        title: '',
        company: '',
        location: '',
        url: '',
        status: 'applied',
    });

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
            setFormError('Title and company are required');
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
            setFormData({ title: '', company: '', location: '', url: '', status: 'applied' });
            setLoading(true);
            await loadApplications();
        } catch (err: unknown) {
            setFormError(err instanceof Error ? err.message : 'Failed to track application');
        } finally {
            setSaving(false);
        }
    }, [formData, loadApplications]);

    useEffect(() => {
        const id = window.setTimeout(() => { void loadApplications(); }, 0);
        return () => window.clearTimeout(id);
    }, [loadApplications]);

    const grouped = STATUS_COUNT_ORDER.reduce<Record<ApplicationStatus, number>>(
        (acc, s) => ({ ...acc, [s]: applications.filter((a) => a.status === s).length }),
        {} as Record<ApplicationStatus, number>
    );

    return (
        <DashboardShell
            title="Application Flow"
            subtitle={loading ? 'Loading…' : `${total} tracked across all stages${total > applications.length ? ` (showing first ${applications.length})` : ''}`}
        >
            {/* Page header action — always visible */}
            {!loading && (
                <div className="flex justify-end mb-6">
                    <button
                        onClick={() => setShowModal(true)}
                        className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-4 py-2 text-xs font-semibold text-primary transition-all hover:bg-primary/15"
                    >
                        <MaterialIcon icon="add" className="text-sm" />
                        Track application
                    </button>
                </div>
            )}

            {loading ? (
                <LoadingState variant="card" message="Loading application flow..." />
            ) : error ? (
                <ErrorState
                    variant={error === 'auth' ? 'auth' : 'network'}
                    message={error === 'auth' ? 'Session expired — please log in again.' : 'Could not load the live pipeline.'}
                    onRetry={error === 'auth' ? undefined : loadApplications}
                />
            ) : (
                <div className="space-y-8">
                    {/* Status count summary strip */}
                    {applications.length > 0 && (
                        <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                            {STATUS_COUNT_ORDER.map((s) => (
                                <div
                                    key={s}
                                    className="bg-surface-glass border border-border-subtle rounded-xl p-3 text-center"
                                >
                                    <p className="text-xl font-black tracking-tight text-on-surface">
                                        {grouped[s]}
                                    </p>
                                    <p className="text-[9px] uppercase tracking-wider text-on-surface-variant mt-1">
                                        {STATUS_LABELS[s]}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}

                    {applications.length === 0 ? (
                        <EmptyState
                            title="No applications tracked yet"
                            description="Use the button above to manually track an application, or apply to jobs from the Matches page."
                        />
                    ) : (
                        <div className="space-y-4">
                            {applications.map((item) => (
                                <GlassPanel
                                    key={item.application_id}
                                    className="p-6 rounded-xl border border-border-soft hover:border-primary/30 transition-all"
                                >
                                    {/* Card header: title/company + status badge */}
                                    <div className="flex items-start justify-between gap-4 mb-3">
                                        <div className="min-w-0">
                                            <h3 className="font-semibold text-on-surface truncate">{item.title}</h3>
                                            <p className="text-sm text-on-surface-variant truncate">{item.company}</p>
                                            {item.location && (
                                                <p className="text-xs text-on-surface-variant/60 mt-0.5">{item.location}</p>
                                            )}
                                        </div>
                                        <StatusBadge status={item.status} />
                                    </div>

                                    {/* Lead heuristic warning */}
                                    {isLeadWithNoUrl(item) && (
                                        <p className="text-xs text-amber-400/80 mb-3 flex items-center gap-1">
                                            <MaterialIcon icon="warning" className="text-xs" />
                                            No apply link — verify the listing before submitting.
                                        </p>
                                    )}

                                    {/* Apply URL if present */}
                                    {item.apply_url && item.apply_url !== '#' && (
                                        <a
                                            href={item.apply_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-xs text-primary hover:underline mb-3 inline-block"
                                        >
                                            View listing ↗
                                        </a>
                                    )}

                                    {/* Divider + date + status dropdown */}
                                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border-subtle">
                                        <span className="text-xs text-on-surface-variant/50 shrink-0">
                                            {fmtDate(item.applied_at) ?? 'No date'}
                                        </span>
                                        <div className="flex-1" />
                                        <select
                                            value={item.status}
                                            onChange={(e) => changeStatus(item, e.target.value as ApplicationStatus)}
                                            disabled={!!updating}
                                            aria-label={`Change status for ${item.title}`}
                                            className="bg-surface/60 border border-border-soft rounded-lg px-2 py-1 text-[11px] text-on-surface-variant outline-none focus:border-primary/40 cursor-pointer disabled:opacity-40 transition-opacity"
                                        >
                                            {STATUS_OPTIONS.map((s) => (
                                                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Per-status next-action guidance */}
                                    <p className="text-xs text-on-surface-variant/60 mt-2">
                                        {NEXT_ACTION[item.status]}
                                    </p>
                                </GlassPanel>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Manual tracking modal */}
            {showModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
                    role="dialog"
                    aria-label="Track application"
                >
                    <GlassPanel className="w-full max-w-md p-6 rounded-xl border border-border-soft">
                        <h2 className="font-semibold text-on-surface mb-4">Track Application</h2>
                        <form onSubmit={handleTrackApplication} className="space-y-4" aria-label="Manual application form">
                            <div>
                                <label htmlFor="title" className="block text-sm text-on-surface-variant mb-1">Job Title *</label>
                                <input
                                    id="title"
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder="e.g., HSE Manager"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="company" className="block text-sm text-on-surface-variant mb-1">Company *</label>
                                <input
                                    id="company"
                                    type="text"
                                    value={formData.company}
                                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder="e.g., Aramco"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="location" className="block text-sm text-on-surface-variant mb-1">Location</label>
                                <input
                                    id="location"
                                    type="text"
                                    value={formData.location}
                                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder="e.g., Abu Dhabi"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="url" className="block text-sm text-on-surface-variant mb-1">Job URL (optional)</label>
                                <input
                                    id="url"
                                    type="url"
                                    value={formData.url}
                                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    placeholder="https://..."
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="status" className="block text-sm text-on-surface-variant mb-1">Status</label>
                                <select
                                    id="status"
                                    value={formData.status}
                                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                                    className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-on-surface outline-none transition focus:border-primary/40"
                                    disabled={saving}
                                >
                                    <option value="applied">Applied</option>
                                    <option value="saved">Saved</option>
                                    <option value="interview">Interview</option>
                                    <option value="offer">Offer</option>
                                    <option value="rejected">Rejected</option>
                                </select>
                            </div>
                            {formError && <p className="text-xs text-red-400" role="alert">{formError}</p>}
                            <div className="flex items-center gap-2 pt-2">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-60"
                                >
                                    {saving ? 'Saving…' : 'Save application'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowModal(false);
                                        setFormError(null);
                                        setFormData({ title: '', company: '', location: '', url: '', status: 'applied' });
                                    }}
                                    disabled={saving}
                                    className="flex-1 rounded-lg border border-border-soft px-4 py-2 text-sm font-semibold text-on-surface-variant transition-colors hover:border-white/20 hover:text-on-surface disabled:opacity-60"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </GlassPanel>
                </div>
            )}
        </DashboardShell>
    );
}
