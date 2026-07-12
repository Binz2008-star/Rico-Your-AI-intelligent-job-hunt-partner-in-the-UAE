"use client";

/**
 * SettingsAtelier — /settings migrated to the approved /design-preview
 * workspace look (Shell C) as a VISUAL/COMPOSITION change only (PR 5C).
 *
 * ALL behavior is preserved verbatim from the previous settings page:
 * getSettings/updateSettings, getTelegramStatus/telegramOptIn/telegramOptOut,
 * the include/exclude keyword inputs, min_score + max_daily_applies sliders,
 * GuardrailWarnings, the Telegram switch + chat-id, the account section, toast,
 * and every persistence key in the update payload (including the non-user-facing
 * score_threshold_apply/watch that ride the backend contract). Only the
 * presentation (AppShell/StatusCard/dark classes → WorkspaceShell + Atelier
 * plates/tokens) changes. i18n keys are unchanged (useTranslation).
 *
 * Colors come from the shared WorkspaceThemeContext so light/dark matches the
 * shell. Rendered inside WorkspaceShell by app/settings/page.tsx.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import { useToast } from "@/hooks/useToast";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { ToastContainer } from "@/components/ui/Toast";
import {
    ApiError,
    getSettings,
    updateSettings,
    getTelegramStatus,
    telegramOptIn,
    telegramOptOut,
    logout,
} from "@/lib/api";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";
import type { StoredUser } from "@/lib/auth";

const SERIF = ATELIER_FONT.serif;

function splitKeywords(value: string): string[] {
    return value
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
}

type Palette = ReturnType<typeof useWorkspaceTheme>;

function Plate({ c, title, children }: { c: Palette; title: string; children: React.ReactNode }) {
    return (
        <section className="rounded-[4px] p-6 sm:p-7" style={{ background: c.panel, border: `1px solid ${c.hair}` }}>
            <Mono style={{ color: c.ink55 }}>{title}</Mono>
            <div className="mt-4">{children}</div>
        </section>
    );
}

export function SettingsAtelier({ user }: { user: StoredUser }) {
    const { toasts, toast } = useToast();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const router = useRouter();
    const c = useWorkspaceTheme();

    const [settings, setSettings] = useState<SettingsResponse | null>(null);
    const [includeStr, setIncludeStr] = useState("");
    const [excludeStr, setExcludeStr] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<"auth" | "other" | null>(null);

    const [telegram, setTelegram] = useState<TelegramStatusResponse | null>(null);
    const telegramBusyRef = useRef(false);
    const [telegramBusy, setTelegramBusy] = useState(false);

    const handleLogout = useCallback(async () => {
        try {
            await logout();
        } finally {
            router.push("/login");
        }
    }, [router]);

    const loadSettings = useCallback(async () => {
        if (!user) return;
        setLoading(true);
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
    }, [user, toast, t]);

    useEffect(() => {
        if (!user) return;
        void loadSettings();
    }, [user, loadSettings]);

    useEffect(() => {
        if (!user) return;
        const ctrl = new AbortController();
        getTelegramStatus(ctrl.signal)
            .then((status) => setTelegram(status))
            .catch(() => setTelegram(null));
        return () => ctrl.abort();
    }, [user]);

    const handleSave = async () => {
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

    const telegramOn = Boolean(telegram?.opted_in);
    const isAr = language === "ar";

    const inputStyle: React.CSSProperties = {
        width: "100%", background: c.inset, border: `1px solid ${c.hair}`,
        borderRadius: 4, padding: "9px 11px", fontSize: "0.92rem", color: c.ink, outline: "none",
    };
    const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: c.ink70 };
    const hintStyle: React.CSSProperties = { fontSize: 11, color: c.ink40 };
    const saveBtn = (
        <button
            onClick={handleSave}
            disabled={saving}
            className="mt-1 inline-flex items-center gap-2 self-start rounded-[4px] px-4 py-2.5 text-[13px] font-semibold"
            style={{ background: c.ink, color: c.bg, cursor: saving ? "default" : "pointer", opacity: saving ? 0.5 : 1 }}
        >
            {saving ? t("saving") : t("saveSettings")}
        </button>
    );

    return (
        <div className="flex w-full max-w-2xl flex-col gap-6" style={{ color: c.ink }}>
            {/* Header */}
            <div>
                <Mono style={{ color: c.ink55 }}>{t("settings")}</Mono>
                <h1 className="mt-2 text-[2.2rem] sm:text-[2.7rem] leading-[1] font-normal" style={{ fontFamily: SERIF, color: c.ink }}>
                    {t("settingsSubtitle")}
                </h1>
            </div>
            <div className="h-px" style={{ background: c.hair }} aria-hidden="true" />

            {/* ── Section A: Job Filters ── */}
            <Plate c={c} title={t("jobFilters")}>
                {loading ? (
                    <div className="flex flex-col gap-3">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="h-10 animate-pulse rounded-[4px] motion-reduce:animate-none" style={{ background: c.inset }} />
                        ))}
                    </div>
                ) : error ? (
                    <div>
                        <p className="text-[0.95rem]" style={{ color: c.ink70 }}>
                            {error === "auth" ? t("sessionExpired") : t("couldNotLoadSettings")}
                        </p>
                        <button type="button" onClick={() => void loadSettings()} className="mt-3 rounded-[4px] px-3.5 py-1.5 text-sm font-semibold" style={{ border: `1px solid ${c.ink}`, color: c.ink, background: "transparent", cursor: "pointer" }}>
                            {t("retry")}
                        </button>
                    </div>
                ) : settings ? (
                    <div className="flex flex-col gap-5">
                        <label className="flex flex-col gap-1.5">
                            <span style={labelStyle}>{t("includeKeywords")}</span>
                            <input type="text" value={includeStr} onChange={(e) => setIncludeStr(e.target.value)} placeholder={t("keywordsPlaceholder")} style={inputStyle} />
                            <span style={hintStyle}>{t("includeKeywordsHint")}</span>
                        </label>

                        <label className="flex flex-col gap-1.5">
                            <span style={labelStyle}>{t("excludeKeywords")}</span>
                            <input type="text" value={excludeStr} onChange={(e) => setExcludeStr(e.target.value)} placeholder={t("keywordsPlaceholder")} style={inputStyle} />
                            <span style={hintStyle}>{t("excludeKeywordsHint")}</span>
                        </label>

                        <label className="flex flex-col gap-2">
                            <span className="flex items-center justify-between" style={labelStyle}>
                                {t("minimumFitScore")}
                                <span style={{ color: c.red }}>{settings.min_score}%</span>
                            </span>
                            <input type="range" min={50} max={95} step={5} value={settings.min_score} aria-label={t("minimumFitScore")}
                                onChange={(e) => setSettings({ ...settings, min_score: Number(e.target.value) })}
                                className="h-1.5 w-full cursor-pointer appearance-none rounded-lg" style={{ background: c.track, accentColor: c.red }} />
                            <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight" style={{ color: c.ink40 }}>
                                <span>{t("general")}</span>
                                <span>{t("highMatchOnly")}</span>
                            </div>
                        </label>

                        <GuardrailWarnings warnings={settings.warnings} language={language} />

                        <label className="flex flex-col gap-2">
                            <span className="flex items-center justify-between" style={labelStyle}>
                                {t("dailyApplyLimit")}
                                <span style={{ color: c.red }}>{settings.max_daily_applies}</span>
                            </span>
                            <input type="range" min={0} max={50} step={1} value={settings.max_daily_applies} aria-label={t("dailyApplyLimit")}
                                onChange={(e) => setSettings({ ...settings, max_daily_applies: Number(e.target.value) })}
                                className="h-1.5 w-full cursor-pointer appearance-none rounded-lg" style={{ background: c.track, accentColor: c.red }} />
                            <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight" style={{ color: c.ink40 }}>
                                <span>{t("safety")}</span>
                                <span>{t("aggressive")}</span>
                            </div>
                        </label>

                        {saveBtn}
                    </div>
                ) : null}
            </Plate>

            {/* ── Section B: Notifications ── */}
            <Plate c={c} title={t("notifications")}>
                <div className="flex flex-col gap-5">
                    <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                            <p className="text-[13px] font-semibold" style={{ color: c.ink }}>{t("telegramAlerts")}</p>
                            <p className="mt-0.5 flex items-center gap-1.5 text-[12px]" style={{ color: c.ink40 }}>
                                <span className="h-1.5 w-1.5 rounded-full" style={{ background: telegramOn ? "#3f9b57" : c.ink40 }} />
                                {telegramOn ? t("telegramConnected") : t("telegramNotConnected")}
                            </p>
                        </div>
                        <button role="switch" aria-checked={telegramOn} aria-label={t("telegramAlerts")} onClick={handleToggleTelegram} disabled={telegramBusy}
                            className="relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50"
                            style={{ background: telegramOn ? c.red : c.hair, cursor: telegramBusy ? "default" : "pointer" }}>
                            <span className="absolute top-0.5 start-0.5 h-5 w-5 rounded-full transition-transform" style={{ background: "#fff", transform: telegramOn ? (isAr ? "translateX(-20px)" : "translateX(20px)") : "translateX(0)" }} />
                        </button>
                    </div>

                    {settings && (
                        <div className="flex flex-col gap-3 pt-5" style={{ borderTop: `1px solid ${c.hair}` }}>
                            <label className="flex flex-col gap-1.5">
                                <span style={labelStyle}>{t("telegramChatId")}</span>
                                <input type="text" value={settings.telegram_chat_id} onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })} placeholder={t("telegramPlaceholder")} style={inputStyle} />
                                <span style={hintStyle}>{t("telegramChatIdHint")}</span>
                            </label>
                            {saveBtn}
                        </div>
                    )}
                </div>
            </Plate>

            {/* ── Section C: Account ── */}
            <Plate c={c} title={t("account")}>
                <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                        <span style={labelStyle}>{t("emailAddress")}</span>
                        <p className="text-[13px]" style={{ color: c.ink }}>{user?.email ?? "—"}</p>
                    </div>

                    <a href="/forgot-password" className="inline-flex items-center gap-1.5 self-start text-[13px]" style={{ color: c.red }}>
                        {t("changePassword")}
                    </a>

                    <div className="mt-1 flex flex-wrap gap-4 pt-4" style={{ borderTop: `1px solid ${c.hair}` }}>
                        <a href="/terms" className="text-[12px]" style={{ color: c.ink55 }}>{t("termsOfService")}</a>
                        <a href="/privacy" className="text-[12px]" style={{ color: c.ink55 }}>{t("privacyPolicy")}</a>
                        <a href="/refund-policy" className="text-[12px]" style={{ color: c.ink55 }}>{t("refundPolicy")}</a>
                    </div>

                    <button type="button" onClick={handleLogout} className="mt-1 self-start text-[12px]" style={{ color: c.ink40, cursor: "pointer", background: "transparent" }}>
                        {t("logout")}
                    </button>
                </div>
            </Plate>

            <ToastContainer toasts={toasts} />
        </div>
    );
}
