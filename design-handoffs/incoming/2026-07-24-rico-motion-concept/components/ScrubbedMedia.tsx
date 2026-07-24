/**
 * ScrubbedMedia — horizontal pointer scrub over a transformation.
 *
 * Motion model (mirrors the spec): a raw target, one eased current value, ONE
 * active RAF loop, and — for the optional <video> — one active seek at a time
 * with the latest target queued (no seek-flooding). Writes `--scrub` (0..1) and
 * `--scrub-pct` (0-100%) onto the root so children (an SVG keyframe wipe, a
 * seam, a track) can style themselves without re-rendering React each frame.
 *
 * Fallbacks: touch taps advance through discrete stages; reduced motion snaps
 * to the clarity end; arrow keys step the seam; `role="slider"` + aria-valuenow.
 */
"use client";
import React, { useCallback, useEffect, useRef } from "react";
import { useMotionSafe } from "./MotionSafe";

export interface ScrubbedMediaProps {
    className?: string;
    /** discrete stages for touch tap-advance (default quarters). */
    touchStages?: number[];
    /** optional video to seek in step with the scrub. */
    videoRef?: React.RefObject<HTMLVideoElement>;
    /** stage label from progress, for aria + any visible tag. */
    stageLabel?: (p: number) => string;
    onProgress?: (p: number) => void;
    children?: React.ReactNode;
    "aria-label"?: string;
}

export function ScrubbedMedia({
    className,
    touchStages = [0.05, 0.35, 0.6, 0.92],
    videoRef,
    stageLabel,
    onProgress,
    children,
    ...rest
}: ScrubbedMediaProps) {
    const root = useRef<HTMLDivElement>(null);
    const target = useRef(0.06);
    const cur = useRef(0.06);
    const raf = useRef(0);
    const { reduced } = useMotionSafe();

    // video seek: one active seek, latest queued.
    const seeking = useRef(false);
    const queued = useRef<number | null>(null);
    const seek = useCallback(
        (p: number) => {
            const v = videoRef?.current;
            if (!v || !v.duration) return;
            const t = p * v.duration;
            if (seeking.current) {
                queued.current = t;
                return;
            }
            seeking.current = true;
            const onSeeked = () => {
                v.removeEventListener("seeked", onSeeked);
                seeking.current = false;
                if (queued.current != null) {
                    const next = queued.current;
                    queued.current = null;
                    seek(next / v.duration);
                }
            };
            v.addEventListener("seeked", onSeeked);
            v.currentTime = t;
        },
        [videoRef],
    );

    const apply = useCallback(
        (p: number) => {
            const el = root.current;
            if (el) {
                el.style.setProperty("--scrub", p.toFixed(3));
                el.style.setProperty("--scrub-pct", `${(p * 100).toFixed(1)}%`);
                el.setAttribute("aria-valuenow", String(Math.round(p * 100)));
                if (stageLabel) el.setAttribute("aria-valuetext", stageLabel(p));
            }
            onProgress?.(p);
            seek(p);
        },
        [onProgress, seek, stageLabel],
    );

    const loop = useCallback(() => {
        cur.current += (target.current - cur.current) * 0.16;
        apply(cur.current);
        if (Math.abs(target.current - cur.current) > 0.001) {
            raf.current = requestAnimationFrame(loop);
        } else {
            cur.current = target.current;
            apply(cur.current);
            raf.current = 0;
        }
    }, [apply]);

    const setTarget = useCallback(
        (t: number) => {
            target.current = Math.max(0, Math.min(1, t));
            if (reduced) {
                cur.current = target.current;
                apply(cur.current);
                return;
            }
            if (!raf.current) raf.current = requestAnimationFrame(loop);
        },
        [reduced, apply, loop],
    );

    useEffect(() => {
        const el = root.current;
        if (!el) return;
        if (reduced) {
            setTarget(1);
            return;
        }
        apply(cur.current);
        const onMove = (e: PointerEvent) => {
            if (e.pointerType === "touch") return;
            const b = el.getBoundingClientRect();
            setTarget((e.clientX - b.left) / b.width);
        };
        const onDown = (e: PointerEvent) => {
            if (e.pointerType !== "touch") return;
            const next = touchStages.find((s) => s > cur.current + 0.02) ?? touchStages[0];
            setTarget(next);
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "ArrowRight") { setTarget(target.current + 0.06); e.preventDefault(); }
            else if (e.key === "ArrowLeft") { setTarget(target.current - 0.06); e.preventDefault(); }
            else if (e.key === "Home") setTarget(0);
            else if (e.key === "End") setTarget(1);
        };
        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerdown", onDown);
        el.addEventListener("keydown", onKey);
        return () => {
            el.removeEventListener("pointermove", onMove);
            el.removeEventListener("pointerdown", onDown);
            el.removeEventListener("keydown", onKey);
            if (raf.current) cancelAnimationFrame(raf.current);
            raf.current = 0;
        };
    }, [reduced, setTarget, apply, loop, touchStages]);

    return (
        <div
            ref={root}
            className={className}
            role="slider"
            tabIndex={0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(cur.current * 100)}
            {...rest}
        >
            {children}
        </div>
    );
}
