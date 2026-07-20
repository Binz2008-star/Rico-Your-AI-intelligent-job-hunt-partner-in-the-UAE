"use client";

/**
 * Shell specimen (client): the real WorkspaceShell wrapping SAMPLE document
 * content. The v5 skin under review is the shell chrome itself — rail
 * accents, energy marker, wordmark, atmosphere, presence, entrance.
 */

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { V5, V5_FONT } from "@/components/workspace/v5/tokens";
import { RicoPresence } from "@/components/workspace/v5/RicoPresence";

export default function ShellSpecimen() {
    return (
        <WorkspaceShell>
            <div className="wsx5" style={{ fontFamily: V5_FONT.sans }}>
                <div className="wsx5-micro" style={{ marginBottom: 12 }}>
                    <span className="wsx5-tick">PR 2</span>&nbsp;Shell specimen · sample content
                </div>
                <h1
                    className="wsx5-display"
                    style={{ fontFamily: V5_FONT.display, fontSize: "clamp(32px, 4vw, 52px)" }}
                >
                    The shell, <em>powered on</em>.
                </h1>
                <p style={{ color: V5.ink70, maxWidth: "56ch", marginTop: 12, lineHeight: 1.6 }}>
                    This page exists only to review the v5 WorkspaceShell treatment: per-route rail
                    accents, the active energy marker, the ember wordmark, route atmosphere, the
                    document entrance, and the Rico presence indicator in the rail.
                </p>
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                        gap: 14,
                        marginTop: 26,
                    }}
                >
                    <div className="wsx5-card" style={{ padding: 18 }}>
                        <div className="wsx5-micro">Sample card</div>
                        <p style={{ marginTop: 8, fontWeight: 600, color: V5.ink85 }}>
                            Document content plane
                        </p>
                        <p style={{ marginTop: 4, fontSize: 12.5, color: V5.ink55 }}>
                            rises in via the shell entrance
                        </p>
                    </div>
                    <div className="wsx5-deepcard" style={{ padding: 18 }}>
                        <div className="wsx5-micro" style={{ color: V5.lightInk50 }}>
                            Sample deep panel
                        </div>
                        <p style={{ marginTop: 8, fontWeight: 600 }}>Focal moment</p>
                        <p style={{ marginTop: 4, fontSize: 12.5, color: V5.lightInk70 }}>
                            unchanged by the shell
                        </p>
                    </div>
                    <div className="wsx5-card" style={{ padding: 18, display: "flex", alignItems: "center", gap: 14 }}>
                        <RicoPresence state="ready" size="md" decorative />
                        <div>
                            <p style={{ fontWeight: 600, color: V5.ink85 }}>Presence in content</p>
                            <p style={{ fontSize: 12.5, color: V5.ink55 }}>same indicator as the rail</p>
                        </div>
                    </div>
                </div>
                <p
                    style={{
                        marginTop: 44,
                        fontFamily: V5_FONT.mono,
                        fontSize: 10.5,
                        color: V5.ink55,
                        letterSpacing: "0.06em",
                    }}
                >
                    COMMAND V5 · PR 2 SHELL SPECIMEN · ALL CONTENT IS SAMPLE
                </p>
            </div>
        </WorkspaceShell>
    );
}
