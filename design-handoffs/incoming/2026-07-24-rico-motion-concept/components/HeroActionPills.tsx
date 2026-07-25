/**
 * HeroActionPills — the starting actions, entering with a staggered fade-up on
 * an INDEPENDENT 400 ms timer (never waits for the typewriter). Every action
 * maps to a real Rico route or chat intent; there is no auto-apply action.
 * One optional "copy" variant demonstrates the copied → reset micro-state.
 */
"use client";
import React, { useEffect, useState } from "react";
import { useMotionSafe } from "./MotionSafe";

export interface RicoAction {
    label: string;
    /** real route (e.g. "/jobs") or intent ("chat"). Informational, shown small. */
    route?: string;
    href?: string;
    onClick?: () => void;
    icon?: React.ReactNode;
    primary?: boolean;
    outline?: boolean;
    /** copies this string to the clipboard and flips to a "Copied" state. */
    copy?: string;
}

/** The six truthful Command starting actions. */
export const RICO_STARTING_ACTIONS: RicoAction[] = [
    { label: "Find jobs", route: "/jobs", primary: true },
    { label: "Review my CV", route: "/profile · cv" },
    { label: "Improve my profile", route: "/profile" },
    { label: "Check my applications", route: "/applications" },
    { label: "Prepare for an interview", route: "chat intent" },
    { label: "Upload a document", route: "/upload" },
];

export interface HeroActionPillsProps {
    actions: RicoAction[];
    /** ms after mount before pills appear, independent of any typewriter. */
    revealDelay?: number;
    className?: string;
    renderPill?: (a: RicoAction, i: number, copied: boolean, onCopy: () => void) => React.ReactNode;
}

export function HeroActionPills({
    actions,
    revealDelay = 400,
    className,
    renderPill,
}: HeroActionPillsProps) {
    const { reduced } = useMotionSafe();
    const [shown, setShown] = useState(false);
    const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

    useEffect(() => {
        const t = window.setTimeout(() => setShown(true), reduced ? 0 : revealDelay);
        return () => clearTimeout(t);
    }, [revealDelay, reduced]);

    const doCopy = (a: RicoAction, i: number) => {
        if (!a.copy) return;
        const finish = () => {
            setCopiedIdx(i);
            window.setTimeout(() => setCopiedIdx((c) => (c === i ? null : c)), 1600);
        };
        try { navigator.clipboard?.writeText(a.copy).then(finish, finish); } catch { finish(); }
    };

    return (
        <div className={className} style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
            {actions.map((a, i) => {
                const copied = copiedIdx === i;
                if (renderPill) return <React.Fragment key={i}>{renderPill(a, i, copied, () => doCopy(a, i))}</React.Fragment>;
                const style: React.CSSProperties = {
                    opacity: shown ? 1 : 0,
                    transform: shown ? "none" : "translateY(9px)",
                    transition: reduced ? undefined : "opacity .4s ease, transform .4s ease",
                    transitionDelay: reduced ? undefined : `${i * 55}ms`,
                };
                const content = (
                    <>
                        {a.icon}
                        {copied ? "Copied" : a.label}
                        {a.route && <span style={{ opacity: 0.5, fontSize: 11 }}>{a.route}</span>}
                    </>
                );
                const cls =
                    "rico-pill" +
                    (a.primary ? " rico-pill--primary" : "") +
                    (a.outline ? " rico-pill--outline" : "") +
                    (copied ? " rico-pill--copied" : "");
                if (a.href) return <a key={i} href={a.href} className={cls} style={style}>{content}</a>;
                return (
                    <button
                        key={i}
                        className={cls}
                        style={style}
                        onClick={() => (a.copy ? doCopy(a, i) : a.onClick?.())}
                    >
                        {content}
                    </button>
                );
            })}
        </div>
    );
}
