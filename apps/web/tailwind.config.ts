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
                // Rico AI Cinematic Design System v3
                // Primary: Gold/Amber — premium AI product
                // Secondary: Magenta — energy + action
                // Tertiary: Cyan — data + intelligence

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

                // Gradient System
                gradient: {
                    gold: "linear-gradient(135deg, #f5a623 0%, #fbbf24 100%)",
                    magenta: "linear-gradient(135deg, #ff2d8e 0%, #ff1a5c 100%)",
                    cyan: "linear-gradient(135deg, #00e5ff 0%, #00b8cc 100%)",
                    duo: "linear-gradient(135deg, #f5a623 0%, #ff2d8e 100%)",
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
                    // Secondary accent → magenta
                    magenta: "rgb(var(--magenta) / <alpha-value>)",
                    "magenta-muted": "rgb(var(--magenta) / 0.10)",
                    text: "rgb(var(--text-primary) / <alpha-value>)",
                    "text-muted": "rgb(var(--text-secondary) / <alpha-value>)",
                    "text-dim": "rgb(var(--text-tertiary) / <alpha-value>)",
                    purple: "rgb(var(--magenta) / <alpha-value>)",
                    teal: "rgb(var(--cyan) / <alpha-value>)",
                    red: "#ff5e5b",
                    // Gold aliases
                    amber: "rgb(var(--gold) / <alpha-value>)",
                    gold: "rgb(var(--gold) / <alpha-value>)",
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
                DEFAULT: "0.25rem",
                lg: "0.5rem",
                xl: "0.75rem",
                full: "9999px",
                // Nocturne radii
                rico: "14px",
                "rico-lg": "22px",
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
                float: "float 14s ease-in-out infinite",
                "float-delayed": "float 16s ease-in-out infinite -4s",
                "pulse-gold": "pulse-gold 8s ease-in-out infinite",
                "pulse-magenta": "pulse-magenta 10s ease-in-out infinite",
                "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                thinking: "thinking 3s ease-in-out infinite",
                shimmer: "shimmer 1.8s ease-in-out infinite",
                "fade-up": "fadeUp 0.4s ease-out forwards",
                // Nocturne Aura animations
                breathe: "breathe 5.5s cubic-bezier(0.22, 0.61, 0.36, 1) infinite",
                "pulse-ring": "pulse-ring 5.5s cubic-bezier(0.22, 0.61, 0.36, 1) infinite",
            },
            keyframes: {
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
                // Nocturne Aura keyframes
                breathe: {
                    "0%, 100%": { transform: "scale(1)", opacity: "0.92" },
                    "50%": { transform: "scale(1.08)", opacity: "1" },
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
