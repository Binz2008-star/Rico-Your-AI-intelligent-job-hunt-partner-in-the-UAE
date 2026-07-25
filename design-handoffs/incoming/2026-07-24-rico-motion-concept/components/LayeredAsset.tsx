/**
 * LayeredAsset — stacks visual layers and applies an optional slow zoom-out
 * (Ken-Burns) to the furthest layer. Transform-only; frozen under reduced
 * motion. Pass any nodes as layers (Rico uses inline-SVG scenes).
 */
"use client";
import React from "react";
import { useMotionSafe } from "./MotionSafe";

export interface LayeredAssetProps {
    layers: React.ReactNode[];
    /** apply the slow zoom to the first (back) layer. */
    zoom?: boolean;
    className?: string;
}

export function LayeredAsset({ layers, zoom = true, className }: LayeredAssetProps) {
    const { reduced } = useMotionSafe();
    return (
        <div className={className} style={{ position: "relative", overflow: "hidden" }}>
            {layers.map((layer, i) => (
                <div
                    key={i}
                    style={{
                        position: "absolute",
                        inset: 0,
                        transformOrigin: "60% 45%",
                        animation:
                            zoom && i === 0 && !reduced
                                ? "rico-slow-zoom 2s cubic-bezier(.16,1,.3,1) forwards"
                                : undefined,
                    }}
                >
                    {layer}
                </div>
            ))}
            <style>{`@keyframes rico-slow-zoom{from{transform:scale(1.1)}to{transform:scale(1)}}`}</style>
        </div>
    );
}
