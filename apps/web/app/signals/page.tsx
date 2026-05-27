"use client";

import { Navigation } from "@/components/layout/Navigation";
import { TopNav } from "@/components/layout/TopNav";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useLinkVerification } from "@/hooks/useLinkVerification";
import { useOrchestration } from "@/hooks/useOrchestration";
import type { OpportunitySignal } from "@/lib/api/orchestration";
import Link from "next/link";
import { useMemo, useState } from "react";

function MomentumLabel({ momentum }: { momentum: "high" | "medium" | "low" }) {
  const palette = {
    high: "text-[#5dcaa5] border-[#5dcaa5]/30",
    medium: "text-[#facc15] border-[#facc15]/30",
    low: "text-[#a78bfa] border-[#a78bfa]/30",
  } as const;

  return (
    <span
      className={`text-label-caps text-[10px] px-2 py-1 border rounded ${palette[momentum]}`}
    >
      {momentum.toUpperCase()} MOMENTUM
    </span>
  );
}

function LinkStatusBadge({
  status,
}: {
  status: OpportunitySignal["linkStatus"];
}) {
  if (!status) return null;

  const palette = {
    live: "text-[#5dcaa5] border-[#5dcaa5]/30",
    expired: "text-[#f87171] border-[#f87171]/30",
    blocked: "text-[#f87171] border-[#f87171]/30",
    redirect: "text-[#facc15] border-[#facc15]/30",
    source_only: "text-[#a78bfa] border-[#a78bfa]/30",
    needs_review: "text-[#facc15] border-[#facc15]/30",
    checking: "text-[#94a3b8] border-[#94a3b8]/30",
  } as const;

  const labels = {
    live: "Verified live",
    expired: "Link unavailable",
    blocked: "Blocked",
    redirect: "Redirects",
    source_only: "Source only",
    needs_review: "Needs review",
    checking: "Checking link...",
  } as const;

  return (
    <span
      className={`text-label-caps text-[10px] px-2 py-1 border rounded ${palette[status]}`}
    >
      {labels[status]}
    </span>
  );
}

function signalDate(signal: OpportunitySignal) {
  return signal.timestamp
    ? new Date(signal.timestamp).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Date unavailable";
}

function commandHref(message: string) {
  return `/command?prompt=${encodeURIComponent(message)}`;
}

function SignalActions({
  signal,
  onDismiss,
  linkStatus,
}: {
  signal: OpportunitySignal;
  onDismiss: () => void;
  linkStatus?: OpportunitySignal["linkStatus"];
}) {
  const titleCompany = `${signal.role} at ${signal.company}`;

  const showViewJob =
    linkStatus === undefined ||
    linkStatus === "checking" ||
    ["live", "redirect", "needs_review", "source_only"].includes(linkStatus);

  const showCaution =
    linkStatus === "needs_review" || linkStatus === "source_only";

  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {linkStatus === "expired" ? (
        <Link
          href={commandHref(`Find similar live jobs — ${titleCompany}`)}
          className="rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1.5 text-[12px] font-semibold text-cyan hover:bg-cyan/15"
        >
          Find similar live jobs
        </Link>
      ) : linkStatus === "blocked" ? (
        <span className="rounded-full border border-red/25 bg-red/10 px-3 py-1.5 text-[12px] font-semibold text-red">
          Needs review — link could not be safely verified
        </span>
      ) : signal.applyUrl && showViewJob ? (
        <a
          href={signal.applyUrl}
          target="_blank"
          rel="noreferrer"
          className="rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1.5 text-[12px] font-semibold text-cyan hover:bg-cyan/15"
        >
          View job
        </a>
      ) : null}
      {showCaution && (
        <span className="text-[10px] text-on-surface-variant/60 self-center">
          Caution: link status uncertain
        </span>
      )}
      <Link
        href={commandHref(`Explain fit — ${titleCompany}`)}
        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-semibold text-on-surface hover:text-white"
      >
        Explain fit
      </Link>
      <Link
        href={commandHref(`Track this job — ${titleCompany}`)}
        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-semibold text-on-surface hover:text-white"
      >
        Track this job
      </Link>
      <Link
        href={commandHref(`Prepare application — ${titleCompany}`)}
        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-semibold text-on-surface hover:text-white"
      >
        Prepare application
      </Link>
      <Link
        href={commandHref(`Mark as applied — ${titleCompany}`)}
        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-semibold text-on-surface hover:text-white"
      >
        Mark as applied
      </Link>
      <Link
        href={commandHref(`Save job — ${titleCompany}`)}
        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-semibold text-on-surface hover:text-white"
      >
        Save
      </Link>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded-full border border-white/10 bg-white/[0.02] px-3 py-1.5 text-[12px] font-semibold text-on-surface-variant hover:text-white"
      >
        Dismiss
      </button>
    </div>
  );
}

