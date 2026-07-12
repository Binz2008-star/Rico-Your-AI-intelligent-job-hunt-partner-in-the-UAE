"use client";

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import type { SettingsResponse, TelegramStatusResponse } from "@/types";
import Link from "next/link";

const SERIF = ATELIER_FONT.serif;

function ThemedPlate({
  children,
  className = "",
  palette,
}: {
  children: React.ReactNode;
  className?: string;
  palette: WorkspacePalette;
}) {
  const tick = "absolute h-2 w-2 pointer-events-none";
  const border = `1px solid ${palette.hair}`;

  return (
    <div
      className={`relative rounded-[4px] ${className}`}
      style={{ background: palette.panel, border: `1px solid ${palette.hair}` }}
    >
      <span className={`${tick} left-1.5 top-1.5`} style={{ borderLeft: border, borderTop: border }} aria-hidden="true" />
      <span className={`${tick} right-1.5 top-1.5`} style={{ borderRight: border, borderTop: border }} aria-hidden="true" />
      <span className={`${tick} bottom-1.5 left-1.5`} style={{ borderBottom: border, borderLeft: border }} aria-hidden="true" />
      <span className={`${tick} bottom-1.5 right-1.5`} style={{ borderBottom: border, borderRight: border }} aria-hidden="true" />
      {children}
    </div>
  );
}

