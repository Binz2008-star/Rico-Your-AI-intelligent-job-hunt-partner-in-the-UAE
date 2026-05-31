"use client";

export const dynamic = "force-dynamic";

import { MobileControls } from "@/components/MobileControls";
import { RicoButton } from "@/components/ui/rico/RicoButton";
import { RicoCommandInput } from "@/components/ui/rico/RicoCommandInput";
import { RicoGlassIsland } from "@/components/ui/rico/RicoGlassIsland";
import {
    RicoJobMatchCard,
    type JobMatchData,
} from "@/components/ui/rico/RicoJobMatchCard";
import { RicoMarkdownContent } from "@/components/ui/rico/RicoMarkdownContent";
import { RicoMessageBubble } from "@/components/ui/rico/RicoMessageBubble";
import { RicoStatusNode } from "@/components/ui/rico/RicoStatusNode";
import { useLanguage } from "@/contexts/LanguageContext";
import type {
    ChatApiResponse,
    JobMatch,
    NextAction,
    ProfilePreview,
    RicoOption,
    UploadCVResponse,
} from "@/lib/api";
import {
    ApiError,
    confirmCVProfile,
    fetchMe,
    getMySubscription,
    logout,
    sendChat,
    sendChatPublic,
    uploadCV,
} from "@/lib/api";
import { buildAuthHref } from "@/lib/redirect";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

// ─── Helpers (verbatim from /command) ────────────────────────────────────────

function ensureSessionId(
    sessionIdRef: React.MutableRefObject<string | null>,
): string {
    if (typeof window === "undefined")
        return sessionIdRef.current || "ssr-session";
    if (!sessionIdRef.current) {
        let sid = localStorage.getItem("rico_sid");
        if (!sid) {
            sid =
                "web-" +
                Date.now().toString(36) +
                "-" +
                Math.random().toString(36).slice(2, 9);
            localStorage.setItem("rico_sid", sid);
        }
        sessionIdRef.current = sid;
    }
    return sessionIdRef.current;
}

function getSessionId(
    sessionIdRef: React.MutableRefObject<string | null>,
): string {
    return ensureSessionId(sessionIdRef);
}

function prefersReducedMotion(): boolean {
    return (
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
}

// ─── Types (verbatim from /command) ──────────────────────────────────────────

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
    sourceLabel?: string;
}

type ChatAudience = "checking" | "authenticated" | "public";
type PendingOperation = {
    operationId: string;
    type: "job_search";
    query: string;
};

let _id = 0;
function nextId() {
    return ++_id;
}

function getSourceLabel(responseSource: string | undefined): string | null {
    // Only show provider labels in development mode
    if (process.env.NODE_ENV !== "development") {
        return null;
    }

    switch ((responseSource ?? "").toLowerCase()) {
        case "fallback":
        case "none":
            return null;
        case "huggingface":
        case "hf":
            return "HF active";
        case "deepseek":
            return "DeepSeek active";
        case "openai":
            return "OpenAI active";
        case "rate_limited":
            return "Provider rate-limited";
        default:
            return null;
    }
}

function createOperationId(): string {
    return (
        "op_web_" +
        Date.now().toString(36) +
        "_" +
        Math.random().toString(36).slice(2, 10)
    );
}

function looksLikeJobSearch(text: string): boolean {
    const normalized = text.toLowerCase();
    return (
        normalized.includes("job") ||
        normalized.includes("jobs") ||
        normalized.includes("find") ||
        normalized.includes("search") ||
        normalized.includes("live roles")
    );
}

// ─── Constants (verbatim from /command) ──────────────────────────────────────

const QUICK_ACTIONS = [
    {
        label: "commandQuickAction1",
        prompt:
            "Find matching jobs using my saved target role. If I do not have one saved, ask me which role to search for.",
    },
    {
        label: "commandQuickAction2",
        prompt:
            "Review my CV and profile for better job matches, then tell me the highest-impact improvements.",
    },
    {
        label: "commandQuickAction3",
        prompt: "Prepare an application plan for my strongest current job match.",
    },
    {
        label: "commandQuickAction4",
        prompt:
            "Check my application follow-ups and tell me what needs attention next.",
    },
];
const COMMAND_LOGIN_HREF = buildAuthHref("/login", "/command");
const COMMAND_SIGNUP_HREF = buildAuthHref("/signup", "/command");
const BACKEND_MAINTENANCE_MODE =
    process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";

// ─── Rico primitives: thinking + operation state ──────────────────────────────

