"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { getMySubscription } from "@/lib/api";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function SessionHint() {
  const params = useSearchParams();
  if (!params.get("session_id")) return null;
  return (
    <p className="text-[12px] text-[#5a5a7a] mt-1">Reference received.</p>
  );
}

function PlanActivatedContent() {
  const [plan, setPlan] = useState<string | null>(null);

  useEffect(() => {
    getMySubscription()
      .then((r) => {
        if (r.subscription.plan && r.subscription.plan !== "free") {
          setPlan(r.subscription.plan);
        }
      })
      .catch(() => {});
  }, []);

  const planLabel = plan
    ? plan.charAt(0).toUpperCase() + plan.slice(1)
    : null;

  const isPremium = plan === "premium";

  return (
    <div className="flex flex-col items-center gap-6 rounded-2xl border border-[rgba(0,229,255,0.2)] bg-[#13132a]/60 p-10 backdrop-blur-md text-center">
      {/* Animated icon */}
      <div className="relative">
        <div className="absolute inset-0 rounded-full animate-ping bg-[rgba(0,229,255,0.15)]" />
        <div
          className={`relative w-16 h-16 rounded-full flex items-center justify-center border ${
            isPremium
              ? "bg-[rgba(255,45,142,0.1)] border-[rgba(255,45,142,0.3)]"
              : "bg-[rgba(0,229,255,0.1)] border-[rgba(0,229,255,0.3)]"
          }`}
        >
          <span
            className={`text-[28px] leading-none ${
              isPremium ? "text-[#ff2d8e]" : "text-[#00e5ff]"
            }`}
          >
            ✦
          </span>
        </div>
      </div>

      <div>
        {planLabel ? (
          <>
            <div
              className={`inline-flex items-center px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-widest border mb-3 ${
                isPremium
                  ? "border-[rgba(255,45,142,0.4)] bg-[rgba(255,45,142,0.1)] text-[#ff2d8e]"
                  : "border-[rgba(91,79,255,0.4)] bg-[rgba(91,79,255,0.1)] text-[#7b6fff]"
              }`}
            >
              {planLabel}
            </div>
            <h2 className="text-[22px] font-bold text-white font-['Cabinet_Grotesk',sans-serif]">
              You&apos;re on {planLabel}
            </h2>
          </>
        ) : (
          <h2 className="text-[22px] font-bold text-white font-['Cabinet_Grotesk',sans-serif]">
            Checkout complete
          </h2>
        )}
        <p className="mt-2 text-[13px] text-[#8080a0] leading-relaxed max-w-sm mx-auto">
          {planLabel
            ? `Your ${planLabel} plan is active. Start using Rico with your new limits right now.`
            : "Your plan activation may take a moment to reflect in your account. Refresh or contact support if your plan has not updated."}
        </p>
        <Suspense>
          <SessionHint />
        </Suspense>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 w-full">
        <Link
          href="/subscription"
          className="flex-1 py-3 rounded-xl text-center text-[13px] font-semibold text-[#7b6fff] bg-[rgba(91,79,255,0.1)] border border-[rgba(91,79,255,0.3)] hover:bg-[rgba(91,79,255,0.2)] transition-all"
        >
          View subscription
        </Link>
        <Link
          href="/command"
          className={`flex-1 py-3 rounded-xl text-center text-[13px] font-bold text-white border transition-all ${
            isPremium
              ? "bg-[rgba(255,45,142,0.12)] border-[rgba(255,45,142,0.3)] hover:bg-[rgba(255,45,142,0.2)]"
              : "bg-[rgba(0,229,255,0.12)] border-[rgba(0,229,255,0.3)] hover:bg-[rgba(0,229,255,0.2)]"
          }`}
        >
          Start chatting with Rico
        </Link>
      </div>
    </div>
  );
}

export default function SubscriptionSuccessPage() {
  return (
    <DashboardShell title="Subscription" subtitle="Checkout complete">
      <div className="max-w-lg flex flex-col gap-8">
        <PlanActivatedContent />

        <p className="text-[11px] text-[#5a5a7a] text-center">
          If your plan does not update within a few minutes, refresh this page
          or contact support.
        </p>
      </div>
    </DashboardShell>
  );
}
