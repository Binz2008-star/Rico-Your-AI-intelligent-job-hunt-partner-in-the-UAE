"use client";

import type { ProfilePreview } from "@/lib/api";

interface Props {
  preview: ProfilePreview;
  filename: string;
  extractionQuality?: string;
}

function qualityToPct(q?: string): number {
  if (q === "excellent") return 95;
  if (q === "good") return 82;
  if (q === "partial") return 55;
  if (q === "poor") return 25;
  return 70;
}

function qualityColor(q?: string): string {
  if (q === "excellent" || q === "good") return "bg-emerald-400";
  if (q === "partial") return "bg-gold";
  return "bg-rico-amber";
}

export function CVDraftCard({ preview, filename, extractionQuality }: Props) {
  const pct = qualityToPct(extractionQuality);
  const barColor = qualityColor(extractionQuality);
  const skills = (preview.skills_detected?.length ? preview.skills_detected : preview.skills) ?? [];
  const topSkills = skills.slice(0, 5);
  const extraSkills = skills.length > 5 ? skills.length - 5 : 0;
  const shortName = filename.split("/").pop() ?? filename;

  return (
    <div className="mt-1 space-y-3 rounded-xl border border-border-subtle/60 bg-surface-elevated/50 p-3.5">
      {/* Header row: filename + quality bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5">
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="shrink-0 text-text-muted"
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span className="truncate text-[11px] text-text-muted" title={shortName}>
            {shortName}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <div className="h-1 w-14 overflow-hidden rounded-full bg-overlay/10">
            <div
              className={`h-full rounded-full transition-all duration-700 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-[10px] font-medium tabular-nums text-text-secondary">{pct}%</span>
        </div>
      </div>

      {/* Name + role */}
      <div>
        {preview.name && (
          <p className="text-[14px] font-semibold text-rico-text">{preview.name}</p>
        )}
        <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          {preview.current_role && (
            <span className="text-[12px] text-text-secondary">{preview.current_role}</span>
          )}
          {preview.experience_years != null && preview.experience_years > 0 && (
            <span className="text-[11px] text-text-muted">
              · {preview.experience_years} yr{preview.experience_years !== 1 ? "s" : ""} exp
            </span>
          )}
        </div>
      </div>

      {/* Skills */}
      {topSkills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {topSkills.map((s) => (
            <span
              key={s}
              className="rounded-md border border-border-subtle/50 bg-surface-glass px-2 py-0.5 text-[10px] text-text-secondary"
            >
              {s}
            </span>
          ))}
          {extraSkills > 0 && (
            <span className="rounded-md border border-border-subtle/50 bg-surface-glass px-2 py-0.5 text-[10px] text-text-muted">
              +{extraSkills} more
            </span>
          )}
        </div>
      )}

      {/* Contact confirmation — indicators only, never raw values in chat */}
      {(preview.email || preview.phone) && (
        <div className="flex flex-wrap gap-2 border-t border-border-subtle/30 pt-2.5">
          {preview.email && (
            <span className="inline-flex items-center gap-1 text-[10px] text-text-muted">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="20 6 12 13 4 6" /><rect x="2" y="4" width="20" height="16" rx="2" />
              </svg>
              Email detected
            </span>
          )}
          {preview.phone && (
            <span className="inline-flex items-center gap-1 text-[10px] text-text-muted">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.96a16 16 0 0 0 6.29 6.29l1.06-1.06a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              Phone detected
            </span>
          )}
        </div>
      )}
    </div>
  );
}
