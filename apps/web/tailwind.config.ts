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
                // Atelier V3 "Obsidian" token system
                // All colors resolve through CSS custom properties for light/dark theming
                background: "rgb(var(--background) / <alpha-value>)",
                foreground: "rgb(var(--foreground) / <alpha-value>)",

                // Canvas and surfaces
                paper: "rgb(var(--paper) / <alpha-value>)",
                "paper-2": "rgb(var(--paper-2) / <alpha-value>)",
                card: "rgb(var(--card) / <alpha-value>)",
                popover: "rgb(var(--popover) / <alpha-value>)",

                // Text hierarchy
                ink: "rgb(var(--ink) / <alpha-value>)",
                "ink-soft": "rgb(var(--ink-soft) / <alpha-value>)",
                "ink-mute": "rgb(var(--ink-mute) / <alpha-value>)",
                rule: "rgb(var(--rule) / <alpha-value>)",

                // Accent — acid-lime signal
                sun: "rgb(var(--sun) / <alpha-value>)",
                "sun-soft": "rgb(var(--sun-soft) / <alpha-value>)",

                // Semantic mappings
                primary: "rgb(var(--primary) / <alpha-value>)",
                "primary-foreground": "rgb(var(--primary-foreground) / <alpha-value>)",
                secondary: "rgb(var(--secondary) / <alpha-value>)",
                "secondary-foreground": "rgb(var(--secondary-foreground) / <alpha-value>)",
                muted: "rgb(var(--muted) / <alpha-value>)",
                "muted-foreground": "rgb(var(--muted-foreground) / <alpha-value>)",
                accent: "rgb(var(--accent) / <alpha-value>)",
                "accent-foreground": "rgb(var(--accent-foreground) / <alpha-value>)",
                destructive: "rgb(var(--destructive) / <alpha-value>)",
                "destructive-foreground": "rgb(var(--destructive-foreground) / <alpha-value>)",
                border: "rgb(var(--border) / <alpha-value>)",
                input: "rgb(var(--input) / <alpha-value>)",
                ring: "rgb(var(--ring) / <alpha-value>)",

                // Sidebar tokens
                sidebar: "rgb(var(--sidebar) / <alpha-value>)",
                "sidebar-foreground": "rgb(var(--sidebar-foreground) / <alpha-value>)",
                "sidebar-primary": "rgb(var(--sidebar-primary) / <alpha-value>)",
                "sidebar-primary-foreground": "rgb(var(--sidebar-primary-foreground) / <alpha-value>)",
                "sidebar-accent": "rgb(var(--sidebar-accent) / <alpha-value>)",
                "sidebar-accent-foreground": "rgb(var(--sidebar-accent-foreground) / <alpha-value>)",
                "sidebar-border": "rgb(var(--sidebar-border) / <alpha-value>)",
                "sidebar-ring": "rgb(var(--sidebar-ring) / <alpha-value>)",

                // Chart colors
                "chart-1": "rgb(var(--chart-1) / <alpha-value>)",
                "chart-2": "rgb(var(--chart-2) / <alpha-value>)",
                "chart-3": "rgb(var(--chart-3) / <alpha-value>)",
                "chart-4": "rgb(var(--chart-4) / <alpha-value>)",
                "chart-5": "rgb(var(--chart-5) / <alpha-value>)",
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
                // Atelier V3: Space Grotesk (display) + Inter (body) + JetBrains Mono (meta) + Fraunces (editorial)
                display: ["var(--font-display)", "sans-serif"],
                sans: ["var(--font-sans)", "system-ui", "sans-serif"],
                body: ["var(--font-sans)", "system-ui", "sans-serif"],
                mono: ["var(--font-mono)", "ui-monospace", "monospace"],
                editorial: ["var(--font-editorial)", "serif"],
                // Arabic fonts
                "display-ar": ["var(--font-display-ar)", "serif"],
                "sans-ar": ["var(--font-sans-ar)", "system-ui", "sans-serif"],
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
