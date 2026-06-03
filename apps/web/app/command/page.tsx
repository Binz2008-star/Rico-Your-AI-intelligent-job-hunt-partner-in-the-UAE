"use client";

import { MobileCommandHeader } from "@/components/command/MobileCommandHeader";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { useLanguage } from "@/contexts/LanguageContext";
import type { ChatApiResponse, JobMatch, NextAction, ProfilePreview, RicoOption, UploadCVResponse } from "@/lib/api";
import { clearChatHistory, confirmCVProfile, fetchChatHistory, fetchMe, logout, sendChat, sendChatPublic, sendChatStream, sendChatStreamPublic, uploadCV } from "@/lib/api";
import { orchestrationApi } from "@/lib/api/orchestration";
import { buildAuthHref } from "@/lib/redirect";
import { formatTrajectory, looksLikeTrajectoryAnalysis } from "@/lib/trajectoryHelpers";
import { translations, useTranslation, type TranslationKey } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

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
    search_query?: string;
    result_count?: number;
    broadened?: boolean;
    rate_limit_notice?: string;
    streaming?: boolean;
    stale?: boolean;
}

type ChatAudience = "checking" | "authenticated" | "public";

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
        if (parsed && typeof parsed === "object" && parsed.type === "job_matches") {
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
    } catch {
        // Fall through to plain text
    }
    return { id, role: "rico", text: content };
}

function renderInline(text: string): React.ReactNode {
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i} className="font-semibold text-rico-text">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("*") && part.endsWith("*")) {
            return <em key={i} className="italic">{part.slice(1, -1)}</em>;
        }
        return part;
    });
}

