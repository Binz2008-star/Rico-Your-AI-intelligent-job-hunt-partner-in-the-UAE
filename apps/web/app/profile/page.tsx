"use client";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ToastContainer } from "@/components/ui/Toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/useToast";
import { ApiError, fetchProfile, logout, updateProfile, type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function SectionHeader({ title, badge, badgeVariant = "default" }: { title: string; badge?: string; badgeVariant?: "default" | "secondary" | "outline" | "ghost" }) {
    return (
        <div className="flex items-center justify-between gap-3 mb-4">
            <CardTitle className="text-base font-semibold">{title}</CardTitle>
            {badge && <Badge variant={badgeVariant}>{badge}</Badge>}
        </div>
    );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="flex flex-col gap-1 py-3 border-b border-border-subtle/50 last:border-0">
            <dt className="text-xs font-medium text-text-secondary uppercase tracking-wide">{label}</dt>
            <dd className="text-sm text-text-primary">{children}</dd>
        </div>
    );
}

function ChatCTA({ message }: { message: string }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    return (
        <div className="flex flex-col gap-3 p-4 rounded-lg bg-surface-elevated/60 border border-border-soft">
            <p className="text-sm text-text-secondary">{message}</p>
            <Link
                href="/command"
                className="inline-flex items-center self-start gap-1.5 rounded-md bg-magenta px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-magenta-hover"
            >
                {t("profileOpenRicoChat")}
                <span aria-hidden="true">→</span>
            </Link>
        </div>
    );
}

