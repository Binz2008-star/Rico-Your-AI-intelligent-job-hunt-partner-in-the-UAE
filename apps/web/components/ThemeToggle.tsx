"use client";

import { useTheme } from "@/contexts/ThemeContext";

// Accessible dark/light switch. Defaults to dark; choice persisted by ThemeContext.
export function ThemeToggle({ className = "" }: { className?: string }) {
    const { resolvedTheme, setTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    return (
        <button
            type="button"
            onClick={() => setTheme(isDark ? "light" : "dark")}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            className={`flex h-9 w-9 items-center justify-center rounded-lg border border-border-soft bg-surface/60 text-text-secondary transition-all duration-300 hover:border-border-strong hover:text-text-primary hover:scale-105 active:scale-95 rico-focus-strong ${className}`}
        >
            <div className="relative">
                {isDark ? (
                    // Sun — tap to go light
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                        className="transition-all duration-300 rotate-0 scale-100"
                    >
                        <circle cx="12" cy="12" r="4" />
                        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                    </svg>
                ) : (
                    // Moon — tap to go dark
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                        className="transition-all duration-300 rotate-0 scale-100"
                    >
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                    </svg>
                )}
            </div>
        </button>
    );
}
