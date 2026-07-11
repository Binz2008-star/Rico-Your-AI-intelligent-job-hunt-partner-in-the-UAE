"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER, ATELIER_FONT } from "./tokens";

/**
 * Mono uppercase editorial label. In Arabic, wide letter-spacing shreds the
 * connected script and the mono face lacks Arabic — so AR labels drop
 * letter-spacing and use the system Arabic (body) fallback. Extracted
 * unchanged from LandingPageV2.tsx (PR 0, TASK-20260710-003).
 */
export function Mono({
    children,
    className = "",
    style,
}: {
    children: React.ReactNode;
    className?: string;
    style?: React.CSSProperties;
}) {
    const { language } = useLanguage();
    const isAr = language === "ar";
    const base: React.CSSProperties = isAr
        ? { fontFamily: ATELIER_FONT.body, fontSize: 11, ...style, letterSpacing: "0" }
        : { fontFamily: ATELIER_FONT.mono, fontSize: 11, letterSpacing: "0.2em", ...style };
    return (
        <span className={`uppercase ${className}`} style={base}>
            {children}
        </span>
    );
}

/**
 * Corner-tick plate (reference "PLATE 01" frame). Extracted unchanged from
 * LandingPageV2.tsx (PR 0, TASK-20260710-003).
 */
export function Plate({
    className = "",
    style,
    children,
}: {
    className?: string;
    style?: React.CSSProperties;
    children: React.ReactNode;
}) {
    const t = "absolute w-2 h-2 pointer-events-none";
    const b = `1px solid ${ATELIER.hair}`;
    return (
        <div
            className={`relative rounded-[4px] ${className}`}
            style={{ background: ATELIER.panel, border: `1px solid ${ATELIER.hair}`, ...style }}
        >
            <span className={`${t} top-1.5 left-1.5`} style={{ borderTop: b, borderLeft: b }} aria-hidden="true" />
            <span className={`${t} top-1.5 right-1.5`} style={{ borderTop: b, borderRight: b }} aria-hidden="true" />
            <span className={`${t} bottom-1.5 left-1.5`} style={{ borderBottom: b, borderLeft: b }} aria-hidden="true" />
            <span className={`${t} bottom-1.5 right-1.5`} style={{ borderBottom: b, borderRight: b }} aria-hidden="true" />
            {children}
        </div>
    );
}
