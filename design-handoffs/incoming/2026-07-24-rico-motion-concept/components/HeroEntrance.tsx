/**
 * HeroEntrance — staggered blur-rise / fade-up entrance for a group of children.
 * GPU-friendly (opacity + transform + filter). Under reduced motion, children
 * appear instantly at their final position.
 */
"use client";
import React from "react";
import { useMotionSafe } from "./MotionSafe";

export interface HeroEntranceProps {
    children: React.ReactNode;
    /** "blur" = blur-rise (headlines); "fade" = fade-up (supporting). */
    variant?: "blur" | "fade";
    /** base delay (s) for the first child; each subsequent child adds `stagger`. */
    delay?: number;
    stagger?: number;
    as?: keyof JSX.IntrinsicElements;
    className?: string;
}

export function HeroEntrance({
    children,
    variant = "fade",
    delay = 0,
    stagger = 0.12,
    as = "div",
    className,
}: HeroEntranceProps) {
    const { reduced } = useMotionSafe();
    const Tag = as as React.ElementType;
    const items = React.Children.toArray(children);
    return (
        <Tag className={className}>
            {items.map((child, i) => (
                <div
                    key={i}
                    style={
                        reduced
                            ? undefined
                            : {
                                  opacity: 0,
                                  animation: `rico-${variant} ${variant === "blur" ? 1.05 : 0.9}s cubic-bezier(.16,1,.3,1) forwards`,
                                  animationDelay: `${delay + i * stagger}s`,
                              }
                    }
                >
                    {child}
                </div>
            ))}
            <style>{`
                @keyframes rico-blur{0%{opacity:0;transform:translateY(26px);filter:blur(12px)}100%{opacity:1;transform:none;filter:blur(0)}}
                @keyframes rico-fade{0%{opacity:0;transform:translateY(18px)}100%{opacity:1;transform:none}}
            `}</style>
        </Tag>
    );
}
