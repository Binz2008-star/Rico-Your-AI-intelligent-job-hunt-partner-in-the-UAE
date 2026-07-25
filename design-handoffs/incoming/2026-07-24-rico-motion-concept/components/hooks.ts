/**
 * Rico motion — shared hooks.
 *
 * SSR-safe (Next.js): every `window` / `matchMedia` read is guarded so these
 * run unchanged in the app router. No dependencies beyond React.
 */
import { useEffect, useRef, useState, useCallback } from "react";

/** True when the user (or OS) prefers reduced motion. SSR-safe, live-updating. */
export function useReducedMotion(): boolean {
    const [reduced, setReduced] = useState(false);
    useEffect(() => {
        if (typeof window === "undefined" || !window.matchMedia) return;
        const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
        const on = () => setReduced(mq.matches);
        on();
        mq.addEventListener?.("change", on);
        return () => mq.removeEventListener?.("change", on);
    }, []);
    return reduced;
}

/** True only on a device with a fine pointer that can hover (mouse/pen). */
export function useFineHover(): boolean {
    const [fine, setFine] = useState(false);
    useEffect(() => {
        if (typeof window === "undefined" || !window.matchMedia) return;
        const mq = window.matchMedia("(hover: hover) and (pointer: fine)");
        const on = () => setFine(mq.matches);
        on();
        mq.addEventListener?.("change", on);
        return () => mq.removeEventListener?.("change", on);
    }, []);
    return fine;
}

export interface SmoothPointerOptions {
    /** 0..1 easing factor per frame (default 0.12). */
    lerp?: number;
    /** disable tracking (e.g. reduced motion / touch / after first interaction). */
    enabled?: boolean;
    /** CSS custom-property names to write on the target element. */
    vars?: { x: string; y: string };
    /** called with eased coordinates each frame, if you'd rather not use CSS vars. */
    onFrame?: (x: number, y: number, active: boolean) => void;
}

/**
 * useSmoothPointer — attaches pointer listeners to `ref`, runs ONE
 * requestAnimationFrame loop that lerps toward the raw pointer, and writes the
 * eased position to CSS custom properties on the target. The loop self-parks
 * when idle and is fully cleaned up on unmount. Pointer events (not mouse-only);
 * touch pointers are ignored. This is the engine behind CursorSpotlight.
 */
export function useSmoothPointer<T extends HTMLElement>(
    ref: React.RefObject<T>,
    opts: SmoothPointerOptions = {},
) {
    const { lerp = 0.12, enabled = true, vars, onFrame } = opts;
    const raw = useRef({ x: -9999, y: -9999 });
    const sm = useRef({ x: -9999, y: -9999 });
    const active = useRef(false);
    const rafId = useRef(0);
    const [isActive, setIsActive] = useState(false);

    const write = useCallback(
        (x: number, y: number) => {
            const el = ref.current;
            if (el && vars) {
                el.style.setProperty(vars.x, `${x.toFixed(1)}px`);
                el.style.setProperty(vars.y, `${y.toFixed(1)}px`);
            }
            onFrame?.(x, y, active.current);
        },
        [ref, vars, onFrame],
    );

    useEffect(() => {
        const el = ref.current;
        if (!el || !enabled) return;

        const frame = () => {
            sm.current.x += (raw.current.x - sm.current.x) * lerp;
            sm.current.y += (raw.current.y - sm.current.y) * lerp;
            write(sm.current.x, sm.current.y);
            const settled =
                Math.abs(raw.current.x - sm.current.x) < 0.5 &&
                Math.abs(raw.current.y - sm.current.y) < 0.5;
            rafId.current = active.current && !settled ? requestAnimationFrame(frame) : 0;
        };
        const kick = () => {
            if (!rafId.current) rafId.current = requestAnimationFrame(frame);
        };
        const onMove = (e: PointerEvent) => {
            if (e.pointerType === "touch") return;
            const b = el.getBoundingClientRect();
            raw.current = { x: e.clientX - b.left, y: e.clientY - b.top };
            if (!active.current) {
                active.current = true;
                sm.current = { ...raw.current };
                setIsActive(true);
            }
            kick();
        };
        const onLeave = () => {
            active.current = false;
            setIsActive(false);
        };

        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerleave", onLeave);
        el.addEventListener("pointercancel", onLeave);
        return () => {
            el.removeEventListener("pointermove", onMove);
            el.removeEventListener("pointerleave", onLeave);
            el.removeEventListener("pointercancel", onLeave);
            if (rafId.current) cancelAnimationFrame(rafId.current);
            rafId.current = 0;
            active.current = false;
        };
    }, [ref, enabled, lerp, write]);

    return { isActive };
}
