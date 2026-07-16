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
import { buildCopyText, getJobFallbackActions } from "@/lib/job-fallback";
import { useTranslation } from "@/lib/translations";
import React, { useState } from "react";

type VerificationStatus = JobMatch["verification_status"];

export function SourceQualityBadge({ status }: { status: VerificationStatus }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    if (!status) return null;
    if (status === "live_verified") {
        return (
            <span title={t("cmdBadgeVerifiedTitle")} className="text-[9px] px-1.5 py-0.5 rounded border border-gold/40 text-gold shrink-0">
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
    const [copied, setCopied] = useState(false);

    const actions = getJobFallbackActions({ title: match.title, company: match.company, employer_url: match.employer_url });

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

    const linkClass =
        "rounded-md border border-border-soft bg-surface-glass px-2.5 py-1.5 text-[10px] text-text-secondary transition-colors hover:border-border-subtle hover:text-rico-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-1 focus-visible:ring-offset-surface";

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
                                aria-label={`${labelFor[a.key]}: ${match.title} at ${match.company}`}
                                className={linkClass}
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
                                className={linkClass}
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
                            className="rounded-md border border-gold/30 bg-gold/10 px-2.5 py-1.5 text-[10px] font-medium text-gold transition-colors hover:bg-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-1 focus-visible:ring-offset-surface"
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
            className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5"
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
 * verification SourceQualityBadge row. SAVE / SKIP route through the existing
 * `onAction` → `sendMessage` → agent_runtime pipeline (SAVE reuses the exact
 * pipeline-save prompt JobFallbackActions already sends).
 *
 * Accent: uses the workspace palette (`c.red` = Atelier sun-red here) directly,
 * so the card carries the single route signal with no hard-coded gold/lime hex.
 * This component renders ONLY on the authenticated Atelier surface; the
 * public/guest surface keeps the unchanged `JobMatchCard` (see render site), so
 * the guest palette is untouched. No data is fabricated: WHY reasons come from
 * `match.match_reasons` (fallback `why`), gaps from `match.match_concerns`, and
 * the block is omitted entirely when the source field is empty.
 */
export function JobMatchCardAtelier({ match, onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const [linkOpened, setLinkOpened] = useState(false);
    const [markedApplied, setMarkedApplied] = useState(false);

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

    // ── Link resolution — identical decision tree to JobMatchCard (BUG-03 safe).
    const clean = (u?: string) => (u && u !== "#" ? u.trim() : "");
    const _isGoogleIntermediary = (u: string): boolean => {
        if (!u) return false;
        try {
            const p = new URL(u);
            const h = p.hostname.replace(/^www\./, "");
            return h === "jobs.google.com" || (h === "google.com" && p.pathname.includes("/search"));
        } catch { return false; }
    };
    const applyUrl = clean(match.apply_url);
    const sourceUrl = (() => { const u = clean(match.source_url); return _isGoogleIntermediary(u) ? "" : u; })();
    const altUrl = (() => { const u = clean(match.alt_link); return _isGoogleIntermediary(u) ? "" : u; })();
    const isBadPrimary =
        vStatus === "login_required" ||
        vStatus === "rate_limited" ||
        vStatus === "aggregator_untrusted" ||
        vStatus === "google_intermediary";

    let linkHref = "";
    let linkLabel = "";
    let linkTestId = "";
    if (applyUrl && !isBadPrimary) {
        linkHref = applyUrl; linkLabel = t("cmdApply"); linkTestId = "job-link-apply";
    } else if (sourceUrl && !isBadPrimary) {
        linkHref = sourceUrl; linkLabel = t("cmdViewSource"); linkTestId = "job-link-source";
    } else if (vStatus === "google_intermediary" && altUrl) {
        linkHref = altUrl; linkLabel = t("cmdApplySearch"); linkTestId = "job-link-alt";
    } else if (isBadPrimary && (altUrl || sourceUrl)) {
        linkHref = altUrl || sourceUrl; linkLabel = t("cmdApplyAlt"); linkTestId = "job-link-alt";
    }
    const showSource = !!sourceUrl && sourceUrl !== linkHref && !isBadPrimary && !!applyUrl;

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
            className="mt-2 rounded-xl px-3.5 py-3"
            aria-label={`Job match: ${match.title} at ${match.company}`}
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
                                className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5"
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

            {/* Action row — primary apply link (real, verified affordance) + SAVE + SKIP */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
                {linkHref ? (
                    <a
                        href={linkHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={linkTestId}
                        aria-label={`${linkLabel}: ${match.title} at ${match.company}`}
                        onClick={() => setLinkOpened(true)}
                        className="rounded-md px-3 py-1.5 text-[11px] font-semibold transition-opacity hover:opacity-90"
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
                        aria-label={`View source: ${match.title} at ${match.company}`}
                        className="rounded-md px-3 py-1.5 text-[11px] transition-opacity hover:opacity-80"
                        style={{ border: `1px solid ${c.hair}`, color: c.ink70 }}
                    >
                        {t("cmdViewSource")}
                    </a>
                )}
                <button
                    type="button"
                    data-testid="job-action-save"
                    onClick={() => onAction(`Save ${match.title} at ${match.company} to my pipeline`)}
                    className="rounded-md px-3 py-1.5 text-[11px] transition-opacity hover:opacity-80"
                    style={{ border: `1px solid ${c.hair}`, color: c.ink70 }}
                >
                    {t("cmdMatchSave")}
                </button>
                <button
                    type="button"
                    data-testid="job-action-skip"
                    onClick={() => onAction(`Skip ${match.title} at ${match.company}`)}
                    className="rounded-md px-3 py-1.5 text-[11px] transition-opacity hover:opacity-80"
                    style={{ color: c.ink55, background: "transparent", border: "1px solid transparent" }}
                >
                    {t("cmdMatchSkip")}
                </button>
            </div>

            {/* Safe fallback CTAs — the card is never a dead-end (BUG-03 preserved) */}
            {!linkHref && (
                <div className="mt-2">
                    <JobFallbackActions match={match} onAction={onAction} />
                </div>
            )}

            {/* Mark as Applied — appears after the user opens the apply link */}
            {linkOpened && !markedApplied && (
                <button
                    type="button"
                    onClick={() => { setMarkedApplied(true); onAction(`I've applied to ${match.title} at ${match.company}`); }}
                    className="mt-2 w-full rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] font-medium text-emerald-200 transition-colors hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50 animate-in fade-in slide-in-from-bottom-1"
                >
                    {t("cmdMarkApplied")}
                </button>
            )}
            {markedApplied && (
                <p className="mt-2 text-[10px] font-medium text-emerald-300">✓ {t("cmdMarkAppliedConfirm")}</p>
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
