"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { RicoChatAction, RicoActionImpact } from "@/lib/schemas";

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
 * Returns true only when the action can be executed in the current context.
 * High-impact and confirmation-required actions are always gated — they must
 * go through the PermissionRequestCard flow, never inline action cards.
 */
function isEnabled(action: RicoChatAction): boolean {
    if (action.impact === "high") return false;
    if (action.requires_confirmation) return false;
    if (action.kind === "navigate") return !!sanitizeHref(action.href);
    if (action.kind === "chat_continue") return true;
    return false;
}

/**
 * Human-readable explanation of why an action card is disabled.
 * Shown as both `title` (hover tooltip) and `aria-label` (screen readers).
 *
 * Kind is checked before impact so that approve/cancel actions always surface
 * the permission-card message regardless of their impact level.
 */
function disabledReason(action: RicoChatAction): string {
    if (action.kind === "approve" || action.kind === "cancel") {
        return "Use the permission card below to approve or cancel";
    }
    if (action.impact === "high") {
        return "High-impact action — approval required via the permission card";
    }
    if (action.requires_confirmation) {
        return "Confirmation required before this action can proceed";
    }
    if (action.kind === "open_drawer") {
        return "Coming soon";
    }
    if (action.kind === "submit") {
        return "Not available yet";
    }
    if (action.kind === "navigate" && !action.href) {
        return "No destination configured";
    }
    return "Not available";
}

const BASE =
    "text-[12px] px-3 py-2 rounded-xl border transition-colors select-none rico-focus-strong";

/** Styling for enabled action cards — medium impact gets a slightly elevated presence. */
function activeClass(impact: RicoActionImpact): string {
    if (impact === "medium") {
        return cn(
            BASE,
            "border-gold/50 bg-gold/5 text-gold hover:bg-gold/15 hover:border-gold/70 cursor-pointer",
        );
    }
    return cn(
        BASE,
        "border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 cursor-pointer",
    );
}

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
                data-impact={action.impact}
                className={activeClass(action.impact)}
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
                data-impact={action.impact}
                onClick={() => onChatContinue(msg)}
                className={activeClass(action.impact)}
            >
                {action.label}
            </button>
        );
    }

    const reason = disabledReason(action);
    return (
        <button
            type="button"
            data-testid="action-card-disabled"
            data-disabled-reason={reason}
            disabled
            title={reason}
            aria-label={`${action.label} — ${reason}`}
            className={INACTIVE}
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
