"use client";

/**
 * Command Workspace v5 — foundation specimen (client). Renders every PR 1
 * primitive with SAMPLE content so reviewers can screenshot the foundation
 * against the accepted v5 evidence package. Nothing here ships to a
 * production route.
 */

import { useState } from "react";
import "@/components/workspace/v5/motion.css";
import { V5, V5_FONT, V5_GRADIENT, V5_MODE_ACCENTS, V5ModeKey } from "@/components/workspace/v5/tokens";
import { RicoPresence, RicoPresenceState } from "@/components/workspace/v5/RicoPresence";

const SWATCH_GROUPS: { title: string; items: [name: string, value: string, note?: string][] }[] = [
    {
        title: "Paper world",
        items: [
            ["paper", V5.paper],
            ["panel", V5.panel],
            ["panel2", V5.panel2],
            ["inset", V5.inset],
            ["raise", V5.raise],
        ],
    },
    {
        title: "Deep cinematic plane",
        items: [
            ["deep", V5.deep],
            ["deepPanel", V5.deepPanel],
            ["deepPanel2", V5.deepPanel2],
            ["deepEdge", V5.deepEdge],
            ["lightInk", V5.lightInk],
        ],
    },
    {
        title: "Energy (decorative)",
        items: [
            ["terra", V5.terra],
            ["coral", V5.coral],
            ["amber", V5.amber],
            ["gold", V5.gold],
            ["goldSoft", V5.goldSoft],
            ["electric", V5.electric],
            ["purple", V5.purple],
            ["moss", V5.moss],
        ],
    },
    {
        title: "AA text-safe accents",
        items: [
            ["terraText", V5.terraText, "5.33:1"],
            ["amberText", V5.amberText, "4.76:1"],
            ["goldText", V5.goldText, "5.63:1"],
            ["electricText", V5.electricText, "5.91:1"],
            ["purpleText", V5.purpleText, "5.65:1"],
            ["goldTextL", V5.goldTextL, "4.03:1 L"],
            ["coralTextL", V5.coralTextL, "3.71:1 L"],
        ],
    },
];

const MODES: V5ModeKey[] = [
    "overview",
    "search",
    "applications",
    "documents",
    "interview",
    "learning",
    "activity",
];

const ORB_STATES: RicoPresenceState[] = ["ready", "thinking", "acting", "completed", "warning"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section style={{ marginTop: 44 }}>
            <div className="wsx5-micro" style={{ marginBottom: 14 }}>
                <span className="wsx5-tick">◆</span>&nbsp;{title}
            </div>
            {children}
        </section>
    );
}

