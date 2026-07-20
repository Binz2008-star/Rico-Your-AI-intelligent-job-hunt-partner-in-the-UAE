"use client";

/**
 * RicoPresence — the v5 ambient presence indicator (PR 1, foundation).
 *
 * Pure presentational: no data fetching, no timers, no app-context
 * dependencies. State is a prop; later PRs bind it to real activity
 * (chat streaming, tool runs). Styles live in ./motion.css (`.wsx5-orb`,
 * scoped under a `.wsx5` island) and collapse to a static badge under
 * prefers-reduced-motion.
 *
 * Honest-state rule (trust vocabulary, EVIDENCE.md §2): callers may only
 * set "thinking"/"acting" while something is genuinely in flight — this
 * component never simulates activity on its own.
 */

export type RicoPresenceState = "ready" | "thinking" | "acting" | "completed" | "warning";
export type RicoPresenceSize = "sm" | "md" | "lg";

const DEFAULT_LABEL: Record<RicoPresenceState, string> = {
    ready: "Rico is ready",
    thinking: "Rico is thinking",
    acting: "Rico is working",
    completed: "Rico finished",
    warning: "Rico needs your attention",
};

export function RicoPresence({
    state = "ready",
    size = "md",
    label,
    decorative = false,
    className,
}: {
    state?: RicoPresenceState;
    size?: RicoPresenceSize;
    /** Localized status text for assistive tech; defaults to English. */
    label?: string;
    /** True when a visible text label sits next to the orb (avoids double announcement). */
    decorative?: boolean;
    className?: string;
}) {
    const a11y = decorative
        ? ({ "aria-hidden": true } as const)
        : ({ role: "status", "aria-label": label ?? DEFAULT_LABEL[state] } as const);
    return (
        <span
            className={["wsx5-orb", className].filter(Boolean).join(" ")}
            data-state={state}
            data-size={size}
            {...a11y}
        />
    );
}
