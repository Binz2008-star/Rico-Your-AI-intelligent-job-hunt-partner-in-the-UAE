"use client";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { StatusCard } from "@/components/StatusCard";
import { ToastContainer } from "@/components/ui/Toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/useToast";
import { ApiError, fetchProfile, logout, updateProfile, type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function Tag({ label }: { label: string }) {
    return (
        <span className="rounded-md bg-surface-glass px-2 py-0.5 text-xs text-text-secondary">
            {label}
        </span>
    );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="min-w-0 rounded-xl border border-overlay/8 bg-surface-elevated/50 p-4 backdrop-blur-sm">
            <dt className="text-start text-[11px] font-semibold uppercase tracking-[0.12em] text-text-tertiary">{label}</dt>
            <dd className="mt-2 min-w-0 text-start text-sm leading-6 text-text-primary [overflow-wrap:anywhere]">{children}</dd>
        </div>
    );
}


function ChatEditCTA({ prompt }: { prompt: string }) {
    return (
        <Link
            href={`/command?prompt=${encodeURIComponent(prompt)}`}
            className="ms-2 text-[11px] font-semibold text-magenta hover:text-magenta-hover transition-colors underline underline-offset-2"
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
    const { language } = useLanguage();
    const t = useTranslation(language);
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
                setError(t("profileNameEmpty"));
                return;
            }

            setSaving(true);
            setError(null);
            try {
                await onSave(trimmed);
                setEditing(false);
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : t("profileCouldNotSaveName"));
            } finally {
                setSaving(false);
            }
        },
        [draft, onSave, t]
    );

    if (!editing) {
        return (
            <span className="inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 align-top">
                <span className="min-w-0 text-text-primary [overflow-wrap:anywhere]">{displayValue}</span>
                <button
                    type="button"
                    aria-label={`${t("edit")} ${t("name").toLowerCase()}`}
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="text-[11px] font-semibold text-magenta underline underline-offset-2 transition-colors hover:text-magenta-hover"
                >
                    {t("edit")}
                </button>
            </span>
        );
    }

    return (
        <form className="mt-2 flex w-full max-w-lg flex-col gap-2" onSubmit={handleSave}>
            <label htmlFor="profile-name" className="sr-only">
                {t("name")}
            </label>
            <input
                id="profile-name"
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-text-primary outline-none transition focus:border-rico-accent"
                placeholder={t("profileEnterName")}
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex flex-wrap items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-rico-accent px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rico-accent-hover disabled:opacity-60"
                >
                    {saving ? t("profileSaving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-lg border border-border-soft px-3 py-1.5 text-xs font-semibold text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:opacity-60"
                >
                    {t("cancel")}
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
    const { language } = useLanguage();
    const t = useTranslation(language);
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
                setError(err instanceof Error ? err.message : t("profileCouldNotSave"));
            } finally {
                setSaving(false);
            }
        },
        [draft, onSave, t]
    );

    if (!editing) {
        return (
            <>
                <span className="inline-block max-w-full text-text-primary [overflow-wrap:anywhere]">{displayValue}</span>
                <button
                    type="button"
                    aria-label={`${t("edit")} ${label}`}
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="ms-2 text-[11px] font-semibold text-magenta underline underline-offset-2 transition-colors hover:text-magenta-hover"
                >
                    {t("edit")}
                </button>
            </>
        );
    }

    return (
        <form className="mt-2 flex w-full max-w-lg flex-col gap-2" onSubmit={handleSave}>
            <label htmlFor={`profile-${label}`} className="sr-only">
                {label}
            </label>
            <input
                id={`profile-${label}`}
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-text-primary outline-none transition focus:border-rico-accent"
                placeholder={placeholder}
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex flex-wrap items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-rico-accent px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rico-accent-hover disabled:opacity-60"
                >
                    {saving ? t("profileSaving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-lg border border-border-soft px-3 py-1.5 text-xs font-semibold text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:opacity-60"
                >
                    {t("cancel")}
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
    onSaveCurrentRole,
    onSaveLinkedin,
    onSaveTargetRoles,
    onSaveCities,
    onSaveSalaryTarget,
    onSaveExperience,
    onSaveSkills,
}: {
    profile: ProfileResponse;
    onSaveName: (nextName: string) => Promise<void>;
    onSavePhone: (nextPhone: string) => Promise<void>;
    onSaveTelegram: (nextTelegram: string) => Promise<void>;
    onSaveVisa: (nextVisa: string) => Promise<void>;
    onSaveNotice: (nextNotice: string) => Promise<void>;
    onSaveMinSalary: (nextMinSalary: number) => Promise<void>;
    onSaveCurrentCompany: (nextCompany: string) => Promise<void>;
    onSaveCurrentRole: (nextRole: string) => Promise<void>;
    onSaveLinkedin: (nextLinkedin: string) => Promise<void>;
    onSaveTargetRoles: (nextRoles: string) => Promise<void>;
    onSaveCities: (nextCities: string) => Promise<void>;
    onSaveSalaryTarget: (nextSalary: string) => Promise<void>;
    onSaveExperience: (nextExperience: string) => Promise<void>;
    onSaveSkills: (nextSkills: string) => Promise<void>;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const hasJobPrefs =
        (profile.target_roles?.length ?? 0) > 0 ||
        (profile.preferred_cities?.length ?? 0) > 0 ||
        profile.salary_expectation_aed != null ||
        profile.years_experience != null;

    const hasSkills = (profile.skills?.length ?? 0) > 0;

    return (
        <div className="flex w-full flex-col gap-5">
            {/* Identity */}
            <StatusCard title={t("profileIdentity")} badge="live" badgeLabel={t("profileBadgeSynced")}>
                <dl className="grid min-w-0 grid-cols-1 gap-3 text-sm lg:grid-cols-2">
                    <Row label={t("name")}>
                        <EditableNameField value={profile.name} onSave={onSaveName} />
                    </Row>
                    <Row label={t("email")}>
                        <span className="text-text-primary">{profile.email ?? "—"}</span>
                    </Row>
                    <Row label={t("profilePhone")}>
                        <EditableTextField
                            value={profile.phone}
                            onSave={onSavePhone}
                            placeholder={t("profileEnterPhone")}
                            label="phone"
                        />
                    </Row>
                    <Row label={t("telegram")}>
                        <EditableTextField
                            value={profile.telegram_username}
                            onSave={onSaveTelegram}
                            placeholder={t("profileEnterTelegram")}
                            label="telegram"
                        />
                    </Row>
                    <Row label={t("profileVisa")}>
                        <EditableTextField
                            value={profile.visa_status}
                            onSave={onSaveVisa}
                            placeholder={t("profileEnterVisa")}
                            label="visa"
                        />
                    </Row>
                    <Row label={t("profileNotice")}>
                        <EditableTextField
                            value={profile.notice_period}
                            onSave={onSaveNotice}
                            placeholder={t("profileEnterNotice")}
                            label="notice"
                        />
                    </Row>
                    <Row label={t("profileCurrentCompany")}>
                        <EditableTextField
                            value={profile.current_company}
                            onSave={onSaveCurrentCompany}
                            placeholder={t("profileEnterCurrentCompany")}
                            label="current-company"
                        />
                    </Row>
                    <Row label={t("profileCurrentRole")}>
                        <EditableTextField
                            value={profile.current_role}
                            onSave={onSaveCurrentRole}
                            placeholder={t("profileEnterCurrentRole")}
                            label="current-role"
                        />
                    </Row>
                    <Row label={t("profileLinkedin")}>
                        <EditableTextField
                            value={profile.linkedin_url}
                            onSave={onSaveLinkedin}
                            placeholder={t("profileEnterLinkedin")}
                            label="linkedin"
                        />
                    </Row>
                </dl>
            </StatusCard>

            {/* Job preferences */}
            <StatusCard title={t("profileJobPreferences")} badge={hasJobPrefs ? "live" : "pending"} badgeLabel={hasJobPrefs ? t("profileBadgeSynced") : t("profileBadgePending")}>
                <dl className="grid min-w-0 grid-cols-1 gap-3 text-sm lg:grid-cols-2">
                    <Row label={t("profileTargetRoles")}>
                        <EditableTextField
                            value={profile.target_roles?.join(', ') || null}
                            onSave={onSaveTargetRoles}
                            placeholder={t("profileEnterTargetRoles")}
                            label="target-roles"
                        />
                    </Row>
                    <Row label={t("profileCities")}>
                        <EditableTextField
                            value={profile.preferred_cities?.join(', ') || null}
                            onSave={onSaveCities}
                            placeholder={t("profileEnterCities")}
                            label="cities"
                        />
                    </Row>
                    <Row label={t("profileSalaryTarget")}>
                        <EditableTextField
                            value={profile.salary_expectation_aed != null ? String(profile.salary_expectation_aed) : null}
                            onSave={onSaveSalaryTarget}
                            placeholder={t("profileEnterSalaryTarget")}
                            label="salary-target"
                        />
                    </Row>
                    <Row label={t("profileMinimumSalary")}>
                        <EditableTextField
                            value={profile.minimum_salary_aed != null ? String(profile.minimum_salary_aed) : null}
                            onSave={async (val) => {
                                const parsed = Number(val);
                                if (!Number.isFinite(parsed) || parsed < 0) {
                                    throw new Error(t("profileInvalidSalary"));
                                }
                                return onSaveMinSalary(parsed);
                            }}
                            placeholder={t("profileEnterMinSalary")}
                            label="min-salary"
                        />
                    </Row>
                    <Row label={t("profileExperience")}>
                        <EditableTextField
                            value={profile.years_experience != null ? String(profile.years_experience) : null}
                            onSave={onSaveExperience}
                            placeholder={t("profileEnterExperience")}
                            label="experience"
                        />
                    </Row>
                </dl>
            </StatusCard>

            {/* Skills */}
            <StatusCard title={t("profileSkills")} badge={hasSkills ? "live" : "pending"} badgeLabel={hasSkills ? t("profileBadgeSynced") : t("profileBadgePending")}>
                <EditableTextField
                    value={profile.skills?.join(', ') || null}
                    onSave={onSaveSkills}
                    placeholder={t("profileEnterSkills")}
                    label="skills"
                />
            </StatusCard>
        </div>
    );
}

export default function ProfilePage() {
    const router = useRouter();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const { toasts, toast } = useToast();

    const handleLogout = useCallback(async () => {
        try {
            await logout();
        } finally {
            router.push("/login");
        }
    }, [router]);
    const [profile, setProfile] = useState<ProfileResponse | null>(null);
    const [error, setError] = useState<"auth" | "other" | null>(null);
    const [loading, setLoading] = useState(true);

    const warnRefreshFail = useCallback(() => {
        toast(t("profileRefreshFailed"), "error");
    }, [toast, t]);

    const loadProfile = useCallback(async () => {
        try {
            const data = await fetchProfile();
            setProfile(data);
            setError(null);
        } catch (err: unknown) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
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
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSavePhone = useCallback(async (nextPhone: string) => {
        await updateProfile({ phone: nextPhone });
        setProfile((current) => (current ? { ...current, phone: nextPhone } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveTelegram = useCallback(async (nextTelegram: string) => {
        await updateProfile({ telegram_username: nextTelegram });
        setProfile((current) => (current ? { ...current, telegram_username: nextTelegram } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveVisa = useCallback(async (nextVisa: string) => {
        await updateProfile({ visa_status: nextVisa });
        setProfile((current) => (current ? { ...current, visa_status: nextVisa } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveNotice = useCallback(async (nextNotice: string) => {
        await updateProfile({ notice_period: nextNotice });
        setProfile((current) => (current ? { ...current, notice_period: nextNotice } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveMinSalary = useCallback(async (nextMinSalary: number) => {
        await updateProfile({ minimum_salary_aed: nextMinSalary });
        setProfile((current) => (current ? { ...current, minimum_salary_aed: nextMinSalary } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveCurrentCompany = useCallback(async (nextCompany: string) => {
        await updateProfile({ current_company: nextCompany });
        setProfile((current) => (current ? { ...current, current_company: nextCompany } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveCurrentRole = useCallback(async (nextRole: string) => {
        await updateProfile({ current_role: nextRole });
        setProfile((current) => (current ? { ...current, current_role: nextRole } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveLinkedin = useCallback(async (nextLinkedin: string) => {
        await updateProfile({ linkedin_url: nextLinkedin });
        setProfile((current) => (current ? { ...current, linkedin_url: nextLinkedin } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveTargetRoles = useCallback(async (nextRoles: string) => {
        const roles = nextRoles.split(',').map(r => r.trim()).filter(Boolean);
        await updateProfile({ target_roles: roles });
        setProfile((current) => (current ? { ...current, target_roles: roles } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveCities = useCallback(async (nextCities: string) => {
        const cities = nextCities.split(',').map(c => c.trim()).filter(Boolean);
        await updateProfile({ preferred_cities: cities });
        setProfile((current) => (current ? { ...current, preferred_cities: cities } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    const handleSaveSalaryTarget = useCallback(async (nextSalary: string) => {
        const parsed = Number(nextSalary);
        if (!Number.isFinite(parsed) || parsed < 0) {
            throw new Error(t("profileInvalidSalary"));
        }
        await updateProfile({ salary_expectation_aed: parsed });
        setProfile((current) => (current ? { ...current, salary_expectation_aed: parsed } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail, t]);

    const handleSaveExperience = useCallback(async (nextExperience: string) => {
        const parsed = Number(nextExperience);
        if (!Number.isFinite(parsed) || parsed < 0) {
            throw new Error(t("profileInvalidYears"));
        }
        await updateProfile({ years_experience: parsed });
        setProfile((current) => (current ? { ...current, years_experience: parsed } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail, t]);

    const handleSaveSkills = useCallback(async (nextSkills: string) => {
        const skills = nextSkills.split(',').map(s => s.trim()).filter(Boolean);
        await updateProfile({ skills });
        setProfile((current) => (current ? { ...current, skills } : current));

        try {
            const refreshed = await fetchProfile();
            setProfile(refreshed);
        } catch {
            warnRefreshFail();
        }
    }, [warnRefreshFail]);

    return (
        <AppShell
            title={t("profileTitle")}
            sidebarProps={{
                user: profile ? { name: profile.name ?? undefined, email: profile.email } : undefined,
                onLogout: handleLogout,
            }}
        >
            <div
                dir={language === "ar" ? "rtl" : "ltr"}
                className="w-full max-w-5xl py-3 text-start sm:py-4 lg:max-w-6xl"
            >
                {loading && <LoadingState variant="card" message={t("profileLoading")} />}

                {!loading && error && (
                    <ErrorState
                        variant={error === "auth" ? "auth" : "network"}
                        title={error === "auth" ? t("profileAuthRequired") : t("profileConnectionFailed")}
                        message={error === "auth" ? t("profileAuthRequiredMsg") : t("profileConnectionFailedMsg")}
                        onRetry={handleRetry}
                    />
                )}

                {!loading && !error && profile && !profile.profile_exists && (
                    <div className="flex flex-col gap-4">
                        <EmptyState
                            title={t("profileNoProfileTitle")}
                            description={t("profileNoProfileDesc")}
                            actionLabel={t("profileStartSetup")}
                            actionHref="/command"
                        />

                        <div className="rounded-xl border border-border-soft bg-surface-elevated/70 p-5">
                            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                                {t("profileWhatRicoSetsUp")}
                            </h3>
                            <ul className="flex flex-col gap-2 text-sm text-text-secondary">
                                {[
                                    t("profileSetupRoles"),
                                    t("profileSetupCities"),
                                    t("profileSetupSalary"),
                                    t("profileSetupExperience"),
                                    t("profileSetupVisa"),
                                ].map((item) => (
                                    <li key={item} className="flex items-start gap-2">
                                        <span className="mt-0.5 text-gold">·</span>
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
                        onSaveCurrentRole={handleSaveCurrentRole}
                        onSaveLinkedin={handleSaveLinkedin}
                        onSaveTargetRoles={handleSaveTargetRoles}
                        onSaveCities={handleSaveCities}
                        onSaveSalaryTarget={handleSaveSalaryTarget}
                        onSaveExperience={handleSaveExperience}
                        onSaveSkills={handleSaveSkills}
                    />
                )}
            </div>
            <ToastContainer toasts={toasts} />
        </AppShell>
    );
}
