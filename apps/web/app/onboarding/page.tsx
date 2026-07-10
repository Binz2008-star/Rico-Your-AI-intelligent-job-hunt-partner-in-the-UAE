"use client";

/**
 * /onboarding — the real authenticated first-run setup flow (DEC-20260710-004).
 *
 * Migrated to the approved Atelier design as a scoped light-first `.atelier`
 * island (same pattern as the auth surfaces), preserving ALL existing behavior:
 * fetchMe/auth guard, CV upload + accepted types + non-CV rejection + 413,
 * parsing state, extracted-data review, the target-roles/cities/salary/
 * experience/skills fields, submitOnboarding, submission-error handling, and
 * EN/AR + RTL.
 *
 * Routing (DEC-20260710-004): completion is decided by the backend via
 * GET /api/v1/onboarding/status (`complete`) — the frontend never re-implements
 * completion rules and never routes on `profile_exists`.
 *   - unauthenticated              → signup/login with return path
 *   - authenticated + complete     → /command (never forced through onboarding)
 *   - authenticated + incomplete   → render onboarding
 *   - status request failure       → recoverable state (Retry / Continue to Rico),
 *                                     no redirect loop, no false completion claim
 *   - after successful submit       → /command
 *   - "Skip for now"               → /command WITHOUT marking onboarding complete
 */

import {
  ApiError,
  fetchOnboardingStatus,
  submitOnboarding,
  uploadCV,
  type OnboardingPayload,
  type ParsedCV,
} from "@/lib/api";
import { buildAuthHref } from "@/lib/redirect";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import "../_atelier/atelier-tokens.css";
import "../_atelier/atelier-onboarding.css";

type TFunc = (key: TranslationKey) => string;

// ── Step indicator ────────────────────────────────────────────────────────────