function ThinkingIndicator({ t }: { t: ReturnType<typeof useTranslation> }) {
    return (
        <div
            className="flex justify-start"
            role="status"
            aria-live="polite"
            aria-label={t("commandThinking")}
        >
            <div className="flex items-center gap-2 px-4 py-3">
                <span className="sr-only">{t("commandThinking")}</span>
                <RicoStatusNode variant="magenta" animation="flicker" />
                <RicoStatusNode
                    variant="cyan"
                    animation="flicker"
                    className="[animation-delay:0.2s]"
                />
                <RicoStatusNode
                    variant="magenta"
                    animation="flicker"
                    className="[animation-delay:0.4s]"
                />
            </div>
        </div>
    );
}

function OperationStateIndicator({
    state,
    message,
}: {
    state: string;
    message: string;
}) {
    const icons: Record<string, string> = {
        reading: "📄",
        extracting: "⚙️",
        searching: "🔍",
        confirming: "✓",
    };
    const icon = icons[state] || "⏳";

    return (
        <div className="flex justify-start" role="status" aria-live="polite">
            <div className="flex items-center gap-2 px-4 py-3">
                <span aria-hidden="true">{icon}</span>
                <span className="text-[13px] text-[var(--rico-fg-3)]">{message}</span>
            </div>
        </div>
    );
}

// ─── OptionButtons migrated to RicoButton ────────────────────────────────────

