"use client";

import { fetchMe, submitOnboarding, uploadCV, type OnboardingPayload, type ParsedCV } from "@/lib/api";
import { buildAuthHref } from "@/lib/redirect";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

// ── Missing-fields form config ────────────────────────────────────────────────

const MISSING_FIELDS: { key: keyof OnboardingPayload; label: string; placeholder: string; isNumber?: boolean; isList?: boolean }[] = [
  { key: "target_roles", label: "Target roles", placeholder: "e.g. HSE Manager, Operations Director", isList: true },
  { key: "preferred_cities", label: "Preferred cities", placeholder: "e.g. Dubai, Abu Dhabi, Remote", isList: true },
  { key: "salary_expectation_aed", label: "Salary expectation (AED/month)", placeholder: "e.g. 25000", isNumber: true },
  { key: "years_experience", label: "Years of experience", placeholder: "e.g. 8", isNumber: true },
  { key: "skills", label: "Additional skills (if any missed)", placeholder: "Comma-separated", isList: true },
];

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
      <div className="mb-4 mx-auto w-10 h-10 rounded-full border-2 border-magenta/30 border-t-magenta animate-spin" />
      <p className="text-sm text-text-secondary">{label}</p>
    </GlassPanel>
  );
}

// ── Completion screen ─────────────────────────────────────────────────────────

function CompletionCard({ onGo }: { onGo: () => void }) {
  return (
    <div className="w-full max-w-lg text-center">
      <div className="mb-6 mx-auto w-14 h-14 rounded-full bg-cyan-soft border border-cyan/20 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-cyan">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="mb-2 font-display font-bold text-2xl text-text-primary tracking-tight">
        Profile saved
      </h2>
      <p className="mb-8 text-sm text-text-secondary leading-relaxed max-w-sm mx-auto">
        Rico now has enough context to start hunting. Your first batch of scored jobs will appear on the dashboard shortly.
      </p>
      <button
        onClick={onGo}
        className="inline-flex items-center gap-2 rounded-lg bg-primary/10 text-primary px-6 py-3 text-sm font-semibold uppercase tracking-widest hover:bg-primary/20 transition-all"
      >
        Go to dashboard →
      </button>
    </div>
  );
}

