/**
 * CareerTransformationHero — composes the whole Rico landing hero from the kit:
 * a LayeredAsset base ("scattered" scene) with a MaskedReveal clarity scene, lit
 * by a CursorSpotlight, an entrance-animated headline, and the starting-action
 * pills. Scenes are passed in as props (Rico uses original inline-SVG scenes),
 * so this component carries no imagery of its own.
 *
 * Truth: the reveal is the organised career state, never a decorative image.
 * Height uses 100dvh so mobile browser chrome never clips it. Always render the
 * "Sample scenario — not live account data" label with any sample content.
 */
"use client";
import React from "react";
import { CursorSpotlight } from "./CursorSpotlight";
import { MaskedReveal } from "./MaskedReveal";
import { LayeredAsset } from "./LayeredAsset";
import { HeroEntrance } from "./HeroEntrance";
import { HeroActionPills, RicoAction, RICO_STARTING_ACTIONS } from "./HeroActionPills";

export interface CareerTransformationHeroProps {
    /** the "scattered" base scene (inline SVG / node). */
    baseScene: React.ReactNode;
    /** the "organised / verified" reveal scene (inline SVG / node). */
    revealScene: React.ReactNode;
    eyebrow?: React.ReactNode;
    headlineLines: [React.ReactNode, React.ReactNode];
    sub?: React.ReactNode;
    actions?: RicoAction[];
    /** rendered top-left; MUST be shown with sample content. */
    sampleLabel?: React.ReactNode;
    spotlightRadius?: number;
}

export function CareerTransformationHero({
    baseScene,
    revealScene,
    eyebrow,
    headlineLines,
    sub,
    actions = RICO_STARTING_ACTIONS,
    sampleLabel = "Sample scenario — not live account data",
    spotlightRadius = 230,
}: CareerTransformationHeroProps) {
    return (
        <CursorSpotlight
            radius={spotlightRadius}
            className="relative w-full overflow-hidden"
            style={{ height: "100dvh" } as React.CSSProperties}
            aria-label="Rico landing hero: a scattered career state that resolves into an organised search, active CV, verified matches and a structured applications board as you move the cursor. Sample scenario, not live account data."
        >
            {sampleLabel && <span className="rico-sample-tag">{sampleLabel}</span>}

            <MaskedReveal
                className="absolute inset-0"
                base={<LayeredAsset layers={[baseScene]} zoom />}
                reveal={<div className="absolute inset-0">{revealScene}</div>}
            />

            <div className="absolute inset-x-0 top-[12%] flex flex-col items-center text-center px-5 pointer-events-none z-50">
                {eyebrow && (
                    <HeroEntrance variant="fade" delay={0.12} className="mb-4">
                        {eyebrow}
                    </HeroEntrance>
                )}
                <HeroEntrance as="h1" variant="blur" delay={0.25} stagger={0.17} className="rico-hero-h1">
                    <span className="block italic">{headlineLines[0]}</span>
                    <span className="block">{headlineLines[1]}</span>
                </HeroEntrance>
                {sub && (
                    <HeroEntrance variant="fade" delay={0.7} className="rico-hero-sub">
                        {sub}
                    </HeroEntrance>
                )}
            </div>

            <div className="absolute inset-x-0 bottom-14 flex justify-center px-5 z-50">
                <HeroActionPills actions={actions} />
            </div>
        </CursorSpotlight>
    );
}
