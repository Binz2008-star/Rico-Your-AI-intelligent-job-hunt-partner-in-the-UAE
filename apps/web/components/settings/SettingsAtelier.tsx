"use client";

/**
 * SettingsAtelier — the authenticated /settings surface rebuilt to match the
 * approved /design-preview reference (en-settings-desktop.png):
 *
 *   • Eyebrow "SETTINGS" + serif title "Preferences." + hairline
 *   • Two-column layout: left tab sub-navigation, right content panel
 *   • Tabs: Account · Preferences · Notifications · Danger zone
 *
 * The composition is the reference; the DATA and BEHAVIOR are Rico's existing
 * production settings — nothing is faked. Every real control the previous
 * /settings page shipped is preserved and bound to the same endpoints:
 *   - Preferences → getSettings / updateSettings (keywords, min_score,
 *     max_daily_applies, guardrail warnings, score_threshold_* passthrough)
 *   - Notifications → getTelegramStatus / telegramOptIn / telegramOptOut +
 *     telegram_chat_id via updateSettings
 *   - Account → real name/phone via updateProfile, email read-only, change
 *     password + legal links
 *   - Danger zone → real logout
 *
 * Fields the reference shows but Rico has no backend for (Timezone) are omitted
 * rather than faked, and the reference's "prototype not connected" banner is
 * intentionally dropped because these fields ARE wired here.
 *
 * Palette comes from useWorkspaceTheme() so the content tracks WorkspaceShell's
 * local light/dark toggle. No backend, auth, cookie, schema, billing, or
 * notification-delivery behavior changes.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { PaddleBillingSection } from "@/components/billing/PaddleBillingSection";
import { GmailConnectionCard } from "@/components/settings/GmailConnectionCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { ToastContainer } from "@/components/ui/Toast";
import { useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/useToast";
import {
    ApiError,
    fetchProfile,
    getSettings,
    getTelegramStatus,
    logout,
    telegramOptIn,
    telegramOptOut,
    updateProfile,
    updateSettings,
    type ProfileResponse,
} from "@/lib/api";
import type { StoredUser } from "@/lib/auth";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";

const SERIF = ATELIER_FONT.serif;

type TabKey = "account" | "preferences" | "notifications" | "danger";

function splitKeywords(value: string): string[] {
    return value
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
}

/* Bordered content card with the reference corner ticks (shared Atelier grammar). */
function Panel({
    children,
    palette,
    id,
    labelledBy,
}: {
    children: React.ReactNode;
    palette: WorkspacePalette;
    id?: string;
    labelledBy?: string;
}) {
    const tick = "absolute h-2 w-2 pointer-events-none";
    const border = `1px solid ${palette.hair}`;
    return (
        <div
            id={id}
            role="tabpanel"
            aria-labelledby={labelledBy}
            className="relative rounded-[4px] p-5 sm:p-7"
            style={{ background: palette.panel, border }}
        >
            <span className={`${tick} left-1.5 top-1.5`} style={{ borderLeft: border, borderTop: border }} aria-hidden="true" />
            <span className={`${tick} right-1.5 top-1.5`} style={{ borderRight: border, borderTop: border }} aria-hidden="true" />
            <span className={`${tick} bottom-1.5 left-1.5`} style={{ borderBottom: border, borderLeft: border }} aria-hidden="true" />
            <span className={`${tick} bottom-1.5 right-1.5`} style={{ borderBottom: border, borderRight: border }} aria-hidden="true" />
            {children}
        </div>
    );
}

function FieldLabel({ children, palette, htmlFor }: { children: React.ReactNode; palette: WorkspacePalette; htmlFor?: string }) {
    return (
        <label htmlFor={htmlFor} className="mb-2 block">
            <Mono style={{ color: palette.ink55 }}>{children}</Mono>
        </label>
    );
}

