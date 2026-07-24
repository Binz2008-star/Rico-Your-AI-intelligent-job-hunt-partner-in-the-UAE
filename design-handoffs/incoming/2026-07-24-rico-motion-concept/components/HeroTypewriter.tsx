/**
 * HeroTypewriter — types ONE short line, once per session, with a blinking
 * caret that disappears when done. Under reduced motion the full text is shown
 * immediately. Keep it to a single short intro line, never a paragraph.
 */
"use client";
import React, { useEffect, useRef, useState } from "react";
import { useMotionSafe } from "./MotionSafe";

export interface HeroTypewriterProps {
    text: string;
    /** ms per character (default 38). */
    speed?: number;
    /** ms before typing starts (default 600). */
    startDelay?: number;
    /** sessionStorage key so it runs once per session (default derived). */
    storageKey?: string;
    className?: string;
    onDone?: () => void;
}

export function HeroTypewriter({
    text,
    speed = 38,
    startDelay = 600,
    storageKey = "rico-tw-seen",
    className,
    onDone,
}: HeroTypewriterProps) {
    const { reduced } = useMotionSafe();
    const [shown, setShown] = useState("");
    const [done, setDone] = useState(false);
    const timers = useRef<number[]>([]);

    useEffect(() => {
        const seen =
            typeof window !== "undefined" && window.sessionStorage?.getItem(storageKey) === "1";
        if (reduced || seen) {
            setShown(text);
            setDone(true);
            onDone?.();
            return;
        }
        let i = 0;
        const tick = () => {
            setShown(text.slice(0, i));
            if (i <= text.length) {
                i += 1;
                timers.current.push(window.setTimeout(tick, speed));
            } else {
                setDone(true);
                try { window.sessionStorage?.setItem(storageKey, "1"); } catch { /* private mode */ }
                onDone?.();
            }
        };
        timers.current.push(window.setTimeout(tick, startDelay));
        return () => { timers.current.forEach(clearTimeout); timers.current = []; };
    }, [text, speed, startDelay, storageKey, reduced, onDone]);

    return (
        <div className={className} aria-live="polite">
            {shown}
            {!done && (
                <span
                    aria-hidden
                    style={{
                        display: "inline-block",
                        width: 2,
                        height: "1.05em",
                        marginLeft: 3,
                        verticalAlign: "-3px",
                        background: "var(--rico-clay, #C6492E)",
                        animation: "rico-blink 1s step-end infinite",
                    }}
                />
            )}
            <style>{`@keyframes rico-blink{50%{opacity:0}}`}</style>
        </div>
    );
}
