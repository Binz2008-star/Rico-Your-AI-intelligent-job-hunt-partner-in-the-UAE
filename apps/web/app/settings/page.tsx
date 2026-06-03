"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusCard } from "@/components/StatusCard";
import { ToastContainer } from "@/components/ui/Toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { ApiError, getSettings, updateSettings } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse } from "@/types";
import { useCallback, useEffect, useState } from "react";

const SETTINGS_BACKEND_MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";

export default function SettingsPage() {
    const { user } = useAuth();
    const { toasts, toast } = useToast();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [settings, setSettings] = useState<SettingsResponse | null>(null);
    const [loadingSettings, setLoadingSettings] = useState(!SETTINGS_BACKEND_MAINTENANCE_MODE);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<"auth" | "other" | null>(null);

    const telegramConfigured = Boolean(settings?.telegram_chat_id?.trim());
    const telegramStatus = SETTINGS_BACKEND_MAINTENANCE_MODE
        ? t("paused")
        : telegramConfigured
            ? t("configured")
            : t("notConfigured");
    const telegramDescription = telegramConfigured
        ? t("telegramConfigured")
        : SETTINGS_BACKEND_MAINTENANCE_MODE
            ? t("telegramPaused")
            : t("telegramNotConfigured");

    const loadSettings = useCallback(async () => {
        if (SETTINGS_BACKEND_MAINTENANCE_MODE) {
            return;
        }
        if (!user) return;
        try {
            const response = await getSettings();
            setSettings(response);
            setError(null);
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "other");
            toast(is401 ? t("sessionExpired") : t("couldNotLoadSettings"), "error");
        } finally {
            setLoadingSettings(false);
        }
    }, [toast, user, t]);

    useEffect(() => {
        if (SETTINGS_BACKEND_MAINTENANCE_MODE) return;
        if (!user) return;
        const timeoutId = window.setTimeout(() => {
            void loadSettings();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadSettings, user]);

    const handleRetrySettings = useCallback(() => {
        if (SETTINGS_BACKEND_MAINTENANCE_MODE) {
            toast(t("settingsSyncPaused"), "error");
            return;
        }
        setError(null);
        setLoadingSettings(true);
        void loadSettings();
    }, [loadSettings, toast, t]);

    const handleSave = async () => {
        if (!settings) return;
        setSaving(true);
        try {
            const updated = await updateSettings({
                min_score: settings.min_score,
                max_daily_applies: settings.max_daily_applies,
                score_threshold_apply: settings.score_threshold_apply,
                score_threshold_watch: settings.score_threshold_watch,
                telegram_chat_id: settings.telegram_chat_id,
                include_keywords: settings.include_keywords,
                exclude_keywords: settings.exclude_keywords,
            });
            setSettings(updated);
            toast(t("settingsSaved"), "success");
        } catch (err) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
        } finally {
            setSaving(false);
        }
    };

    return (
        <DashboardShell
            title={t("settings")}
            subtitle={t("settingsSubtitle")}
        >
            <div className="max-w-3xl flex flex-col gap-8">
                {SETTINGS_BACKEND_MAINTENANCE_MODE && (
                    <section className="rounded-2xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
                        <p className="text-[13px] font-semibold text-[#f5a623]">{t("backendMaintenance")}</p>
                        <p className="mt-1 text-[12px] leading-relaxed text-[#a08040]">
                            {t("backendMaintenanceDescription")}
                        </p>
                    </section>
                )}

                {/* Job Matching Preferences */}
                {settings && (
                    <section className="space-y-4">
                        <h2 className="text-[11px] font-black text-text-tertiary uppercase tracking-[0.2em] ms-1">{t("jobMatchingPreferences")}</h2>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <StatusCard title={t("applyPacing")} value={String(settings.max_daily_applies)}>
                                <div className="mt-2">
                                    <input
                                        type="range" min={0} max={50} step={1}
                                        aria-label={t("applyPacing")}
                                        value={settings.max_daily_applies}
                                        onChange={(e) => setSettings({ ...settings, max_daily_applies: Number(e.target.value) })}
                                        className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-magenta"
                                    />
                                    <div className="flex justify-between mt-2 text-[10px] text-text-tertiary font-bold uppercase tracking-tighter">
                                        <span>{t("safety")}</span>
                                        <span>{t("aggressive")}</span>
                                    </div>
                                </div>
                            </StatusCard>

                            <StatusCard title={t("minimumFitScore")} value={`${settings.min_score}%`}>
                                <div className="mt-2">
                                    <input
                                        type="range" min={50} max={95} step={5}
                                        aria-label={t("minimumFitScore")}
                                        value={settings.min_score}
                                        onChange={(e) => setSettings({ ...settings, min_score: Number(e.target.value) })}
                                        className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-cyan"
                                    />
                                    <div className="flex justify-between mt-2 text-[10px] text-text-tertiary font-bold uppercase tracking-tighter">
                                        <span>{t("general")}</span>
                                        <span>{t("highMatchOnly")}</span>
                                    </div>
                                </div>
                            </StatusCard>
                        </div>
                    </section>
                )}

                {/* Match Thresholds */}
                <section className="bg-surface-elevated/40 border border-border-subtle rounded-2xl p-6 backdrop-blur-md relative overflow-hidden">
                    <div className="absolute -top-10 -right-10 w-32 h-32 bg-magenta/5 blur-3xl rounded-full pointer-events-none" aria-hidden="true" />

                    <h3 className="font-['Cabinet_Grotesk',sans-serif] font-bold text-[17px] text-text-primary mb-6">{t("matchThresholds")}</h3>

                    {loadingSettings ? (
                        <div className="flex flex-col gap-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <div key={i} className="h-10 rounded-lg bg-surface-glass animate-pulse" />
                            ))}
                        </div>
                    ) : error ? (
                        <ErrorState
                            variant={error === "auth" ? "auth" : "network"}
                            onRetry={handleRetrySettings}
                        />
                    ) : settings ? (
                        <div className="flex flex-col gap-4">
                            <div className="grid grid-cols-2 gap-4">
                                <label className="flex flex-col gap-1.5">
                                    <span className="text-[11px] text-text-tertiary uppercase tracking-wider font-semibold">{t("applyThreshold")}</span>
                                    <input
                                        type="number"
                                        min={0}
                                        max={100}
                                        value={settings.score_threshold_apply}
                                        onChange={(e) => setSettings({ ...settings, score_threshold_apply: Number(e.target.value) })}
                                        className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-magenta/40"
                                    />
                                </label>
                                <label className="flex flex-col gap-1.5">
                                    <span className="text-[11px] text-text-tertiary uppercase tracking-wider font-semibold">{t("watchThreshold")}</span>
                                    <input
                                        type="number"
                                        min={0}
                                        max={100}
                                        value={settings.score_threshold_watch}
                                        onChange={(e) => setSettings({ ...settings, score_threshold_watch: Number(e.target.value) })}
                                        className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-magenta/40"
                                    />
                                </label>
                            </div>
                            <label className="flex flex-col gap-1.5">
                                <span className="text-[11px] text-text-tertiary uppercase tracking-wider font-semibold">{t("telegramChatId")}</span>
                                <input
                                    type="text"
                                    value={settings.telegram_chat_id}
                                    onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                                    placeholder={t("telegramPlaceholder")}
                                    className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-magenta/40 placeholder:text-text-tertiary"
                                />
                            </label>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="self-start px-4 py-2 rounded-lg bg-rico-accent-muted text-rico-purple border border-rico-accent-border text-[13px] font-semibold hover:bg-rico-accent/25 transition-all disabled:opacity-40"
                            >
                                {saving ? t("saving") : t("saveSettings")}
                            </button>
                        </div>
                    ) : null}
                </section>

                {/* Channel Preferences — Glow Card */}
                <section className="bg-surface-elevated/40 border border-border-subtle rounded-2xl p-6 backdrop-blur-md relative overflow-hidden">
                    <div className="absolute -top-10 -right-10 w-32 h-32 bg-cyan/5 blur-3xl rounded-full pointer-events-none" aria-hidden="true" />

                    <h3 className="font-['Cabinet_Grotesk',sans-serif] font-bold text-[17px] text-text-primary mb-6">{t("channelPreferences")}</h3>

                    <div className="space-y-6">
                        <div className="flex items-center justify-between group">
                            <div className="space-y-1">
                                <p className="text-sm font-bold text-text-primary group-hover:text-white transition-colors">{t("telegramNotifications")}</p>
                                <p className="text-xs text-text-tertiary">
                                    {telegramDescription}
                                </p>
                            </div>
                            <span className="text-xs text-[#5b4fff] font-medium">{telegramStatus}</span>
                        </div>

                        <div className="pt-6 border-t border-border-subtle flex items-center justify-between">
                            <span className="text-[11px] text-text-tertiary font-medium uppercase tracking-widest">
                                {SETTINGS_BACKEND_MAINTENANCE_MODE
                                    ? t("statusPaused")
                                    : saving ? t("statusSyncing") : t("statusSynced")}
                            </span>
                            {saving && <div className="w-3 h-3 border-2 border-[#5b4fff] border-t-transparent rounded-full animate-spin" />}
                        </div>
                    </div>
                </section>


                {/* Legal */}
                <section className="bg-surface-elevated/80 border border-border-subtle rounded-2xl p-6">
                    <h2 className="font-['Cabinet_Grotesk',sans-serif] font-bold text-[15px] mb-4 text-text-primary">{t("legal")}</h2>
                    <div className="flex flex-wrap gap-4">
                        <a href="/terms" className="text-[13px] text-text-tertiary hover:text-text-primary transition-colors">{t("termsOfService")}</a>
                        <a href="/privacy" className="text-[13px] text-text-tertiary hover:text-text-primary transition-colors">{t("privacyPolicy")}</a>
                        <a href="/refund-policy" className="text-[13px] text-text-tertiary hover:text-text-primary transition-colors">{t("refundPolicy")}</a>
                    </div>
                </section>

            </div>
            <ToastContainer toasts={toasts} />
        </DashboardShell>
    );
}
