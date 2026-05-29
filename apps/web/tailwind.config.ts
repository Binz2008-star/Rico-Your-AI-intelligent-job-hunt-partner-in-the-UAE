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
                // Rico AI Cinematic Design System v2
                // Based on DESIGN.md spec: pure black + magenta + cyan

                // Rico Site v2 token system — all semantic colors resolve through
                // CSS variables (channels) so they switch with the .light theme and
                // still support Tailwind alpha modifiers via `/ <alpha-value>`.

                // Global Canvas
                background: "rgb(var(--bg) / <alpha-value>)",
                surface: {
                    DEFAULT: "rgb(var(--surface) / <alpha-value>)",
                    elevated: "rgb(var(--surface-elevated) / <alpha-value>)",
                    subtle: "rgb(var(--overlay) / 0.02)",
                    glass: "rgb(var(--overlay) / 0.04)",
                },

                // Primary System - Magenta
                magenta: {
                    DEFAULT: "rgb(var(--magenta) / <alpha-value>)",
                    glow: "rgb(var(--magenta) / 0.3)",
                    soft: "rgb(var(--magenta) / 0.1)",
                    dim: "rgb(var(--magenta) / 0.05)",
                    hover: "rgb(var(--magenta-hover) / <alpha-value>)",
                },

                // Secondary System - Cyan
                cyan: {
                    DEFAULT: "rgb(var(--cyan) / <alpha-value>)",
                    glow: "rgb(var(--cyan) / 0.3)",
                    soft: "rgb(var(--cyan) / 0.1)",
                    dim: "rgb(var(--cyan) / 0.05)",
                    hover: "rgb(var(--cyan-hover) / <alpha-value>)",
                },

                // Gradient System (kept as literal gradients; accent endpoints fixed)
                gradient: {
                    magenta: "linear-gradient(135deg, #ff2d8e 0%, #ff1a5c 100%)",
                    cyan: "linear-gradient(135deg, #00e5ff 0%, #00b8cc 100%)",
                    duo: "linear-gradient(135deg, #ff2d8e 0%, #00e5ff 100%)",
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
                    accent: "rgb(var(--magenta) / <alpha-value>)",
                    "accent-hover": "rgb(var(--magenta-hover) / <alpha-value>)",
                    "accent-muted": "rgb(var(--magenta) / 0.1)",
                    "accent-border": "rgb(var(--magenta) / 0.4)",
                    "accent-glow": "rgb(var(--magenta) / 0.2)",
                    text: "rgb(var(--text-primary) / <alpha-value>)",
                    "text-muted": "rgb(var(--text-secondary) / <alpha-value>)",
                    "text-dim": "rgb(var(--text-tertiary) / <alpha-value>)",
                    purple: "rgb(var(--magenta) / <alpha-value>)",
                    teal: "rgb(var(--cyan) / <alpha-value>)",
                    red: "#ff5e5b",
                    amber: "#f5a623",
                },
            },
            borderRadius: {
                DEFAULT: "0.25rem",
                lg: "0.5rem",
                xl: "0.75rem",
                full: "9999px",
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
                // DESIGN.md spec: IBM Plex Sans Variable + Sora
                display: ["var(--font-ibm-plex-sans)", "var(--font-sora)", "sans-serif"],
                headline: ["var(--font-ibm-plex-sans)", "var(--font-sora)", "sans-serif"],
                body: ["var(--font-ibm-plex-sans)", "system-ui", "sans-serif"],
                mono: ["var(--font-space-mono)", "monospace"],
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
                "pulse-magenta": "pulse-magenta 10s ease-in-out infinite",
                "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                thinking: "thinking 3s ease-in-out infinite",
            },
            keyframes: {
                float: {
                    "0%, 100%": { transform: "translateY(0px) rotate(0deg)" },
                    "50%": { transform: "translateY(-30px) rotate(0.8deg)" },
                },
                "pulse-magenta": {
                    "0%, 100%": { opacity: "0.3", filter: "blur(140px)" },
                    "50%": { opacity: "0.7", filter: "blur(180px)" },
                },
                thinking: {
                    "0%, 100%": { opacity: "0.15", transform: "scale(1)" },
                    "50%": { opacity: "0.25", transform: "scale(1.05)" },
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
