"use client";

/**
 * ProfileAtelier — read-only "portrait" view of the authenticated profile.
 *
 * Uses the shared Atelier typography and the active application theme while
 * rendering only real ProfileResponse fields. No fabricated education,
 * experience-timeline, or language sections. The portrait is the default
 * /profile view; an explicit Edit button switches to the existing production
 * inline editor.
 */

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { WORKSPACE_THEME, type WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import { type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";

const SERIF = ATELIER_FONT.serif;

function ThemedPlate({
    children,
    className = "",
    palette,
}: {
    children: React.ReactNode;
    className?: string;
    palette: WorkspacePalette;
}) {
    const tick = "absolute h-2 w-2 pointer-events-none";
    const border = `1px solid ${palette.hair}`;

    return (
        <div
            className={`relative rounded-[4px] ${className}`}
            style={{ background: palette.panel, border: `1px solid ${palette.hair}` }}
        >
            <span className={`${tick} left-1.5 top-1.5`} style={{ borderLeft: border, borderTop: border }} aria-hidden="true" />
            <span className={`${tick} right-1.5 top-1.5`} style={{ borderRight: border, borderTop: border }} aria-hidden="true" />
            <span className={`${tick} bottom-1.5 left-1.5`} style={{ borderBottom: border, borderLeft: border }} aria-hidden="true" />
            <span className={`${tick} bottom-1.5 right-1.5`} style={{ borderBottom: border, borderRight: border }} aria-hidden="true" />
            {children}
        </div>
    );
}

function SectionTitle({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
    return (
        <Mono className="mb-3 block" style={{ color: palette.ink55 }}>
            {children}
        </Mono>
    );
}

function Field({
    label,
    children,
    palette,
    isAr,
}: {
    label: string;
    children: React.ReactNode;
    palette: WorkspacePalette;
    isAr: boolean;
}) {
    return (
        <div className="min-w-0">
            <dt
                className={`text-[11px] font-medium uppercase ${isAr ? "tracking-normal" : "tracking-wider"}`}
                style={{ color: palette.ink55 }}
            >
                {label}
            </dt>
            <dd className="mt-1 break-words text-sm" style={{ color: palette.ink }}>
                {children}
            </dd>
        </div>
    );
}

function TagPill({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
    return (
        <span
            className="inline-block rounded-[3px] px-2 py-0.5 text-xs"
            style={{ background: palette.inset, color: palette.ink70 }}
        >
            {children}
        </span>
    );
}

function EmptyValue({ palette }: { palette: WorkspacePalette }) {
    return <span style={{ color: palette.ink40 }}>—</span>;
}

function formatAed(value: number | null | undefined, language: "en" | "ar") {
    if (value == null) return null;
    const locale = language === "ar" ? "ar-AE" : "en-AE";
    const unit = language === "ar" ? "د.إ" : "AED";
    return `${new Intl.NumberFormat(locale).format(value)} ${unit}`;
}

function clampPct(value: number | null | undefined): number {
    if (value == null) return 0;
    const n = value > 1 ? value : value * 100;
    return Math.max(0, Math.min(100, Math.round(n)));
}

function CompletenessBar({ profile, palette }: { profile: ProfileResponse; palette: WorkspacePalette }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const pct = clampPct(profile.completeness_score);

    return (
        <ThemedPlate className="p-5" palette={palette}>
            <div className="flex items-center justify-between gap-3">
                <SectionTitle palette={palette}>{t("profileCompleteness")}</SectionTitle>
                <span style={{ fontFamily: SERIF, fontSize: "1.75rem", lineHeight: 1, color: palette.ink }}>
                    {pct}%
                </span>
            </div>
            <div
                className="mt-3 h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: palette.track }}
                role="progressbar"
                aria-label={t("profileCompleteness")}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={pct}
            >
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: palette.red }} />
            </div>
            {pct === 100 && (
                <p className="mt-3 text-xs" style={{ color: palette.red }}>
                    {t("profileCompletenessTip")}
                </p>
            )}
        </ThemedPlate>
    );
}

export function ProfileAtelier({
    profile,
    onEdit,
}: {
    profile: ProfileResponse;
    onEdit: () => void;
}) {
    const { language } = useLanguage();
    const { resolvedTheme } = useTheme();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const palette = WORKSPACE_THEME[resolvedTheme];

    const displayName = profile.name?.trim() || t("profileNoProfileTitle");
    const subtitle = [profile.current_role, profile.current_company]
        .filter(Boolean)
        .join(" · ") || null;

    const hasTargetRoles = (profile.target_roles?.length ?? 0) > 0;
    const hasCities = (profile.preferred_cities?.length ?? 0) > 0;
    const hasSkills = (profile.skills?.length ?? 0) > 0;

    const fieldProps = { palette, isAr };

    return (
        <div
            className="profile-atelier-portrait space-y-4"
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            style={{ color: palette.ink }}
        >
            <style dangerouslySetInnerHTML={{ __html: `
                .profile-atelier-portrait .profile-atelier-action {
                    transition: border-color .15s ease, color .15s ease, transform .15s ease;
                }
                .profile-atelier-portrait .profile-atelier-action:hover {
                    border-color: ${palette.red} !important;
                    color: ${palette.red} !important;
                }
                .profile-atelier-portrait .profile-atelier-action:focus-visible {
                    outline: 2px solid ${palette.red};
                    outline-offset: 3px;
                }
                .profile-atelier-portrait [role="alert"] {
                    border-color: ${palette.hair};
                    background: ${palette.inset};
                }
                .profile-atelier-portrait [role="alert"] p {
                    color: ${palette.ink};
                }
                .profile-atelier-portrait [role="alert"] li p + p {
                    color: ${palette.ink70};
                }
            ` }} />

            <GuardrailWarnings warnings={profile.warnings} language={language} />

            <ThemedPlate className="p-5 sm:p-6" palette={palette}>
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <Mono style={{ color: palette.ink55 }}>{t("profileTitle")}</Mono>
                        <h1
                            className={`mt-2 text-[2.2rem] font-normal sm:text-[2.8rem] ${isAr ? "leading-[1.15]" : "leading-[0.98]"}`}
                            style={{ fontFamily: SERIF, color: palette.ink }}
                        >
                            {displayName}
                        </h1>
                        {subtitle && (
                            <p className="mt-2 text-[1rem]" style={{ color: palette.ink70 }}>
                                {subtitle}
                            </p>
                        )}
                    </div>
                    <button
                        type="button"
                        onClick={onEdit}
                        aria-label={isAr ? "تعديل الملف الشخصي" : "Edit profile"}
                        className="profile-atelier-action shrink-0 rounded-[4px] px-4 py-2 text-sm font-semibold"
                        style={{
                            color: palette.ink,
                            background: palette.panel,
                            border: `1px solid ${palette.hair}`,
                            cursor: "pointer",
                        }}
                    >
                        {t("edit")}
                    </button>
                </div>
            </ThemedPlate>

            <CompletenessBar profile={profile} palette={palette} />

            <ThemedPlate className="p-5 sm:p-6" palette={palette}>
                <SectionTitle palette={palette}>{t("profileIdentity")}</SectionTitle>
                <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <Field label={t("name")} {...fieldProps}>{profile.name?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("email")} {...fieldProps}>{profile.email ?? <EmptyValue palette={palette} />}</Field>
                    <Field label={t("profilePhone")} {...fieldProps}>{profile.phone?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("telegram")} {...fieldProps}>{profile.telegram_username?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("profileCurrentRole")} {...fieldProps}>{profile.current_role?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("profileCurrentCompany")} {...fieldProps}>{profile.current_company?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("profileLinkedin")} {...fieldProps}>
                        {profile.linkedin_url?.trim() ? (
                            <Link
                                href={profile.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="break-all underline underline-offset-2"
                                style={{ color: palette.red }}
                            >
                                {profile.linkedin_url}
                            </Link>
                        ) : (
                            <EmptyValue palette={palette} />
                        )}
                    </Field>
                    <Field label={t("profileVisa")} {...fieldProps}>{profile.visa_status?.trim() || <EmptyValue palette={palette} />}</Field>
                    <Field label={t("profileNotice")} {...fieldProps}>{profile.notice_period?.trim() || <EmptyValue palette={palette} />}</Field>
                </dl>
            </ThemedPlate>

            <ThemedPlate className="p-5 sm:p-6" palette={palette}>
                <SectionTitle palette={palette}>{t("profileJobPreferences")}</SectionTitle>
                <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <Field label={t("profileTargetRoles")} {...fieldProps}>
                        {hasTargetRoles ? (
                            <div className="flex flex-wrap gap-1.5">
                                {profile.target_roles!.map((role) => (
                                    <TagPill key={role} palette={palette}>{role}</TagPill>
                                ))}
                            </div>
                        ) : (
                            <EmptyValue palette={palette} />
                        )}
                    </Field>
                    <Field label={t("profileCities")} {...fieldProps}>
                        {hasCities ? (
                            <div className="flex flex-wrap gap-1.5">
                                {profile.preferred_cities!.map((city) => (
                                    <TagPill key={city} palette={palette}>{city}</TagPill>
                                ))}
                            </div>
                        ) : (
                            <EmptyValue palette={palette} />
                        )}
                    </Field>
                    <Field label={t("profileSalaryTarget")} {...fieldProps}>
                        {formatAed(profile.salary_expectation_aed, language) || <EmptyValue palette={palette} />}
                    </Field>
                    <Field label={t("profileMinimumSalary")} {...fieldProps}>
                        {formatAed(profile.minimum_salary_aed, language) || <EmptyValue palette={palette} />}
                    </Field>
                    <Field label={t("profileExperience")} {...fieldProps}>
                        {profile.years_experience != null ? (
                            <span>{new Intl.NumberFormat(isAr ? "ar-AE" : "en-AE").format(Math.round(profile.years_experience))}</span>
                        ) : (
                            <EmptyValue palette={palette} />
                        )}
                    </Field>
                </dl>
            </ThemedPlate>

            <ThemedPlate className="p-5 sm:p-6" palette={palette}>
                <SectionTitle palette={palette}>{t("profileSkills")}</SectionTitle>
                {hasSkills ? (
                    <div className="flex flex-wrap gap-1.5">
                        {profile.skills!.map((skill) => (
                            <TagPill key={skill} palette={palette}>{skill}</TagPill>
                        ))}
                    </div>
                ) : (
                    <EmptyValue palette={palette} />
                )}
            </ThemedPlate>
        </div>
    );
}
