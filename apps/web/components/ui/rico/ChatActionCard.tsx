"use client";

import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import type { WorkspacePalette } from "@/components/workspace/theme";
import type { RicoChatAction, RicoActionImpact } from "@/lib/schemas";

export interface ChatActionsRowProps {
    actions: RicoChatAction[];
    onChatContinue: (message: string) => void;
    onSubmit?: (action: RicoChatAction) => Promise<void>;
    onOpenDrawer?: (action: RicoChatAction) => void;
    disabled?: boolean;
    /** Atelier surface (authenticated /command, slice 4c). Default false =
     *  pre-4c presentation, unchanged. */
    atelier?: boolean;
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
    if (action.kind === "submit") return !!action.endpoint;
    if (action.kind === "open_drawer") return true;
    return false;
}

/**
 * Human-readable explanation of why an action card is disabled.
 * Shown as both `title` (hover tooltip) and `aria-label` (screen readers).
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
    if (action.kind === "submit" && !action.endpoint) {
        return "No endpoint configured for this action";
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

/** Atelier presentation: sun-red accents on paper hairlines (slice 4c).
 *  Hover rules live in the scoped style emitted by ChatActionsRow. */
function presentation(
    impact: RicoActionImpact,
    enabled: boolean,
    atelier: boolean,
    c: WorkspacePalette,
): { className: string; style?: React.CSSProperties } {
    if (!atelier) {
        return { className: enabled ? activeClass(impact) : INACTIVE };
    }
    if (!enabled) {
        return {
            className: cn(BASE, "opacity-50 cursor-not-allowed"),
            style: { borderColor: c.hair, color: c.ink40, fontFamily: ATELIER_FONT.body },
        };
    }
    if (impact === "medium") {
        return {
            className: cn(BASE, "atl4c-action cursor-pointer"),
            style: {
                borderColor: `${c.red}66`,
                background: `${c.red}14`,
                color: c.red,
                fontFamily: ATELIER_FONT.body,
            },
        };
    }
    return {
        className: cn(BASE, "atl4c-action cursor-pointer"),
        style: { borderColor: c.hair, color: c.ink55, fontFamily: ATELIER_FONT.body },
    };
}

function ChatActionCard({
    action,
    onChatContinue,
    onSubmit,
    onOpenDrawer,
    disabled = false,
    atelier = false,
}: {
    action: RicoChatAction;
    onChatContinue: (message: string) => void;
    onSubmit?: (action: RicoChatAction) => Promise<void>;
    onOpenDrawer?: (action: RicoChatAction) => void;
    disabled?: boolean;
    atelier?: boolean;
}) {
    const c = useWorkspaceTheme();
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const enabled = !disabled && isEnabled(action);
    const active = presentation(action.impact, true, atelier, c);

    if (action.kind === "navigate" && enabled) {
        const href = sanitizeHref(action.href)!;
        const isExternal = href.startsWith("http");
        return (
            <Link
                href={href}
                {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                data-testid="action-card-navigate"
                data-impact={action.impact}
                className={active.className}
                style={active.style}
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
                className={active.className}
                style={active.style}
            >
                {action.label}
            </button>
        );
    }

    if (action.kind === "submit" && enabled && onSubmit) {
        async function handleSubmit() {
            if (submitting) return;
            setSubmitting(true);
            setSubmitError(null);
            try {
                await onSubmit!(action);
            } catch (err) {
                setSubmitError(
                    err instanceof Error ? err.message : "Something went wrong.",
                );
            } finally {
                setSubmitting(false);
            }
        }
        return (
            <span className="flex flex-col gap-1">
                <button
                    type="button"
                    data-testid="action-card-submit"
                    data-impact={action.impact}
                    onClick={handleSubmit}
                    disabled={submitting}
                    className={cn(active.className, submitting && "opacity-70 cursor-wait")}
                    style={active.style}
                >
                    {submitting ? "Saving…" : action.label}
                </button>
                {submitError && (
                    <span className="text-[11px] text-red-400 px-1">{submitError}</span>
                )}
            </span>
        );
    }

    if (action.kind === "open_drawer" && enabled && onOpenDrawer) {
        return (
            <button
                type="button"
                data-testid="action-card-open-drawer"
                data-impact={action.impact}
                onClick={() => onOpenDrawer(action)}
                className={active.className}
                style={active.style}
            >
                {action.label}
            </button>
        );
    }

    const reason = disabledReason(action);
    const inactive = presentation(action.impact, false, atelier, c);
    return (
        <button
            type="button"
            data-testid="action-card-disabled"
            data-disabled-reason={reason}
            disabled
            title={reason}
            aria-label={`${action.label} — ${reason}`}
            className={inactive.className}
            style={inactive.style}
        >
            {action.label}
        </button>
    );
}

export function ChatActionsRow({
    actions,
    onChatContinue,
    onSubmit,
    onOpenDrawer,
    disabled = false,
    atelier = false,
}: ChatActionsRowProps) {
    const c = useWorkspaceTheme();
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
                    onSubmit={onSubmit}
                    onOpenDrawer={onOpenDrawer}
                    disabled={disabled}
                    atelier={atelier}
                />
            ))}
            {atelier && (
                <style dangerouslySetInnerHTML={{ __html: `
                    .atl4c-action:hover {
                        border-color: ${c.red} !important;
                        color: ${c.red} !important;
                        background: ${c.red}1F !important;
                    }
                ` }} />
            )}
        </div>
    );
}
