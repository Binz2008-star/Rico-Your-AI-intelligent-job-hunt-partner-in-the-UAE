"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/shared/ErrorState";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { StatusCard } from "@/components/StatusCard";
import { KeywordTagInput } from "@/components/ui/KeywordTagInput";
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
  logout,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

export default function SettingsPage() {
  const { user } = useAuth();
  const { toasts, toast } = useToast();
  const { language } = useLanguage();
  const t = useTranslation(language);
  const router = useRouter();

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [includeTags, setIncludeTags] = useState<string[]>([]);
  const [excludeTags, setExcludeTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<"auth" | "other" | null>(null);

  // Telegram status loads independently and must never block the page.
  const [telegram, setTelegram] = useState<TelegramStatusResponse | null>(null);
  // useRef so rapid clicks cannot slip through between state batches.
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
      setIncludeTags(response.include_keywords ?? []);
      setExcludeTags(response.exclude_keywords ?? []);
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
        include_keywords: includeTags,
        exclude_keywords: excludeTags,
        min_score: settings.min_score,
        max_daily_applies: settings.max_daily_applies,
        telegram_chat_id: settings.telegram_chat_id,
        // Preserved in the payload (backend contract) but not user-facing.
        score_threshold_apply: settings.score_threshold_apply,
        score_threshold_watch: settings.score_threshold_watch,
      });
      setSettings(updated);
      setIncludeTags(updated.include_keywords ?? []);
      setExcludeTags(updated.exclude_keywords ?? []);
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
  const inputClass =
    "w-full rounded-lg border border-border-soft bg-surface-glass px-3 py-2 text-sm text-text-primary outline-none transition focus:border-rico-accent placeholder:text-text-tertiary";

  return (
    <AppShell
      title={t("settings")}
      subtitle={t("settingsSubtitle")}
      sidebarProps={{
        user: user ? { name: user.name ?? undefined, email: user.email } : undefined,
        onLogout: handleLogout,
      }}
    >
      <div
        dir={language === "ar" ? "rtl" : "ltr"}
        className="flex w-full max-w-2xl flex-col gap-6 text-start"
      >
        {/* ── Section A: Job Filters ─────────────────────────────────── */}
        <StatusCard
          title={t("jobFilters")}
          className="min-h-0"
        >
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 animate-pulse rounded-lg bg-surface-subtle/50 motion-reduce:animate-none"
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
              <div className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("includeKeywords")}
                </span>
                <KeywordTagInput
                  tags={includeTags}
                  onChange={setIncludeTags}
                  placeholder={t("keywordsPlaceholder")}
                  hint={t("keywordTagHint")}
                  disabled={saving}
                  label={t("includeKeywords")}
                />
                <span className="text-[11px] text-text-tertiary">
                  {t("includeKeywordsHint")}
                </span>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("excludeKeywords")}
                </span>
                <KeywordTagInput
                  tags={excludeTags}
                  onChange={setExcludeTags}
                  placeholder={t("keywordsPlaceholder")}
                  hint={t("keywordTagHint")}
                  disabled={saving}
                  label={t("excludeKeywords")}
                />
                <span className="text-[11px] text-text-tertiary">
                  {t("excludeKeywordsHint")}
                </span>
              </div>

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold text-text-secondary">
                  {t("minimumFitScore")}
                  <span className="text-rico-accent">{settings.min_score}%</span>
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
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-white/5 accent-rico-accent"
                />
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight text-text-tertiary">
                  <span>{t("general")}</span>
                  <span>{t("highMatchOnly")}</span>
                </div>
              </label>

              <GuardrailWarnings warnings={settings.warnings} language={language} />

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold text-text-secondary">
                  {t("dailyApplyLimit")}
                  <span className="text-rico-accent">{settings.max_daily_applies}</span>
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
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-white/5 accent-rico-accent"
                />
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight text-text-tertiary">
                  <span>{t("safety")}</span>
                  <span>{t("aggressive")}</span>
                </div>
              </label>

              <button
                onClick={handleSave}
                disabled={saving}
                className="mt-1 inline-flex items-center gap-2 self-start rounded-lg bg-rico-accent px-4 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rico-accent/50 disabled:opacity-40"
              >
                {saving && (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[#0a0a1a] border-t-transparent motion-reduce:hidden" />
                )}
                {saving ? t("saving") : t("saveSettings")}
              </button>
            </div>
          ) : null}
        </StatusCard>

        {/* ── Section B: Notifications ───────────────────────────────── */}
        <StatusCard
          title={t("notifications")}
          className="min-h-0"
        >
          <div className="flex flex-col gap-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-text-primary">
                  {t("telegramAlerts")}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-[12px] text-text-tertiary">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${telegramOn ? "bg-emerald-400" : "bg-text-tertiary/50"}`}
                  />
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
                  telegramOn ? "bg-rico-accent" : "bg-white/15"
                }`}
              >
                <span
                  className={`absolute top-0.5 start-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                    telegramOn ? "translate-x-5 rtl:-translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            {settings && (
              <div className="flex flex-col gap-3 border-t border-overlay/10 pt-5">
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
                    className={inputClass}
                  />
                  <span className="text-[11px] text-text-tertiary">
                    {t("telegramChatIdHint")}
                  </span>
                </label>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 self-start rounded-lg bg-rico-accent px-4 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rico-accent/50 disabled:opacity-40"
                >
                  {saving && (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent motion-reduce:hidden" />
                  )}
                  {saving ? t("saving") : t("saveSettings")}
                </button>
              </div>
            )}
          </div>
        </StatusCard>

        {/* ── Section C: Account ─────────────────────────────────────── */}
        <StatusCard title={t("account")} className="min-h-0">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] font-semibold text-text-secondary">
                {t("emailAddress")}
              </span>
              <p className="text-[13px] text-text-primary">{user?.email ?? "—"}</p>
            </div>

            <a
              href="/forgot-password"
              className="inline-flex items-center gap-1.5 self-start text-[13px] text-magenta underline-offset-2 hover:underline hover:text-magenta-hover transition-colors"
            >
              {t("changePassword")}
            </a>

            <div className="mt-1 flex flex-wrap gap-4 border-t border-overlay/10 pt-4">
              <a
                href="/terms"
                className="text-[12px] text-text-tertiary transition-colors hover:text-text-primary"
              >
                {t("termsOfService")}
              </a>
              <a
                href="/privacy"
                className="text-[12px] text-text-tertiary transition-colors hover:text-text-primary"
              >
                {t("privacyPolicy")}
              </a>
              <a
                href="/refund-policy"
                className="text-[12px] text-text-tertiary transition-colors hover:text-text-primary"
              >
                {t("refundPolicy")}
              </a>
            </div>
          </div>
        </StatusCard>
      </div>
      <ToastContainer toasts={toasts} />
    </AppShell>
  );
}