export default function SignalsPage() {
  const { signals, isLoading, error, refetchSignals } = useOrchestration();
  const { getLinkStatus, isChecking } = useLinkVerification(signals);
  const [selectedSignal, setSelectedSignal] =
    useState<OpportunitySignal | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const visibleSignals = useMemo(
    () => signals.filter((signal) => !dismissedIds.has(signal.id)),
    [dismissedIds, signals],
  );
  const dismissSignal = (id: string) => {
    setDismissedIds((current) => new Set([...current, id]));
    if (selectedSignal?.id === id) setSelectedSignal(null);
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />
      <TopNav />

      <main className="relative z-10 pt-40 pb-60 px-container-padding-mobile md:px-container-padding-desktop max-w-7xl mx-auto">
        <div className="mb-section-gap">
          <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">
            Opportunity Signals
          </h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
            Live market signals sourced from your matched jobs feed and scored
            against current opportunity momentum.
          </p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 3 }).map((_, index) => (
              <GlassPanel
                key={index}
                className="p-6 rounded-xl border border-white/10 animate-pulse motion-reduce:animate-none"
              >
                <div className="h-5 w-32 rounded bg-white/5 mb-4" />
                <div className="h-4 w-40 rounded bg-white/5 mb-2" />
                <div className="h-4 w-24 rounded bg-white/5" />
              </GlassPanel>
            ))}
          </div>
        ) : error ? (
          <GlassPanel className="p-6 rounded-xl border border-white/10">
            <p className="text-on-surface mb-2">Could not load live signals.</p>
            <p className="text-body-md text-on-surface-variant">
              The backend is reachable for command execution, but the signals
              surface could not read the current jobs feed.
            </p>
            <button
              type="button"
              onClick={() => void refetchSignals()}
              className="mt-4 rounded-full border border-cyan/25 bg-cyan/10 px-4 py-2 text-sm font-semibold text-cyan hover:bg-cyan/15"
            >
              Retry signals
            </button>
          </GlassPanel>
        ) : visibleSignals.length === 0 ? (
          <GlassPanel className="p-6 rounded-xl border border-white/10">
            <p className="text-on-surface mb-2">No live signals yet.</p>
            <p className="text-body-md text-on-surface-variant">
              Rico will populate this view when matched opportunities are
              available from the live jobs endpoint.
            </p>
          </GlassPanel>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {visibleSignals.map((signal) => (
              <GlassPanel
                key={signal.id}
                className="p-6 rounded-xl border border-white/10 hover:border-primary/30 transition-all group"
              >
                <button
                  type="button"
                  onClick={() => setSelectedSignal(signal)}
                  className="block w-full text-left"
                >
                  <div className="flex items-start justify-between mb-4 gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <MaterialIcon
                          icon="business"
                          className="text-primary"
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-headline-lg text-headline-lg text-on-surface break-words">
                          {signal.role}
                        </h3>
                        <p className="mt-1 text-on-surface-variant text-sm break-words">
                          {signal.company}
                        </p>
                        <p className="mt-1 text-on-surface-variant text-sm">
                          {signal.location || "Location unavailable"}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <MomentumLabel momentum={signal.momentum} />
                      <LinkStatusBadge status={getLinkStatus(signal.id)} />
                    </div>
                  </div>
                  <div className="mb-4">
                    <p className="text-body-md text-on-surface-variant mb-2 line-clamp-3">
                      {signal.whyItFits ||
                        "Rico matched this role against your profile."}
                    </p>
                    <div className="flex gap-2 items-center">
                      <span className="text-[10px] text-on-surface-variant/60">
                        Match score {signal.matchScore}%
                      </span>
                      <span className="text-[10px] text-on-surface-variant/60">
                        •
                      </span>
                      <span className="text-[10px] text-on-surface-variant/60">
                        {signal.source || "Rico job search"} ·{" "}
                        {signalDate(signal)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-1.5 h-1.5 rounded-full ${signal.momentum === "high" ? "bg-secondary" : signal.momentum === "medium" ? "bg-[#facc15]" : "bg-primary"}`}
                      />
                      <span className="text-label-caps text-[10px] text-on-surface-variant">
                        Open details
                      </span>
                    </div>
                    <MaterialIcon
                      icon="arrow_forward"
                      className="text-on-surface-variant/40 group-hover:text-primary transition-colors"
                    />
                  </div>
                </button>
                <SignalActions
                  signal={signal}
                  linkStatus={getLinkStatus(signal.id)}
                  onDismiss={() => dismissSignal(signal.id)}
                />
              </GlassPanel>
            ))}
          </div>
        )}
      </main>

      {selectedSignal && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 px-4 py-6 backdrop-blur-sm md:items-center">
          <GlassPanel className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-label-caps text-[10px] text-cyan">
                  {selectedSignal.source || "Rico job search"} ·{" "}
                  {signalDate(selectedSignal)}
                </p>
                <h2 className="mt-3 text-2xl font-semibold text-on-surface">
                  {selectedSignal.role}
                </h2>
                <p className="mt-2 text-body-md text-on-surface-variant">
                  {selectedSignal.company} ·{" "}
                  {selectedSignal.location || "Location unavailable"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSignal(null)}
                className="rounded-full border border-white/10 px-3 py-1 text-sm text-on-surface-variant hover:text-white"
              >
                Close
              </button>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-label-caps text-[10px] text-on-surface-variant">
                  Match score
                </p>
                <p className="mt-2 text-3xl font-semibold text-on-surface">
                  {selectedSignal.matchScore}%
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-label-caps text-[10px] text-on-surface-variant">
                  Momentum
                </p>
                <div className="mt-3">
                  <MomentumLabel momentum={selectedSignal.momentum} />
                </div>
              </div>
            </div>
            <div className="mt-6 space-y-4">
              <section>
                <h3 className="text-sm font-semibold text-on-surface">
                  Why it fits
                </h3>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  {selectedSignal.whyItFits ||
                    "Rico matched this role against your profile and saved preferences."}
                </p>
              </section>
              <section>
                <h3 className="text-sm font-semibold text-on-surface">
                  Missing facts to verify
                </h3>
                {selectedSignal.missingFacts?.length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-on-surface-variant">
                    {selectedSignal.missingFacts.map((fact) => (
                      <li key={fact}>{fact}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                    Check the job post for salary, visa requirements, reporting
                    line, and exact application deadline.
                  </p>
                )}
              </section>
            </div>
            <SignalActions
              signal={selectedSignal}
              linkStatus={getLinkStatus(selectedSignal.id)}
              onDismiss={() => dismissSignal(selectedSignal.id)}
            />
          </GlassPanel>
        </div>
      )}

      <Navigation />
    </div>
  );
}
