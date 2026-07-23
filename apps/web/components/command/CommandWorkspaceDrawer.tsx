"use client";

/**
 * CommandWorkspaceDrawer — TASK-20260723-002.
 *
 * A small, dedicated, content-agnostic accessible drawer for the /command
 * medium-workspace tiers (768–1199px): opens Sessions or Career-context real
 * content that no longer fits as an inline rail at these widths.
 *
 * Built new rather than extracted from MobileCommandHeader's existing
 * hamburger drawer — that primitive is tightly coupled to its own nav-item
 * list and mobile-only call site; a clean extraction risked destabilizing
 * mobile nav for a gain that a small, purpose-built dialog achieves more
 * safely. MobileCommandHeader itself is untouched by this task.
 *
 * Accessibility contract (matches the plan exactly):
 *  - role="dialog", aria-modal="true", aria-labelledby the visible heading
 *  - focus moves into the panel on open (the panel itself, tabIndex={-1})
 *  - Escape closes it
 *  - backdrop click closes it
 *  - the explicit close button closes it
 *  - focus returns to the trigger element on close
 *  - motion-reduce respected (entrance animation only; no motion when
 *    prefers-reduced-motion is set)
 *
 * Positioning uses Tailwind's logical `start-0`/`end-0` (inset-inline-*), so
 * RTL mirroring is automatic — no isRTL branching for placement. The
 * entrance is a fade/scale (an existing, already-shipped, already
 * reduced-motion-safe utility: `animate-fade-in-scale
 * motion-reduce:animate-none`, the same one CommandObsidianShell's account
 * menu already uses) rather than a directional slide — simpler, and the
 * "opens from the correct logical side" requirement is satisfied by the
 * anchored position itself, not by which direction it animates in from.
 */

import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useEffect, useRef } from "react";

export function CommandWorkspaceDrawer({
    open,
    onClose,
    titleId,
    title,
    side,
    triggerRef,
    testId,
    children,
}: {
    open: boolean;
    onClose: () => void;
    /** id placed on the visible heading; referenced by aria-labelledby. */
    titleId: string;
    title: string;
    /** Logical anchor edge — "start" for Sessions, "end" for Career context. */
    side: "start" | "end";
    /** The button that opened this drawer — focus returns here on close. */
    triggerRef: React.RefObject<HTMLElement | null>;
    testId: string;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const isAr = language === "ar";
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        // Move focus into the dialog on open (WAI-ARIA dialog pattern).
        panelRef.current?.focus();
        function handleKey(e: KeyboardEvent) {
            if (e.key === "Escape") onClose();
        }
        document.addEventListener("keydown", handleKey);
        return () => {
            document.removeEventListener("keydown", handleKey);
        };
    }, [open, onClose]);

    // Focus-return: fires once, on the transition from open -> closed, not on
    // every unrelated re-render (the effect above intentionally does not
    // depend on triggerRef, since a ref's identity is stable across renders
    // and re-focusing on every keystroke inside the drawer would be wrong).
    const wasOpen = useRef(false);
    useEffect(() => {
        if (open) {
            wasOpen.current = true;
        } else if (wasOpen.current) {
            wasOpen.current = false;
            triggerRef.current?.focus();
        }
    }, [open, triggerRef]);

    if (!open) return null;

    return (
        <>
            <div
                aria-hidden="true"
                data-testid={`${testId}-backdrop`}
                className="fixed inset-0 z-40 animate-fade-in motion-reduce:animate-none"
                style={{ background: "rgba(20,17,13,0.35)" }}
                onClick={onClose}
            />
            <div
                ref={panelRef}
                id={testId}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                tabIndex={-1}
                data-testid={testId}
                className={`fixed inset-y-0 z-50 flex w-[300px] max-w-[86vw] flex-col outline-none animate-fade-in-scale motion-reduce:animate-none ${side === "start" ? "start-0" : "end-0"}`}
                style={{ background: c.panel, boxShadow: "0 8px 32px rgba(20,17,13,0.24)" }}
            >
                <div
                    className="flex shrink-0 items-center justify-between px-4 py-3"
                    style={{ borderBottom: `1px solid ${c.hair}` }}
                >
                    <h2 id={titleId} className="text-[13px] font-semibold" style={{ color: c.ink }}>
                        {title}
                    </h2>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label={isAr ? "إغلاق" : "Close"}
                        data-testid={`${testId}-close`}
                        className="obs-ghost rounded-md p-1.5"
                        style={{ color: c.ink70, background: "transparent", border: "none", cursor: "pointer" }}
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
            </div>
        </>
    );
}
