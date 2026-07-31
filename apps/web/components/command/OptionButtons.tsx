"use client";

import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import type { RicoOption } from "@/lib/api";

export interface OptionButtonsProps {
    options: RicoOption[];
    onAction: (prompt: string) => void;
}

export function OptionButtons({ options, onAction }: OptionButtonsProps) {
    const { language } = useLanguage();
    const c = useWorkspaceTheme();
    const isRTL = language === "ar";

    return (
        <div
            className="flex flex-wrap gap-2 mt-2"
            dir={isRTL ? "rtl" : "ltr"}
            style={
                {
                    "--ws-ink": c.ink,
                    "--ws-ink70": c.ink70,
                    "--ws-hair": c.hair,
                    "--ws-panel": c.panel,
                    "--ws-active": c.activeBg,
                    "--ws-red": c.red,
                } as React.CSSProperties
            }
        >
            {options.map((opt, i) => (
                <button
                    key={`${opt.action}-${opt.label}-${i}`}
                    type="button"
                    onClick={() => onAction(opt.message ?? opt.label)}
                    className="inline-flex items-center justify-center min-h-[32px] px-3 rounded-full border border-[var(--ws-hair)] bg-[var(--ws-panel)] text-[var(--ws-ink70)] font-mono text-[11px] transition-all duration-150 hover:bg-[var(--ws-active)] hover:border-[var(--ws-ink)] hover:text-[var(--ws-ink)] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ws-red)] rico-focus-strong"
                    aria-label={opt.label}
                >
                    {opt.label}
                </button>
            ))}
        </div>
    );
}