/* Field hint under an input. */
function Hint({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
    return (
        <p className="mt-2 text-[11px]" style={{ color: palette.ink40 }}>
            {children}
        </p>
    );
}

/* Rico-voice intro line at the top of each control-center panel. */
function TabIntro({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
    return (
        <p className="mb-6 text-[13px]" style={{ color: palette.ink55 }}>
            {children}
        </p>
    );
}

/**
 * "Ask Rico" affordance — the conversational path to the same capability the
 * manual control writes. Deep-links to /command with a one-shot ?q= prompt
 * (the established production pattern used by profile/signals/mission/sidebar);
 * Rico's own chat + safety layer handles any actual change. This never mutates
 * state itself and never bypasses approval — it only opens the conversation.
 */
function AskRico({ q, label, palette }: { q: string; label: string; palette: WorkspacePalette }) {
    return (
        <Link
            href={`/command?q=${encodeURIComponent(q)}`}
            className="sx-askrico inline-flex items-center gap-1.5 text-[12px]"
            style={{ color: palette.red, textDecoration: "none" }}
        >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.6-.8L3 21l1.9-5.9a8.5 8.5 0 0 1-.8-3.6A8.38 8.38 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z" />
            </svg>
            <span>{label}</span>
            <span className="sx-askrico-arrow" aria-hidden="true">→</span>
        </Link>
    );
}

export function SettingsAtelier({ user }: { user: StoredUser }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const router = useRouter();
    const palette = useWorkspaceTheme();
    const { toasts, toast } = useToast();

    const [tab, setTab] = useState<TabKey>("account");

    // ── Settings (Preferences + Notifications chat id) ──
    const [settings, setSettings] = useState<SettingsResponse | null>(null);
    const [includeStr, setIncludeStr] = useState("");
    const [excludeStr, setExcludeStr] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<"auth" | "other" | null>(null);

    // ── Account (real profile-backed name/phone; email read-only) ──
    const [nameStr, setNameStr] = useState(user.name ?? "");
    const [phoneStr, setPhoneStr] = useState("");
    const [email, setEmail] = useState<string>(user.email ?? "");
    const [savingAccount, setSavingAccount] = useState(false);

    // ── Telegram (independent, never blocks the page) ──
    const [telegram, setTelegram] = useState<TelegramStatusResponse | null>(null);
    const telegramBusyRef = useRef(false);
    const [telegramBusy, setTelegramBusy] = useState(false);

    const [loggingOut, setLoggingOut] = useState(false);

    // No synchronous setLoading(true) here: `loading` starts true for the
    // initial mount, and the retry handler flips it back on before re-calling.
    // Keeps the mount effect free of synchronous setState (set-state-in-effect).
    const loadSettings = useCallback(async () => {
        try {
            const response = await getSettings();
            setSettings(response);
            setIncludeStr((response.include_keywords ?? []).join(", "));
            setExcludeStr((response.exclude_keywords ?? []).join(", "));
            setError(null);
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "other");
            toast(is401 ? t("sessionExpired") : t("couldNotLoadSettings"), "error");
        } finally {
            setLoading(false);
        }
    }, [toast, t]);

    // 1) Settings — blocking dependency for Preferences/Notifications tabs.
    //    Deferred through a timer so the mount effect performs no synchronous
    //    setState (matches the /profile page's load pattern).
    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadSettings();
        });
        return () => window.clearTimeout(timeoutId);
    }, [loadSettings]);

    // 2) Profile — populates real Account fields (name/phone/email). Failure is
    //    non-fatal: Account falls back to the StoredUser name/email.
    useEffect(() => {
        const ctrl = new AbortController();
        fetchProfile()
            .then((p: ProfileResponse) => {
                if (ctrl.signal.aborted) return;
                setNameStr((prev) => (p.name?.trim() ? p.name : prev));
                setPhoneStr(p.phone?.trim() ? p.phone : "");
                if (p.email) setEmail(p.email);
            })
            .catch(() => {
                /* Silent: Account still works from StoredUser. */
            });
        return () => ctrl.abort();
    }, []);

    // 3) Telegram status — parallel, graceful failure.
    useEffect(() => {
        const ctrl = new AbortController();
        getTelegramStatus(ctrl.signal)
            .then((status) => setTelegram(status))
            .catch(() => setTelegram(null));
        return () => ctrl.abort();
    }, []);

    const handleSaveSettings = async () => {
        if (!settings) return;
        setSaving(true);
        try {
            const updated = await updateSettings({
                include_keywords: splitKeywords(includeStr),
                exclude_keywords: splitKeywords(excludeStr),
                min_score: settings.min_score,
                max_daily_applies: settings.max_daily_applies,
                telegram_chat_id: settings.telegram_chat_id,
                // Preserved in the payload (backend contract) but not user-facing.
                score_threshold_apply: settings.score_threshold_apply,
                score_threshold_watch: settings.score_threshold_watch,
            });
            setSettings(updated);
            setIncludeStr((updated.include_keywords ?? []).join(", "));
            setExcludeStr((updated.exclude_keywords ?? []).join(", "));
            toast(t("settingsSaved"), "success");
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
        } finally {
            setSaving(false);
        }
    };

    const handleSaveAccount = async () => {
        setSavingAccount(true);
        try {
            await updateProfile({ name: nameStr.trim(), phone: phoneStr.trim() });
            toast(t("settingsSaved"), "success");
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
        } finally {
            setSavingAccount(false);
        }
    };

    const handleToggleTelegram = async () => {
        if (telegramBusyRef.current) return;
        telegramBusyRef.current = true;
        setTelegramBusy(true);
        const turningOn = !telegram?.opted_in;
        try {
            const next = turningOn
                ? await telegramOptIn(settings?.telegram_chat_id || undefined)
                : await telegramOptOut();
            setTelegram(next);
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
        } finally {
            telegramBusyRef.current = false;
            setTelegramBusy(false);
        }
    };

    const handleLogout = async () => {
        setLoggingOut(true);
        try {
            await logout();
        } finally {
            router.push("/login");
        }
    };

    const telegramOn = Boolean(telegram?.opted_in);

    const TABS: { key: TabKey; label: string }[] = [
        { key: "account", label: t("account") },
        { key: "preferences", label: t("settingsTabPreferences") },
        { key: "notifications", label: t("notifications") },
        { key: "danger", label: t("settingsTabDanger") },
    ];

    const inputStyle: React.CSSProperties = {
        background: palette.inset,
        border: `1px solid ${palette.hair}`,
        color: palette.ink,
    };

    /* Solid primary action (matches the reference's solid-dark active elements). */
    const primaryBtn = (busy: boolean): React.CSSProperties => ({
        background: palette.ink,
        color: palette.bg,
        opacity: busy ? 0.55 : 1,
        cursor: busy ? "default" : "pointer",
    });

    return (
        <div
            className="sx-root"
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            style={{ color: palette.ink }}
        >
            <style dangerouslySetInnerHTML={{
                __html: `
                .sx-root .sx-input { transition: border-color .15s ease; outline: none; }
                .sx-root .sx-input:focus { border-color: ${palette.red}; }
                .sx-root .sx-input::placeholder { color: ${palette.ink40}; }
                .sx-root .sx-tab { transition: background-color .15s ease, color .15s ease; }
                .sx-root .sx-tab:hover { color: ${palette.ink}; }
                .sx-root .sx-primary { transition: opacity .15s ease; }
                .sx-root .sx-primary:hover { opacity: .9; }
                .sx-root .sx-link { color: ${palette.red}; text-decoration: none; }
                .sx-root .sx-link:hover { text-decoration: underline; text-underline-offset: 2px; }
                .sx-root .sx-askrico { transition: opacity .15s ease; }
                .sx-root .sx-askrico:hover { text-decoration: underline; text-underline-offset: 3px; }
                .sx-root[dir="rtl"] .sx-askrico-arrow { display: inline-block; transform: scaleX(-1); }
                .sx-root a:focus-visible, .sx-root button:focus-visible, .sx-root input:focus-visible {
                    outline: 2px solid ${palette.red}; outline-offset: 2px; border-radius: 4px;
                }
                .sx-root [role="alert"] { border-color: ${palette.hair}; background: ${palette.inset}; }
                .sx-root [role="alert"] p { color: ${palette.ink}; }
                .sx-root [role="alert"] li p + p { color: ${palette.ink70}; }
            ` }} />

            {/* ── Header ── */}
            <header className="pb-5" style={{ borderBottom: `1px solid ${palette.hair}` }}>
                <Mono style={{ color: palette.ink55 }}>{t("settings")}</Mono>
                <h1
                    className={`mt-2 text-[2.2rem] font-normal sm:text-[2.8rem] ${isAr ? "leading-[1.15]" : "leading-[0.98]"}`}
                    style={{ fontFamily: SERIF, color: palette.ink }}
                >
                    {t("preferencesTitle")}
                </h1>
            </header>

            {/* ── Two-column: tab nav + panel ── */}
            <div className="mt-7 flex flex-col gap-6 lg:grid lg:items-start lg:gap-8" style={{ gridTemplateColumns: "200px 1fr" }}>
                {/* Sub-navigation */}
                <nav
                    role="tablist"
                    aria-orientation="vertical"
                    aria-label={t("settings")}
                    className="flex flex-row gap-1 overflow-x-auto lg:flex-col lg:overflow-visible"
                >
                    {TABS.map(({ key, label }) => {
                        const active = tab === key;
                        return (
                            <button
                                key={key}
                                type="button"
                                role="tab"
                                id={`sx-tab-${key}`}
                                aria-selected={active}
                                aria-controls={`sx-panel-${key}`}
                                onClick={() => setTab(key)}
                                className="sx-tab shrink-0 whitespace-nowrap rounded-[6px] px-3.5 py-2.5 text-start text-sm"
                                style={{
                                    color: active ? palette.ink : palette.ink55,
                                    background: active ? palette.activeBg : "transparent",
                                    borderInlineStart: `2px solid ${active ? palette.red : "transparent"}`,
                                    fontWeight: active ? 600 : 400,
                                }}
                            >
                                {label}
                            </button>
                        );
                    })}
                </nav>

                {/* ── Account ── */}
                {tab === "account" && (
                    <Panel palette={palette} id="sx-panel-account" labelledBy="sx-tab-account">
                        <TabIntro palette={palette}>{t("settingsAccountIntro")}</TabIntro>
                        <div className="flex flex-col gap-6">
                            <div>
                                <FieldLabel palette={palette} htmlFor="sx-name">{t("displayName")}</FieldLabel>
                                <input
                                    id="sx-name"
                                    type="text"
                                    value={nameStr}
                                    onChange={(e) => setNameStr(e.target.value)}
                                    placeholder={t("yourName")}
                                    className="sx-input w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                    style={inputStyle}
                                />
                            </div>

                            <div>
                                <FieldLabel palette={palette} htmlFor="sx-email">{t("email")}</FieldLabel>
                                <input
                                    id="sx-email"
                                    type="email"
                                    value={email || "—"}
                                    readOnly
                                    aria-readonly="true"
                                    tabIndex={-1}
                                    className="w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                    style={{ ...inputStyle, color: palette.ink55, cursor: "default" }}
                                />
                            </div>

                            <div>
                                <FieldLabel palette={palette} htmlFor="sx-phone">{t("profilePhone")}</FieldLabel>
                                <input
                                    id="sx-phone"
                                    type="tel"
                                    value={phoneStr}
                                    onChange={(e) => setPhoneStr(e.target.value)}
                                    placeholder="+971 50 000 0000"
                                    dir="ltr"
                                    className="sx-input w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                    style={{ ...inputStyle, textAlign: isAr ? "end" : "start" }}
                                />
                            </div>

                            <div className="flex flex-wrap items-center gap-4 pt-1">
                                <button
                                    type="button"
                                    onClick={handleSaveAccount}
                                    disabled={savingAccount}
                                    className="sx-primary inline-flex items-center gap-2 rounded-[6px] px-4 py-2.5 text-[13px] font-semibold"
                                    style={primaryBtn(savingAccount)}
                                >
                                    {savingAccount && (
                                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:hidden" style={{ opacity: 0.6 }} />
                                    )}
                                    {savingAccount ? t("saving") : t("saveSettings")}
                                </button>
                                <Link href="/forgot-password" className="sx-link text-[13px]">
                                    {t("changePassword")}
                                </Link>
                                <AskRico q={t("settingsAskAccountPrompt")} label={t("settingsAskAccount")} palette={palette} />
                            </div>

                            <div className="flex flex-wrap gap-4 pt-4" style={{ borderTop: `1px solid ${palette.hair}` }}>
                                <Link href="/terms" className="text-[12px]" style={{ color: palette.ink40 }}>{t("termsOfService")}</Link>
                                <Link href="/privacy" className="text-[12px]" style={{ color: palette.ink40 }}>{t("privacyPolicy")}</Link>
                                <Link href="/refund-policy" className="text-[12px]" style={{ color: palette.ink40 }}>{t("refundPolicy")}</Link>
                            </div>

                            <PaddleBillingSection
                                userId={user.email}
                                userEmail={user.email}
                                colors={{
                                    ink: palette.ink,
                                    ink70: palette.ink70,
                                    ink40: palette.ink40,
                                    surface: palette.panel,
                                    red: palette.red,
                                    borderDefault: palette.hair,
                                }}
                            />
                        </div>
                    </Panel>
                )}

                {/* ── Preferences (job filters) ── */}
                {tab === "preferences" && (
                    <Panel palette={palette} id="sx-panel-preferences" labelledBy="sx-tab-preferences">
                        <TabIntro palette={palette}>{t("settingsPreferencesIntro")}</TabIntro>
                        {loading ? (
                            <div className="flex flex-col gap-4">
                                {Array.from({ length: 4 }).map((_, i) => (
                                    <div key={i} className="h-10 animate-pulse rounded-[6px] motion-reduce:animate-none" style={{ background: palette.track }} />
                                ))}
                            </div>
                        ) : error ? (
                            <ErrorState
                                variant={error === "auth" ? "auth" : "network"}
                                onRetry={() => {
                                    setLoading(true);
                                    void loadSettings();
                                }}
                            />
                        ) : settings ? (
                            <div className="flex flex-col gap-6">
                                <div>
                                    <FieldLabel palette={palette} htmlFor="sx-include">{t("includeKeywords")}</FieldLabel>
                                    <input
                                        id="sx-include"
                                        type="text"
                                        value={includeStr}
                                        onChange={(e) => setIncludeStr(e.target.value)}
                                        placeholder={t("keywordsPlaceholder")}
                                        className="sx-input w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                        style={inputStyle}
                                    />
                                    <Hint palette={palette}>{t("includeKeywordsHint")}</Hint>
                                </div>

                                <div>
                                    <FieldLabel palette={palette} htmlFor="sx-exclude">{t("excludeKeywords")}</FieldLabel>
                                    <input
                                        id="sx-exclude"
                                        type="text"
                                        value={excludeStr}
                                        onChange={(e) => setExcludeStr(e.target.value)}
                                        placeholder={t("keywordsPlaceholder")}
                                        className="sx-input w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                        style={inputStyle}
                                    />
                                    <Hint palette={palette}>{t("excludeKeywordsHint")}</Hint>
                                </div>

                                <div>
                                    <div className="mb-2 flex items-center justify-between">
                                        <FieldLabel palette={palette} htmlFor="sx-minscore">{t("settingsMatchSelectivity")}</FieldLabel>
                                        <span style={{ fontFamily: SERIF, fontSize: "1.15rem", color: palette.red }}>{settings.min_score}%</span>
                                    </div>
                                    <input
                                        id="sx-minscore"
                                        type="range"
                                        min={50}
                                        max={95}
                                        step={5}
                                        value={settings.min_score}
                                        aria-label={t("settingsMatchSelectivity")}
                                        onChange={(e) => setSettings({ ...settings, min_score: Number(e.target.value) })}
                                        className="h-1.5 w-full cursor-pointer appearance-none rounded-full"
                                        style={{ background: palette.track, accentColor: palette.red }}
                                    />
                                    <div className="mt-1.5 flex justify-between">
                                        <Mono style={{ color: palette.ink40 }}>{t("general")}</Mono>
                                        <Mono style={{ color: palette.ink40 }}>{t("highMatchOnly")}</Mono>
                                    </div>
                                    <Hint palette={palette}>{t("settingsMatchContext").replace("{score}", String(settings.min_score))}</Hint>
                                    <div className="mt-2">
                                        <AskRico q={t("settingsAskStricterPrompt")} label={t("settingsAskStricter")} palette={palette} />
                                    </div>
                                </div>

                                <GuardrailWarnings warnings={settings.warnings} language={language} />

                                <div>
                                    <div className="mb-2 flex items-center justify-between">
                                        <FieldLabel palette={palette} htmlFor="sx-daily">{t("dailyApplyLimit")}</FieldLabel>
                                        <span style={{ fontFamily: SERIF, fontSize: "1.15rem", color: palette.red }}>{settings.max_daily_applies}</span>
                                    </div>
                                    <input
                                        id="sx-daily"
                                        type="range"
                                        min={0}
                                        max={50}
                                        step={1}
                                        value={settings.max_daily_applies}
                                        aria-label={t("dailyApplyLimit")}
                                        onChange={(e) => setSettings({ ...settings, max_daily_applies: Number(e.target.value) })}
                                        className="h-1.5 w-full cursor-pointer appearance-none rounded-full"
                                        style={{ background: palette.track, accentColor: palette.red }}
                                    />
                                    <div className="mt-1.5 flex justify-between">
                                        <Mono style={{ color: palette.ink40 }}>{t("safety")}</Mono>
                                        <Mono style={{ color: palette.ink40 }}>{t("aggressive")}</Mono>
                                    </div>
                                    <Hint palette={palette}>{t("settingsDailyContext")}</Hint>
                                    <div className="mt-2">
                                        <AskRico q={t("settingsAskDailyPrompt")} label={t("settingsAskDaily")} palette={palette} />
                                    </div>
                                </div>

                                <button
                                    type="button"
                                    onClick={handleSaveSettings}
                                    disabled={saving}
                                    className="sx-primary inline-flex items-center gap-2 self-start rounded-[6px] px-4 py-2.5 text-[13px] font-semibold"
                                    style={primaryBtn(saving)}
                                >
                                    {saving && (
                                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:hidden" style={{ opacity: 0.6 }} />
                                    )}
                                    {saving ? t("saving") : t("saveSettings")}
                                </button>
                            </div>
                        ) : null}
                    </Panel>
                )}

                {/* ── Notifications ── */}
                {tab === "notifications" && (
                    <Panel palette={palette} id="sx-panel-notifications" labelledBy="sx-tab-notifications">
                        <TabIntro palette={palette}>{t("settingsNotificationsIntro")}</TabIntro>
                        <div className="flex flex-col gap-6">
                            <div className="flex items-center justify-between gap-4">
                                <div className="min-w-0">
                                    <p className="text-[14px] font-semibold" style={{ color: palette.ink }}>{t("telegramAlerts")}</p>
                                    <p className="mt-1 flex items-center gap-1.5 text-[12px]" style={{ color: palette.ink55 }}>
                                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: telegramOn ? palette.red : palette.ink40 }} />
                                        {telegramOn ? t("telegramConnected") : t("telegramNotConnected")}
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={telegramOn}
                                    aria-label={t("telegramAlerts")}
                                    onClick={handleToggleTelegram}
                                    disabled={telegramBusy}
                                    className="relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50"
                                    style={{ background: telegramOn ? palette.red : palette.track, cursor: telegramBusy ? "default" : "pointer" }}
                                >
                                    <span
                                        className="absolute top-0.5 h-5 w-5 rounded-full transition-all"
                                        style={{
                                            background: palette.bg,
                                            insetInlineStart: telegramOn ? "calc(100% - 1.375rem)" : "0.125rem",
                                        }}
                                    />
                                </button>
                            </div>

                            {settings && (
                                <div className="flex flex-col gap-3 pt-5" style={{ borderTop: `1px solid ${palette.hair}` }}>
                                    <div>
                                        <FieldLabel palette={palette} htmlFor="sx-tgchat">{t("telegramChatId")}</FieldLabel>
                                        <input
                                            id="sx-tgchat"
                                            type="text"
                                            value={settings.telegram_chat_id}
                                            onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                                            placeholder={t("telegramPlaceholder")}
                                            dir="ltr"
                                            className="sx-input w-full rounded-[6px] px-3.5 py-2.5 text-sm"
                                            style={{ ...inputStyle, textAlign: isAr ? "end" : "start" }}
                                        />
                                        <Hint palette={palette}>{t("telegramChatIdHint")}</Hint>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-4">
                                        <button
                                            type="button"
                                            onClick={handleSaveSettings}
                                            disabled={saving}
                                            className="sx-primary inline-flex items-center gap-2 rounded-[6px] px-4 py-2.5 text-[13px] font-semibold"
                                            style={primaryBtn(saving)}
                                        >
                                            {saving && (
                                                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:hidden" style={{ opacity: 0.6 }} />
                                            )}
                                            {saving ? t("saving") : t("saveSettings")}
                                        </button>
                                        <AskRico q={t("settingsAskNotifyPrompt")} label={t("settingsAskNotify")} palette={palette} />
                                    </div>
                                </div>
                            )}

                            {/* Gmail read-only connector (M0) — flag-gated backend;
                                renders a "coming soon" state until enabled. */}
                            <GmailConnectionCard palette={palette} notify={toast} />
                        </div>
                    </Panel>
                )}

                {/* ── Danger zone ── */}
                {tab === "danger" && (
                    <Panel palette={palette} id="sx-panel-danger" labelledBy="sx-tab-danger">
                        <TabIntro palette={palette}>{t("settingsDangerIntro")}</TabIntro>
                        <div className="flex flex-col gap-4">
                            <p className="text-[14px] font-semibold" style={{ color: palette.ink }}>{t("logout")}</p>
                            <p className="text-[13px]" style={{ color: palette.ink55 }}>{t("dangerZoneDescription")}</p>
                            <button
                                type="button"
                                onClick={handleLogout}
                                disabled={loggingOut}
                                className="inline-flex items-center gap-2 self-start rounded-[6px] px-4 py-2.5 text-[13px] font-semibold transition-colors"
                                style={{
                                    background: "transparent",
                                    color: palette.red,
                                    border: `1px solid ${palette.red}`,
                                    opacity: loggingOut ? 0.55 : 1,
                                    cursor: loggingOut ? "default" : "pointer",
                                }}
                            >
                                {loggingOut && (
                                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:hidden" style={{ opacity: 0.6 }} />
                                )}
                                {t("logout")}
                            </button>
                        </div>
                    </Panel>
                )}
            </div>

            <ToastContainer toasts={toasts} />
        </div>
    );
}