function StepIndicator({ current, t }: { current: 0 | 1 | 2; t: TFunc }) {
  const steps = [t("onboardingStepUpload"), t("onboardingStepComplete"), t("onboardingStepReady")] as const;
  return (
    <ol className="atl-onb-steps" aria-label="Onboarding progress">
      {steps.map((label, idx) => {
        const done = idx < current;
        const active = idx === current;
        return (
          <li key={label} className="atl-onb-step">
            <span
              className={[
                "atl-onb-step-dot",
                done ? "is-done" : active ? "is-active" : "",
              ].join(" ").trim()}
              aria-current={active ? "step" : undefined}
            >
              {done ? (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                idx + 1
              )}
            </span>
            <span className={["atl-onb-step-label", active ? "is-active" : done ? "is-done" : ""].join(" ").trim()}>
              {label}
            </span>
            {idx < steps.length - 1 && <span className="atl-onb-step-line" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

// ── Spinner block ────────────────────────────────────────────────────────────

function SpinnerBlock({ label }: { label: string }) {
  return (
    <div className="atl-onb-spinner-wrap" role="status" aria-live="polite">
      <span className="atl-onb-spin" />
      <p className="atl-onb-spinner-label">{label}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Phase = "checking" | "ready" | "guardError";
type PageState = "upload" | "parsing" | "form" | "submitting";

function isAuthFailure(error: unknown): boolean {
  if (error instanceof ApiError && error.statusCode === 401) return true;
  const message = error instanceof Error ? error.message : String(error ?? "");
  return message.includes("401") || /not authenticated|expired/i.test(message);
}

export default function OnboardingPage() {
  const router = useRouter();
  const { language, setLanguage } = useLanguage();
  const t = useTranslation(language);
  const isAr = language === "ar";
  const [dark, setDark] = useState(false);
  const [phase, setPhase] = useState<Phase>("checking");
  const [pageState, setPageState] = useState<PageState>("upload");
  const [parsed, setParsed] = useState<ParsedCV | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [errorMsg, setErrorMsg] = useState("");
  const cancelledRef = useRef(false);
  // Keep a stable ref to the (per-render) router so the mount guard effect and
  // its useCallback don't re-run on every render (router identity is not stable).
  const routerRef = useRef(router);
  routerRef.current = router;
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

  // ── Completion guard: the backend decides via /onboarding/status ──────────
  const runGuard = useCallback(() => {
    setPhase("checking");
    fetchOnboardingStatus()
      .then((status) => {
        if (cancelledRef.current) return;
        // Route on `complete` only — never on profile_exists.
        if (status.complete) {
          routerRef.current.replace("/command");
          return;
        }
        setPhase("ready");
      })
      .catch((err) => {
        if (cancelledRef.current) return;
        if (isAuthFailure(err)) {
          routerRef.current.replace(signUpHref);
          return;
        }
        // Recoverable — do NOT loop, do NOT assume complete.
        setPhase("guardError");
      });
  }, [signUpHref]);

  useEffect(() => {
    cancelledRef.current = false;
    runGuard();
    return () => {
      cancelledRef.current = true;
    };
  }, [runGuard]);

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
      // Reject non-CV classified files (job descriptions, images, etc.)
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
      // Route to /command only after a successful, persisted submit response.
      await submitOnboarding(payload);
      router.push("/command");
    } catch (err) {
      if (isAuthFailure(err)) {
        router.replace(loginHref);
        return;
      }
      // Submission failure stays on the form and shows no success state.
      setErrorMsg(err instanceof Error ? err.message : t("onboardingErrSave"));
      setPageState("form");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldValues, loginHref, router, t]);

  // "Skip for now" — go to Rico WITHOUT marking onboarding complete.
  const handleSkip = useCallback(() => {
    router.push("/command");
  }, [router]);

  return (
    <div
      className="atelier atl-onb"
      data-atl-theme={dark ? "dark" : "light"}
      dir={isAr ? "rtl" : "ltr"}
      lang={isAr ? "ar" : "en"}
    >
      <header className="atl-onb-header">
        <Link href="/" className="atl-onb-brand" aria-label="Rico">
          Rico <span className="atl-onb-brand-accent">Hunt</span>
        </Link>
        <div className="atl-onb-controls">
          <div className="atl-onb-seg" role="group" aria-label="Language">
            <button type="button" className="atl-onb-seg-btn" aria-pressed={!isAr} onClick={() => setLanguage("en")}>EN</button>
            <button type="button" className="atl-onb-seg-btn" aria-pressed={isAr} onClick={() => setLanguage("ar")}>عربي</button>
          </div>
          <button
            type="button"
            className="atl-onb-toggle"
            aria-label={dark ? t("atlToLight") : t("atlToDark")}
            aria-pressed={dark}
            onClick={() => setDark((v) => !v)}
          >
            {dark ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      <main className="atl-onb-main">
        <div className="atl-onb-col">
          {/* ── Guard: checking status ── */}
          {phase === "checking" && <SpinnerBlock label={t("onboardingCheckSetup")} />}

          {/* ── Guard: status failure (recoverable, no loop, no false completion) ── */}
          {phase === "guardError" && (
            <div className="atl-onb-panel atl-onb-status" role="alert">
              <h1 className="atl-onb-title">{t("onboardingStatusErrTitle")}</h1>
              <p className="atl-onb-sub">{t("onboardingStatusErrDesc")}</p>
              <div className="atl-onb-status-actions">
                <button type="button" className="atl-onb-btn atl-onb-btn-primary" onClick={runGuard}>
                  {t("onboardingRetry")}
                </button>
                <button type="button" className="atl-onb-btn atl-onb-btn-ghost" onClick={handleSkip}>
                  {t("onboardingContinueToRico")}
                </button>
              </div>
            </div>
          )}

          {/* ── Ready: the onboarding flow ── */}
          {phase === "ready" && (
            <>
              <StepIndicator
                current={
                  pageState === "upload" || pageState === "parsing" ? 0
                  : 1
                }
                t={t}
              />

              {/* Upload zone */}
              {pageState === "upload" && (
                <section className="atl-onb-panel">
                  <p className="atl-onb-eyebrow">{t("onboardingStepUpload")}</p>
                  <h1 className="atl-onb-title">{t("onboardingUploadTitle")}</h1>
                  <p className="atl-onb-sub">{t("onboardingUploadDesc")}</p>

                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleDrop}
                    className="atl-onb-drop"
                  >
                    <input type="file" accept="application/pdf,.doc,.docx,image/jpeg,image/png,image/webp" onChange={handleFileInput} className="atl-onb-file" id="cv-upload" />
                    <label htmlFor="cv-upload" className="atl-onb-drop-inner">
                      <span className="atl-onb-drop-icon" aria-hidden="true">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                          <polyline points="17 8 12 3 7 8" />
                          <line x1="12" y1="3" x2="12" y2="15" />
                        </svg>
                      </span>
                      <span className="atl-onb-drop-main">{t("onboardingClickUpload")}</span>
                      <span className="atl-onb-drop-hint">{t("onboardingPdfOnly")}</span>
                    </label>
                  </div>

                  {errorMsg && <p className="atl-onb-alert" role="alert">{errorMsg}</p>}

                  <p className="atl-onb-foot">
                    {t("onboardingHaveProfile")}{" "}
                    <Link href="/command" className="atl-onb-link">{t("onboardingGoToRico")}</Link>
                  </p>
                </section>
              )}

              {/* Parsing spinner */}
              {pageState === "parsing" && (
                <section className="atl-onb-panel">
                  <SpinnerBlock label={t("onboardingParsing")} />
                </section>
              )}

              {/* Missing-fields form */}
              {pageState === "form" && (
                <section className="atl-onb-panel">
                  <p className="atl-onb-eyebrow">{t("onboardingStepComplete")}</p>
                  <h1 className="atl-onb-title">{t("onboardingExtractedTitle")}</h1>
                  <p className="atl-onb-sub">{t("onboardingExtractedDesc")}</p>

                  {parsed && (
                    <div className="atl-onb-plate">
                      <p className="atl-onb-plate-label">{t("onboardingExtractedFrom")}</p>
                      {yearsExperience != null && (
                        <p className="atl-onb-plate-row">
                          <span className="atl-onb-plate-key">{t("onboardingExperience")} </span>{yearsExperience} {t("onboardingYrs")}
                        </p>
                      )}
                      {(parsed.skills?.length ?? 0) > 0 && (
                        <p className="atl-onb-plate-row">
                          <span className="atl-onb-plate-key">{t("onboardingSkillsLabel")} </span>{(parsed.skills ?? []).slice(0, 8).join(", ")}
                        </p>
                      )}
                      {(parsed.certifications?.length ?? 0) > 0 && (
                        <p className="atl-onb-plate-row">
                          <span className="atl-onb-plate-key">{t("onboardingCerts")} </span>{(parsed.certifications ?? []).join(", ")}
                        </p>
                      )}
                      {(parsed.languages?.length ?? 0) > 0 && (
                        <p className="atl-onb-plate-row">
                          <span className="atl-onb-plate-key">{t("onboardingLanguagesLabel")} </span>{(parsed.languages ?? []).join(", ")}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="atl-onb-fields">
                    {missingFields.map((field) => (
                      <div key={field.key} className="atl-onb-field">
                        <label htmlFor={`onb-${field.key}`} className="atl-onb-label">{field.label}</label>
                        <input
                          id={`onb-${field.key}`}
                          type="text"
                          value={fieldValues[field.key] ?? ""}
                          onChange={(e) => setFieldValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                          placeholder={field.placeholder}
                          className="atl-onb-input"
                        />
                      </div>
                    ))}
                  </div>

                  {errorMsg && <p className="atl-onb-alert" role="alert">{errorMsg}</p>}

                  <div className="atl-onb-actions">
                    <div className="atl-onb-skip-group">
                      <button type="button" onClick={handleSkip} className="atl-onb-link atl-onb-skip">
                        {t("onboardingSkipForNow")}
                      </button>
                      <p className="atl-onb-note">{t("onboardingSkipNote")}</p>
                    </div>
                    <button onClick={handleSubmit} className="atl-onb-btn atl-onb-btn-primary">
                      {t("onboardingCompleteProfile")}
                    </button>
                  </div>
                </section>
              )}

              {/* Saving spinner */}
              {pageState === "submitting" && (
                <section className="atl-onb-panel">
                  <SpinnerBlock label={t("onboardingSaving")} />
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