// ── Error screen ──────────────────────────────────────────────────────────────

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <GlassPanel className="w-full max-w-lg p-6 text-center border-error/30 bg-error/5">
      <p className="mb-4 text-sm text-error">{message}</p>
      <button
        onClick={onRetry}
        className="rounded-lg bg-primary/10 text-primary px-5 py-2.5 text-sm font-semibold uppercase tracking-widest hover:bg-primary/20 transition-all"
      >
        Try again
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
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [pageState, setPageState] = useState<PageState>("upload");
  const [parsed, setParsed] = useState<ParsedCV | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [errorMsg, setErrorMsg] = useState("");
  const signUpHref = buildAuthHref("/signup", "/onboarding");
  const loginHref = buildAuthHref("/login", "/onboarding");
  const yearsExperience =
    parsed?.years_experience_hint ?? parsed?.years_experience ?? null;

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
        setErrorMsg("Could not verify your session. Please refresh or sign in again.");
        setAuthState("ready");
      });

    return () => {
      cancelled = true;
    };
  }, [router, signUpHref]);

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") {
      setErrorMsg("Only PDF files are accepted.");
      return;
    }
    setPageState("parsing");
    setErrorMsg("");
    try {
      const res = await uploadCV(file);
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
      setErrorMsg(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setPageState("upload");
    }
  }, [loginHref, router]);

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
    for (const field of MISSING_FIELDS) {
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
      setErrorMsg(err instanceof Error ? err.message : "Could not save your profile. Please try again.");
      setPageState("form");
    }
  }, [fieldValues, loginHref, router]);

  const pageContent = (
    <>
      {/* ── Auth check spinner ── */}
      {authState === "checking" && (
        <SpinnerCard label="Checking your session…" />
      )}

      {authState === "ready" && (
        <>
          {/* ── Upload zone ── */}
          {pageState === "upload" && (
            <GlassPanel className="w-full max-w-md p-8">
              <div className="mb-8 text-center">
                <h1 className="font-display font-bold text-2xl text-text-primary tracking-tight mb-2">
                  Start with your CV
                </h1>
                <p className="text-sm text-text-secondary">
                  Upload your CV (PDF) — Rico extracts everything and only asks for missing details.
                </p>
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="w-full rounded-xl border-2 border-dashed border-border-medium p-10 text-center transition-colors hover:border-magenta/40"
              >
                <input type="file" accept="application/pdf" onChange={handleFileInput} className="hidden" id="cv-upload" />
                <label htmlFor="cv-upload" className="flex flex-col items-center gap-3 cursor-pointer">
                  <div className="w-12 h-12 rounded-full bg-magenta-soft flex items-center justify-center">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-magenta">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <span className="text-sm text-text-primary font-medium">Click to upload or drag &amp; drop</span>
                  <span className="text-xs text-text-secondary">PDF only · max 10 MB</span>
                </label>
              </div>

              {errorMsg && (
                <p className="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error text-center">
                  {errorMsg}
                </p>
              )}

              <p className="mt-6 text-xs text-text-secondary text-center">
                Already have a profile?{" "}
                <Link href="/dashboard?skip=1" className="text-primary hover:text-primary/80 transition-colors">
                  Go to dashboard →
                </Link>
              </p>
            </GlassPanel>
          )}

          {/* ── Parsing spinner ── */}
          {pageState === "parsing" && <SpinnerCard label="Parsing your CV…" />}

          {/* ── Missing fields form ── */}
          {pageState === "form" && (
            <GlassPanel className="w-full max-w-2xl p-8">
              <h1 className="mb-1 font-display font-bold text-2xl text-text-primary tracking-tight">
                Profile extracted
              </h1>
              <p className="mb-6 text-sm text-text-secondary">
                Rico read your CV. Fill in any missing details to complete your profile.
              </p>

              {parsed && (
                <div className="mb-6 rounded-xl bg-surface p-4 border border-border-subtle space-y-1">
                  <p className="text-[11px] uppercase tracking-wider text-text-tertiary mb-2">Extracted from CV</p>
                  {yearsExperience != null && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">Experience: </span>{yearsExperience} yrs
                    </p>
                  )}
                  {(parsed.skills?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">Skills: </span>{(parsed.skills ?? []).slice(0, 8).join(", ")}
                    </p>
                  )}
                  {(parsed.certifications?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">Certs: </span>{(parsed.certifications ?? []).join(", ")}
                    </p>
                  )}
                  {(parsed.languages?.length ?? 0) > 0 && (
                    <p className="text-sm text-text-secondary">
                      <span className="text-text-tertiary">Languages: </span>{(parsed.languages ?? []).join(", ")}
                    </p>
                  )}
                </div>
              )}

              <div className="space-y-4">
                {MISSING_FIELDS.map((field) => (
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
                  Skip for now
                </button>
                <button
                  onClick={handleSubmit}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary/10 text-primary px-6 py-3 text-sm font-semibold uppercase tracking-widest hover:bg-primary/20 transition-all"
                >
                  Complete profile →
                </button>
              </div>
            </GlassPanel>
          )}

          {/* ── Saving spinner ── */}
          {pageState === "submitting" && <SpinnerCard label="Saving your profile…" />}

          {/* ── Done ── */}
          {pageState === "done" && (
            <CompletionCard onGo={() => router.push("/dashboard?skip=1")} />
          )}

          {/* ── Error (fatal) ── */}
          {pageState === "error" && (
            <ErrorCard
              message={errorMsg}
              onRetry={() => { setPageState("upload"); setErrorMsg(""); }}
            />
          )}
        </>
      )}
    </>
  );

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4">
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
