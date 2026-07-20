"use client";

import { CommandComposer } from "@/components/command/CommandComposer";
import { CommandConversationRail, countUserTurns, deriveConversationTitle, type RailSessionEntry } from "@/components/command/CommandConversationRail";
import { classifyMessage } from "@/components/command/CommandEventAdapter";
import { AtelierMarkdownScope, CommandEmptyState } from "@/components/command/CommandMessages";
import { CommandObsidianShell } from "@/components/command/CommandObsidianShell";
import { CommandRail, deriveSessionPicks, type RailPipelineEntry } from "@/components/command/CommandRail";
import { RefineSearchPanel } from "@/components/command/RefineSearchPanel";
import { AtelierCardScope } from "@/components/command/CommandStates";
import { CommandTranscriptStep, TranscriptWorkingRow } from "@/components/command/CommandTranscriptStep";
import { SubscriptionCta } from "@/components/command/SubscriptionCta";
import { JobMatchCardAtelier } from "@/components/command/JobMatchCardAtelier";
import { MobileCommandHeader } from "@/components/command/MobileCommandHeader";
import { CVDraftCard } from "@/components/mission/CVDraftCard";
import { MissionContextBar } from "@/components/mission/MissionContextBar";
import { AttachmentAnalysisCard } from "@/components/ui/rico/AttachmentAnalysisCard";
import { ChatActionsRow } from "@/components/ui/rico/ChatActionCard";
import { PermissionRequestCard } from "@/components/ui/rico/PermissionRequestCard";
import { ProposedChangeCard } from "@/components/ui/rico/ProposedChangeCard";
import { RicoMarkdownContent } from "@/components/ui/rico/RicoMarkdownContent";
import { useLanguage } from "@/contexts/LanguageContext";
import { bustSidebarCache } from "@/hooks/useSidebarStatus";
import type { ChatApiResponse, JobMatch, NextAction, ProfilePreview, ProfileUpdatePayload, RicoOption, UploadCVResponse } from "@/lib/api";
import { ApiError, clearChatHistory, confirmCVProfile, cvQuotaCountSuffix, DEFAULT_CHAT_SESSION_ID, executePermissionAction, fetchChatHistory, fetchChatSessions, fetchMe, getCvQuotaError, logout, mintChatSessionId, mintOperationId, pollOperationUntilSettled, sendChat, sendChatPublic, sendChatStream, sendChatStreamPublic, submitAction, updateProfile, uploadCV } from "@/lib/api";
import { orchestrationApi } from "@/lib/api/orchestration";
import { APPLICATION_STATUSES } from "@/lib/applicationStatus";
import { stripDeepLinkParams } from "@/lib/deepLinkPrompt";
import { buildCopyText, getJobFallbackActions, resolveJobLink } from "@/lib/job-fallback";
import { mentionsSubscription } from "@/lib/subscriptionCta";
import { buildAuthHref } from "@/lib/redirect";
import type { ExecuteAllowedAction, RicoAgenticUi, RicoAttachmentAnalysis, RicoChatAction, RicoProposedChange } from "@/lib/schemas";
import { EXECUTE_ALLOWED_ACTIONS } from "@/lib/schemas";
import { formatTrajectory, looksLikeTrajectoryAnalysis } from "@/lib/trajectoryHelpers";
import { translations, useTranslation, type TranslationKey } from "@/lib/translations";
import type { ApplicationStatus } from "@/types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { isRetryableJobSearchIntent, pickOperationState } from "./operationState";
import { ensureSessionId, getSessionId } from "./sessionId";

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
    uploadId?: string | null;
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
    // Set on network/timeout/generic send failures so the bubble can offer a
    // Retry that resends the exact user text that failed (retryText).
    isError?: boolean;
    retryText?: string;
}

// ── Public/guest session history (localStorage only) ───────────────────────
// Authenticated users already have server-truth history via fetchChatHistory
// (src/api routers) — this mirror is scoped to public/guest sessions only,
// which currently have zero persistence across reloads. It intentionally
// stores plain role+text pairs only: agentic_ui (permission_request,
// proposed_changes) and job/action cards are never replayed from storage, so
// a reload can never resurrect a stale approve/apply affordance.
const PUBLIC_HISTORY_KEY = "rico_command_public_history_v1";
const PUBLIC_HISTORY_LIMIT = 40;

interface StoredPublicMessage {
    role: "user" | "rico";
    text: string;
}

function loadPublicHistory(sessionIdRef: React.MutableRefObject<string | null>): StoredPublicMessage[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = window.localStorage.getItem(PUBLIC_HISTORY_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw) as { sid?: string; messages?: unknown };
        if (!parsed || parsed.sid !== getSessionId(sessionIdRef) || !Array.isArray(parsed.messages)) return [];
        return parsed.messages.filter(
            (m): m is StoredPublicMessage =>
                !!m && typeof m === "object" &&
                ((m as StoredPublicMessage).role === "user" || (m as StoredPublicMessage).role === "rico") &&
                typeof (m as StoredPublicMessage).text === "string",
        );
    } catch {
        return [];
    }
}

function savePublicHistory(sessionIdRef: React.MutableRefObject<string | null>, messages: Message[]): void {
    if (typeof window === "undefined") return;
    try {
        const flat: StoredPublicMessage[] = messages
            .filter((m) => m.text && m.text.length > 0)
            .slice(-PUBLIC_HISTORY_LIMIT)
            .map((m) => ({ role: m.role, text: m.text }));
        window.localStorage.setItem(
            PUBLIC_HISTORY_KEY,
            JSON.stringify({ sid: getSessionId(sessionIdRef), messages: flat }),
        );
    } catch {
        /* localStorage unavailable (private mode / quota) — persistence is best-effort */
    }
}

type ChatAudience = "checking" | "authenticated" | "public";

// Module-level counter replaced by component-local ref (see _idRef below).
// Kept for import compatibility only; do not use outside CommandPage.
let _id = 0;
function nextId() { return ++_id; }
// Welcome turns get a reserved negative id so they can never collide with
// nextId()-generated ids (streamId in particular — see the fresh-page-load
// token-append bug this guards against).
const WELCOME_MESSAGE_ID = -1;

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

/** Map server history rows to transcript Messages — deduplicated by
 *  (role, content) and id'd in the reserved negative namespace (welcome is
 *  -1) so nextId()-generated ids (1, 2, …) can never collide with them.
 *  Shared by the initial history load and Sessions-rail thread switches. */
