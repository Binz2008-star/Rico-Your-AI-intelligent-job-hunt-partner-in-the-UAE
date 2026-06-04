"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/shared/ErrorState";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
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
import { useCallback, useEffect, useState } from "react";

function splitKeywords(value: string): string[] {
  return value
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

interface SectionCardProps {
  icon: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

function SectionCard({ icon, title, subtitle, children }: SectionCardProps) {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-overlay/10 bg-surface/60 p-5 backdrop-blur-sm sm:p-6">
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-gold/5 blur-3xl" aria-hidden="true" />
      <header className="mb-5 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gold/10">
          <MaterialIcon icon={icon} size={18} className="text-gold" />
        </div>
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-text-primary">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 text-[13px] text-text-tertiary">{subtitle}</p>
          )}
        </div>
      </header>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { toasts, toast } = useToast();
  const { language } = useLanguage();
  const t = useTranslation(language);
  const router = useRouter();

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [includeStr, setIncludeStr] = useState("");
  const [excludeStr, setExcludeStr] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<"auth" | "other" | null>(null);

  // Telegram status loads independently and must never block the page.
  const [telegram, setTelegram] = useState<TelegramStatusResponse | null>(null);
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
  const inputClass =
    "w-full rounded-lg border border-overlay/10 bg-surface-subtle/60 px-3 py-2.5 text-[13px] text-text-primary outline-none transition-colors focus:border-gold/40 placeholder:text-text-tertiary";

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
        <SectionCard
          icon="work"
          title={t("jobFilters")}
          subtitle={t("jobFiltersSubtitle")}
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
              <label className="flex flex-col gap-1.5">
                <span className="text-[12px] font-semibold text-text-secondary">
                  {t("includeKeywords")}
                </span>
                <input
                  type="text"
                  value={includeStr}
                  onChange={(e) => setIncludeStr(e.target.value)}
                  placeholder={t("keywordsPlaceholder")}
                  className={inputClass}
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
                  className={inputClass}
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
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-white/5 accent-gold"
                />
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight text-text-tertiary">
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
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-white/5 accent-gold"
                />
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight text-text-tertiary">
                  <span>{t("safety")}</span>
                  <span>{t("aggressive")}</span>
                </div>
              </label>

              <button
                onClick={handleSave}
                disabled={saving}
                className="mt-1 inline-flex items-center gap-2 self-start rounded-lg bg-gold px-4 py-2.5 text-[13px] font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 disabled:opacity-40"
              >
                {saving && (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[#0a0a1a] border-t-transparent motion-reduce:hidden" />
                )}
                {saving ? t("saving") : t("saveSettings")}
              </button>
            </div>
          ) : null}
        </SectionCard>

        {/* ── Section B: Notifications ───────────────────────────────── */}
        <SectionCard
          icon="send"
          title={t("notifications")}
          subtitle={t("notificationsSubtitle")}
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
                  telegramOn ? "bg-gold" : "bg-white/15"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                    telegramOn ? "left-0.5 translate-x-5" : "left-0.5 translate-x-0"
                  }`}
                />
              </button>
            </div>

            {settings && (
              <label className="flex flex-col gap-1.5 border-t border-overlay/10 pt-5">
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
            )}
          </div>
        </SectionCard>

        {/* ── Section C: Account ─────────────────────────────────────── */}
        <SectionCard icon="account_circle" title={t("account")}>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] font-semibold text-text-secondary">
                {t("emailAddress")}
              </span>
              <p className="text-[13px] text-text-primary">{user?.email ?? "—"}</p>
            </div>

            <a
              href="/forgot-password"
              className="inline-flex items-center gap-1.5 self-start text-[13px] text-gold underline-offset-2 hover:underline"
            >
              <MaterialIcon icon="lock_reset" size={15} />
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
        </SectionCard>
      </div>
      <ToastContainer toasts={toasts} />
    </AppShell>
  );
}
