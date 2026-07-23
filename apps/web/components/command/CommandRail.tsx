"use client";

/**
 * CommandRail — slice 4e of the Atelier full-site migration program.
 *
 * The /command right rail ("opportunity panel"), derived from the approved
 * in-repo reference (`components/design-gallery/atelier-console/
 * RicoConsole.tsx` → ShortlistRail): a 300px paper aside on lg+ with a
 * mono-eyebrow SHORTLIST section (job matches Rico surfaced this session),
 * an optional PIPELINE section (application stages seen this session), and
 * a footer link to /applications.
 *
 * DATA CONTRACT — session-derived only, exactly like the reference ("the
 * right rail derives entirely from the [conversation]"): everything shown
 * comes from the existing chat `messages` state via the pure helpers below.
 * No new API calls, no polling, no writes. Items are display-only in this
 * slice; the only interactive element is the existing /applications route
 * link. Authenticated surface only — public/guest never mounts the rail.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import type { JobMatch } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import React from "react";

/* ── Session-derived data (pure, unit-tested) ────────────────────────────── */

export interface RailPipelineEntry {
    key: string;
    company: string;
    title: string;
    /** Pre-localized stage label — built by the caller with its status map. */
    statusLabel: string;
}

/** Minimal shape of a chat message the derivations need. */
export interface RailSourceMessage {
    role: "user" | "rico";
    type?: string;
    matches?: JobMatch[];
    applications?: Array<{ title?: string; company?: string; status?: string }>;
}

/**
 * Collect the job matches surfaced this session, newest first, deduped by
 * title+company (a re-search keeps the newest occurrence), capped at `max`.
 */
export function deriveSessionPicks(
    messages: RailSourceMessage[],
    max = 6,
): JobMatch[] {
    const seen = new Set<string>();
    const picks: JobMatch[] = [];
    for (let i = messages.length - 1; i >= 0 && picks.length < max; i--) {
        const m = messages[i];
        if (m.role !== "rico" || !m.matches?.length) continue;
        for (const match of m.matches) {
            if (picks.length >= max) break;
            const key = `${match.title}|${match.company}`.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            picks.push(match);
        }
    }
    return picks;
}

/** True when a score is real and strong enough for the sun-red "pick" read. */
export function isStrongPick(score: number | null | undefined): boolean {
    if (score == null || score <= 0) return false;
    const s = score > 1 ? score / 100 : score;
    return s >= 0.8;
}

function scoreText(score: number | null | undefined): string | null {
    if (score == null || score <= 0) return null;
    const s = Math.min(1, Math.max(0, score > 1 ? score / 100 : score));
    return `${Math.round(s * 100)}%`;
}

/* ── Rail ────────────────────────────────────────────────────────────────── */