function mapHistoryToMessages(rows: Array<{ role: string; content: string }>): Message[] {
    const seen = new Set<string>();
    const mapped: Message[] = [];
    rows.forEach((msg, idx) => {
        const key = `${msg.role}:${msg.content}`;
        if (seen.has(key)) return;
        seen.add(key);
        if (msg.role === "user") {
            mapped.push({ id: -(idx + 2), role: "user", text: msg.content });
        } else {
            // Parse JSON assistant payloads (job_matches, etc.) into rich messages
            mapped.push(parseHistoryContent(msg.content, -(idx + 2)) as Message);
        }
    });
    return mapped;
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

    // Which link (if any) to surface — SHARED with JobMatchCardAtelier via
    // resolveJobLink so the apply/source/alt/unavailable decision and BUG-03
    // trust gating are single-sourced and cannot drift between the two cards.
    // apply_url = direct apply (highest trust); source_url = listing page
    // (secondary, shown when it differs); alt_link = Google Jobs fallback
    // (lowest, only when the primary is blocked); neither → "link unavailable".
    const { linkHref, linkLabelKey, linkTestId, sourceUrl, altUrl, isBadPrimary, showSource } =
        resolveJobLink(match);
    const linkLabel = linkLabelKey ? t(linkLabelKey) : "";

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

// Status -> translation key, covering every status in APPLICATION_STATUSES
// (lib/applicationStatus.ts) so the chat pipeline summary never silently
// drops a status the way it used to (BUG-6: this previously only knew about
// 5 of the 10 backend statuses).
const CMD_STATUS_LABEL_KEYS: Record<ApplicationStatus, TranslationKey> = {
    saved: "cmdStatusSaved",
    opened: "cmdStatusOpened",
    opened_external: "cmdStatusOpenedExternal",
    prepared: "cmdStatusPrepared",
    applied: "cmdStatusApplied",
    follow_up_due: "cmdStatusFollowUpDue",
    interview: "cmdStatusInterview",
    offer: "cmdStatusOffer",
    rejected: "cmdStatusRejected",
    decision_made: "cmdStatusDecision",
};

function ApplicationStatusCard({ applications, followUpNeeded }: {
    applications: ApplicationEntry[];
    followUpNeeded: ApplicationEntry[];
}) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const stageDefs = APPLICATION_STATUSES.map((status) => ({
        key: status as string,
        label: t(CMD_STATUS_LABEL_KEYS[status]),
    }));
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

function IconCopy() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="9" y="9" width="13" height="13" rx="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
    );
}

function IconCheck() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
        </svg>
    );
}

