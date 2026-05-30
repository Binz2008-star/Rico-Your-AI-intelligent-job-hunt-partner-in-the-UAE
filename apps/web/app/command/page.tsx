"use client";

import type { ChatApiResponse, JobMatch, NextAction, ProfilePreview, ProfileResponse, RicoOption, UploadCVResponse } from "@/lib/api";
import { confirmCVProfile, fetchMe, fetchProfile, logout, sendChat, sendChatPublic, sendChatStream, sendChatStreamPublic, uploadCV } from "@/lib/api";
import { orchestrationApi } from "@/lib/api/orchestration";
import { buildAuthHref } from "@/lib/redirect";
import { formatTrajectory, looksLikeTrajectoryAnalysis } from "@/lib/trajectoryHelpers";
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
}

type ChatAudience = "checking" | "authenticated" | "public";

let _id = 0;
function nextId() { return ++_id; }

const QUICK_ACTIONS = [
    { label: "Find UAE jobs that match my CV", prompt: "Find UAE jobs that match my CV and experience." },
    { label: "Upload my CV", prompt: "__cv_upload__" },
    { label: "What should I do next?", prompt: "Based on my profile and experience, what's the best next step in my job search?" },
    { label: "Analyze my next career move", prompt: "Analyze the best next career move based on my background." },
    { label: "Show my applications", prompt: "Show my job applications and their status." },
    { label: "Help me prep for an interview", prompt: "Help me prepare for an upcoming job interview." },
];

function buildWelcomeMessage(isAuthenticated: boolean, profile: ProfileResponse | null): string {
    if (!isAuthenticated || !profile?.profile_exists) {
        return "Hi, I'm Rico — your AI job-hunt partner in the UAE.\n\nUpload your CV and I'll find matching jobs, track your applications, and guide your next career move.";
    }
    const firstName = profile.name?.split(" ")[0] ?? null;
    const greeting = firstName ? `Welcome back, ${firstName}.` : "Welcome back.";
    const role = profile.target_roles?.[0] ?? profile.current_role ?? null;
    const hasData = (profile.completeness_score ?? 0) > 0.15;

    if (hasData && role) {
        return `${greeting}\n\nI'm actively watching for ${role} opportunities in UAE.\n\nAsk me to find new jobs, review your applications, prep for interviews, or plan your next career move.`;
    }
    if (hasData) {
        return `${greeting}\n\nYour profile is active. Tell me your target role and I'll search UAE opportunities immediately.`;
    }
    return `${greeting}\n\nUpload your CV and I'll build your profile and start matching you to UAE jobs.`;
}

const COMMAND_LOGIN_HREF = buildAuthHref("/login", "/command");
const COMMAND_SIGNUP_HREF = buildAuthHref("/signup", "/command");

