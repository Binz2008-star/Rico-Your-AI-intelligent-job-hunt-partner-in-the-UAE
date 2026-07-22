"use client";

/**
 * CommandStates — slice 4c of the Atelier full-site migration program.
 *
 * Atelier presentation for the /command *transient / interactive* surfaces
 * that live inside a Rico message row and were explicitly deferred by 4b:
 *
 *   - tool execution states       (agent actions, proposed changes)
 *   - permission request cards
 *   - attachment / CV analysis cards
 *   - loading / thinking / streaming states
 *   - error and retry states
 *
 * DESIGN APPROACH — the same CSS-variable-scope technique 4b introduced for
 * markdown (`AtelierMarkdownScope`). Every design-system colour these cards
 * consume resolves through `rgb(var(--token) / <alpha>)` channels (see
 * tailwind.config.ts), so remapping a handful of channel variables on a
 * wrapper repaints the *unchanged* card components in Atelier ink / paper /
 * sun-red — no card component is edited, so no behaviour, data shape, or
 * markup changes. The wrapper is `display:contents`, so it adds no box and
 * cannot shift layout; children inherit the remapped variables through the
 * DOM tree exactly as before.
 *
 * The remap is derived from the live WorkspaceShell palette
 * (`useWorkspaceTheme`), so it tracks the shell's light/dark Atelier toggle
 * just like 4a/4b. It is applied ONLY on the authenticated Atelier surface;
 * the public/guest surface renders its children verbatim (pre-4c classes),
 * matching 4a/4b.
 *
 * SCOPE BOUNDARY: slice 4d extended the same wrap to the job-match /
 * application / profile-gap cards (see page.tsx render sites). The right
 * rail is slice 4e and keeps the global variables until its own slice.
 */

