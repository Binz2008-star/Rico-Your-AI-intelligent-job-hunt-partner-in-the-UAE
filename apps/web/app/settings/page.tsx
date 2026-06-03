"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/shared/ErrorState";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { useLanguage } from "@/contexts/LanguageContext";
import { ApiError, fetchMe, getHealth, getSettings, updateSettings } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import type { HealthResponse, SettingsResponse } from "@/types";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";

// ── Shared primitives ────────────────────────────────────────────────────────

function SectionCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-elevated/40 p-6 backdrop-blur-md ${className}`}>
      <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-gold/5 blur-3xl" aria-hidden="true" />
      <div className="relative">{children}</div>
    </section>
  );
}

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="mb-5 flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gold/20 bg-gold/10 text-gold" aria-hidden="true">
        {icon}
      </div>
      <div>
        <h2 className="text-[15px] font-bold text-text-primary">{title}</h2>
        <p className="mt-0.5 text-[12px] text-text-tertiary">{subtitle}</p>
      </div>
    </div>
  );
}

function ComingSoonBadge() {
  return (
    <span className="rounded-md border border-border-soft bg-surface-glass px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-text-muted">
      Coming soon
    </span>
  );
}

function FieldRow({
  label,
  helper,
  children,
  comingSoon = false,
}: {
  label: string;
  helper?: string;
  children?: React.ReactNode;
  comingSoon?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-border-subtle/50 py-3.5 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-text-primary">{label}</span>
          {comingSoon && <ComingSoonBadge />}
        </div>
        {helper && <p className="mt-0.5 text-[11px] text-text-tertiary">{helper}</p>}
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </div>
  );
}

function HealthRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border-subtle/50 last:border-0">
      <span className="text-[12px] text-text-tertiary">{label}</span>
      <span className={`text-[12px] font-medium flex items-center gap-1.5 ${ok === true ? "text-rico-teal" : ok === false ? "text-rico-red" : "text-text-muted"}`}>
        {ok === true && <span className="w-1.5 h-1.5 rounded-full bg-rico-teal" />}
        {ok === false && <span className="w-1.5 h-1.5 rounded-full bg-rico-red" />}
        {value}
      </span>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user, ready } = useAuth();
  const { toasts, toast } = useToast();
  const { language, setLanguage } = useLanguage();
  const t = useTranslation(language);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(!MAINTENANCE_MODE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<"auth" | "other" | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);

  // Keyword editing state
  const [includeInput, setIncludeInput] = useState("");
  const [excludeInput, setExcludeInput] = useState("");

  const isAdmin = userRole === "admin";

  // ── Health ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (MAINTENANCE_MODE) return;
    getHealth()
      .then(setHealth)
      .catch(() => {/* health is optional, fail silently */});
  }, []);

  // ── Settings load ──────────────────────────────────────────────────────────
  const loadSettings = useCallback(async () => {
    if (MAINTENANCE_MODE || !user) {
      setLoadingSettings(false);
      return;
    }
    try {
      const response = await getSettings();
      setSettings(response);
      setIncludeInput((response.include_keywords ?? []).join(", "));
      setExcludeInput((response.exclude_keywords ?? []).join(", "));
      setError(null);
    } catch (err) {
      const is401 = err instanceof ApiError && err.statusCode === 401;
      setError(is401 ? "auth" : "other");
    } finally {
      setLoadingSettings(false);
    }
  }, [user]);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setLoadingSettings(false);
      return;
    }
    void loadSettings();
  }, [ready, user, loadSettings]);

  // ── Role fetch ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!user || MAINTENANCE_MODE) { setUserRole(null); return; }
    let active = true;
    fetchMe()
      .then((me) => { if (active) setUserRole(me.role ?? null); })
      .catch(() => { if (active) setUserRole(null); });
    return () => { active = false; };
  }, [user]);

  // ── Save ───────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const parseKeywords = (raw: string) =>
        raw.split(",").map((s) => s.trim()).filter(Boolean);

      const updated = await updateSettings({
        min_score: settings.min_score,
        max_daily_applies: settings.max_daily_applies,
        score_threshold_apply: settings.score_threshold_apply,
        score_threshold_watch: settings.score_threshold_watch,
        telegram_chat_id: settings.telegram_chat_id,
        include_keywords: parseKeywords(includeInput),
        exclude_keywords: parseKeywords(excludeInput),
      });
      setSettings(updated);
      setIncludeInput((updated.include_keywords ?? []).join(", "));
      setExcludeInput((updated.exclude_keywords ?? []).join(", "));
      toast(t("settingsSaved"), "success");
    } catch (err) {
      const is401 = err instanceof ApiError && err.statusCode === 401;
      toast(is401 ? t("sessionExpiredLogIn") : t("saveFailed"), "error");
    } finally {
      setSaving(false);
    }
  };

  const isMock = process.env.NEXT_PUBLIC_USE_MOCK === "true";
  const telegramConfigured = Boolean(settings?.telegram_chat_id?.trim());

  return (
    <AppShell title="Rico Setup Center" subtitle="Tell Rico how to search, score, speak, and support your job hunt.">
      <div className="max-w-3xl flex flex-col gap-6">

        {/* Maintenance banner */}
        {MAINTENANCE_MODE && (
          <div className="rounded-2xl border border-gold/35 bg-gold/8 px-5 py-4">
            <p className="text-[13px] font-semibold text-gold">{t("backendMaintenance")}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-gold/70">{t("backendMaintenanceDescription")}</p>
          </div>
        )}

        {/* ── 1. Rico Identity / Personalization ─────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg>}
            title="Rico Identity"
            subtitle="Personalise how Rico addresses you and presents information."
          />
          <FieldRow
            label="Your name"
            helper="Rico uses this when addressing you in conversations."
            comingSoon={false}
          >
            <Link href="/profile" className="text-[12px] px-3 py-1.5 rounded-lg border border-gold/30 bg-gold/10 text-gold hover:bg-gold/20 transition-colors">
              Edit in Profile
            </Link>
          </FieldRow>
          <FieldRow label="Preferred language" helper="Controls the language of Rico's responses.">
            <div className="flex gap-1.5 rounded-lg border border-border-soft bg-surface-glass p-0.5">
              {(["en", "ar"] as const).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setLanguage(lang)}
                  className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${language === lang ? "bg-gold text-[#0a0a1a]" : "text-text-secondary hover:text-text-primary"}`}
                >
                  {lang === "en" ? "English" : "العربية"}
                </button>
              ))}
            </div>
          </FieldRow>
          <FieldRow label="Response tone" helper="Direct and short, friendly, or professional." comingSoon />
          <FieldRow label="Explanation depth" helper="How much Rico explains its reasoning per answer." comingSoon />
        </SectionCard>

        {/* ── 2. Career Targeting ──────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="3" /></svg>}
            title="Career Targeting"
            subtitle="Tell Rico what you're looking for and what to avoid."
          />
          <FieldRow label="Target roles" helper="Job titles Rico should prioritise when searching.">
            <Link href="/profile" className="text-[12px] px-3 py-1.5 rounded-lg border border-gold/30 bg-gold/10 text-gold hover:bg-gold/20 transition-colors">
              Edit in Profile
            </Link>
          </FieldRow>
          <FieldRow label="Preferred UAE / GCC cities" helper="Dubai, Abu Dhabi, Riyadh, etc.">
            <Link href="/profile" className="text-[12px] px-3 py-1.5 rounded-lg border border-gold/30 bg-gold/10 text-gold hover:bg-gold/20 transition-colors">
              Edit in Profile
            </Link>
          </FieldRow>
          <FieldRow label="Minimum salary (AED/month)" helper="Rico will skip roles that don't meet this threshold.">
            <Link href="/profile" className="text-[12px] px-3 py-1.5 rounded-lg border border-gold/30 bg-gold/10 text-gold hover:bg-gold/20 transition-colors">
              Edit in Profile
            </Link>
          </FieldRow>
          <FieldRow label="Industries" helper="Sectors Rico should focus on or avoid." comingSoon />
          <FieldRow label="Companies to avoid" helper="Rico will exclude these employers from results." comingSoon />
          <FieldRow label="Work arrangement" helper="On-site, hybrid, or remote." comingSoon />
          <FieldRow label="Visa / notice period" helper="Helps Rico filter by eligibility.">
            <Link href="/profile" className="text-[12px] px-3 py-1.5 rounded-lg border border-gold/30 bg-gold/10 text-gold hover:bg-gold/20 transition-colors">
              Edit in Profile
            </Link>
          </FieldRow>
        </SectionCard>

        {/* ── 3. Job Search Rules ──────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>}
            title="Job Search Rules"
            subtitle="Control how Rico scores, filters, and surfaces job matches."
          />

          {loadingSettings ? (
            <div className="flex flex-col gap-3 py-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-10 rounded-lg bg-surface-glass animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <ErrorState
              variant={error === "auth" ? "auth" : "network"}
              onRetry={() => { setError(null); setLoadingSettings(true); void loadSettings(); }}
            />
          ) : !user && ready ? (
            <p className="text-[13px] text-text-muted py-4 text-center">
              Sign in to manage your job search rules.
            </p>
          ) : settings ? (
            <div className="flex flex-col gap-0">
              {/* Min fit score */}
              <FieldRow label="Minimum fit score" helper={`${settings.min_score}% — Rico skips jobs below this score.`}>
                <div className="flex w-44 flex-col gap-1">
                  <input
                    type="range" min={50} max={95} step={5}
                    aria-label="Minimum fit score"
                    value={settings.min_score}
                    onChange={(e) => setSettings({ ...settings, min_score: Number(e.target.value) })}
                    className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-gold"
                  />
                  <div className="flex justify-between text-[9px] text-text-tertiary font-semibold uppercase tracking-tight">
                    <span>General</span><span>High match only</span>
                  </div>
                </div>
              </FieldRow>

              {/* Max daily applies */}
              <FieldRow label="Apply pacing (per day)" helper={`${settings.max_daily_applies} applications — prevents spam applying.`}>
                <div className="flex w-44 flex-col gap-1">
                  <input
                    type="range" min={0} max={50} step={1}
                    aria-label="Apply pacing"
                    value={settings.max_daily_applies}
                    onChange={(e) => setSettings({ ...settings, max_daily_applies: Number(e.target.value) })}
                    className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-gold"
                  />
                  <div className="flex justify-between text-[9px] text-text-tertiary font-semibold uppercase tracking-tight">
                    <span>Safe</span><span>Aggressive</span>
                  </div>
                </div>
              </FieldRow>

              {/* Thresholds */}
              <div className="border-b border-border-subtle/50 py-3.5 last:border-0">
                <p className="mb-3 text-[13px] font-medium text-text-primary">Score thresholds</p>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1">
                    <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">Auto-apply above</span>
                    <input
                      type="number" min={0} max={100}
                      value={settings.score_threshold_apply}
                      onChange={(e) => setSettings({ ...settings, score_threshold_apply: Number(e.target.value) })}
                      className="rounded-lg bg-surface border border-border-soft px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-gold/40"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">Watch above</span>
                    <input
                      type="number" min={0} max={100}
                      value={settings.score_threshold_watch}
                      onChange={(e) => setSettings({ ...settings, score_threshold_watch: Number(e.target.value) })}
                      className="rounded-lg bg-surface border border-border-soft px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-gold/40"
                    />
                  </label>
                </div>
              </div>

              {/* Include keywords */}
              <div className="border-b border-border-subtle/50 py-3.5 last:border-0">
                <label className="flex flex-col gap-1.5">
                  <div>
                    <span className="text-[13px] font-medium text-text-primary">Include keywords</span>
                    <p className="mt-0.5 text-[11px] text-text-tertiary">Rico boosts jobs containing these terms.</p>
                  </div>
                  <input
                    type="text"
                    value={includeInput}
                    onChange={(e) => setIncludeInput(e.target.value)}
                    placeholder="e.g. React, fintech, Dubai, remote"
                    className="rounded-lg bg-surface border border-border-soft px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                  />
                  <p className="text-[10px] text-text-tertiary">Comma-separated</p>
                </label>
              </div>

              {/* Exclude keywords */}
              <div className="py-3.5">
                <label className="flex flex-col gap-1.5">
                  <div>
                    <span className="text-[13px] font-medium text-text-primary">Exclude keywords</span>
                    <p className="mt-0.5 text-[11px] text-text-tertiary">Rico hides jobs containing these terms.</p>
                  </div>
                  <input
                    type="text"
                    value={excludeInput}
                    onChange={(e) => setExcludeInput(e.target.value)}
                    placeholder="e.g. junior, unpaid, commission only"
                    className="rounded-lg bg-surface border border-border-soft px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                  />
                  <p className="text-[10px] text-text-tertiary">Comma-separated</p>
                </label>
              </div>

              <div className="mt-1 flex items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 rounded-lg bg-gold/10 text-gold border border-gold/30 text-[13px] font-semibold hover:bg-gold/20 transition-all disabled:opacity-40 flex items-center gap-2"
                >
                  {saving && <span className="w-3 h-3 border-2 border-gold border-t-transparent rounded-full animate-spin" />}
                  {saving ? t("saving") : t("saveSettings")}
                </button>
                {saving && (
                  <span className="text-[11px] text-text-tertiary uppercase tracking-widest">{t("statusSyncing")}</span>
                )}
              </div>
            </div>
          ) : null}

          {/* Non-wired search rules */}
          <div className={`${settings ? "mt-4 border-t border-border-subtle/50 pt-4" : ""} flex flex-col`}>
            <FieldRow label="Job freshness window" helper="Only show jobs posted within this many days." comingSoon />
            <FieldRow label="Seniority level" helper="Entry, mid, senior, executive." comingSoon />
            <FieldRow label="Prefer direct employer posts" helper="Deprioritise recruiter or aggregator listings." comingSoon />
            <FieldRow label="Auto-broaden if no matches" helper="Rico expands search terms when results are thin." comingSoon />
          </div>
        </SectionCard>

        {/* ── 4. Rico AI Skills ─────────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>}
            title="Rico AI Skills"
            subtitle="The capabilities Rico can use during your job hunt. All active by default."
          />
          {[
            { label: "Find live jobs", helper: "Search UAE and GCC job boards for matching roles.", active: true },
            { label: "Score job fit", helper: "Rate each job against your CV and preferences.", active: true },
            { label: "Explain why a job matches", helper: "Rico gives reasons for each recommendation.", active: true },
            { label: "Prepare application messages", helper: "Draft cover letters and outreach messages.", active: true },
            { label: "Track applications", helper: "Log applied jobs and their status.", active: true },
            { label: "Follow-up reminders", helper: "Remind you when to chase applications.", active: true },
            { label: "Telegram alerts", helper: "Push new matches to Telegram.", active: telegramConfigured },
            { label: "CV improvement advice", helper: "Suggest profile and CV improvements.", active: true },
            { label: "Interview preparation", helper: "Coaching, mock questions, and tips.", active: true },
          ].map(({ label, helper, active }) => (
            <FieldRow key={label} label={label} helper={helper} comingSoon>
              <span className={`text-[11px] font-semibold ${active ? "text-rico-teal" : "text-text-muted"}`}>
                {active ? "Active" : "Inactive"}
              </span>
            </FieldRow>
          ))}
        </SectionCard>

        {/* ── 5. Communication Channels ─────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.18h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.96a16 16 0 0 0 6.13 6.13l.95-.95a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" /></svg>}
            title="Communication Channels"
            subtitle="Where Rico reaches you — configure your preferred notification channel."
          />

          {/* Telegram — wired */}
          <div className="border-b border-border-subtle/50 py-3.5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[13px] font-medium text-text-primary">Telegram notifications</p>
                <p className="mt-0.5 text-[11px] text-text-tertiary">
                  {MAINTENANCE_MODE
                    ? t("telegramPaused")
                    : telegramConfigured
                      ? t("telegramConfigured")
                      : t("telegramNotConfigured")}
                </p>
              </div>
              <span className={`shrink-0 text-[11px] font-semibold ${telegramConfigured ? "text-rico-teal" : "text-gold"}`}>
                {telegramConfigured ? "Active" : "Not configured"}
              </span>
            </div>
            {settings && (
              <label className="mt-3 flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">{t("telegramChatId")}</span>
                <input
                  type="text"
                  value={settings.telegram_chat_id}
                  onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                  placeholder={t("telegramPlaceholder")}
                  className="rounded-lg bg-surface border border-border-soft px-3 py-2 text-[13px] text-text-secondary outline-none focus:border-gold/40 placeholder:text-text-tertiary"
                />
              </label>
            )}
          </div>

          <FieldRow label="WhatsApp support" helper="Direct access to Rico support team." comingSoon />
          <FieldRow label="Email notifications" helper="Job digests and application updates." comingSoon />

          {/* Notification types */}
          <div className="mt-3 space-y-0">
            {[
              { label: "New job matches", helper: "When Rico finds a role above your fit score." },
              { label: "Saved job updates", helper: "When a saved role closes or changes." },
              { label: "Follow-up reminders", helper: "When you should chase an application." },
              { label: "Application status updates", helper: "When a status change is detected." },
            ].map(({ label, helper }) => (
              <FieldRow key={label} label={label} helper={helper} comingSoon />
            ))}
          </div>

          {settings && (
            <div className="mt-4 flex items-center gap-3 border-t border-border-subtle/50 pt-4">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-gold/10 text-gold border border-gold/30 text-[13px] font-semibold hover:bg-gold/20 transition-all disabled:opacity-40 flex items-center gap-2"
              >
                {saving && <span className="w-3 h-3 border-2 border-gold border-t-transparent rounded-full animate-spin" />}
                {saving ? t("saving") : t("saveSettings")}
              </button>
            </div>
          )}
        </SectionCard>

        {/* ── 6. Privacy and Control ────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>}
            title="Privacy and Control"
            subtitle="Your data, your rules. Rico only uses what you share."
          />
          <FieldRow
            label="Rico can use CV data for matching"
            helper="Extracted fields are used to score job fit. Nothing is shared externally."
          >
            <span className="text-[11px] font-semibold text-rico-teal">On</span>
          </FieldRow>
          <FieldRow
            label="Rico remembers career preferences"
            helper="Your profile and targeting rules persist across sessions."
          >
            <span className="text-[11px] font-semibold text-rico-teal">On</span>
          </FieldRow>
          <FieldRow label="Clear saved preferences" helper="Reset job search rules to default values." comingSoon />
          <FieldRow label="Export profile and preferences" helper="Download a copy of everything Rico knows about you." comingSoon />
          <FieldRow label="Delete account" helper="Permanently remove your data.">
            <a
              href="mailto:support@ricohunt.com?subject=Account+deletion+request"
              className="text-[12px] px-3 py-1.5 rounded-lg border border-rico-red/30 bg-rico-red/5 text-rico-red hover:bg-rico-red/10 transition-colors"
            >
              Contact support
            </a>
          </FieldRow>
        </SectionCard>

        {/* ── 7. Backend Status — Admin Only ────────────────────────────────── */}
        {isAdmin && (
          <SectionCard>
            <SectionHeader
              icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>}
              title="System Status"
              subtitle="Backend health — visible to admin accounts only."
            />
            {health ? (
              (() => {
                const rico = health.rico;
                const readyForHf = health.ready_for_hf ?? rico?.ready_for_hf ?? false;
                const readyForOpenAI = health.ready_for_openai ?? rico?.ready_for_openai ?? health.openai ?? false;
                const readyForDeepSeek = health.ready_for_deepseek ?? rico?.ready_for_deepseek ?? false;
                const readyForJotform = health.ready_for_jotform ?? rico?.ready_for_jotform ?? false;
                const readyForTelegram = health.telegram ?? rico?.ready_for_telegram ?? false;
                const aiProvider = health.ai_provider ?? rico?.ai_provider ?? "unknown";
                const dbStatus = health.database ?? health.db ?? (rico?.ready_for_db ? "connected" : "unknown");
                return (
                  <>
                    <HealthRow label={t("service")} value={health.service ?? "—"} />
                    <HealthRow label={t("status")} value={health.status} ok={health.status === "ok" || health.status === "healthy"} />
                    <HealthRow label={t("database")} value={dbStatus} ok={dbStatus === "connected"} />
                    <HealthRow label={t("aiProvider")} value={aiProvider} ok={readyForHf || readyForOpenAI || readyForDeepSeek} />
                    <HealthRow label={t("deepSeek")} value={readyForDeepSeek ? t("active") : t("notActive")} ok={readyForDeepSeek} />
                    <HealthRow label={t("openai")} value={readyForOpenAI ? t("active") : t("notActive")} ok={readyForOpenAI} />
                    <HealthRow label={t("huggingFace")} value={readyForHf ? t("configured") : t("notConfigured")} ok={readyForHf} />
                    <HealthRow label={t("jotform")} value={readyForJotform ? t("configured") : t("notConfigured")} ok={readyForJotform} />
                    <HealthRow label={t("telegram")} value={readyForTelegram ? t("connected") : t("notConfigured")} ok={readyForTelegram} />
                    <HealthRow label={t("version")} value={`v${health.version ?? "0"}`} />
                  </>
                );
              })()
            ) : (
              <p className="text-[12px] text-text-muted py-2">Backend status unavailable.</p>
            )}
            {isMock && (
              <div className="mt-4 border-t border-border-subtle/50 pt-4">
                <HealthRow label={t("mockMode")} value={t("mockEnabled")} ok={false} />
              </div>
            )}
          </SectionCard>
        )}

        {/* ── Legal ─────────────────────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>}
            title="Legal"
            subtitle="Documents governing your use of Rico."
          />
          <div className="flex flex-wrap gap-3 pt-1">
            {[
              { label: t("termsOfService"), href: "/terms" },
              { label: t("privacyPolicy"), href: "/privacy" },
              { label: t("refundPolicy"), href: "/refund-policy" },
            ].map(({ label, href }) => (
              <a
                key={href}
                href={href}
                className="text-[13px] text-text-tertiary hover:text-text-primary transition-colors underline underline-offset-2"
              >
                {label}
              </a>
            ))}
          </div>
        </SectionCard>

      </div>
      <ToastContainer toasts={toasts} />
    </AppShell>
  );
}
