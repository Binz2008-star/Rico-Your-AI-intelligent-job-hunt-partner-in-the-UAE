"use client";

/**
 * JobMatchCardAtelier — the authenticated `/command` MATCH job card, re-applied
 * on the merged Atelier surface (#1060; owner decision DEC-20260716-001 retires
 * the "Obsidian" naming).
 *
 * The authenticated `/command` surface renders the job-match card in the
 * canonical MATCH structure: display-font role title + RICO PICKS pill +
 * ScorePip, mono meta line, accent-bordered "WHY IT FITS YOU" `→` bullets,
 * italic "HONEST GAPS", and the action row. Extracted into its own module
 * (rather than living inline in `app/command/page.tsx`) because a Next.js App
 * Router `page.tsx` may not carry arbitrary named exports, and this component is
 * unit-tested directly.
 *
 * The public/guest surface keeps the unchanged inline `JobMatchCard` in
 * page.tsx, so the guest palette/structure is untouched. `SourceQualityBadge`
 * and `JobFallbackActions` are brought here too (both are shared by the two
 * cards); their markup/behaviour is verbatim from the original page.tsx
 * definitions, so the rendered output of those sub-components is unchanged.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import type { JobMatch } from "@/lib/api";
import { buildCopyText, getJobFallbackActions, resolveJobLink } from "@/lib/job-fallback";
import { useTranslation } from "@/lib/translations";
import React, { useState } from "react";

type VerificationStatus = JobMatch["verification_status"];

/**
 * Interpolate a localized format string (e.g. "Job match: {title} at {company}"
 * or the RTL "{label}: {title} لدى {company}") with the given values. Keeps
 * every screen-reader label localized instead of a hardcoded English join.
 */
function fmt(template: string, vars: Record<string, string>): string {
    return template.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? `{${k}}`);
}

/** Convert a 0–1 Tailwind alpha to the two-hex-digit suffix for a hex colour. */
const A = {
    /** /40 → ~0.40 */ b40: "66",
    /** /50 → ~0.50 */ b50: "80",
    /** /30 → ~0.30 */ b30: "4d",
    /** /20 → ~0.20 */ b20: "33",
    /** /10 → ~0.10 */ b10: "1a",
} as const;

