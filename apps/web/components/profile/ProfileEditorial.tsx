"use client";

/**
 * ProfileEditorial — the /profile experience rebuilt on the owner-supplied
 * "Rico Profile" editorial design (a4666713-Rico_Profile.dc.html, 2026-07-17):
 * hero identity plate + profile-strength meter, a sticky numbered section rail,
 * and numbered editorial section cards with a global unsaved-changes save bar.
 *
 * Every rendered fact is wired to the real system — no sample data ships:
 *   01 About        → name / phone / telegram_username / linkedin_url
 *   02 Career       → current_role / current_company / years_experience
 *   03 Skills       → skills[]                (chip editor)
 *   04 Documents    → /api/v1/user/files list + upload-cv / set-primary / delete
 *   05 Preferences  → target_roles (max 4) / preferred_cities (UAE) / salaries /
 *                     visa_status / notice_period
 *   06 Integrations → GmailConnectionCard (real connector) + Telegram status
 *   07 Security     → verified email (login requires verification) + password
 *                     reset via the existing /forgot-password flow
 *   08 Billing      → GET /api/v1/subscription/me (plan name/price from the
 *                     API) with "Manage plan" → /subscription
 *
 * Design sections with no backend capability (education, certifications,
 * avatar upload, 2FA, card-on-file, privacy toggles, delete account) are
 * deliberately omitted rather than faked.
 *
 * All field edits accumulate into ONE dirty draft; Save issues a single
 * PATCH /api/v1/rico/profile containing only the changed fields, then the
 * parent refreshes the profile. Colors come from the WorkspaceShell island
 * palette so light/dark and EN/AR (RTL via logical properties) both work.
 */