function renderInline(text: string): React.ReactNode {
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
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
            return <p key={i} className="font-semibold text-[13px] text-white mt-2 mb-0.5">{renderInline(line.slice(4))}</p>;
        }
        if (line.startsWith("## ")) {
            return <p key={i} className="font-semibold text-[14px] text-white mt-3 mb-1">{renderInline(line.slice(3))}</p>;
        }
        if (line.startsWith("# ")) {
            return <p key={i} className="font-bold text-[15px] text-white mt-3 mb-1">{renderInline(line.slice(2))}</p>;
        }
        if (line.startsWith("- ") || line.startsWith("• ")) {
            return (
                <div key={i} className="flex gap-1.5 leading-relaxed">
                    <span className="text-magenta shrink-0 mt-0.5">•</span>
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

function JobMatchCard({ match, onAction: _onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const score = match.score ?? 0;
    const scorePct = score > 0 ? `${Math.round(score * 100)}%` : null;
    const scoreColor = score >= 0.8 ? "text-cyan" : score >= 0.6 ? "text-rico-amber" : "text-magenta";
    const topReason = match.match_reasons?.[0] ?? match.why ?? "";

    const clean = (u?: string) => (u && u !== "#" ? u.trim() : "");
    const primary = [clean(match.apply_url), clean(match.source_url), clean(match.alt_link)].filter(Boolean)[0] ?? "";

    return (
        <article
            className="flex items-center gap-2.5 rounded-lg border border-border-subtle/50 px-2.5 py-2"
            aria-label={`Job match: ${match.title} at ${match.company}`}
            data-testid="opportunity-card"
        >
            <div className="flex-1 min-w-0">
                <div
                    className="text-[12px] font-semibold text-white break-normal line-clamp-1"
                    data-testid="opportunity-card-title"
                >
                    {match.title}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5 line-clamp-1">
                    {match.company}{match.location ? ` · ${match.location}` : ""}{topReason ? ` · ${topReason}` : ""}
                </div>
            </div>
            {scorePct && (
                <span className={`text-[10px] font-semibold shrink-0 tabular-nums ${scoreColor}`}>{scorePct}</span>
            )}
            {primary ? (
                <a
                    href={primary}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid="view-job-action"
                    aria-label={`Apply for ${match.title} at ${match.company}`}
                    className="text-[10px] px-2 py-1 rounded-md bg-magenta/10 border border-magenta/30 text-magenta hover:bg-magenta/20 transition-colors shrink-0 font-medium"
                >
                    Apply
                </a>
            ) : (
                match.verification_status === "lead_needs_verification" && (
                    <span className="text-[9px] px-2 py-1 rounded-md border border-border-soft text-text-muted italic shrink-0">
                        Verifying
                    </span>
                )
            )}
        </article>
    );
}

function ApplicationStatusCard({ applications, followUpNeeded }: {
    applications: ApplicationEntry[];
    followUpNeeded: ApplicationEntry[];
}) {
    const stageDefs = [
        { key: "saved", label: "Saved" },
        { key: "applied", label: "Applied" },
        { key: "interview", label: "Interview" },
        { key: "offer", label: "Offer" },
        { key: "rejected", label: "Rejected" },
    ];
    const counts = stageDefs.reduce((acc, s) => ({
        ...acc,
        [s.key]: applications.filter((a) => a.status === s.key).length,
    }), {} as Record<string, number>);
    const activeStages = stageDefs.filter((s) => counts[s.key] > 0);

    return (
        <div className="mt-1.5 rounded-lg border border-border-subtle/50 px-2.5 py-2 space-y-1.5">
            {activeStages.length > 0 && (
                <div className="flex flex-wrap gap-3">
                    {activeStages.map((s) => (
                        <div key={s.key} className="flex items-baseline gap-1">
                            <span className="text-[14px] font-bold text-white leading-none tabular-nums">{counts[s.key]}</span>
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
    return (
        <div className="mt-1.5 rounded-lg border border-border-subtle/50 px-2.5 py-1.5 flex items-center gap-2">
            <div className="flex-1 min-w-0 text-[11px] text-text-secondary line-clamp-1">
                <span className="text-rico-amber font-medium">Incomplete — </span>
                {gaps.slice(0, 2).join(", ")}
                {gaps.length > 2 && ` +${gaps.length - 2}`}
            </div>
            <Link
                href="/profile"
                className="text-[10px] px-2 py-1 rounded-md bg-magenta/10 border border-magenta/30 text-magenta hover:bg-magenta/20 transition-colors shrink-0"
            >
                Fill profile
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
                    className="text-[12px] px-3 py-2 rounded-xl border border-magenta/30 text-magenta hover:bg-magenta-soft hover:border-magenta/60 transition-colors rico-focus-strong"
                >
                    {opt.label}
                </button>
            ))}
        </div>
    );
}

export default function CommandPage() {
    const router = useRouter();
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
    const [userProfile, setUserProfile] = useState<ProfileResponse | null>(null);
    const [profileLoading, setProfileLoading] = useState(true);
    const bottomRef = useRef<HTMLDivElement>(null);
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
        }, 5000);

        fetchMe(controller.signal)
            .then((me) => {
                if (cancelled) return;
                clearTimeout(fallbackId);
                setChatAudience(me.authenticated ? "authenticated" : "public");
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

    useEffect(() => {
        if (chatAudience === "checking") return;
        if (chatAudience !== "authenticated") {
            setProfileLoading(false);
            return;
        }
        fetchProfile()
            .then(setUserProfile)
            .catch(() => {})
            .finally(() => setProfileLoading(false));
    }, [chatAudience]);

    const scrollBottom = useCallback(() => {
        const behavior = prefersReducedMotion() ? "auto" : "smooth";
        if (typeof window !== "undefined") {
            window.requestAnimationFrame(() => {
                bottomRef.current?.scrollIntoView({ behavior });
            });
            return;
        }
        setTimeout(() => bottomRef.current?.scrollIntoView({ behavior }), 50);
    }, []);

    const sendMessage = useCallback(async (text: string) => {
        if (chatAudience === "checking") return;
        if (text === "__cv_upload__") {
            fileInputRef.current?.click();
            return;
        }
        const trimmed = text.trim();
        if (!trimmed || thinking) return;

        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: trimmed }]);
        setThinking(true);
        const lc = trimmed.toLowerCase();
        if (lc.match(/\b(subscri|plan|pricing|package|upgrade)\b/)) {
            setOperationState({ state: "checking", message: "Checking plans…" });
        } else if (lc.match(/\b(job|find|search|vacanc|opening|role|position|hiring)\b/)) {
            setOperationState({ state: "searching", message: "Searching UAE jobs…" });
        } else if (lc.match(/\b(appli|track|application|status|applied|offer)\b/)) {
            setOperationState({ state: "reviewing", message: "Reviewing applications…" });
        } else if (lc.match(/\b(cv|resume|profile|experience|skills)\b/)) {
            setOperationState({ state: "reading", message: "Looking at your profile…" });
        } else if (lc.match(/\b(career|next move|recommend|suggest|direction|trajectory|what should)\b/)) {
            setOperationState({ state: "extracting", message: "Preparing recommendations…" });
        } else if (lc.match(/\b(interview|prep|prepare|question)\b/)) {
            setOperationState({ state: "extracting", message: "Preparing interview guidance…" });
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

        try {
            // Use SSE streaming for conversational messages; fall back to JSON for errors
            const streamId = nextId();
            let streamStarted = false;

            function applyDoneResponse(res: ChatApiResponse) {
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
                        return [...filtered, { id: streamId, role: "rico", text: "Rico is busy right now — please try again in a minute." }];
                    });
                } else if (isFallbackMode) {
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, { id: streamId, role: "rico", text: "I'm here! Upload your CV to get started, or ask me about UAE jobs, applications, or interview prep.", options: res.options as RicoOption[] | undefined }];
                    });
                } else if (!reply && !res.matches && !res.options) {
                    setMessages((prev) => {
                        const filtered = prev.filter((m) => m.id !== streamId);
                        return [...filtered, { id: streamId, role: "rico", text: "Rico returned an empty response. Please try again." }];
                    });
                } else {
                    const hasEmptyMatches = res.type === "job_matches" && Array.isArray(res.matches) && res.matches.length === 0;
                    const displayText = hasEmptyMatches && !reply
                        ? "No live UAE matches found right now. Try a related role or broaden your search — I can suggest alternatives based on your CV."
                        : reply;
                    const displayOptions: RicoOption[] = hasEmptyMatches && !res.options ? [
                        { action: "broaden", label: "Suggest related roles", message: "Suggest roles similar to my target based on my CV" },
                        { action: "upload_cv", label: "Upload or update my CV", message: "__cv_upload__" },
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
                            rate_limit_notice: res.rate_limited ? (res.rate_limit_notice ?? "This source is temporarily rate-limited. Try the alternate link.") : undefined,
                            applications: (res as Record<string, unknown>).applications as ApplicationEntry[] | undefined,
                            follow_up_needed: (res as Record<string, unknown>).follow_up_needed as ApplicationEntry[] | undefined,
                            profile_gaps: (res as Record<string, unknown>).profile_gaps as string[] | undefined,
                            streaming: false,
                        }];
                    });
                }
            }

            const streamGen = chatAudience === "authenticated"
                ? sendChatStream(trimmed, controller.signal)
                : sendChatStreamPublic(trimmed, getSessionId(sessionIdRef), controller.signal);

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
                            ? await sendChat(trimmed, controller.signal)
                            : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal);
                    applyDoneResponse(res);
                }
            }

            if (!streamStarted) {
                const res: ChatApiResponse =
                    chatAudience === "authenticated"
                        ? await sendChat(trimmed, controller.signal)
                        : await sendChatPublic(trimmed, getSessionId(sessionIdRef), controller.signal);
                applyDoneResponse(res);
            }
        } catch (err) {
            if (err instanceof Error) {
                if (err.name === "AbortError") {
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: "Rico is taking longer than usual — the server may be waking up. Please try again in 30 seconds." }]);
                    return;
                }
                if (err.message.includes("401")) { setSessionExpired(true); return; }
                if (err.name === "TypeError" || err.message === "Failed to fetch" || err.message.includes("network")) {
                    setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: "Could not reach Rico. Check your connection or try again." }]);
                    return;
                }
            }
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: "Something went wrong. Please try again." }]);
        } finally {
            clearTimeout(timeoutId);
            clearTimeout(slowHintId);
            setSlowHint(false);
            setThinking(false);
            setOperationState(null);
            scrollBottom();
            textareaRef.current?.focus();
        }
    }, [chatAudience, scrollBottom, thinking]);

    useEffect(() => {
        if (chatAudience === "checking" || promptSentRef.current) return;
        if (chatAudience === "authenticated" && profileLoading) return;
        promptSentRef.current = true;
        const timeoutId = window.setTimeout(() => {
            if (prompt) {
                void sendMessage(prompt);
                return;
            }
            if (cvReady) {
                setMessages([{ id: 1, role: "rico", text: "Your CV is ready — I've read it and built your profile.\n\nWhat would you like to do next?\n\n- Find UAE jobs that match my CV\n- Analyze my best next career move\n- Show my profile summary\n- Track my applications" }]);
                return;
            }
            setMessages([{ id: 1, role: "rico", text: buildWelcomeMessage(chatAudience === "authenticated", userProfile) }]);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [chatAudience, cvReady, profileLoading, userProfile, prompt, sendMessage]);

    async function handleCVUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file || chatAudience === "checking") return;
        e.target.value = "";
        setUploadError("");
        setMessages((prev) => [...prev, { id: nextId(), role: "user", text: `📎 Uploading CV: ${file.name}` }]);
        setThinking(true);
        setOperationState({ state: "reading", message: "Reading CV…" });
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
                const text = result.message || `This document does not look like a CV/resume (detected as: ${result.document_type}). I did not update your personal job profile. Please upload a personal CV or resume.`;
                setMessages((prev) => [...prev, { id: nextId(), role: "rico", text }]);
                return;
            }

            // Check if preview is ready for confirmation
            if (result.status === "preview_ready" && result.preview) {
                const preview = result.preview;
                // Handle both new (skills_detected) and old (skills) response shapes
                const skills = preview.skills_detected ?? preview.skills ?? [];
                const previewText = (
                    `CV profile preview\n\n` +
                    `Name: ${preview.name || "—"}\n` +
                    `Email: ${preview.email || "—"}\n` +
                    `Phone: ${preview.phone || "—"}\n` +
                    `Current role: ${preview.current_role || "—"}\n` +
                    `Experience: ${preview.experience_years ? `~${preview.experience_years} years` : "—"}\n` +
                    `Skills: ${skills.slice(0, 6).join(", ") || "—"}\n` +
                    `Document quality: ${result.extraction_quality || "unknown"}\n\n` +
                    `Use this profile for job matching?`
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
                    skills.length ? `Skills detected: ${skills.slice(0, 6).join(", ")}` : "",
                    p.emails?.length ? `Email: ${p.emails[0]}` : "",
                    p.phones?.length ? `Phone: ${p.phones[0]}` : "",
                    p.extracted_chars ? `Chars extracted: ${p.extracted_chars}` : "",
                ].filter(Boolean).join(" · ");

                let text: string;
                if (p.extraction_quality === "poor") {
                    text = `CV received: ${file.name}, but I could not read enough text from the document. It may be scanned or image-based. Please upload a text-based PDF or DOCX for better extraction.`;
                } else if (p.extraction_quality === "partial") {
                    text = `CV received: ${file.name}. I extracted the readable details and updated your profile.${summary ? `\n\n${summary}` : ""}\n\nTell me your target roles and I'll start finding matches.`;
                } else {
                    text = `CV received: ${file.name}. I extracted your details and pre-filled your profile.${summary ? `\n\n${summary}` : ""}\n\nTell me your target roles and I'll start finding matches.`;
                }
                setMessages((prev) => [...prev, { id: nextId(), role: "rico", text }]);
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Upload failed";
            setUploadError(msg);
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: `Could not process CV: ${msg}. Please make sure it's a PDF under 10 MB.` }]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    async function handleConfirmProfile(preview: ProfilePreview, filename: string, messageId: number) {
        setThinking(true);
        setOperationState({ state: "confirming", message: "Saving your profile…" });
        try {
            const userId = `public:${getSessionId(sessionIdRef)}`;
            await confirmCVProfile({ preview, filename }, userId);
            const confirmText = chatAudience === "public"
                ? "Profile saved for this session.\n\n**Sign up free** to keep your profile, track applications, and get job alerts — so you don't lose your progress when you close the tab."
                : "Profile confirmed. I can now use it for job matching. Tell me your target roles and I'll start finding matches.";
            setMessages((prev) => prev.map(m => m.id === messageId ? { ...m, type: "profile_confirmed", text: confirmText } : m));
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Confirmation failed";
            setMessages((prev) => [...prev, { id: nextId(), role: "rico", text: `Could not confirm profile: ${msg}. Please try again.` }]);
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
                    <p className="text-sm font-medium text-white">Session expired.</p>
                    <p className="text-sm text-text-muted">Sign in again to continue chatting with Rico.</p>
                    <Link href={COMMAND_LOGIN_HREF} className="rounded-lg bg-magenta px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-magenta-hover">
                        Sign in
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex flex-col relative overflow-hidden">
            {/* Ambient glows - cinematic magenta/cyan */}
            <div className="fixed inset-0 pointer-events-none z-0">
                <div aria-hidden="true" className="absolute -top-[250px] -left-[150px] w-[700px] h-[700px] rounded-full bg-magenta-dim blur-[140px]" />
                <div aria-hidden="true" className="absolute bottom-0 -right-[100px] w-[500px] h-[500px] rounded-full bg-cyan-dim blur-[140px]" />
            </div>

            {/* Top nav — minimal, matches landing */}
            <header className="relative z-10 flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-border-subtle">
                <Link href="/" className="flex items-center gap-2 text-white font-black text-base sm:text-lg tracking-tight">
                    <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-[9px] bg-[#f5a623] flex items-center justify-center text-sm font-black text-[#0a0a1a] shadow-[0_4px_16px_rgba(245,166,35,0.35)]">R</div>
                    Rico<span className="text-[#f5a623]"> Hunt</span>
                </Link>
                <div className="flex items-center gap-2 sm:gap-3">
                    {chatAudience === "authenticated" ? (
                        <>
                            <Link href="/profile" className="hidden sm:block text-[13px] text-text-muted hover:text-white transition-colors">Profile</Link>
                            <button
                                type="button"
                                onClick={handleLogout}
                                className="text-[12px] px-3 py-1.5 rounded-lg bg-magenta text-white hover:bg-magenta-hover transition-colors font-medium"
                            >
                                Sign out
                            </button>
                        </>
                    ) : chatAudience === "public" ? (
                        <>
                            <Link href={COMMAND_LOGIN_HREF} className="text-[13px] text-text-muted hover:text-white transition-colors">Sign in</Link>
                            <Link href={COMMAND_SIGNUP_HREF} className="text-[12px] px-3 py-1.5 rounded-lg bg-magenta text-white hover:bg-magenta-hover transition-colors font-medium">Sign up free</Link>
                        </>
                    ) : (
                        /* checking — reveal no auth state until /me resolves, so signed-in
                           users never flash public "Sign in / Sign up free" links. */
                        <span
                            aria-hidden="true"
                            className="h-8 w-28 rounded-lg bg-surface/60 border border-border-subtle animate-pulse motion-reduce:animate-none"
                        />
                    )}
                </div>
            </header>

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

            {/* Context strip — shown for authenticated users with profile data */}
            {chatAudience === "authenticated" && !profileLoading && userProfile?.profile_exists && (
                <div className="relative z-10 flex items-center gap-3 px-4 sm:px-6 py-2 border-b border-border-subtle bg-surface/20 overflow-x-auto">
                    {userProfile.name && (
                        <span className="text-[11px] font-medium text-white shrink-0">
                            {userProfile.name.split(" ")[0]}
                        </span>
                    )}
                    {(userProfile.target_roles?.[0] ?? userProfile.current_role) && (
                        <span className="text-[10px] text-text-muted shrink-0">
                            {userProfile.target_roles?.[0] ?? userProfile.current_role} · UAE
                        </span>
                    )}
                    <div className="flex-1" />
                    <span className={`text-[9px] px-2 py-0.5 rounded-full border font-medium shrink-0 whitespace-nowrap ${
                        (userProfile.completeness_score ?? 0) > 0.15
                            ? "border-cyan/30 text-cyan bg-cyan/5"
                            : "border-amber-400/30 text-amber-400 bg-amber-400/5"
                    }`}>
                        {(userProfile.completeness_score ?? 0) > 0.15 ? "CV Active" : "Upload CV"}
                    </span>
                </div>
            )}

            <div className="relative z-10 flex flex-col flex-1 h-[calc(100dvh-57px)] sm:h-[calc(100dvh-65px)] max-w-3xl w-full mx-auto px-2 sm:px-4">
                {/* Messages Container */}
                <div className="flex-1 min-h-0 overflow-y-auto px-2 py-6 space-y-5" role="log" aria-live="polite" aria-atomic="false" aria-busy={thinking}>

                    {/* Quick start (shown above first message) */}
                    {messages.length <= 1 && !thinking && (
                        <div className="grid grid-cols-2 sm:flex sm:flex-wrap sm:justify-center gap-2 pb-4" dir="ltr">
                            {QUICK_ACTIONS.map((qa) => (
                                <button
                                    type="button"
                                    key={qa.label}
                                    onClick={() => sendMessage(qa.prompt)}
                                    disabled={thinking || chatAudience === "checking"}
                                    className="rounded-xl border border-border-subtle bg-surface-glass px-3 py-2 text-[11px] sm:text-xs text-text-secondary transition-colors hover:border-magenta/30 hover:bg-surface-subtle hover:text-white disabled:opacity-50 rico-focus-strong text-center"
                                >
                                    {qa.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((m, idx) => {
                        const prevMsg = messages[idx - 1];
                        const isFirstInGroup = !prevMsg || prevMsg.role !== m.role;
                        // Only profile_preview gets a light panel — job cards and app cards
                        // float as attachments directly in the chat stream.
                        const isStructured = m.type === "profile_preview";

                        return (
                            <div
                                key={m.id}
                                className={`flex animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none ${m.role === "user" ? "justify-end items-end" : "justify-start items-start gap-2.5"} ${isFirstInGroup ? "mt-4" : "mt-1"}`}
                            >
                                {m.role === "rico" && (
                                    <div
                                        className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black shrink-0 mt-0.5 ${isFirstInGroup ? "bg-[#f5a623]/15 border border-[#f5a623]/25 text-[#f5a623]" : "invisible"}`}
                                        aria-hidden="true"
                                    >R</div>
                                )}
                                <div className={`${m.role === "user"
                                    ? "max-w-[75%] sm:max-w-[68%] rounded-2xl rounded-tr-sm bg-magenta px-3.5 py-2.5 text-[14px] text-white leading-relaxed shadow-sm"
                                    : isStructured
                                        ? "flex-1 min-w-0 rounded-xl bg-surface/20 border border-border-subtle/40 p-3 text-[13px] text-white leading-relaxed"
                                        : "flex-1 min-w-0 text-[14px] text-white leading-relaxed"
                                    }`}>

                                    {/* Search result caption */}
                                    {m.type === "job_matches" && m.search_query && (
                                        <div className="mb-1.5 text-[10px] text-text-muted">
                                            {m.result_count != null && m.result_count > 0
                                                ? `${m.result_count} match${m.result_count === 1 ? "" : "es"}`
                                                : "No matches"} for <strong className="text-text-secondary">{m.search_query}</strong>
                                            {m.broadened && <span className="text-rico-amber"> · broadened</span>}
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
                                        <div className="mt-2 flex items-start gap-2 rounded-lg border border-rico-amber/40 bg-rico-amber/10 px-3 py-2 text-[11px] text-rico-amber">
                                            <span aria-hidden="true">⚠️</span>
                                            <span>{m.rate_limit_notice}</span>
                                        </div>
                                    )}

                                    {/* Job match cards */}
                                    {m.matches && m.matches.length > 0 && (
                                        <div className="mt-2 space-y-2">
                                            {m.matches.map((match, i) => (
                                                <JobMatchCard key={i} match={match} onAction={(prompt) => sendMessage(prompt)} />
                                            ))}
                                        </div>
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
                                                className="text-[12px] px-4 py-2 rounded-lg bg-cyan text-white font-medium hover:bg-cyan-hover transition-colors disabled:opacity-50"
                                            >
                                                Use this profile
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setEditingProfileId(m.id);
                                                    setDraftProfile(m.preview!);
                                                }}
                                                disabled={thinking}
                                                className="text-[12px] px-4 py-2 rounded-lg border border-border-soft text-text-secondary hover:border-magenta/40 hover:text-white transition-colors disabled:opacity-50"
                                            >
                                                Edit before saving
                                            </button>
                                        </div>
                                    )}
                                    {m.type === "profile_preview" && editingProfileId === m.id && draftProfile && (
                                        <div className="mt-3 space-y-2 border-t border-border-soft pt-3">
                                            <p className="text-[11px] font-semibold text-magenta">Edit profile</p>
                                            {(
                                                [
                                                    ["name", "Name"],
                                                    ["current_role", "Current role"],
                                                    ["email", "Email"],
                                                    ["phone", "Phone"],
                                                ] as [keyof ProfilePreview, string][]
                                            ).map(([field, label]) => (
                                                <label key={field} className="block space-y-0.5">
                                                    <span className="text-[10px] text-text-muted">{label}</span>
                                                    <input
                                                        value={(draftProfile[field] as string) ?? ""}
                                                        onChange={(e) =>
                                                            setDraftProfile((prev) => (prev ? { ...prev, [field]: e.target.value } : prev))
                                                        }
                                                        className="w-full rounded-lg bg-surface-subtle border border-border-soft px-3 py-1.5 text-[12px] text-white placeholder:text-text-muted focus:outline-none focus:border-magenta/60"
                                                    />
                                                </label>
                                            ))}
                                            <label className="block space-y-0.5">
                                                <span className="text-[10px] text-text-muted">Skills (comma-separated)</span>
                                                <input
                                                    value={(draftProfile.skills_detected ?? draftProfile.skills ?? []).join(", ")}
                                                    onChange={(e) => {
                                                        const skills = e.target.value.split(",").map((skill) => skill.trim()).filter(Boolean);
                                                        setDraftProfile((prev) =>
                                                            prev ? { ...prev, skills_detected: skills, skills } : prev
                                                        );
                                                    }}
                                                    className="w-full rounded-lg bg-surface-subtle border border-border-soft px-3 py-1.5 text-[12px] text-white placeholder:text-text-muted focus:outline-none focus:border-magenta/60"
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
                                                    className="text-[12px] px-4 py-2 rounded-lg bg-cyan text-white font-medium hover:bg-cyan-hover transition-colors disabled:opacity-50"
                                                >
                                                    Save profile
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setEditingProfileId(null);
                                                        setDraftProfile(null);
                                                    }}
                                                    className="text-[12px] px-4 py-2 rounded-lg border border-border-soft text-text-secondary hover:border-magenta/40 hover:text-white transition-colors"
                                                >
                                                    Cancel
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
                                                            className="text-[11px] px-3 py-1.5 rounded-xl border border-magenta/30 text-magenta hover:bg-magenta-soft hover:border-magenta/60 transition-colors rico-focus-strong"
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
                            <WorkingIndicator message={operationState?.message ?? "Thinking…"} />
                            {slowHint && (
                                <p className="text-[11px] text-text-muted pl-[42px] animate-pulse motion-reduce:animate-none" role="status">
                                    Rico is waking up — first request after idle can take up to a minute…
                                </p>
                            )}
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                {/* Input bar — shrink-0 flex child keeps it below the scroll area;
                    safe-area padding covers iOS home indicator. */}
                <div className="shrink-0 px-4 pt-3 pb-[calc(1.25rem+env(safe-area-inset-bottom))] bg-gradient-to-t from-background via-background/95 to-transparent">
                    {chatAudience === "public" && messages.filter((m) => m.role === "rico").length >= 2 && (
                        <div className="mb-2 flex items-center justify-between gap-3 px-1">
                            <p className="text-[11px] text-text-muted">Save your profile and track applications.</p>
                            <Link
                                href={COMMAND_SIGNUP_HREF}
                                className="text-[11px] px-3 py-1 rounded-lg bg-magenta/10 border border-magenta/30 text-magenta hover:bg-magenta/20 transition-colors shrink-0 font-medium"
                            >
                                Sign up free
                            </Link>
                        </div>
                    )}
                    {uploadError && (
                        <p className="text-[11px] text-rico-red mb-2 text-center" role="alert">{uploadError}</p>
                    )}
                    <div className="flex items-end gap-2">
                        {/* CV upload button */}
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={thinking || chatAudience === "checking"}
                            title="Upload your CV (PDF)"
                            className="w-10 h-10 rounded-xl border border-border-soft bg-surface/80 text-text-secondary flex items-center justify-center hover:border-magenta/40 hover:text-white transition-all disabled:opacity-30 shrink-0 rico-focus-strong"
                            aria-label="Upload CV"
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
                                    ? "Checking your session…"
                                    : "Ask Rico anything — jobs, CV, applications, interviews…"}
                                className="w-full resize-none bg-surface border border-border-soft hover:border-border-strong focus:border-magenta/60 backdrop-blur-xl rounded-2xl py-3 pl-4 pr-12 text-sm text-white placeholder:text-text-muted transition-all shadow-2xl"
                            />
                            <button
                                type="button"
                                onClick={handleSend}
                                disabled={thinking || chatAudience === "checking" || !input.trim()}
                                className="absolute right-2 top-1.5 bottom-1.5 w-9 h-9 rounded-xl bg-magenta text-white flex items-center justify-center hover:bg-magenta-hover transition-all disabled:opacity-30 disabled:grayscale rico-focus-strong"
                                aria-label={thinking ? "Sending…" : "Send"}
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
                        Enter to send · Shift+Enter for new line · clip icon to upload CV
                    </p>
                </div>
            </div>
        </div>
    );
}
