"use client";

/**
 * RailGoalMini — the persistent "Current goal" card in the WorkspaceShell
 * rail (frozen Command Workspace v4 reference, goal-mini region; PR-V4-2a,
 * DEC-20260719-002).
 *
 * Real data only: renders exclusively from a loaded MissionState (the shared
 * useMissionSummary cache). Fail-hidden by contract — a null mission
 * (loading, error, disabled) renders NOTHING, so the shell is byte-identical
 * to the pre-PR chrome whenever data isn't available. The title derives from
 * the structured mission fields via deriveGoalTitle (bilingual; the
 * English-only server `goal` string is never rendered).
 */

import Link from "next/link";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";
import { deriveGoalTitle } from "@/components/workspace/DashboardAtelier";
import type { WorkspacePalette } from "@/components/workspace/theme";
import type { MissionState } from "@/lib/api";

export function RailGoalMini({
    mission,
    language,
    c,
    accentFill,
    onNavigate,
}: {
    mission: MissionState | null;
    language: "en" | "ar";
    c: WorkspacePalette;
    /** Optional v5 gradient for the progress fill (light island); falls back
     *  to the palette accent so the dark island is untouched. */
    accentFill?: string;
    /** Close the mobile drawer when the card navigates. */
    onNavigate?: () => void;
}) {
    if (!mission) return null;

    const pct = Math.max(0, Math.min(100, Math.round(mission.progress_score ?? 0)));
    const title = deriveGoalTitle(mission, language);

    return (
        <Link
            href="/dashboard"
            data-testid="rail-goal-mini"
            onClick={onNavigate}
            className="block rounded-[8px] p-3"
            style={{ background: c.panel, border: `1px solid ${c.hair}`, textDecoration: "none" }}
        >
            <Mono style={{ color: c.ink55 }}>{language === "ar" ? "الهدف الحالي" : "Current goal"}</Mono>
            <div
                className="mt-1 text-[0.9rem] leading-snug"
                style={{ fontFamily: ATELIER_FONT.serif, color: c.ink }}
                data-testid="rail-goal-mini-title"
            >
                {title}
            </div>
            <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: c.track }} aria-hidden="true">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: accentFill ?? c.red }} />
            </div>
            <div className="mt-1">
                <span dir="ltr" style={{ fontFamily: ATELIER_FONT.mono, color: c.ink40, fontSize: 10 }}>{pct}%</span>
            </div>
        </Link>
    );
}
