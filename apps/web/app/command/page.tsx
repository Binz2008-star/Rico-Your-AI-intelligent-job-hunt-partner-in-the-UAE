"use client";

import { MobileCommandHeader } from "@/components/command/MobileCommandHeader";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { MobileBottomNav } from "@/components/layout/MobileBottomNav";
import { useLanguage } from "@/contexts/LanguageContext";
import type { ChatApiResponse, JobMatch, NextAction, ProfilePreview, ProfileUpdatePayload, RicoOption, UploadCVResponse } from "@/lib/api";
import type { RicoAgenticUi, RicoChatAction, RicoProposedChange, RicoAttachmentAnalysis, ExecuteAllowedAction } from "@/lib/schemas";
import { EXECUTE_ALLOWED_ACTIONS } from "@/lib/schemas";
import { bustSidebarCache } from "@/hooks/useSidebarStatus";
import { ChatActionsRow } from "@/components/ui/rico/ChatActionCard";
import { RicoMarkdownContent } from "@/components/ui/rico/RicoMarkdownContent";
import { PermissionRequestCard } from "@/components/ui/rico/PermissionRequestCard";
import { ProposedChangeCard } from "@/components/ui/rico/ProposedChangeCard";
import { AttachmentAnalysisCard } from "@/components/ui/rico/AttachmentAnalysisCard";
import { ApiError, clearChatHistory, confirmCVProfile, executePermissionAction, fetchChatHistory, fetchMe, logout, sendChat, sendChatPublic, sendChatStream, sendChatStreamPublic, submitAction, updateProfile, uploadCV } from "@/lib/api";
import { orchestrationApi } from "@/lib/api/orchestration";
import { buildAuthHref } from "@/lib/redirect";
import { getJobFallbackActions, buildCopyText } from "@/lib/job-fallback";
import { formatTrajectory, looksLikeTrajectoryAnalysis } from "@/lib/trajectoryHelpers";
import { translations, useTranslation, type TranslationKey } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState } from "react";

function ensureSessionId(sessionIdRef: React.MutableRefObject<string | null>): string {
    if (typeof window === "undefined") return sessionIdRef.current || "ssr-session";
    if (!sessionIdRef.current) {
        let sid = localStorage.getItem("rico_sid");
        if (!sid) {
            sid = "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 9);
            localStorage.setItem("rico_sid", sid);
        }
        sessionIdRef.current = sid;
    }
    return sessionIdRef.current;
}

function getSessionId(sessionIdRef: React.MutableRefObject<string | null>): string {
    return ensureSessionId(sessionIdRef);
}

function prefersReducedMotion(): boolean {
    return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

interface ApplicationEntry {
    job_id?: string;
    title?: string;
    company?: string;
    status?: string;
    date_applied?: string | null;
    date_updated?: string | null;
    days_since_applied?: number | null;
    days_since_update?: number | null;
    needs_follow_up?: boolean;
}

interface Message {
    id: number;
    role: "user" | "rico";
    text: string;
    type?: string;
    matches?: JobMatch[];
    applications?: ApplicationEntry[];
    follow_up_needed?: ApplicationEntry[];
    profile_gaps?: string[];
    options?: RicoOption[];
    next_action?: string;
    freeMode?: boolean;
    roleName?: string;
    reasons?: string[];
    next_actions?: NextAction[];
    preview?: ProfilePreview;
    filename?: string;
    extractionQuality?: string;
    docType?: string;
    search_query?: string;
    result_count?: number;
    broadened?: boolean;
    rate_limit_notice?: string;
    streaming?: boolean;
    stale?: boolean;
    agentic_ui?: RicoAgenticUi | null;
    permission_dismissed?: boolean;
    proposed_dismissed?: boolean;
    actions?: RicoChatAction[];
}

type ChatAudience = "checking" | "authenticated" | "public";

// Module-level counter replaced by component-local ref (see _idRef below).
// Kept for import compatibility only; do not use outside CommandPage.
let _id = 0;
function nextId() { return ++_id; }

const QUICK_ACTION_DEFS = [
    { key: "cmdQaFindJobs", prompt: "Find UAE jobs that match my CV and experience." },
    { key: "cmdQaUploadCv", prompt: "__cv_upload__" },
    { key: "cmdQaWhatNext", prompt: "Based on my profile and experience, what's the best next step in my job search?" },
    { key: "cmdQaCareerMove", prompt: "Analyze the best next career move based on my background." },
    { key: "cmdQaApplications", prompt: "Show my job applications and their status." },
    { key: "cmdQaInterview", prompt: "Help me prepare for an upcoming job interview." },
];
const CV_READY_CHIP_DEFS = [
    { key: "cmdCvReadyChipFindJobs", prompt: "Find UAE jobs that match my CV and experience." },
    { key: "cmdCvReadyChipImproveProfile", prompt: "Review my CV profile for gaps and tell me the highest-impact improvements I can make." },
    { key: "cmdCvReadyChipStrengths", prompt: "Based on my CV, what are my strongest skills and most marketable experiences?" },
    { key: "cmdCvReadyChipWhatNext", prompt: "Based on my CV and experience, what's the best next step in my job search?" },
];
const COMMAND_LOGIN_HREF = buildAuthHref("/login", "/command");
const COMMAND_SIGNUP_HREF = buildAuthHref("/signup", "/command");

function buildWelcomeMessage(lang: "en" | "ar", name: string | null): string {
    const firstName = name ? name.trim().split(/\s+/)[0] : null;
    if (lang === "ar") {
        return firstName
            ? `أهلًا بعودتك ${firstName}. بماذا تريد أن أساعدك اليوم؟`
            : "أهلًا بعودتك. بماذا تريد أن أساعدك اليوم؟";
    }
    return firstName
        ? `Welcome back, ${firstName}. What would you like to work on today?`
        : "Welcome back. What would you like to work on today?";
}

const QUICK_ACTION_ICONS: Record<string, React.ReactNode> = {
    cmdQaFindJobs: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
    ),
    cmdQaUploadCv: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
        </svg>
    ),
    cmdQaWhatNext: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><path d="M12 8v4l3 3" />
        </svg>
    ),
    cmdQaCareerMove: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
        </svg>
    ),
    cmdQaApplications: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
    ),
    cmdQaInterview: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
    ),
};

const _BARE_SEARCH_ROLES = new Set([
    "engineer", "manager", "specialist", "consultant", "officer",
    "analyst", "director", "coordinator", "executive", "lead",
]);

function isStaleSearchQuery(query?: string): boolean {
    if (!query) return false;
    return _BARE_SEARCH_ROLES.has(query.trim().toLowerCase());
}

function parseHistoryContent(content: string, id: number): Partial<Message> {
    try {
        const parsed = JSON.parse(content) as Record<string, unknown>;
        if (parsed && typeof parsed === "object") {
            if (parsed.type === "job_matches") {
                const query = parsed.search_query as string | undefined;
                return {
                    id,
                    role: "rico",
                    type: "job_matches",
                    text: (parsed.message ?? parsed.reply ?? parsed.response ?? "") as string,
                    matches: (parsed.matches as JobMatch[] | undefined) ?? [],
                    search_query: query,
                    result_count: parsed.result_count as number | undefined,
                    broadened: parsed.broadened as boolean | undefined,
                    stale: isStaleSearchQuery(query),
                };
            }
            if (parsed.type === "options" || parsed.type === "help") {
                return {
                    id,
                    role: "rico",
                    type: parsed.type as string,
                    text: (parsed.message ?? "") as string,
                    options: (parsed.options as RicoOption[] | undefined) ?? [],
                };
            }
            if (parsed.type === "application_status") {
                return {
                    id,
                    role: "rico",
                    type: "application_status",
                    text: (parsed.message ?? "") as string,
                    applications: parsed.applications as ApplicationEntry[] | undefined,
                    follow_up_needed: parsed.follow_up_needed as ApplicationEntry[] | undefined,
                };
            }
            // Generic structured response: extract message text and any options
            const text = (parsed.message ?? parsed.reply ?? parsed.response ?? "") as string;
            if (text) {
                return {
                    id,
                    role: "rico",
                    text,
                    options: parsed.options as RicoOption[] | undefined,
                };
            }
        }
    } catch {
        // Fall through to plain text
    }
    return { id, role: "rico", text: content };
}


function WorkingIndicator({ message }: { message: string }) {
    return (
        <div className="rico-thinking-row" role="status" aria-live="polite" aria-label={message}>
            <span className="sr-only">{message}</span>
            <div className="rico-orb" aria-hidden="true"><span>R</span></div>
            <div className="rico-thinking-label">
                <span>{message}</span>
                <span className="rico-dots" aria-hidden="true"><i /><i /><i /></span>
            </div>
        </div>
    );
}

function SearchElapsedTimer({ t }: { t: (k: TranslationKey) => string }) {
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(id);
    }, []);
    const hint =
        elapsed >= 20 ? t("cmdSearchWakingUp")
        : elapsed >= 10 ? t("cmdSearchStillLooking")
        : null;
    return (
        <div className="pl-[42px] flex flex-col gap-1">
            <span className="text-[11px] tabular-nums text-text-muted" aria-live="off">{elapsed}s</span>
            {hint && (
                <p className="text-[11px] text-text-muted animate-pulse motion-reduce:animate-none" role="status">
                    {hint}
                </p>
            )}
        </div>
    );
}