export function SourceQualityBadge({ status }: { status: VerificationStatus }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    if (!status) return null;
    if (status === "live_verified") {
        // Verified badge carries the Atelier accent (sun-red) from the palette —
        // NOT the retired `gold` token. Palette-driven inline style so it reads
        // `c.red` directly, independent of any channel-remap wrapper.
        return (
            <span
                title={t("cmdBadgeVerifiedTitle")}
                data-testid="job-badge-verified"
                className="text-[9px] px-1.5 py-0.5 rounded shrink-0"
                style={{ border: `1px solid ${c.red}${A.b40}`, color: c.red }}
            >
                {t("cmdBadgeVerifiedLabel")}
            </span>
        );
    }
    if (status === "login_required") {
        return (
            <span title={t("cmdBadgeLoginTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-rico-amber/40 text-rico-amber shrink-0">
                {t("cmdBadgeLoginLabel")}
            </span>
        );
    }
    if (status === "rate_limited") {
        return (
            <span title={t("cmdBadgeRateLimitTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-rico-amber/40 text-rico-amber shrink-0">
                {t("cmdBadgeRateLimitLabel")}
            </span>
        );
    }
    if (status === "aggregator_untrusted") {
        return (
            <span title={t("cmdBadgeAggregatorTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-border-soft text-text-muted shrink-0">
                {t("cmdBadgeAggregatorLabel")}
            </span>
        );
    }
    if (status === "google_intermediary") {
        return (
            <span title={t("cmdBadgeSearchLinkTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-rico-amber/30 text-rico-amber shrink-0">
                {t("cmdBadgeSearchLinkLabel")}
            </span>
        );
    }
    if (status === "needs_source_verification" || status === "lead_needs_verification") {
        return (
            <span title={t("cmdBadgeNeedsVerifTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-border-soft text-text-muted shrink-0 italic">
                {t("cmdBadgeNeedsVerifLabel")}
            </span>
        );
    }
    return null;
}

/**
 * JobFallbackActions — safe, honestly-labelled actions for a job card whose
 * direct apply/source link is unavailable or degraded (login_required,
 * rate_limited, aggregator_untrusted, google_intermediary, or missing).
 *
 * Guarantees a card is never a dead-end without re-introducing BUG-03: none of
 * these are presented as a verified "Apply" link. They are user-initiated
 * searches (company site / Google / LinkedIn), a clipboard copy, and a save to
 * the pipeline. Safety/source gating is untouched — we never surface the bad
 * provider URL itself.
 */
export function JobFallbackActions({ match, onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const [copied, setCopied] = useState(false);

    const actions = getJobFallbackActions({ title: match.title, company: match.company, employer_url: match.employer_url });

    // Localized "{title} at {company}" join reused in every fallback aria-label.
    const atCompany = fmt(t("cmdJobAtCompany"), { title: match.title ?? "", company: match.company ?? "" });
    const ariaFor = (label: string) => fmt(t("cmdAriaJobAction"), { label, job: atCompany });

    const labelFor: Record<string, string> = {
        company_website: t("cmdFallbackCompanyWebsite"),
        company_site: t("cmdFallbackCompanySite"),
        linkedin: t("cmdFallbackLinkedIn"),
        google: t("cmdFallbackGoogle"),
        copy: copied ? t("cmdFallbackCopied") : t("cmdFallbackCopy"),
        save: t("cmdFallbackSave"),
    };

    const handleCopy = async () => {
        const text = buildCopyText(match.title ?? "", match.company ?? "");
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Clipboard unavailable (insecure context / denied) — fall back to a
            // chat prompt so the action is never silently lost.
            onAction(`Search for ${text}`);
        }
    };

    // Neutral link/copy chips. Focus ring is palette-driven (sun-red) via an
    // inline `--tw-ring-color`, which Tailwind's `focus-visible:ring-2` reads —
    // no hard-coded `gold` ring. The var is harmless until the ring width shows.
    const linkClass =
        "rounded-md border border-border-soft bg-surface-glass px-2.5 py-1.5 text-[10px] text-text-secondary transition-colors hover:border-border-subtle hover:text-rico-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-surface";
    const ringStyle = { ["--tw-ring-color" as string]: `${c.red}${A.b50}` } as React.CSSProperties;

    return (
        <div className="flex flex-col gap-1.5" data-testid="job-fallback-actions">
            <span className="text-[9px] text-text-muted italic">{t("cmdNoDirectApply")}</span>
            <div className="flex flex-wrap items-center gap-1.5">
                {actions.map((a) => {
                    if (a.kind === "link") {
                        return (
                            <a
                                key={a.key}
                                href={a.href}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={`job-fallback-${a.key}`}
                                aria-label={ariaFor(labelFor[a.key])}
                                className={linkClass}
                                style={ringStyle}
                            >
                                {labelFor[a.key]}
                            </a>
                        );
                    }
                    if (a.kind === "copy") {
                        return (
                            <button
                                key={a.key}
                                type="button"
                                onClick={handleCopy}
                                data-testid={`job-fallback-${a.key}`}
                                aria-label={ariaFor(labelFor[a.key])}
                                className={linkClass}
                                style={ringStyle}
                            >
                                {labelFor[a.key]}
                            </button>
                        );
                    }
                    return (
                        <button
                            key={a.key}
                            type="button"
                            onClick={() => onAction(`Save ${match.title} at ${match.company} to my pipeline`)}
                            data-testid={`job-fallback-${a.key}`}
                            aria-label={ariaFor(labelFor[a.key])}
                            className="rounded-md px-2.5 py-1.5 text-[10px] font-medium transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-surface"
                            style={{
                                border: `1px solid ${c.red}${A.b30}`,
                                background: `${c.red}${A.b10}`,
                                color: c.red,
                                ...ringStyle,
                            }}
                        >
                            {labelFor[a.key]}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

/**
 * ScorePip — tiered fit indicator for the Atelier MATCH card.
 *
 * Maps a REAL match score (0–1) to an accent-intensity tier: strong ≥0.8 (solid
 * accent plate), mid 0.6–0.79 (medium — outlined accent), low <0.6 (dim). Mono
 * `FIT · n%`. Only rendered by JobMatchCardAtelier when a real score exists
 * (scorePct is non-null), so no fabricated numeral is ever shown. The accent is
 * the route's single signal (`c.red` = Atelier sun-red on this surface).
 */
function ScorePip({ score, scorePct, accent, contrastInk, fitLabel }: {
    score: number;
    scorePct: string;
    accent: string;
    contrastInk: string;
    fitLabel: string;
}) {
    const tier = score >= 0.8 ? "strong" : score >= 0.6 ? "mid" : "low";
    const filled = tier === "strong";
    return (
        <span
            data-testid="job-score"
            data-score-tier={tier}
            className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 animate-pop-in motion-reduce:animate-none"
            style={{
                fontFamily: ATELIER_FONT.mono,
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.08em",
                border: `1px solid ${accent}`,
                background: filled ? accent : "transparent",
                color: filled ? contrastInk : accent,
                opacity: tier === "low" ? 0.6 : 1,
            }}
        >
            {fitLabel} · {scorePct}
        </span>
    );
}

/**
 * JobMatchCardAtelier — the authenticated `/command` job-match card in the
 * canonical MATCH structure: display-font role title + RICO PICKS pill +
 * ScorePip, mono meta line, accent-bordered "WHY IT FITS YOU" `→` bullets,
 * italic "HONEST GAPS", and the action row.
 *
 * PRESERVES EVERY REAL AFFORDANCE of the production card verbatim — the exact
 * same apply/source/alt link decision tree (BUG-03 safe), JobFallbackActions
 * for dead-end-free cards, the "mark as applied" follow-up, and the
 * verification SourceQualityBadge row. Phase 5 of #1262: the SAVE / SKIP
 * buttons are retired — Rico's results message speaks the equivalent ("save
 * the first job" / "skip the second one"), which routes through the same
 * agent_runtime pipeline the buttons used. The apply/source links stay: they
 * are real external affordances, not suggestions.
 *
 * Accent: uses the workspace palette (`c.red` = Atelier sun-red here) directly,
 * so the card carries the single route signal with no hard-coded gold/lime hex.
 * This component renders ONLY on the authenticated Atelier surface; the
 * public/guest surface keeps the unchanged `JobMatchCard` (see render site), so
 * the guest palette is untouched. No data is fabricated: WHY reasons come from
 * `match.match_reasons` (fallback `why`), gaps from `match.match_concerns`, and
 * the block is omitted entirely when the source field is empty.
 */
/** idle → pending → success (only after confirmed completion) → error (safe
 *  retry back to pending). Never skips straight to success on click. */
type ApplyState = "idle" | "pending" | "success" | "error";

export function JobMatchCardAtelier({
    match,
    onAction,
    onMarkApplied,
}: {
    match: JobMatch;
    onAction: (prompt: string) => void;
    /** Confirms the "I've applied…" turn actually produced a real, non-error
     *  reply before the card is allowed to claim success. Optional so
     *  existing callers/tests that don't wire it keep working — the card
     *  simply stays in "idle" (never confirms) without it. */
    onMarkApplied?: (prompt: string) => Promise<boolean>;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const [linkOpened, setLinkOpened] = useState(false);
    const [applyState, setApplyState] = useState<ApplyState>("idle");

    async function handleMarkApplied() {
        // Guards duplicate clicks: a second click while pending, or after
        // success, is a no-op — matches PermissionRequestCard/ProposedChangeCard.
        if (applyState === "pending" || applyState === "success" || !onMarkApplied) return;
        setApplyState("pending");
        const ok = await onMarkApplied(`I've applied to ${match.title} at ${match.company}`);
        setApplyState(ok ? "success" : "error");
    }

    const accent = c.red; // route's single signal — Atelier sun-red on this surface
    const contrastInk = c.bg; // readable text on an accent-filled plate

    // Score — real score only (null when no scorer ran; never a default).
    // Mirror of JobMatchCard's clamp so the two surfaces agree exactly.
    const _rawScore = match.score ?? null;
    const score = _rawScore != null ? Math.min(1, Math.max(0, _rawScore > 1 ? _rawScore / 100 : _rawScore)) : null;
    const scorePct = score != null && score > 0 ? `${Math.round(score * 100)}%` : null;
    const strong = score != null && score >= 0.8;

    // WHY IT FITS YOU — real reasons only; fall back to the single `why` string.
    const whyReasons = match.match_reasons && match.match_reasons.length > 0
        ? match.match_reasons
        : (match.why ? [match.why] : []);
    // HONEST GAPS — real concerns only; block omitted entirely when absent.
    const gaps = match.match_concerns ?? [];

    const vStatus = match.verification_status;

    // ── Link resolution — SHARED with the public JobMatchCard via resolveJobLink
    // so the apply/source/alt/unavailable decision (BUG-03 trust gating) can
    // never drift between the two cards. Labels come back as translation keys.
    const { linkHref, linkLabelKey, linkTestId, sourceUrl, altUrl, isBadPrimary, showSource } =
        resolveJobLink(match);
    const linkLabel = linkLabelKey ? t(linkLabelKey) : "";

    // Localized screen-reader strings — the "{title} at {company}" join is the
    // shared translated fragment reused across every aria-label (EN + AR).
    const atCompany = fmt(t("cmdJobAtCompany"), { title: match.title ?? "", company: match.company ?? "" });
    const ariaMatch = fmt(t("cmdAriaJobMatch"), { job: atCompany });
    const ariaFor = (label: string) => fmt(t("cmdAriaJobAction"), { label, job: atCompany });

    const EYEBROW: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 10,
        letterSpacing: language === "ar" ? "0" : "0.18em",
        textTransform: language === "ar" ? "none" : "uppercase",
        color: c.ink55,
    };
    const metaStyle: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 11,
        letterSpacing: language === "ar" ? "0" : "0.02em",
        color: c.ink55,
    };

    return (
        <article
            className="atl-match-card mt-2 rounded-xl px-3.5 py-3 animate-fade-up motion-reduce:animate-none"
            aria-label={ariaMatch}
            data-testid="opportunity-card"
            style={{
                background: c.panel,
                border: `1px solid ${strong ? `${accent}59` : c.hair}`,
                boxShadow: strong ? `0 0 0 1px ${accent}1f, 0 8px 22px rgba(0,0,0,0.28)` : "none",
            }}
        >
            {/* Header — title + RICO PICKS pill + ScorePip */}
            <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3
                            data-testid="opportunity-card-title"
                            className="min-w-0 break-words"
                            style={{ fontFamily: ATELIER_FONT.body, fontSize: 18, fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.01em", color: c.ink }}
                        >
                            {match.title}
                        </h3>
                        {strong && (
                            <span
                                data-testid="job-rico-picks"
                                className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 animate-fade-in-scale motion-reduce:animate-none"
                                style={{ fontFamily: ATELIER_FONT.mono, fontSize: 9, fontWeight: 600, letterSpacing: language === "ar" ? "0" : "0.14em", textTransform: language === "ar" ? "none" : "uppercase", color: accent, border: `1px solid ${accent}80`, background: `${accent}14` }}
                            >
                                ✦ {t("cmdMatchPicks")}
                            </span>
                        )}
                    </div>
                    {/* Mono meta — company / city / salary (real fields only) */}
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5" style={metaStyle}>
                        <span className="break-words">{match.company}</span>
                        {match.location && (<><span aria-hidden="true">·</span><span className="break-words">{match.location}</span></>)}
                        {match.salary && (<><span aria-hidden="true">·</span><span className="break-words">{match.salary}</span></>)}
                    </div>
                </div>
                {scorePct && (
                    <ScorePip score={score!} scorePct={scorePct} accent={accent} contrastInk={contrastInk} fitLabel={t("cmdMatchFit")} />
                )}
            </div>

            {/* WHY IT FITS YOU — accent start-border, → bullets from real reasons */}
            {whyReasons.length > 0 && (
                <div className="mt-3" style={{ borderInlineStart: `2px solid ${accent}`, paddingInlineStart: 12 }}>
                    <div style={EYEBROW}>{t("cmdMatchWhy")}</div>
                    <ul className="mt-1.5 space-y-1" data-testid="job-why-fits">
                        {whyReasons.map((r, i) => (
                            <li key={i} className="flex gap-2" style={{ fontSize: 13, lineHeight: 1.5, color: c.ink70 }}>
                                <span aria-hidden="true" style={{ color: accent }}>→</span>
                                <span className="min-w-0">{r}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* HONEST GAPS — italic, real concerns only; omitted when none */}
            {gaps.length > 0 && (
                <div className="mt-3" data-testid="job-honest-gaps">
                    <div style={EYEBROW}>{t("cmdMatchGaps")}</div>
                    <ul className="mt-1 space-y-0.5">
                        {gaps.map((g, i) => (
                            <li key={i} className="flex gap-2" style={{ fontSize: 12.5, fontStyle: "italic", lineHeight: 1.5, color: c.ink55 }}>
                                <span aria-hidden="true">·</span>
                                <span className="min-w-0">{g}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Action row — primary apply link (real, verified affordance).
                Phase 5 of #1262: SAVE/SKIP buttons retired — spoken in the
                results message instead. */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
                {linkHref ? (
                    <a
                        href={linkHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={linkTestId}
                        aria-label={ariaFor(linkLabel)}
                        onClick={() => setLinkOpened(true)}
                        className="rounded-md px-3 py-1.5 text-[11px] font-semibold transition-[opacity,transform] duration-150 hover:opacity-90 hover:-translate-y-px active:translate-y-0 active:scale-[0.98]"
                        style={{ background: c.ink, color: c.bg }}
                    >
                        {linkLabel}
                    </a>
                ) : (
                    <span className="text-[10px] italic" data-testid="job-link-unavailable" style={{ color: c.ink55 }}>
                        {t("cmdLinkUnavailable")}
                    </span>
                )}
                {showSource && (
                    <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="job-link-source"
                        aria-label={ariaFor(t("cmdViewSource"))}
                        className="rounded-md px-3 py-1.5 text-[11px] transition-[opacity,transform] duration-150 hover:opacity-80 active:scale-[0.98]"
                        style={{ border: `1px solid ${c.hair}`, color: c.ink70 }}
                    >
                        {t("cmdViewSource")}
                    </a>
                )}
            </div>

            {/* Safe fallback CTAs — the card is never a dead-end (BUG-03 preserved) */}
            {!linkHref && (
                <div className="mt-2">
                    <JobFallbackActions match={match} onAction={onAction} />
                </div>
            )}

            {/* Mark as Applied — appears after the user opens the apply link.
                State machine: idle → pending → success (only once onMarkApplied
                resolves true) → error (safe retry, same button). Never shows
                the confirmed state before the backend-round-trip settles. */}
            {linkOpened && applyState !== "success" && (
                <button
                    type="button"
                    data-testid="job-mark-applied"
                    onClick={handleMarkApplied}
                    disabled={applyState === "pending" || !onMarkApplied}
                    aria-live="polite"
                    className="mt-2 w-full rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] font-medium text-emerald-200 transition-colors hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-70 animate-in fade-in slide-in-from-bottom-1"
                >
                    {applyState === "pending" ? t("cmdMarkAppliedPending") : t("cmdMarkApplied")}
                </button>
            )}
            {applyState === "error" && (
                <p data-testid="job-mark-applied-error" role="alert" aria-live="assertive" className="mt-1.5 text-[10px] text-red-400">
                    {t("cmdMarkAppliedError")}
                </p>
            )}
            {applyState === "success" && (
                <p data-testid="job-mark-applied-success" role="status" aria-live="polite" className="mt-2 text-[10px] font-medium text-emerald-300">✓ {t("cmdMarkAppliedConfirm")}</p>
            )}

            {/* Source quality row — verification status + honest link notes */}
            {vStatus && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <SourceQualityBadge status={vStatus} />
                    {vStatus === "google_intermediary" && altUrl && (
                        <span className="text-[9px] italic" style={{ color: c.ink55 }}>{t("cmdGoogleJobsNote")}</span>
                    )}
                    {isBadPrimary && vStatus !== "google_intermediary" && (altUrl || sourceUrl) && (
                        <span className="text-[9px] italic" style={{ color: c.ink55 }}>{t("cmdAltLinkNote")}</span>
                    )}
                </div>
            )}
        </article>
    );
}