export function CommandRail({
    authenticated,
    picks,
    pipeline,
    open = true,
    variant = "aside",
}: {
    authenticated: boolean;
    picks: JobMatch[];
    pipeline: RailPipelineEntry[];
    /** Desktop visibility — driven by the shell's PanelRight toggle (slice C1). */
    open?: boolean;
    /** "aside": the ≥1200px inline column (own border/background/width).
     *  "bare": content only, no outer chrome — for embedding inside
     *  CommandWorkspaceDrawer (TASK-20260723-002, 768–1199px), which already
     *  supplies its own panel background, border, and heading. Same props,
     *  same real data, same markup below the wrapper either way. */
    variant?: "aside" | "bare";
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);

    if (!authenticated) return null;

    const eyebrow: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 10,
        textTransform: "uppercase",
        letterSpacing: "0.22em",
    };

    const content = (
        <>
            <div className="flex-1 min-h-0 overflow-y-auto p-4" data-testid="command-rail-content">
                {/* Shortlist eyebrow + count */}
                <div className="mb-4 flex items-center justify-between">
                    <span style={{ ...eyebrow, color: c.ink55 }}>{t("cmdRailShortlist")}</span>
                    <span dir="ltr" style={{ ...eyebrow, color: c.ink }} data-testid="command-rail-count">
                        {picks.length}
                    </span>
                </div>

                {picks.length === 0 ? (
                    <p
                        data-testid="command-rail-empty"
                        className="text-[13px] italic leading-relaxed"
                        style={{ color: c.ink55, fontFamily: ATELIER_FONT.body }}
                    >
                        {t("cmdRailEmpty")}
                    </p>
                ) : (
                    <ul className="space-y-2">
                        {picks.map((j) => {
                            const pct = scoreText(j.score);
                            const strong = isStrongPick(j.score);
                            return (
                                <li
                                    key={`${j.title}|${j.company}`}
                                    data-testid="command-rail-pick"
                                    className="rounded-md p-2.5"
                                    style={{ border: `1px solid ${c.hair}`, background: c.inset }}
                                >
                                    <div className="mb-1 flex items-baseline justify-between gap-2">
                                        <span
                                            className="truncate text-[13px] leading-tight"
                                            style={{ color: c.ink, fontFamily: ATELIER_FONT.serif, fontWeight: 600 }}
                                        >
                                            {j.company}
                                        </span>
                                        {pct && (
                                            <span
                                                dir="ltr"
                                                className="shrink-0 text-[10px] tabular-nums"
                                                style={{
                                                    fontFamily: ATELIER_FONT.mono,
                                                    color: strong ? c.red : c.ink55,
                                                }}
                                                data-testid="command-rail-score"
                                            >
                                                {pct}
                                            </span>
                                        )}
                                    </div>
                                    <div
                                        className="truncate text-[10.5px]"
                                        style={{ fontFamily: ATELIER_FONT.mono, color: c.ink70 }}
                                    >
                                        {j.title}
                                    </div>
                                    {j.location && (
                                        <div
                                            className="mt-1 truncate"
                                            style={{ ...eyebrow, fontSize: 10, letterSpacing: "0.18em", color: c.ink40 }}
                                        >
                                            {j.location}
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}

                {/* Pipeline — only when the session surfaced application data */}
                {pipeline.length > 0 && (
                    <>
                        <div className="mb-2 mt-5 flex items-center justify-between">
                            <span style={{ ...eyebrow, color: c.ink55 }}>{t("cmdRailPipeline")}</span>
                            <span dir="ltr" style={{ ...eyebrow, color: c.ink }}>
                                {pipeline.length}
                            </span>
                        </div>
                        <ul className="space-y-1.5">
                            {pipeline.map((p) => (
                                <li
                                    key={p.key}
                                    data-testid="command-rail-pipeline"
                                    className="rounded-md p-2"
                                    style={{ border: `1px solid ${c.hair}`, background: c.inset }}
                                >
                                    <div className="flex items-baseline justify-between gap-2">
                                        <span
                                            className="truncate text-[12.5px] leading-tight"
                                            style={{ color: c.ink, fontFamily: ATELIER_FONT.serif, fontWeight: 600 }}
                                        >
                                            {p.company || p.title}
                                        </span>
                                        <span
                                            className="shrink-0"
                                            style={{ ...eyebrow, fontSize: 9, color: c.red }}
                                        >
                                            {p.statusLabel}
                                        </span>
                                    </div>
                                    {p.company && p.title && (
                                        <div
                                            className="mt-0.5 truncate text-[10px]"
                                            style={{ fontFamily: ATELIER_FONT.mono, color: c.ink55 }}
                                        >
                                            {p.title}
                                        </div>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </>
                )}
            </div>

            {/* Footer — existing route, the rail's only interactive element */}
            <div className="p-4 pt-0">
                <Link
                    href="/applications"
                    data-testid="command-rail-applications-link"
                    className="atl-rail-link inline-flex items-center gap-1.5 transition-colors"
                    style={{ ...eyebrow, color: c.ink55, textDecoration: "none" }}
                >
                    {t("cmdRailOpenApplications")} →
                </Link>
                <style dangerouslySetInnerHTML={{ __html: `
                    .atl-rail-link:hover { color: ${c.red} !important; }
                ` }} />
            </div>
        </>
    );

    if (variant === "bare") {
        return <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">{content}</div>;
    }

    return (
        <aside
            data-testid="command-rail"
            className={`hidden w-[272px] shrink-0 flex-col overflow-hidden ${open ? "min-[1200px]:flex" : ""}`}
            style={{ borderInlineStart: `1px solid ${c.hair}`, background: c.panel }}
            aria-label={t("cmdRailShortlist")}
        >
            {content}
        </aside>
    );
}
