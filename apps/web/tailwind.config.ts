import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: "class",
    content: [
        "./app/**/*.{ts,tsx}",
        "./components/**/*.{ts,tsx}",
        "./lib/**/*.{ts,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // ── Atelier editorial token layer (route-scoped to /command) ──
                // Backed by CSS custom properties the CommandObsidianShell sets
                // from its JS WorkspacePalette (channels: "r g b"), so light /
                // "Atelier at Night" both resolve automatically and Tailwind's
                // `/<alpha>` modifier works (e.g. from-ink/50, via-ink/20).
                // Only consumed by the /command reply surface (RicoReply /
                // RicoUserBubble / RicoThinking); no other route defines these vars.
                ink: "rgb(var(--ink) / <alpha-value>)",
                "ink-soft": "rgb(var(--ink-soft) / <alpha-value>)",
                "ink-mute": "rgb(var(--ink-mute) / <alpha-value>)",
                paper: "rgb(var(--paper) / <alpha-value>)",
                "paper-2": "rgb(var(--paper-2) / <alpha-value>)",
                rule: "rgb(var(--rule) / <alpha-value>)",
                sun: "rgb(var(--sun) / <alpha-value>)",

                // Rico AI Design System v4 — Premium UAE Career
                // Primary:   Gold/Amber  — brand, CTAs
                // Secondary: Indigo      — actions, interactive (professional)
                // Tertiary:  Sky Blue    — data, links
                // Success:   Emerald     — confirmed, applied, live

                // Rico Site v3 token system — all semantic colors resolve through
                // CSS variables (channels) so they switch with the .light theme and
                // still support Tailwind alpha modifiers via `/ <alpha-value>`.

                // Global Canvas
                background: "rgb(var(--bg) / <alpha-value>)",
                // Nocturne aliases — `void` is the canvas, `overlay` the translucent
                // white/dark channel used for hairline borders + glass fills.
                void: "rgb(var(--bg) / <alpha-value>)",
                overlay: "rgb(var(--overlay) / <alpha-value>)",
                surface: {
                    DEFAULT: "rgb(var(--surface) / <alpha-value>)",
                    elevated: "rgb(var(--surface-elevated) / <alpha-value>)",
                    subtle: "rgb(var(--overlay) / 0.02)",
                    glass: "rgb(var(--overlay) / 0.04)",
                },

                // Primary System - Gold/Amber
                gold: {
                    DEFAULT: "rgb(var(--gold) / <alpha-value>)",
                    hover: "rgb(var(--gold-hover) / <alpha-value>)",
                    glow: "rgb(var(--gold) / 0.25)",
                    soft: "rgb(var(--gold) / 0.10)",
                    muted: "rgb(var(--gold) / 0.15)",
                    dim: "rgb(var(--gold) / 0.05)",
                    border: "rgb(var(--gold) / 0.35)",
                },

                // Secondary System - Magenta
                magenta: {
                    DEFAULT: "rgb(var(--magenta) / <alpha-value>)",
                    glow: "rgb(var(--magenta) / 0.3)",
                    soft: "rgb(var(--magenta) / 0.1)",
                    dim: "rgb(var(--magenta) / 0.05)",
                    hover: "rgb(var(--magenta-hover) / <alpha-value>)",
                },

                // Tertiary System - Cyan
                cyan: {
                    DEFAULT: "rgb(var(--cyan) / <alpha-value>)",
                    glow: "rgb(var(--cyan) / 0.3)",
                    soft: "rgb(var(--cyan) / 0.1)",
                    dim: "rgb(var(--cyan) / 0.05)",
                    hover: "rgb(var(--cyan-hover) / <alpha-value>)",
                },

                // Nocturne — Ember (Rico's voice). Aliases the --gold token for semantic reads.
                ember: {
                    DEFAULT: "rgb(var(--gold) / <alpha-value>)",
                    bright: "rgb(var(--gold-hover) / <alpha-value>)",
                    glow: "rgb(var(--gold) / 0.25)",
                    soft: "rgb(var(--gold) / 0.10)",
                    border: "rgb(var(--gold) / 0.35)",
                },

                // Nocturne — Aura (intelligence / data only). Teal on dark, AA-darkened on light.
                aura: {
                    DEFAULT: "rgb(var(--aura) / <alpha-value>)",
                    dim: "rgb(var(--aura-dim) / <alpha-value>)",
                    glow: "rgb(var(--aura) / 0.25)",
                    soft: "rgb(var(--aura) / 0.10)",
                    border: "rgb(var(--aura) / 0.40)",
                },

                // Success System — Emerald
                success: {
                    DEFAULT: "rgb(var(--success) / <alpha-value>)",
                    hover: "rgb(var(--success-hover) / <alpha-value>)",
                    soft: "rgb(var(--success) / 0.10)",
                    border: "rgb(var(--success) / 0.30)",
                    glow: "rgb(var(--success) / 0.20)",
                },

                // Gradient System
                gradient: {
                    gold: "linear-gradient(135deg, #f0a94a 0%, #fbbf24 100%)",
                    magenta: "linear-gradient(135deg, #818cf8 0%, #6366f1 100%)",
                    cyan: "linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)",
                    duo: "linear-gradient(135deg, #f0a94a 0%, #818cf8 100%)",
                    subtle: "linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%)",
                },

                // Text System
                text: {
                    primary: "rgb(var(--text-primary) / <alpha-value>)",
                    secondary: "rgb(var(--text-secondary) / <alpha-value>)",
                    tertiary: "rgb(var(--text-tertiary) / <alpha-value>)",
                    muted: "rgb(var(--text-muted) / <alpha-value>)",
                    disabled: "rgb(var(--text-disabled) / <alpha-value>)",
                },

                // Border System (overlay channel + fixed alphas)
                border: {
                    subtle: "rgb(var(--overlay) / 0.06)",
                    soft: "rgb(var(--overlay) / 0.1)",
                    medium: "rgb(var(--overlay) / 0.16)",
                    strong: "rgb(var(--overlay) / 0.24)",
                    gradient: "linear-gradient(135deg, rgba(255,45,142,0.5) 0%, rgba(0,229,255,0.5) 100%)",
                },

                // Legacy compatibility layer — now token-backed so it themes too.
                "surface-container": "rgb(var(--surface) / <alpha-value>)",
                "surface-variant": "rgb(var(--surface-elevated) / <alpha-value>)",
                primary: "rgb(var(--text-primary) / <alpha-value>)",
                secondary: "rgb(var(--cyan) / <alpha-value>)",
                error: "#ff5e5b",
                outline: "rgb(var(--overlay) / 0.1)",
                rico: {
                    bg: "rgb(var(--bg) / <alpha-value>)",
                    surface: "rgb(var(--surface) / <alpha-value>)",
                    "surface-2": "rgb(var(--surface-elevated) / <alpha-value>)",
                    border: "rgb(var(--overlay) / 0.06)",
                    // Primary accent → gold
                    accent: "rgb(var(--gold) / <alpha-value>)",
                    "accent-hover": "rgb(var(--gold-hover) / <alpha-value>)",
                    "accent-muted": "rgb(var(--gold) / 0.10)",
                    "accent-border": "rgb(var(--gold) / 0.35)",
                    "accent-glow": "rgb(var(--gold) / 0.20)",
                    // Secondary accent → indigo (was magenta)
                    magenta: "rgb(var(--magenta) / <alpha-value>)",
                    "magenta-muted": "rgb(var(--magenta) / 0.10)",
                    text: "rgb(var(--text-primary) / <alpha-value>)",
                    "text-muted": "rgb(var(--text-secondary) / <alpha-value>)",
                    "text-dim": "rgb(var(--text-tertiary) / <alpha-value>)",
                    purple: "rgb(var(--magenta) / <alpha-value>)",
                    teal: "rgb(var(--cyan) / <alpha-value>)",
                    red: "#f87171",
                    // Gold aliases
                    amber: "rgb(var(--gold) / <alpha-value>)",
                    gold: "rgb(var(--gold) / <alpha-value>)",
                    // Success alias
                    success: "rgb(var(--success) / <alpha-value>)",
                    "success-muted": "rgb(var(--success) / 0.10)",
                },
            },
            // Nocturne hairline alpha stops — Tailwind's `/N` color-alpha modifier only
            // resolves values present in the opacity scale, and the reference uses
            // off-scale stops (e.g. overlay/7 hairlines, ember/13 bubble fill).
            opacity: {
                7: "0.07",
                12: "0.12",
                13: "0.13",
                16: "0.16",
            },
            borderRadius: {
                DEFAULT: "0.375rem",
                lg: "0.625rem",
                xl: "0.875rem",
                "2xl": "1.125rem",
                full: "9999px",
                // Rico card radii — slightly more rounded for premium feel
                rico: "16px",
                "rico-lg": "24px",
            },
            spacing: {
                unit: "8px",
                gutter: "32px",
                "section-gap": "128px",
                "container-max": "1440px",
                "safe-area": "48px",
                "container-padding-mobile": "24px",
                "container-padding-desktop": "120px",
            },
            fontFamily: {
                // Nocturne: Space Grotesk (display/headline) + Inter (body/sans) + IBM Plex Mono
                display: ["var(--font-display)", "var(--font-body)", "sans-serif"],
                headline: ["var(--font-display)", "var(--font-body)", "sans-serif"],
                sans: ["var(--font-body)", "system-ui", "sans-serif"],
                body: ["var(--font-body)", "system-ui", "sans-serif"],
                mono: ["var(--font-mono)", "ui-monospace", "monospace"],
            },
            fontSize: {
                "display-lg": ["80px", { lineHeight: "1.1", letterSpacing: "-0.04em", fontWeight: "700" }],
                "display-lg-mobile": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
                "headline-xl": ["48px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "600" }],
                "headline-lg": ["32px", { lineHeight: "1.3", fontWeight: "500" }],
                "headline-md": ["32px", { lineHeight: "1.3", fontWeight: "500" }],
                "body-lg": ["18px", { lineHeight: "1.6", letterSpacing: "0.02em", fontWeight: "300" }],
                "body-md": ["16px", { lineHeight: "1.6", letterSpacing: "0.01em", fontWeight: "300" }],
                "label-caps": ["12px", { lineHeight: "1.0", letterSpacing: "0.15em", fontWeight: "400" }],
            },
            animation: {
                // Atelier editorial blink caret (step-end so it snaps, not fades)
                caret: "caret 1s step-end infinite",
                float: "float 14s ease-in-out infinite",
                "float-delayed": "float 16s ease-in-out infinite -4s",
                "pulse-gold": "pulse-gold 8s ease-in-out infinite",
                "pulse-magenta": "pulse-magenta 10s ease-in-out infinite",
                "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                thinking: "thinking 3s ease-in-out infinite",
                shimmer: "shimmer 1.8s ease-in-out infinite",
                "fade-up": "fadeUp 0.4s ease-out forwards",
                // Command reply-experience motion layer (2026-07-17):
                // entrance/reveal micro-interactions for the chat surface.
                "fade-in-scale": "fadeInScale 0.18s ease-out both",
                "pop-in": "popIn 0.32s cubic-bezier(0.34, 1.56, 0.64, 1) both",
                "dot-cascade": "dotCascade 1.15s ease-in-out infinite",
                "rail-draw": "railDraw 0.45s ease-out both",
                "stage-in": "stageIn 0.28s cubic-bezier(0.23, 1, 0.32, 1) both",
                // Nocturne Aura animations
                breathe: "breathe 5.5s cubic-bezier(0.22, 0.61, 0.36, 1) infinite",
                "pulse-ring": "pulse-ring 5.5s cubic-bezier(0.22, 0.61, 0.36, 1) infinite",
                "glow-pulse": "glow-pulse 6s ease-in-out infinite",
                drift: "drift 9s ease-in-out infinite",
                "ring-reveal": "ring-reveal 1.1s cubic-bezier(0.22, 0.61, 0.36, 1) 0.15s backwards",
            },
            keyframes: {
                caret: {
                    "0%,49%": { opacity: "1" },
                    "50%,100%": { opacity: "0" },
                },
                float: {
                    "0%, 100%": { transform: "translateY(0px) rotate(0deg)" },
                    "50%": { transform: "translateY(-30px) rotate(0.8deg)" },
                },
                "pulse-gold": {
                    "0%, 100%": { opacity: "0.25", filter: "blur(120px)" },
                    "50%": { opacity: "0.55", filter: "blur(160px)" },
                },
                "pulse-magenta": {
                    "0%, 100%": { opacity: "0.3", filter: "blur(140px)" },
                    "50%": { opacity: "0.7", filter: "blur(180px)" },
                },
                thinking: {
                    "0%, 100%": { opacity: "0.15", transform: "scale(1)" },
                    "50%": { opacity: "0.25", transform: "scale(1.05)" },
                },
                shimmer: {
                    "0%": { backgroundPosition: "-200% 0" },
                    "100%": { backgroundPosition: "200% 0" },
                },
                fadeUp: {
                    "0%": { opacity: "0", transform: "translateY(6px)" },
                    "100%": { opacity: "1", transform: "translateY(0)" },
                },
                // Command reply-experience motion layer (2026-07-17)
                fadeInScale: {
                    "0%": { opacity: "0", transform: "scale(0.96)" },
                    "100%": { opacity: "1", transform: "scale(1)" },
                },
                popIn: {
                    "0%": { opacity: "0", transform: "scale(0.85)" },
                    "100%": { opacity: "1", transform: "scale(1)" },
                },
                dotCascade: {
                    "0%, 60%, 100%": { transform: "translateY(0)", opacity: "0.35" },
                    "30%": { transform: "translateY(-3px)", opacity: "1" },
                },
                railDraw: {
                    "0%": { transform: "scaleY(0)", transformOrigin: "top" },
                    "100%": { transform: "scaleY(1)", transformOrigin: "top" },
                },
                // Thinking-stage crossfade: blur bridges the old/new label swap
                // so it reads as one evolving thought, not two strings replacing.
                stageIn: {
                    "0%": { opacity: "0", filter: "blur(3px)", transform: "translateY(3px)" },
                    "100%": { opacity: "1", filter: "blur(0)", transform: "translateY(0)" },
                },
                // Nocturne Aura keyframes
                breathe: {
                    "0%, 100%": { transform: "scale(1)", opacity: "0.92" },
                    "50%": { transform: "scale(1.08)", opacity: "1" },
                },
                // Logo halo — opacity only so the badge never moves
                "glow-pulse": {
                    "0%, 100%": { opacity: "0.35" },
                    "50%": { opacity: "0.7" },
                },
                // Hero card float — 3px max so text stays readable
                drift: {
                    "0%, 100%": { transform: "translateY(0)" },
                    "50%": { transform: "translateY(-3px)" },
                },
                // FitRing one-shot draw-in; --ring-c = per-instance circumference,
                // animates to the element's own stroke-dashoffset (no `to` frame)
                "ring-reveal": {
                    from: { strokeDashoffset: "var(--ring-c)" },
                },
                "pulse-ring": {
                    "0%, 100%": { transform: "scale(0.96)", opacity: "0.7" },
                    "50%": { transform: "scale(1.06)", opacity: "0.25" },
                },
            },
            backdropBlur: {
                xs: "2px",
            },
        },
    },
    plugins: [],
};

export default config;
