"use client";

import type { ChatApiResponse, JobMatch, NextAction, ProfilePreview, RicoOption, UploadCVResponse } from "@/lib/api";
import { confirmCVProfile, fetchMe, logout, sendChat, sendChatPublic, sendChatStream, sendChatStreamPublic, uploadCV } from "@/lib/api";
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

interface Message {
    id: number;
    role: "user" | "rico";
    text: string;
    type?: string;
    matches?: JobMatch[];
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

function ThinkingIndicator({ label }: { label?: string }) {
    return (
        <div className="rico-thinking-row" role="status" aria-live="polite" aria-label="Rico is thinking">
            <span className="sr-only">Rico is thinking</span>
            <div className="rico-orb" aria-hidden="true"><span>R</span></div>
            <div className="rico-thinking-label">
                <span>{label ?? "Thinking…"}</span>
                <span className="rico-dots" aria-hidden="true"><i /><i /><i /></span>
            </div>
        </div>
    );
}

function OperationStateIndicator({ state, message }: { state: string; message: string }) {
    const icons = {
        reading: "📄",
        extracting: "⚙️",
        searching: "🔍",
        confirming: "✓",
    };
    const icon = icons[state as keyof typeof icons] || "⏳";

    return (
        <div className="flex justify-start animate-pulse motion-reduce:animate-none" role="status" aria-live="polite">
            <div className="bg-surface border border-border-subtle rounded-2xl rounded-tl-none px-4 py-3 flex gap-2 items-center backdrop-blur-md">
                <span className="text-lg" aria-hidden="true">{icon}</span>
                <span className="text-[13px] text-text-secondary">{message}</span>
            </div>
        </div>
    );
}

function JobMatchCard({ match, onAction }: { match: JobMatch; onAction: (prompt: string) => void }) {
    const score = match.score ?? 0;
    const scoreLabel = score >= 0.8 ? "Strong match" : score >= 0.6 ? "Good match" : "Possible match";
    const confidence = match.confidence || "medium";

    // Confidence badge styling with clear accessibility (colored text + border on dark background)
    const getConfidenceBadge = () => {
        const config = {
            high: {
                label: "High confidence fit",
                bgColor: "bg-transparent",
                textColor: "text-cyan",
                borderColor: "border-cyan",
                icon: "✓"
            },
            medium: {
                label: "Medium confidence fit",
                bgColor: "bg-transparent",
                textColor: "text-rico-amber",
                borderColor: "border-rico-amber",
                icon: "○"
            },
            low: {
                label: "Needs careful review",
                bgColor: "bg-transparent",
                textColor: "text-rico-red",
                borderColor: "border-rico-red",
                icon: "!"
            }
        };
        return config[confidence as keyof typeof config] || config.medium;
    };

    const confidenceBadge = getConfidenceBadge();

    return (
        <article className="rounded-xl border border-border-subtle bg-surface p-3 mb-2" aria-label={`Job match: ${match.title} at ${match.company}. ${scoreLabel}. ${confidenceBadge.label}.`}>
            {/* Top row: title, company, score, confidence */}
            <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-white">{match.title}</div>
                    <div className="text-[11px] text-text-secondary">{match.company}{match.location ? ` · ${match.location}` : ""}</div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                    {score > 0 && (
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${score >= 0.8
                            ? "bg-cyan-dim text-cyan"
                            : score >= 0.6
                                ? "bg-rico-amber/10 text-rico-amber"
                                : "bg-magenta-dim text-magenta"
                            }`}>
                            {scoreLabel}
                        </span>
                    )}
                    {/* Confidence badge with icon and label for accessibility */}
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 flex items-center gap-1 ${confidenceBadge.bgColor} ${confidenceBadge.textColor} border ${confidenceBadge.borderColor} cursor-pointer`}>
                        <span aria-hidden="true">{confidenceBadge.icon}</span>
                        <span>{confidenceBadge.label}</span>
                    </span>
                </div>
            </div>

            {/* Why this fits - max 4 items for scan speed */}
            {match.match_reasons && match.match_reasons.length > 0 && (
                <section className="mb-2" aria-label="Why this job fits your profile">
                    <p className="text-[10px] font-semibold text-cyan mb-1">Why this fits:</p>
                    <ul className="text-[10px] text-text-secondary list-disc list-inside space-y-0.5">
                        {match.match_reasons.slice(0, 4).map((reason, idx) => (
                            <li key={idx}>{reason}</li>
                        ))}
                        {match.match_reasons.length > 4 && (
                            <li className="text-[9px] text-text-muted italic">+{match.match_reasons.length - 4} more reasons</li>
                        )}
                    </ul>
                </section>
            )}

            {/* Worth checking - max 3 items to prevent overwhelming */}
            {match.match_concerns && match.match_concerns.length > 0 && (
                <section className="mb-2" aria-label="Items worth checking about this job match">
                    <p className="text-[10px] font-semibold text-rico-amber mb-1">Worth checking:</p>
                    <ul className="text-[10px] text-text-secondary list-disc list-inside space-y-0.5">
                        {match.match_concerns.slice(0, 3).map((concern, idx) => (
                            <li key={idx}>{concern}</li>
                        ))}
                        {match.match_concerns.length > 3 && (
                            <li className="text-[9px] text-text-muted italic">+{match.match_concerns.length - 3} more</li>
                        )}
                    </ul>
                </section>
            )}

            {/* Missing facts - max 3 items for cognitive load */}
            {match.missing_facts && match.missing_facts.length > 0 && (
                <section className="mb-2" aria-label="Missing facts from job posting">
                    <p className="text-[10px] font-semibold text-magenta mb-1">Missing facts:</p>
                    <ul className="text-[10px] text-text-secondary list-disc list-inside space-y-0.5">
                        {match.missing_facts.slice(0, 3).map((fact, idx) => (
                            <li key={idx}>{fact}</li>
                        ))}
                        {match.missing_facts.length > 3 && (
                            <li className="text-[9px] text-text-muted italic">+{match.missing_facts.length - 3} more</li>
                        )}
                    </ul>
                </section>
            )}

            {/* Recommended action - max 2 lines for instant clarity */}
            {match.recommended_action && (
                <section className="mb-2 p-2 bg-surface-subtle rounded-lg border-l-2 border-magenta" aria-label="Recommended next step">
                    <p className="text-[10px] font-semibold text-magenta mb-0.5">Recommended next step:</p>
                    <p className="text-[10px] text-white leading-relaxed line-clamp-2">{match.recommended_action}</p>
                </section>
            )}

            {/* Fallback to legacy why field */}
            {!match.match_reasons && match.why && (
                <p className="text-[11px] text-text-muted mb-2 leading-relaxed">{match.why}</p>
            )}

            {/* Apply / Source links — fallback chain: apply_url → source_url → alt_link.
                The first usable link becomes "Apply now"; the next distinct link is
                offered as an alternate so the user keeps a path when one source is down. */}
            {(() => {
                const clean = (u?: string) => (u && u !== "#" ? u.trim() : "");
                const chain = [clean(match.apply_url), clean(match.source_url), clean(match.alt_link)].filter(Boolean);
                const primary = chain[0] || "";
                const alternate = chain.find((u) => u !== primary) || "";
                return (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                        {primary && (
                            <a
                                href={primary}
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label={`Apply for ${match.title} at ${match.company}`}
                                className="text-[11px] px-3 py-1.5 rounded-lg bg-magenta text-white font-medium hover:bg-magenta-hover transition-colors"
                            >
                                Apply now
                            </a>
                        )}
                        {alternate && (
                            <a
                                href={alternate}
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label={`Open alternate link for ${match.title} at ${match.company}`}
                                className="text-[11px] px-3 py-1.5 rounded-lg border border-border-soft text-text-secondary hover:border-cyan/40 hover:text-white transition-colors"
                            >
                                Alternate link
                            </a>
                        )}
                        {!primary && match.verification_status === "lead_needs_verification" && (
                            <span className="text-[10px] px-2 py-1 rounded-lg border border-border-soft text-text-muted italic">
                                Link pending verification
                            </span>
                        )}
                    </div>
                );
            })()}
            <div className="flex flex-wrap gap-1.5 mt-2">
                {/* Chat action buttons */}
                {match.actions && match.actions.length > 0 && match.actions.map((action) => (
                    <button
                        type="button"
                        key={action}
                        onClick={() => onAction(`${action} — ${match.title} at ${match.company}`)}
                        aria-label={`${action} for ${match.title} at ${match.company}`}
                        className="text-[10px] px-2.5 py-1 rounded-lg border border-border-soft text-text-secondary hover:border-magenta/40 hover:text-white transition-colors"
                    >
                        {action}
                    </button>
                ))}
            </div>
        </article>
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
        if (lc.match(/\b(job|find|search|vacanc|opening|role|position|hiring|live jobs|live role)\b/)) {
            setOperationState({ state: "searching", message: "Searching UAE jobs…" });
        } else if (lc.match(/\b(match|appli|track|status|applied|offer)\b/)) {
            setOperationState({ state: "searching", message: "Checking your matches…" });
        } else if (lc.match(/\b(career|next move|recommend|suggest|direction|trajectory|what should)\b/)) {
            setOperationState({ state: "extracting", message: "Preparing recommendations…" });
        } else if (lc.match(/\b(cv|resume|profile|experience|skills)\b/)) {
            setOperationState({ state: "reading", message: "Reading your profile…" });
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
            setMessages([{ id: 1, role: "rico", text: "Hi, I'm Rico — your AI job-hunt partner in the UAE.\n\nUpload your CV and I'll find matching jobs, track your applications, and guide your next career move." }]);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [chatAudience, cvReady, prompt, sendMessage]);

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

            <div className="relative z-10 flex flex-col flex-1 h-[calc(100dvh-57px)] sm:h-[calc(100dvh-65px)] max-w-3xl w-full mx-auto px-2 sm:px-4">
                {/* Messages Container */}
                <div className="flex-1 overflow-y-auto px-2 py-6 space-y-5 pb-32" role="log" aria-live="polite" aria-atomic="false" aria-busy={thinking}>

                    {/* Quick start (shown above first message) */}
                    {messages.length <= 1 && !thinking && (
                        <div className="grid grid-cols-2 sm:flex sm:flex-wrap sm:justify-center gap-2 pb-4">
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
                        const hasJobCards = m.type === "job_matches" && Array.isArray(m.matches) && m.matches.length > 0;
                        const isStructured = m.type === "profile_preview" || hasJobCards;

                        return (
                            <div
                                key={m.id}
                                className={`flex animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none ${m.role === "user" ? "justify-end items-end gap-1.5" : "justify-start items-start gap-2"
                                    } ${isFirstInGroup ? "mt-3" : "mt-1"}`}
                            >
                                <div className={`${isStructured ? "max-w-[92%] sm:max-w-[85%]" : "max-w-[78%] sm:max-w-[72%]"} ${m.role === "user"
                                    ? "rounded-2xl rounded-tr-sm bg-magenta px-3.5 py-2.5 text-[14px] text-white leading-relaxed shadow-sm"
                                    : isStructured
                                        ? "rounded-xl bg-surface/60 border border-border-subtle p-3 text-[13px] text-white leading-relaxed backdrop-blur-sm"
                                        : "rounded-2xl rounded-tl-sm bg-surface/50 border border-border-subtle/60 px-3.5 py-2.5 text-[14px] text-white leading-relaxed backdrop-blur-sm"
                                    }`}>

                                    {/* Search result summary bar */}
                                    {m.type === "job_matches" && (
                                        <div className="flex items-center gap-2 mb-2 text-[10px] text-text-muted">
                                            <span className="text-cyan">🔍</span>
                                            <span>
                                                Searched: <strong className="text-text-secondary">{m.search_query ?? "UAE jobs"}</strong>
                                                {" · "}
                                                {m.result_count != null
                                                    ? m.result_count === 0
                                                        ? "No matches"
                                                        : `${m.result_count} match${m.result_count === 1 ? "" : "es"}`
                                                    : "Results"}
                                                {m.broadened && <span className="text-rico-amber"> · Broadened</span>}
                                            </span>
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
                            {operationState ? (
                                <OperationStateIndicator state={operationState.state} message={operationState.message} />
                            ) : (
                                <ThinkingIndicator />
                            )}
                            {slowHint && (
                                <p className="text-[11px] text-text-muted pl-9 animate-pulse motion-reduce:animate-none" role="status">
                                    Rico is waking up — first request after idle can take up to a minute…
                                </p>
                            )}
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                {/* Floating input bar — dvh column + safe-area keeps it on-screen above
                    the mobile browser chrome / iOS home indicator. */}
                <div className="absolute bottom-0 left-0 right-0 px-4 pt-4 pb-[calc(2rem+env(safe-area-inset-bottom))] bg-gradient-to-t from-background via-background to-transparent">
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
                                onChange={(e) => setInput(e.target.value)}
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
                        Enter to send · Shift+Enter for new line · 📎 to upload CV
                    </p>
                </div>
            </div>
        </div>
    );
}