function IconRetry() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 2.64-6.36" />
            <polyline points="3 3 3 9 9 9" />
        </svg>
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
    // Obsidian shell rail visibility (slice C1) — desktop panel toggles only;
    // presentation state, never touches chat behavior.
    const [leftRailOpen, setLeftRailOpen] = useState(true);
    const [rightRailOpen, setRightRailOpen] = useState(true);
    // Real signal: the authenticated server-history fetch failed. Existing
    // behavior (fall through to the welcome state) is unchanged — this only
    // lets the conversation rail tell the user truthfully what happened.
    const [historyLoadError, setHistoryLoadError] = useState(false);
    const [clearHistoryError, setClearHistoryError] = useState<string | null>(null);
    const [userName, setUserName] = useState<string | null>(null);
    // "pending" = history not yet checked; "has_history" = history loaded; "empty" = no history
    const [historyState, setHistoryState] = useState<"pending" | "has_history" | "empty">("pending");
    // ── Multi-session chat threads (#1193) ─────────────────────────────────
    // multiSession turns on ONLY after GET /chat/sessions answers, so an older
    // backend (or any fetch failure) degrades to the original single-thread
    // rail with zero behavior change. sessions is the rail's thread list —
    // server-derived entries plus at most one local unsent draft.
    const [multiSession, setMultiSession] = useState(false);
    const [chatSessions, setChatSessions] = useState<RailSessionEntry[]>([]);
    const [activeChatSession, setActiveChatSession] = useState<string>(DEFAULT_CHAT_SESSION_ID);
    const [switchingSessionId, setSwitchingSessionId] = useState<string | null>(null);
    const [sessionSwitchError, setSessionSwitchError] = useState(false);
    const [messagesRemaining, setMessagesRemaining] = useState<number | null>(null);
    const [initialContentReady, setInitialContentReady] = useState(false);
    // id of the message whose "Copy" button most recently confirmed a copy
    const [copiedId, setCopiedId] = useState<number | null>(null);
    // Structured refine flow (P1): non-null opens the RefineSearchPanel with
    // the role prefilled from the message's search context.
    const [refineDraft, setRefineDraft] = useState<{ role: string } | null>(null);

    // True when the latest Rico message has an unresolved permission request — blocks new input.
    // 4e right rail — session-derived only (same contract as the atelier-console
    // reference): shortlist from this session's job matches, pipeline from the
    // latest application_status turn. No API calls; pure reads of chat state.
    const railPicks = React.useMemo(() => deriveSessionPicks(messages), [messages]);
    const railPipeline = React.useMemo<RailPipelineEntry[]>(() => {
        for (let i = messages.length - 1; i >= 0; i--) {
            const m = messages[i];
            if (m.role === "rico" && m.type === "application_status" && m.applications?.length) {
                return m.applications.slice(0, 5).map((app, idx) => ({
                    key: `${app.title ?? ""}|${app.company ?? ""}|${idx}`,
                    company: app.company ?? "",
                    title: app.title ?? "",
                    statusLabel: app.status && CMD_STATUS_LABEL_KEYS[app.status as ApplicationStatus]
                        ? t(CMD_STATUS_LABEL_KEYS[app.status as ApplicationStatus])
                        : (app.status ?? ""),
                }));
            }
        }
        return [];
    }, [messages, t]);

    const hasPendingPermission = messages.some(
        (m) => m.role === "rico" && !m.permission_dismissed && !!m.agentic_ui?.permission_request,
    );

    // Slice C3 — id of the last assistant (rico-role) turn. The Atelier
    // editorial reply offers Regenerate only on the latest answer, and only
    // when there is a real user prompt to resend (see the map below).
    const lastAssistantId = React.useMemo(() => {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].role === "rico") return messages[i].id;
        }
        return null;
    }, [messages]);

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
        setCvReady(new URLSearchParams(window.location.search).get("cv") === "ready");

        // BUG-18: ?q=/?prompt= are one-shot action params. Capture the prompt, then
        // strip it from the URL so a page refresh or back-navigation does not re-fire
        // the same prompt and re-inject it into an already-active chat thread. The
        // captured value still drives the single send below via `prompt` state;
        // every other param (e.g. cv=ready) is preserved.
        const { prompt: deepLinkPrompt, cleanSearch, changed } = stripDeepLinkParams(window.location.search);
        setPrompt(deepLinkPrompt);
        if (changed && typeof window.history?.replaceState === "function") {
            window.history.replaceState(null, "", window.location.pathname + cleanSearch + window.location.hash);
        }
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
    // Holds the AbortController for the current in-flight request (primary or retry).
    // Exposed so the cancel button can abort mid-stream without waiting for the
    // 45-second hard timeout.  Nulled in the sendMessage finally block.
    const abortRef = useRef<AbortController | null>(null);

    // Set by cancelRequest so the AbortError handler can distinguish a
    // DELIBERATE user Stop (canonical stopped row; partial streamed content
    // preserved) from the 45s hard timeout (error row + Retry). Slice C2.
    const stopRequestedRef = useRef(false);

    // Live mirrors for sendMessage (a stable useCallback): the active chat
    // thread and whether the backend supports threads. Refs, not deps, so the
    // send pipeline is never re-created on a session switch.
    const activeChatSessionRef = useRef<string>(DEFAULT_CHAT_SESSION_ID);
    const multiSessionRef = useRef(false);
    useEffect(() => {
        activeChatSessionRef.current = activeChatSession;
        multiSessionRef.current = multiSession;
    }, [activeChatSession, multiSession]);

    /** Cancel any in-flight request and reset UI to idle state. The stopped
     *  presentation itself is appended by the AbortError handler in
     *  sendMessage, which also finalizes any partial streamed message. */
    const cancelRequest = useCallback(() => {
        if (abortRef.current) {
            stopRequestedRef.current = true;
            abortRef.current.abort();
            abortRef.current = null;
        }
        sendingRef.current = false;
        setThinking(false);
        setSlowHint(false);
        setOperationState(null);
        textareaRef.current?.focus();
    }, []);

    // Keyboard shortcuts: Esc cancels an in-flight request (same action as the
    // composer's Cancel button); Ctrl/Cmd+K focuses the composer. Both are pure
    // additions — this page previously wired no global shortcuts, so neither
    // combo can collide with an existing handler.
    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            const mod = e.metaKey || e.ctrlKey;
            if (mod && e.key.toLowerCase() === "k") {
                e.preventDefault();
                textareaRef.current?.focus();
            } else if (e.key === "Escape" && thinking) {
                e.preventDefault();
                cancelRequest();
            }
        }
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [thinking, cancelRequest]);

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

    // Load chat threads + history for authenticated users; result gates the
    // welcome message. Sessions-rail flow (#1193): list the user's real
    // threads first, open the most recently active one, and scope the history
    // fetch to it. Any sessions-endpoint failure (older backend, network)
    // falls back to the original unscoped single-thread load unchanged.
    useEffect(() => {
        if (chatAudience !== "authenticated") return;
        if (useMock) { setHistoryState("empty"); return; }

        let cancelled = false;

        const withTimeout = <T,>(p: Promise<T>): Promise<T> =>
            Promise.race([
                p,
                new Promise<never>((_, reject) =>
                    window.setTimeout(() => reject(new Error("history timeout")), 8000)),
            ]);

        const applyHistory = (rows: Array<{ role: string; content: string }>): boolean => {
            if (rows.length === 0) return false;
            const mappedMessages = mapHistoryToMessages(rows);
            // If the user already started chatting while history was in
            // flight, prepend history instead of wiping their live turns.
            setMessages((prev) => (prev.length > 0 ? [...mappedMessages, ...prev] : mappedMessages));
            promptSentRef.current = true;
            setHistoryState("has_history");
            setInitialContentReady(true);
            return true;
        };

        (async () => {
            // ── Threads-first path ────────────────────────────────────────
            try {
                // Hard 8s cap: a hung fetch otherwise leaves historyState
                // "pending" forever (no welcome, no transcript).
                const listed = await withTimeout(fetchChatSessions());
                if (cancelled) return;
                setMultiSession(true);
                setChatSessions(
                    listed.sessions.map((s) => ({
                        id: s.id,
                        title: s.title ?? null,
                        userTurns: s.user_turns,
                    })),
                );
                if (listed.sessions.length === 0) {
                    // No server threads yet — the rail shows the truthful
                    // unsent draft this fresh conversation actually is.
                    setChatSessions([{ id: DEFAULT_CHAT_SESSION_ID, title: null, userTurns: 0, draft: true }]);
                    setHistoryState("empty");
                    return;
                }
                const mostRecent = listed.sessions[0].id;
                setActiveChatSession(mostRecent);
                const history = await withTimeout(fetchChatHistory(50, undefined, mostRecent));
                if (cancelled) return;
                if (applyHistory(history.messages)) return;
                setHistoryState("empty");
                return;
            } catch {
                if (cancelled) return;
                // Older backend or transient failure — legacy single-thread
                // load below; the rail keeps its original one-entry surface.
            }

            // ── Legacy unscoped fallback (pre-sessions behavior, unchanged) ──
            try {
                const history = await withTimeout(fetchChatHistory(20));
                if (cancelled) return;
                if (applyHistory(history.messages)) return;
            } catch {
                // If history fetch fails, fall through to show welcome. The
                // conversation rail surfaces this real failure (no behavior change).
                if (!cancelled) setHistoryLoadError(true);
            }
            if (!cancelled) setHistoryState("empty");
        })();

        return () => {
            cancelled = true;
        };
    }, [chatAudience, useMock]);

    // The rail's displayed thread list: chatSessions (server truth + explicit
    // handler updates) with a LIVE overlay for the active thread — title from
    // the real first user turn, real turn count, floated to the top on new
    // activity. Pure derivation (no state sync effect), so the list can never
    // drift from the transcript it describes.
    const railSessions = React.useMemo<RailSessionEntry[]>(() => {
        if (!multiSession) return chatSessions;
        const idx = chatSessions.findIndex((s) => s.id === activeChatSession);
        if (idx === -1) return chatSessions;
        const current = chatSessions[idx];
        const turns = countUserTurns(messages);
        const live: RailSessionEntry = {
            ...current,
            title: turns > 0 ? deriveConversationTitle(messages, "") || current.title : current.title,
            userTurns: Math.max(current.userTurns, turns),
            draft: current.draft && turns === 0,
        };
        if (turns > 0 && idx > 0) return [live, ...chatSessions.filter((s) => s.id !== activeChatSession)];
        return [...chatSessions.slice(0, idx), live, ...chatSessions.slice(idx + 1)];
    }, [multiSession, chatSessions, activeChatSession, messages]);

    // Load locally-persisted history for public/guest sessions (no server-side
    // history exists for guests). Mirrors the authenticated effect above: sets
    // historyState + promptSentRef so the welcome effect below defers to it.
    useEffect(() => {
        if (chatAudience !== "public") return;
        if (useMock) { setHistoryState("empty"); return; }

        ensureSessionId(sessionIdRef);
        const stored = loadPublicHistory(sessionIdRef);
        if (stored.length > 0) {
            // Same reserved negative namespace as the authenticated loader.
            setMessages(stored.map((m, idx) => ({ id: -(idx + 2), role: m.role, text: m.text })));
            promptSentRef.current = true;
            setHistoryState("has_history");
            setInitialContentReady(true);
            return;
        }
        setHistoryState("empty");
    }, [chatAudience, useMock]);

    // Persist public/guest conversation on every settled turn (never mid-stream,
    // to keep localStorage writes quiet and avoid partial-token snapshots).
    useEffect(() => {
        if (chatAudience !== "public") return;
        if (useMock) return;
        if (historyState === "pending") return;
        if (thinking) return;
        savePublicHistory(sessionIdRef, messages);
    }, [chatAudience, useMock, historyState, thinking, messages]);

    // Canonical auto-follow (slice C2): the transcript stays pinned to the
    // bottom while the user is within 96px of it; scrolling up releases the
    // pin so streaming output never yanks the reader back down.
    const pinnedToBottomRef = useRef(true);
    useEffect(() => {
        const pane = messagesContainerRef.current;
        if (!pane) return;
        const onScroll = () => {
            const distance = pane.scrollHeight - pane.scrollTop - pane.clientHeight;
            pinnedToBottomRef.current = distance < 96;
        };
        pane.addEventListener("scroll", onScroll, { passive: true });
        return () => pane.removeEventListener("scroll", onScroll);
    }, [chatAudience]);

    const scrollBottom = useCallback(() => {
        if (!pinnedToBottomRef.current) return;
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

        // One user turn = ONE operation id, shared by every transport attempt
        // (SSE, JSON fallback, timeout recovery). The backend refuses to start
        // a second search execution for an id that is still running.
        const operationId = mintOperationId();

        sendingRef.current = true;
        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: displayText?.trim() ?? trimmed }]);
        setThinking(true);
        const lc = trimmed.toLowerCase();
        const opGuess = pickOperationState(lc);
        if (opGuess) {
            setOperationState({ state: opGuess.state, message: t(opGuess.messageKey) });
        }
        scrollBottom();

        // Kill any previous in-flight request before starting a new one.
        // Prevents the duplicate-spinner bug (BUG #3) where a mid-flight request
        // races with a retry and both update the message list concurrently.
        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }

        const controller = new AbortController();
        abortRef.current = controller;  // expose for cancelRequest()
        stopRequestedRef.current = false; // fresh request — no deliberate stop yet
        // Hard 45-second timeout — aborts the stream and triggers the AbortError
        // catch block below, which shows a user-readable message (BUG #4).
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
        // Hoisted out of the try so the AbortError handler can finalize a
        // partial streamed message on a deliberate user Stop (slice C2).
        const streamId = nextId();
        let streamStarted = false;
        // Thread binding (#1193), hoisted for the retry path too: only sent
        // once the sessions API has answered (multiSession) so an older
        // backend never sees the field.
        const chatThread = multiSessionRef.current ? activeChatSessionRef.current : undefined;

        try {
            // Use SSE streaming for conversational messages; fall back to JSON for errors

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
                ? sendChatStream(trimmed, controller.signal, language, operationId, chatThread)
                : sendChatStreamPublic(trimmed, getSessionId(sessionIdRef), controller.signal, language, operationId);

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
                            ? await sendChat(trimmed, controller.signal, operationId, language, chatThread)
                            : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal, operationId, language);
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
                        ? await sendChat(trimmed, controller.signal, operationId, language, chatThread)
                        : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal, operationId, language);
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
                    // DELIBERATE user Stop (canonical, slice C2) — distinct from
                    // the 45s hard timeout below: preserve any partial streamed
                    // content and append the truthful stopped row with Retry.
                    // Never auto-retried, even for job-search intents.
                    if (stopRequestedRef.current) {
                        if (streamStarted) {
                            setMessages((prev) =>
                                prev.map((msg) =>
                                    msg.id === streamId ? { ...msg, streaming: false } : msg,
                                ),
                            );
                        }
                        setMessages((prev) => [
                            ...prev,
                            {
                                id: nextId(),
                                role: "rico" as const,
                                type: "stopped",
                                text: streamStarted ? t("cmdStoppedByUser") : t("cmdStoppedNoPartial"),
                                retryText: trimmed,
                            },
                        ]);
                        return;
                    }
                    // For job-search queries, retry once with a longer timeout
                    // before giving up so cold-start Render delays don't drop results.
                    // Standalone retry-only guard (not the chip classifier) so profile
                    // questions and applied/saved lists are never retried as a search,
                    // while real CV/career/comparison searches still are (TC-11 item 7).
                    const isJobSearch = isRetryableJobSearchIntent(trimmed);
                    if (isJobSearch) {
                        const retryId = nextId();
                        setMessages((prev) => [...prev, { id: retryId, role: "rico", text: t("cmdRetryingSearch") }]);
                        try {
                            // Explicitly cancel the timed-out primary controller before
                            // creating the retry.  Without this the primary SSE connection
                            // lingers alongside the retry, producing two concurrent spinners
                            // (BUG #3 — duplicate request dedup fix).
                            if (abortRef.current === controller) {
                                controller.abort();
                            }
                            const retryController = new AbortController();
                            abortRef.current = retryController;  // cancel button targets recovery too

                            // Duplicate-execution guard: the server is usually STILL
                            // WORKING on this exact search (provider cascades can pass
                            // 45s) — re-sending would start a second cascade and burn
                            // provider quota. Wait on the operation instead; only a
                            // definitively ended/unknown operation may be re-sent.
                            if (chatAudience === "authenticated") {
                                const verdict = await pollOperationUntilSettled(operationId, retryController.signal);
                                if (verdict === "aborted") {
                                    setMessages((prev) => prev.map((m) =>
                                        m.id === retryId
                                            ? { ...m, type: "stopped", text: t("cmdStoppedNoPartial"), retryText: trimmed }
                                            : m
                                    ));
                                    return;
                                }
                                if (verdict === "completed") {
                                    // The late result was appended to chat history by the
                                    // server — recover it instead of searching again. The
                                    // recovered row is bound to THIS turn's exact
                                    // operation_id (server responses embed it); we never
                                    // render "whatever assistant message is newest", which
                                    // could belong to a different turn or conversation.
                                    try {
                                        const history = await fetchChatHistory(
                                            10,
                                            undefined,
                                            multiSessionRef.current ? activeChatSessionRef.current : undefined,
                                        );
                                        const exact = [...history.messages].reverse().find((m) => {
                                            if (m.role === "user") return false;
                                            try {
                                                const parsed = JSON.parse(m.content) as Record<string, unknown>;
                                                return parsed?.operation_id === operationId;
                                            } catch {
                                                return false; // non-JSON rows carry no operation binding
                                            }
                                        });
                                        if (exact) {
                                            const parsed = parseHistoryContent(exact.content, retryId);
                                            setMessages((prev) => prev.map((m) =>
                                                m.id === retryId ? ({ ...m, ...parsed, id: retryId } as Message) : m
                                            ));
                                            return;
                                        }
                                    } catch {
                                        // History fetch failed — fall through below.
                                    }
                                    // Exact result row not visible (append raced/lost) —
                                    // fall through to the single re-send: the server-side
                                    // guard answers with the completed status instead of
                                    // re-executing, so this can never start a second search.
                                }
                                if (verdict === "still_running") {
                                    // Budget exhausted while the search is still live —
                                    // surface the manual retry affordance, never a blind
                                    // auto re-send against an active operation.
                                    setMessages((prev) => prev.map((m) =>
                                        m.id === retryId
                                            ? { ...m, text: t("cmdErrTimeout"), isError: true, retryText: trimmed }
                                            : m
                                    ));
                                    return;
                                }
                                // "terminal" (failed/timed_out/unknown) or "unavailable"
                                // (status API unreachable) → one legitimate re-send below,
                                // carrying the SAME operationId so the server guard has the
                                // final word even if our view of the state was stale.
                            }
                            const retryTimeoutId = setTimeout(() => retryController.abort(), 45_000);
                            const retryRes: ChatApiResponse =
                                chatAudience === "authenticated"
                                    ? await sendChat(trimmed, retryController.signal, operationId, language, chatThread)
                                    : await sendChatPublic(trimmed, getSessionId(sessionIdRef), retryController.signal, operationId, language);
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
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrTimeout"), isError: true, retryText: trimmed }]);
                    return;
                }
                if (err.message.includes("401")) { setSessionExpired(true); return; }
                if (err.name === "TypeError" || err.message === "Failed to fetch" || err.message.includes("network")) {
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrNetwork"), isError: true, retryText: trimmed }]);
                    return;
                }
            }
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdErrGeneric"), isError: true, retryText: trimmed }]);
        } finally {
            clearTimeout(timeoutId);
            clearTimeout(slowHintId);
            // Null out abortRef so cancelRequest() is a no-op after the request
            // completes naturally.  Prevents a stale abort firing on the next request.
            if (abortRef.current === controller) {
                abortRef.current = null;
            }
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
        // For authenticated users wait until we know whether history exists;
        // public/guest sessions wait on the localStorage history check above.
        if (chatAudience === "authenticated" && historyState === "pending") return;
        if (chatAudience === "public" && historyState === "pending") return;
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
                // Reserved sentinel id: nextId() yields positive ints only. A
                // hardcoded id of 1 collides with the first streamId on a fresh
                // page load (_id = 0 → streamId = 1, since queued setMessages
                // updaters run after streamId is taken), making every token
                // map-append into the welcome row as well as the stream row.
                // Late-bootstrap guard: if the user already started chatting
                // while the sessions/history fetch was in flight, an "empty"
                // result must NOT wipe their live turns — the same contract
                // the has_history path (applyHistory) already enforces by
                // prepending instead of replacing.
                setMessages((prev) =>
                    prev.length > 0 ? prev : [{ id: WELCOME_MESSAGE_ID, role: "rico", text: msg }],
                );
                setInitialContentReady(true);
                return;
            }
            // Same late-bootstrap guard for the public surface.
            setMessages((prev) =>
                prev.length > 0 ? prev : [{ id: WELCOME_MESSAGE_ID, role: "rico", text: t("cmdWelcomePublic") }],
            );
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
                const message: Message = {
                    id: nextId(),
                    role: "rico",
                    text: "",
                    type: "profile_preview",
                    preview: preview,
                    filename: result.filename,
                    extractionQuality: result.extraction_quality,
                    docType: result.document_type,
                    uploadId: result.upload_id,
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
            // Explicit order: 413 (file too large) → CV storage-quota 422
            // (detected via the exact backend sentinel, never a blanket 422
            // mapping) → generic upload error. The quota copy is the existing
            // localized key — never the raw English backend message.
            const tooLarge = err instanceof ApiError && err.statusCode === 413;
            const quota = tooLarge ? null : getCvQuotaError(err);
            const msg = tooLarge
                ? t("cmdCvTooLarge")
                : quota
                    ? `${t("uploadErrQuota")}${cvQuotaCountSuffix(quota)}`
                    : t("cmdCvUploadErr");
            setUploadError(msg);
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: msg }]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    async function handleConfirmProfile(preview: ProfilePreview, filename: string, messageId: number, docType?: string, uploadId?: string | null) {
        setThinking(true);
        setOperationState({ state: "confirming", message: t("cmdWorkingSavingProfile") });
        try {
            const userId = `public:${getSessionId(sessionIdRef)}`;
            await confirmCVProfile({ preview, filename, doc_type: docType ?? "cv", upload_id: uploadId }, userId);
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

    /** Persist the active thread's live overlay (title/turns from the real
     *  transcript) into chatSessions before switching away, so the rail keeps
     *  showing truthful entries for inactive threads. */
    function snapshotActiveSession() {
        if (!multiSession) return;
        const turns = countUserTurns(messages);
        setChatSessions((prev) => prev.map((s) =>
            s.id === activeChatSession
                ? {
                    ...s,
                    title: turns > 0 ? deriveConversationTitle(messages, "") || s.title : s.title,
                    userTurns: Math.max(s.userTurns, turns),
                    draft: s.draft && turns === 0,
                }
                : s,
        ));
    }

    function handleNewChat() {
        setConfirmClear(false);
        setSessionSwitchError(false);
        if (chatAudience === "authenticated" && multiSession) {
            snapshotActiveSession();
            // One truthful draft at a time: reuse an existing unsent draft
            // instead of stacking empty threads in the rail.
            const existingDraft = railSessions.find((s) => s.draft && s.userTurns === 0);
            const id = existingDraft?.id ?? mintChatSessionId();
            if (!existingDraft) {
                setChatSessions((prev) => [{ id, title: null, userTurns: 0, draft: true }, ...prev]);
            }
            setActiveChatSession(id);
            setHistoryState("empty");
        }
        const greeting =
            chatAudience === "authenticated"
                ? t("cmdNewChatAuth")
                : t("cmdNewChatPublic");
        setMessages([{ id: nextId(), role: "rico", text: greeting }]);
        setInput("");
    }

    /** Load one thread's transcript into the pane (no guards — callers guard).
     *  Returns true on success so callers can keep or revert selection. */
    async function loadSessionTranscript(id: string): Promise<boolean> {
        const target = railSessions.find((s) => s.id === id);
        // Unsent draft: no server rows — present the fresh-thread greeting.
        if (target?.draft) {
            setActiveChatSession(id);
            setHistoryState("empty");
            setMessages([{ id: nextId(), role: "rico", text: t("cmdNewChatAuth") }]);
            setInput("");
            return true;
        }
        setSwitchingSessionId(id);
        try {
            const history = await fetchChatHistory(50, undefined, id);
            const mapped = mapHistoryToMessages(history.messages);
            setActiveChatSession(id);
            setHistoryState(mapped.length > 0 ? "has_history" : "empty");
            setMessages(
                mapped.length > 0
                    ? mapped
                    : [{ id: nextId(), role: "rico", text: t("cmdNewChatAuth") }],
            );
            setInput("");
            return true;
        } catch {
            setSessionSwitchError(true);
            return false;
        } finally {
            setSwitchingSessionId(null);
        }
    }

    /** Sessions-rail click: switch to another thread. */
    function handleSelectSession(id: string) {
        if (id === activeChatSession || thinking || clearingHistory || switchingSessionId) return;
        setConfirmClear(false);
        setSessionSwitchError(false);
        snapshotActiveSession();
        void loadSessionTranscript(id);
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
            // Multi-session mode deletes the ACTIVE thread only; legacy mode
            // keeps the original clear-everything behavior.
            await clearChatHistory(multiSession ? activeChatSession : undefined);
        } catch (err) {
            // Server-side delete failed — keep local UI cleared but warn the user
            // so they know history may reappear on next load.
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

        if (multiSession) {
            // Drop the deleted thread from the rail, then open the next most
            // recent one — or a fresh truthful draft when none remain.
            const remaining = railSessions.filter((s) => s.id !== activeChatSession);
            if (remaining.length > 0) {
                setChatSessions(remaining);
                const opened = await loadSessionTranscript(remaining[0].id);
                if (opened) return;
            }
            const freshId =
                remaining.length > 0 || activeChatSession !== DEFAULT_CHAT_SESSION_ID
                    ? mintChatSessionId()
                    : DEFAULT_CHAT_SESSION_ID;
            setChatSessions((prev) => [
                { id: freshId, title: null, userTurns: 0, draft: true },
                ...prev.filter((s) => s.id !== activeChatSession && s.id !== freshId),
            ]);
            setActiveChatSession(freshId);
            setHistoryState("empty");
        }
        setMessages([]);
        promptSentRef.current = false;
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    async function handleCopyMessage(id: number, text: string) {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedId(id);
            window.setTimeout(() => setCopiedId((prev) => (prev === id ? null : prev)), 1600);
        } catch {
            // Clipboard unavailable (insecure context / permission denied) — no-op,
            // the text is already visible on screen for manual selection.
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

    /** Handle open_drawer action — structured UI flows that must never route
     * through the chat/LLM (P1: the refine label used to be sent as a message
     * and parsed as a job role). Unknown drawers keep the legacy behavior of
     * injecting payload content as a Rico message. */
    function handleOpenDrawer(m: Message, action: RicoChatAction): void {
        const payload = action.payload as Record<string, unknown>;
        if (payload.drawer === "refine_search") {
            const role = String(payload.search_query ?? m.search_query ?? "");
            setRefineDraft({ role: role === "these roles" ? "" : role });
            return;
        }
        const content = String(payload.content ?? payload.message ?? action.label);
        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: "rico" as const, text: content },
        ]);
    }

    // A streamed reply is actively rendering. Drives the REPLYING status and
    // keeps the composer's Stop control available through the whole stream —
    // without this, `thinking` flips false on the first token and a mid-stream
    // deliberate Stop would be impossible (slice C2).
    const streamingActive = messages.some((m) => m.streaming === true);

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
        <CommandChrome
            audience={chatAudience}
            busy={thinking}
            replying={streamingActive}
            leftOpen={leftRailOpen}
            rightOpen={rightRailOpen}
            onToggleLeft={() => setLeftRailOpen((v) => !v)}
            onToggleRight={() => setRightRailOpen((v) => !v)}
            onLogout={handleLogout}
            mobileActions={
                /* Command actions in the shared mobile drawer — replaces the
                   legacy MobileCommandHeader overflow menu for authenticated
                   mobile (single-shell chrome). Inherits the drawer palette. */
                <div className="flex flex-col gap-2" data-testid="command-mobile-actions">
                    <button
                        type="button"
                        onClick={handleNewChat}
                        className="rounded-[7px] px-3 py-2.5 text-start text-[14px]"
                        style={{ border: "1px solid rgba(127,127,127,0.35)", background: "transparent", color: "inherit", cursor: "pointer" }}
                    >
                        {t("newChat")}
                    </button>
                    <button
                        type="button"
                        onClick={() => void handleClearHistory()}
                        className="rounded-[7px] px-3 py-2.5 text-start text-[14px]"
                        style={{ border: "1px solid rgba(127,127,127,0.35)", background: "transparent", color: "inherit", cursor: "pointer" }}
                    >
                        {t("clearChat")}
                    </button>
                    <button
                        type="button"
                        onClick={handleLogout}
                        className="rounded-[7px] px-3 py-2.5 text-start text-[14px]"
                        style={{ border: "1px solid rgba(127,127,127,0.35)", background: "transparent", color: "inherit", cursor: "pointer" }}
                    >
                        {t("logout")}
                    </button>
                </div>
            }
            leftRail={
                <CommandConversationRail
                    audience={chatAudience}
                    messages={messages}
                    historyState={historyState}
                    historyLoadError={historyLoadError}
                    busy={thinking}
                    confirmClear={confirmClear}
                    clearingHistory={clearingHistory}
                    onNewChat={handleNewChat}
                    onClearHistory={() => void handleClearHistory()}
                    onCancelClear={() => setConfirmClear(false)}
                    multiSession={multiSession}
                    sessions={railSessions}
                    activeSessionId={activeChatSession}
                    switchingSessionId={switchingSessionId}
                    sessionSwitchError={sessionSwitchError}
                    onSelectSession={handleSelectSession}
                />
            }
        >
            {/* Main column — fills remaining width */}
            <div className="flex flex-1 min-w-0 flex-col overflow-hidden">
                {/* Top nav — public/checking audiences only (all widths). The
                authenticated audience gets single-shell chrome instead: the
                WorkspaceShell rail on lg+ and the shared WorkspaceShell mobile
                bar/drawer below lg (2026-07-18 single-shell defect — the legacy
                dark header/dock must never render over workspace surfaces). */}
                {chatAudience !== "authenticated" && (
                    <MobileCommandHeader
                        chatAudience={chatAudience}
                        onLogout={handleLogout}
                        onNewChat={handleNewChat}
                        onClearChat={handleClearChat}
                        loginHref={COMMAND_LOGIN_HREF}
                        signupHref={COMMAND_SIGNUP_HREF}
                    />
                )}

                {/* Mission Context Bar — authenticated only; shows goal, progress, next
                action. 4e: repainted via AtelierCardScope (supporting workspace panel). */}
                {chatAudience === "authenticated" && (
                    <AtelierCardScope authenticated>
                        <MissionContextBar onAction={(prompt) => void sendMessage(prompt)} />
                    </AtelierCardScope>
                )}

                <main id="command-main" className={`relative z-10 mx-auto flex min-h-0 w-full flex-1 flex-col px-2 sm:px-4 lg:px-6 ${chatAudience === "public" ? "max-w-5xl" : "max-w-[720px]"}`}>
                    {/* The cold-start banner stays mounted and overlays the message pane,
                    so its delayed appearance cannot resize the pane or composer. */}
                    <div
                        role="status"
                        aria-hidden={!(slowHint && thinking)}
                        data-testid="command-slow-banner"
                        className={`pointer-events-none absolute inset-x-0 top-0 z-20 mx-2 mt-2 flex min-h-9 items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-[11px] font-medium text-amber-300 shadow-lg shadow-background/40 transition-opacity duration-200 sm:mx-4 ${slowHint && thinking ? "visible opacity-100" : "invisible opacity-0"
                            }`}
                    >
                        <span aria-hidden="true">⚡</span>
                        {t("cmdWorkingSlowHint")}
                    </div>

                    {/* Messages Container */}
                    <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-2 pt-12 pb-5 space-y-4 scroll-pb-32 sm:px-4 sm:pt-14 sm:pb-7" role="log" aria-live="polite" aria-atomic="false" aria-label="Chat messages">

                        {/* Desktop conversation toolbar — New chat + (authenticated) Clear history.
                        Mobile already has both via MobileCommandHeader's overflow menu, so this
                        is desktop-only to avoid a redundant duplicate control on small screens.
                        Lives inside the scrollable pane (like the row it replaces) so it can
                        never shift the composer's position — see command-composer-stability e2e. */}
                        {chatAudience !== "checking" && messages.length > 0 && (
                            <div className="hidden md:flex items-center justify-end gap-3 pb-1">
                                <button
                                    type="button"
                                    onClick={handleNewChat}
                                    disabled={thinking}
                                    className="text-[11px] text-text-muted hover:text-text-secondary transition-colors disabled:opacity-50"
                                    aria-label={t("newChat")}
                                    title={t("newChat")}
                                >
                                    {t("newChat")}
                                </button>
                                {chatAudience === "authenticated" && messages.length > 1 && (
                                    confirmClear ? (
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
                                    )
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

                        {/* Welcome hero + quick start chips — PR 4b: Atelier for
                        authenticated, original public surface unchanged. */}
                        {initialContentReady && messages.length === 0 && !thinking && !cvReady && (
                            <CommandEmptyState
                                authenticated={chatAudience === "authenticated"}
                                variant="hero"
                                title={t("cmdHeroTitle")}
                                subtitle={t("cmdHeroSubtitle")}
                                disabled={thinking || chatAudience === "checking"}
                                actions={QUICK_ACTION_DEFS.map((qa) => {
                                    const label = t(qa.key as TranslationKey);
                                    return {
                                        key: qa.key,
                                        label,
                                        icon: QUICK_ACTION_ICONS[qa.key],
                                        onClick: () => sendMessage(qa.prompt, label),
                                    };
                                })}
                            />
                        )}
                        {/* Chips only (no hero) when there's already one message */}
                        {messages.length === 1 && !thinking && !cvReady && (
                            <CommandEmptyState
                                authenticated={chatAudience === "authenticated"}
                                variant="chips"
                                title={t("cmdHeroTitle")}
                                subtitle={t("cmdHeroSubtitle")}
                                disabled={thinking || chatAudience === "checking"}
                                actions={QUICK_ACTION_DEFS.map((qa) => {
                                    const label = t(qa.key as TranslationKey);
                                    return {
                                        key: qa.key,
                                        label,
                                        icon: QUICK_ACTION_ICONS[qa.key],
                                        onClick: () => sendMessage(qa.prompt, label),
                                    };
                                })}
                            />
                        )}

                        {/* Messages */}
                        {messages.map((m, idx) => {
                            const prevMsg = messages[idx - 1];
                            const isFirstInGroup = !prevMsg || prevMsg.role !== m.role;
                            // Only profile_preview gets a light panel — all other Rico responses
                            // render as flowing text with no backing bubble.
                            const isStructured = m.type === "profile_preview";
                            // Atelier card surfaces (4c: tool/permission/attachment/CV/
                            // error states; 4d: job-match/application/profile-gap cards)
                            // repaint via AtelierCardScope on the authenticated surface
                            // only; the right rail is slice 4e.
                            const atelierCards = chatAudience === "authenticated";

                            // ── Slice C3: Atelier editorial reply rendering ──
                            // On the authenticated surface, the USER turn and the
                            // plain-TEXT Rico turn are rendered by CommandTranscriptStep
                            // (RicoUserBubble / RicoReply). For those two cases the page
                            // suppresses its inline text (the bubble/serif prose owns it)
                            // and, for the Rico text turn, its own Copy/Retry row
                            // (RicoReply owns Copy + Regenerate). Cards, fail, and stopped
                            // rows keep their existing inline rendering.
                            const authKind = chatAudience === "authenticated" ? classifyMessage(m) : null;
                            const isEditorialUser = authKind === "you";
                            const isEditorialRicoText = authKind === "rico";
                            // Regenerate target: the exact text that produced this answer —
                            // an explicit retryText if present, else the nearest preceding
                            // user turn. Absent (e.g. the welcome turn) → no Regenerate.
                            const regenText = (() => {
                                if (m.role !== "rico") return null;
                                if (m.retryText) return m.retryText;
                                for (let j = idx - 1; j >= 0; j--) {
                                    if (messages[j].role === "user") return messages[j].text;
                                }
                                return null;
                            })();
                            const canRegenerate =
                                isEditorialRicoText && m.id === lastAssistantId && !m.streaming && !!regenText;

                            return (
                                <CommandTranscriptStep
                                    key={m.id}
                                    authenticated={chatAudience === "authenticated"}
                                    message={m}
                                    isFirstInGroup={isFirstInGroup}
                                    isStructured={isStructured}
                                    canRegenerate={canRegenerate}
                                    onRegenerate={regenText ? () => sendMessage(regenText) : undefined}
                                >

                                    {/* Search result caption — 4d: Atelier ink on the
                                        authenticated surface (part of the job-match cluster). */}
                                    {m.type === "job_matches" && m.search_query && (
                                        <AtelierCardScope authenticated={atelierCards}>
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
                                        </AtelierCardScope>
                                    )}

                                    {/* Message text — markdown ink scope (4b); nested cards
                                        get their own AtelierCardScope wraps (4c/4d).
                                        C3: suppressed for the authenticated user turn and
                                        plain-text Rico turn — RicoUserBubble / RicoReply own
                                        the text there (card/fail/stopped/public unchanged). */}
                                    {m.text && !isEditorialUser && !isEditorialRicoText && (
                                        m.role === "rico"
                                            ? (
                                                <AtelierMarkdownScope authenticated={chatAudience === "authenticated"}>
                                                    <RicoMarkdownContent>{m.text!}</RicoMarkdownContent>
                                                </AtelierMarkdownScope>
                                            )
                                            : <div className="whitespace-pre-wrap">{m.text}</div>
                                    )}

                                    {/* fix/command-subscription-cta: a reply that points at the
                                        subscription surface gets a real localized CTA to the
                                        internal /subscription route — the model's raw-text URL
                                        is never the navigation affordance, and /subscription
                                        stays the single source of truth for plan copy. */}
                                    {m.role === "rico" && !m.isError && !!m.text && mentionsSubscription(m.text) && (
                                        <SubscriptionCta />
                                    )}

                                    {/* Source rate-limited notice — keep the user inside Rico
                                    and point them at the alternate link on each card. */}
                                    {m.rate_limit_notice && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <div className="mt-2 flex items-start gap-2 rounded-lg border border-gold/30 bg-gold/8 px-3 py-2 text-[11px] text-gold">
                                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5" aria-hidden="true">
                                                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                                    <line x1="12" y1="9" x2="12" y2="13" />
                                                    <line x1="12" y1="17" x2="12.01" y2="17" />
                                                </svg>
                                                <span>{m.rate_limit_notice}</span>
                                            </div>
                                        </AtelierCardScope>
                                    )}

                                    {/* Job match cards — stale results are collapsed by default.
                                        4d: repainted via AtelierCardScope on the authenticated
                                        surface; the card components themselves are unchanged so
                                        the public/guest surface renders pre-4d verbatim. */}
                                    {m.matches && m.matches.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            {m.stale ? (
                                                <details className="mt-2 group">
                                                    <summary className="cursor-pointer text-[11px] text-text-muted hover:text-text-secondary transition-colors select-none list-none flex items-center gap-1">
                                                        <svg width="10" height="10" viewBox="0 0 10 10" className="transition-transform group-open:rotate-90" fill="currentColor"><path d="M3 2l4 3-4 3V2z" /></svg>
                                                        {t("cmdShowOld")} {m.matches.length} {m.matches.length === 1 ? t("cmdMatch") : t("cmdMatches")} {t("cmdStaleNote")}
                                                    </summary>
                                                    <div className="mt-2 space-y-2 opacity-70">
                                                        {m.matches.map((match, i) =>
                                                            atelierCards ? (
                                                                <JobMatchCardAtelier key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                            ) : (
                                                                <JobMatchCard key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                            ),
                                                        )}
                                                    </div>
                                                </details>
                                            ) : (
                                                <div className="mt-2 space-y-2">
                                                    {m.matches.map((match, i) =>
                                                        atelierCards ? (
                                                            <JobMatchCardAtelier key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                        ) : (
                                                            <JobMatchCard key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                                        ),
                                                    )}
                                                </div>
                                            )}
                                        </AtelierCardScope>
                                    )}

                                    {/* Application status card — 4d Atelier scope */}
                                    {m.type === "application_status" && m.applications && m.applications.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <ApplicationStatusCard
                                                applications={m.applications}
                                                followUpNeeded={m.follow_up_needed ?? []}
                                            />
                                        </AtelierCardScope>
                                    )}

                                    {/* Profile gap card — 4d Atelier scope */}
                                    {m.type === "profile_gap" && m.profile_gaps && m.profile_gaps.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <ProfileGapCard gaps={m.profile_gaps} />
                                        </AtelierCardScope>
                                    )}

                                    {/* CV draft card — structured preview, no raw contact values */}
                                    {m.type === "profile_preview" && m.preview && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <CVDraftCard
                                                preview={m.preview}
                                                filename={m.filename ?? ""}
                                                extractionQuality={m.extractionQuality}
                                            />
                                        </AtelierCardScope>
                                    )}

                                    {/* Profile preview confirmation buttons */}
                                    {m.type === "profile_preview" && m.preview && m.filename && editingProfileId !== m.id && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <div className="mt-3 flex gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handleConfirmProfile(m.preview!, m.filename!, m.id, m.docType, m.uploadId)}
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
                                        </AtelierCardScope>
                                    )}
                                    {m.type === "profile_preview" && editingProfileId === m.id && draftProfile && (
                                        <AtelierCardScope authenticated={atelierCards}>
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
                                                            handleConfirmProfile(draftProfile, m.filename!, m.id, m.docType, m.uploadId);
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
                                        </AtelierCardScope>
                                    )}
                                    {!m.streaming && m.options && m.options.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <OptionButtons options={m.options} onAction={(prompt) => sendMessage(prompt)} />
                                        </AtelierCardScope>
                                    )}
                                    {!m.streaming && m.agentic_ui?.actions && m.agentic_ui.actions.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <ChatActionsRow
                                                actions={m.agentic_ui.actions}
                                                onChatContinue={(prompt) => sendMessage(prompt)}
                                                onSubmit={(action) => handleActionSubmit(m, action)}
                                                onOpenDrawer={(action) => handleOpenDrawer(m, action)}
                                                disabled={thinking}
                                            />
                                        </AtelierCardScope>
                                    )}
                                    {!m.streaming && m.actions && m.actions.length > 0 && (
                                        <AtelierCardScope authenticated={atelierCards}>
                                            <ChatActionsRow
                                                actions={m.actions}
                                                onChatContinue={(prompt) => sendMessage(prompt)}
                                                disabled={thinking}
                                            />
                                        </AtelierCardScope>
                                    )}
                                    {!m.streaming && !m.permission_dismissed && m.agentic_ui?.permission_request && (
                                        <AtelierCardScope authenticated={atelierCards}>
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
                                        </AtelierCardScope>
                                    )}
                                    {!m.streaming && !m.proposed_dismissed &&
                                        m.agentic_ui?.proposed_changes &&
                                        m.agentic_ui.proposed_changes.length > 0 && (
                                            <AtelierCardScope authenticated={atelierCards}>
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
                                            </AtelierCardScope>
                                        )}
                                    {!m.streaming &&
                                        m.agentic_ui?.attachment_analysis &&
                                        m.agentic_ui.attachment_analysis.length > 0 && (
                                            <AtelierCardScope authenticated={atelierCards}>
                                                <AttachmentAnalysisCard
                                                    analyses={m.agentic_ui.attachment_analysis as RicoAttachmentAnalysis[]}
                                                />
                                            </AtelierCardScope>
                                        )}

                                    {/* Role confirmation reasons + next_actions */}
                                    {!m.streaming && m.type === "role_confirmation" && (
                                        <AtelierCardScope authenticated={atelierCards}>
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
                                        </AtelierCardScope>
                                    )}

                                    {/* Copy / Retry row — copy is offered on every settled Rico turn;
                                        retry only on turns marked isError (network/timeout/generic send
                                        failures), and resends the exact original user text.
                                        C3: suppressed for the plain-text Rico turn — RicoReply owns
                                        Copy + Regenerate there (card/fail/stopped rows keep this row). */}
                                        {!m.streaming && m.role === "rico" && !isEditorialRicoText && (m.text || ((m.isError || m.type === "stopped") && m.retryText)) && (
                                            <AtelierCardScope authenticated={atelierCards}>
                                            <div className="mt-2 flex items-center gap-3">
                                                {m.text && (
                                                    <button
                                                        type="button"
                                                        onClick={() => handleCopyMessage(m.id, m.text)}
                                                        className="inline-flex items-center gap-1 text-[10px] text-text-muted transition-colors hover:text-text-secondary rico-focus-strong"
                                                        aria-label={copiedId === m.id ? t("cmdCopied") : t("cmdCopy")}
                                                    >
                                                        {copiedId === m.id ? <IconCheck /> : <IconCopy />}
                                                        {copiedId === m.id ? t("cmdCopied") : t("cmdCopy")}
                                                    </button>
                                                )}
                                                {(m.isError || m.type === "stopped") && m.retryText && (
                                                    <button
                                                        type="button"
                                                        onClick={() => sendMessage(m.retryText!)}
                                                        disabled={thinking}
                                                        className="inline-flex items-center gap-1 text-[10px] text-gold transition-colors hover:text-gold-hover disabled:opacity-50 rico-focus-strong"
                                                        aria-label={t("retry")}
                                                    >
                                                        <IconRetry />
                                                        {t("retry")}
                                                    </button>
                                                )}
                                            </div>
                                            </AtelierCardScope>
                                        )}
                                </CommandTranscriptStep>
                            );
                        })}

                        {thinking && (
                            <div className="flex min-h-12 flex-col gap-2">
                                {chatAudience === "authenticated"
                                    ? <TranscriptWorkingRow operationMessage={operationState?.message} fallback={t("cmdWorking")} />
                                    : <WorkingIndicator message={operationState?.message ?? t("cmdWorking")} />}
                                {operationState?.state === "searching" && (
                                    <AtelierCardScope authenticated={chatAudience === "authenticated"}>
                                        <SearchElapsedTimer t={t} />
                                    </AtelierCardScope>
                                )}
                            </div>
                        )}

                        <div aria-hidden="true" />
                    </div>

                    {/* Structured refine flow — only the composed query ever
                    reaches the chat; UI wording never does. */}
                    {refineDraft !== null && (
                        <RefineSearchPanel
                            initialRole={refineDraft.role}
                            onSubmit={(query) => sendMessage(query)}
                            onClose={() => setRefineDraft(null)}
                            disabled={thinking}
                        />
                    )}

                    {/* Input bar — PR 4a of the Atelier migration program.
                    Authenticated: Atelier surface. Public/checking: original surface. */}
                    <CommandComposer
                        isAuthenticated={chatAudience === "authenticated"}
                        showSignUpCta={chatAudience === "public" && messages.filter((m) => m.role === "rico").length >= 2}
                        input={input}
                        onInputChange={setInput}
                        textareaRef={textareaRef}
                        fileInputRef={fileInputRef}
                        thinking={thinking || streamingActive}
                        chatAudience={chatAudience}
                        hasPendingPermission={hasPendingPermission}
                        messagesRemaining={messagesRemaining}
                        uploadError={uploadError}
                        onKeyDown={handleKeyDown}
                        onSend={handleSend}
                        onCancel={cancelRequest}
                        onCVUpload={handleCVUpload}
                        onNewChat={handleNewChat}
                        t={t}
                        signupHref={COMMAND_SIGNUP_HREF}
                        language={language}
                    />
                </main>
            </div>{/* end main column */}

            {/* 4e right rail — authenticated lg+ only; session-derived opportunity
            panel per the atelier-console ShortlistRail reference. */}
            <CommandRail
                authenticated={chatAudience === "authenticated"}
                picks={railPicks}
                pipeline={railPipeline}
                open={rightRailOpen}
            />

        </CommandChrome>
    );
}