function SectionTitle({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
  return (
    <Mono className="mb-4 block" style={{ color: palette.ink55 }}>
      {children}
    </Mono>
  );
}

function FieldLabel({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
  return (
    <span className="mb-1.5 block text-[12px] font-semibold" style={{ color: palette.ink70 }}>
      {children}
    </span>
  );
}

function FieldHint({ children, palette }: { children: React.ReactNode; palette: WorkspacePalette }) {
  return (
    <span className="mt-1.5 block text-[11px]" style={{ color: palette.ink40 }}>
      {children}
    </span>
  );
}

function Input({
  palette,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { palette: WorkspacePalette }) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg px-3 py-2 text-sm outline-none transition ${props.className ?? ""}`}
      style={{
        background: palette.inset,
        border: `1px solid ${palette.hair}`,
        color: palette.ink,
        ...props.style,
      }}
    />
  );
}

function RangeLabels({
  left,
  right,
  palette,
}: {
  left: string;
  right: string;
  palette: WorkspacePalette;
}) {
  return (
    <div className="flex justify-between text-[10px] font-bold uppercase tracking-tight" style={{ color: palette.ink40 }}>
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}

function AtelierButton({
  children,
  onClick,
  disabled,
  palette,
  variant = "primary",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  palette: WorkspacePalette;
  variant?: "primary" | "secondary";
}) {
  const primary = variant === "primary";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`settings-action inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-[13px] font-semibold transition disabled:opacity-40 ${primary ? "settings-primary-action" : ""}`}
      style={{
        background: primary ? palette.red : "transparent",
        color: primary ? palette.bg : palette.ink,
        border: `1px solid ${primary ? palette.red : palette.hair}`,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {children}
    </button>
  );
}

function LoadingSkeleton({ palette }: { palette: WorkspacePalette }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="h-10 animate-pulse rounded-lg motion-reduce:animate-none"
          style={{ background: palette.track }}
        />
      ))}
    </div>
  );
}

function ErrorCard({
  variant,
  onRetry,
  palette,
}: {
  variant: "auth" | "other";
  onRetry: () => void;
  palette: WorkspacePalette;
}) {
  const { language } = useLanguage();
  const t = useTranslation(language);

  return (
    <ThemedPlate className="p-6" palette={palette}>
      <div className="flex flex-col items-center gap-3 text-center">
        <div style={{ color: palette.red }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold" style={{ color: palette.ink }}>
          {variant === "auth" ? t("profileAuthRequired") : t("profileConnectionFailed")}
        </h3>
        <p className="max-w-sm text-sm" style={{ color: palette.ink70 }}>
          {variant === "auth" ? t("profileAuthRequiredMsg") : t("profileConnectionFailedMsg")}
        </p>
        <div className="flex flex-wrap gap-2">
          <AtelierButton onClick={onRetry} palette={palette}>
            {t("retry")}
          </AtelierButton>
          {variant === "auth" && (
            <Link
              href="/login"
              className="settings-action inline-flex items-center rounded-lg px-4 py-2.5 text-[13px] font-semibold"
              style={{ color: palette.ink, border: `1px solid ${palette.hair}` }}
            >
              {t("signIn")}
            </Link>
          )}
        </div>
      </div>
    </ThemedPlate>
  );
}

export interface SettingsAtelierProps {
  userEmail?: string;
  settings: SettingsResponse | null;
  includeStr: string;
  excludeStr: string;
  loading: boolean;
  saving: boolean;
  error: "auth" | "other" | null;
  telegram: TelegramStatusResponse | null;
  telegramBusy: boolean;
  onIncludeChange: (value: string) => void;
  onExcludeChange: (value: string) => void;
  onSettingsChange: (patch: Partial<SettingsResponse>) => void;
  onSave: () => void;
  onToggleTelegram: () => void;
  onRetry: () => void;
  onLogout: () => void;
}

export function SettingsAtelier({
  userEmail,
  settings,
  includeStr,
  excludeStr,
  loading,
  saving,
  error,
  telegram,
  telegramBusy,
  onIncludeChange,
  onExcludeChange,
  onSettingsChange,
  onSave,
  onToggleTelegram,
  onRetry,
  onLogout,
}: SettingsAtelierProps) {
  const { language } = useLanguage();
  const t = useTranslation(language);
  const palette = useWorkspaceTheme();
  const isAr = language === "ar";
  const telegramOn = Boolean(telegram?.opted_in);

  return (
    <div
      className="settings-atelier max-w-2xl"
      dir={isAr ? "rtl" : "ltr"}
      lang={language}
      style={{ color: palette.ink }}
    >
      <style dangerouslySetInnerHTML={{
        __html: `
        .settings-atelier input[type="text"]::placeholder { color: ${palette.ink40}; }
        .settings-atelier input[type="text"]:focus { border-color: ${palette.red} !important; }
        .settings-atelier input[type="range"] {
          -webkit-appearance: none;
          appearance: none;
          width: 100%;
          height: 6px;
          background: ${palette.track};
          border-radius: 4px;
          outline: none;
        }
        .settings-atelier input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: ${palette.red};
          cursor: pointer;
          border: 2px solid ${palette.panel};
        }
        .settings-atelier input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: ${palette.red};
          cursor: pointer;
          border: 2px solid ${palette.panel};
        }
        .settings-atelier [role="alert"] {
          border-color: ${palette.hair} !important;
          background: ${palette.inset} !important;
        }
        .settings-atelier [role="alert"] p {
          color: ${palette.ink} !important;
        }
        .settings-atelier [role="alert"] p + p {
          color: ${palette.ink70} !important;
        }
        .settings-atelier .settings-action {
          transition: border-color .15s ease, color .15s ease, transform .15s ease;
        }
        .settings-atelier .settings-action:hover:not(.settings-primary-action) {
          border-color: ${palette.red} !important;
          color: ${palette.red} !important;
        }
        .settings-atelier .settings-primary-action:hover {
          background: ${palette.bg} !important;
          color: ${palette.red} !important;
          border-color: ${palette.red} !important;
        }
        .settings-atelier .settings-action:focus-visible {
          outline: 2px solid ${palette.red};
          outline-offset: 2px;
        }
      ` }} />

      <header className="mb-6">
        <Mono style={{ color: palette.ink55 }}>{t("settings")}</Mono>
        <h1
          className="mt-2 text-[2rem] font-normal sm:text-[2.4rem]"
          style={{ fontFamily: SERIF, color: palette.ink, lineHeight: 1 }}
        >
          {t("settings")}
        </h1>
        <p className="mt-2 text-sm" style={{ color: palette.ink70 }}>
          {t("settingsSubtitle")}
        </p>
      </header>

      <div className="flex flex-col gap-5">
        {/* ── Job Filters ── */}
        <ThemedPlate className="p-5 sm:p-6" palette={palette}>
          <SectionTitle palette={palette}>{t("jobFilters")}</SectionTitle>

          {loading ? (
            <LoadingSkeleton palette={palette} />
          ) : error ? (
            <ErrorCard variant={error} onRetry={onRetry} palette={palette} />
          ) : settings ? (
            <div className="flex flex-col gap-5">
              <label className="flex flex-col">
                <FieldLabel palette={palette}>{t("includeKeywords")}</FieldLabel>
                <Input
                  type="text"
                  value={includeStr}
                  onChange={(e) => onIncludeChange(e.target.value)}
                  placeholder={t("keywordsPlaceholder")}
                  palette={palette}
                />
                <FieldHint palette={palette}>{t("includeKeywordsHint")}</FieldHint>
              </label>

              <label className="flex flex-col">
                <FieldLabel palette={palette}>{t("excludeKeywords")}</FieldLabel>
                <Input
                  type="text"
                  value={excludeStr}
                  onChange={(e) => onExcludeChange(e.target.value)}
                  placeholder={t("keywordsPlaceholder")}
                  palette={palette}
                />
                <FieldHint palette={palette}>{t("excludeKeywordsHint")}</FieldHint>
              </label>

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold" style={{ color: palette.ink70 }}>
                  {t("minimumFitScore")}
                  <span style={{ color: palette.red }}>{settings.min_score}%</span>
                </span>
                <input
                  type="range"
                  min={50}
                  max={95}
                  step={5}
                  value={settings.min_score}
                  aria-label={t("minimumFitScore")}
                  onChange={(e) => onSettingsChange({ min_score: Number(e.target.value) })}
                  className="h-1.5 w-full cursor-pointer rounded-lg"
                />
                <RangeLabels left={t("general")} right={t("highMatchOnly")} palette={palette} />
              </label>

              <GuardrailWarnings warnings={settings.warnings} language={language} />

              <label className="flex flex-col gap-2">
                <span className="flex items-center justify-between text-[12px] font-semibold" style={{ color: palette.ink70 }}>
                  {t("dailyApplyLimit")}
                  <span style={{ color: palette.red }}>{settings.max_daily_applies}</span>
                </span>
                <input
                  type="range"
                  min={0}
                  max={50}
                  step={1}
                  value={settings.max_daily_applies}
                  aria-label={t("dailyApplyLimit")}
                  onChange={(e) => onSettingsChange({ max_daily_applies: Number(e.target.value) })}
                  className="h-1.5 w-full cursor-pointer rounded-lg"
                />
                <RangeLabels left={t("safety")} right={t("aggressive")} palette={palette} />
              </label>

              <AtelierButton onClick={onSave} disabled={saving} palette={palette}>
                {saving && (
                  <span
                    className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-t-transparent"
                    style={{ borderColor: palette.bg, borderTopColor: "transparent" }}
                  />
                )}
                {saving ? t("saving") : t("saveSettings")}
              </AtelierButton>
            </div>
          ) : null}
        </ThemedPlate>

        {/* ── Notifications ── */}
        <ThemedPlate className="p-5 sm:p-6" palette={palette}>
          <SectionTitle palette={palette}>{t("notifications")}</SectionTitle>

          <div className="flex flex-col gap-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[13px] font-semibold" style={{ color: palette.ink }}>
                  {t("telegramAlerts")}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-[12px]" style={{ color: palette.ink40 }}>
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: telegramOn ? "#34d399" : palette.ink40 }}
                  />
                  {telegramOn ? t("telegramConnected") : t("telegramNotConnected")}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={telegramOn}
                aria-label={t("telegramAlerts")}
                onClick={onToggleTelegram}
                disabled={telegramBusy}
                className="relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50"
                style={{
                  background: telegramOn ? palette.red : palette.track,
                  cursor: telegramBusy ? "not-allowed" : "pointer",
                }}
              >
                <span
                  className="absolute top-0.5 h-5 w-5 rounded-full transition-transform"
                  style={{
                    background: palette.panel,
                    [isAr ? "right" : "left"]: "0.125rem",
                    transform: telegramOn ? `translateX(${isAr ? "-" : ""}20px)` : "translateX(0)",
                  }}
                />
              </button>
            </div>

            {settings && (
              <div className="flex flex-col gap-3 pt-5" style={{ borderTop: `1px solid ${palette.hair}` }}>
                <label className="flex flex-col">
                  <FieldLabel palette={palette}>{t("telegramChatId")}</FieldLabel>
                  <Input
                    type="text"
                    value={settings.telegram_chat_id}
                    onChange={(e) => onSettingsChange({ telegram_chat_id: e.target.value })}
                    placeholder={t("telegramPlaceholder")}
                    palette={palette}
                  />
                  <FieldHint palette={palette}>{t("telegramChatIdHint")}</FieldHint>
                </label>
                <AtelierButton onClick={onSave} disabled={saving} palette={palette}>
                  {saving && (
                    <span
                      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-t-transparent"
                      style={{ borderColor: palette.bg, borderTopColor: "transparent" }}
                    />
                  )}
                  {saving ? t("saving") : t("saveSettings")}
                </AtelierButton>
              </div>
            )}
          </div>
        </ThemedPlate>

        {/* ── Account ── */}
        <ThemedPlate className="p-5 sm:p-6" palette={palette}>
          <SectionTitle palette={palette}>{t("account")}</SectionTitle>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <FieldLabel palette={palette}>{t("emailAddress")}</FieldLabel>
              <p className="text-[13px]" style={{ color: palette.ink }}>
                {userEmail ?? "—"}
              </p>
            </div>

            <Link
              href="/forgot-password"
              className="settings-action inline-flex items-center gap-1.5 self-start text-[13px] underline-offset-2"
              style={{ color: palette.red }}
            >
              {t("changePassword")}
            </Link>

            <AtelierButton onClick={onLogout} palette={palette} variant="secondary">
              {t("logout")}
            </AtelierButton>

            <div className="mt-1 flex flex-wrap gap-4 pt-4" style={{ borderTop: `1px solid ${palette.hair}` }}>
              {[
                { href: "/terms", label: t("termsOfService") },
                { href: "/privacy", label: t("privacyPolicy") },
                { href: "/refund-policy", label: t("refundPolicy") },
              ].map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="settings-action text-[12px]"
                  style={{ color: palette.ink40 }}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </ThemedPlate>
      </div>
    </div>
  );
}
