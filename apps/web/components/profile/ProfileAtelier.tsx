"use client";

/**
 * ProfileAtelier — read-only "portrait" view of the authenticated profile.
 *
 * Uses the shared Atelier prospectus tokens (PR 0) and real ProfileResponse
 * fields only. No fabricated education, experience-timeline, or language
 * sections. The portrait is the default /profile view; an explicit Edit button
 * switches the page into the existing production inline editor.
 */

import { Mono, Plate } from "@/components/atelier-kit/primitives";
import { ATELIER, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { useLanguage } from "@/contexts/LanguageContext";
import { type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";

const SERIF = ATELIER_FONT.serif;

function SectionTitle({ children }: { children: React.ReactNode }) {
    return (
        <Mono className="block mb-3" style={{ color: ATELIER.ink55 }}>
            {children}
        </Mono>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="min-w-0">
            <dt className="text-[11px] font-medium uppercase tracking-wider" style={{ color: ATELIER.ink55 }}>
                {label}
            </dt>
            <dd className="mt-1 text-sm break-words" style={{ color: ATELIER.ink }}>
                {children}
            </dd>
        </div>
    );
}

function TagPill({ children }: { children: React.ReactNode }) {
    return (
        <span
            className="inline-block rounded-[3px] px-2 py-0.5 text-xs"
            style={{ background: ATELIER.inset, color: ATELIER.ink70 }}
        >
            {children}
        </span>
    );
}

function EmptyValue() {
    return <span style={{ color: ATELIER.ink40 }}>—</span>;
}

function formatAed(value: number | null | undefined) {
    if (value == null) return null;
    return `${value.toLocaleString("en-US")} AED`;
}

function clampPct(value: number | null | undefined): number {
    if (value == null) return 0;
    const n = value > 1 ? value : value * 100;
    return Math.max(0, Math.min(100, Math.round(n)));
}

function CompletenessBar({ profile }: { profile: ProfileResponse }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const pct = clampPct(profile.completeness_score);

    return (
        <Plate className="p-5">
            <div className="flex items-center justify-between gap-3">
                <SectionTitle>{t("profileCompleteness")}</SectionTitle>
                <span style={{ fontFamily: SERIF, fontSize: "1.75rem", lineHeight: 1, color: ATELIER.ink }}>
                    {pct}%
                </span>
            </div>
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full" style={{ background: ATELIER.inset }}>
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: ATELIER.red }} />
            </div>
            {pct === 100 && (
                <p className="mt-3 text-xs" style={{ color: ATELIER.red }}>
                    {t("profileCompletenessTip")}
                </p>
            )}
        </Plate>
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
    const t = useTranslation(language);
    const isAr = language === "ar";

    const displayName = profile.name?.trim() || t("profileNoProfileTitle");
    const subtitle = [profile.current_role, profile.current_company]
        .filter(Boolean)
        .join(" · ") || null;

    const hasTargetRoles = (profile.target_roles?.length ?? 0) > 0;
    const hasCities = (profile.preferred_cities?.length ?? 0) > 0;
    const hasSkills = (profile.skills?.length ?? 0) > 0;

    return (
        <div
            className="space-y-4"
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
        >
            <GuardrailWarnings warnings={profile.warnings} language={language} />

            {/* Header */}
            <Plate className="p-5 sm:p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <Mono style={{ color: ATELIER.ink55 }}>{t("profileTitle")}</Mono>
                        <h1
                            className="mt-2 text-[2.2rem] sm:text-[2.8rem] leading-[0.98] font-normal"
                            style={{ fontFamily: SERIF, color: ATELIER.ink }}
                        >
                            {displayName}
                        </h1>
                        {subtitle && (
                            <p className="mt-2 text-[1rem]" style={{ color: ATELIER.ink70 }}>
                                {subtitle}
                            </p>
                        )}
                    </div>
                    <button
                        type="button"
                        onClick={onEdit}
                        aria-label="Edit profile"
                        className="wsx-action shrink-0 rounded-[4px] px-4 py-2 text-sm font-semibold"
                        style={{
                            color: ATELIER.ink,
                            background: ATELIER.panel,
                            border: `1px solid ${ATELIER.hair}`,
                            cursor: "pointer",
                        }}
                    >
                        {t("edit")}
                    </button>
                </div>
            </Plate>

            <CompletenessBar profile={profile} />

            {/* Identity */}
            <Plate className="p-5 sm:p-6">
                <SectionTitle>{t("profileIdentity")}</SectionTitle>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <Field label={t("name")}>{profile.name?.trim() || <EmptyValue />}</Field>
                    <Field label={t("email")}>{profile.email ?? <EmptyValue />}</Field>
                    <Field label={t("profilePhone")}>{profile.phone?.trim() || <EmptyValue />}</Field>
                    <Field label={t("telegram")}>{profile.telegram_username?.trim() || <EmptyValue />}</Field>
                    <Field label={t("profileCurrentRole")}>{profile.current_role?.trim() || <EmptyValue />}</Field>
                    <Field label={t("profileCurrentCompany")}>{profile.current_company?.trim() || <EmptyValue />}</Field>
                    <Field label={t("profileLinkedin")}>
                        {profile.linkedin_url?.trim() ? (
                            <Link
                                href={profile.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline underline-offset-2 break-all"
                                style={{ color: ATELIER.red }}
                            >
                                {profile.linkedin_url}
                            </Link>
                        ) : (
                            <EmptyValue />
                        )}
                    </Field>
                    <Field label={t("profileVisa")}>{profile.visa_status?.trim() || <EmptyValue />}</Field>
                    <Field label={t("profileNotice")}>{profile.notice_period?.trim() || <EmptyValue />}</Field>
                </dl>
            </Plate>

            {/* Job preferences */}
            <Plate className="p-5 sm:p-6">
                <SectionTitle>{t("profileJobPreferences")}</SectionTitle>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <Field label={t("profileTargetRoles")}>
                        {hasTargetRoles ? (
                            <div className="flex flex-wrap gap-1.5">
                                {profile.target_roles!.map((role) => (
                                    <TagPill key={role}>{role}</TagPill>
                                ))}
                            </div>
                        ) : (
                            <EmptyValue />
                        )}
                    </Field>
                    <Field label={t("profileCities")}>
                        {hasCities ? (
                            <div className="flex flex-wrap gap-1.5">
                                {profile.preferred_cities!.map((city) => (
                                    <TagPill key={city}>{city}</TagPill>
                                ))}
                            </div>
                        ) : (
                            <EmptyValue />
                        )}
                    </Field>
                    <Field label={t("profileSalaryTarget")}>{formatAed(profile.salary_expectation_aed) || <EmptyValue />}</Field>
                    <Field label={t("profileMinimumSalary")}>{formatAed(profile.minimum_salary_aed) || <EmptyValue />}</Field>
                    <Field label={t("profileExperience")}>
                        {profile.years_experience != null ? (
                            <span>{Math.round(profile.years_experience)}</span>
                        ) : (
                            <EmptyValue />
                        )}
                    </Field>
                </dl>
            </Plate>

            {/* Skills */}
            <Plate className="p-5 sm:p-6">
                <SectionTitle>{t("profileSkills")}</SectionTitle>
                {hasSkills ? (
                    <div className="flex flex-wrap gap-1.5">
                        {profile.skills!.map((skill) => (
                            <TagPill key={skill}>{skill}</TagPill>
                        ))}
                    </div>
                ) : (
                    <EmptyValue />
                )}
            </Plate>
        </div>
    );
}