/**
 * Command chrome — visual-consistency correction (owner directive 2026-07-17).
 *
 * Public/guest keeps the approved reference chrome untouched (top bar +
 * chat column; no sidebar — matches the design-reference screenshots).
 * Authenticated (and the transient "checking" state, so auth resolution
 * causes no layout jump) lives in CommandObsidianShell, which now composes
 * the shared WorkspaceShell: same sidebar, WORKSPACE_THEME palette, light
 * default and user dark toggle as every other workspace route, plus the
 * /command-only console bar (status, panel toggles, account menu) and the
 * collapsible 260px Sessions rail — all delivered through the same
 * workspace-theme context the 4a–4e surfaces already consume.
 * Chat behavior, streaming, attachments, safety, and EN/AR are untouched.
 */
function CommandChrome({
    audience,
    busy,
    replying,
    leftOpen,
    rightOpen,
    onToggleLeft,
    onToggleRight,
    onLogout,
    leftRail,
    mobileActions,
    children,
}: {
    audience: "checking" | "public" | "authenticated";
    busy: boolean;
    /** A streamed reply is actively rendering — drives the REPLYING status. */
    replying: boolean;
    leftOpen: boolean;
    rightOpen: boolean;
    onToggleLeft: () => void;
    onToggleRight: () => void;
    onLogout?: () => void;
    leftRail: React.ReactNode;
    /** Command actions for the shared mobile drawer (authenticated only). */
    mobileActions?: React.ReactNode;
    children: React.ReactNode;
}) {
    if (audience === "public") {
        return (
            <div className="relative flex h-[100dvh] min-h-[100dvh] overflow-hidden bg-background">
                {children}
            </div>
        );
    }
    return (
        <CommandObsidianShell
            busy={busy}
            replying={replying}
            leftOpen={leftOpen}
            rightOpen={rightOpen}
            onToggleLeft={onToggleLeft}
            onToggleRight={onToggleRight}
            onLogout={onLogout}
            leftRail={leftRail}
            mobileChrome={audience === "authenticated"}
            mobileActions={mobileActions}
        >
            <div className="relative flex h-full min-h-0 flex-1 overflow-hidden">
                {children}
            </div>
        </CommandObsidianShell>
    );
}
