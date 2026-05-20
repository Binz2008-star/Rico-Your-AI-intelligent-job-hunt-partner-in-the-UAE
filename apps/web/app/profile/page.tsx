"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { StatusCard } from "@/components/StatusCard";
import { fetchProfile, updateProfile, type ProfileResponse } from "@/lib/api";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function Tag({ label }: { label: string }) {
    return (
        <span className="rounded-md bg-white/[0.06] px-2 py-0.5 text-xs text-rico-text-muted">
            {label}
        </span>
    );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div>
            <dt className="text-rico-text-dim">{label}</dt>
            <dd>{children}</dd>
        </div>
    );
}

function ChatCTA({ message }: { message: string }) {
    return (
        <div className="rounded-lg border border-rico-accent-border bg-rico-accent/[0.05] px-4 py-3">
            <p className="mb-2 text-sm text-rico-text-dim">{message}</p>
            <Link
                href="/command"
                className="inline-block rounded-lg bg-rico-accent px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-rico-accent-hover"
            >
                Open Rico chat →
            </Link>
        </div>
    );
}

function ChatEditCTA({ prompt }: { prompt: string }) {
    return (
        <Link
            href={`/command?prompt=${encodeURIComponent(prompt)}`}
            className="ml-2 text-[11px] text-rico-purple hover:text-[#c4b5fd] transition-colors underline underline-offset-2"
        >
            Edit
        </Link>
    );
}

function EditableNameField({
    value,
    onSave,
}: {
    value: string | null | undefined;
    onSave: (nextName: string) => Promise<void>;
}) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value ?? "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const displayValue = value?.trim() ? value : "—";

    const handleCancel = useCallback(() => {
        setDraft(value ?? "");
        setEditing(false);
        setError(null);
    }, [value]);

    const handleSave = useCallback(
        async (event: React.FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            const trimmed = draft.trim();
            if (!trimmed) {
                setError("Name cannot be empty.");
                return;
            }

            setSaving(true);
            setError(null);
            try {
                await onSave(trimmed);
                setEditing(false);
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : "Could not save name.");
            } finally {
                setSaving(false);
            }
        },
        [draft, onSave]
    );

    if (!editing) {
        return (
            <>
                <span className="text-[#eeeef5]">{displayValue}</span>
                <button
                    type="button"
                    aria-label="Edit name"
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="ml-2 text-[11px] text-rico-purple underline underline-offset-2 transition-colors hover:text-[#c4b5fd]"
                >
                    Edit
                </button>
            </>
        );
    }

    return (
        <form className="mt-2 flex max-w-sm flex-col gap-2" onSubmit={handleSave}>
            <label htmlFor="profile-name" className="sr-only">
                Name
            </label>
            <input
                id="profile-name"
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                placeholder="Enter your name"
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-rico-accent px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rico-accent-hover disabled:opacity-60"
                >
                    {saving ? "Saving..." : "Save"}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-rico-text-muted transition-colors hover:border-white/20 hover:text-[#eeeef5] disabled:opacity-60"
                >
                    Cancel
                </button>
            </div>
        </form>
    );
}

