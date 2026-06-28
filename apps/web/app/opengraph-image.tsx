import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Rico Hunt — AI Career Operating System for the UAE";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
    return new ImageResponse(
        (
            <div
                style={{
                    background: "#06060c",
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    justifyContent: "center",
                    padding: "80px 88px",
                    fontFamily: "system-ui, sans-serif",
                    position: "relative",
                }}
            >
                {/* Subtle purple radial glow top-right */}
                <div
                    style={{
                        position: "absolute",
                        top: -120,
                        right: -80,
                        width: 520,
                        height: 520,
                        borderRadius: "50%",
                        background: "radial-gradient(circle, rgba(139,92,246,0.18) 0%, transparent 70%)",
                    }}
                />

                {/* UAE accent bar */}
                <div style={{ display: "flex", gap: 8, marginBottom: 44 }}>
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#00732F" }} />
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#CCCCCC" }} />
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#EF4444" }} />
                </div>

                {/* Brand */}
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 28 }}>
                    <span style={{ fontSize: 58, fontWeight: 700, color: "#FFFFFF", letterSpacing: -2, lineHeight: 1 }}>
                        Rico Hunt
                    </span>
                    <span
                        style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: "#A78BFA",
                            background: "rgba(139,92,246,0.15)",
                            border: "1px solid rgba(139,92,246,0.35)",
                            borderRadius: 6,
                            padding: "5px 12px",
                            letterSpacing: 0.5,
                        }}
                    >
                        AI
                    </span>
                </div>

                {/* Headline */}
                <div
                    style={{
                        fontSize: 46,
                        fontWeight: 700,
                        color: "#F9FAFB",
                        lineHeight: 1.15,
                        marginBottom: 20,
                        maxWidth: 820,
                        letterSpacing: -1,
                    }}
                >
                    AI Career Operating System for the UAE
                </div>

                {/* Sub-headline */}
                <div
                    style={{
                        fontSize: 22,
                        color: "#9CA3AF",
                        lineHeight: 1.5,
                        maxWidth: 700,
                        marginBottom: 52,
                    }}
                >
                    CV analysis, job matching, application tracking, follow-ups, and interview preparation — all in one place.
                </div>

                {/* Feature pills */}
                <div style={{ display: "flex", gap: 12 }}>
                    {["CV Analysis", "Job Matching", "Application Tracking", "Interview Prep"].map((label) => (
                        <div
                            key={label}
                            style={{
                                background: "rgba(255,255,255,0.06)",
                                border: "1px solid rgba(255,255,255,0.12)",
                                borderRadius: 40,
                                padding: "10px 22px",
                                color: "#D1D5DB",
                                fontSize: 16,
                                fontWeight: 500,
                            }}
                        >
                            {label}
                        </div>
                    ))}
                </div>

                {/* Domain watermark bottom-right */}
                <div
                    style={{
                        position: "absolute",
                        bottom: 44,
                        right: 88,
                        color: "#4B5563",
                        fontSize: 18,
                        fontWeight: 500,
                    }}
                >
                    ricohunt.com
                </div>
            </div>
        ),
        { ...size },
    );
}
