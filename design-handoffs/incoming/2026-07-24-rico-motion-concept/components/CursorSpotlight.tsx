/**
 * CursorSpotlight — writes `--spotlight-x/y/r` onto a target element from a
 * smoothed pointer, so a CSS radial-gradient mask (see MaskedReveal) can follow
 * the cursor. No canvas, no per-frame toDataURL. Disables on touch, on reduced
 * motion, and optionally after the first interaction.
 */
"use client";
import React, { useEffect, useRef, useState } from "react";
import { useFineHover, useSmoothPointer } from "./hooks";
import { useMotionSafe } from "./MotionSafe";

export interface CursorSpotlightProps extends React.HTMLAttributes<HTMLDivElement> {
    /** spotlight radius in px (default 230). */
    radius?: number;
    /** turn the spotlight off permanently once the user interacts. */
    disableAfterInteraction?: boolean;
    /** CSS var names to write (defaults match MaskedReveal). */
    vars?: { x: string; y: string; r: string };
}

export function CursorSpotlight({
    radius = 230,
    disableAfterInteraction = false,
    vars = { x: "--spotlight-x", y: "--spotlight-y", r: "--spotlight-r" },
    className,
    children,
    ...rest
}: CursorSpotlightProps) {
    const ref = useRef<HTMLDivElement>(null);
    const fine = useFineHover();
    const { reduced } = useMotionSafe();
    const [interacted, setInteracted] = useState(false);

    const enabled = fine && !reduced && !(disableAfterInteraction && interacted);

    const { isActive } = useSmoothPointer(ref, { enabled, vars: { x: vars.x, y: vars.y } });

    // radius easing (in/out) on a light RAF; keeps the halo from popping.
    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        if (!enabled) {
            el.style.setProperty(vars.r, "0px");
            return;
        }
        let raf = 0;
        let cur = 0;
        const target = () => (isActive ? radius : 0);
        const step = () => {
            cur += (target() - cur) * 0.14;
            el.style.setProperty(vars.r, `${cur.toFixed(1)}px`);
            raf = Math.abs(target() - cur) > 0.5 ? requestAnimationFrame(step) : 0;
        };
        raf = requestAnimationFrame(step);
        return () => {
            if (raf) cancelAnimationFrame(raf);
        };
    }, [isActive, enabled, radius, vars.r]);

    return (
        <div
            ref={ref}
            className={className}
            data-lit={enabled && isActive ? "" : undefined}
            onPointerDownCapture={() => disableAfterInteraction && setInteracted(true)}
            {...rest}
        >
            {children}
        </div>
    );
}