function CvReadyOnboardingPanel({
    onAction,
    disabled,
}: {
    onAction: (prompt: string, label: string) => void;
    disabled: boolean;
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    return (
        <div className="pb-4 animate-in fade-in motion-reduce:animate-none">
            <div className="relative overflow-hidden rounded-2xl border border-border-subtle/70 bg-surface-elevated/60 p-5 backdrop-blur-sm sm:p-6">
                {/* Pulse-style ambient glow */}
                <div className="pointer-events-none absolute -right-10 -top-10 h-36 w-36 rounded-full bg-gold/[0.08] blur-2xl" aria-hidden="true" />

                {/* Header */}
                <div className="relative flex items-start gap-3">
                    <div
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gold/20 bg-gold/10 text-[15px] font-black text-gold"
                        aria-hidden="true"
                    >✓</div>
                    <div className="min-w-0">
                        <p className="text-[14px] font-semibold leading-snug text-rico-text">
                            {t("cmdCvReadyPanelTitle")}
                        </p>
                        <p className="mt-1 text-[12px] leading-relaxed text-text-muted">
                            {t("cmdCvReadyPanelSubtext")}
                        </p>
                    </div>
                </div>

                {/* Status insight cards — individual dark mini-rows */}
                <div className="relative mt-4 space-y-1.5">
                    <div className="flex items-center gap-2.5 rounded-lg border border-overlay/8 bg-surface-elevated/50 px-3 py-2 transition-all duration-300 hover:bg-surface-elevated/70">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-gold shadow-[0_0_6px_rgba(245,166,35,0.6)] animate-pulse" aria-hidden="true" />
                        <span className="flex-1 text-[12px] text-text-secondary">{t("cmdCvReadyCard1Label")}</span>
                        <span className="text-[10px] font-medium text-gold">{t("cmdCvReadyCard1Badge")}</span>
                    </div>
                    <div className="flex items-center gap-2.5 rounded-lg border border-overlay/8 bg-surface-elevated/50 px-3 py-2 transition-all duration-300 hover:bg-surface-elevated/70">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-gold shadow-[0_0_6px_rgba(245,166,35,0.6)] animate-pulse" aria-hidden="true" />
                        <span className="flex-1 text-[12px] text-text-secondary">{t("cmdCvReadyCard2Label")}</span>
                        <span className="text-[10px] font-medium text-gold">{t("cmdCvReadyCard2Badge")}</span>
                    </div>
                    <div className="flex items-center gap-2.5 rounded-lg border border-overlay/8 bg-surface-elevated/50 px-3 py-2 transition-all duration-300 hover:bg-surface-elevated/70">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-gold/60 shadow-[0_0_6px_rgba(245,166,35,0.4)] animate-pulse" aria-hidden="true" />
                        <span className="flex-1 text-[12px] text-text-secondary">{t("cmdCvReadyCard3Label")}</span>
                        <span className="text-[10px] font-medium text-gold/80">{t("cmdCvReadyCard3Badge")}</span>
                    </div>
                </div>

                {/* Action chips */}
                <div className="relative mt-3 grid grid-cols-1 gap-2 min-[480px]:grid-cols-2">
                    {CV_READY_CHIP_DEFS.map((qa) => {
                        const label = t(qa.key as TranslationKey);
                        return (
                            <button
                                type="button"
                                key={qa.key}
                                onClick={() => onAction(qa.prompt, label)}
                                disabled={disabled}
                                className="min-h-10 rounded-xl border border-gold/25 bg-gold/5 px-3 py-2.5 text-center text-[12px] font-medium text-gold transition-colors hover:border-gold/40 hover:bg-gold/10 disabled:opacity-50 rico-focus-strong"
                            >
                                {label}
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

type VerificationStatus = JobMatch["verification_status"];

function SourceQualityBadge({ status }: { status: VerificationStatus }) {
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
function JobFallbackActions({ match, onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
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

function JobMatchCard({ match, onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [linkOpened, setLinkOpened] = useState(false);
    const [markedApplied, setMarkedApplied] = useState(false);

    // Score: only display when a real score was calculated (non-null, non-zero).
    // Backend emits null when no scorer ran — never show a default 50%.
    const _rawScore = match.score ?? null;
    const score = _rawScore != null ? Math.min(1, Math.max(0, _rawScore > 1 ? _rawScore / 100 : _rawScore)) : null;
    const scorePct = score != null && score > 0 ? `${Math.round(score * 100)}%` : null;
    const scoreColor = score != null && score >= 0.8 ? "text-gold" : "text-text-muted";

    const topReason = match.match_reasons?.[0] ?? match.why ?? "";
    const vStatus = match.verification_status;

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

    // Determine which link button(s) to show — conditional on what the provider returned.
    // apply_url = direct apply page (highest trust)
    // source_url = job listing page (medium trust, shown as secondary button when differs from apply)
    // alt_link   = Google Jobs fallback (lowest trust, only when primary blocked)
    // Neither    = show "Link unavailable" text — never invent a URL
    const isBadPrimary =
        vStatus === "login_required" ||
        vStatus === "rate_limited" ||
        vStatus === "aggregator_untrusted" ||
        vStatus === "google_intermediary";

    // Primary link: apply_url when clean, fall back to alt_link when primary is bad
    let linkHref = "";
    let linkLabel = "";
    let linkTestId = "";
    if (applyUrl && !isBadPrimary) {
        linkHref = applyUrl;
        linkLabel = t("cmdApply");
        linkTestId = "job-link-apply";
    } else if (sourceUrl && !isBadPrimary) {
        linkHref = sourceUrl;
        linkLabel = t("cmdViewSource");
        linkTestId = "job-link-source";
    } else if (vStatus === "google_intermediary" && altUrl) {
        linkHref = altUrl;
        linkLabel = t("cmdApplySearch");
        linkTestId = "job-link-alt";
    } else if (isBadPrimary && (altUrl || sourceUrl)) {
        linkHref = altUrl || sourceUrl;
        linkLabel = t("cmdApplyAlt");
        linkTestId = "job-link-alt";
    }
    // Secondary source link — shown when source_url exists and differs from the primary link
    const showSource = !!sourceUrl && sourceUrl !== linkHref && !isBadPrimary && !!applyUrl;
    // linkHref="" → "Link unavailable" badge shown below, no <a> rendered

    return (
        <article
            className="space-y-2 rounded-xl border border-border-subtle/70 bg-surface-elevated/50 px-3 py-2.5"
            aria-label={`Job match: ${match.title} at ${match.company}`}
            data-testid="opportunity-card"
        >
            {/* Title + score */}
            <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                    <div
                        className="break-words text-[12px] font-semibold text-rico-text line-clamp-2"
                        data-testid="opportunity-card-title"
                    >
                        {match.title}
                    </div>
                    <div className="mt-0.5 break-words text-[10px] text-text-muted sm:line-clamp-1">
                        {match.company}
                        {match.location ? ` · ${match.location}` : ""}
                        {/* Salary only shown when provider supplied it — never inferred */}
                        {match.salary ? ` · ${match.salary}` : ""}
                    </div>
                </div>
                {/* Score pill — hidden when no real score was calculated */}
                {scorePct && (
                    <span
                        className={`text-[10px] font-semibold shrink-0 tabular-nums mt-0.5 ${scoreColor}`}
                        data-testid="job-score"
                    >
                        {scorePct}
                    </span>
                )}
            </div>

            {/* Match reason — dedicated readable block, only when backend supplies one */}
            {topReason && (
                <p className="text-[11px] leading-relaxed text-text-secondary rounded-lg border border-border-subtle/40 bg-surface-glass px-3 py-2">
                    {topReason}
                </p>
            )}

            {/* Action links — flex row; Apply + optional Source secondary */}
            <div className="flex flex-wrap items-center gap-1.5">
                {/* Apply / Source / Alt link — conditional on what provider returned */}
                {linkHref ? (
                    <a
                        href={linkHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={linkTestId}
                        aria-label={`${linkLabel}: ${match.title} at ${match.company}`}
                        onClick={() => setLinkOpened(true)}
                        className="rounded-md border border-gold/30 bg-gold/10 px-2.5 py-1.5 text-[10px] font-medium text-gold transition-colors hover:bg-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-1 focus-visible:ring-offset-surface"
                    >
                        {linkLabel}
                    </a>
                ) : (
                    <span
                        className="text-[9px] text-text-muted italic"
                        data-testid="job-link-unavailable"
                    >
                        {t("cmdLinkUnavailable")}
                    </span>
                )}
                {/* Secondary source link when apply and source both exist and differ */}
                {showSource && (
                    <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="job-link-source"
                        aria-label={`View source: ${match.title} at ${match.company}`}
                        className="rounded-md border border-border-soft bg-surface-glass px-2.5 py-1.5 text-[10px] text-text-secondary transition-colors hover:border-border-subtle hover:text-rico-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-1 focus-visible:ring-offset-surface"
                    >
                        {t("cmdViewSource")}
                    </a>
                )}
            </div>

            {/* Safe fallback CTAs — when no clean direct link exists, the card
                must never be a dead-end. Never presented as a verified Apply
                link, so source/safety gating is preserved (BUG-03 stays fixed). */}
            {!linkHref && (
                <JobFallbackActions match={match} onAction={onAction} />
            )}

            {/* Mark as Applied CTA — appears after the user opens the apply link */}
            {linkOpened && !markedApplied && (
                <button
                    type="button"
                    onClick={() => {
                        setMarkedApplied(true);
                        onAction(`I've applied to ${match.title} at ${match.company}`);
                    }}
                    className="w-full rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1.5 text-[10px] font-medium text-emerald-200 transition-colors hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50 animate-in fade-in slide-in-from-bottom-1"
                >
                    {t("cmdMarkApplied")}
                </button>
            )}
            {markedApplied && (
                <p className="text-[10px] text-emerald-300 font-medium px-0.5">
                    ✓ {t("cmdMarkAppliedConfirm")}
                </p>
            )}

            {/* Source quality row — only shown when there is something to say */}
            {vStatus && (
                <div className="flex flex-wrap items-center gap-1.5">
                    <SourceQualityBadge status={vStatus} />
                    {/* "No direct apply" note is now rendered by JobFallbackActions
                        (shown whenever there is no clean link), so it is omitted here
                        to avoid duplicating the same message on the card. */}
                    {vStatus === "google_intermediary" && altUrl && (
                        <span className="text-[9px] text-text-muted italic">
                            {t("cmdGoogleJobsNote")}
                        </span>
                    )}
                    {isBadPrimary && vStatus !== "google_intermediary" && (altUrl || sourceUrl) && (
                        <span className="text-[9px] text-text-muted italic">
                            {t("cmdAltLinkNote")}
                        </span>
                    )}
                </div>
            )}
        </article>
    );
}

function ApplicationStatusCard({ applications, followUpNeeded }: {
    applications: ApplicationEntry[];
    followUpNeeded: ApplicationEntry[];
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const stageDefs = [
        { key: "saved", label: t("cmdStatusSaved") },
        { key: "applied", label: t("cmdStatusApplied") },
        { key: "interview", label: t("cmdStatusInterview") },
        { key: "offer", label: t("cmdStatusOffer") },
        { key: "rejected", label: t("cmdStatusRejected") },
    ];
    const counts = stageDefs.reduce((acc, s) => ({
        ...acc,
        [s.key]: applications.filter((a) => a.status === s.key).length,
    }), {} as Record<string, number>);
    const activeStages = stageDefs.filter((s) => counts[s.key] > 0);

    return (
        <div className="mt-2 space-y-2 rounded-xl border border-border-subtle/70 bg-surface-elevated/50 px-3 py-2.5">
            {activeStages.length > 0 && (
                <div className="flex flex-wrap gap-3">
                    {activeStages.map((s) => (
                        <div key={s.key} className="flex items-baseline gap-1">
                            <span className="text-[14px] font-bold text-rico-text leading-none tabular-nums">{counts[s.key]}</span>
                            <span className="text-[10px] text-text-muted">{s.label}</span>
                        </div>
                    ))}
                </div>
            )}
            {followUpNeeded.length > 0 && (
                <div className={activeStages.length > 0 ? "border-t border-border-subtle/40 pt-1.5" : ""}>
                    <div className="space-y-0.5">
                        {followUpNeeded.map((app, i) => (
                            <div key={i} className="text-[10px] text-text-secondary flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-rico-amber shrink-0" aria-hidden="true" />
                                <span className="line-clamp-1">
                                    {app.title ?? "Role"}{app.company ? ` · ${app.company}` : ""}
                                    {app.days_since_applied != null ? ` · ${app.days_since_applied}d ago` : ""}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function ProfileGapCard({ gaps }: { gaps: string[] }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    return (
        <div className="mt-2 flex flex-col gap-2 rounded-xl border border-border-subtle/70 bg-surface-elevated/50 px-3 py-2.5 sm:flex-row sm:items-center">
            <div className="flex-1 min-w-0 text-[11px] text-text-secondary line-clamp-1">
                <span className="text-rico-amber font-medium">{t("cmdIncompletePrefix")}</span>
                {gaps.slice(0, 2).join(", ")}
                {gaps.length > 2 && ` +${gaps.length - 2}`}
            </div>
            <Link
                href="/profile"
                className="text-[10px] px-2 py-1 rounded-md bg-gold/10 border border-gold/30 text-gold hover:bg-gold/20 transition-colors shrink-0"
            >
                {t("cmdFillProfile")}
            </Link>
        </div>
    );
}

function OptionButtons({ options, onAction }: { options: RicoOption[]; onAction: (prompt: string) => void }) {
    return (
        <div className="flex flex-wrap gap-2 mt-2">
            {options.map((opt) => (
                <button
                    type="button"
                    key={opt.action}
                    onClick={() => onAction(opt.message ?? opt.label)}
                    className="text-[12px] px-3 py-2 rounded-xl border border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 transition-colors rico-focus-strong"
                >
                    {opt.label}
                </button>
            ))}
        </div>
    );
}

export default function CommandPage() {
    const router = useRouter();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "true";
    // SSR-safe: always false/null on server and first client render.
    // Populated by useEffect after hydration so server and client initial HTML match.
    const [cvReady, setCvReady] = useState(false);
    const [prompt, setPrompt] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [thinking, setThinking] = useState(false);
    const [slowHint, setSlowHint] = useState(false);
    const [sessionExpired, setSessionExpired] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [chatAudience, setChatAudience] = useState<ChatAudience>(useMock ? "authenticated" : "checking");
    const [operationState, setOperationState] = useState<{ state: string; message: string } | null>(null);
    const [editingProfileId, setEditingProfileId] = useState<number | null>(null);
    const [draftProfile, setDraftProfile] = useState<ProfilePreview | null>(null);
    const [clearingHistory, setClearingHistory] = useState(false);
    const [confirmClear, setConfirmClear] = useState(false);
    const [clearHistoryError, setClearHistoryError] = useState<string | null>(null);
    const [sidebarUser, setSidebarUser] = useState<{ email?: string } | null>(null);
    const [userName, setUserName] = useState<string | null>(null);
    // "pending" = history not yet checked; "has_history" = history loaded; "empty" = no history
    const [historyState, setHistoryState] = useState<"pending" | "has_history" | "empty">("pending");
    const [messagesRemaining, setMessagesRemaining] = useState<number | null>(null);
    const [initialContentReady, setInitialContentReady] = useState(false);

    // True when the latest Rico message has an unresolved permission request — blocks new input.
    const hasPendingPermission = messages.some(
        (m) => m.role === "rico" && !m.permission_dismissed && !!m.agentic_ui?.permission_request,
    );

    useEffect(() => {
        if (typeof window !== "undefined") {
            document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
            document.documentElement.lang = language;
        }
    }, [language]);

    // Read URL params client-side only so SSR and first client render both produce
    // cvReady=false / prompt=null, preventing a hydration mismatch.
    // Supports ?prompt= (legacy) and ?q= (CAREER-OS-10 sidebar deep-links).
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        setCvReady(params.get("cv") === "ready");
        setPrompt(params.get("prompt") ?? params.get("q") ?? null);
    }, []);

    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const promptSentRef = useRef(false);
    const sessionIdRef = useRef<string | null>(null);
    const welcomeMessageRef = useRef("");
    // Synchronous send guard — prevents double-send from rapid Enter taps.
    // React state (thinking) is async-batched and cannot guard against same-tick
    // re-entry; a useRef is set/cleared synchronously so the second tap sees it.
    const sendingRef = useRef(false);

    useEffect(() => {
        ensureSessionId(sessionIdRef);
        if (useMock) {
            return;
        }

        let cancelled = false;
        const controller = new AbortController();
        // Safety fallback: if fetchMe hangs (e.g. proxy/backend unreachable),
        // force guest mode after 8 s so the UI never stays in "checking" forever.
        // Must be long enough for Render cold-start + Vercel proxy round-trip (~3–5 s).
        const fallbackId = setTimeout(() => {
            if (!cancelled) {
                controller.abort();
                setChatAudience("public");
            }
        }, 8000);

        fetchMe(controller.signal)
            .then((me) => {
                if (cancelled) return;
                clearTimeout(fallbackId);
                setChatAudience(me.authenticated ? "authenticated" : "public");
                setSidebarUser(me.authenticated ? { email: me.email ?? undefined } : null);
                setUserName(me.authenticated && me.name ? me.name : null);
            })
            .catch(() => {
                if (cancelled) return;
                clearTimeout(fallbackId);
                setChatAudience("public");
            });

        return () => {
            cancelled = true;
            clearTimeout(fallbackId);
            controller.abort();
        };
    }, [useMock]);

    // Load chat history for authenticated users; result gates the welcome message
    useEffect(() => {
        if (chatAudience !== "authenticated") return;
        if (useMock) { setHistoryState("empty"); return; }

        let cancelled = false;

        (async () => {
            try {
                const history = await fetchChatHistory(20);
                if (cancelled) return;
                if (history.messages.length > 0) {
                    // Deduplicate by (role, content) pairs to avoid double-rendering
                    // if history is loaded more than once.
                    const seen = new Set<string>();
                    const mappedMessages: Message[] = [];
                    history.messages.forEach((msg: { role: string; content: string }, idx: number) => {
                        const key = `${msg.role}:${msg.content}`;
                        if (seen.has(key)) return;
                        seen.add(key);
                        if (msg.role === "user") {
                            mappedMessages.push({ id: idx, role: "user", text: msg.content });
                        } else {
                            // Parse JSON assistant payloads (job_matches, etc.) into rich messages
                            mappedMessages.push(parseHistoryContent(msg.content, idx) as Message);
                        }
                    });
                    setMessages(mappedMessages);
                    promptSentRef.current = true;
                    setHistoryState("has_history");
                    setInitialContentReady(true);
                    return;
                }
            } catch {
                // If history fetch fails, fall through to show welcome
            }
            if (!cancelled) setHistoryState("empty");
        })();

        return () => {
            cancelled = true;
        };
    }, [chatAudience, useMock]);

    const scrollBottom = useCallback(() => {
        const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
        const scrollMessagesPane = () => {
            const pane = messagesContainerRef.current;
            if (!pane) return;
            pane.scrollTo({ top: pane.scrollHeight, behavior });
        };
        if (typeof window !== "undefined") {
            window.requestAnimationFrame(() => {
                scrollMessagesPane();
            });
            return;
        }
        setTimeout(scrollMessagesPane, 50);
    }, []);

    const sendMessage = useCallback(async (text: string, displayText?: string) => {
        if (chatAudience === "checking") return;
        if (text === "__cv_upload__") {
            fileInputRef.current?.click();
            return;
        }
        const trimmed = text.trim();
        if (!trimmed || sendingRef.current) return;

        sendingRef.current = true;
        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: displayText?.trim() ?? trimmed }]);
        setThinking(true);
        const lc = trimmed.toLowerCase();
        if (lc.match(/\b(subscri|plan|pricing|package|upgrade)\b/)) {
            setOperationState({ state: "checking", message: t("cmdWorkingPlans") });
        } else if (lc.match(/\b(job|find|search|vacanc|opening|role|position|hiring)\b/)) {
            setOperationState({ state: "searching", message: t("cmdWorkingJobs") });
        } else if (lc.match(/\b(appli|track|application|status|applied|offer)\b/)) {
            setOperationState({ state: "reviewing", message: t("cmdWorkingApplications") });
        } else if (lc.match(/\b(cv|resume|profile|experience|skills)\b/)) {
            setOperationState({ state: "reading", message: t("cmdWorkingProfile") });
        } else if (lc.match(/\b(career|next move|recommend|suggest|direction|trajectory|what should)\b/)) {
            setOperationState({ state: "extracting", message: t("cmdWorkingRecommendations") });
        } else if (lc.match(/\b(interview|prep|prepare|question)\b/)) {
            setOperationState({ state: "extracting", message: t("cmdWorkingInterview") });
        }
        scrollBottom();

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45_000);
        const slowHintId = setTimeout(() => setSlowHint(true), 5_000);

        // Trajectory-analysis reroute: for authenticated users, answer with the
        // structured trajectory forecast instead of the generic chat fallback.
        // Any failure or empty result falls through to the normal chat path.
        if (chatAudience === "authenticated" && looksLikeTrajectoryAnalysis(trimmed)) {
            try {
                const forecast = await orchestrationApi.getTrajectory();
                if (forecast.nodes.length > 0) {
                    setMessages((prev) => [
                        ...prev,
                        { id: nextId(), role: "rico", text: formatTrajectory(forecast) },
                    ]);
                    clearTimeout(timeoutId);
                    clearTimeout(slowHintId);
                    setSlowHint(false);
                    sendingRef.current = false;
                    setThinking(false);
                    setOperationState(null);
                    scrollBottom();
                    textareaRef.current?.focus();
                    return;
                }
                // No trajectory nodes yet (e.g. profile pending) — fall through to chat.
            } catch {
                // Trajectory fetch failed — fall through to the normal chat path.
            }
        }

        // Tracks whether a real response (reply/matches/options) was already
        // rendered. Prevents a late stream/network failure from appending a
        // stale "Something went wrong" message below successful job cards (#325).
        let responseApplied = false;

        try {
            // Use SSE streaming for conversational messages; fall back to JSON for errors
            const streamId = nextId();
            let streamStarted = false;

            function applyDoneResponse(res: ChatApiResponse) {
                responseApplied = true;
                const reply =
                    res.response ?? res.reply ?? res.message ?? res.content ??
                    res.answer ?? res.text ??
                    res.data?.response ?? res.data?.reply ?? res.data?.message ??
                    res.data?.content ?? res.data?.text ?? "";
                const responseSource = res.response_source ?? "unknown";
                const isRateLimited = responseSource === "rate_limited";
                const isFallbackMode = res.type === "fallback_response";

                if (isRateLimited) {
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, { id: streamId, role: "rico", text: t("cmdErrRateLimit") }];
                    });
                } else if (isFallbackMode) {
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, { id: streamId, role: "rico", text: t("cmdFallbackResponse"), options: res.options as RicoOption[] | undefined }];
                    });
                } else if (!reply && !res.matches && !res.options) {
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, { id: streamId, role: "rico", text: t("cmdErrEmptyResponse") }];
                    });
                } else {
                    const hasEmptyMatches = res.type === "job_matches" && Array.isArray(res.matches) && res.matches.length === 0;
                    const displayText = hasEmptyMatches && !reply ? t("cmdErrNoMatches") : reply;
                    const displayOptions: RicoOption[] = hasEmptyMatches && !res.options ? [
                        { action: "broaden", label: t("cmdOptSuggestRoles"), message: "Suggest roles similar to my target based on my CV" },
                        { action: "upload_cv", label: t("cmdOptUploadCv"), message: "__cv_upload__" },
                    ] : (res.options as RicoOption[] | undefined) ?? [];
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, {
                            id: streamId,
                            role: "rico",
                            text: displayText,
                            type: res.type,
                            matches: res.matches as JobMatch[] | undefined,
                            options: displayOptions.length > 0 ? displayOptions : (res.options as RicoOption[] | undefined),
                            next_action: res.next_action,
                            roleName: res.role,
                            reasons: res.reasons,
                            next_actions: res.next_actions as NextAction[] | undefined,
                            search_query: (res as Record<string, unknown>).search_query as string | undefined,
                            result_count: (res as Record<string, unknown>).result_count as number | undefined,
                            broadened: (res as Record<string, unknown>).broadened as boolean | undefined,
                            rate_limit_notice: res.rate_limited ? (res.rate_limit_notice ?? t("cmdErrRateLimitSource")) : undefined,
                            applications: (res as Record<string, unknown>).applications as ApplicationEntry[] | undefined,
                            follow_up_needed: (res as Record<string, unknown>).follow_up_needed as ApplicationEntry[] | undefined,
                            profile_gaps: (res as Record<string, unknown>).profile_gaps as string[] | undefined,
                            agentic_ui: (res as Record<string, unknown>).agentic_ui as RicoAgenticUi | null | undefined,
                            streaming: false,
                        }];
                    });
                }
                if (typeof res.messages_remaining === "number") {
                    setMessagesRemaining(res.messages_remaining);
                }
                if (res.type === "save_job") {
                    bustSidebarCache();
                }
            }

            const streamGen = chatAudience === "authenticated"
                ? sendChatStream(trimmed, controller.signal, language)
                : sendChatStreamPublic(trimmed, getSessionId(sessionIdRef), controller.signal, language);

            for await (const event of streamGen) {
                if (event.type === "token" && event.text) {
                    if (!streamStarted) {
                        streamStarted = true;
                        setThinking(false);
                        setOperationState(null);
                        setMessages((prev) => [...prev, { id: streamId, role: "rico", text: event.text!, streaming: true }]);
                    } else {
                        setMessages((prev) => prev.map((m) =>
                            m.id === streamId ? { ...m, text: m.text + event.text! } : m
                        ));
                    }
                    scrollBottom();
                } else if (event.type === "done" && event.response) {
                    applyDoneResponse(event.response);
                } else if (event.type === "error") {
                    const res: ChatApiResponse =
                        chatAudience === "authenticated"
                            ? await sendChat(trimmed, controller.signal, undefined, language)
                            : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal, undefined, language);
                    applyDoneResponse(res);
                }
            }

            // Only fall back to the non-streaming endpoint when streaming truly
            // produced nothing. A "done" event without tokens (legacy path) already
            // called applyDoneResponse — responseApplied guards against a double call
            // that would waste a rate-limit slot and could overwrite the first response.
            if (!streamStarted && !responseApplied) {
                const res: ChatApiResponse =
                    chatAudience === "authenticated"
                        ? await sendChat(trimmed, controller.signal, undefined, language)
                        : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal, undefined, language);
                applyDoneResponse(res);
            }
        } catch (err) {
            // A real response already rendered (e.g. job matches) — a late
            // stream/network failure must not append a stale error below it (#325).
            if (responseApplied) {
                if (err instanceof Error && err.message.includes("401")) setSessionExpired(true);
                return;
            }
            if (err instanceof Error) {
                if (err.name === "AbortError") {
                    // For job-search queries, retry once with a longer timeout
                    // before giving up so cold-start Render delays don't drop results.
                    const isJobSearch = /\b(job|find|search|vacanc|opening|role|position|hiring)\b/i.test(trimmed)
                        || /ابحث|وظيف|بحث/.test(trimmed);
                    if (isJobSearch) {
                        const retryId = nextId();
                        setMessages((prev) => [...prev, { id: retryId, role: "rico", text: t("cmdRetryingSearch") }]);
                        try {
                            const retryController = new AbortController();
                            const retryTimeoutId = setTimeout(() => retryController.abort(), 90_000);
                            const retryRes: ChatApiResponse =
                                chatAudience === "authenticated"
                                    ? await sendChat(trimmed, retryController.signal, undefined, language)
                                    : await sendChatPublic(trimmed, getSessionId(sessionIdRef), retryController.signal, undefined, language);
                            clearTimeout(retryTimeoutId);
                            const retryReply =
                                retryRes.response ?? retryRes.reply ?? retryRes.message ?? retryRes.content ??
                                retryRes.answer ?? retryRes.text ??
                                retryRes.data?.response ?? retryRes.data?.reply ?? retryRes.data?.message ??
                                retryRes.data?.content ?? retryRes.data?.text ?? "";
                            setMessages((prev) => prev.map((m) =>
                                m.id === retryId
                                    ? {
                                        ...m,
                                        text: retryReply,
                                        type: retryRes.type,
                                        matches: retryRes.matches as JobMatch[] | undefined,
                                        options: retryRes.options as RicoOption[] | undefined,
                                        roleName: retryRes.role,
                                        next_action: retryRes.next_action,
                                        streaming: false,
                                    }
                                    : m
                            ));
                            return;
                        } catch {
                            // Retry also failed — replace hint with actionable fallback
                            setMessages((prev) => prev.map((m) =>
                                m.id === retryId
                                    ? {
                                        ...m,
                                        text: t("cmdSearchFailedFallback"),
                                        options: [
                                            { action: "suggest_roles", label: t("cmdOptSuggestRoles"), message: "Suggest roles similar to my target based on my CV" },
                                            { action: "find_jobs", label: t("cmdCvReadyChipFindJobs") ?? "Find jobs from my CV", message: "Find UAE jobs that match my CV" },
                                        ] as RicoOption[],
                                    }
                                    : m
                            ));
                            return;
                        }
                    }
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrTimeout") }]);
                    return;
                }
                if (err.message.includes("401")) { setSessionExpired(true); return; }
                if (err.name === "TypeError" || err.message === "Failed to fetch" || err.message.includes("network")) {
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrNetwork") }]);
                    return;
                }
            }
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrGeneric") }]);
        } finally {
            clearTimeout(timeoutId);
            clearTimeout(slowHintId);
            setSlowHint(false);
            sendingRef.current = false;
            setThinking(false);
            setOperationState(null);
            scrollBottom();
            textareaRef.current?.focus();
        }
    }, [chatAudience, language, scrollBottom, t]);

    useEffect(() => {
        if (chatAudience === "checking") return;
        // For authenticated users wait until we know whether history exists
        if (chatAudience === "authenticated" && historyState === "pending") return;
        if (promptSentRef.current) return;
        promptSentRef.current = true;

        const timeoutId = window.setTimeout(() => {
            if (prompt) {
                setInitialContentReady(true);
                void sendMessage(prompt);
                return;
            }
            if (cvReady) {
                // CvReadyOnboardingPanel renders instead of a static message.
                setInitialContentReady(true);
                return;
            }
            if (chatAudience === "authenticated") {
                // History exists — messages already set; no welcome needed.
                if (historyState === "has_history") {
                    setInitialContentReady(true);
                    return;
                }
                const msg = buildWelcomeMessage(language, userName);
                welcomeMessageRef.current = msg;
                setMessages([{ id: 1, role: "rico", text: msg }]);
                setInitialContentReady(true);
                return;
            }
            setMessages([{ id: 1, role: "rico", text: t("cmdWelcomePublic") }]);
            setInitialContentReady(true);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [chatAudience, historyState, cvReady, prompt, sendMessage, t, language, userName]);

    // Re-translate the welcome message when language changes while chat is still at welcome state
    useEffect(() => {
        setMessages((prev) => {
            if (prev.length !== 1 || prev[0].role !== "rico") return prev;

            // Personalized authenticated welcome — rebuild deterministically
            if (welcomeMessageRef.current && prev[0].text === welcomeMessageRef.current) {
                const msg = buildWelcomeMessage(language, userName);
                welcomeMessageRef.current = msg;
                return [{ ...prev[0], text: msg }];
            }

            // Translation-key-based welcome messages (cvReady panel intro, public)
            const welcomeKeys: TranslationKey[] = ["cmdWelcomeCvReady", "cmdWelcomePublic"];
            const isWelcome = welcomeKeys.some(
                (k) => prev[0].text === translations.en[k] || prev[0].text === translations.ar[k],
            );
            if (!isWelcome) return prev;
            const key = cvReady ? "cmdWelcomeCvReady" : "cmdWelcomePublic";
            return [{ ...prev[0], text: translations[language][key] }];
        });
    }, [language, cvReady, userName]);

    async function handleCVUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file || chatAudience === "checking") return;
        e.target.value = "";
        setUploadError("");
        const isImage = file.type.startsWith("image/");
        const isEmail = file.name.endsWith(".eml") || file.name.endsWith(".msg");
        const uploadLabel = isImage ? "image" : isEmail ? "email" : "document";
        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: `📎 Uploading ${uploadLabel}: ${file.name}` }]);
        setThinking(true);
        setOperationState({ state: "reading", message: isImage ? "Analysing image…" : t("cmdWorkingReadingCv") });
        scrollBottom();
        try {
            const result: UploadCVResponse =
                chatAudience === "authenticated"
                    ? await uploadCV(file)
                    : await uploadCV(file, `public:${getSessionId(sessionIdRef)}`);
            // Store returned user_id for guest→auth merge later (client-only)
            if (typeof window !== "undefined" && result.user_id && result.user_id.startsWith("public:")) {
                localStorage.setItem("rico_public_uid", result.user_id);
            }

            // Document Intelligence: non-CV classification with suggested actions
            if (result.status === "classified" && result.document_type) {
                const actions = (result.suggested_actions ?? []).map((a, i) => ({
                    id: `doc-action-${Date.now()}-${i}`,
                    label: a.label,
                    kind: "chat_continue" as const,
                    impact: "low" as const,
                    requires_confirmation: false,
                    payload: { message: a.message ?? a.label },
                }));
                setMessages((prev) => [
                    ...prev,
                    {
                        id: nextId(),
                        role: "rico" as const,
                        text: result.message ?? `I detected this as: **${result.display_label ?? result.document_type}**\n\nWhat would you like me to do with it?`,
                        actions,
                        agentic_ui: (result as unknown as Record<string, unknown>).agentic_ui as RicoAgenticUi | null | undefined,
                    },
                ]);
                return;
            }

            // Hard rejection (identity docs, etc.)
            if (result.ok === false) {
                const text = result.message ?? t("cmdCvWrongType");
                setMessages((prev) => [...prev, { id: nextId(), role: "rico" as const, text }]);
                return;
            }

            // CV preview ready for confirmation
            if (result.status === "preview_ready" && result.preview) {
                const preview = result.preview;
                const skills = preview.skills_detected ?? preview.skills ?? [];
                const previewText = (
                    `${t("cmdCvPreviewTitle")}\n\n` +
                    `${t("cmdCvPreviewName")} ${preview.name || "—"}\n` +
                    `${t("cmdCvPreviewEmail")} ${preview.email || "—"}\n` +
                    `${t("cmdCvPreviewPhone")} ${preview.phone || "—"}\n` +
                    `${t("cmdCvPreviewRole")} ${preview.current_role || "—"}\n` +
                    `${t("cmdCvPreviewExp")} ${preview.experience_years ? `~${preview.experience_years} ${t("cmdCvPreviewExpYears")}` : "—"}\n` +
                    `${t("cmdCvPreviewSkills")} ${skills.slice(0, 6).join(", ") || "—"}\n` +
                    `${t("cmdCvPreviewQuality")} ${result.extraction_quality || "—"}\n\n` +
                    t("cmdCvConfirmPrompt")
                );
                const message: Message = {
                    id: nextId(),
                    role: "rico",
                    text: previewText,
                    type: "profile_preview",
                    preview: preview,
                    filename: result.filename,
                    extractionQuality: result.extraction_quality,
                    docType: result.document_type,
                };
                setMessages((prev) => [...prev, message]);
                return;
            }

            // Fallback for old response format
            const p = result.parsed;
            if (p) {
                const skills = p.skills ?? [];
                const summary = [
                    skills.length ? `${t("cmdCvSkillsDetected")} ${skills.slice(0, 6).join(", ")}` : "",
                    p.emails?.length ? `${t("cmdCvPreviewEmail")} ${p.emails[0]}` : "",
                    p.phones?.length ? `${t("cmdCvPreviewPhone")} ${p.phones[0]}` : "",
                ].filter(Boolean).join(" · ");
                let text: string;
                if (p.extraction_quality === "poor") {
                    text = t("cmdCvPoor");
                } else if (p.extraction_quality === "partial") {
                    text = `${t("cmdCvPartial")}${summary ? `\n\n${summary}` : ""}\n\n${t("cmdCvFindMatches")}`;
                } else {
                    text = `${t("cmdCvGood")}${summary ? `\n\n${summary}` : ""}\n\n${t("cmdCvFindMatches")}`;
                }
                setMessages((prev) => [...prev, { id: nextId(), role: "rico", text }]);
            }
        } catch (err) {
            // A 413 means the file was too large — show the friendly size message,
            // never the generic "could not process your CV" (the size is the real reason).
            const tooLarge = err instanceof ApiError && err.statusCode === 413;
            const msgKey = tooLarge ? "cmdCvTooLarge" : "cmdCvUploadErr";
            setUploadError(t(msgKey));
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t(msgKey) }]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    async function handleConfirmProfile(preview: ProfilePreview, filename: string, messageId: number, docType?: string) {
        setThinking(true);
        setOperationState({ state: "confirming", message: t("cmdWorkingSavingProfile") });
        try {
            const userId = `public:${getSessionId(sessionIdRef)}`;
            await confirmCVProfile({ preview, filename, doc_type: docType ?? "cv" }, userId);
            // Detect the user's chat language from recent messages so that Arabic-speaking
            // users receive an Arabic confirmation even when the UI toggle is still on "EN".
            const recentUserText = messages
                .filter(m => m.role === "user")
                .slice(-4)
                .map(m => m.text || "")
                .join("");
            const arabicCount = (recentUserText.match(/[؀-ۿ]/g) || []).length;
            const effectiveLang: "en" | "ar" = arabicCount > 3 ? "ar" : language;
            const tEff = (key: TranslationKey) =>
                (translations[effectiveLang][key] ?? translations.en[key]) as string;
            const confirmText = chatAudience === "public"
                ? tEff("cmdCvProfileSavedPublic")
                : tEff("cmdCvProfileConfirmed");
            const confirmOptions: RicoOption[] = chatAudience === "authenticated" ? [
                { action: "find_jobs_cv", label: tEff("cmdFindJobsCv") ?? "Find jobs from my CV", message: "Find UAE jobs that match my CV and experience." },
                { action: "view_applications", label: tEff("cmdViewApplications") ?? "Track my applications", message: "show my applications" },
            ] : [];
            setMessages((prev) => prev.map(m => m.id === messageId ? { ...m, type: "profile_confirmed", text: confirmText, options: confirmOptions.length > 0 ? confirmOptions : m.options } : m));
        } catch (err) {
            const text = err instanceof Error ? `${t("cmdCvProfileError")}: ${err.message}` : t("cmdCvProfileError");
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: text }]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    async function handleSend() {
        const text = input.trim();
        if (!text) return;
        setInput("");
        if (textareaRef.current) textareaRef.current.style.height = "auto";
        await sendMessage(text);
    }

    async function handleLogout() {
        await logout();
        router.push("/login");
    }

    function handleNewChat() {
        const greeting =
            chatAudience === "authenticated"
                ? t("cmdNewChatAuth")
                : t("cmdNewChatPublic");
        setMessages([{ id: nextId(), role: "rico", text: greeting }]);
        setInput("");
    }

    function handleClearChat() {
        setMessages([]);
        setInput("");
    }

    async function handleClearHistory() {
        if (!confirmClear) {
            setConfirmClear(true);
            setClearHistoryError(null);
            return;
        }
        setClearingHistory(true);
        setConfirmClear(false);
        setClearHistoryError(null);
        try {
            await clearChatHistory();
            setMessages([]);
            promptSentRef.current = false;
        } catch (err) {
            // Server-side delete failed — keep local UI cleared but warn the user
            // so they know history may reappear on next load.
            setMessages([]);
            promptSentRef.current = false;
            const msg = err instanceof Error ? err.message : String(err);
            const isAuth = msg.includes("401") || msg.toLowerCase().includes("unauthorized");
            setClearHistoryError(
                isAuth
                    ? "Session expired — history cleared locally. Sign in again to clear server history."
                    : "Could not clear server history. It may reappear on next load."
            );
        } finally {
            setClearingHistory(false);
        }
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    /** Execute a permission-engine approved action and add the result to the thread.
     *
     * Called by PermissionRequestCard.onApprove. Throws on network/API errors so
     * the card can show an inline error and let the user retry or cancel.
     * On success, dismisses the card and appends Rico's response to the message list.
     */
    async function handlePermissionApprove(m: Message, action: RicoChatAction): Promise<void> {
        const permission = m.agentic_ui!.permission_request!;
        const rawAction = String((action.payload as Record<string, unknown>)?.action ?? "");
        if (!(EXECUTE_ALLOWED_ACTIONS as readonly string[]).includes(rawAction)) {
            throw new Error(`Action "${rawAction}" is not permitted via the permission engine.`);
        }
        const actionName = rawAction as ExecuteAllowedAction;
        const jobKey = String((action.payload as Record<string, unknown>)?.job_key ?? "");
        const job = (action.payload as Record<string, unknown>)?.job as Record<string, unknown> | null;

        const res = await executePermissionAction({
            permission_id: permission.id,
            action: actionName,
            job_key: jobKey,
            job,
        });

        const resultMsg = res.ok
            ? res.message || `${action.label} completed.`
            : res.error || res.message || "Could not complete this action. Please try again.";

        // Dismiss the card so it doesn't linger after the action resolves.
        setMessages((prev) =>
            prev.map((msg) => msg.id === m.id ? { ...msg, permission_dismissed: true } : msg),
        );
        // Append Rico's response as a new message in the thread.
        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: "rico" as const, text: resultMsg },
        ]);
    }

    /** Execute a submit-kind action from ChatActionsRow or ProposedChangeCard.
     *
     * Profile update actions POST/PATCH to the known profile endpoint via updateProfile().
     * All other endpoints use the generic submitAction() POST helper.
     * Dismisses the agentic_ui card on success and appends Rico's response.
     */
    async function handleActionSubmit(m: Message, action: RicoChatAction): Promise<void> {
        const endpoint = action.endpoint ?? "";
        const payload = action.payload as Record<string, unknown>;

        let resultText: string;
        if (endpoint === "/api/v1/rico/profile") {
            const res = await updateProfile(payload as ProfileUpdatePayload);
            const fields = res.updated_fields ?? [];
            resultText = fields.length
                ? `Profile updated: ${fields.join(", ")}.`
                : "Profile saved.";
        } else {
            const res = await submitAction(endpoint, payload);
            resultText = String(res.message ?? "Done.");
        }

        setMessages((prev) =>
            prev.map((msg) =>
                msg.id === m.id ? { ...msg, proposed_dismissed: true } : msg,
            ),
        );
        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: "rico" as const, text: resultText },
        ]);
    }

    /** Handle open_drawer action — injects the drawer content as a new Rico message. */
    function handleOpenDrawer(m: Message, action: RicoChatAction): void {
        const payload = action.payload as Record<string, unknown>;
        const content = String(payload.content ?? payload.message ?? action.label);
        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: "rico" as const, text: content },
        ]);
    }

    if (sessionExpired) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="flex max-w-lg flex-col items-center gap-4 rounded-2xl border border-border-subtle bg-surface/80 p-8 text-center backdrop-blur-md">
                    <p className="text-sm font-medium text-rico-text">{t("cmdSessionExpired")}</p>
                    <p className="text-sm text-text-muted">{t("cmdSessionExpiredMsg")}</p>
                    <Link href={COMMAND_LOGIN_HREF} className="rounded-lg bg-gold px-6 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-colors hover:bg-gold-hover cursor-pointer">
                        {t("signIn")}
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div
            className="relative flex h-[100dvh] min-h-[100dvh] overflow-hidden bg-background"
        >
            {/* Desktop sidebar — md+ only, hidden on mobile. Shown when authenticated or
                checking (so there's no layout jump when auth resolves). Hides for public. */}
            {chatAudience !== "public" && (
                <AppSidebar
                    className="hidden md:flex shrink-0"
                    user={sidebarUser ?? undefined}
                    onLogout={chatAudience === "authenticated" ? handleLogout : undefined}
                />
            )}

            {/* Main column — fills remaining width */}
            <div className="flex flex-1 min-w-0 flex-col overflow-hidden">
            {/* Top nav: always on mobile; on desktop only when no sidebar (public/checking→public) */}
            <div className={chatAudience === "authenticated" ? "md:hidden" : ""}>
                <MobileCommandHeader
                    chatAudience={chatAudience}
                    onLogout={handleLogout}
                    onNewChat={handleNewChat}
                    onClearChat={handleClearChat}
                    loginHref={COMMAND_LOGIN_HREF}
                    signupHref={COMMAND_SIGNUP_HREF}
                />
            </div>

            {/* Hidden file input for CV upload */}
            <input
                id="cv-file-upload"
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.webp,.gif,.bmp,.eml,.msg"
                aria-label="Upload document"
                title="Upload document"
                className="hidden"
                onChange={handleCVUpload}
            />

            <main id="command-main" className="relative z-10 mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col px-2 sm:px-4 lg:px-6">
                {/* The cold-start banner stays mounted and overlays the message pane,
                    so its delayed appearance cannot resize the pane or composer. */}
                <div
                    role="status"
                    aria-hidden={!(slowHint && thinking)}
                    data-testid="command-slow-banner"
                    className={`pointer-events-none absolute inset-x-0 top-0 z-20 mx-2 mt-2 flex min-h-9 items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-[11px] font-medium text-amber-300 shadow-lg shadow-background/40 transition-opacity duration-200 sm:mx-4 ${
                        slowHint && thinking ? "visible opacity-100" : "invisible opacity-0"
                    }`}
                >
                    <span aria-hidden="true">⚡</span>
                    {t("cmdWorkingSlowHint")}
                </div>

                {/* Messages Container */}
                <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-2 py-5 space-y-4 scroll-pb-32 sm:px-4 sm:py-7" role="log" aria-live="polite" aria-atomic="false" aria-label="Chat messages">

                    {/* Clear history control — shown at top when authenticated with loaded history */}
                    {chatAudience === "authenticated" && messages.length > 1 && (
                        <div className="flex justify-end pb-1">
                            {confirmClear ? (
                                <div className="flex items-center gap-2 text-[11px]">
                                    <span className="text-text-muted">{t("cmdDeleteHistory")}</span>
                                    <button
                                        type="button"
                                        onClick={handleClearHistory}
                                        disabled={clearingHistory}
                                        className="px-2.5 py-1 rounded-lg bg-rico-red/20 border border-rico-red/40 text-rico-red hover:bg-rico-red/30 transition-colors disabled:opacity-50"
                                    >
                                        {clearingHistory ? t("cmdClearing") : t("cmdClearConfirm")}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setConfirmClear(false)}
                                        className="px-2.5 py-1 rounded-lg border border-border-soft text-text-secondary hover:text-rico-text transition-colors"
                                    >
                                        {t("cancel")}
                                    </button>
                                </div>
                            ) : (
                                <button
                                    type="button"
                                    onClick={handleClearHistory}
                                    className="text-[11px] text-text-muted hover:text-text-secondary transition-colors"
                                    aria-label={t("cmdClearHistory")}
                                >
                                    {t("cmdClearHistory")}
                                </button>
                            )}
                        </div>
                    )}

                    {/* Clear-history error — shown if server DELETE failed */}
                    {clearHistoryError && (
                        <p className="px-4 py-1.5 text-[11px] text-amber-400/90 text-center">
                            {clearHistoryError}
                        </p>
                    )}

                    {/* CV-ready onboarding panel — Pulse-style glass card with action chips */}
                    {initialContentReady && cvReady && messages.length === 0 && chatAudience !== "checking" && !thinking && (
                        <CvReadyOnboardingPanel
                            onAction={(prompt, label) => sendMessage(prompt, label)}
                            disabled={thinking}
                        />
                    )}

                    {/* Welcome hero + quick start chips */}
                    {initialContentReady && messages.length === 0 && !thinking && !cvReady && (
                        <div className="flex flex-col items-center gap-5 pb-4 pt-6 sm:pt-10 animate-in fade-in motion-reduce:animate-none">
                            {/* Hero */}
                            <div className="flex flex-col items-center gap-3 text-center">
                                <div className="rico-orb !w-12 !h-12 !text-[18px]" aria-hidden="true"><span>R</span></div>
                                <div>
                                    <p className="text-[22px] font-bold tracking-tight text-text-primary sm:text-[26px]">
                                        {t("cmdHeroTitle")}
                                    </p>
                                    <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">
                                        {t("cmdHeroSubtitle")}
                                    </p>
                                </div>
                            </div>
                            {/* Chips */}
                            <div className="grid w-full max-w-xl grid-cols-1 gap-2 min-[480px]:grid-cols-2">
                                {QUICK_ACTION_DEFS.map((qa) => {
                                    const label = t(qa.key as TranslationKey);
                                    const icon = QUICK_ACTION_ICONS[qa.key];
                                    return (
                                        <button
                                            type="button"
                                            key={qa.key}
                                            onClick={() => sendMessage(qa.prompt, label)}
                                            disabled={thinking || chatAudience === "checking"}
                                            className="group flex min-h-[52px] cursor-pointer items-center gap-3 rounded-2xl border border-border-subtle bg-surface-glass px-4 py-3 text-start text-[12px] text-text-secondary transition-all hover:border-gold/30 hover:bg-surface-subtle hover:text-text-primary disabled:opacity-50 rico-focus-strong"
                                        >
                                            <span className="shrink-0 text-text-muted transition-colors group-hover:text-gold" aria-hidden="true">
                                                {icon}
                                            </span>
                                            <span>{label}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                    {/* Chips only (no hero) when there's already one message */}
                    {messages.length === 1 && !thinking && !cvReady && (
                        <div className="grid grid-cols-1 gap-2 pb-4 min-[480px]:grid-cols-2">
                            {QUICK_ACTION_DEFS.map((qa) => {
                                const label = t(qa.key as TranslationKey);
                                const icon = QUICK_ACTION_ICONS[qa.key];
                                return (
                                    <button
                                        type="button"
                                        key={qa.key}
                                        onClick={() => sendMessage(qa.prompt, label)}
                                        disabled={thinking || chatAudience === "checking"}
                                        className="group flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border border-border-subtle bg-surface-glass px-3 py-2.5 text-start text-[11px] text-text-secondary transition-all hover:border-gold/25 hover:bg-surface-subtle hover:text-text-primary disabled:opacity-50 rico-focus-strong"
                                    >
                                        <span className="shrink-0 text-text-muted transition-colors group-hover:text-gold" aria-hidden="true">
                                            {icon}
                                        </span>
                                        <span>{label}</span>
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((m, idx) => {
                        const prevMsg = messages[idx - 1];
                        const isFirstInGroup = !prevMsg || prevMsg.role !== m.role;
                        // Only profile_preview gets a light panel — all other Rico responses
                        // render as flowing text with no backing bubble.
                        const isStructured = m.type === "profile_preview";

                        return (
                            <div
                                key={m.id}
                                dir="ltr"
                                className={`flex min-h-6 animate-in fade-in motion-reduce:animate-none ${m.role === "user" ? "justify-end items-end" : "justify-start items-start gap-2.5"} ${isFirstInGroup ? "mt-4" : "mt-1"}`}
                            >
                                {m.role === "rico" && (
                                    <div
                                        className={`rico-orb !w-6 !h-6 !text-[10px] mt-0.5 shrink-0 ${isFirstInGroup ? "" : "invisible"}`}
                                        aria-hidden="true"
                                    ><span>R</span></div>
                                )}
                                <div dir="auto" className={`${m.role === "user"
                                    ? "max-w-[84%] break-words rounded-2xl rounded-tr-sm bg-gold px-3.5 py-2.5 text-start text-[14px] font-medium leading-relaxed text-[#0a0a1a] sm:max-w-[72%]"
                                    : isStructured
                                        ? "flex-1 min-w-0 rounded-xl border border-border-subtle/70 bg-surface-elevated/60 p-3 text-start text-[13px] leading-relaxed text-rico-text"
                                        : "flex-1 min-w-0 break-words text-start text-[14px] leading-relaxed text-rico-text"
                                    }`}>

                                    {/* Search result caption */}
                                    {m.type === "job_matches" && m.search_query && (
                                        <div className="mb-1.5 text-[10px] text-text-muted">
                                            {m.stale && (
                                                <span className="mr-1.5 px-1.5 py-0.5 rounded bg-border-subtle text-text-muted border border-border-soft">
                                                    {t("cmdOldResult")}
                                                </span>
                                            )}
                                            {m.result_count != null && m.result_count > 0
                                                ? `${m.result_count} ${m.result_count === 1 ? t("cmdMatch") : t("cmdMatches")}`
                                                : t("cmdNoMatches")} for <strong className="text-text-secondary">{m.search_query}</strong>
                                            {m.broadened && <span className="text-rico-amber"> · {t("cmdBroadened")}</span>}
                                        </div>
                                    )}

                                    {/* Message text */}
                                    {m.text && (
                                        m.role === "rico"
                                            ? <RicoMarkdownContent>{m.text!}</RicoMarkdownContent>
                                            : <div className="whitespace-pre-wrap">{m.text}</div>
                                    )}

                                    {/* Source rate-limited notice — keep the user inside Rico
                                    and point them at the alternate link on each card. */}
                                    {m.rate_limit_notice && (
                                        <div className="mt-2 flex items-start gap-2 rounded-lg border border-gold/30 bg-gold/8 px-3 py-2 text-[11px] text-gold">
                                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5" aria-hidden="true">
                                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                                <line x1="12" y1="9" x2="12" y2="13" />
                                                <line x1="12" y1="17" x2="12.01" y2="17" />
                                            </svg>
                                            <span>{m.rate_limit_notice}</span>
                                        </div>
                                    )}

                                    {/* Job match cards — stale results are collapsed by default */}
                                    {m.matches && m.matches.length > 0 && (
                                        m.stale ? (
                                            <details className="mt-2 group">
                                                <summary className="cursor-pointer text-[11px] text-text-muted hover:text-text-secondary transition-colors select-none list-none flex items-center gap-1">
                                                    <svg width="10" height="10" viewBox="0 0 10 10" className="transition-transform group-open:rotate-90" fill="currentColor"><path d="M3 2l4 3-4 3V2z" /></svg>
                                                    {t("cmdShowOld")} {m.matches.length} {m.matches.length === 1 ? t("cmdMatch") : t("cmdMatches")} {t("cmdStaleNote")}
                                                </summary>
                                                <div className="mt-2 space-y-2 opacity-70">
                                                    {m.matches.map((match, i) => (
                                                        <JobMatchCard key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                    ))}
                                                </div>
                                            </details>
                                        ) : (
                                            <div className="mt-2 space-y-2">
                                                {m.matches.map((match, i) => (
                                                    <JobMatchCard key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                ))}
                                            </div>
                                        )
                                    )}

                                    {/* Application status card */}
                                    {m.type === "application_status" && m.applications && m.applications.length > 0 && (
                                        <ApplicationStatusCard
                                            applications={m.applications}
                                            followUpNeeded={m.follow_up_needed ?? []}
                                        />
                                    )}

                                    {/* Profile gap card */}
                                    {m.type === "profile_gap" && m.profile_gaps && m.profile_gaps.length > 0 && (
                                        <ProfileGapCard gaps={m.profile_gaps} />
                                    )}

                                    {/* Profile preview confirmation buttons */}
                                    {m.type === "profile_preview" && m.preview && m.filename && editingProfileId !== m.id && (
                                        <div className="mt-3 flex gap-2">
                                            <button
                                                type="button"
                                                onClick={() => handleConfirmProfile(m.preview!, m.filename!, m.id, m.docType)}
                                                disabled={thinking}
                                                className="text-[12px] px-4 py-2 rounded-lg bg-gold text-[#0a0a1a] font-medium hover:bg-gold-hover transition-colors disabled:opacity-50"
                                            >
                                                {t("cmdProfileUseThis")}
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setEditingProfileId(m.id);
                                                    setDraftProfile(m.preview!);
                                                }}
                                                disabled={thinking}
                                                className="text-[12px] px-4 py-2 rounded-lg border border-border-soft text-text-secondary hover:border-gold/40 hover:text-rico-text transition-colors disabled:opacity-50"
                                            >
                                                {t("cmdProfileEditBefore")}
                                            </button>
                                        </div>
                                    )}
                                    {m.type === "profile_preview" && editingProfileId === m.id && draftProfile && (
                                        <div className="mt-3 space-y-2 border-t border-border-soft pt-3">
                                            <p className="text-[11px] font-semibold text-gold">{t("cmdProfileEditLabel")}</p>
                                            {(
                                                [
                                                    ["name", t("name")],
                                                    ["current_role", t("cmdProfileCurrentRole")],
                                                    ["email", t("email")],
                                                    ["phone", t("profilePhone")],
                                                ] as [keyof ProfilePreview, string][]
                                            ).map(([field, label]) => (
                                                <label key={field} className="block space-y-0.5">
                                                    <span className="text-[10px] text-text-muted">{label}</span>
                                                    <input
                                                        value={(draftProfile[field] as string) ?? ""}
                                                        onChange={(e) =>
                                                            setDraftProfile((prev) => (prev ? { ...prev, [field]: e.target.value } : prev))
                                                        }
                                                        className="w-full rounded-lg bg-surface-subtle border border-border-soft px-3 py-1.5 text-[12px] text-rico-text placeholder:text-text-muted focus:outline-none focus:border-gold/60"
                                                    />
                                                </label>
                                            ))}
                                            <label className="block space-y-0.5">
                                                <span className="text-[10px] text-text-muted">{t("cmdProfileSkills")}</span>
                                                <input
                                                    value={(draftProfile.skills_detected ?? draftProfile.skills ?? []).join(", ")}
                                                    onChange={(e) => {
                                                        const skills = e.target.value.split(",").map((skill) => skill.trim()).filter(Boolean);
                                                        setDraftProfile((prev) =>
                                                            prev ? { ...prev, skills_detected: skills, skills } : prev
                                                        );
                                                    }}
                                                    className="w-full rounded-lg bg-surface-subtle border border-border-soft px-3 py-1.5 text-[12px] text-rico-text placeholder:text-text-muted focus:outline-none focus:border-gold/60"
                                                />
                                            </label>
                                            <div className="flex gap-2 pt-1">
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        handleConfirmProfile(draftProfile, m.filename!, m.id, m.docType);
                                                        setEditingProfileId(null);
                                                        setDraftProfile(null);
                                                    }}
                                                    disabled={thinking}
                                                    className="text-[12px] px-4 py-2 rounded-lg bg-gold text-[#0a0a1a] font-medium hover:bg-gold-hover transition-colors disabled:opacity-50"
                                                >
                                                    {t("cmdProfileSave")}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setEditingProfileId(null);
                                                        setDraftProfile(null);
                                                    }}
                                                    className="text-[12px] px-4 py-2 rounded-lg border border-border-soft text-text-secondary hover:border-gold/40 hover:text-rico-text transition-colors"
                                                >
                                                    {t("cancel")}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                    {!m.streaming && m.options && m.options.length > 0 && (
                                        <OptionButtons options={m.options} onAction={(prompt) => sendMessage(prompt)} />
                                    )}
                                    {!m.streaming && m.agentic_ui?.actions && m.agentic_ui.actions.length > 0 && (
                                        <ChatActionsRow
                                            actions={m.agentic_ui.actions}
                                            onChatContinue={(prompt) => sendMessage(prompt)}
                                            onSubmit={(action) => handleActionSubmit(m, action)}
                                            onOpenDrawer={(action) => handleOpenDrawer(m, action)}
                                            disabled={thinking}
                                        />
                                    )}
                                    {!m.streaming && m.actions && m.actions.length > 0 && (
                                        <ChatActionsRow
                                            actions={m.actions}
                                            onChatContinue={(prompt) => sendMessage(prompt)}
                                            disabled={thinking}
                                        />
                                    )}
                                    {!m.streaming && !m.permission_dismissed && m.agentic_ui?.permission_request && (
                                        <PermissionRequestCard
                                            request={m.agentic_ui.permission_request}
                                            disabled={thinking}
                                            onApprove={(action: RicoChatAction) =>
                                                handlePermissionApprove(m, action)
                                            }
                                            onCancel={() =>
                                                setMessages((prev) =>
                                                    prev.map((msg) =>
                                                        msg.id === m.id
                                                            ? { ...msg, permission_dismissed: true }
                                                            : msg,
                                                    ),
                                                )
                                            }
                                        />
                                    )}
                                    {!m.streaming && !m.proposed_dismissed &&
                                        m.agentic_ui?.proposed_changes &&
                                        m.agentic_ui.proposed_changes.length > 0 && (
                                        <ProposedChangeCard
                                            changes={m.agentic_ui.proposed_changes as RicoProposedChange[]}
                                            submitAction={m.agentic_ui.actions?.find(
                                                (a) => a.kind === "submit",
                                            )}
                                            onSubmit={(action) => handleActionSubmit(m, action)}
                                            onCancel={() =>
                                                setMessages((prev) =>
                                                    prev.map((msg) =>
                                                        msg.id === m.id
                                                            ? { ...msg, proposed_dismissed: true }
                                                            : msg,
                                                    ),
                                                )
                                            }
                                            disabled={thinking}
                                        />
                                    )}
                                    {!m.streaming &&
                                        m.agentic_ui?.attachment_analysis &&
                                        m.agentic_ui.attachment_analysis.length > 0 && (
                                        <AttachmentAnalysisCard
                                            analyses={m.agentic_ui.attachment_analysis as RicoAttachmentAnalysis[]}
                                        />
                                    )}

                                    {/* Role confirmation reasons + next_actions */}
                                    {!m.streaming && m.type === "role_confirmation" && (
                                        <div className="mt-3 space-y-2">
                                            {m.reasons && m.reasons.length > 0 && (
                                                <ul className="list-disc list-inside text-[12px] text-text-secondary space-y-0.5">
                                                    {m.reasons.map((r, i) => (
                                                        <li key={i}>{r}</li>
                                                    ))}
                                                </ul>
                                            )}
                                            {m.next_actions && m.next_actions.length > 0 && (
                                                <div className="flex flex-wrap gap-2 pt-1">
                                                    {m.next_actions.map((na) => (
                                                        <button
                                                            type="button"
                                                            key={na.action}
                                                            onClick={() => sendMessage(na.message ?? na.label)}
                                                            className="text-[11px] px-3 py-1.5 rounded-xl border border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 transition-colors rico-focus-strong"
                                                        >
                                                            {na.label}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {thinking && (
                        <div className="flex min-h-12 flex-col gap-2">
                            <WorkingIndicator message={operationState?.message ?? t("cmdWorking")} />
                            {operationState?.state === "searching" && (
                                <SearchElapsedTimer t={t} />
                            )}
                        </div>
                    )}

                    <div aria-hidden="true" />
                </div>

                {/* Input bar — shrink-0 flex child keeps it below the scroll area;
                    safe-area padding covers iOS home indicator. */}
                <div className={`shrink-0 px-2 pt-3 sm:px-4 ${chatAudience === "authenticated" ? "pb-[calc(56px+1rem+env(safe-area-inset-bottom))] md:pb-[calc(1rem+env(safe-area-inset-bottom))]" : "pb-[calc(1rem+env(safe-area-inset-bottom))]"}`}>
                    {/* Dynamic notices use an always-present slot, preventing quota,
                        upload, or sign-up messages from moving the composer. */}
                    <div className="relative min-h-10" aria-live="polite">
                        <div className="absolute inset-x-0 bottom-2 space-y-2">
                            {chatAudience === "public" && messages.filter((m) => m.role === "rico").length >= 2 && (
                                <div className="flex items-center justify-between gap-3 px-1">
                                    <p className="text-[11px] text-text-muted">{t("cmdSignUpCta")}</p>
                                    <Link
                                        href={COMMAND_SIGNUP_HREF}
                                        className="text-[11px] px-3 py-1 rounded-lg bg-gold/10 border border-gold/25 text-gold hover:bg-gold/18 transition-colors shrink-0 font-medium cursor-pointer"
                                    >
                                        {t("cmdSignUpFree")}
                                    </Link>
                                </div>
                            )}
                            {uploadError && (
                                <p className="text-center text-[11px] text-rico-red" role="alert">{uploadError}</p>
                            )}
                            {messagesRemaining !== null && messagesRemaining <= 10 && chatAudience === "authenticated" && (
                                <div className="flex items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3 py-2" role="status">
                                    <p className="text-[11px] text-amber-400">
                                        {messagesRemaining === 0
                                            ? t("cmdMsgLimitReached")
                                            : messagesRemaining === 1
                                                ? t("cmdMsgLimitOne")
                                                : t("cmdMsgLimitFew").replace("{n}", String(messagesRemaining))}
                                    </p>
                                    <Link
                                        href="/subscription"
                                        className="shrink-0 text-[11px] font-medium text-amber-400 underline underline-offset-2 hover:text-amber-300 transition-colors"
                                    >
                                        {t("cmdUpgrade")}
                                    </Link>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-end gap-2 rounded-2xl border border-border-soft bg-surface-elevated/95 p-1.5 shadow-xl shadow-black/10 backdrop-blur-md transition-[border-color,box-shadow] focus-within:border-gold/30 focus-within:shadow-[0_0_0_3px_rgba(245,166,35,0.07),0_8px_32px_rgba(0,0,0,0.12)]">
                        {/* CV upload button — label triggers the hidden file input natively,
                            avoiding the programmatic .click() which some mobile browsers block. */}
                        <label
                            htmlFor={thinking || chatAudience === "checking" || hasPendingPermission ? undefined : "cv-file-upload"}
                            role="button"
                            tabIndex={thinking || chatAudience === "checking" || hasPendingPermission ? -1 : 0}
                            aria-disabled={thinking || chatAudience === "checking" || hasPendingPermission}
                            title={t("cmdUploadCvTitle")}
                            aria-label={t("cmdUploadCvAriaLabel")}
                            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-text-secondary transition-colors rico-focus-strong ${thinking || chatAudience === "checking" || hasPendingPermission ? "opacity-30 pointer-events-none cursor-default" : "cursor-pointer hover:bg-surface-subtle hover:text-rico-text"}`}
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                            </svg>
                        </label>

                        {/* Text input */}
                        <div className="relative flex-1">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(e) => {
                                    setInput(e.target.value);
                                    e.target.style.height = "auto";
                                    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                                }}
                                onKeyDown={handleKeyDown}
                                disabled={thinking || chatAudience === "checking" || hasPendingPermission}
                                rows={1}
                                aria-label="Message Rico"
                                aria-describedby="command-input-hint"
                                placeholder={hasPendingPermission
                                    ? "Approve or cancel the request above to continue"
                                    : chatAudience === "checking"
                                        ? t("cmdPlaceholderChecking")
                                        : t("cmdPlaceholderReady")}
                                className="max-h-[120px] w-full resize-none rounded-xl border-0 bg-transparent py-3 pe-12 ps-3 text-[16px] sm:text-sm text-rico-text placeholder:text-text-muted outline-none transition-all"
                            />
                            <button
                                type="button"
                                onClick={handleSend}
                                disabled={thinking || chatAudience === "checking" || hasPendingPermission || !input.trim()}
                                className="absolute bottom-1.5 end-1.5 top-1.5 flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl bg-gold text-[#0a0a1a] transition-colors hover:bg-gold-hover disabled:opacity-30 disabled:grayscale rico-focus-strong"
                                aria-label={thinking ? t("cmdSending") : t("send")}
                            >
                                {thinking ? (
                                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin motion-reduce:animate-none" />
                                ) : (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                    <p id="command-input-hint" className="mt-2 min-h-4 text-center text-[10px] text-text-secondary">
                        {t("cmdHint")}
                    </p>
                </div>
            </main>
            </div>{/* end main column */}

            {/* Mobile bottom dock — matches AppShell; authenticated only (public gets sign-in links in MobileCommandHeader) */}
            {chatAudience === "authenticated" && <MobileBottomNav />}
        </div>
    );
}
