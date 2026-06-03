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
    high: "text-cyan border-cyan/30",
    medium: "text-rico-amber border-rico-amber/30",
    low: "text-magenta border-magenta/30",
  } as const;

  return (
    <span
      className={`text-label-caps text-[10px] px-2 py-1 border rounded ${palette[momentum]}`}
    >
      {momentum.toUpperCase()} MOMENTUM
    </span>
  );
}

function MatchScoreBadge({ score }: { score: number }) {
  const color =
    score >= 75
      ? "text-cyan bg-cyan/10 border-cyan/20"
      : score >= 50
        ? "text-rico-amber bg-rico-amber/10 border-rico-amber/20"
        : "text-rico-red bg-rico-red/10 border-rico-red/20";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${color}`}
    >
      <MaterialIcon icon="auto_awesome" size={12} />
      {score}%
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
    live: "text-cyan border-cyan/30",
    expired: "text-rico-red border-rico-red/30",
    blocked: "text-rico-red border-rico-red/30",
    redirect: "text-rico-amber border-rico-amber/30",
    source_only: "text-magenta border-magenta/30",
    needs_review: "text-rico-amber border-rico-amber/30",
    checking: "text-text-tertiary border-text-tertiary/30",
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
      data-testid="link-status-badge"
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

function PrimaryAction({
  signal,
  linkStatus,
}: {
  signal: OpportunitySignal;
  linkStatus?: OpportunitySignal["linkStatus"];
}) {
  const titleCompany = `${signal.role} at ${signal.company}`;

  const showViewJob =
    linkStatus === undefined ||
    linkStatus === "checking" ||
    ["live", "redirect", "needs_review", "source_only"].includes(linkStatus);

  if (linkStatus === "expired") {
    return (
      <Link
        data-testid="find-similar-action"
        href={commandHref(`Find similar live jobs — ${titleCompany}`)}
        className="inline-flex items-center gap-1.5 rounded-full border border-cyan/25 bg-cyan/10 px-4 py-2 text-[13px] font-semibold text-cyan hover:bg-cyan/15"
      >
        <MaterialIcon icon="rocket_launch" size={14} />
        Find similar live jobs
      </Link>
    );
  }

  if (linkStatus === "blocked") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red/25 bg-red/10 px-4 py-2 text-[13px] font-semibold text-red">
        <MaterialIcon icon="lock" size={14} />
        Needs review
      </span>
    );
  }

  if (signal.applyUrl && showViewJob) {
    return (
      <a
        data-testid="view-job-action"
        href={signal.applyUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 rounded-full border border-cyan/25 bg-cyan/10 px-4 py-2 text-[13px] font-semibold text-cyan hover:bg-cyan/15"
      >
        <MaterialIcon icon="arrow_forward" size={14} />
        View job
      </a>
    );
  }

  return null;
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
  const showCaution =
    linkStatus === "needs_review" || linkStatus === "source_only";

  const secondaryClass =
    "rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-on-surface hover:text-white hover:bg-white/[0.06]";

  return (
    <div className="mt-4 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <PrimaryAction signal={signal} linkStatus={linkStatus} />
        {showCaution && (
          <span className="text-[11px] text-on-surface-variant/60">
            Caution: link status uncertain
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Link
          href={commandHref(`Explain fit — ${titleCompany}`)}
          className={secondaryClass}
        >
          Explain fit
        </Link>
        <Link
          href={commandHref(`Track this job — ${titleCompany}`)}
          className={secondaryClass}
        >
          Track
        </Link>
        <Link
          href={commandHref(`Prepare application — ${titleCompany}`)}
          className={secondaryClass}
        >
          Prepare application
        </Link>
        <Link
          href={commandHref(`Mark as applied — ${titleCompany}`)}
          className={secondaryClass}
        >
          Mark as applied
        </Link>
        <Link
          href={commandHref(`Save job — ${titleCompany}`)}
          className={secondaryClass}
        >
          Save
        </Link>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 text-[11px] font-medium text-on-surface-variant hover:text-white hover:bg-white/[0.04]"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

function SignalCard({
  signal,
  linkStatus,
  onSelect,
  onDismiss,
  viewMode,
}: {
  signal: OpportunitySignal;
  linkStatus?: OpportunitySignal["linkStatus"];
  onSelect: (s: OpportunitySignal) => void;
  onDismiss: () => void;
  viewMode: "card" | "list";
}) {
  const isList = viewMode === "list";

  return (
    <GlassPanel
      data-testid="opportunity-card"
      className={`rounded-xl border border-white/10 hover:border-primary/30 transition-all group ${isList ? "p-4" : "p-5"}`}
    >
      <button
        type="button"
        onClick={() => onSelect(signal)}
        className="block w-full text-left"
      >
        {/* Header row */}
        <div
          className={`flex items-start justify-between gap-3 ${isList ? "mb-2" : "mb-3"}`}
        >
          <div className="min-w-0 flex-1">
            <h3
              data-testid="opportunity-card-title"
              className={`font-semibold text-on-surface break-normal ${isList ? "text-base line-clamp-1" : "text-lg line-clamp-2"}`}
            >
              {signal.role}
            </h3>
            <p className="mt-0.5 text-on-surface-variant text-sm break-normal line-clamp-1">
              {signal.company}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <MatchScoreBadge score={signal.matchScore} />
            <LinkStatusBadge status={linkStatus} />
          </div>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-on-surface-variant/60 mb-3">
          <span>{signal.location || "Location unavailable"}</span>
          <span>·</span>
          <span>{signal.source || "Rico job search"}</span>
          <span>·</span>
          <span>{signalDate(signal)}</span>
          <span>·</span>
          <MomentumLabel momentum={signal.momentum} />
        </div>

        {/* Body */}
        <p className="text-sm text-on-surface-variant/80 line-clamp-2 mb-3">
          {signal.whyItFits || "Rico matched this role against your profile."}
        </p>

        {/* Footer hint */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
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
            size={18}
          />
        </div>
      </button>

      <SignalActions
        signal={signal}
        linkStatus={linkStatus}
        onDismiss={onDismiss}
      />
    </GlassPanel>
  );
}

export default function SignalsPage() {
  const { signals, isLoading, error, refetchSignals } = useOrchestration();
  const { getLinkStatus } = useLinkVerification(signals);
  const [selectedSignal, setSelectedSignal] =
    useState<OpportunitySignal | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<"card" | "list">("card");

  const visibleSignals = useMemo(
    () => signals.filter((signal) => !dismissedIds.has(signal.id)),
    [dismissedIds, signals],
  );

  // Sort by match score descending
  const sortedSignals = useMemo(
    () => [...visibleSignals].sort((a, b) => b.matchScore - a.matchScore),
    [visibleSignals],
  );

  const highConfidence = sortedSignals.filter((s) => s.matchScore >= 50);
  const lowConfidence = sortedSignals.filter((s) => s.matchScore < 50);

  const dismissSignal = (id: string) => {
    setDismissedIds((current) => new Set([...current, id]));
    if (selectedSignal?.id === id) setSelectedSignal(null);
  };

  const gridClass =
    viewMode === "list"
      ? "grid grid-cols-1 gap-4"
      : "grid grid-cols-1 xl:grid-cols-2 gap-5";

  const renderSignalGrid = (items: OpportunitySignal[]) => (
    <div data-testid="signals-grid" className={gridClass}>
      {items.map((signal) => (
        <SignalCard
          key={signal.id}
          signal={signal}
          linkStatus={getLinkStatus(signal.id)}
          onSelect={setSelectedSignal}
          onDismiss={() => dismissSignal(signal.id)}
          viewMode={viewMode}
        />
      ))}
    </div>
  );

  return (
    <div
      data-testid="opportunity-radar-page"
      className="relative min-h-screen overflow-x-hidden"
    >
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />
      <TopNav />

      <main className="relative z-10 pt-32 pb-40 px-container-padding-mobile md:px-container-padding-desktop max-w-6xl mx-auto">
        <div className="mb-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <h1
              data-testid="opportunity-radar-title"
              className="font-headline-xl text-headline-xl text-on-surface mb-3"
            >
              Opportunity Radar
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
              Live market signals scored against your profile. Links are
              verified before you apply.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              data-testid="view-mode-toggle-card"
              type="button"
              onClick={() => setViewMode("card")}
              className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors ${viewMode === "card" ? "bg-white/10 text-white" : "text-on-surface-variant hover:text-white"}`}
              aria-label="Card view"
              title="Card view"
            >
              Cards
            </button>
            <button
              data-testid="view-mode-toggle-list"
              type="button"
              onClick={() => setViewMode("list")}
              className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors ${viewMode === "list" ? "bg-white/10 text-white" : "text-on-surface-variant hover:text-white"}`}
              aria-label="List view"
              title="List view"
            >
              Focus list
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className={gridClass}>
            {Array.from({ length: 4 }).map((_, index) => (
              <GlassPanel
                key={index}
                className="p-5 rounded-xl border border-white/10 animate-pulse motion-reduce:animate-none"
              >
                <div className="h-5 w-40 rounded bg-white/5 mb-3" />
                <div className="h-4 w-32 rounded bg-white/5 mb-2" />
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
          <div className="space-y-8">
            {highConfidence.length > 0 && renderSignalGrid(highConfidence)}

            {lowConfidence.length > 0 && (
              <>
                <div className="flex items-center gap-3 pt-2">
                  <div className="h-px flex-1 bg-white/10" />
                  <span className="text-[11px] font-medium text-on-surface-variant/50 uppercase tracking-wider">
                    Below 50% match — review with caution
                  </span>
                  <div className="h-px flex-1 bg-white/10" />
                </div>
                {renderSignalGrid(lowConfidence)}
              </>
            )}
          </div>
        )}
      </main>

      {selectedSignal && (
        <div
          data-testid="opportunity-detail-modal"
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 px-4 py-6 backdrop-blur-sm md:items-center"
        >
          <GlassPanel className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-label-caps text-[10px] text-cyan">
                  {selectedSignal.source || "Rico job search"} ·{" "}
                  {signalDate(selectedSignal)}
                </p>
                <h2 className="mt-3 text-2xl font-semibold text-on-surface break-normal">
                  {selectedSignal.role}
                </h2>
                <p className="mt-2 text-body-md text-on-surface-variant">
                  {selectedSignal.company} ·{" "}
                  {selectedSignal.location || "Location unavailable"}
                </p>
              </div>
              <button
                data-testid="close-modal"
                type="button"
                onClick={() => setSelectedSignal(null)}
                className="shrink-0 rounded-full border border-white/10 px-3 py-1 text-sm text-on-surface-variant hover:text-white"
              >
                Close
              </button>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <MatchScoreBadge score={selectedSignal.matchScore} />
              <MomentumLabel momentum={selectedSignal.momentum} />
              <LinkStatusBadge status={getLinkStatus(selectedSignal.id)} />
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
