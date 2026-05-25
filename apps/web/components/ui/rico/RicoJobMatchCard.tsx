"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";
import { RicoGlassIsland } from "./RicoGlassIsland";
import { RicoPill } from "./RicoPill";
import { RicoButton } from "./RicoButton";
import { RicoStatusNode } from "./RicoStatusNode";

export interface JobMatchData {
  title: string;
  company: string;
  location?: string;
  score?: number;
  confidence?: "high" | "medium" | "low";
  match_reasons?: string[];
  match_concerns?: string[];
  missing_facts?: string[];
  recommended_action?: string;
  actions?: string[];
  why?: string; // Legacy fallback field for backward compatibility
  // Job authenticity fields (optional — absent on older responses)
  apply_url?: string;
  source_url?: string;
  verification_status?: "live" | "lead_needs_verification";
}

interface RicoJobMatchCardProps {
  match: JobMatchData;
  onActionClick?: (action: string, job: JobMatchData) => void;
  className?: string;
}

/**
 * RicoJobMatchCard — Design system job match card
 *
 * Composition shell using Rico primitives:
 * - RicoGlassIsland for container
 * - RicoPill for score, missing facts
 * - RicoButton for actions
 * - RicoStatusNode for status indicators
 *
 * Structure:
 * - header: title, company, location, score pill
 * - reasons section: positive RicoStatusNode list
 * - concerns section: warning RicoStatusNode list
 * - missing facts section: RicoPill list
 * - recommended action section
 * - footer action buttons
 *
 * Tolerates missing optional fields gracefully.
 * No API calls or job mutation logic inside.
 * All actions go through callback props.
 */
export function RicoJobMatchCard({ match, onActionClick, className }: RicoJobMatchCardProps) {
  // Normalize score to handle both 0-1 and 0-100 ranges
  const rawScore = match.score ?? 0;
  const normalizedScore = rawScore <= 1 ? rawScore * 100 : rawScore;
  const boundedScore = Math.max(0, Math.min(100, normalizedScore));

  const scoreLabel =
    boundedScore >= 80 ? "Strong match" :
    boundedScore >= 60 ? "Good match" :
    "Possible match";

  const getScoreVariant = (): "cyan" | "magenta" | "default" => {
    if (boundedScore >= 80) return "cyan";
    if (boundedScore >= 60) return "default";
    return "magenta";
  };

  const getConfidenceBadge = () => {
    const config = {
      high: { label: "High confidence", variant: "cyan" as const },
      medium: { label: "Medium confidence", variant: "default" as const },
      low: { label: "Needs review", variant: "magenta" as const },
    };
    return config[match.confidence || "medium"];
  };

  const confidenceBadge = getConfidenceBadge();

  return (
    <RicoGlassIsland className={cn("p-4 space-y-3", className)}>
      {/* Header: title, company, location, score */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-[13px] font-semibold text-[var(--rico-fg-1)] leading-tight line-clamp-2" title={match.title}>
            {match.title}
          </h3>
          <p className="text-[11px] text-[var(--rico-fg-3)] mt-0.5 truncate" title={`${match.company}${match.location ? ` · ${match.location}` : ""}`}>
            {match.company}
            {match.location && ` · ${match.location}`}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0 sm:mt-0 flex-wrap justify-end">
          {boundedScore > 0 && (
            <RicoPill variant={getScoreVariant()}>{scoreLabel}</RicoPill>
          )}
          <RicoPill variant={confidenceBadge.variant}>{confidenceBadge.label}</RicoPill>
          {match.verification_status === "lead_needs_verification" && (
            <RicoPill variant="magenta">Lead — verify before applying</RicoPill>
          )}
        </div>
      </div>

      {/* Reasons section */}
      {match.match_reasons && match.match_reasons.length > 0 && (
        <section className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[var(--rico-secondary-dim)] uppercase tracking-wider">
            Why this fits
          </p>
          <ul className="space-y-1">
            {match.match_reasons.slice(0, 4).map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[10px] text-[var(--rico-fg-2)]">
                <RicoStatusNode variant="cyan" className="mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
            {match.match_reasons.length > 4 && (
              <li className="text-[9px] text-[var(--rico-fg-4)] italic">
                +{match.match_reasons.length - 4} more reasons
              </li>
            )}
          </ul>
        </section>
      )}

      {/* Legacy why fallback for backward compatibility */}
      {(!match.match_reasons || match.match_reasons.length === 0) && match.why && (
        <section className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[var(--rico-secondary-dim)] uppercase tracking-wider">
            Why this fits
          </p>
          <p className="text-[10px] text-[var(--rico-fg-2)] leading-relaxed">
            {match.why}
          </p>
        </section>
      )}

      {/* Concerns section */}
      {match.match_concerns && match.match_concerns.length > 0 && (
        <section className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[var(--rico-primary)] uppercase tracking-wider">
            Worth checking
          </p>
          <ul className="space-y-1">
            {match.match_concerns.slice(0, 3).map((concern, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[10px] text-[var(--rico-fg-2)]">
                <RicoStatusNode variant="magenta" className="mt-0.5" />
                <span>{concern}</span>
              </li>
            ))}
            {match.match_concerns.length > 3 && (
              <li className="text-[9px] text-[var(--rico-fg-4)] italic">
                +{match.match_concerns.length - 3} more
              </li>
            )}
          </ul>
        </section>
      )}

      {/* Missing facts section */}
      {match.missing_facts && match.missing_facts.length > 0 && (
        <section className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[var(--rico-fg-3)] uppercase tracking-wider">
            Missing facts
          </p>
          <div className="flex flex-wrap gap-1.5">
            {match.missing_facts.slice(0, 3).map((fact, idx) => (
              <RicoPill key={idx} variant="default" className="text-[9px]">
                {fact}
              </RicoPill>
            ))}
            {match.missing_facts.length > 3 && (
              <RicoPill variant="default" className="text-[9px]">
                +{match.missing_facts.length - 3} more
              </RicoPill>
            )}
          </div>
        </section>
      )}

      {/* Recommended action section */}
      {match.recommended_action && (
        <section className="bg-[rgba(255,177,200,0.08)] border-l-2 border-[var(--rico-primary)] rounded-r-lg px-3 py-2">
          <p className="text-[10px] font-semibold text-[var(--rico-primary)] mb-1">
            Recommended next step
          </p>
          <p className="text-[10px] text-[var(--rico-fg-1)] leading-relaxed line-clamp-2">
            {match.recommended_action}
          </p>
        </section>
      )}

      {/* Footer action buttons */}
      {match.actions && match.actions.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--rico-border-subtle)]">
          {match.actions.map((action, idx) => (
            <RicoButton
              key={action}
              variant={idx === 0 ? "magenta" : "ghost"}
              size="sm"
              onClick={() => onActionClick?.(action, match)}
            >
              {action}
            </RicoButton>
          ))}
        </div>
      )}
    </RicoGlassIsland>
  );
}
