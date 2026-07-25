/**
 * MaskedReveal — stacks a `reveal` layer over a `base` layer and masks the
 * reveal with a soft radial gradient positioned by CSS custom properties
 * (`--spotlight-x/y/r`, written by CursorSpotlight). The reveal shows only
 * inside the moving soft circle.
 *
 * Reduced motion / touch: the mask is removed so the reveal (the honest, clear
 * end-state) is shown in full — nothing meaningful is locked behind a pointer.
 *
 * WebKit fallback: both `maskImage` and `WebkitMaskImage` are set.
 */
"use client";
import React from "react";
import { useFineHover } from "./hooks";
import { useMotionSafe } from "./MotionSafe";

export interface MaskedRevealProps {
    base: React.ReactNode;
    reveal: React.ReactNode;
    className?: string;
}

const MASK =
    "radial-gradient(circle var(--spotlight-r, 0px) at var(--spotlight-x, -9999px) var(--spotlight-y, -9999px)," +
    "#000 0%, #000 40%, rgba(0,0,0,.75) 60%, rgba(0,0,0,.4) 75%, rgba(0,0,0,.12) 88%, transparent 100%)";

export function MaskedReveal({ base, reveal, className }: MaskedRevealProps) {
    const fine = useFineHover();
    const { reduced } = useMotionSafe();
    const static_ = reduced || !fine; // show clarity in full

    const maskStyle: React.CSSProperties = static_
        ? {}
        : {
              maskImage: MASK,
              WebkitMaskImage: MASK,
              maskRepeat: "no-repeat",
              WebkitMaskRepeat: "no-repeat",
              willChange: "mask-image",
          };

    return (
        <div className={className} style={{ position: "relative" }}>
            <div style={{ position: "absolute", inset: 0, zIndex: 10 }}>{base}</div>
            <div style={{ position: "absolute", inset: 0, zIndex: 30, ...maskStyle }}>{reveal}</div>
        </div>
    );
}