export default function CommandV5Specimen() {
    const [play, setPlay] = useState(true);
    const replay = () => {
        setPlay(false);
        requestAnimationFrame(() => requestAnimationFrame(() => setPlay(true)));
    };

    return (
        <main
            className="wsx5"
            style={{
                minHeight: "100dvh",
                background: V5.paper,
                color: V5.ink,
                fontFamily: V5_FONT.sans,
                padding: "clamp(20px, 4vw, 56px)",
                paddingBottom: 120,
            }}
        >
            <div style={{ maxWidth: 1080, margin: "0 auto" }}>
                {/* header */}
                <header>
                    <div className="wsx5-micro" style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span className="wsx5-tick">PR 1</span> Command v5 foundation · internal specimen ·
                        sample content
                        <span className="wsx5-breathe-dot" aria-hidden="true" />
                    </div>
                    <h1
                        className="wsx5-display"
                        style={{ fontFamily: V5_FONT.display, fontSize: "clamp(38px, 5vw, 64px)", marginTop: 14 }}
                    >
                        The v5 foundation, <em>powered on</em>.
                    </h1>
                    <p style={{ color: V5.ink70, maxWidth: "56ch", marginTop: 12, lineHeight: 1.6 }}>
                        Tokens, typography, surfaces, motion primitives and the Rico presence
                        indicator — everything later v5 PRs compose from. No chat logic, no data,
                        no production routes.
                    </p>
                </header>

                {/* palette */}
                <Section title="Tokens — audited palette">
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
                        {SWATCH_GROUPS.map((g) => (
                            <div key={g.title} className="wsx5-card" style={{ padding: 16 }}>
                                <div className="wsx5-micro" style={{ marginBottom: 10 }}>{g.title}</div>
                                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                    {g.items.map(([name, value, note]) => (
                                        <div key={name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                            <span
                                                aria-hidden="true"
                                                style={{
                                                    width: 26,
                                                    height: 26,
                                                    borderRadius: 8,
                                                    background: value,
                                                    border: `1px solid ${V5.hair}`,
                                                    flex: "0 0 auto",
                                                }}
                                            />
                                            <span style={{ fontFamily: V5_FONT.mono, fontSize: 11.5, color: V5.ink70 }}>
                                                {name}
                                            </span>
                                            <span
                                                style={{
                                                    marginLeft: "auto",
                                                    fontFamily: V5_FONT.mono,
                                                    fontSize: 10.5,
                                                    color: V5.ink55,
                                                }}
                                            >
                                                {note ?? value}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </Section>

                {/* typography */}
                <Section title="Typography — editorial hierarchy">
                    <div className="wsx5-card" style={{ padding: "26px 26px 30px" }}>
                        <div className="wsx5-micro">Micro label · 10.5px · 0.22em tracking</div>
                        <p
                            className="wsx5-display"
                            style={{ fontFamily: V5_FONT.display, fontSize: "clamp(34px, 4.4vw, 56px)", marginTop: 10 }}
                        >
                            Find work worth <em>moving</em> for.
                        </p>
                        <p style={{ color: V5.ink70, marginTop: 12, maxWidth: "58ch", lineHeight: 1.6 }}>
                            Body — Space Grotesk 14.5px on paper. Secondary ink passes AA at 5.80:1;
                            the smallest metadata ink (ink55) passes at 4.51:1.
                        </p>
                        <div style={{ display: "flex", gap: 22, marginTop: 18, alignItems: "baseline", flexWrap: "wrap" }}>
                            <span style={{ fontFamily: V5_FONT.display, fontSize: 52, letterSpacing: "-0.04em", background: V5_GRADIENT.goldNumeralText, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
                                96
                            </span>
                            <span style={{ fontFamily: V5_FONT.mono, fontSize: 11, color: V5.ink55 }}>
                                numeral gradient · every stop ≥3.0:1
                            </span>
                            <span style={{ color: V5.terraText, fontWeight: 700, fontSize: 12, letterSpacing: "0.08em" }}>
                                TERRA TEXT
                            </span>
                            <span style={{ color: V5.electricText, fontWeight: 700, fontSize: 12, letterSpacing: "0.08em" }}>
                                ELECTRIC TEXT
                            </span>
                        </div>
                    </div>
                </Section>

                {/* surfaces */}
                <Section title="Surfaces — three planes">
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
                        <div className="wsx5-card" style={{ padding: 20 }}>
                            <div className="wsx5-micro">Paper card</div>
                            <p style={{ marginTop: 8, color: V5.ink85, fontWeight: 600 }}>Primary content plane</p>
                            <p style={{ marginTop: 4, color: V5.ink55, fontSize: 12.5 }}>hairline border · layered shadow</p>
                        </div>
                        <div className="wsx5-deepcard" style={{ padding: 20, position: "relative", overflow: "hidden" }}>
                            <div className="wsx5-lightsweep" aria-hidden="true" />
                            <div className="wsx5-micro" style={{ color: V5.lightInk50 }}>Deep cinematic plane</div>
                            <p style={{ marginTop: 8, color: V5.lightInk, fontWeight: 600 }}>Focal moments only</p>
                            <p style={{ marginTop: 4, color: V5.lightInk70, fontSize: 12.5 }}>score · stage · constellation</p>
                        </div>
                        <div style={{ position: "relative", borderRadius: 18, overflow: "hidden", background: V5_GRADIENT.ember, padding: 3 }}>
                            <div className="wsx5-glass" style={{ borderRadius: 15, padding: 17 }}>
                                <div className="wsx5-micro">Glass layer</div>
                                <p style={{ marginTop: 8, color: V5.ink85, fontWeight: 600 }}>Sticky chrome & sheets</p>
                                <p style={{ marginTop: 4, color: V5.ink55, fontSize: 12.5 }}>blur 18px · saturate 1.15</p>
                            </div>
                        </div>
                    </div>
                </Section>

                {/* motion */}
                <Section title="Motion primitives — replayable">
                    <div className="wsx5-card" style={{ padding: 20 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                            <button
                                type="button"
                                onClick={replay}
                                style={{
                                    background: V5_GRADIENT.emberButton,
                                    color: V5.onEmber,
                                    border: 0,
                                    borderRadius: 12,
                                    padding: "11px 20px",
                                    fontWeight: 600,
                                    fontSize: 13.5,
                                    fontFamily: "inherit",
                                    cursor: "pointer",
                                }}
                            >
                                Replay entrances
                            </button>
                            <span style={{ fontFamily: V5_FONT.mono, fontSize: 11, color: V5.ink55 }}>
                                rise · unfold · mask · scale · tiltin · slide — 70ms stagger, collapses under
                                reduced motion
                            </span>
                        </div>
                        <div
                            className={play ? "wsx5-play" : undefined}
                            style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginTop: 18 }}
                        >
                            {(["rise", "unfold", "mask", "scale", "tiltin", "slide"] as const).map((kind, i) => (
                                <div
                                    key={kind}
                                    data-wsx5-anim={kind}
                                    className="wsx5-card"
                                    style={{ ["--i" as string]: i, padding: "18px 14px", textAlign: "center", background: V5.raise }}
                                >
                                    <span style={{ fontFamily: V5_FONT.mono, fontSize: 11, color: V5.ink70 }}>{kind}</span>
                                </div>
                            ))}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 26, marginTop: 22, flexWrap: "wrap" }}>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 9, fontSize: 12, color: V5.ink70, fontWeight: 600 }}>
                                <span className="wsx5-breathe-dot" aria-hidden="true" /> live dot
                            </span>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 12, fontSize: 12, color: V5.ink70, fontWeight: 600 }}>
                                <span className="wsx5-pip" aria-hidden="true" /> urgency pip
                            </span>
                            <div className="wsx5-skel" style={{ width: 180, height: 34 }} aria-hidden="true" />
                            <span style={{ fontFamily: V5_FONT.mono, fontSize: 11, color: V5.ink55 }}>skeleton shimmer</span>
                        </div>
                    </div>
                </Section>

                {/* presence */}
                <Section title="Rico presence — five states">
                    <div className="wsx5-card" style={{ padding: 20 }}>
                        <div style={{ display: "flex", gap: 30, flexWrap: "wrap" }}>
                            {ORB_STATES.map((s) => (
                                <div key={s} style={{ textAlign: "center" }}>
                                    <RicoPresence state={s} size="md" decorative />
                                    <div style={{ fontFamily: V5_FONT.mono, fontSize: 10.5, color: V5.ink55, marginTop: 8 }}>{s}</div>
                                </div>
                            ))}
                            <div style={{ display: "flex", alignItems: "flex-end", gap: 16, marginLeft: "auto" }}>
                                <RicoPresence state="ready" size="sm" decorative />
                                <RicoPresence state="ready" size="md" decorative />
                                <RicoPresence state="ready" size="lg" decorative />
                            </div>
                        </div>
                        <p style={{ marginTop: 16, fontSize: 12, color: V5.ink55, lineHeight: 1.6 }}>
                            Honest-state rule: thinking/acting may only be set while real work is in
                            flight — the component never simulates activity.
                        </p>
                    </div>
                </Section>

                {/* per-mode accents */}
                <Section title="Per-mode accents — modeA / modeB / modeAText">
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
                        {MODES.map((m) => {
                            const a = V5_MODE_ACCENTS[m];
                            return (
                                <div key={m} className="wsx5-card" style={{ padding: 14 }}>
                                    <div style={{ display: "flex", gap: 6, marginBottom: 10 }} aria-hidden="true">
                                        <span style={{ flex: 1, height: 22, borderRadius: 7, background: a.modeA }} />
                                        <span style={{ flex: 1, height: 22, borderRadius: 7, background: a.modeB }} />
                                    </div>
                                    <div style={{ fontSize: 11.5, fontWeight: 700, color: a.modeAText, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                                        {m}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </Section>

                <p style={{ marginTop: 52, textAlign: "center", fontFamily: V5_FONT.mono, fontSize: 10.5, color: V5.ink55, letterSpacing: "0.06em" }}>
                    COMMAND V5 · PR 1 FOUNDATION · INTERNAL SPECIMEN · ALL CONTENT IS SAMPLE
                </p>
            </div>
        </main>
    );
}