function EditableTextField({
    value,
    onSave,
    placeholder = "Enter value",
    label = "Field",
}: {
    value: string | null | undefined;
    onSave: (nextValue: string) => Promise<void>;
    placeholder?: string;
    label?: string;
}) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value ?? "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const displayValue = value?.trim() ? value : "—";

    const handleCancel = useCallback(() => {
        setDraft(value ?? "");
        setEditing(false);
        setError(null);
    }, [value]);

    const handleSave = useCallback(
        async (event: React.FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            const trimmed = draft.trim();
            setSaving(true);
            setError(null);
            try {
                await onSave(trimmed);
                setEditing(false);
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : "Could not save.");
            } finally {
                setSaving(false);
            }
        },
        [draft, onSave]
    );

    if (!editing) {
        return (
            <>
                <span className="text-[#eeeef5]">{displayValue}</span>
                <button
                    type="button"
                    aria-label={`Edit ${label}`}
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="ml-2 text-[11px] text-rico-purple underline underline-offset-2 transition-colors hover:text-[#c4b5fd]"
                >
                    Edit
                </button>
            </>
        );
    }

    return (
        <form className="mt-2 flex max-w-sm flex-col gap-2" onSubmit={handleSave}>
            <label htmlFor={`profile-${label}`} className="sr-only">
                {label}
            </label>
            <input
                id={`profile-${label}`}
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-[#eeeef5] outline-none transition focus:border-rico-accent"
                placeholder={placeholder}
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-rico-accent px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rico-accent-hover disabled:opacity-60"
                >
                    {saving ? "Saving..." : "Save"}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-rico-text-muted transition-colors hover:border-white/20 hover:text-[#eeeef5] disabled:opacity-60"
                >
                    Cancel
                </button>
            </div>
        </form>
    );
}

function ProfileDetail({
    profile,
    onSaveName,
    onSavePhone,
    onSaveTelegram,
    onSaveVisa,
    onSaveNotice,
    onSaveMinSalary,
    onSaveCurrentCompany,
    onSaveLinkedin,
}: {
    profile: ProfileResponse;
    onSaveName: (nextName: string) => Promise<void>;
    onSavePhone: (nextPhone: string) => Promise<void>;
    onSaveTelegram: (nextTelegram: string) => Promise<void>;
    onSaveVisa: (nextVisa: string) => Promise<void>;
    onSaveNotice: (nextNotice: string) => Promise<void>;
    onSaveMinSalary: (nextMinSalary: number) => Promise<void>;
    onSaveCurrentCompany: (nextCompany: string) => Promise<void>;
    onSaveLinkedin: (nextLinkedin: string) => Promise<void>;
}) {
    const hasJobPrefs =
        (profile.target_roles?.length ?? 0) > 0 ||
        (profile.preferred_cities?.length ?? 0) > 0 ||
        profile.salary_expectation_aed != null ||
        profile.years_experience != null;

    const hasSkills = (profile.skills?.length ?? 0) > 0;

    return (
        <div className="flex flex-col gap-4">
            {/* Identity */}
            <StatusCard title="Identity" badge="live">
                <dl className="grid grid-cols-1 gap-y-3 text-sm sm:grid-cols-2 sm:gap-x-6">
                    <Row label="Name">
                        <EditableNameField value={profile.name} onSave={onSaveName} />
                    </Row>
                    <Row label="Email">
                        <span className="text-[#eeeef5]">{profile.email ?? "—"}</span>
                    </Row>
                    <Row label="Phone">
                        <EditableTextField
                            value={profile.phone}
                            onSave={onSavePhone}
                            placeholder="Enter phone number"
                            label="phone"
                        />
                    </Row>
                    <Row label="Telegram">
                        <EditableTextField
                            value={profile.telegram_username}
                            onSave={onSaveTelegram}
                            placeholder="Enter Telegram username"
                            label="telegram"
                        />
                    </Row>
                    <Row label="Visa">
                        <EditableTextField
                            value={profile.visa_status}
                            onSave={onSaveVisa}
                            placeholder="Enter visa status"
                            label="visa"
                        />
                    </Row>
                    <Row label="Notice">
                        <EditableTextField
                            value={profile.notice_period}
                            onSave={onSaveNotice}
                            placeholder="Enter notice period"
                            label="notice"
                        />
                    </Row>
                    <Row label="Current company">
                        <EditableTextField
                            value={profile.current_company}
                            onSave={onSaveCurrentCompany}
                            placeholder="Enter current company"
                            label="current-company"
                        />
                    </Row>
                    <Row label="LinkedIn">
                        <EditableTextField
                            value={profile.linkedin_url}
                            onSave={onSaveLinkedin}
                            placeholder="Enter LinkedIn URL"
                            label="linkedin"
                        />
                    </Row>
                </dl>
            </StatusCard>

            {/* Job preferences */}
            <StatusCard title="Job preferences" badge={hasJobPrefs ? "live" : "pending"}>
                {hasJobPrefs ? (
                    <dl className="grid grid-cols-1 gap-y-3 text-sm sm:grid-cols-2 sm:gap-x-6">
                        <Row label="Target roles">
                            {(profile.target_roles?.length ?? 0) > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                    {profile.target_roles!.map((r) => <Tag key={r} label={r} />)}
                                </div>
                            ) : (
                                <span className="text-[#eeeef5]">—</span>
                            )}
                            <ChatEditCTA prompt="Update my target roles" />
                        </Row>
                        <Row label="Cities">
                            {(profile.preferred_cities?.length ?? 0) > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                    {profile.preferred_cities!.map((c) => <Tag key={c} label={c} />)}
                                </div>
                            ) : (
                                <span className="text-[#eeeef5]">—</span>
                            )}
                            <ChatEditCTA prompt="Update my preferred cities" />
                        </Row>
                        <Row label="Salary target">
                            <span className="text-[#eeeef5]">
                                {profile.salary_expectation_aed != null ? `AED ${profile.salary_expectation_aed.toLocaleString()}` : "—"}
                            </span>
                            <ChatEditCTA prompt="Update my salary target" />
                        </Row>
                        <Row label="Minimum salary">
                            <EditableTextField
                                value={profile.minimum_salary_aed != null ? String(profile.minimum_salary_aed) : null}
                                onSave={async (val) => {
                                    const parsed = Number(val);
                                    if (!Number.isFinite(parsed) || parsed < 0) {
                                        throw new Error("Enter a valid salary amount.");
                                    }
                                    return onSaveMinSalary(parsed);
                                }}
                                placeholder="Enter minimum salary (AED)"
                                label="min-salary"
                            />
                        </Row>
                        <Row label="Experience">
                            <span className="text-[#eeeef5]">
                                {profile.years_experience != null ? `${profile.years_experience} yrs` : "—"}
                            </span>
                            <ChatEditCTA prompt="Update my years of experience" />
                        </Row>
                    </dl>
                ) : (
                    <ChatCTA message="Tell Rico your target roles, preferred cities, and salary expectations to complete your job preferences." />
                )}
            </StatusCard>

            {/* Skills */}
            <StatusCard title="Skills" badge={hasSkills ? "live" : "pending"}>
                {hasSkills ? (
                    <div className="flex flex-wrap gap-1.5">
                        {(profile.skills ?? []).map((s) => <Tag key={s} label={s} />)}
                        <ChatEditCTA prompt="Update my skills" />
                    </div>
                ) : (
                    <ChatCTA message="Share your skills with Rico to improve job matching accuracy." />
                )}
            </StatusCard>
        </div>
    );
}

