"use client";

import { fetchProfile, type ProfileResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useCallback, useEffect, useState } from "react";

// ── Field definitions ─────────────────────────────────────────────────────────

interface FieldDef {
  key: string;
  label: string;
  group: "identity" | "targeting" | "experience";
  present: (p: ProfileResponse) => boolean;
}

const FIELDS: FieldDef[] = [
  { key: "name",              label: "Name",             group: "identity",   present: (p) => Boolean(p.name) },
  { key: "visa_status",       label: "Visa status",      group: "identity",   present: (p) => Boolean(p.visa_status) },
  { key: "target_roles",      label: "Target roles",     group: "targeting",  present: (p) => Boolean(p.target_roles?.length) },
  { key: "preferred_cities",  label: "Preferred cities", group: "targeting",  present: (p) => Boolean(p.preferred_cities?.length) },
  { key: "salary",            label: "Salary expectation", group: "targeting", present: (p) => p.salary_expectation_aed != null },
  { key: "current_role",      label: "Current role",     group: "experience", present: (p) => Boolean(p.current_role) },
  { key: "years_experience",  label: "Years of experience", group: "experience", present: (p) => p.years_experience != null },
  { key: "skills",            label: "Skills (from CV)", group: "experience", present: (p) => Boolean(p.skills?.length) },
];

const GROUP_LABELS: Record<FieldDef["group"], string> = {
  identity:   "Identity",
  targeting:  "Job targeting",
  experience: "Experience",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function FieldRow({ label, present }: { label: string; present: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-overlay/6 last:border-0">
      <span className="text-[12px] text-text-secondary">{label}</span>
      {present ? (
        <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
          <MaterialIcon icon="check_circle" size={12} />
          Provided
        </span>
      ) : (
        <span className="flex items-center gap-1 text-[11px] text-text-tertiary">
          <MaterialIcon icon="radio_button_unchecked" size={12} />
          Missing
        </span>
      )}
    </div>
  );
}

function TargetRoleProvenance({ roles }: { roles: string[] }) {
  return (
    <div className="mt-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-tertiary mb-2">
        Target roles · source: profile
      </p>
      <div className="flex flex-wrap gap-1.5">
        {roles.map((role) => (
          <span
            key={role}
            className="inline-flex items-center gap-1 rounded-full border border-gold/20 bg-gold/8 px-2.5 py-0.5 text-[11px] font-medium text-gold"
          >
            {role}
          </span>
        ))}
      </div>
    </div>
  );
}

function ReadinessBar({ score }: { score: number }) {
  const pct = Math.round(Math.min(100, Math.max(0, score * 100)));
  const color =
    pct >= 80 ? "bg-emerald-500" :
    pct >= 50 ? "bg-gold" :
    "bg-rose-500";

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 rounded-full bg-overlay/12 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("shrink-0 text-[13px] font-semibold tabular-nums", color.replace("bg-", "text-"))}>
        {pct}%
      </span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ProfileReadinessCard() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");

  const load = useCallback(async () => {
    try {
      const data = await fetchProfile();
      setProfile(data);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const cardClass =
    "rico-card rounded-2xl border border-border-soft bg-surface-elevated/70 p-5 md:p-6 flex flex-col gap-4 shadow-sm transition-all duration-300";

  if (status === "loading") {
    return (
      <div className={cardClass}>
        <div className="animate-pulse space-y-3">
          <div className="h-3 w-28 rounded bg-white/5" />
          <div className="h-1.5 rounded-full bg-white/5" />
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => <div key={i} className="h-3 rounded bg-white/5" />)}
          </div>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">Profile Readiness</p>
        <p className="text-[13px] text-text-tertiary">Could not load profile data.</p>
        <button onClick={load} className="text-[11px] text-gold hover:underline">Retry</button>
      </div>
    );
  }

  if (!profile?.profile_exists) {
    return (
      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-text-secondary">Profile Readiness</p>
        <p className="text-[13px] text-text-tertiary">
          Not enough evidence — complete your profile to see a readiness breakdown.
        </p>
      </div>
    );
  }

  const score = profile.completeness_score ?? 0;
  const groups = (["identity", "targeting", "experience"] as FieldDef["group"][]);
  const roles = profile.target_roles ?? [];

  return (
    <div className={cardClass}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">
          Profile Readiness
        </span>
        <span className="rounded-full bg-surface-glass px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-text-tertiary">
          Live
        </span>
      </div>

      <ReadinessBar score={score} />

      {/* Field breakdown by group */}
      <div className="space-y-4">
        {groups.map((group) => {
          const fields = FIELDS.filter((f) => f.group === group);
          return (
            <div key={group}>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-tertiary">
                {GROUP_LABELS[group]}
              </p>
              {fields.map((f) => (
                <FieldRow key={f.key} label={f.label} present={f.present(profile)} />
              ))}
            </div>
          );
        })}
      </div>

      {/* Target role provenance */}
      {roles.length > 0 ? (
        <TargetRoleProvenance roles={roles} />
      ) : (
        <p className="text-[12px] text-text-tertiary">
          <span className="text-amber-400 font-semibold">Target roles:</span> Not enough evidence — add roles via{" "}
          <a href="/onboarding" className="underline hover:text-gold transition-colors">onboarding</a>.
        </p>
      )}
    </div>
  );
}
