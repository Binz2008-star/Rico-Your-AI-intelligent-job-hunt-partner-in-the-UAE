"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { RicoChatAction } from "@/lib/schemas";

export interface ChatActionsRowProps {
    actions: RicoChatAction[];
    onChatContinue: (message: string) => void;
    disabled?: boolean;
}

/** Only allow internal paths and safe external URLs — blocks javascript: and data: URIs. */
function sanitizeHref(href: string | null | undefined): string | null {
    if (!href) return null;
    if (href.startsWith("/") || href.startsWith("https://") || href.startsWith("http://")) {
        return href;
    }
    return null;
}

/**
 * True only when the action can execute in this PR.
 * High-impact or confirmation-required actions are blocked regardless of kind.
 */
function isEnabled(action: RicoChatAction): boolean {
    if (action.impact === "high" || action.requires_confirmation) return false;
    if (action.kind === "navigate") return !!sanitizeHref(action.href);
    if (action.kind === "chat_continue") return true;
    return false; // open_drawer, submit, approve, cancel, unknown kinds
}

const BASE =
    "text-[12px] px-3 py-2 rounded-xl border transition-colors select-none rico-focus-strong";
const ACTIVE = cn(
    BASE,
    "border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 cursor-pointer",
);
const INACTIVE = cn(BASE, "border-border-soft text-text-muted opacity-50 cursor-not-allowed");

function ChatActionCard({
    action,
    onChatContinue,
    disabled = false,
}: {
    action: RicoChatAction;
    onChatContinue: (message: string) => void;
    disabled?: boolean;
}) {
    const enabled = !disabled && isEnabled(action);

    if (action.kind === "navigate" && enabled) {
        const href = sanitizeHref(action.href)!;
        const isExternal = href.startsWith("http");
        return (
            <Link
                href={href}
                {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                data-testid="action-card-navigate"
                className={ACTIVE}
            >
                {action.label}
            </Link>
        );
    }

    if (action.kind === "chat_continue" && enabled) {
        const msg =
            (action.payload as Record<string, string>)?.message ?? action.label;
        return (
            <button
                type="button"
                data-testid="action-card-chat-continue"
                onClick={() => onChatContinue(msg)}
                className={ACTIVE}
            >
                {action.label}
            </button>
        );
    }

    return (
        <button
            type="button"
            data-testid="action-card-disabled"
            disabled
            className={INACTIVE}
            title={action.kind === "open_drawer" ? "Coming soon" : undefined}
        >
            {action.label}
        </button>
    );
}

export function ChatActionsRow({
    actions,
    onChatContinue,
    disabled = false,
}: ChatActionsRowProps) {
    if (!actions.length) return null;
    return (
        <div
            className="flex flex-wrap gap-2 mt-2"
            data-testid="chat-actions-row"
            role="group"
            aria-label="Suggested actions"
        >
            {actions.map((action) => (
                <ChatActionCard
                    key={action.id}
                    action={action}
                    onChatContinue={onChatContinue}
                    disabled={disabled}
                />
            ))}
        </div>
    );
}
