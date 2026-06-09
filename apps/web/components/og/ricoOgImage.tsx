import type { ReactElement } from "react";

/**
 * Shared Open Graph / Twitter card artwork for Rico Hunt.
 *
 * Rendered through `next/og` (Satori) by the `app/opengraph-image.tsx` and
 * `app/twitter-image.tsx` route conventions, so a single source produces both
 * the `og:image` and `twitter:image` shown on LinkedIn, WhatsApp, and X.
 *
 * Satori constraints respected here: flexbox-only layout, every multi-child box
 * sets `display:flex`, gradients use explicit rgba stops (no `transparent`
 * keyword), and no `filter`/`backdrop-filter`. No web fonts are loaded — the
 * built-in font is used so the image renders offline at build time with no
 * network dependency.
 */

export const OG_SIZE = { width: 1200, height: 630 } as const;
export const OG_ALT = "Rico Hunt — Your AI Job-Hunt Partner in the UAE";

const GOLD = "#f5a623";
const CANVAS = "#0a0a1a";

export function RicoOgImage(): ReactElement {
    return (
        <div
            style={{
                width: "1200px",
                height: "630px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                padding: "64px",
                backgroundColor: CANVAS,
                backgroundImage:
                    "radial-gradient(45% 45% at 0% 0%, rgba(245,166,35,0.18) 0%, rgba(10,10,26,0) 60%), radial-gradient(45% 45% at 100% 100%, rgba(255,45,142,0.14) 0%, rgba(10,10,26,0) 60%)",
                color: "#ffffff",
                fontFamily: "sans-serif",
            }}
        >
            {/* Brand */}
            <div style={{ display: "flex", alignItems: "center" }}>
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "64px",
                        height: "64px",
                        borderRadius: "16px",
                        backgroundColor: GOLD,
                        color: CANVAS,
                        fontSize: "38px",
                        fontWeight: 700,
                        boxShadow: "0 0 44px rgba(245,166,35,0.45)",
                    }}
                >
                    R
                </div>
                <div
                    style={{
                        display: "flex",
                        marginLeft: "20px",
                        fontSize: "34px",
                        fontWeight: 700,
                        letterSpacing: "-0.02em",
                    }}
                >
                    <span style={{ color: "#ffffff" }}>Rico</span>
                    <span style={{ color: GOLD, marginLeft: "10px" }}>Hunt</span>
                </div>
            </div>

            {/* Headline */}
            <div style={{ display: "flex", flexDirection: "column" }}>
                <div
                    style={{
                        display: "flex",
                        color: GOLD,
                        fontSize: "22px",
                        letterSpacing: "0.28em",
                        textTransform: "uppercase",
                        marginBottom: "22px",
                    }}
                >
                    AI Job-Hunt Partner · UAE
                </div>
                <div
                    style={{
                        display: "flex",
                        fontSize: "70px",
                        lineHeight: 1.04,
                        letterSpacing: "-0.02em",
                        fontWeight: 700,
                        maxWidth: "920px",
                    }}
                >
                    Your AI job-hunt partner in the UAE.
                </div>
                <div
                    style={{
                        display: "flex",
                        marginTop: "26px",
                        fontSize: "27px",
                        lineHeight: 1.4,
                        color: "rgba(255,255,255,0.62)",
                        maxWidth: "840px",
                    }}
                >
                    Upload your CV. Rico finds matching UAE jobs, explains the fit, and tracks every application.
                </div>
            </div>

            {/* Match card + domain */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        border: "1px solid rgba(255,255,255,0.12)",
                        backgroundColor: "rgba(255,255,255,0.04)",
                        borderRadius: "16px",
                        padding: "16px 24px",
                    }}
                >
                    <div style={{ display: "flex", flexDirection: "column", marginRight: "28px" }}>
                        <span style={{ fontSize: "21px", color: "#ffffff" }}>Environmental Compliance Officer</span>
                        <span style={{ fontSize: "16px", color: "rgba(255,255,255,0.45)", marginTop: "4px" }}>
                            Dubai · Full-time
                        </span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <span style={{ fontSize: "42px", fontWeight: 700, color: GOLD, lineHeight: 1 }}>86</span>
                        <span
                            style={{
                                fontSize: "13px",
                                letterSpacing: "0.2em",
                                color: "rgba(255,255,255,0.4)",
                                textTransform: "uppercase",
                                marginTop: "5px",
                            }}
                        >
                            Fit
                        </span>
                    </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                    <span style={{ fontSize: "26px", color: "#ffffff" }}>ricohunt.com</span>
                    <span style={{ fontSize: "18px", color: "rgba(255,255,255,0.45)", marginTop: "6px" }}>
                        English &amp; Arabic
                    </span>
                </div>
            </div>
        </div>
    );
}
