"use client";

import { AuthGate } from "@/components/auth/AuthGate";
import { SettingsAtelier } from "@/components/settings/SettingsAtelier";
import { ToastContainer } from "@/components/ui/Toast";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useToast } from "@/hooks/useToast";
import {
  ApiError,
  getSettings,
  getTelegramStatus,
  logout,
  telegramOptIn,
  telegramOptOut,
  updateSettings,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

function splitKeywords(value: string): string[] {
  return value
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  // Authenticated-only: guests are redirected to /login?next=/settings and see
  // a neutral loader (never the private AppShell); `user` stays null until an
  // authenticated identity is confirmed, so no private API fires for a guest.
  const { user, authorized } = useRequireAuth();
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

  const updateSetting = useCallback((patch: Partial<SettingsResponse>) => {
    setSettings((current: SettingsResponse | null) => (current ? { ...current, ...patch } : null));
  }, []);

  // Never render the private shell until an authenticated identity is confirmed.
  if (!authorized) return <AuthGate />;

  return (
    <WorkspaceShell>
      <SettingsAtelier
        userEmail={user?.email ?? undefined}
        settings={settings}
        includeStr={includeStr}
        excludeStr={excludeStr}
        loading={loading}
        saving={saving}
        error={error}
        telegram={telegram}
        telegramBusy={telegramBusy}
        onIncludeChange={setIncludeStr}
        onExcludeChange={setExcludeStr}
        onSettingsChange={updateSetting}
        onSave={() => void handleSave()}
        onToggleTelegram={() => void handleToggleTelegram()}
        onRetry={() => void loadSettings()}
        onLogout={handleLogout}
      />
      <ToastContainer toasts={toasts} />
    </WorkspaceShell>
  );
}