function renderMarkdown(text: string): React.ReactNode {
    const lines = text.split("\n");
    return lines.map((line, i) => {
        if (line.startsWith("### ")) {
            return <p key={i} className="font-semibold text-[13px] text-rico-text mt-2 mb-0.5">{renderInline(line.slice(4))}</p>;
        }
        if (line.startsWith("## ")) {
            return <p key={i} className="font-semibold text-[14px] text-rico-text mt-3 mb-1">{renderInline(line.slice(3))}</p>;
        }
        if (line.startsWith("# ")) {
            return <p key={i} className="font-bold text-[15px] text-rico-text mt-3 mb-1">{renderInline(line.slice(2))}</p>;
        }
        if (line.startsWith("- ") || line.startsWith("• ")) {
            return (
                <div key={i} className="flex gap-1.5 leading-relaxed">
                    <span className="text-gold shrink-0 mt-0.5">•</span>
                    <span>{renderInline(line.slice(2))}</span>
                </div>
            );
        }
        if (line.trim() === "") {
            return <div key={i} className="h-1.5" />;
        }
        return <p key={i} className="leading-relaxed">{renderInline(line)}</p>;
    });
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
        <div className="pb-4 animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none">
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

function JobMatchCard({ match, onAction: _onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    // Normalize to [0.0, 1.0]. New backend sends floats; legacy history may
    // have 0–100 integers. Values > 1 are divided by 100, then clamped.
    const _rawScore = match.score ?? 0;
    const score = Math.min(1, Math.max(0, _rawScore > 1 ? _rawScore / 100 : _rawScore));
    const scorePct = score > 0 ? `${Math.round(score * 100)}%` : null;
    // Single-role palette (#325): cyan = positive signal only. Strong matches are
    // highlighted; everything else stays neutral instead of cycling amber/magenta.
    const scoreColor = score >= 0.8 ? "text-gold" : "text-text-muted";
    const topReason = match.match_reasons?.[0] ?? match.why ?? "";
    const vStatus = match.verification_status;

    const clean = (u?: string) => (u && u !== "#" ? u.trim() : "");
    // apply_url is guaranteed to be a direct page (not a Google intermediary) — backend
    // moves Google links to alt_link and sets verification_status="google_intermediary".
    const primary = [clean(match.apply_url), clean(match.source_url), clean(match.alt_link)].filter(Boolean)[0] ?? "";

    // Downgrade known-bad primaries to the alt_link fallback
    const isBadLink =
        vStatus === "login_required" ||
        vStatus === "rate_limited" ||
        vStatus === "aggregator_untrusted" ||
        vStatus === "google_intermediary";
    const fallback = clean(match.alt_link) || clean(match.source_url) || "";
    const applyHref = isBadLink && fallback ? fallback : primary;
    const applyLabel =
        vStatus === "google_intermediary" ? t("cmdApplySearch") :
            isBadLink && fallback ? t("cmdApplyAlt") :
                t("cmdApply");

    return (
        <article
            className="space-y-2 rounded-xl border border-border-subtle/70 bg-surface-elevated/50 px-3 py-2.5"
            aria-label={`Job match: ${match.title} at ${match.company}`}
            data-testid="opportunity-card"
        >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2.5">
                <div className="flex-1 min-w-0">
                    <div
                        className="break-words text-[12px] font-semibold text-rico-text sm:line-clamp-1"
                        data-testid="opportunity-card-title"
                    >
                        {match.title}
                    </div>
                    <div className="mt-0.5 break-words text-[10px] text-text-muted sm:line-clamp-1">
                        {match.company}{match.location ? ` · ${match.location}` : ""}{topReason ? ` · ${topReason}` : ""}
                    </div>
                </div>
                {scorePct && (
                    <span className={`text-[10px] font-semibold shrink-0 tabular-nums ${scoreColor}`}>{scorePct}</span>
                )}
                {applyHref ? (
                    <a
                        href={applyHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="view-job-action"
                        aria-label={`${applyLabel}: ${match.title} at ${match.company}`}
                        className="w-full shrink-0 rounded-md border border-gold/30 bg-gold/10 px-2 py-1 text-center text-[10px] font-medium text-gold transition-colors hover:bg-gold/20 sm:w-auto"
                    >
                        {applyLabel}
                    </a>
                ) : null}
            </div>

            {/* Source quality row — only shown when there is something to say */}
            {vStatus && (
                <div className="flex flex-wrap items-center gap-1.5">
                    <SourceQualityBadge status={vStatus} />
                    {isBadLink && !fallback && (
                        <span className="text-[9px] text-text-muted italic">
                            {t("cmdNoDirectApply")}
                        </span>
                    )}
                    {vStatus === "google_intermediary" && fallback && (
                        <span className="text-[9px] text-text-muted italic">
                            {t("cmdGoogleJobsNote")}
                        </span>
                    )}
                    {isBadLink && vStatus !== "google_intermediary" && fallback && (
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
    const cvReady = typeof window === "undefined"
        ? false
        : new URLSearchParams(window.location.search).get("cv") === "ready";

    const prompt = typeof window === "undefined"
        ? null
        : new URLSearchParams(window.location.search).get("prompt");
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
    const [sidebarUser, setSidebarUser] = useState<{ email?: string } | null>(null);

    useEffect(() => {
        if (typeof window !== "undefined") {
            document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
            document.documentElement.lang = language;
        }
    }, [language]);
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const promptSentRef = useRef(false);
    const sessionIdRef = useRef<string | null>(null);

    useEffect(() => {
        ensureSessionId(sessionIdRef);
        if (useMock) {
            return;
        }

        let cancelled = false;
        const controller = new AbortController();
        // Safety fallback: if fetchMe hangs (e.g. proxy/backend unreachable),
        // force guest mode after 5 s so the UI never stays in "checking" forever.
        const fallbackId = setTimeout(() => {
            if (!cancelled) {
                controller.abort();
                setChatAudience("public");
            }
        }, 2000);

        fetchMe(controller.signal)
            .then((me) => {
                if (cancelled) return;
                clearTimeout(fallbackId);
                setChatAudience(me.authenticated ? "authenticated" : "public");
                setSidebarUser(me.authenticated ? { email: me.email ?? undefined } : null);
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

    // Load chat history for authenticated users
    useEffect(() => {
        if (chatAudience !== "authenticated" || useMock) return;

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
                    promptSentRef.current = true; // Skip welcome message
                }
            } catch {
                // If history fetch fails, continue with empty state (show welcome)
            }
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
        if (!trimmed || thinking) return;

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
                            streaming: false,
                        }];
                    });
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

            if (!streamStarted) {
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
            setThinking(false);
            setOperationState(null);
            scrollBottom();
            textareaRef.current?.focus();
        }
    }, [chatAudience, language, scrollBottom, thinking, t]);

    useEffect(() => {
        if (chatAudience === "checking" || promptSentRef.current) return;
        promptSentRef.current = true;
        const timeoutId = window.setTimeout(() => {
            if (prompt) {
                void sendMessage(prompt);
                return;
            }
            if (cvReady) {
                // CvReadyOnboardingPanel renders instead of a static message.
                return;
            }
            if (chatAudience === "authenticated") {
                setMessages([{ id: 1, role: "rico", text: t("cmdWelcomeBack") }]);
                return;
            }
            setMessages([{ id: 1, role: "rico", text: t("cmdWelcomePublic") }]);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [chatAudience, cvReady, prompt, sendMessage, t]);

    // Re-translate the welcome message when language changes while chat is still at welcome state
    useEffect(() => {
        void (async () => {
            setMessages((prev) => {
                if (prev.length !== 1 || prev[0].role !== "rico") return prev;
                const welcomeKeys: TranslationKey[] = ["cmdWelcomeCvReady", "cmdWelcomeBack", "cmdWelcomePublic"];
                const isWelcome = welcomeKeys.some(
                    (k) => prev[0].text === translations.en[k] || prev[0].text === translations.ar[k],
                );
                if (!isWelcome) return prev;
                const key = cvReady ? "cmdWelcomeCvReady" : chatAudience === "authenticated" ? "cmdWelcomeBack" : "cmdWelcomePublic";
                return [{ ...prev[0], text: translations[language][key] }];
            });
        })();
    }, [language, chatAudience, cvReady]);

    async function handleCVUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file || chatAudience === "checking") return;
        e.target.value = "";
        setUploadError("");
        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: `📎 ${t("cmdCvUploading")}: ${file.name}` }]);
        setThinking(true);
        setOperationState({ state: "reading", message: t("cmdWorkingReadingCv") });
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

            // Check if document was rejected due to wrong type
            if (result.ok === false && result.document_type) {
                const text = result.message || t("cmdCvWrongType");
                setMessages((prev) => [...prev, { id: nextId(), role: "rico", text }]);
                return;
            }

            // Check if preview is ready for confirmation
            if (result.status === "preview_ready" && result.preview) {
                const preview = result.preview;
                // Handle both new (skills_detected) and old (skills) response shapes
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
                };
                setMessages((prev) => [...prev, message]);
                return;
            }

            // Fallback for old response format (shouldn't happen with new backend)
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
        } catch {
            setUploadError(t("uploadError"));
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: t("cmdCvUploadErr") }]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    async function handleConfirmProfile(preview: ProfilePreview, filename: string, messageId: number) {
        setThinking(true);
        setOperationState({ state: "confirming", message: t("cmdWorkingSavingProfile") });
        try {
            const userId = `public:${getSessionId(sessionIdRef)}`;
            await confirmCVProfile({ preview, filename }, userId);
            const confirmText = chatAudience === "public"
                ? t("cmdCvProfileSavedPublic")
                : t("cmdCvProfileConfirmed");
            setMessages((prev) => prev.map(m => m.id === messageId ? { ...m, type: "profile_confirmed", text: confirmText } : m));
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
            return;
        }
        setClearingHistory(true);
        setConfirmClear(false);
        try {
            await clearChatHistory();
            setMessages([]);
            promptSentRef.current = false;
        } catch {
            // Best-effort — silently swallow; history still cleared locally
            setMessages([]);
            promptSentRef.current = false;
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
            dir={language === "ar" ? "rtl" : "ltr"}
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
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                aria-label="Upload CV PDF"
                title="Upload CV PDF"
                className="hidden"
                onChange={handleCVUpload}
            />

            <div className="relative z-10 mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col px-2 sm:px-4 lg:px-6">
                {/* Messages Container */}
                <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-2 py-5 space-y-4 scroll-pb-32 sm:px-4 sm:py-7" role="log" aria-live="polite" aria-atomic="false">

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

                    {/* CV-ready onboarding panel — Pulse-style glass card with action chips */}
                    {cvReady && messages.length === 0 && chatAudience !== "checking" && !thinking && (
                        <CvReadyOnboardingPanel
                            onAction={(prompt, label) => sendMessage(prompt, label)}
                            disabled={thinking}
                        />
                    )}

                    {/* Quick start (shown above first message on non-cv-ready entry) */}
                    {messages.length <= 1 && !thinking && !cvReady && (
                        <div className="grid grid-cols-1 gap-2 pb-4 min-[480px]:grid-cols-2 sm:flex sm:flex-wrap sm:justify-center">
                            {QUICK_ACTION_DEFS.map((qa) => {
                                const label = t(qa.key as TranslationKey);
                                return (
                                    <button
                                        type="button"
                                        key={qa.key}
                                        onClick={() => sendMessage(qa.prompt, label)}
                                        disabled={thinking || chatAudience === "checking"}
                                        className="min-h-10 cursor-pointer rounded-xl border border-border-subtle bg-surface-glass px-3 py-2 text-center text-[11px] text-text-secondary transition-colors hover:border-gold/25 hover:bg-surface-subtle hover:text-rico-text disabled:opacity-50 rico-focus-strong sm:text-xs"
                                    >
                                        {label}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((m, idx) => {
                        const prevMsg = messages[idx - 1];
                        const isFirstInGroup = !prevMsg || prevMsg.role !== m.role;
                        // Only profile_preview gets a light panel — job cards and app cards
                        // float as attachments directly in the chat stream.
                        const isStructured = m.type === "profile_preview";
                        // Longer Rico responses get a subtle glass backing for visual depth.
                        const isConversational = m.role === "rico" && !isStructured && m.text.length > 80;

                        return (
                            <div
                                key={m.id}
                                dir="ltr"
                                className={`flex animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none ${m.role === "user" ? "justify-end items-end" : "justify-start items-start gap-2.5"} ${isFirstInGroup ? "mt-4" : "mt-1"}`}
                            >
                                {m.role === "rico" && (
                                    <div
                                        className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black shrink-0 mt-0.5 ${isFirstInGroup ? "bg-gold/15 border border-gold/25 text-gold" : "invisible"}`}
                                        aria-hidden="true"
                                    >R</div>
                                )}
                                <div dir="auto" className={`${m.role === "user"
                                    ? "max-w-[84%] break-words rounded-2xl rounded-tr-sm bg-surface-elevated border border-overlay/12 px-3.5 py-2.5 text-start text-[14px] leading-relaxed text-text-primary shadow-sm sm:max-w-[72%]"
                                    : isStructured
                                        ? "flex-1 min-w-0 rounded-xl border border-border-subtle/70 bg-surface-elevated/60 p-3 text-start text-[13px] leading-relaxed text-rico-text"
                                        : isConversational
                                            ? "flex-1 min-w-0 break-words rounded-xl border border-overlay/6 bg-surface-elevated/30 px-3 py-2.5 text-start text-[14px] leading-relaxed text-rico-text"
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
                                            ? <div className="space-y-0.5 text-[13px]">{renderMarkdown(m.text)}</div>
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
                                                onClick={() => handleConfirmProfile(m.preview!, m.filename!, m.id)}
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
                                                        handleConfirmProfile(draftProfile, m.filename!, m.id);
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
                        <div className="flex flex-col gap-2">
                            <WorkingIndicator message={operationState?.message ?? t("cmdWorking")} />
                            {slowHint && (
                                <p className="text-[11px] text-text-muted pl-[42px] animate-pulse motion-reduce:animate-none" role="status">
                                    {t("cmdWorkingSlowHint")}
                                </p>
                            )}
                        </div>
                    )}

                    <div aria-hidden="true" />
                </div>

                {/* Input bar — shrink-0 flex child keeps it below the scroll area;
                    safe-area padding covers iOS home indicator. */}
                <div className="shrink-0 px-2 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:px-4">
                    {chatAudience === "public" && messages.filter((m) => m.role === "rico").length >= 2 && (
                        <div className="mb-2 flex items-center justify-between gap-3 px-1">
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
                        <p className="text-[11px] text-rico-red mb-2 text-center" role="alert">{uploadError}</p>
                    )}
                    <div className="flex items-end gap-2 rounded-2xl border border-border-soft bg-surface-elevated/95 p-1.5 shadow-xl shadow-black/10 backdrop-blur-md">
                        {/* CV upload button */}
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={thinking || chatAudience === "checking"}
                            title={t("cmdUploadCvTitle")}
                            className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-xl text-text-secondary transition-colors hover:bg-surface-subtle hover:text-rico-text disabled:opacity-30 rico-focus-strong"
                            aria-label={t("cmdUploadCvAriaLabel")}
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                            </svg>
                        </button>

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
                                disabled={thinking || chatAudience === "checking"}
                                rows={1}
                                aria-label="Message Rico"
                                aria-describedby="command-input-hint"
                                placeholder={chatAudience === "checking"
                                    ? t("cmdPlaceholderChecking")
                                    : t("cmdPlaceholderReady")}
                                className="max-h-[120px] w-full resize-none rounded-xl border-0 bg-transparent py-3 pe-12 ps-3 text-sm text-rico-text placeholder:text-text-muted outline-none transition-all"
                            />
                            <button
                                type="button"
                                onClick={handleSend}
                                disabled={thinking || chatAudience === "checking" || !input.trim()}
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
                    <p id="command-input-hint" className="text-center text-[10px] text-text-muted mt-2 opacity-40">
                        {t("cmdHint")}
                    </p>
                </div>
            </div>
            </div>{/* end main column */}
        </div>
    );
}