import React from "react";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { AtelierRicoMark } from "@/components/command/CommandMessages";
import { useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";

/* ── Channel helpers ─────────────────────────────────────────────────────────
 * The token system stores colours as space-separated RGB channels
 * (`R G B`) so Tailwind can apply `/ <alpha-value>` modifiers. Convert the
 * Atelier hex palette into that channel form, compositing the translucent
 * ink tiers onto the paper panel so secondary/muted text stays a solid,
 * alpha-modifiable channel. */

function hexChannels(hex: string): string {
    const h = hex.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return `${r} ${g} ${b}`;
}

function compositeChannels(fgHex: string, bgHex: string, alpha: number): string {
    const f = fgHex.replace("#", "");
    const b = bgHex.replace("#", "");
    const mix = (i: number) => {
        const fc = parseInt(f.slice(i, i + 2), 16);
        const bc = parseInt(b.slice(i, i + 2), 16);
        return Math.round(bc + (fc - bc) * alpha);
    };
    return `${mix(0)} ${mix(2)} ${mix(4)}`;
}

/**
 * The design-system channel variables the 4c cards consume, remapped to the
 * active Atelier palette. Kept intentionally minimal — only the tokens these
 * cards actually reference (surface/overlay/gold/text). Semantic risk hues
 * (amber/red-500 Tailwind literals used by the permission risk badge) are NOT
 * channel-backed and stay meaningful.
 */
export function atelierCardVars(c: WorkspacePalette): React.CSSProperties {
    return {
        "--bg": hexChannels(c.bg),
        "--surface": hexChannels(c.panel),
        "--surface-elevated": hexChannels(c.panel),
        // Ink-tinted hairline/glass channel (dark on paper, light on the dark
        // Atelier panel) — mirrors how `--overlay` flips between the global
        // light/dark themes.
        "--overlay": hexChannels(c.ink),
        // Atelier accent is sun-red; the cards' gold CTAs/borders inherit it.
        "--gold": hexChannels(c.red),
        "--gold-hover": hexChannels(c.red),
        "--text-primary": hexChannels(c.ink),
        "--text-secondary": compositeChannels(c.ink, c.panel, 0.7),
        "--text-muted": compositeChannels(c.ink, c.panel, 0.45),
    } as React.CSSProperties;
}

/**
 * Full-surface channel remap for the PUBLIC /command chrome (artifact design,
 * owner instruction 2026-07-21). Extends the card remap with every remaining
 * channel token the guest surface consumes — text tiers, aura glow, and the
 * Atelier editorial layer (--ink/--paper/--rule/--sun) that the reply CSS
 * reads — so the entire guest page repaints into the artifact palette with
 * zero markup changes. Semantic hues (success/cyan/magenta, emerald status
 * dots, rose logout) intentionally keep their global values.
 */
export function publicCommandArtifactVars(c: WorkspacePalette): React.CSSProperties {
    return {
        ...atelierCardVars(c),
        "--text-tertiary": compositeChannels(c.ink, c.bg, 0.55),
        "--text-disabled": compositeChannels(c.ink, c.bg, 0.35),
        "--aura": hexChannels(c.red),
        "--aura-dim": hexChannels(c.red),
        /* Atelier editorial channels — same derivation CommandObsidianShell
           emits for the authenticated console (palette values are hex). */
        "--ink": hexChannels(c.ink),
        "--ink-soft": hexChannels(c.ink70),
        "--ink-mute": hexChannels(c.ink55),
        "--paper": hexChannels(c.bg),
        "--paper-2": hexChannels(c.panel),
        "--rule": hexChannels(c.hair),
        "--sun": hexChannels(c.red),
        /* Reply/markdown foreground tiers. Global `:root` substitutes
           `--rico-fg-*: rgb(var(--text-*))` ONCE against the dark root and the
           result inherits down as a computed color — so overriding
           `--text-*` here does NOT recolor them. Re-declare the four tiers as
           concrete Atelier-ink colors on the guest wrapper so Rico's prose
           reads as dark ink on paper, not the dark theme's cool grey. */
        "--rico-fg-1": `rgb(${hexChannels(c.ink)})`,
        "--rico-fg-2": `rgb(${compositeChannels(c.ink, c.panel, 0.72)})`,
        "--rico-fg-3": `rgb(${compositeChannels(c.ink, c.bg, 0.55)})`,
        "--rico-fg-4": `rgb(${compositeChannels(c.ink, c.panel, 0.45)})`,
    } as React.CSSProperties;
}

/* ── Card scope ──────────────────────────────────────────────────────────────
 * Layout-transparent wrapper (`display:contents`) that repaints the unchanged
 * card children in Atelier colours on the authenticated surface. */

export function AtelierCardScope({
    authenticated,
    children,
}: {
    authenticated: boolean;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();
    if (!authenticated) return <>{children}</>;
    return (
        <div
            data-testid="atelier-card-scope"
            style={{ display: "contents", ...atelierCardVars(c) }}
        >
            {children}
        </div>
    );
}

/* ── Working / thinking / streaming indicator ────────────────────────────────
 * Atelier variant of the /command "Rico is working" row: the serif "R" mark
 * (4b) + ink label + sun-red typing dots. Reuses the shared `.rico-thinking-*`
 * / `.rico-dots` CSS (the dots read `rgb(var(--gold))`, which the scoped
 * Atelier `--gold` turns sun-red — no new keyframes). Accessibility contract
 * (role="status", aria-live, sr-only label) is identical to the public
 * WorkingIndicator. */

export function AtelierWorkingIndicator({ message }: { message: string }) {
    const c = useWorkspaceTheme();
    return (
        <div
            className="rico-thinking-row"
            style={atelierCardVars(c)}
            role="status"
            aria-live="polite"
            aria-label={message}
            data-testid="atelier-working-indicator"
        >
            <span className="sr-only">{message}</span>
            <AtelierRicoMark size={28} />
            <div
                className="rico-thinking-label"
                style={{ color: c.ink55, fontFamily: ATELIER_FONT.body }}
            >
                <span>{message}</span>
                <span className="rico-dots" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                </span>
            </div>
        </div>
    );
}
