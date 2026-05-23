"use client";

import { DashboardShell } from "@/components/DashboardShell";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function SessionHint() {
  const params = useSearchParams();
  if (!params.get("session_id")) return null;
  return (
    <p className="text-[12px] text-[#5a5a7a] mt-1">Reference received.</p>
  );
}

export default function SubscriptionSuccessPage() {
  return (
    <DashboardShell title="Subscription" subtitle="Checkout complete">
      <div className="max-w-lg flex flex-col gap-8">

        <div className="flex flex-col items-center gap-6 rounded-2xl border border-[rgba(0,229,255,0.2)] bg-[#13132a]/60 p-10 backdrop-blur-md text-center">
          <div className="w-16 h-16 rounded-full bg-[rgba(0,229,255,0.1)] border border-[rgba(0,229,255,0.3)] flex items-center justify-center">
            <span className="text-[#00e5ff] text-[28px] leading-none">✦</span>
          </div>

          <div>
            <h2 className="text-[22px] font-bold text-white font-['Cabinet_Grotesk',sans-serif]">
              Checkout complete
            </h2>
            <p className="mt-2 text-[13px] text-[#8080a0] leading-relaxed max-w-sm mx-auto">
              Your payment is being processed by Stripe. Plan activation may
              take a moment to reflect in your account — no action needed.
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
              className="flex-1 py-3 rounded-xl text-center text-[13px] font-bold text-white bg-[rgba(0,229,255,0.12)] border border-[rgba(0,229,255,0.3)] hover:bg-[rgba(0,229,255,0.2)] transition-all"
            >
              Go to Command
            </Link>
          </div>
        </div>

        <p className="text-[11px] text-[#5a5a7a] text-center">
          If your plan does not update within a few minutes, refresh this page
          or contact support.
        </p>

      </div>
    </DashboardShell>
  );
}
