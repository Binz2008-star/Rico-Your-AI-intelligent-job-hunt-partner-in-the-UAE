"use client";

import { submitOnboarding, type OnboardingPayload } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

// ── Step definitions ──────────────────────────────────────────────────────────

interface Step {
  id: keyof OnboardingPayload;
  question: string;
  placeholder: string;
  hint: string;
  optional?: boolean;
  parse: (raw: string) => OnboardingPayload[keyof OnboardingPayload];
}

const STEPS: Step[] = [
  {
    id: "target_roles",
    question: "What roles are you targeting?",
    placeholder: "e.g. Product Manager, Operations Director",
    hint: "List one or more job titles, separated by commas. Rico uses these to score and filter every job it finds.",
    parse: (raw) => raw.split(",").map((s) => s.trim()).filter(Boolean),
  },
  {
    id: "preferred_cities",
    question: "Where do you want to work?",
    placeholder: "e.g. Dubai, Abu Dhabi, Remote",
    hint: "One or more cities, or 'Remote' if location-flexible.",
    parse: (raw) => raw.split(",").map((s) => s.trim()).filter(Boolean),
  },
  {
    id: "salary_expectation_aed",
    question: "What is your monthly salary expectation?",
    placeholder: "e.g. 25000",
    hint: "Monthly figure in AED (numbers only). Used to filter out roles below your floor.",
    optional: true,
    parse: (raw) => {
      const n = parseFloat(raw.replace(/[^0-9.]/g, ""));
      return isNaN(n) ? undefined : n;
    },
  },
  {
    id: "years_experience",
    question: "How many years of total experience do you have?",
    placeholder: "e.g. 8",
    hint: "Enter a number. Include your current role.",
    parse: (raw) => {
      const n = parseFloat(raw.replace(/[^0-9.]/g, ""));
      return isNaN(n) ? undefined : n;
    },
  },
  {
    id: "skills",
    question: "What are your key skills?",
    placeholder: "e.g. P&L management, ISO compliance, stakeholder management",
    hint: "Skills most relevant to the roles you are targeting, separated by commas.",
    parse: (raw) => raw.split(",").map((s) => s.trim()).filter(Boolean),
  },
];

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = Math.round(((current + 1) / total) * 100);
  return (
    <div className="w-full h-1 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
      <div
        className="h-full rounded-full bg-gradient-to-r from-[#5b4fff] to-[#8b5cf6] transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Step card ─────────────────────────────────────────────────────────────────

function StepCard({
  step,
  stepIndex,
  total,
  onNext,
}: {
  step: Step;
  stepIndex: number;
  total: number;
  onNext: (value: OnboardingPayload[keyof OnboardingPayload]) => void;
}) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed && !step.optional) return;
    onNext(trimmed ? step.parse(trimmed) : undefined);
  };

  return (
    <div className="w-full max-w-lg">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[#5a5a7a]">
        Step {stepIndex + 1} of {total}
      </p>

      <ProgressBar current={stepIndex} total={total} />

      <div className="mt-8 rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[#13132a]/80 p-6 backdrop-blur-xl">
        <h2 className="mb-1 font-['Cabinet_Grotesk',sans-serif] font-bold text-[20px] text-[#eeeef5] tracking-tight">
          {step.question}
        </h2>
        <p className="mb-5 text-[13px] text-[#5a5a7a] leading-relaxed">{step.hint}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={step.placeholder}
            autoFocus
            className="w-full rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0d0d1f] px-3 py-2.5 text-sm text-[#eeeef5] placeholder-[#5a5a7a] focus:border-[rgba(91,79,255,0.5)] focus:outline-none focus:ring-1 focus:ring-[rgba(91,79,255,0.3)] transition-colors"
          />

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!value.trim() && !step.optional}
              className="rounded-lg bg-[#5b4fff] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#4a3fdf] disabled:cursor-not-allowed disabled:opacity-40 shadow-[0_4px_15px_rgba(91,79,255,0.2)]"
            >
              Continue →
            </button>

            {step.optional && (
              <button
                type="button"
                onClick={() => onNext(undefined)}
                className="text-sm text-[#5a5a7a] hover:text-[#8080a0] transition-colors"
              >
                Skip for now
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Submitting screen ─────────────────────────────────────────────────────────

function SubmittingCard() {
  return (
    <div className="w-full max-w-lg rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[#13132a]/80 p-8 backdrop-blur-xl text-center">
      <div className="mb-4 mx-auto w-10 h-10 rounded-full border-2 border-[#5b4fff] border-t-transparent animate-spin" />
      <p className="text-sm text-[#5a5a7a]">Saving your profile…</p>
    </div>
  );
}

// ── Completion screen ─────────────────────────────────────────────────────────

function CompletionCard({ onGo }: { onGo: () => void }) {
  return (
    <div className="w-full max-w-lg text-center">
      <div className="mb-6 mx-auto w-14 h-14 rounded-full bg-[rgba(0,201,167,0.12)] border border-[rgba(0,201,167,0.2)] flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00c9a7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="mb-2 font-['Cabinet_Grotesk',sans-serif] font-bold text-[24px] text-[#eeeef5] tracking-tight">
        Profile saved
      </h2>
      <p className="mb-8 text-[14px] text-[#5a5a7a] leading-relaxed max-w-sm mx-auto">
        Rico now has enough context to start hunting. Your first batch of scored jobs will appear on the dashboard shortly.
      </p>
      <button
        onClick={onGo}
        className="inline-flex items-center gap-2 rounded-lg bg-[#5b4fff] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#4a3fdf] shadow-[0_4px_15px_rgba(91,79,255,0.2)]"
      >
        Go to dashboard →
      </button>
    </div>
  );
}

// ── Error screen ──────────────────────────────────────────────────────────────

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="w-full max-w-lg rounded-2xl border border-[rgba(255,94,91,0.3)] bg-[rgba(255,94,91,0.05)] p-6 text-center">
      <p className="mb-4 text-sm text-[#ff5e5b]">{message}</p>
      <button
        onClick={onRetry}
        className="rounded-lg bg-[#5b4fff] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#4a3fdf]"
      >
        Try again
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type PageState = "collecting" | "submitting" | "done" | "error";

export default function OnboardingPage() {
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<OnboardingPayload>({});
  const [pageState, setPageState] = useState<PageState>("collecting");
  const [errorMsg, setErrorMsg] = useState("");

  const doSubmit = useCallback(async (finalAnswers: OnboardingPayload) => {
    setPageState("submitting");
    try {
      await submitOnboarding(finalAnswers);
      setPageState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not save your profile. Please try again.");
      setPageState("error");
    }
  }, []);

  const handleStepNext = useCallback(
    (value: OnboardingPayload[keyof OnboardingPayload]) => {
      const step = STEPS[stepIndex];
      const updated: OnboardingPayload = { ...answers };
      if (value !== undefined) {
        (updated as Record<string, unknown>)[step.id] = value;
      }
      setAnswers(updated);

      if (stepIndex + 1 >= STEPS.length) {
        doSubmit(updated);
      } else {
        setStepIndex((i) => i + 1);
      }
    },
    [stepIndex, answers, doSubmit]
  );

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#06060f] px-4 relative overflow-hidden">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-[200px] -left-[100px] w-[600px] h-[600px] rounded-full bg-[rgba(91,79,255,0.06)] blur-[140px]" />
        <div className="absolute bottom-0 -right-[100px] w-[400px] h-[400px] rounded-full bg-[rgba(0,201,167,0.04)] blur-[140px]" />
      </div>

      <div className="relative z-10 flex flex-col items-center w-full">
        <Link href="/" className="mb-10 inline-flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-[9px] bg-gradient-to-br from-[#5b4fff] to-[#8b5cf6] flex items-center justify-center text-sm font-black text-white shadow-[0_4px_16px_rgba(91,79,255,0.3)]">
            R
          </div>
          <span className="font-['Cabinet_Grotesk',sans-serif] font-black text-lg text-white tracking-tight">Rico AI</span>
        </Link>

        {pageState === "collecting" && (
          <>
            <div className="mb-6 text-center">
              <h1 className="font-['Cabinet_Grotesk',sans-serif] font-bold text-[28px] text-[#eeeef5] tracking-tight mb-1">
                Let&apos;s set up your profile
              </h1>
              <p className="text-[14px] text-[#5a5a7a]">5 quick questions so Rico knows what to hunt for.</p>
            </div>

            <StepCard
              key={stepIndex}
              step={STEPS[stepIndex]}
              stepIndex={stepIndex}
              total={STEPS.length}
              onNext={handleStepNext}
            />

            <p className="mt-6 text-[12px] text-[#5a5a7a]">
              Already set up?{" "}
              <Link href="/dashboard?skip=1" className="text-[#a78bfa] hover:text-[#c4b5fd] transition-colors">
                Go to dashboard →
              </Link>
            </p>
          </>
        )}

        {pageState === "submitting" && <SubmittingCard />}

        {pageState === "done" && (
          <CompletionCard onGo={() => router.push("/dashboard?skip=1")} />
        )}

        {pageState === "error" && (
          <ErrorCard
            message={errorMsg}
            onRetry={() => { setPageState("collecting"); setErrorMsg(""); }}
          />
        )}
      </div>
    </main>
  );
}