import { GmailConnectionCard } from "@/components/settings/GmailConnectionCard";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { WORKSPACE_THEME, useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    deleteUserFile,
    getMySubscription,
    listUserFiles,
    setPrimaryFile,
    updateProfile,
    uploadCV,
    type ProfileResponse,
    type ProfileUpdatePayload,
    type SubscriptionMeResponse,
    type UserDocument,
} from "@/lib/api";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { Check, Mail, MapPin, Phone, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const SERIF = ATELIER_FONT.serif;
const MONO = ATELIER_FONT.mono;

export const MAX_TARGET_ROLES = 4;

const UAE_CITIES = new Set([
    "abu dhabi", "dubai", "sharjah", "ajman", "ras al khaimah",
    "fujairah", "al ain", "umm al quwain",
    "أبوظبي", "أبو ظبي", "دبي", "الشارقة", "عجمان",
    "رأس الخيمة", "الفجيرة", "العين", "أم القيوين",
]);

function isUAECity(city: string): boolean {
    return UAE_CITIES.has(city.toLowerCase().trim()) || UAE_CITIES.has(city.trim());
}

function hexToRgba(hex: string, alpha: number): string {
    const h = hex.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

function initialsOf(name: string | null | undefined): string {
    const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "R";
    return parts.slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
}

function clampPct(value: number | null | undefined): number {
    if (value == null) return 0;
    const n = value > 1 ? value : value * 100;
    return Math.max(0, Math.min(100, Math.round(n)));
}

function formatBytes(size: number): string {
    if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(size / 1024))} KB`;
}

function extOf(filename: string): string {
    const dot = filename.lastIndexOf(".");
    return dot >= 0 ? filename.slice(dot + 1).toUpperCase().slice(0, 4) : "FILE";
}

/* ── draft model ────────────────────────────────────────────────────────────── */

interface ProfileDraft {
    name: string;
    phone: string;
    telegram_username: string;
    linkedin_url: string;
    current_role: string;
    current_company: string;
    years_experience: string;
    salary_expectation_aed: string;
    minimum_salary_aed: string;
    visa_status: string;
    notice_period: string;
    target_roles: string[];
    preferred_cities: string[];
    skills: string[];
}

function toDraft(p: ProfileResponse): ProfileDraft {
    return {
        name: p.name ?? "",
        phone: p.phone ?? "",
        telegram_username: p.telegram_username ?? "",
        linkedin_url: p.linkedin_url ?? "",
        current_role: p.current_role ?? "",
        current_company: p.current_company ?? "",
        years_experience: p.years_experience != null ? String(Math.round(p.years_experience)) : "",
        salary_expectation_aed: p.salary_expectation_aed != null ? String(p.salary_expectation_aed) : "",
        minimum_salary_aed: p.minimum_salary_aed != null ? String(p.minimum_salary_aed) : "",
        visa_status: p.visa_status ?? "",
        notice_period: p.notice_period ?? "",
        target_roles: p.target_roles ?? [],
        preferred_cities: p.preferred_cities ?? [],
        skills: p.skills ?? [],
    };
}

const TEXT_FIELDS = [
    "name", "phone", "telegram_username", "linkedin_url",
    "current_role", "current_company", "visa_status", "notice_period",
] as const;
const NUMBER_FIELDS = ["years_experience", "salary_expectation_aed", "minimum_salary_aed"] as const;
const LIST_FIELDS = ["target_roles", "preferred_cities", "skills"] as const;

/* ── route-exit dirty-state protection (Phase 4) ────────────────────────────
   The click interceptor + beforeunload (from #1161) cover link navigation and
   refresh/close, but browser Back/forward that EXITS /profile cannot be
   blocked safely in the Next 14 App Router without a history trap that would
   break in-profile section back/forward. Instead of an unsafe trap, the dirty
   draft is mirrored to per-tab sessionStorage: ANY route exit — Back included —
   can no longer destroy unsaved edits, because returning to /profile restores
   the draft (and the unsaved-changes bar). The mirror is cleared the moment
   the draft is clean (save/discard) and is never restored across accounts. */

const DRAFT_STORAGE_KEY = "rico-profile-draft";

function sanitizeStoredDraft(value: unknown): Partial<ProfileDraft> | null {
    if (!value || typeof value !== "object") return null;
    const raw = value as Record<string, unknown>;
    const out: Partial<ProfileDraft> = {};
    for (const k of [...TEXT_FIELDS, ...NUMBER_FIELDS]) {
        if (typeof raw[k] === "string") out[k] = raw[k] as string;
    }
    for (const k of LIST_FIELDS) {
        const v = raw[k];
        if (Array.isArray(v) && v.every((x) => typeof x === "string")) out[k] = v as string[];
    }
    return Object.keys(out).length > 0 ? out : null;
}

/** Restore a same-account stored draft that still differs from the loaded
 *  profile; anything else (missing, foreign account, corrupt, or already
 *  clean) yields null and a clean start. */
export function restoreStoredDraft(profile: ProfileResponse): ProfileDraft | null {
    try {
        if (typeof window === "undefined") return null;
        const raw = window.sessionStorage.getItem(DRAFT_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as { email?: unknown; draft?: unknown };
        if (parsed.email !== profile.email) {
            // A draft from another account must never surface here.
            window.sessionStorage.removeItem(DRAFT_STORAGE_KEY);
            return null;
        }
        const partial = sanitizeStoredDraft(parsed.draft);
        if (!partial) return null;
        const restored = { ...toDraft(profile), ...partial };
        return changedKeys(profile, restored).length > 0 ? restored : null;
    } catch {
        return null; // storage unavailable/corrupt — protection degrades gracefully
    }
}

type DraftKey = keyof ProfileDraft;

function listsEqual(a: string[], b: string[]): boolean {
    return a.length === b.length && a.every((v, i) => v === b[i]);
}

/** Fields whose draft value differs from the loaded profile. */
export function changedKeys(profile: ProfileResponse, draft: ProfileDraft): DraftKey[] {
    const base = toDraft(profile);
    const keys: DraftKey[] = [];
    for (const k of TEXT_FIELDS) if (draft[k] !== base[k]) keys.push(k);
    for (const k of NUMBER_FIELDS) if (draft[k].trim() !== base[k]) keys.push(k);
    for (const k of LIST_FIELDS) if (!listsEqual(draft[k], base[k])) keys.push(k);
    return keys;
}

/**
 * Validate the changed fields and build the minimal PATCH payload.
 * Returns per-field error translation keys when invalid.
 */
export function buildPayload(
    profile: ProfileResponse,
    draft: ProfileDraft,
): { payload: ProfileUpdatePayload; errors: Partial<Record<DraftKey, TranslationKey>> } {
    const errors: Partial<Record<DraftKey, TranslationKey>> = {};
    const payload: ProfileUpdatePayload = {};
    const changed = new Set(changedKeys(profile, draft));

    if (changed.has("name")) {
        if (!draft.name.trim()) errors.name = "profileNameEmpty";
        else payload.name = draft.name.trim();
    }
    for (const k of ["phone", "telegram_username", "linkedin_url", "current_role", "current_company", "visa_status", "notice_period"] as const) {
        if (changed.has(k)) payload[k] = draft[k].trim();
    }
    for (const k of NUMBER_FIELDS) {
        if (!changed.has(k)) continue;
        const raw = draft[k].trim();
        if (raw === "") {
            // Explicit clear: the PATCH API distinguishes an explicit null
            // ("clear this value") from an omitted field ("unchanged").
            payload[k] = null;
            continue;
        }
        const parsed = Number(raw);
        if (!Number.isFinite(parsed) || parsed < 0) {
            errors[k] = k === "years_experience" ? "profileInvalidYears" : "profileInvalidSalary";
        } else {
            payload[k] = parsed;
        }
    }
    if (changed.has("target_roles")) {
        if (draft.target_roles.length > MAX_TARGET_ROLES) errors.target_roles = "profileTooManyRoles";
        else payload.target_roles = draft.target_roles;
    }
    if (changed.has("preferred_cities")) {
        if (draft.preferred_cities.some((c) => !isUAECity(c))) errors.preferred_cities = "profileInvalidCity";
        else payload.preferred_cities = draft.preferred_cities;
    }
    if (changed.has("skills")) payload.skills = draft.skills;

    return { payload, errors };
}

/* ── shared visual atoms ────────────────────────────────────────────────────── */

interface Tone {
    palette: WorkspacePalette;
    isAr: boolean;
    isDark: boolean;
    sunTint: string;
    success: string;
    successTint: string;
    destructive: string;
    warning: string;
    warningTint: string;
    shadow: string;
}

function useTone(): Tone {
    const palette = useWorkspaceTheme();
    const { language } = useLanguage();
    const isDark = palette.bg === WORKSPACE_THEME.dark.bg;
    return {
        palette,
        isAr: language === "ar",
        isDark,
        sunTint: hexToRgba(palette.red, isDark ? 0.16 : 0.1),
        success: isDark ? "#6FBE8F" : "#3C7A52",
        successTint: isDark ? "rgba(111,190,143,0.16)" : "rgba(60,122,82,0.14)",
        destructive: isDark ? "#D6552E" : "#B23A1A",
        warning: isDark ? "#D99C4E" : "#A8702B",
        warningTint: isDark ? "rgba(217,156,78,0.14)" : "rgba(168,112,43,0.12)",
        shadow: isDark
            ? "0 1px 0 rgba(224,137,90,0.05), 0 20px 40px -28px rgba(0,0,0,0.55)"
            : "0 1px 0 rgba(31,27,21,0.03), 0 20px 40px -32px rgba(31,27,21,0.20)",
    };
}

function Eyebrow({ tone, children }: { tone: Tone; children: React.ReactNode }) {
    return (
        <div
            className={tone.isAr ? "" : "uppercase tracking-[0.14em]"}
            style={{ fontFamily: MONO, fontSize: "9.5px", color: tone.palette.ink55 }}
        >
            {children}
        </div>
    );
}

function SectionCard({
    id,
    num,
    eyebrow,
    title,
    help,
    action,
    index,
    tone,
    children,
}: {
    id: string;
    num: string;
    eyebrow: string;
    title: string;
    help?: string;
    action?: React.ReactNode;
    index: number;
    tone: Tone;
    children: React.ReactNode;
}) {
    return (
        <section
            id={`profile-${id}`}
            aria-labelledby={`profile-${id}-title`}
            className="scroll-mt-24 overflow-hidden rounded-[18px] animate-fade-up motion-reduce:animate-none"
            style={{
                border: `1px solid ${tone.palette.hair}`,
                background: tone.palette.panel,
                boxShadow: tone.shadow,
                animationDelay: `${Math.min(index, 6) * 60}ms`,
                animationFillMode: "both",
            }}
        >
            <div
                className="flex items-start justify-between gap-4 px-5 py-5 sm:px-6"
                style={{ borderBottom: `1px solid ${tone.palette.hair}` }}
            >
                <div className="min-w-0">
                    <div className="mb-1"><Eyebrow tone={tone}>{num} · {eyebrow}</Eyebrow></div>
                    <h2
                        id={`profile-${id}-title`}
                        tabIndex={-1}
                        className="m-0 text-[22px] font-medium leading-tight tracking-[-0.01em] outline-none"
                        style={{ fontFamily: SERIF, color: tone.palette.ink }}
                    >
                        {title}
                    </h2>
                    {help && (
                        <p className="mb-0 mt-1.5 text-[13.5px] leading-[1.55]" style={{ color: tone.palette.ink55 }}>
                            {help}
                        </p>
                    )}
                </div>
                {action && <div className="shrink-0">{action}</div>}
            </div>
            <div className="px-5 py-5 sm:px-6">{children}</div>
        </section>
    );
}

function FieldLabel({ tone, htmlFor, children }: { tone: Tone; htmlFor?: string; children: React.ReactNode }) {
    return (
        <label
            htmlFor={htmlFor}
            className={`mb-1.5 block ${tone.isAr ? "" : "uppercase tracking-[0.14em]"}`}
            style={{ fontFamily: MONO, fontSize: "9.5px", color: tone.palette.ink55 }}
        >
            {children}
        </label>
    );
}

function FieldError({ tone, children }: { tone: Tone; children: React.ReactNode }) {
    return (
        <p role="alert" className="mb-0 mt-1.5 text-xs" style={{ color: tone.destructive }}>
            {children}
        </p>
    );
}

function TextInput({
    id,
    tone,
    value,
    onChange,
    placeholder,
    inputMode,
    ltr = false,
}: {
    id: string;
    tone: Tone;
    value: string;
    onChange: (next: string) => void;
    placeholder?: string;
    inputMode?: "numeric" | "decimal";
    /** Force LTR display for phone numbers / URLs inside the RTL layout. */
    ltr?: boolean;
}) {
    return (
        <input
            id={id}
            type="text"
            value={value}
            inputMode={inputMode}
            placeholder={placeholder}
            dir={ltr ? "ltr" : undefined}
            onChange={(e) => onChange(e.target.value)}
            className="profile-ed-input h-10 w-full rounded-[10px] px-3.5 text-sm outline-none transition-colors"
            style={{
                border: `1px solid ${tone.palette.hair}`,
                background: tone.palette.inset,
                color: tone.palette.ink,
            }}
        />
    );
}

/** Chip list editor — chips with ×-remove plus a dashed "+ add" inline input. */
function ChipEditor({
    idBase,
    tone,
    values,
    onChange,
    addLabel,
    hint,
}: {
    idBase: string;
    tone: Tone;
    values: string[];
    onChange: (next: string[]) => void;
    addLabel: string;
    hint: string;
}) {
    const [adding, setAdding] = useState(false);
    const [text, setText] = useState("");

    const commit = () => {
        const trimmed = text.trim();
        if (trimmed && !values.includes(trimmed)) onChange([...values, trimmed]);
        setText("");
    };

    return (
        <div>
            <div className="flex flex-wrap items-center gap-2">
                {values.map((v) => (
                    <span
                        key={v}
                        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px]"
                        style={{ border: `1px solid ${tone.palette.hair}`, background: tone.palette.inset, color: tone.palette.ink }}
                    >
                        {v}
                        <button
                            type="button"
                            aria-label={`${addLabel}: remove ${v}`}
                            onClick={() => onChange(values.filter((x) => x !== v))}
                            className="transition-colors"
                            style={{ fontFamily: MONO, color: tone.palette.ink55, cursor: "pointer" }}
                        >
                            ×
                        </button>
                    </span>
                ))}
                {adding ? (
                    <input
                        id={`${idBase}-add`}
                        autoFocus
                        type="text"
                        value={text}
                        aria-label={addLabel}
                        onChange={(e) => setText(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === ",") {
                                e.preventDefault();
                                commit();
                            } else if (e.key === "Escape") {
                                setText("");
                                setAdding(false);
                            }
                        }}
                        onBlur={() => {
                            commit();
                            setAdding(false);
                        }}
                        className="h-[34px] min-w-[140px] rounded-full px-3 text-[12.5px] outline-none"
                        style={{ border: `1px solid ${tone.palette.red}`, background: tone.palette.inset, color: tone.palette.ink }}
                    />
                ) : (
                    <button
                        type="button"
                        onClick={() => setAdding(true)}
                        className="profile-ed-ghost rounded-full px-3 py-1.5 text-[12.5px] transition-colors"
                        style={{ border: `1px dashed ${tone.palette.hair}`, background: "transparent", color: tone.palette.ink55, cursor: "pointer" }}
                    >
                        + {addLabel}
                    </button>
                )}
            </div>
            {adding && (
                <p className="mb-0 mt-1.5 text-[10.5px]" style={{ fontFamily: MONO, color: tone.palette.ink40 }}>
                    {hint}
                </p>
            )}
        </div>
    );
}

/* ── actionable matching warnings (Profile Phase 4B) ────────────────────────── */

type GuardrailWarningEntry = NonNullable<ProfileResponse["warnings"]>[number];

type WarningSeverityTier = "blocking" | "important" | "recommendation";

const SEVERITY_ORDER: Record<WarningSeverityTier, number> = {
    blocking: 0,
    important: 1,
    recommendation: 2,
};

const SEVERITY_LABEL_KEY: Record<WarningSeverityTier, TranslationKey> = {
    blocking: "profileWarnSevBlocking",
    important: "profileWarnSevImportant",
    recommendation: "profileWarnSevRecommendation",
};

/** Profile-owned editable fields → owning section + stable field anchor.
 *  Keyed by the backend contract's `field` value (stable identifiers — never
 *  DOM text). Anchors are ids on the field containers in the goals section. */
const WARNING_FIELD_TARGETS: Record<string, { section: string; anchor: string; labelKey: TranslationKey }> = {
    target_roles: { section: "goals", anchor: "profile-field-target_roles", labelKey: "profileTargetRoles" },
    preferred_cities: { section: "goals", anchor: "profile-field-preferred_cities", labelKey: "profileCities" },
};

/** Matching fields owned by the Settings page — their fix action opens /settings. */
const SETTINGS_OWNED_FIELDS = new Set(["min_score", "exclude_keywords", "include_keywords", "max_daily_applies"]);

/** Backend is authoritative for severity; anything unknown renders as the
 *  conservative middle tier (mirrors the backend's own fail-safe). */
function normalizeSeverity(value: unknown): WarningSeverityTier {
    return value === "blocking" || value === "recommendation" ? value : "important";
}

/** Stable identity for defer/restore — never index-based, so a re-fetch that
 *  reorders or removes other warnings cannot mis-target a deferral. */
function warningIdentity(w: GuardrailWarningEntry): string {
    return `${w.code ?? ""}|${w.field ?? ""}|${w.message ?? ""}`;
}

function ProfileActionableWarnings({
    warnings,
    tone,
    onFieldAction,
}: {
    warnings: GuardrailWarningEntry[];
    tone: Tone;
    onFieldAction: (section: string, anchor: string, fieldLabel: string) => void;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const palette = tone.palette;
    // Session-scoped "review later" — deferring is NOT resolving: state lives in
    // memory only, so deferred warnings return on the next visit, and a save
    // re-fetch drops entries that were actually fixed.
    const [deferred, setDeferred] = useState<ReadonlySet<string>>(() => new Set<string>());

    const items = useMemo(
        () =>
            warnings
                .filter((w) => typeof w?.message === "string" && w.message.trim())
                .map((w) => ({
                    id: warningIdentity(w),
                    code: w.code ?? "matching_warning",
                    field: w.field ?? "",
                    severity: normalizeSeverity(w.severity),
                    message: language === "ar" && w.message_ar ? w.message_ar : w.message,
                    suggestion: language === "ar" && w.suggestion_ar ? w.suggestion_ar : w.suggestion,
                }))
                .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]),
        [warnings, language],
    );

    if (items.length === 0) return null;

    const visible = items.filter((w) => !deferred.has(w.id));
    const deferredCount = items.length - visible.length;
    const summary =
        visible.length === 1
            ? t("profileWarnSummaryOne")
            : t("profileWarnSummaryMany").replace("{count}", String(visible.length));

    const severityStyle = (severity: WarningSeverityTier) => {
        if (severity === "blocking") {
            return { border: `1px solid ${tone.destructive}`, color: tone.destructive, background: "transparent" };
        }
        if (severity === "important") {
            return { border: `1px solid ${tone.warning}`, color: tone.warning, background: "transparent" };
        }
        return { border: `1px solid ${palette.hair}`, color: palette.ink55, background: "transparent" };
    };

    return (
        <section
            aria-labelledby="profile-warnings-title"
            className="rounded-[14px] p-4 sm:p-5"
            style={{ border: `1px solid ${tone.warning}59`, background: tone.warningTint }}
        >
            {visible.length > 0 && (
                <>
                    <h2
                        id="profile-warnings-title"
                        aria-live="polite"
                        className="m-0 text-[15px] font-semibold leading-snug"
                        style={{ fontFamily: SERIF, color: palette.ink }}
                    >
                        {summary}
                    </h2>
                    <p className="mb-0 mt-1 text-[12.5px]" style={{ color: palette.ink70 }}>
                        {t("profileWarnSummaryHint")}
                    </p>
                    <ul className="m-0 mt-3 flex list-none flex-col gap-3 p-0">
                        {visible.map((item) => {
                            const target = WARNING_FIELD_TARGETS[item.field];
                            const opensSettings = !target && SETTINGS_OWNED_FIELDS.has(item.field);
                            return (
                                <li
                                    key={item.id}
                                    data-warning-code={item.code}
                                    data-warning-severity={item.severity}
                                    className="rounded-[10px] p-3"
                                    style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}
                                >
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span
                                            className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                            style={{ fontFamily: MONO, ...severityStyle(item.severity) }}
                                        >
                                            {t(SEVERITY_LABEL_KEY[item.severity])}
                                        </span>
                                        <p className="m-0 min-w-0 flex-1 text-[13px] font-medium leading-[1.5]" style={{ color: palette.ink }}>
                                            {item.message}
                                        </p>
                                    </div>
                                    {item.suggestion && (
                                        <p className="mb-0 mt-1.5 text-[12.5px] leading-[1.5]" style={{ color: palette.ink70 }}>
                                            {item.suggestion}
                                        </p>
                                    )}
                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                        {target && (
                                            <button
                                                type="button"
                                                className="profile-ed-warn-action rounded-[8px] px-2.5 py-1 text-[12px] font-semibold"
                                                style={{ border: `1px solid ${palette.hair}`, background: "transparent", color: palette.red, cursor: "pointer" }}
                                                onClick={() => onFieldAction(target.section, target.anchor, t(target.labelKey))}
                                            >
                                                {t("profileWarnGoTo").replace("{target}", t(target.labelKey))}
                                            </button>
                                        )}
                                        {opensSettings && (
                                            <Link
                                                href="/settings"
                                                className="profile-ed-warn-action rounded-[8px] px-2.5 py-1 text-[12px] font-semibold"
                                                style={{ border: `1px solid ${palette.hair}`, textDecoration: "none", color: palette.red }}
                                            >
                                                {t("profileWarnOpenSettings")}
                                            </Link>
                                        )}
                                        {item.severity !== "blocking" && (
                                            <button
                                                type="button"
                                                className="profile-ed-warn-action rounded-[8px] px-2.5 py-1 text-[12px]"
                                                style={{ border: `1px solid ${palette.hair}`, background: "transparent", color: palette.ink55, cursor: "pointer" }}
                                                onClick={() => setDeferred((prev) => new Set(prev).add(item.id))}
                                            >
                                                {t("profileWarnReviewLater")}
                                            </button>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                </>
            )}
            {deferredCount > 0 && (
                <div className={`flex flex-wrap items-center gap-2 ${visible.length > 0 ? "mt-3" : ""}`}>
                    <p className="m-0 text-[12px]" style={{ color: palette.ink55 }}>
                        {t("profileWarnDeferredNote").replace("{count}", String(deferredCount))}
                    </p>
                    <button
                        type="button"
                        className="profile-ed-warn-action rounded-[8px] px-2 py-0.5 text-[12px]"
                        style={{ border: `1px solid ${palette.hair}`, background: "transparent", color: palette.ink70, cursor: "pointer" }}
                        onClick={() => setDeferred(new Set<string>())}
                    >
                        {t("profileWarnShowDeferred")}
                    </button>
                </div>
            )}
        </section>
    );
}

/* ── sections config ────────────────────────────────────────────────────────── */

// Canonical, stable section slugs. These are the source of truth for the
// `?section=` URL parameter, the desktop rail, the mobile selector, and the
// render-only-selected switch below. Slugs are user-visible in the URL, so they
// are kept short and stable (do not rename without a redirect).
const RAIL_SECTIONS: { id: string; num: string; labelKey: TranslationKey }[] = [
    { id: "about", num: "01", labelKey: "profileEdAboutTitle" },
    { id: "career", num: "02", labelKey: "profileCareer" },
    { id: "skills", num: "03", labelKey: "profileSkills" },
    { id: "documents", num: "04", labelKey: "profileEdDocsTitle" },
    { id: "goals", num: "05", labelKey: "profileEdPrefsTitle" },
    { id: "integrations", num: "06", labelKey: "profileEdIntegrationsTitle" },
    { id: "security", num: "07", labelKey: "profileEdSecurityTitle" },
    { id: "billing", num: "08", labelKey: "profileEdBillingTitle" },
];

const SECTION_IDS = RAIL_SECTIONS.map((s) => s.id);
const DEFAULT_SECTION = "about";

/**
 * Resolve the section to render from the raw `?section=` value.
 *  - a valid explicit slug always wins (even alongside a Gmail callback);
 *  - otherwise a Gmail OAuth callback (`?gmail=…`) opens Integrations so the
 *    returning user lands on the card that owns that callback;
 *  - anything else (missing / invalid) falls back to `about`.
 */
function resolveSection(raw: string | null, hasGmailCallback: boolean): string {
    if (raw && SECTION_IDS.includes(raw)) return raw;
    if (hasGmailCallback) return "integrations";
    return DEFAULT_SECTION;
}

/* ── main component ─────────────────────────────────────────────────────────── */

export function ProfileEditorial({
    profile,
    refresh,
    notify,
}: {
    profile: ProfileResponse;
    /** Re-fetch the profile after a successful save/upload. */
    refresh: () => Promise<void> | void;
    notify: (message: string, type: "success" | "error") => void;
}) {
    const tone = useTone();
    const { palette, isAr } = tone;
    const { language } = useLanguage();
    const t = useTranslation(language);

    // Seed from a same-account stored draft when one survived a route exit
    // (browser Back included) — otherwise start clean from the loaded profile.
    const [draft, setDraft] = useState<ProfileDraft>(() => restoreStoredDraft(profile) ?? toDraft(profile));
    const [errors, setErrors] = useState<Partial<Record<DraftKey, TranslationKey>>>({});
    const [saving, setSaving] = useState(false);

    /* ── true section navigation (URL-backed) ────────────────────────────────
       The rendered section is derived from `?section=` — not React state — so
       deep links, browser back/forward, and refresh all resolve to the same
       section with no local mirror to fall out of sync. */
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const rawSection = searchParams.get("section");
    const hasGmailCallback = searchParams.has("gmail");
    const activeSection = resolveSection(rawSection, hasGmailCallback);

    // Build a section URL that preserves every unrelated query parameter
    // (Gmail/billing callbacks included) — only `section` changes.
    const sectionHref = useCallback(
        (id: string) => {
            const params = new URLSearchParams(searchParams.toString());
            params.set("section", id);
            return `${pathname}?${params.toString()}`;
        },
        [pathname, searchParams],
    );

    // Canonicalize the URL when the section param is invalid, or when a Gmail
    // callback forced Integrations without an explicit section — with `replace`
    // (no history entry), preserving all other params. A clean `/profile`
    // (missing section, no callback) is left untouched so the URL stays tidy.
    useEffect(() => {
        const needsWrite =
            (rawSection !== null && rawSection !== activeSection) ||
            (rawSection === null && hasGmailCallback && activeSection !== DEFAULT_SECTION);
        if (!needsWrite) return;
        router.replace(sectionHref(activeSection), { scroll: false });
    }, [rawSection, activeSection, hasGmailCallback, router, sectionHref]);

    // After an INTENTIONAL section change, move focus to the section heading so
    // keyboard and screen-reader users land in the new content. Skipped on the
    // initial mount (never steal focus on page load) and when the section value
    // did not actually change (e.g. a canonicalizing replace that keeps it).
    const focusPrimed = useRef(false);
    useEffect(() => {
        if (!focusPrimed.current) {
            focusPrimed.current = true;
            return;
        }
        const heading = document.getElementById(`profile-${activeSection}-title`);
        heading?.focus();
    }, [activeSection]);

    /* ── actionable-warning field navigation (Phase 4B) ──────────────────────
       Selecting a warning jumps to the owning section (same URL-backed push as
       the rail — unrelated params preserved), then focuses and briefly
       highlights the exact field container. Runs AFTER the heading-focus
       effect above, so on a warning-driven jump the final focus target is the
       field, not the section heading. Screen readers get the move announced
       via the polite live region below. */
    const pendingFieldAnchor = useRef<string | null>(null);
    const [fieldFlash, setFieldFlash] = useState<string | null>(null);
    const [fieldNavTick, setFieldNavTick] = useState(0);
    const [fieldNavAnnouncement, setFieldNavAnnouncement] = useState("");

    const goToWarningField = useCallback(
        (section: string, anchor: string, fieldLabel: string) => {
            pendingFieldAnchor.current = anchor;
            if (activeSection !== section) router.push(sectionHref(section));
            setFieldNavTick((n) => n + 1);
            setFieldNavAnnouncement(t("profileWarnNavAnnounce").replace("{target}", fieldLabel));
        },
        [activeSection, router, sectionHref, t],
    );

    useEffect(() => {
        const anchor = pendingFieldAnchor.current;
        if (!anchor) return;
        const el = document.getElementById(anchor);
        if (!el) return; // target section not rendered yet — retried when activeSection updates
        pendingFieldAnchor.current = null;
        el.focus();
        setFieldFlash(anchor);
        const timeoutId = window.setTimeout(() => setFieldFlash(null), 2400);
        return () => window.clearTimeout(timeoutId);
    }, [activeSection, fieldNavTick]);

    // Reset the draft whenever a fresh profile arrives (post-save/upload
    // refresh). Render-time adjustment (React's "state from previous renders"
    // pattern) instead of an effect, so no extra committed render of stale data.
    const [prevProfile, setPrevProfile] = useState(profile);
    if (prevProfile !== profile) {
        setPrevProfile(profile);
        setDraft(toDraft(profile));
        setErrors({});
    }

    const dirty = useMemo(() => changedKeys(profile, draft).length > 0, [profile, draft]);

    // Mirror the dirty draft to per-tab sessionStorage (route-exit protection);
    // remove it the moment the draft is clean again (save success or discard),
    // so no stale draft outlives its resolution. Single effect — no duplicate
    // listeners, nothing global.
    useEffect(() => {
        try {
            if (dirty) {
                window.sessionStorage.setItem(
                    DRAFT_STORAGE_KEY,
                    JSON.stringify({ email: profile.email, draft }),
                );
            } else {
                window.sessionStorage.removeItem(DRAFT_STORAGE_KEY);
            }
        } catch {
            // storage unavailable — beforeunload + click-interceptor still guard
        }
    }, [dirty, draft, profile.email]);

    const set = useCallback(<K extends DraftKey>(key: K, value: ProfileDraft[K]) => {
        setDraft((d) => ({ ...d, [key]: value }));
        setErrors((e) => (e[key] ? { ...e, [key]: undefined } : e));
    }, []);

    const onDiscard = useCallback(() => {
        setDraft(toDraft(profile));
        setErrors({});
    }, [profile]);

    const onSave = useCallback(async () => {
        const { payload, errors: nextErrors } = buildPayload(profile, draft);
        if (Object.values(nextErrors).some(Boolean)) {
            setErrors(nextErrors);
            return;
        }
        if (Object.keys(payload).length === 0) return;
        setSaving(true);
        try {
            await updateProfile(payload);
            notify(t("profileEdSaved"), "success");
            try {
                await refresh();
            } catch {
                notify(t("profileRefreshFailed"), "error");
            }
        } catch (err: unknown) {
            notify(err instanceof Error ? err.message : t("profileCouldNotSave"), "error");
        } finally {
            setSaving(false);
        }
    }, [profile, draft, notify, refresh, t]);

    /* documents */
    const [files, setFiles] = useState<UserDocument[]>([]);
    const [filesLoaded, setFilesLoaded] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
    const [docBusyId, setDocBusyId] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    const loadFiles = useCallback(async () => {
        try {
            const res = await listUserFiles();
            setFiles(res.files);
        } catch {
            // list stays empty; the section still renders with the upload action
        } finally {
            setFilesLoaded(true);
        }
    }, []);

    useEffect(() => {
        // Deferred like the page's loadProfile call: keeps the effect body
        // free of synchronous setState (react-hooks/set-state-in-effect).
        const timeoutId = window.setTimeout(() => {
            void loadFiles();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadFiles]);

    const onUpload = useCallback(
        async (file: File) => {
            setUploading(true);
            try {
                await uploadCV(file);
                notify(t("profileEdUploadDone"), "success");
                await loadFiles();
                // CV parsing can update profile facts (skills, role, years).
                try {
                    await refresh();
                } catch {
                    notify(t("profileRefreshFailed"), "error");
                }
            } catch (err: unknown) {
                notify(err instanceof Error ? err.message : t("profileEdUploadFailed"), "error");
            } finally {
                setUploading(false);
            }
        },
        [loadFiles, notify, refresh, t],
    );

    const onSetPrimary = useCallback(
        async (id: string) => {
            setDocBusyId(id);
            try {
                await setPrimaryFile(id);
                await loadFiles();
            } catch {
                notify(t("profileEdDocActionFailed"), "error");
            } finally {
                setDocBusyId(null);
            }
        },
        [loadFiles, notify, t],
    );

    const onDeleteDoc = useCallback(
        async (id: string) => {
            if (confirmDeleteId !== id) {
                setConfirmDeleteId(id);
                return;
            }
            setDocBusyId(id);
            try {
                await deleteUserFile(id);
                await loadFiles();
            } catch {
                notify(t("profileEdDocActionFailed"), "error");
            } finally {
                setDocBusyId(null);
                setConfirmDeleteId(null);
            }
        },
        [confirmDeleteId, loadFiles, notify, t],
    );

    /* billing — explicit lifecycle so "Free" is only ever shown when the API
       confirmed an inactive subscription (never while loading / on failure) */
    const [sub, setSub] = useState<SubscriptionMeResponse | null>(null);
    const [subState, setSubState] = useState<"loading" | "loaded" | "error">("loading");
    useEffect(() => {
        let cancelled = false;
        getMySubscription()
            .then((s) => {
                if (cancelled) return;
                setSub(s);
                setSubState("loaded");
            })
            .catch(() => {
                if (!cancelled) setSubState("error");
            });
        return () => {
            cancelled = true;
        };
    }, []);

    // Dirty-state protection: warn only when the user would actually DISCARD
    // unsaved edits by leaving or refreshing the profile route. Section switches
    // are SPA navigations (pushState) and never trigger `beforeunload`, and the
    // draft lives in component state that survives switching — so changing
    // sections shows no warning and loses nothing. Only a real unload
    // (refresh / tab close / full navigation) with a dirty draft prompts.
    useEffect(() => {
        if (!dirty) return;
        const onBeforeUnload = (e: BeforeUnloadEvent) => {
            e.preventDefault();
            e.returnValue = "";
        };
        window.addEventListener("beforeunload", onBeforeUnload);
        return () => window.removeEventListener("beforeunload", onBeforeUnload);
    }, [dirty]);

    // Client-side navigation guard: `beforeunload` only covers refresh/close/hard
    // nav. App Router <Link> clicks (e.g. a sidebar route) need a capture-phase
    // interceptor — there is no official App-Router blocker. Profile-scoped: the
    // listener exists only while /profile has unsaved edits and is removed on
    // clean/unmount, so it never affects the rest of the app. A same-route click
    // (a section change: same pathname, different ?section=) is always allowed —
    // the draft is preserved — so switching sections never prompts.
    useEffect(() => {
        if (!dirty) return;
        const onDocClickCapture = (e: MouseEvent) => {
            if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            const anchor = (e.target as HTMLElement | null)?.closest?.("a");
            const href = anchor?.getAttribute("href");
            if (!anchor || !href || anchor.target === "_blank") return;
            let dest: URL;
            try {
                dest = new URL(href, window.location.href);
            } catch {
                return;
            }
            if (dest.origin !== window.location.origin) return; // external → beforeunload owns it
            if (dest.pathname === pathname) return; // same route (section change) → always allowed
            if (!window.confirm(t("profileUnsavedLeaveConfirm"))) {
                e.preventDefault();
                e.stopPropagation();
            }
        };
        document.addEventListener("click", onDocClickCapture, true);
        return () => document.removeEventListener("click", onDocClickCapture, true);
    }, [dirty, pathname, t]);

    /* derived hero facts */
    const pct = clampPct(profile.completeness_score);
    const subtitle = [profile.current_role, profile.current_company].filter((v) => v?.trim()).join(" · ");
    const heroCity = profile.preferred_cities?.[0]?.trim() || null;
    const nfCurrency = useMemo(
        () => (currency: string, value: number) =>
            new Intl.NumberFormat(isAr ? "ar-AE" : "en-AE", { style: "currency", currency, minimumFractionDigits: 2 }).format(value),
        [isAr],
    );
    const renewDate = useMemo(() => {
        const end = sub?.subscription.current_period_end;
        if (!end) return null;
        const d = new Date(end);
        if (Number.isNaN(d.getTime())) return null;
        return new Intl.DateTimeFormat(isAr ? "ar-AE" : "en-AE", { dateStyle: "long" }).format(d);
    }, [sub, isAr]);
    const planActive = subState === "loaded" && sub?.is_active ? sub.plan : null;
    const docDate = useCallback(
        (iso: string | null | undefined) => {
            if (!iso) return null;
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return null;
            return new Intl.DateTimeFormat(isAr ? "ar-AE" : "en-AE", { dateStyle: "medium" }).format(d);
        },
        [isAr],
    );

    const askRicoHref = `/command?prompt=${encodeURIComponent(t("profileEdAskRicoPrompt"))}`;
    // Honest Telegram status: only the SAVED username counts as "added"; a
    // draft that differs from the saved value is flagged as not yet saved.
    // No "connected" claim — the backend stores a username, it does not verify
    // a bot connection here.
    const savedTelegram = (profile.telegram_username ?? "").trim().replace(/^@/, "");
    const draftTelegram = draft.telegram_username.trim().replace(/^@/, "");
    const telegramStatus: "unsaved" | "added" | "none" =
        draftTelegram !== savedTelegram ? "unsaved" : savedTelegram ? "added" : "none";

    const ghostButton = {
        border: `1px solid ${palette.hair}`,
        background: "transparent",
        color: palette.ink,
        cursor: "pointer",
    } as const;

    return (
        <div className="profile-editorial" style={{ color: palette.ink }}>
            <style dangerouslySetInnerHTML={{ __html: `
                .profile-editorial .profile-ed-input::placeholder { color: ${palette.ink40}; }
                .profile-editorial .profile-ed-input:focus { border-color: ${palette.red} !important; }
                .profile-editorial .profile-ed-ghost:hover { border-color: ${palette.red}; color: ${palette.red}; }
                .profile-editorial .profile-ed-action { transition: border-color .15s ease, color .15s ease, transform .15s ease; }
                .profile-editorial .profile-ed-action:hover { border-color: ${palette.red} !important; color: ${palette.red} !important; }
                .profile-editorial .profile-ed-action:focus-visible,
                .profile-editorial .profile-ed-ghost:focus-visible { outline: 2px solid ${palette.red}; outline-offset: 2px; }
                .profile-editorial .profile-ed-rail-link { transition: background .12s ease, color .12s ease; }
                .profile-editorial .profile-ed-warn-action { transition: border-color .12s ease, color .12s ease; }
                .profile-editorial .profile-ed-warn-action:hover { border-color: ${palette.red} !important; }
                .profile-editorial .profile-ed-warn-action:focus-visible { outline: 2px solid ${palette.red}; outline-offset: 2px; }
                /* Warning-driven field highlight: a brief accessible outline pulse
                   on the exact field container after navigation. Under reduced
                   motion the outline is static (no pulse) and still time-bounded. */
                .profile-editorial .profile-ed-field-flash {
                    outline: 2px solid ${tone.warning};
                    outline-offset: 6px;
                    border-radius: 12px;
                    animation: profile-ed-field-flash 0.8s ease-in-out 2;
                }
                @keyframes profile-ed-field-flash {
                    0%, 100% { outline-color: ${tone.warning}; }
                    50% { outline-color: transparent; }
                }
                @media (prefers-reduced-motion: reduce) {
                    .profile-editorial .profile-ed-field-flash { animation: none; }
                }
            ` }} />

            {/* unsaved-changes bar (design: sticky sun banner with Save / Discard) */}
            {dirty && (
                <div
                    data-testid="profile-ed-savebar"
                    className="sticky top-2 z-30 mb-4 flex items-center justify-between gap-4 rounded-[12px] px-4 py-2.5 animate-fade-up motion-reduce:animate-none sm:px-5"
                    style={{ background: palette.red, color: "#fff", boxShadow: tone.shadow }}
                >
                    <span className="text-[13px] font-medium">{t("profileEdUnsaved")}</span>
                    <div className="flex shrink-0 items-center gap-2">
                        <button
                            type="button"
                            onClick={onDiscard}
                            disabled={saving}
                            className="h-8 rounded-[8px] px-3.5 text-[12.5px] font-medium transition-opacity disabled:opacity-60"
                            style={{ border: "1px solid rgba(255,255,255,0.4)", background: "transparent", color: "#fff", cursor: "pointer" }}
                        >
                            {t("profileEdDiscard")}
                        </button>
                        <button
                            type="button"
                            onClick={() => void onSave()}
                            disabled={saving}
                            className="h-8 rounded-[8px] px-4 text-[12.5px] font-semibold transition-transform active:scale-[0.98] disabled:opacity-60"
                            style={{ border: "none", background: "#fff", color: palette.red, cursor: "pointer" }}
                        >
                            {saving ? t("profileEdSaving") : t("profileEdSave")}
                        </button>
                    </div>
                </div>
            )}

            {/* screen-reader announcement for warning-driven field navigation */}
            <div aria-live="polite" role="status" className="sr-only">
                {fieldNavAnnouncement}
            </div>

            {profile.warnings && profile.warnings.length > 0 && (
                <div className="profile-ed-warnings mb-6">
                    <ProfileActionableWarnings
                        warnings={profile.warnings}
                        tone={tone}
                        onFieldAction={goToWarningField}
                    />
                </div>
            )}

            {/* hero identity plate */}
            <section
                aria-label={t("profileTitle")}
                className="mb-6 grid grid-cols-1 items-center gap-6 rounded-[20px] p-6 animate-fade-up motion-reduce:animate-none sm:grid-cols-[auto_1fr] lg:grid-cols-[auto_1fr_auto]"
                style={{ border: `1px solid ${palette.hair}`, background: palette.panel, boxShadow: tone.shadow }}
            >
                <div
                    aria-hidden
                    className="flex h-[104px] w-[104px] items-center justify-center rounded-full text-[34px] font-medium"
                    style={{ fontFamily: SERIF, background: tone.sunTint, color: palette.red, border: `1px solid ${palette.hair}` }}
                >
                    {initialsOf(profile.name)}
                </div>
                <div className="min-w-0">
                    <div className="mb-1 flex flex-wrap items-center gap-2.5">
                        <h1
                            className="m-0 text-[28px] font-medium leading-[1.15] tracking-[-0.015em]"
                            style={{ fontFamily: SERIF, color: palette.ink }}
                        >
                            {profile.name?.trim() || t("profileTitle")}
                        </h1>
                        <span
                            className="inline-flex items-center gap-1.5 rounded-full py-0.5 pe-2.5 ps-2 text-[10.5px] font-medium"
                            style={{ fontFamily: MONO, background: tone.successTint, color: tone.success }}
                        >
                            <Check className="h-2.5 w-2.5" strokeWidth={2.6} />
                            {t("profileEdVerified")}
                        </span>
                    </div>
                    {subtitle && (
                        <div className="mb-2 text-[15px]" style={{ color: palette.ink70 }}>{subtitle}</div>
                    )}
                    <div
                        className="flex flex-wrap gap-4 text-[11.5px]"
                        style={{ fontFamily: MONO, color: palette.ink55, letterSpacing: "0.02em" }}
                    >
                        {heroCity && (
                            <span className="inline-flex items-center gap-1.5"><MapPin className="h-3 w-3" />{heroCity}</span>
                        )}
                        {profile.email && (
                            <span className="inline-flex items-center gap-1.5"><Mail className="h-3 w-3" />{profile.email}</span>
                        )}
                        {profile.phone?.trim() && (
                            // dir=ltr keeps "+971…" from bidi-scrambling in RTL
                            <span className="inline-flex items-center gap-1.5"><Phone className="h-3 w-3" /><bdi dir="ltr">{profile.phone}</bdi></span>
                        )}
                    </div>
                </div>
                <div className="flex min-w-[200px] flex-col items-stretch gap-2">
                    <div className="rounded-[12px] px-3.5 py-3" style={{ border: `1px solid ${palette.hair}`, background: palette.inset }}>
                        <div className="mb-1.5 flex items-center justify-between">
                            <Eyebrow tone={tone}>{t("profileEdStrength")}</Eyebrow>
                            <span className="text-[15px] font-semibold" style={{ fontFamily: SERIF, color: palette.red }}>{pct}%</span>
                        </div>
                        <div
                            className="h-1 overflow-hidden rounded-full"
                            style={{ background: palette.track }}
                            role="progressbar"
                            aria-label={t("profileEdStrength")}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={pct}
                        >
                            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: palette.red }} />
                        </div>
                    </div>
                    <Link
                        href={askRicoHref}
                        className="profile-ed-action flex h-9 items-center justify-center gap-1.5 rounded-[10px] text-[12.5px] font-medium"
                        style={{ ...ghostButton, textDecoration: "none" }}
                    >
                        {t("profileEdAskRico")}
                    </Link>
                </div>
            </section>

            <div className="grid grid-cols-1 items-start gap-7 lg:grid-cols-[220px_1fr]">
                {/* sticky numbered rail (desktop) — true navigation: each item is a
                    real link to ?section=<slug> (push → browser back/forward work). */}
                <nav className="sticky top-20 hidden flex-col gap-0.5 lg:flex" aria-label={t("profileEdSections")}>
                    <div className="px-3 pb-2"><Eyebrow tone={tone}>{t("profileEdSections")}</Eyebrow></div>
                    {RAIL_SECTIONS.map((s) => {
                        const active = activeSection === s.id;
                        return (
                            <Link
                                key={s.id}
                                href={sectionHref(s.id)}
                                scroll={false}
                                aria-current={active ? "page" : undefined}
                                className="profile-ed-rail-link flex items-center justify-between rounded-[9px] px-3 py-2 text-[13px]"
                                style={{
                                    textDecoration: "none",
                                    color: active ? palette.red : palette.ink70,
                                    background: active ? tone.sunTint : "transparent",
                                    borderInlineStart: `2px solid ${active ? palette.red : "transparent"}`,
                                    fontWeight: active ? 600 : 500,
                                }}
                            >
                                {t(s.labelKey)}
                                <span style={{ fontFamily: MONO, fontSize: "9.5px", color: active ? palette.red : palette.ink40 }}>{s.num}</span>
                            </Link>
                        );
                    })}
                </nav>

                {/* WorkspaceShell owns the single <main> landmark; this is a plain column. */}
                <div className="flex min-w-0 flex-col gap-6">
                    {/* mobile section selector (below lg) — same URL-backed navigation as the rail */}
                    <div className="lg:hidden">
                        <label htmlFor="profile-section-select" className="sr-only">{t("profileEdSections")}</label>
                        <select
                            id="profile-section-select"
                            value={activeSection}
                            onChange={(e) => router.push(sectionHref(e.target.value))}
                            className="profile-ed-input w-full rounded-[10px] px-3 py-2.5 text-[14px]"
                            style={{ border: `1px solid ${palette.hair}`, background: palette.panel, color: palette.ink }}
                        >
                            {RAIL_SECTIONS.map((s) => (
                                <option key={s.id} value={s.id}>{s.num} · {t(s.labelKey)}</option>
                            ))}
                        </select>
                    </div>

                    {/* Render only the selected section (true navigation). All field
                        edits live in the parent `draft` state, so switching sections
                        preserves unsaved values and never refetches. */}
                    {/* 01 · About */}
                    {activeSection === "about" && (
                    <SectionCard id="about" num="01" index={0} tone={tone} eyebrow={t("profileEdAboutEyebrow")} title={t("profileEdAboutTitle")} help={t("profileEdAboutHelp")}>
                        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-name">{t("name")}</FieldLabel>
                                <TextInput id="profile-ed-name" tone={tone} value={draft.name} onChange={(v) => set("name", v)} />
                                {errors.name && <FieldError tone={tone}>{t(errors.name)}</FieldError>}
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-phone">{t("profilePhone")}</FieldLabel>
                                <TextInput id="profile-ed-phone" tone={tone} value={draft.phone} onChange={(v) => set("phone", v)} ltr />
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-telegram">{t("telegram")}</FieldLabel>
                                <TextInput id="profile-ed-telegram" tone={tone} value={draft.telegram_username} onChange={(v) => set("telegram_username", v)} />
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-linkedin">{t("profileLinkedin")}</FieldLabel>
                                <TextInput id="profile-ed-linkedin" tone={tone} value={draft.linkedin_url} onChange={(v) => set("linkedin_url", v)} ltr />
                            </div>
                        </div>
                    </SectionCard>

                    )}

                    {/* 02 · Career */}
                    {activeSection === "career" && (
                    <SectionCard id="career" num="02" index={1} tone={tone} eyebrow={t("profileEdCareerEyebrow")} title={t("profileCareer")} help={t("profileEdCareerHelp")}>
                        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-role">{t("profileCurrentRole")}</FieldLabel>
                                <TextInput id="profile-ed-role" tone={tone} value={draft.current_role} onChange={(v) => set("current_role", v)} />
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-company">{t("profileCurrentCompany")}</FieldLabel>
                                <TextInput id="profile-ed-company" tone={tone} value={draft.current_company} onChange={(v) => set("current_company", v)} />
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-years">{t("profileExperience")}</FieldLabel>
                                <TextInput id="profile-ed-years" tone={tone} value={draft.years_experience} onChange={(v) => set("years_experience", v)} inputMode="numeric" />
                                {errors.years_experience && <FieldError tone={tone}>{t(errors.years_experience)}</FieldError>}
                            </div>
                        </div>
                    </SectionCard>

                    )}

                    {/* 03 · Skills */}
                    {activeSection === "skills" && (
                    <SectionCard id="skills" num="03" index={2} tone={tone} eyebrow={t("profileEdSkillsEyebrow")} title={t("profileSkills")} help={t("profileEdSkillsHelp")}>
                        <ChipEditor
                            idBase="profile-ed-skill"
                            tone={tone}
                            values={draft.skills}
                            onChange={(v) => set("skills", v)}
                            addLabel={t("profileEdAddSkill")}
                            hint={t("profileEdChipHint")}
                        />
                    </SectionCard>

                    )}

                    {/* 04 · CV & documents */}
                    {activeSection === "documents" && (
                    <SectionCard
                        id="documents"
                        num="04"
                        index={3}
                        tone={tone}
                        eyebrow={t("profileEdDocsEyebrow")}
                        title={t("profileEdDocsTitle")}
                        help={t("profileEdDocsHelp")}
                        action={
                            <>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf,.doc,.docx,.txt"
                                    className="hidden"
                                    aria-label={t("profileEdUploadCV")}
                                    onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) void onUpload(file);
                                        e.target.value = "";
                                    }}
                                />
                                <button
                                    type="button"
                                    disabled={uploading}
                                    onClick={() => fileInputRef.current?.click()}
                                    className="h-[34px] rounded-[9px] px-3.5 text-[12.5px] font-medium transition-transform active:scale-[0.98] disabled:opacity-60"
                                    style={{ border: "none", background: palette.red, color: "#fff", cursor: "pointer" }}
                                >
                                    ↑ {uploading ? t("profileEdUploading") : t("profileEdUploadCV")}
                                </button>
                            </>
                        }
                    >
                        {filesLoaded && files.length === 0 ? (
                            <p className="m-0 text-[13.5px]" style={{ color: palette.ink55 }}>{t("profileEdDocsEmpty")}</p>
                        ) : (
                            <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                                {files.map((f) => {
                                    const busy = docBusyId === f.id;
                                    const updated = docDate(f.updated_at ?? f.created_at);
                                    return (
                                        <li
                                            key={f.id}
                                            className="flex flex-wrap items-center gap-3.5 rounded-[12px] px-3.5 py-3"
                                            style={{ border: `1px solid ${palette.hair}`, background: palette.inset }}
                                        >
                                            <div
                                                className="flex h-11 w-9 shrink-0 items-center justify-center rounded-[6px] text-[8.5px] font-semibold"
                                                style={{ fontFamily: MONO, background: palette.panel, border: `1px solid ${palette.hair}`, color: palette.ink55 }}
                                            >
                                                {extOf(f.original_filename || f.filename)}
                                            </div>
                                            <div className="min-w-0 flex-1 basis-44">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="truncate text-sm font-semibold" style={{ color: palette.ink }}>
                                                        {f.original_filename || f.filename}
                                                    </span>
                                                    {f.is_primary && (
                                                        <span
                                                            className="rounded-full px-2 py-px text-[9.5px]"
                                                            style={{ fontFamily: MONO, background: palette.red, color: "#fff", letterSpacing: "0.06em" }}
                                                        >
                                                            {t("profileEdPrimary")}
                                                        </span>
                                                    )}
                                                </div>
                                                {/* <bdi> isolates each segment so "284 KB · 10 Jul 2026"
                                                    keeps its order inside the RTL layout */}
                                                <div className="mt-0.5 text-[10.5px]" style={{ fontFamily: MONO, color: palette.ink55 }}>
                                                    <bdi dir="ltr">{formatBytes(f.file_size)}</bdi>
                                                    {updated && <> · <bdi>{updated}</bdi></>}
                                                    {f.label && <> · <bdi>{f.label}</bdi></>}
                                                </div>
                                            </div>
                                            <div className="ms-auto flex items-center gap-2">
                                                {!f.is_primary && (
                                                    <button
                                                        type="button"
                                                        disabled={busy}
                                                        onClick={() => void onSetPrimary(f.id)}
                                                        className="profile-ed-action inline-flex h-[30px] items-center gap-1 rounded-[8px] px-2.5 text-[11px] font-medium disabled:opacity-50"
                                                        style={ghostButton}
                                                    >
                                                        <Star className="h-3 w-3" />
                                                        {t("profileEdSetPrimary")}
                                                    </button>
                                                )}
                                                <button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() => void onDeleteDoc(f.id)}
                                                    className="inline-flex h-[30px] items-center gap-1 rounded-[8px] px-2.5 text-[11px] font-medium transition-colors disabled:opacity-50"
                                                    style={{
                                                        border: `1px solid ${confirmDeleteId === f.id ? tone.destructive : palette.hair}`,
                                                        background: "transparent",
                                                        color: tone.destructive,
                                                        cursor: "pointer",
                                                    }}
                                                >
                                                    <Trash2 className="h-3 w-3" />
                                                    {confirmDeleteId === f.id ? t("profileEdConfirmDelete") : t("delete")}
                                                </button>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ul>
                        )}
                    </SectionCard>

                    )}

                    {/* 05 · Career goals */}
                    {activeSection === "goals" && (
                    <SectionCard id="goals" num="05" index={4} tone={tone} eyebrow={t("profileEdPrefsEyebrow")} title={t("profileEdPrefsTitle")} help={t("profileEdPrefsHelp")}>
                        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                            <div
                                className={`sm:col-span-2 outline-none ${fieldFlash === "profile-field-target_roles" ? "profile-ed-field-flash" : ""}`}
                                id="profile-field-target_roles"
                                data-profile-field="target_roles"
                                tabIndex={-1}
                            >
                                <FieldLabel tone={tone}>{t("profileTargetRoles")}</FieldLabel>
                                <ChipEditor
                                    idBase="profile-ed-target-role"
                                    tone={tone}
                                    values={draft.target_roles}
                                    onChange={(v) => set("target_roles", v)}
                                    addLabel={t("profileEdAddRole")}
                                    hint={t("profileEdChipHint")}
                                />
                                {errors.target_roles && <FieldError tone={tone}>{t(errors.target_roles)}</FieldError>}
                            </div>
                            <div
                                className={`sm:col-span-2 outline-none ${fieldFlash === "profile-field-preferred_cities" ? "profile-ed-field-flash" : ""}`}
                                id="profile-field-preferred_cities"
                                data-profile-field="preferred_cities"
                                tabIndex={-1}
                            >
                                <FieldLabel tone={tone}>{t("profileCities")}</FieldLabel>
                                <ChipEditor
                                    idBase="profile-ed-city"
                                    tone={tone}
                                    values={draft.preferred_cities}
                                    onChange={(v) => set("preferred_cities", v)}
                                    addLabel={t("profileEdAddCity")}
                                    hint={t("profileEdChipHint")}
                                />
                                {errors.preferred_cities && <FieldError tone={tone}>{t(errors.preferred_cities)}</FieldError>}
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-salary">{t("profileSalaryTarget")} · {t("profileEdSalaryUnit")}</FieldLabel>
                                <TextInput id="profile-ed-salary" tone={tone} value={draft.salary_expectation_aed} onChange={(v) => set("salary_expectation_aed", v)} inputMode="decimal" />
                                {errors.salary_expectation_aed && <FieldError tone={tone}>{t(errors.salary_expectation_aed)}</FieldError>}
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-min-salary">{t("profileMinimumSalary")} · {t("profileEdSalaryUnit")}</FieldLabel>
                                <TextInput id="profile-ed-min-salary" tone={tone} value={draft.minimum_salary_aed} onChange={(v) => set("minimum_salary_aed", v)} inputMode="decimal" />
                                {errors.minimum_salary_aed && <FieldError tone={tone}>{t(errors.minimum_salary_aed)}</FieldError>}
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-visa">{t("profileVisa")}</FieldLabel>
                                <TextInput id="profile-ed-visa" tone={tone} value={draft.visa_status} onChange={(v) => set("visa_status", v)} />
                            </div>
                            <div>
                                <FieldLabel tone={tone} htmlFor="profile-ed-notice">{t("profileNotice")}</FieldLabel>
                                <TextInput id="profile-ed-notice" tone={tone} value={draft.notice_period} onChange={(v) => set("notice_period", v)} />
                            </div>
                        </div>
                    </SectionCard>

                    )}

                    {/* 06 · Integrations */}
                    {activeSection === "integrations" && (
                    <SectionCard id="integrations" num="06" index={5} tone={tone} eyebrow={t("profileEdIntegrationsEyebrow")} title={t("profileEdIntegrationsTitle")} help={t("profileEdIntegrationsHelp")}>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div className="rounded-[12px] p-4" style={{ border: `1px solid ${palette.hair}`, background: palette.inset }}>
                                <GmailConnectionCard palette={palette} notify={notify} />
                            </div>
                            <div
                                className="flex items-start justify-between gap-3 rounded-[12px] p-4"
                                style={{ border: `1px solid ${palette.hair}`, background: palette.inset }}
                            >
                                <div className="flex min-w-0 items-start gap-3">
                                    <div
                                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] text-sm font-semibold"
                                        style={{ fontFamily: SERIF, background: tone.sunTint, color: palette.red }}
                                    >
                                        T
                                    </div>
                                    <div className="min-w-0">
                                        <div className="text-sm font-semibold" style={{ color: palette.ink }}>{t("telegram")}</div>
                                        <div className="mt-0.5 text-[11px]" style={{ fontFamily: MONO, color: telegramStatus === "added" ? tone.success : palette.ink55 }}>
                                            {telegramStatus === "added" && <>● {t("profileEdTelegramAdded")} · <bdi dir="ltr">@{savedTelegram}</bdi></>}
                                            {telegramStatus === "unsaved" && <>○ {t("profileEdTelegramUnsaved")}</>}
                                            {telegramStatus === "none" && <>○ {t("profileEdTelegramOff")}</>}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </SectionCard>

                    )}

                    {/* 07 · Account & security */}
                    {activeSection === "security" && (
                    <SectionCard id="security" num="07" index={6} tone={tone} eyebrow={t("profileEdSecurityEyebrow")} title={t("profileEdSecurityTitle")}>
                        <div className="flex flex-col">
                            <div className="flex items-center justify-between gap-4 py-3.5" style={{ borderBottom: `1px solid ${palette.track}` }}>
                                <div className="min-w-0">
                                    <div className="text-sm font-medium" style={{ color: palette.ink }}>{t("email")}</div>
                                    <div className="mt-0.5 truncate text-[11.5px]" style={{ fontFamily: MONO, color: palette.ink55 }}>
                                        {profile.email ?? "—"} · {t("profileEdVerifiedWord")}
                                    </div>
                                </div>
                                <span
                                    className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                                    style={{ fontFamily: MONO, background: tone.successTint, color: tone.success }}
                                >
                                    <Check className="h-2.5 w-2.5" strokeWidth={3} />
                                    {t("profileEdVerifiedWord")}
                                </span>
                            </div>
                            <div className="flex items-center justify-between gap-4 pt-3.5">
                                <div>
                                    <div className="text-sm font-medium" style={{ color: palette.ink }}>{t("profileEdPassword")}</div>
                                    <div className="mt-0.5 text-[12.5px]" style={{ color: palette.ink55 }}>{t("profileEdPasswordHelp")}</div>
                                </div>
                                <Link
                                    href="/forgot-password"
                                    className="profile-ed-action inline-flex h-8 shrink-0 items-center rounded-[8px] px-3.5 text-xs font-medium"
                                    style={{ ...ghostButton, textDecoration: "none" }}
                                >
                                    {t("profileEdChange")}
                                </Link>
                            </div>
                        </div>
                    </SectionCard>

                    )}

                    {/* 08 · Billing — real subscription state; plan facts come from the API */}
                    {activeSection === "billing" && (
                    <SectionCard id="billing" num="08" index={7} tone={tone} eyebrow={t("profileEdBillingEyebrow")} title={t("profileEdBillingTitle")}>
                        <div
                            className="grid grid-cols-1 gap-4 rounded-[14px] p-5 sm:grid-cols-[1fr_auto]"
                            style={
                                planActive
                                    ? { background: `linear-gradient(135deg, ${palette.red} 0%, ${hexToRgba(palette.red, 0.75)} 100%)`, color: "#fff", boxShadow: `0 8px 32px -12px ${hexToRgba(palette.red, 0.35)}` }
                                    : { border: `1px solid ${palette.hair}`, background: palette.inset }
                            }
                        >
                            <div>
                                <div
                                    className={tone.isAr ? "" : "uppercase tracking-[0.14em]"}
                                    style={{ fontFamily: MONO, fontSize: "10px", color: planActive ? "rgba(255,255,255,0.8)" : palette.ink55 }}
                                >
                                    {t("profileEdCurrentPlan")}
                                </div>
                                {subState === "loaded" ? (
                                    <div
                                        className="mt-1 text-[26px] font-medium leading-tight tracking-[-0.01em]"
                                        style={{ fontFamily: SERIF, color: planActive ? "#fff" : palette.ink }}
                                    >
                                        {planActive ? planActive.name : t("profileEdFreePlan")}
                                    </div>
                                ) : (
                                    <div className="mt-1.5 text-[13.5px]" style={{ color: palette.ink55 }} role={subState === "loading" ? "status" : undefined}>
                                        {subState === "loading" ? t("loading") : t("profileEdBillingUnavailable")}
                                    </div>
                                )}
                                {planActive && renewDate && (
                                    <div className="mt-1 text-[12.5px]" style={{ color: "rgba(255,255,255,0.9)" }}>
                                        {t("profileEdRenewsOn")} {renewDate}
                                    </div>
                                )}
                            </div>
                            <div className="text-end">
                                {planActive && (
                                    <div className="text-[22px] font-medium" style={{ fontFamily: SERIF, color: "#fff" }}>
                                        {nfCurrency(planActive.currency, planActive.price_monthly)}
                                        <span className="text-[13px] opacity-80">{t("profileEdPerMonth")}</span>
                                    </div>
                                )}
                                <Link
                                    href="/subscription"
                                    className="mt-2 inline-flex h-8 items-center rounded-[8px] px-3.5 text-xs font-medium"
                                    style={
                                        planActive
                                            ? { border: "1px solid rgba(255,255,255,0.5)", color: "#fff", textDecoration: "none" }
                                            : { border: "none", background: palette.red, color: "#fff", textDecoration: "none", fontWeight: 600 }
                                    }
                                >
                                    {t("profileEdManagePlan")}
                                </Link>
                            </div>
                        </div>
                    </SectionCard>
                    )}
                </div>
            </div>
        </div>
    );
}
