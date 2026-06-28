"use client";

import { ApiError, fetchMe, submitOnboarding, uploadCV, type OnboardingPayload, type ParsedCV } from "@/lib/api";
import { buildAuthHref } from "@/lib/redirect";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type TFunc = (key: TranslationKey) => string;

// ── Step indicator ────────────────────────────────────────────────────────────

function StepIndicator({ current, t }: { current: 0 | 1 | 2; t: TFunc }) {
  const steps = [t("onboardingStepUpload"), t("onboardingStepComplete"), t("onboardingStepReady")] as const;
  return (
    <div className="mb-8 flex items-center gap-0" aria-label="Onboarding progress">
      {steps.map((label, idx) => {
        const done = idx < current;
        const active = idx === current;
        return (
          <div key={label} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={[
                  "flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-bold transition-all duration-300",
                  done
                    ? "border-gold bg-gold text-[#0a0a1a]"
                    : active
                    ? "border-gold bg-gold/15 text-gold shadow-[0_0_12px_rgba(245,166,35,0.25)]"
                    : "border-overlay/20 bg-surface-elevated/40 text-text-tertiary",
                ].join(" ")}
                aria-current={active ? "step" : undefined}
              >
                {done ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </div>
              <span className={[
                "text-[10px] font-semibold tracking-wide whitespace-nowrap",
                active ? "text-gold" : done ? "text-text-secondary" : "text-text-tertiary",
              ].join(" ")}>
                {label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div
                className={[
                  "mx-2 mb-4 h-px w-12 transition-all duration-500",
                  idx < current ? "bg-gold/60" : "bg-overlay/15",
                ].join(" ")}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Brand header ─────────────────────────────────────────────────────────────

function BrandHeader() {
  return (
    <Link href="/" className="mb-10 inline-flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-[9px] bg-rico-amber flex items-center justify-center text-sm font-black text-background shadow-[0_4px_16px_rgba(245,166,35,0.35)]">
        R
      </div>
      <span className="font-display font-black text-lg text-text-primary tracking-tight">
        Rico <span className="text-rico-amber">Hunt</span>
      </span>
    </Link>
  );
}

// ── Spinner card ─────────────────────────────────────────────────────────────

function SpinnerCard({ label }: { label: string }) {
  return (
    <GlassPanel className="w-full max-w-lg p-8 text-center">
      <div className="mb-4 mx-auto w-10 h-10 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
      <p className="text-sm text-text-secondary">{label}</p>
    </GlassPanel>
  );
}

// ── Completion screen ─────────────────────────────────────────────────────────

function CompletionCard({ onGo, t }: { onGo: () => void; t: TFunc }) {
  return (
    <div className="w-full max-w-lg text-center">
      <div className="mb-6 mx-auto w-14 h-14 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-gold">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="mb-2 font-display font-bold text-2xl text-text-primary tracking-tight">
        {t("onboardingDoneTitle")}
      </h2>
      <p className="mb-8 text-sm text-text-secondary leading-relaxed max-w-sm mx-auto">
        {t("onboardingDoneDesc")}
      </p>
      <button
        onClick={onGo}
        className="inline-flex items-center gap-2 rounded-lg bg-gold text-[#0a0a1a] px-6 py-3 text-sm font-semibold uppercase tracking-widest hover:bg-gold-hover transition-all shadow-[0_4px_16px_rgba(245,166,35,0.28)]"
      >
        {t("onboardingGoToDashboard")}
      </button>
    </div>
  );
}

// ── Error screen ──────────────────────────────────────────────────────────────

function ErrorCard({ message, onRetry, t }: { message: string; onRetry: () => void; t: TFunc }) {
  return (
    <GlassPanel className="w-full max-w-lg p-6 text-center border-error/30 bg-error/5">
      <p className="mb-4 text-sm text-error">{message}</p>
      <button
        onClick={onRetry}
        className="rounded-lg bg-gold text-[#0a0a1a] px-5 py-2.5 text-sm font-semibold uppercase tracking-widest hover:bg-gold-hover transition-all"
      >
        {t("onboardingTryAgain")}
      </button>
    </GlassPanel>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type PageState = "upload" | "parsing" | "form" | "submitting" | "done" | "error";
type AuthState = "checking" | "ready";

function isAuthFailure(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return message.includes("401") || /not authenticated|expired/i.test(message);
}

export default function OnboardingPage() {
  const router = useRouter();
  const { language } = useLanguage();
  const t = useTranslation(language);
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [pageState, setPageState] = useState<PageState>("upload");
  const [parsed, setParsed] = useState<ParsedCV | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [errorMsg, setErrorMsg] = useState("");
  const signUpHref = buildAuthHref("/signup", "/onboarding");
  const loginHref = buildAuthHref("/login", "/onboarding");
  const yearsExperience =
    parsed?.years_experience_hint ?? parsed?.years_experience ?? null;

  const missingFields: { key: keyof OnboardingPayload; label: string; placeholder: string; isNumber?: boolean; isList?: boolean }[] = [
    { key: "target_roles", label: t("onboardingFieldTargetRoles"), placeholder: t("onboardingFieldTargetRolesPlaceholder"), isList: true },
    { key: "preferred_cities", label: t("onboardingFieldCities"), placeholder: t("onboardingFieldCitiesPlaceholder"), isList: true },
    { key: "salary_expectation_aed", label: t("onboardingFieldSalary"), placeholder: t("onboardingFieldSalaryPlaceholder"), isNumber: true },
    { key: "years_experience", label: t("onboardingFieldExperience"), placeholder: t("onboardingFieldExperiencePlaceholder"), isNumber: true },
    { key: "skills", label: t("onboardingFieldSkills"), placeholder: t("onboardingFieldSkillsPlaceholder"), isList: true },
  ];

  useEffect(() => {
    let cancelled = false;

    fetchMe()
      .then((me) => {
        if (cancelled) return;
        if (!me.authenticated) {
          router.replace(signUpHref);
          return;
        }
        setAuthState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (isAuthFailure(err)) {
          router.replace(signUpHref);
          return;
        }
        setErrorMsg(t("onboardingErrSession"));
        setAuthState("ready");
      });

    return () => {
      cancelled = true;
    };
  }, [router, signUpHref, t]);

  const handleFile = useCallback(async (file: File) => {
    const ACCEPTED_TYPES = [
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/jpeg", "image/png", "image/webp",
    ];
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setErrorMsg(t("onboardingErrPdfOnly"));
      return;
    }
    setPageState("parsing");
    setErrorMsg("");
    try {
      const res = await uploadCV(file);
      // Finding 4: reject non-CV classified files (job descriptions, images, etc.)
      if (res.status === "classified" && res.document_type !== "cv") {
        setErrorMsg(t("onboardingErrNotCv"));
        setPageState("upload");
        return;
      }
      setParsed(res.parsed ?? null);
      const skills = res.parsed?.skills ?? [];
      if (skills.length > 0) {
        setFieldValues((prev) => ({
          ...prev,
          skills: skills.join(", "),
        }));
      }
      setPageState("form");
    } catch (err) {
      if (isAuthFailure(err)) {
        router.replace(loginHref);
        return;
      }
      if (err instanceof ApiError && err.statusCode === 413) {
        setErrorMsg(t("cmdCvTooLarge"));   // file too large — localized size message
      } else {
        setErrorMsg(err instanceof Error ? err.message : t("onboardingErrUpload"));
      }
      setPageState("upload");
    }
  }, [loginHref, router, t]);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleSubmit = useCallback(async () => {
    setPageState("submitting");
    setErrorMsg("");

    const payload: OnboardingPayload = {};
    for (const field of missingFields) {
      const raw = (fieldValues[field.key] ?? "").trim();
      if (!raw) continue;
      if (field.isNumber) {
        const n = parseFloat(raw.replace(/[^0-9.]/g, ""));
        if (!isNaN(n)) (payload as Record<string, unknown>)[field.key] = n;
      } else if (field.isList) {
        const arr = raw.split(",").map((s) => s.trim()).filter(Boolean);
        if (arr.length) (payload as Record<string, unknown>)[field.key] = arr;
      }
    }

    try {
      await submitOnboarding(payload);
      setPageState("done");
    } catch (err) {
      if (isAuthFailure(err)) {
        router.replace(loginHref);
        return;
      }
      setErrorMsg(err instanceof Error ? err.message : t("onboardingErrSave"));
      setPageState("form");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldValues, loginHref, router, t]);

  const pageContent = (
    <>
      {/* ── Auth check spinner ── */}
      {authState === "checking" && (
        <SpinnerCard label={t("onboardingCheckSession")} />
      )}

      {authState === "ready" && (
        <>
          {/* ── Step progress ── */}
          {pageState !== "error" && (
            <StepIndicator
              current={
                pageState === "upload" || pageState === "parsing" ? 0
                : pageState === "form" || pageState === "submitting" ? 1
                : 2
              }
              t={t}
            />
          )}

          {/* ── Upload zone ── */}
          {pageState === "upload" && (
            <GlassPanel className="w-full max-w-md p-8">
              <div className="mb-8 text-center">
                <h1 className="font-display font-bold text-2xl text-text-primary tracking-tight mb-2">
                  {t("onboardingUploadTitle")}
                </h1>
                <p className="text-sm text-text-secondary">
                  {t("onboardingUploadDesc")}
                </p>
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="w-full rounded-xl border-2 border-dashed border-border-medium p-10 text-center transition-colors hover:border-gold/40"
              >
                <input type="file" accept="application/pdf,.doc,.docx,image/jpeg,image/png,image/webp" onChange={handleFileInput} className="hidden" id="cv-upload" />
                <label htmlFor="cv-upload" className="flex flex-col items-center gap-3 cursor-pointer">
                  <div className="w-12 h-12 rounded-full bg-gold/10 flex items-center justify-center">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gold">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <span className="text-sm text-text-primary font-medium">{t("onboardingClickUpload")}</span>
                  <span className="text-xs text-text-secondary">{t("onboardingPdfOnly")}</span>
                </label>
              </div>

              {errorMsg && (
                <p className="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error text-center">
                  {errorMsg}
                </p>
              )}

              <p className="mt-6 text-xs text-text-secondary text-center">
                {t("onboardingHaveProfile")}{" "}
                <Link href="/dashboard?skip=1" className="text-primary hover:text-primary/80 transition-colors">
                  {t("onboardingGoToDashboard")}
                </Link>
              </p>
            </GlassPanel>
          )}

          {/* ── Parsing spinner ── */}
          {pageState === "parsing" && <SpinnerCard label={t("onboardingParsing")} />}

          {/* ── Missing fields form ── */}
          {pageState === "form" && (
            <GlassPanel className="w-full max-w-2xl p-8">
              <h1 className="mb-1 font-display font-bold text-2xl text-text-primary tracking-tight">
                {t("onboardingExtractedTitle")}
              </h1>
              <p className="mb-6 text-sm text-text-secondary">
                {t("onboardingExtractedDesc")}
              </p>

              {parsed && (
                <div className="mb-6 rounded-xl bg-surface p-4 border border-border-subtle space-y-1">
                  <p className="text-[11px] uppercase tracking-wider text-text-tertiary mb-2">{t("onboardingExtractedFrom")}</p>
                  {yearsExperience != null && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">{t("onboardingExperience")} </span>{yearsExperience} {t("onboardingYrs")}
                    </p>
                  )}
                  {(parsed.skills?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">{t("onboardingSkillsLabel")} </span>{(parsed.skills ?? []).slice(0, 8).join(", ")}
                    </p>
                  )}
                  {(parsed.certifications?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">{t("onboardingCerts")} </span>{(parsed.certifications ?? []).join(", ")}
                    </p>
                  )}
                  {(parsed.languages?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">{t("onboardingLanguagesLabel")} </span>{(parsed.languages ?? []).join(", ")}
                    </p>
                  )}
                </div>
              )}

              <div className="space-y-4">
                {missingFields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-[10px] uppercase tracking-widest text-text-secondary mb-1.5">
                      {field.label}
                    </label>
                    <input
                      type="text"
                      value={fieldValues[field.key] ?? ""}
                      onChange={(e) => setFieldValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                      className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary/40 transition-all"
                    />
                  </div>
                ))}
              </div>

              {errorMsg && (
                <p className="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error text-center">
                  {errorMsg}
                </p>
              )}

              <div className="mt-6 flex items-center justify-between">
                <button
                  onClick={() => router.push("/dashboard?skip=1")}
                  className="text-sm text-text-secondary hover:text-text-primary transition-colors"
                >
                  {t("onboardingSkipForNow")}
                </button>
                <button
                  onClick={handleSubmit}
                  className="inline-flex items-center gap-2 rounded-lg bg-gold text-[#0a0a1a] px-6 py-3 text-sm font-semibold uppercase tracking-widest hover:bg-gold-hover transition-all shadow-[0_4px_16px_rgba(245,166,35,0.28)]"
                >
                  {t("onboardingCompleteProfile")}
                </button>
              </div>
            </GlassPanel>
          )}

          {/* ── Saving spinner ── */}
          {pageState === "submitting" && <SpinnerCard label={t("onboardingSaving")} />}

          {/* ── Done ── */}
          {pageState === "done" && (
            <CompletionCard onGo={() => router.push("/dashboard?skip=1")} t={t} />
          )}

          {/* ── Error (fatal) ── */}
          {pageState === "error" && (
            <ErrorCard
              message={errorMsg}
              onRetry={() => { setPageState("upload"); setErrorMsg(""); }}
              t={t}
            />
          )}
        </>
      )}
    </>
  );

  return (
    <main
      className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4"
      dir={language === "ar" ? "rtl" : "ltr"}
    >
      <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
      <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />

      <div className="relative z-10 flex flex-col items-center w-full">
        <BrandHeader />
        <PageTransition className="w-full flex flex-col items-center">
          {pageContent}
        </PageTransition>
      </div>
    </main>
  );
}