export default function ProfilePage() {
    const [profile, setProfile] = useState<ProfileResponse | null>(null);
    const [error, setError] = useState<"auth" | "other" | null>(null);
    const [loading, setLoading] = useState(true);

    const loadProfile = useCallback(async () => {
        try {
            const data = await fetchProfile();
            setProfile(data);
            setError(null);
        } catch (err: unknown) {
            const is401 = err instanceof Error && err.message.includes("401");
            setError(is401 ? "auth" : "other");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadProfile();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadProfile]);

    const handleRetry = useCallback(() => {
        setError(null);
        setLoading(true);
        void loadProfile();
    }, [loadProfile]);

    const handleSaveName = useCallback(async (nextName: string) => {
        await updateProfile({ name: nextName });
        setProfile((current) => (current ? { ...current, name: nextName } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSavePhone = useCallback(async (nextPhone: string) => {
        await updateProfile({ phone: nextPhone });
        setProfile((current) => (current ? { ...current, phone: nextPhone } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveTelegram = useCallback(async (nextTelegram: string) => {
        await updateProfile({ telegram_username: nextTelegram });
        setProfile((current) => (current ? { ...current, telegram_username: nextTelegram } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveVisa = useCallback(async (nextVisa: string) => {
        await updateProfile({ visa_status: nextVisa });
        setProfile((current) => (current ? { ...current, visa_status: nextVisa } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveNotice = useCallback(async (nextNotice: string) => {
        await updateProfile({ notice_period: nextNotice });
        setProfile((current) => (current ? { ...current, notice_period: nextNotice } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveMinSalary = useCallback(async (nextMinSalary: number) => {
        await updateProfile({ minimum_salary_aed: nextMinSalary });
        setProfile((current) => (current ? { ...current, minimum_salary_aed: nextMinSalary } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveCurrentCompany = useCallback(async (nextCompany: string) => {
        await updateProfile({ current_company: nextCompany });
        setProfile((current) => (current ? { ...current, current_company: nextCompany } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    const handleSaveLinkedin = useCallback(async (nextLinkedin: string) => {
        await updateProfile({ linkedin_url: nextLinkedin });
        setProfile((current) => (current ? { ...current, linkedin_url: nextLinkedin } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            // Keep the optimistic value if the follow-up read fails.
        }
    }, []);

    return (
        <DashboardShell title="Profile">
            <div className="max-w-2xl">
                {loading && <LoadingState variant="card" message="Loading profile…" />}

                {!loading && error && (
                    <ErrorState
                        variant={error === "auth" ? "auth" : "network"}
                        onRetry={handleRetry}
                    />
                )}

                {!loading && !error && profile && !profile.profile_exists && (
                    <div className="flex flex-col gap-4">
                        <EmptyState
                            title="No profile set up yet"
                            description="Rico builds your profile through a short conversation. Tell it your target role, experience, location, and salary range to get started."
                            actionLabel="Start setup with Rico"
                            actionHref="/command"
                        />

                        <div className="rounded-xl border border-rico-border bg-rico-surface-2/60 p-5">
                            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-rico-text-dim">
                                What Rico will set up
                            </h3>
                            <ul className="flex flex-col gap-2 text-sm text-rico-text-muted">
                                {[
                                    "Target roles and preferred job titles",
                                    "Preferred cities and remote preferences",
                                    "Salary expectations",
                                    "Years of experience and skills",
                                    "Visa status and notice period",
                                ].map((item) => (
                                    <li key={item} className="flex items-start gap-2">
                                        <span className="mt-0.5 text-rico-purple">·</span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                )}

                {!loading && !error && profile?.profile_exists && (
                    <ProfileDetail
                        profile={profile}
                        onSaveName={handleSaveName}
                        onSavePhone={handleSavePhone}
                        onSaveTelegram={handleSaveTelegram}
                        onSaveVisa={handleSaveVisa}
                        onSaveNotice={handleSaveNotice}
                        onSaveMinSalary={handleSaveMinSalary}
                        onSaveCurrentCompany={handleSaveCurrentCompany}
                        onSaveLinkedin={handleSaveLinkedin}
                    />
                )}
            </div>
        </DashboardShell>
    );
}