function OptionButtons({
    options,
    onAction,
}: {
    options: RicoOption[];
    onAction: (prompt: string) => void;
}) {
    return (
        <div className="flex flex-wrap gap-2 mt-3">
            {options.map((opt) => (
                <RicoButton
                    key={opt.action}
                    variant="ghost"
                    size="sm"
                    onClick={() => onAction(opt.message ?? opt.label)}
                >
                    {opt.label}
                </RicoButton>
            ))}
        </div>
    );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CommandClient() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const router = useRouter();
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "true";
    const prompt =
        typeof window === "undefined"
            ? null
            : new URLSearchParams(window.location.search).get("prompt");

    // ── State (verbatim from /command) ──
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [thinking, setThinking] = useState(false);
    const [slowHint, setSlowHint] = useState(false);
    const [sessionExpired, setSessionExpired] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [chatAudience, setChatAudience] = useState<ChatAudience>(
        useMock ? "authenticated" : "checking",
    );
    const [operationState, setOperationState] = useState<{
        state: string;
        message: string;
    } | null>(null);
    const [editingProfileId, setEditingProfileId] = useState<number | null>(null);
    const [draftProfile, setDraftProfile] = useState<ProfilePreview | null>(null);
    const [userPlan, setUserPlan] = useState<"free" | "pro" | "premium" | null>(
        null,
    );

    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const promptSentRef = useRef(false);
    const sessionIdRef = useRef<string | null>(null);
    const pendingOperationRef = useRef<PendingOperation | null>(null);

    // ── Auth check (verbatim from /command) ──
    useEffect(() => {
        ensureSessionId(sessionIdRef);
        if (useMock) return;

        let cancelled = false;
        const controller = new AbortController();
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

    // ── Subscription plan fetch (non-blocking, authenticated only) ──
    useEffect(() => {
        if (chatAudience !== "authenticated") return;
        getMySubscription()
            .then((r) => setUserPlan(r.subscription.plan))
            .catch(() => { }); // non-critical
    }, [chatAudience]);

    // ── Scroll (verbatim from /command) ──
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

    // ── sendMessage (verbatim from /command) ──
    const sendMessage = useCallback(
        async (text: string) => {
            if (BACKEND_MAINTENANCE_MODE) return;
            if (chatAudience === "checking") return;
            if (text === "__cv_upload__") {
                fileInputRef.current?.click();
                return;
            }
            const trimmed = text.trim();
            if (!trimmed || thinking) return;

            setMessages((prev) => [
                ...prev,
                { id: nextId(), role: "user", text: trimmed },
            ]);
            setThinking(true);
            const jobSearchRequest = looksLikeJobSearch(trimmed);
            const operationId = jobSearchRequest ? createOperationId() : undefined;
            if (operationId) {
                pendingOperationRef.current = {
                    operationId,
                    type: "job_search",
                    query: trimmed,
                };
                setOperationState({
                    state: "searching",
                    message: t("commandSearching"),
                });
            }
            scrollBottom();

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 45_000);
            const slowHintId = setTimeout(() => setSlowHint(true), 5_000);
            let keepOperationVisible = false;

            try {
                const res: ChatApiResponse =
                    chatAudience === "authenticated"
                        ? await sendChat(trimmed, controller.signal, operationId, language)
                        : await sendChatPublic(
                            trimmed,
                            getSessionId(sessionIdRef),
                            controller.signal,
                            operationId,
                            language,
                        );
                if (res.operation_id) {
                    pendingOperationRef.current = {
                        operationId: res.operation_id,
                        type: "job_search",
                        query: trimmed,
                    };
                }
                if (
                    res.operation_status === "completed" ||
                    res.operation_status === "failed" ||
                    (!res.operation_id && operationId) ||
                    res.type === "clarification" ||
                    res.type === "profile_incomplete"
                ) {
                    pendingOperationRef.current = null;
                }
                const reply =
                    res.response ??
                    res.reply ??
                    res.message ??
                    res.content ??
                    res.answer ??
                    res.text ??
                    res.data?.response ??
                    res.data?.reply ??
                    res.data?.message ??
                    res.data?.content ??
                    res.data?.text ??
                    "";
                const responseSource = res.response_source ?? "unknown";
                const sourceLabel = getSourceLabel(responseSource);
                const isRateLimited = responseSource === "rate_limited";

                if (isRateLimited) {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: nextId(),
                            role: "rico",
                            text: "Rico's AI is rate-limited right now — please try again in a minute.",
                            sourceLabel: sourceLabel ?? undefined,
                        },
                    ]);
                } else if (!reply && !res.matches && !res.options) {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: nextId(),
                            role: "rico",
                            text: "Rico returned an empty response. Please try again.",
                        },
                    ]);
                } else {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: nextId(),
                            role: "rico",
                            text: reply,
                            type: res.type,
                            matches: res.matches as JobMatch[] | undefined,
                            options: res.options as RicoOption[] | undefined,
                            next_action: res.next_action,
                            roleName: res.role,
                            reasons: res.reasons,
                            next_actions: res.next_actions as NextAction[] | undefined,
                            sourceLabel: sourceLabel ?? undefined,
                        },
                    ]);
                }
            } catch (err) {
                if (err instanceof Error) {
                    if (err.name === "AbortError") {
                        keepOperationVisible = Boolean(pendingOperationRef.current);
                        const timeoutMessage = pendingOperationRef.current
                            ? 'Still searching. Ask "are you done?" or "check status" and I will check the last job search.'
                            : "Rico is taking longer than usual - the server may be waking up. Please try again in 30 seconds.";
                        if (pendingOperationRef.current) {
                            setOperationState({
                                state: "searching",
                                message: "Still searching. Check status when ready.",
                            });
                        }
                        setMessages((prev) => [
                            ...prev,
                            { id: nextId(), role: "rico", text: timeoutMessage },
                        ]);
                        return;
                    }
                    pendingOperationRef.current = null;
                    setOperationState(null);
                    if (
                        (err instanceof ApiError && err.statusCode === 401) ||
                        err.message.includes("401")
                    ) {
                        setSessionExpired(true);
                        return;
                    }
                    if (
                        err.name === "TypeError" ||
                        err.message === "Failed to fetch" ||
                        err.message.includes("network")
                    ) {
                        setMessages((prev) => [
                            ...prev,
                            {
                                id: nextId(),
                                role: "rico",
                                text: "Could not reach Rico. Check your connection or try again.",
                            },
                        ]);
                        return;
                    }
                }
                pendingOperationRef.current = null;
                setOperationState(null);
                setMessages((prev) => [
                    ...prev,
                    {
                        id: nextId(),
                        role: "rico",
                        text: "Something went wrong. Please try again.",
                    },
                ]);
            } finally {
                clearTimeout(timeoutId);
                clearTimeout(slowHintId);
                setSlowHint(false);
                setThinking(false);
                if (!keepOperationVisible && !pendingOperationRef.current) {
                    setOperationState(null);
                }
                scrollBottom();
                inputRef.current?.focus();
            }
        },
        [chatAudience, scrollBottom, thinking, language, t],
    );

    // ── Initial message / URL prompt (verbatim from /command) ──
    useEffect(() => {
        if (chatAudience === "checking" || promptSentRef.current) return;
        promptSentRef.current = true;
        const timeoutId = window.setTimeout(() => {
            if (prompt) {
                void sendMessage(prompt);
                return;
            }
            // For authenticated users, show profile-aware greeting instead of generic onboarding
            if (chatAudience === "authenticated") {
                setMessages([
                    {
                        id: 1,
                        role: "rico",
                        text: "Welcome back. I'm ready to help with your job search.\n\nWhat would you like to do today?\n\n- Find matching jobs\n- Analyze my career trajectory\n- Review my applications\n- Update my profile",
                    },
                ]);
                return;
            }
            setMessages([
                {
                    id: 1,
                    role: "rico",
                    text: "I'm Rico, your career trajectory intelligence system. Ask me to analyze your trajectory, evaluate an opportunity, map your next move, or upload your CV so I can build your strategic profile.",
                },
            ]);
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [chatAudience, prompt, sendMessage]);

    // ── CV upload (verbatim from /command) ──
    async function handleCVUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (BACKEND_MAINTENANCE_MODE) {
            e.target.value = "";
            return;
        }
        if (!file || chatAudience === "checking") return;
        e.target.value = "";
        setUploadError("");
        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: "user", text: `📎 Uploading CV: ${file.name}` },
        ]);
        setThinking(true);
        setOperationState({ state: "reading", message: "Reading PDF file..." });
        scrollBottom();
        try {
            const result: UploadCVResponse =
                chatAudience === "authenticated"
                    ? await uploadCV(file)
                    : await uploadCV(file, `public:${getSessionId(sessionIdRef)}`);
            if (
                typeof window !== "undefined" &&
                result.user_id &&
                result.user_id.startsWith("public:")
            ) {
                localStorage.setItem("rico_public_uid", result.user_id);
            }
            if (result.ok === false && result.document_type) {
                const text =
                    result.message ||
                    `This document does not look like a CV/resume (detected as: ${result.document_type}). I did not update your personal job profile. Please upload a personal CV or resume.`;
                setMessages((prev) => [...prev, { id: nextId(), role: "rico", text }]);
                return;
            }
            if (result.status === "preview_ready" && result.preview) {
                const preview = result.preview;
                const skills = preview.skills_detected ?? preview.skills ?? [];
                const previewText =
                    `CV profile preview\n\n` +
                    `Name: ${preview.name || "—"}\n` +
                    `Email: ${preview.email || "—"}\n` +
                    `Phone: ${preview.phone || "—"}\n` +
                    `Current role: ${preview.current_role || "—"}\n` +
                    `Experience: ${preview.experience_years ? `~${preview.experience_years} years` : "—"}\n` +
                    `Skills: ${skills.slice(0, 6).join(", ") || "—"}\n` +
                    `Document quality: ${result.extraction_quality || "unknown"}\n\n` +
                    `Use this profile for job matching?`;
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
            const p = result.parsed;
            if (p) {
                const skills = p.skills ?? [];
                const summary = [
                    skills.length
                        ? `Skills detected: ${skills.slice(0, 6).join(", ")}`
                        : "",
                    p.emails?.length ? `Email: ${p.emails[0]}` : "",
                    p.phones?.length ? `Phone: ${p.phones[0]}` : "",
                    p.extracted_chars ? `Chars extracted: ${p.extracted_chars}` : "",
                ]
                    .filter(Boolean)
                    .join(" · ");
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
            setMessages((prev) => [
                ...prev,
                {
                    id: nextId(),
                    role: "rico",
                    text: `Could not process CV: ${msg}. Please make sure it's a PDF under 10 MB.`,
                },
            ]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    // ── Confirm CV profile (verbatim from /command) ──
    async function handleConfirmProfile(
        preview: ProfilePreview,
        filename: string,
        messageId: number,
    ) {
        setThinking(true);
        setOperationState({ state: "confirming", message: "Saving profile..." });
        try {
            const userId = `public:${getSessionId(sessionIdRef)}`;
            await confirmCVProfile({ preview, filename }, userId);
            setMessages((prev) =>
                prev.map((m) =>
                    m.id === messageId
                        ? {
                            ...m,
                            type: "profile_confirmed",
                            text: "Profile confirmed. I can now use it for job matching. Tell me your target roles and I'll start finding matches.",
                        }
                        : m,
                ),
            );
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Confirmation failed";
            setMessages((prev) => [
                ...prev,
                {
                    id: nextId(),
                    role: "rico",
                    text: `Could not confirm profile: ${msg}. Please try again.`,
                },
            ]);
        } finally {
            setThinking(false);
            setOperationState(null);
            scrollBottom();
        }
    }

    // ── Input handlers (verbatim from /command) ──
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
            void handleSend();
        }
    }

    // ── Session expired screen ──
    if (sessionExpired) {
        return (
            <div className="min-h-screen bg-[var(--rico-bg)] flex items-center justify-center">
                <RicoGlassIsland className="flex max-w-lg flex-col items-center gap-4 p-8 text-center">
                    <p className="text-sm font-medium text-[var(--rico-fg-1)]">
                        Session expired.
                    </p>
                    <p className="text-sm text-[var(--rico-fg-3)]">
                        Sign in again to continue chatting with Rico.
                    </p>
                    <RicoButton
                        variant="magenta"
                        onClick={() => router.push(COMMAND_LOGIN_HREF)}
                    >
                        Sign in
                    </RicoButton>
                </RicoGlassIsland>
            </div>
        );
    }

    // ── Main render ──
    return (
        <div className="min-h-screen bg-[var(--rico-bg)] flex flex-col relative overflow-hidden">
            {/* Ambient glows */}
            <div className="fixed inset-0 pointer-events-none z-0" aria-hidden="true">
                <div className="absolute -top-[250px] -left-[150px] w-[700px] h-[700px] rounded-full bg-[var(--rico-magenta-glow)] blur-[140px] opacity-30" />
                <div className="absolute bottom-0 -right-[100px] w-[500px] h-[500px] rounded-full bg-[var(--rico-cyan-glow)] blur-[140px] opacity-25" />
            </div>

            {/* Header */}
            <header className="relative z-10 flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-[var(--rico-border-subtle)]">
                <Link
                    href="/"
                    className="flex items-center gap-2 text-[var(--rico-fg-1)] font-black text-base sm:text-lg tracking-tight"
                >
                    <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-[9px] bg-gradient-to-br from-[var(--rico-primary)] to-[var(--rico-secondary-dim)] flex items-center justify-center text-sm font-black shadow-[0_4px_16px_var(--rico-magenta-glow)]">
                        R
                    </div>
                    Rico<span className="text-[var(--rico-primary)]">.ai</span>
                </Link>
                <nav className="flex items-center gap-2 sm:gap-3">
                    {/* Mobile theme/language controls */}
                    <div className="sm:hidden">
                        <MobileControls />
                    </div>

                    {chatAudience === "authenticated" ? (
                        <>
                            {userPlan && userPlan !== "free" && (
                                <Link
                                    href="/subscription"
                                    className={`hidden sm:inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-widest border transition-colors ${userPlan === "premium"
                                        ? "border-[rgba(255,45,142,0.4)] bg-[rgba(255,45,142,0.1)] text-[#ff2d8e] hover:bg-[rgba(255,45,142,0.18)]"
                                        : "border-[rgba(91,79,255,0.4)] bg-[rgba(91,79,255,0.1)] text-[#7b6fff] hover:bg-[rgba(91,79,255,0.18)]"
                                        }`}
                                >
                                    {userPlan}
                                </Link>
                            )}
                            {userPlan === "free" && (
                                <Link
                                    href="/subscription"
                                    className="hidden sm:inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold border border-white/[0.08] bg-white/[0.03] text-[var(--rico-fg-4)] hover:text-[var(--rico-fg-2)] transition-colors"
                                >
                                    Free
                                </Link>
                            )}
                            <Link
                                href="/dashboard"
                                className="hidden sm:block text-[13px] text-[var(--rico-fg-3)] hover:text-[var(--rico-fg-1)] transition-colors"
                            >
                                Dashboard
                            </Link>
                            <RicoButton variant="magenta" size="sm" onClick={handleLogout}>
                                Sign out
                            </RicoButton>
                        </>
                    ) : chatAudience === "public" ? (
                        <>
                            <Link
                                href={COMMAND_LOGIN_HREF}
                                className="text-[13px] text-[var(--rico-fg-3)] hover:text-[var(--rico-fg-1)] transition-colors"
                            >
                                Sign in
                            </Link>
                            <RicoButton
                                variant="magenta"
                                size="sm"
                                onClick={() => router.push(COMMAND_SIGNUP_HREF)}
                            >
                                Sign up free
                            </RicoButton>
                        </>
                    ) : (
                        /* checking — hide auth links until /me resolves */
                        <span
                            aria-hidden="true"
                            className="h-8 w-28 rounded-[var(--r-xl)] bg-[rgba(255,255,255,0.05)] border border-[var(--rico-border-subtle)] animate-pulse motion-reduce:animate-none"
                        />
                    )}
                </nav>
            </header>

            {/* Hidden CV file input */}
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                aria-label="Upload CV PDF"
                title="Upload CV PDF"
                className="hidden"
                onChange={handleCVUpload}
                disabled={BACKEND_MAINTENANCE_MODE}
            />

            {/* Chat area */}
            <div className="relative z-10 flex flex-col flex-1 h-[calc(100dvh-57px)] sm:h-[calc(100dvh-65px)] max-w-3xl w-full mx-auto px-2 sm:px-4">
                {/* Message list */}
                <div
                    className="flex-1 overflow-y-auto px-2 py-6 space-y-5 pb-[calc(8rem+env(safe-area-inset-bottom))]"
                    role="log"
                    aria-live="polite"
                    aria-atomic="false"
                    aria-busy={thinking ? "true" : "false"}
                >
                    {BACKEND_MAINTENANCE_MODE && (
                        <div className="rounded-[var(--r-xl)] border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-amber-100">
                            <p className="text-sm font-semibold text-amber-300">
                                {t("commandMaintenance")}
                            </p>
                            <p className="mt-1 text-xs leading-relaxed text-amber-100/80">
                                Rico&apos;s backend service is temporarily offline while hosting
                                is being restored. Subscription, login, Telegram, and Stripe
                                webhook features are paused. No payment validation should be
                                attempted until the backend is back online.
                            </p>
                        </div>
                    )}

                    {/* Quick actions (shown before first real exchange) */}
                    {messages.length <= 1 && !thinking && !BACKEND_MAINTENANCE_MODE && (
                        <div className="grid grid-cols-2 sm:flex sm:flex-wrap sm:justify-center gap-2 pb-4">
                            {QUICK_ACTIONS.map((qa) => (
                                <button
                                    type="button"
                                    key={qa.label}
                                    onClick={() => sendMessage(qa.prompt)}
                                    disabled={thinking || chatAudience === "checking"}
                                    className="rounded-[var(--r-xl)] border border-[var(--rico-border-subtle)] bg-[rgba(255,255,255,0.03)] px-3 py-2 text-[11px] sm:text-xs text-[var(--rico-fg-3)] transition-colors hover:border-[var(--rico-primary-container)] hover:text-[var(--rico-fg-1)] disabled:opacity-50 text-center"
                                >
                                    {t(qa.label)}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((m) => (
                        <div
                            key={m.id}
                            className={`flex items-end gap-2 animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none ${m.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                            {/* Rico avatar */}
                            {m.role === "rico" && (
                                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--rico-primary)] to-[var(--rico-secondary-dim)] flex items-center justify-center text-[11px] font-black text-white shrink-0 mb-1 shadow-[0_2px_8px_var(--rico-magenta-glow)]">
                                    R
                                </div>
                            )}

                            <div
                                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"} max-w-[82%]`}
                            >
                                {/* Main bubble */}
                                {m.text &&
                                    (m.role === "user" ? (
                                        <div className="rounded-2xl rounded-tr-none bg-[var(--rico-primary)] px-4 py-3 text-[14px] text-white leading-relaxed shadow-[0_4px_15px_var(--rico-magenta-glow)]">
                                            <div className="whitespace-pre-wrap">{m.text}</div>
                                        </div>
                                    ) : (
                                        <RicoMessageBubble
                                            variant="assistant"
                                            useGlassWrap={m.text.length > 120}
                                        >
                                            <RicoMarkdownContent>{m.text}</RicoMarkdownContent>
                                        </RicoMessageBubble>
                                    ))}

                                {/* Job match cards */}
                                {m.matches && m.matches.length > 0 && (
                                    <div className="mt-3 w-full space-y-3">
                                        {m.matches.map((match, i) => (
                                            <RicoJobMatchCard
                                                key={i}
                                                match={match as JobMatchData}
                                                onActionClick={(action, job) =>
                                                    sendMessage(
                                                        `${action} — ${job.title} at ${job.company}`,
                                                    )
                                                }
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Profile preview: confirm / edit */}
                                {m.type === "profile_preview" &&
                                    m.preview &&
                                    m.filename &&
                                    editingProfileId !== m.id && (
                                        <div className="mt-3 flex gap-2">
                                            <RicoButton
                                                variant="primary"
                                                size="sm"
                                                onClick={() =>
                                                    handleConfirmProfile(m.preview!, m.filename!, m.id)
                                                }
                                                disabled={thinking}
                                            >
                                                Use this profile
                                            </RicoButton>
                                            <RicoButton
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => {
                                                    setEditingProfileId(m.id);
                                                    setDraftProfile(m.preview!);
                                                }}
                                                disabled={thinking}
                                            >
                                                Edit before saving
                                            </RicoButton>
                                        </div>
                                    )}

                                {/* Profile editor (inline) */}
                                {m.type === "profile_preview" &&
                                    editingProfileId === m.id &&
                                    draftProfile && (
                                        <div className="mt-3 w-full">
                                            <RicoGlassIsland className="p-4 space-y-3">
                                                <p className="text-[11px] font-semibold text-[var(--rico-primary)]">
                                                    Edit profile
                                                </p>
                                                {(
                                                    [
                                                        ["name", "Name"],
                                                        ["current_role", "Current role"],
                                                        ["email", "Email"],
                                                        ["phone", "Phone"],
                                                    ] as [keyof ProfilePreview, string][]
                                                ).map(([field, label]) => (
                                                    <label key={field} className="block space-y-0.5">
                                                        <span className="text-[10px] text-[var(--rico-fg-4)]">
                                                            {label}
                                                        </span>
                                                        <input
                                                            value={(draftProfile[field] as string) ?? ""}
                                                            onChange={(e) =>
                                                                setDraftProfile((prev) =>
                                                                    prev
                                                                        ? { ...prev, [field]: e.target.value }
                                                                        : prev,
                                                                )
                                                            }
                                                            className="w-full rounded-[var(--r-lg)] bg-[rgba(255,255,255,0.04)] border border-[var(--rico-border-soft)] px-3 py-1.5 text-[12px] text-[var(--rico-fg-1)] placeholder:text-[var(--rico-fg-4)] focus:outline-none focus:border-[var(--rico-primary-container)]"
                                                        />
                                                    </label>
                                                ))}
                                                <label className="block space-y-0.5">
                                                    <span className="text-[10px] text-[var(--rico-fg-4)]">
                                                        Skills (comma-separated)
                                                    </span>
                                                    <input
                                                        value={(
                                                            draftProfile.skills_detected ??
                                                            draftProfile.skills ??
                                                            []
                                                        ).join(", ")}
                                                        onChange={(e) => {
                                                            const skills = e.target.value
                                                                .split(",")
                                                                .map((s) => s.trim())
                                                                .filter(Boolean);
                                                            setDraftProfile((prev) =>
                                                                prev
                                                                    ? { ...prev, skills_detected: skills, skills }
                                                                    : prev,
                                                            );
                                                        }}
                                                        className="w-full rounded-[var(--r-lg)] bg-[rgba(255,255,255,0.04)] border border-[var(--rico-border-soft)] px-3 py-1.5 text-[12px] text-[var(--rico-fg-1)] placeholder:text-[var(--rico-fg-4)] focus:outline-none focus:border-[var(--rico-primary-container)]"
                                                    />
                                                </label>
                                                <div className="flex gap-2 pt-1">
                                                    <RicoButton
                                                        variant="primary"
                                                        size="sm"
                                                        onClick={() => {
                                                            handleConfirmProfile(
                                                                draftProfile,
                                                                m.filename!,
                                                                m.id,
                                                            );
                                                            setEditingProfileId(null);
                                                            setDraftProfile(null);
                                                        }}
                                                        disabled={thinking}
                                                    >
                                                        Save profile
                                                    </RicoButton>
                                                    <RicoButton
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            setEditingProfileId(null);
                                                            setDraftProfile(null);
                                                        }}
                                                    >
                                                        Cancel
                                                    </RicoButton>
                                                </div>
                                            </RicoGlassIsland>
                                        </div>
                                    )}

                                {/* Options */}
                                {m.options && m.options.length > 0 && (
                                    <OptionButtons
                                        options={m.options}
                                        onAction={(p) => sendMessage(p)}
                                    />
                                )}

                                {/* Role confirmation reasons + next_actions */}
                                {m.type === "role_confirmation" && (
                                    <div className="mt-3 space-y-2">
                                        {m.reasons && m.reasons.length > 0 && (
                                            <ul className="list-disc list-inside text-[13px] text-[var(--rico-fg-3)] space-y-0.5">
                                                {m.reasons.map((r, i) => (
                                                    <li key={i}>{r}</li>
                                                ))}
                                            </ul>
                                        )}
                                        {m.next_actions && m.next_actions.length > 0 && (
                                            <div className="flex flex-wrap gap-2 pt-1">
                                                {m.next_actions.map((na) => (
                                                    <RicoButton
                                                        key={na.action}
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => sendMessage(na.message ?? na.label)}
                                                    >
                                                        {na.label}
                                                    </RicoButton>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Source label */}
                                {m.sourceLabel && (
                                    <p className="mt-2 text-[11px] text-[var(--rico-fg-4)]">
                                        {m.sourceLabel}
                                    </p>
                                )}
                            </div>

                            {/* User avatar */}
                            {m.role === "user" && (
                                <div className="w-6 h-6 rounded-full bg-[rgba(255,255,255,0.06)] flex items-center justify-center text-[10px] font-medium text-[var(--rico-fg-3)] shrink-0 mb-1">
                                    You
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Free plan upsell nudge — shown after 4 messages for free-tier authenticated users */}
                    {chatAudience === "authenticated" &&
                        userPlan === "free" &&
                        messages.length >= 5 &&
                        messages.length % 6 === 5 &&
                        !thinking && (
                            <div className="flex items-center gap-3 rounded-[var(--r-xl)] border border-[rgba(91,79,255,0.25)] bg-[rgba(91,79,255,0.06)] px-4 py-3 text-[12px]">
                                <span className="text-[#7b6fff] shrink-0">✦</span>
                                <span className="text-[var(--rico-fg-3)]">
                                    You&apos;re on the Free plan —{" "}
                                    <span className="text-[var(--rico-fg-2)]">
                                        50 AI messages/mo.
                                    </span>{" "}
                                    Pro gives you 300.
                                </span>
                                <Link
                                    href="/subscription"
                                    className="ml-auto shrink-0 text-[#7b6fff] font-semibold hover:underline whitespace-nowrap"
                                >
                                    Upgrade →
                                </Link>
                            </div>
                        )}

                    {/* Thinking / operation state */}
                    {(thinking || operationState) && (
                        <div className="flex flex-col gap-2">
                            {operationState ? (
                                <OperationStateIndicator
                                    state={operationState.state}
                                    message={operationState.message}
                                />
                            ) : (
                                <ThinkingIndicator t={t} />
                            )}
                            {slowHint && (
                                <p
                                    className="text-[11px] text-[var(--rico-fg-4)] pl-9 animate-pulse motion-reduce:animate-none"
                                    role="status"
                                >
                                    Rico is waking up — first request after idle can take up to a
                                    minute…
                                </p>
                            )}
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                {/* Floating input bar */}
                <div className="absolute bottom-0 left-0 right-0 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] bg-gradient-to-t from-[var(--rico-bg)] via-[rgba(0,0,0,0.95)] to-transparent">
                    {uploadError && (
                        <p
                            className="text-[11px] text-[var(--rico-error)] mb-2 text-center"
                            role="alert"
                        >
                            {uploadError}
                        </p>
                    )}
                    <div className="flex items-center gap-2">
                        {/* CV upload icon button */}
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={
                                thinking ||
                                chatAudience === "checking" ||
                                BACKEND_MAINTENANCE_MODE
                            }
                            title="Upload your CV (PDF)"
                            aria-label={t("commandUploadCV")}
                            className="w-10 h-10 rounded-[var(--r-xl)] border border-[var(--rico-border-soft)] bg-[rgba(255,255,255,0.03)] text-[var(--rico-fg-3)] flex items-center justify-center hover:border-[var(--rico-primary-container)] hover:text-[var(--rico-fg-1)] transition-all disabled:opacity-30 shrink-0"
                        >
                            <svg
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                            >
                                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                            </svg>
                        </button>

                        {/* Text input */}
                        <div className="relative flex-1">
                            <RicoCommandInput
                                ref={inputRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={
                                    thinking ||
                                    chatAudience === "checking" ||
                                    BACKEND_MAINTENANCE_MODE
                                }
                                placeholder={
                                    BACKEND_MAINTENANCE_MODE
                                        ? t("commandMaintenance")
                                        : chatAudience === "checking"
                                            ? t("commandCheckingSession")
                                            : t("commandDefaultPlaceholder")
                                }
                                aria-label={t("commandMessageRico")}
                                aria-describedby="command-input-hint"
                                className="pr-12"
                            />
                            <button
                                type="button"
                                onClick={handleSend}
                                disabled={
                                    thinking ||
                                    chatAudience === "checking" ||
                                    BACKEND_MAINTENANCE_MODE ||
                                    !input.trim()
                                }
                                aria-label={thinking ? t("commandSending") : t("commandSend")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-[var(--r-lg)] bg-[var(--rico-primary)] text-white flex items-center justify-center hover:bg-[rgba(255,177,200,0.9)] transition-all disabled:opacity-30 disabled:grayscale"
                            >
                                {thinking ? (
                                    <span
                                        className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin motion-reduce:animate-none"
                                        aria-hidden="true"
                                    />
                                ) : (
                                    <svg
                                        width="14"
                                        height="14"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2.5"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        aria-hidden="true"
                                    >
                                        <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                    <p
                        id="command-input-hint"
                        className="text-center text-[10px] text-[var(--rico-fg-4)] mt-2 opacity-40"
                    >
                        Enter to send · Shift+Enter for new line · 📎 to upload CV
                    </p>
                </div>
            </div>
        </div>
    );
}
