import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Rico Hunt \u2014 AI Career Operating System for the UAE";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const features = [
    { icon: "\u2713", label: "Find Jobs" },
    { icon: "\u2713", label: "Tailor CVs" },
    { icon: "\u2713", label: "Track Applications" },
    { icon: "\u2713", label: "Interview Prep" },
];

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
                    padding: "72px 88px",
                    fontFamily: "system-ui, sans-serif",
                    position: "relative",
                }}
            >
                {/* Subtle purple radial glow top-right */}
                <div
                    style={{
                        position: "absolute",
                        top: -100,
                        right: -60,
                        width: 480,
                        height: 480,
                        borderRadius: "50%",
                        background: "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)",
                    }}
                />

                {/* UAE flag accent bar */}
                <div style={{ display: "flex", gap: 8, marginBottom: 36 }}>
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#00732F" }} />
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#CCCCCC" }} />
                    <div style={{ width: 44, height: 5, borderRadius: 3, background: "#EF4444" }} />
                </div>

                {/* Layout: left column (brand + headline) and right column (feature list) */}
                <div style={{ display: "flex", width: "100%", gap: 64, alignItems: "center" }}>

                    {/* Left */}
                    <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
                        {/* Brand */}
                        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
                            <span style={{ fontSize: 52, fontWeight: 700, color: "#FFFFFF", letterSpacing: -2, lineHeight: 1 }}>
                                Rico Hunt
                            </span>
                            <span
                                style={{
                                    fontSize: 12,
                                    fontWeight: 600,
                                    color: "#A78BFA",
                                    background: "rgba(139,92,246,0.15)",
                                    border: "1px solid rgba(139,92,246,0.35)",
                                    borderRadius: 6,
                                    padding: "4px 10px",
                                    letterSpacing: 0.5,
                                }}
                            >
                                AI
                            </span>
                        </div>

                        {/* Primary headline */}
                        <div
                            style={{
                                fontSize: 38,
                                fontWeight: 700,
                                color: "#F9FAFB",
                                lineHeight: 1.2,
                                marginBottom: 16,
                                letterSpacing: -0.8,
                            }}
                        >
                            AI Career Operating System
                        </div>

                        {/* Sub-headline */}
                        <div
                            style={{
                                fontSize: 18,
                                color: "#9CA3AF",
                                lineHeight: 1.5,
                                maxWidth: 460,
                            }}
                        >
                            Manage your entire job search with AI \u2014 built for UAE professionals.
                        </div>
                    </div>

                    {/* Right: feature checklist */}
                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 18,
                            background: "rgba(255,255,255,0.04)",
                            border: "1px solid rgba(255,255,255,0.10)",
                            borderRadius: 16,
                            padding: "36px 40px",
                            minWidth: 280,
                        }}
                    >
                        {features.map(({ icon, label }) => (
                            <div
                                key={label}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 14,
                                    color: "#E5E7EB",
                                    fontSize: 20,
                                    fontWeight: 500,
                                }}
                            >
                                <span
                                    style={{
                                        color: "#A78BFA",
                                        fontSize: 18,
                                        fontWeight: 700,
                                        width: 24,
                                        textAlign: "center",
                                    }}
                                >
                                    {icon}
                                </span>
                                {label}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Domain watermark */}
                <div
                    style={{
                        position: "absolute",
                        bottom: 40,
                        right: 88,
                        color: "#4B5563",
                        fontSize: 16,
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