function InlineEditLink({ prompt, label = "Edit" }: { prompt: string; label?: string }) {
    return (
        <Link
            href={`/command?prompt=${encodeURIComponent(prompt)}`}
            className="ml-2 text-xs text-magenta hover:text-magenta-hover transition-colors underline underline-offset-2"
        >
            {label}
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
            <span className="inline-flex items-center gap-2">
                <span className="text-text-primary">{displayValue}</span>
                <button
                    type="button"
                    aria-label={`${t("edit")} ${t("name").toLowerCase()}`}
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="text-xs text-magenta hover:text-magenta-hover transition-colors underline underline-offset-2"
                >
                    {t("edit")}
                </button>
            </span>
        );
    }

    return (
        <form className="mt-2 flex max-w-sm flex-col gap-2" onSubmit={handleSave}>
            <label htmlFor="profile-name" className="sr-only">
                {t("name")}
            </label>
            <input
                id="profile-name"
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                className="w-full rounded-md border border-border-soft bg-surface px-3 py-2 text-sm text-text-primary outline-none transition focus:border-magenta focus:ring-1 focus:ring-magenta/20"
                placeholder={t("profileEnterName")}
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-md bg-magenta px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-magenta-hover disabled:opacity-60"
                >
                    {saving ? t("profileSaving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-md border border-border-soft px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-border-medium hover:text-text-primary disabled:opacity-60"
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
                <span className="text-text-primary">{displayValue}</span>
                <button
                    type="button"
                    aria-label={`${t("edit")} ${label}`}
                    onClick={() => {
                        setDraft(value ?? "");
                        setError(null);
                        setEditing(true);
                    }}
                    className="ms-2 text-[11px] text-rico-purple underline underline-offset-2 transition-colors hover:text-[#c4b5fd]"
                >
                    {t("edit")}
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
                className="w-full rounded-md border border-border-soft bg-surface px-3 py-2 text-sm text-text-primary outline-none transition focus:border-magenta focus:ring-1 focus:ring-magenta/20"
                placeholder={placeholder}
                disabled={saving}
            />
            {error && <p className="text-xs text-rico-red" role="alert">{error}</p>}
            <div className="flex items-center gap-2">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-md bg-magenta px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-magenta-hover disabled:opacity-60"
                >
                    {saving ? t("profileSaving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="rounded-md border border-border-soft px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-border-medium hover:text-text-primary disabled:opacity-60"
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
        <div className="flex flex-col gap-6 max-w-3xl">
            {/* Identity */}
            <Card>
                <CardHeader className="pb-2">
                    <SectionHeader
                        title={t("profileIdentity")}
                        badge={t("profileBadgeSynced")}
                        badgeVariant="default"
                    />
                </CardHeader>
                <CardContent>
                    <dl className="flex flex-col">
                        <FieldRow label={t("name")}>
                            <EditableNameField value={profile.name} onSave={onSaveName} />
                        </FieldRow>
                        <FieldRow label={t("email")}>
                            <span className="font-medium">{profile.email ?? "—"}</span>
                        </FieldRow>
                    </dl>
                    <Separator className="my-4" />
                    <dl className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                        <FieldRow label={t("profilePhone")}>
                            <EditableTextField
                                value={profile.phone}
                                onSave={onSavePhone}
                                placeholder={t("profileEnterPhone")}
                                label="phone"
                            />
                        </FieldRow>
                        <FieldRow label={t("telegram")}>
                            <EditableTextField
                                value={profile.telegram_username}
                                onSave={onSaveTelegram}
                                placeholder={t("profileEnterTelegram")}
                                label="telegram"
                            />
                        </FieldRow>
                        <FieldRow label={t("profileLinkedin")}>
                            <EditableTextField
                                value={profile.linkedin_url}
                                onSave={onSaveLinkedin}
                                placeholder={t("profileEnterLinkedin")}
                                label="linkedin"
                            />
                        </FieldRow>
                        <FieldRow label={t("profileVisa")}>
                            <EditableTextField
                                value={profile.visa_status}
                                onSave={onSaveVisa}
                                placeholder={t("profileEnterVisa")}
                                label="visa"
                            />
                        </FieldRow>
                        <FieldRow label={t("profileNotice")}>
                            <EditableTextField
                                value={profile.notice_period}
                                onSave={onSaveNotice}
                                placeholder={t("profileEnterNotice")}
                                label="notice"
                            />
                        </FieldRow>
                    </dl>
                    <Separator className="my-4" />
                    <dl className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                        <FieldRow label={t("profileCurrentCompany")}>
                            <EditableTextField
                                value={profile.current_company}
                                onSave={onSaveCurrentCompany}
                                placeholder={t("profileEnterCurrentCompany")}
                                label="current-company"
                            />
                        </FieldRow>
                        <FieldRow label={t("profileCurrentRole")}>
                            <EditableTextField
                                value={profile.current_role}
                                onSave={onSaveCurrentRole}
                                placeholder={t("profileEnterCurrentRole")}
                                label="current-role"
                            />
                        </FieldRow>
                    </dl>
                </CardContent>
            </Card>

            {/* Job Preferences */}
            <Card>
                <CardHeader className="pb-2">
                    <SectionHeader
                        title={t("profileJobPreferences")}
                        badge={hasJobPrefs ? t("profileBadgeSynced") : t("profileBadgePending")}
                        badgeVariant={hasJobPrefs ? "default" : "secondary"}
                    />
                </CardHeader>
                <CardContent>
                    {hasJobPrefs ? (
                        <dl className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                            <FieldRow label={t("profileTargetRoles")}>
                                <EditableTextField
                                    value={profile.target_roles?.join(', ') || null}
                                    onSave={onSaveTargetRoles}
                                    placeholder={t("profileEnterTargetRoles")}
                                    label="target-roles"
                                />
                            </FieldRow>
                            <FieldRow label={t("profileCities")}>
                                <EditableTextField
                                    value={profile.preferred_cities?.join(', ') || null}
                                    onSave={onSaveCities}
                                    placeholder={t("profileEnterCities")}
                                    label="cities"
                                />
                            </FieldRow>
                            <FieldRow label={t("profileSalaryTarget")}>
                                <EditableTextField
                                    value={profile.salary_expectation_aed != null ? String(profile.salary_expectation_aed) : null}
                                    onSave={onSaveSalaryTarget}
                                    placeholder={t("profileEnterSalaryTarget")}
                                    label="salary-target"
                                />
                            </FieldRow>
                            <FieldRow label={t("profileMinimumSalary")}>
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
                            </FieldRow>
                            <FieldRow label={t("profileExperience")}>
                                <EditableTextField
                                    value={profile.years_experience != null ? String(profile.years_experience) : null}
                                    onSave={onSaveExperience}
                                    placeholder={t("profileEnterExperience")}
                                    label="experience"
                                />
                            </FieldRow>
                        </dl>
                    ) : (
                        <ChatCTA message={t("profileJobPrefsCTA")} />
                    )}
                </CardContent>
            </Card>

            {/* Skills */}
            <Card>
                <CardHeader className="pb-2">
                    <SectionHeader
                        title={t("profileSkills")}
                        badge={hasSkills ? t("profileBadgeSynced") : t("profileBadgePending")}
                        badgeVariant={hasSkills ? "default" : "secondary"}
                    />
                </CardHeader>
                <CardContent>
                    {hasSkills ? (
                        <FieldRow label={t("profileSkills")}>
                            <EditableTextField
                                value={profile.skills?.join(', ') || null}
                                onSave={onSaveSkills}
                                placeholder={t("profileEnterSkills")}
                                label="skills"
                            />
                        </FieldRow>
                    ) : (
                        <ChatCTA message={t("profileSkillsCTA")} />
                    )}
                </CardContent>
            </Card>
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
            <div className="w-full max-w-3xl py-2" dir={language === "ar" ? "rtl" : "ltr"}>
                {loading && <LoadingState variant="card" message={t("profileLoading")} />}

                {!loading && error && (
                    <Card className="p-6">
                        <ErrorState
                            variant={error === "auth" ? "auth" : "network"}
                            title={error === "auth" ? t("profileAuthRequired") : t("profileConnectionFailed")}
                            message={error === "auth" ? t("profileAuthRequiredMsg") : t("profileConnectionFailedMsg")}
                            onRetry={handleRetry}
                        />
                    </Card>
                )}

                {!loading && !error && profile && !profile.profile_exists && (
                    <div className="flex flex-col gap-4 max-w-3xl">
                        <EmptyState
                            title={t("profileNoProfileTitle")}
                            description={t("profileNoProfileDesc")}
                            actionLabel={t("profileStartSetup")}
                            actionHref="/command"
                        />

                        <Card>
                            <CardContent className="p-5">
                                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-secondary">
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
                                            <span className="mt-0.5 text-magenta">•</span>
                                            {item}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
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
