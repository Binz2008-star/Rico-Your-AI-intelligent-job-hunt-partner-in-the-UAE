"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { ErrorState } from "@/components/shared/ErrorState";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  ApiError,
  getSettings,
  updateSettings,
  getTelegramStatus,
  telegramOptIn,
  telegramOptOut,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";
import { useCallback, useEffect, useState } from "react";

function splitKeywords(value: string): string[] {
  return value
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { toasts, toast } = useToast();
  const { language } = useLanguage();
  const t = useTranslation(language);

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [includeStr, setIncludeStr] = useState("");
  const [excludeStr, setExcludeStr] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<"auth" | "other" | null>(null);

  // Telegram status loads independently and must never block the page.
  const [telegram, setTelegram] = useState<TelegramStatusResponse | null>(null);
  const [telegramBusy, setTelegramBusy] = useState(false);

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

  // 1) Settings first — this is the page's blocking dependency.
  useEffect(() => {
    if (!user) return;
    void loadSettings();
  }, [user, loadSettings]);

  // 2) Telegram status in parallel — graceful failure, never blocks render.
  useEffect(() => {
    if (!user) return;
    const ctrl = new AbortController();
    getTelegramStatus(ctrl.signal)
      .then((status) => setTelegram(status))
      .catch(() => {
        // Silent: Settings must work even if Telegram status is unavailable.
        setTelegram(null);
      });
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
    if (telegramBusy) return;
    const turningOn = !telegram?.opted_in;
    setTelegramBusy(true);
    try {
      const next = turningOn
        ? await telegramOptIn(settings?.telegram_chat_id || undefined)
        : await telegramOptOut();
      setTelegram(next);
    } catch (err) {
      const is401 = err instanceof ApiError && err.statusCode === 401;
      toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
    } finally {
      setTelegramBusy(false);
    }
  };

  const telegramOn = Boolean(telegram?.opted_in);

  return (
    <DashboardShell title={t("settings")} subtitle={t("settingsSubtitle")}>
      <div className="max-w-2xl flex flex-col gap-8">
        {/* ── Section A: Job Filters ─────────────────────────────────── */}
        <section className="bg-surface-elevated/40 border border-border-subtle rounded-2xl p-6">
          <header className="mb-5">
            <h2 className="font-semibold text-[15px] text-text-primary">
              {t("jobFilters")}
            </h2>
            <p className="mt-1 text-[13px] text-text-tertiary">
              {t("jobFiltersSubtitle")}
            </p>
          </header>

          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 rounded-lg bg-surface-glass animate-pulse motion-reduce:animate-none"
                />
              ))}
            </div>
          ) : error ? (
            <ErrorState
              variant={error === "auth" ? "auth" : "network"}
              onRetry={() => void loadSettings()}
            />
          ) : settings ? (
            <div className="flex flex-col gap-5">
              <label className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("includeKeywords")}
                </span>
                <input
                  type="text"
                  value={includeStr}
                  onChange={(e) => setIncludeStr(e.target.value)}
                  placeholder={t("keywordsPlaceholder")}
                  className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-primary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                />
                <span className="text-[11px] text-text-tertiary">
                  {t("includeKeywordsHint")}
                </span>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("excludeKeywords")}
                </span>
                <input
                  type="text"
                  value={excludeStr}
                  onChange={(e) => setExcludeStr(e.target.value)}
                  placeholder={t("keywordsPlaceholder")}
                  className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-primary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                />
                <span className="text-[11px] text-text-tertiary">
                  {t("excludeKeywordsHint")}
                </span>
              </label>

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold text-text-secondary">
                  {t("minimumFitScore")}
                  <span className="text-gold">{settings.min_score}%</span>
                </span>
                <input
                  type="range"
                  min={50}
                  max={95}
                  step={5}
                  value={settings.min_score}
                  aria-label={t("minimumFitScore")}
                  onChange={(e) =>
                    setSettings({ ...settings, min_score: Number(e.target.value) })
                  }
                  className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-gold"
                />
                <div className="flex justify-between text-[10px] text-text-tertiary font-bold uppercase tracking-tight">
                  <span>{t("general")}</span>
                  <span>{t("highMatchOnly")}</span>
                </div>
              </label>

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold text-text-secondary">
                  {t("dailyApplyLimit")}
                  <span className="text-gold">{settings.max_daily_applies}</span>
                </span>
                <input
                  type="range"
                  min={0}
                  max={50}
                  step={1}
                  value={settings.max_daily_applies}
                  aria-label={t("dailyApplyLimit")}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      max_daily_applies: Number(e.target.value),
                    })
                  }
                  className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-gold"
                />
                <div className="flex justify-between text-[10px] text-text-tertiary font-bold uppercase tracking-tight">
                  <span>{t("safety")}</span>
                  <span>{t("aggressive")}</span>
                </div>
              </label>

              <button
                onClick={handleSave}
                disabled={saving}
                className="self-start mt-1 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gold text-[#0a0a1a] text-[13px] font-semibold hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                {saving && (
                  <span className="w-3.5 h-3.5 border-2 border-[#0a0a1a] border-t-transparent rounded-full animate-spin motion-reduce:hidden" />
                )}
                {saving ? t("saving") : t("saveSettings")}
              </button>
            </div>
          ) : null}
        </section>

        {/* ── Section B: Notifications ───────────────────────────────── */}
        <section className="bg-surface-elevated/40 border border-border-subtle rounded-2xl p-6">
          <header className="mb-5">
            <h2 className="font-semibold text-[15px] text-text-primary">
              {t("notifications")}
            </h2>
            <p className="mt-1 text-[13px] text-text-tertiary">
              {t("notificationsSubtitle")}
            </p>
          </header>

          <div className="flex flex-col gap-5">
            {/* Telegram alerts toggle + connection status */}
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-text-primary">
                  {t("telegramAlerts")}
                </p>
                <p className="mt-0.5 text-[12px] text-text-tertiary">
                  {telegramOn ? t("telegramConnected") : t("telegramNotConnected")}
                </p>
              </div>
              <button
                role="switch"
                aria-checked={telegramOn}
                aria-label={t("telegramAlerts")}
                onClick={handleToggleTelegram}
                disabled={telegramBusy}
                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 disabled:opacity-50 ${
                  telegramOn ? "bg-gold" : "bg-white/15"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                    telegramOn ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            {/* Telegram Chat ID — supported by current contract; clearly labeled */}
            {settings && (
              <label className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("telegramChatId")}
                </span>
                <input
                  type="text"
                  value={settings.telegram_chat_id}
                  onChange={(e) =>
                    setSettings({ ...settings, telegram_chat_id: e.target.value })
                  }
                  placeholder={t("telegramPlaceholder")}
                  className="bg-surface border border-border-soft rounded-lg px-3 py-2 text-[13px] text-text-primary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                />
                <span className="text-[11px] text-text-tertiary">
                  {t("telegramChatIdHint")}
                </span>
              </label>
            )}
          </div>
        </section>

        {/* ── Section C: Account ─────────────────────────────────────── */}
        <section className="bg-surface-elevated/40 border border-border-subtle rounded-2xl p-6">
          <header className="mb-5">
            <h2 className="font-semibold text-[15px] text-text-primary">
              {t("account")}
            </h2>
          </header>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] font-semibold text-text-secondary">
                {t("emailAddress")}
              </span>
              <p className="text-[13px] text-text-primary">{user?.email ?? "—"}</p>
            </div>

            <a
              href="/forgot-password"
              className="self-start text-[13px] text-gold underline-offset-2 hover:underline"
            >
              {t("changePassword")}
            </a>

            <div className="pt-4 mt-1 border-t border-border-subtle flex flex-wrap gap-4">
              <a
                href="/terms"
                className="text-[12px] text-text-tertiary hover:text-text-primary transition-colors"
              >
                {t("termsOfService")}
              </a>
              <a
                href="/privacy"
                className="text-[12px] text-text-tertiary hover:text-text-primary transition-colors"
              >
                {t("privacyPolicy")}
              </a>
              <a
                href="/refund-policy"
                className="text-[12px] text-text-tertiary hover:text-text-primary transition-colors"
              >
                {t("refundPolicy")}
              </a>
            </div>
          </div>
        </section>
      </div>
      <ToastContainer toasts={toasts} />
    </DashboardShell>
  );
}
