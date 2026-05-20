'use client';

import { Navigation } from '@/components/layout/Navigation';
import { TopNav } from '@/components/layout/TopNav';
import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { createManualApplication, getApplications } from '@/lib/api';
import type { Application } from '@/types';
import { useCallback, useEffect, useState } from 'react';

const STATUS_LABELS: Record<Application['status'], string> = {
    applied: 'Applied',
    interview: 'Interview',
    offer: 'Offer',
    rejected: 'Rejected',
    saved: 'Saved',
    opened: 'Opened',
    decision_made: 'Decision',
};

export default function FlowPage() {
    const [applications, setApplications] = useState<Application[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [formData, setFormData] = useState({
        title: '',
        company: '',
        location: '',
        url: '',
        status: 'applied',
    });

    const loadApplications = useCallback(async () => {
        try {
            const response = await getApplications(undefined, 1, 6);
            setApplications(response.applications);
            setError(false);
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, []);

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
            await loadApplications();
        } catch (err: unknown) {
            setFormError(err instanceof Error ? err.message : 'Failed to track application');
        } finally {
            setSaving(false);
        }
    }, [formData, loadApplications]);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadApplications();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadApplications]);

    return (
        <div className="relative min-h-screen overflow-x-hidden">
            <AuraGlow aria-hidden="true" variant="cyan" position="top-left" />
            <AuraGlow aria-hidden="true" variant="magenta" position="bottom-right" />
            <TopNav />

            <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
                <div className="mb-section-gap">
                    <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">Application Flow</h1>
                    <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
                        Live application state from the backend pipeline, mapped into Rico&apos;s active flow view.
                    </p>
                </div>

                {loading ? (
                    <div className="space-y-8">
                        {Array.from({ length: 3 }).map((_, index) => (
                            <GlassPanel key={index} className="p-8 rounded-xl border border-white/10 animate-pulse motion-reduce:animate-none">
                                <div className="h-5 w-32 rounded bg-white/5 mb-4" />
                                <div className="h-4 w-44 rounded bg-white/5 mb-2" />
                                <div className="h-4 w-28 rounded bg-white/5" />
                            </GlassPanel>
                        ))}
                    </div>
                ) : error ? (
                    <GlassPanel className="p-6 rounded-xl border border-white/10">
                        <p className="text-on-surface mb-2">Could not load the live pipeline.</p>
                        <p className="text-body-md text-on-surface-variant">
                            Rico&apos;s command interface is available, but this flow surface could not fetch current applications.
                        </p>
                    </GlassPanel>
                ) : applications.length === 0 ? (
                    <GlassPanel className="p-6 rounded-xl border border-white/10">
                        <p className="text-on-surface mb-2">No applications tracked yet.</p>
                        <p className="text-body-md text-on-surface-variant mb-4">
                            Apply to jobs or mark openings as tracked to populate the live flow timeline.
                        </p>
                        <button
                            onClick={() => setShowModal(true)}
                            className="inline-flex items-center gap-2 rounded-lg bg-rico-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-rico-accent-hover"
                        >
                            <MaterialIcon icon="add" className="text-sm" />
                            Track application
                        </button>
                    </GlassPanel>
                ) : (
                    <div className="space-y-8">
                        {applications.map((item, index) => (
                            <GlassPanel key={item.application_id} className="p-8 rounded-xl border border-white/10 hover:border-primary/30 transition-all">
                                <div className="flex items-start justify-between mb-4 gap-4">
                                    <div className="flex items-center gap-4 min-w-0">
                                        <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center shrink-0">
                                            <span className="font-headline-lg text-headline-lg text-primary">{index + 1}</span>
                                        </div>
                                        <div className="min-w-0">
                                            <h3 className="font-headline-lg text-headline-lg text-on-surface truncate">{item.company}</h3>
                                            <p className="text-on-surface-variant truncate">{item.title}</p>
                                        </div>
                                    </div>
                                    <span className="text-label-caps text-[10px] px-3 py-1 border border-white/10 rounded-full shrink-0">
                                        {STATUS_LABELS[item.status]}
                                    </span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="w-full h-[1px] bg-white/10" />
                                    <span className="text-label-caps text-[10px] text-secondary shrink-0">
                                        {item.applied_at ? new Date(item.applied_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Live'}
                                    </span>
                                    <MaterialIcon icon="check_circle" className="text-secondary text-sm" />
                                </div>
                            </GlassPanel>
                        ))}
                    </div>
                )}
            </main>

            {/* Modal for manual application tracking */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" role="dialog" aria-label="Track application">
                    <GlassPanel className="w-full max-w-md p-6 rounded-xl border border-white/10">
                        <h2 className="font-headline-lg text-headline-lg text-on-surface mb-4">Track Application</h2>
                        <form onSubmit={handleTrackApplication} className="space-y-4" aria-label="Manual application form">
                            <div>
                                <label htmlFor="title" className="block text-sm text-on-surface-variant mb-1">
                                    Job Title *
                                </label>
                                <input
                                    id="title"
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                                    placeholder="e.g., Senior Manager Audit Programs"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="company" className="block text-sm text-on-surface-variant mb-1">
                                    Company *
                                </label>
                                <input
                                    id="company"
                                    type="text"
                                    value={formData.company}
                                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                                    className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                                    placeholder="e.g., TALENTMATE"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="location" className="block text-sm text-on-surface-variant mb-1">
                                    Location
                                </label>
                                <input
                                    id="location"
                                    type="text"
                                    value={formData.location}
                                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                                    className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                                    placeholder="e.g., Abu Dhabi"
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="url" className="block text-sm text-on-surface-variant mb-1">
                                    Job URL (optional)
                                </label>
                                <input
                                    id="url"
                                    type="url"
                                    value={formData.url}
                                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                                    className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                                    placeholder="https://..."
                                    disabled={saving}
                                />
                            </div>
                            <div>
                                <label htmlFor="status" className="block text-sm text-on-surface-variant mb-1">
                                    Status
                                </label>
                                <select
                                    id="status"
                                    value={formData.status}
                                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                                    className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                                    disabled={saving}
                                >
                                    <option value="applied">Applied</option>
                                    <option value="interview">Interview</option>
                                    <option value="offer">Offer</option>
                                    <option value="rejected">Rejected</option>
                                    <option value="saved">Saved</option>
                                </select>
                            </div>
                            {formError && <p className="text-xs text-rico-red" role="alert">{formError}</p>}
                            <div className="flex items-center gap-2 pt-2">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 rounded-lg bg-rico-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-rico-accent-hover disabled:opacity-60"
                                >
                                    {saving ? "Saving..." : "Save application"}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowModal(false);
                                        setFormError(null);
                                        setFormData({ title: '', company: '', location: '', url: '', status: 'applied' });
                                    }}
                                    disabled={saving}
                                    className="flex-1 rounded-lg border border-white/10 px-4 py-2 text-sm font-semibold text-rico-text-muted transition-colors hover:border-white/20 hover:text-[#eeeef5] disabled:opacity-60"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </GlassPanel>
                </div>
            )}

            <Navigation />
        </div>
    );
}
