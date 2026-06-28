"use client";

import { useCallback, useEffect, useState } from "react";
import { getMission, type MissionState } from "@/lib/api";

interface Props {
  onAction: (prompt: string) => void;
}

export function MissionContextBar({ onAction }: Props) {
  const [mission, setMission] = useState<MissionState | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const m = await getMission();
      setMission(m);
    } catch {
      // Non-fatal — bar stays hidden if mission endpoint unreachable
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    // Slight delay so the chat thread loads first and the bar appears as a
    // secondary context layer, not as a blocking loader.
    const id = window.setTimeout(() => void load(), 600);
    return () => window.clearTimeout(id);
  }, [load]);

  // Stay hidden until data arrives — prevents a layout jump on cold load.
  if (!loaded || !mission) return null;

  const pct = mission.progress_score;
  const role = mission.target_roles[0] ?? null;
  const city = mission.target_locations[0] ?? null;
  const hasMission = role || city;
  const isComplete = pct === 100;

  const quickAction = isComplete
    ? { label: "Find matching jobs →", prompt: "Find UAE jobs that match my CV and experience." }
    : mission.next_recommendation
      ? { label: "Fix this →", prompt: mission.next_recommendation }
      : null;

  return (
    <div className="shrink-0 border-b border-border-subtle/30 bg-surface-elevated/30 backdrop-blur-sm animate-in fade-in duration-300 motion-reduce:animate-none">
      {/* Collapsed bar — always visible, full width */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-start transition-colors hover:bg-surface-elevated/50 sm:px-4 rico-focus-strong"
        aria-expanded={expanded}
        aria-label="Mission context"
      >
        {/* Pulse dot */}
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${isComplete ? "bg-emerald-400" : "bg-gold animate-pulse"}`}
          aria-hidden="true"
        />

        {/* Mission label */}
        <span className="flex min-w-0 flex-1 items-baseline gap-1.5 truncate">
          {hasMission ? (
            <>
              {role && (
                <span className="truncate text-[11px] font-semibold text-rico-text">{role}</span>
              )}
              {role && city && (
                <span className="text-[10px] text-text-muted">·</span>
              )}
              {city && (
                <span className="text-[11px] text-text-secondary">{city}</span>
              )}
            </>
          ) : (
            <span className="text-[11px] text-text-muted">Set your career mission</span>
          )}
        </span>

        {/* Progress — bar on md+, pct pill on mobile */}
        <span className="flex shrink-0 items-center gap-2">
          <span className="hidden items-center gap-1.5 sm:flex">
            <span className="h-1 w-16 overflow-hidden rounded-full bg-overlay/10">
              <span
                className="block h-full rounded-full bg-gold transition-all duration-700"
                style={{ width: `${pct}%` }}
              />
            </span>
          </span>
          <span
            className={`text-[10px] font-semibold tabular-nums ${isComplete ? "text-emerald-400" : "text-gold"}`}
          >
            {pct}%
          </span>

          {/* Chevron */}
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`text-text-muted transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path d="M1 1l4 4 4-4" />
          </svg>
        </span>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="border-t border-border-subtle/20 px-3 py-2.5 sm:px-4 animate-in slide-in-from-top-1 duration-150 motion-reduce:animate-none">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              {mission.next_recommendation && !isComplete && (
                <p className="text-[11px] leading-relaxed text-text-secondary">
                  <span className="text-gold" aria-hidden="true">→ </span>
                  {mission.next_recommendation}
                </p>
              )}
              {isComplete && (
                <p className="text-[11px] text-emerald-400">
                  Profile complete — Rico is ready to find your best matches.
                </p>
              )}
            </div>
            {quickAction && (
              <button
                type="button"
                onClick={() => {
                  onAction(quickAction.prompt);
                  setExpanded(false);
                }}
                className="shrink-0 rounded-lg border border-gold/30 bg-gold/8 px-2.5 py-1 text-[10px] font-medium text-gold transition-colors hover:bg-gold/15 rico-focus-strong"
              >
                {quickAction.label}
              </button>
            )}
          </div>

          {/* Missing factors — compact chips when profile is incomplete */}
          {mission.missing_factors.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {mission.missing_factors.map((f) => {
                const label: Record<string, string> = {
                  cv_uploaded: "Upload CV",
                  roles_set: "Set target role",
                  locations_set: "Set city",
                  pipeline_active: "Search jobs",
                };
                return (
                  <span
                    key={f}
                    className="rounded-md border border-border-subtle/50 bg-surface-glass px-2 py-0.5 text-[10px] text-text-muted"
                  >
                    {label[f] ?? f}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
