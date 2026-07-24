/**
 * ContextReveal — a RESTRAINED spotlight for the Command empty state. It warms
 * the suggestion nearest the cursor to guide the eye, then switches off for good
 * after the first interaction so it never competes with a live conversation,
 * text selection, or the keyboard.
 *
 * Accessibility: suggestions are real, focusable children present with or
 * without the light. Mark each with `data-suggestion`; the nearest one receives
 * `data-near`. Disabled entirely on touch / reduced motion (suggestions remain
 * fully usable).
 */
"use client";
import React, { useEffect, useRef, useState } from "react";
import { useFineHover } from "./hooks";
import { useMotionSafe } from "./MotionSafe";

export interface ContextRevealProps {
    children: React.ReactNode;
    className?: string;
    /** px distance within which a suggestion is considered "near" (default 220). */
    nearRadius?: number;
    onDisabled?: () => void;
}

export function ContextReveal({ children, className, nearRadius = 220, onDisabled }: ContextRevealProps) {
    const host = useRef<HTMLDivElement>(null);
    const haloRef = useRef<HTMLDivElement>(null);
    const fine = useFineHover();
    const { reduced } = useMotionSafe();
    const [used, setUsed] = useState(false);
    const enabled = fine && !reduced && !used;

    useEffect(() => {
        const el = host.current;
        if (!el || !enabled) return;
        let raf = 0;
        let x = 0, y = 0;
        const frame = () => {
            const b = el.getBoundingClientRect();
            if (haloRef.current) {
                haloRef.current.style.left = `${x}px`;
                haloRef.current.style.top = `${y}px`;
                haloRef.current.style.opacity = "1";
            }
            const sugs = el.querySelectorAll<HTMLElement>("[data-suggestion]");
            let best: HTMLElement | null = null;
            let bd = Infinity;
            sugs.forEach((s) => {
                const r = s.getBoundingClientRect();
                const cx = r.left - b.left + r.width / 2;
                const cy = r.top - b.top + r.height / 2;
                const d = Math.hypot(cx - x, cy - y);
                if (d < bd) { bd = d; best = s; }
            });
            sugs.forEach((s) => {
                if (s === best && bd < nearRadius) s.setAttribute("data-near", "");
                else s.removeAttribute("data-near");
            });
            raf = 0;
        };
        const onMove = (e: PointerEvent) => {
            if (e.pointerType === "touch") return;
            const b = el.getBoundingClientRect();
            x = e.clientX - b.left; y = e.clientY - b.top;
            if (!raf) raf = requestAnimationFrame(frame);
        };
        const onLeave = () => {
            if (haloRef.current) haloRef.current.style.opacity = "0";
            el.querySelectorAll("[data-suggestion]").forEach((s) => s.removeAttribute("data-near"));
        };
        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerleave", onLeave);
        return () => {
            el.removeEventListener("pointermove", onMove);
            el.removeEventListener("pointerleave", onLeave);
            if (raf) cancelAnimationFrame(raf);
        };
    }, [enabled, nearRadius]);

    const disable = () => {
        if (used) return;
        setUsed(true);
        onDisabled?.();
    };

    return (
        <div
            ref={host}
            className={className}
            style={{ position: "relative" }}
            onClickCapture={disable}
            onKeyDownCapture={disable}
            onPointerDownCapture={(e) => e.pointerType === "touch" && disable()}
        >
            {enabled && (
                <div
                    ref={haloRef}
                    aria-hidden
                    style={{
                        position: "absolute",
                        width: 360,
                        height: 360,
                        transform: "translate(-50%,-50%)",
                        borderRadius: "50%",
                        opacity: 0,
                        transition: "opacity .4s ease",
                        pointerEvents: "none",
                        zIndex: 0,
                        background:
                            "radial-gradient(circle, color-mix(in srgb, var(--rico-clay,#C6492E) 10%, transparent), transparent 68%)",
                    }}
                />
            )}
            {children}
        </div>
    );
}
