"use client";

/**
 * /rico-preview client shell (INTERNAL PREVIEW).
 *
 * Thin wrapper: a fixed preview banner (INTERNAL PREVIEW · SAMPLE DATA ·
 * ACTIONS DISABLED) above the merged Atelier Console reference component
 * (`components/design-gallery/atelier-console`, from #924). No console code is
 * duplicated — the component is reused as-is and dynamically imported (ssr:false)
 * like the design-gallery entry.
 *
 * Everything below the banner is the same reference-only console: scripted demo
 * walkthrough, sample data, every action disabled/reference-only, self-scoped
 * theme (light/dark) + language (EN/AR) + direction (RTL) that never touch <html>.
 */

import dynamic from "next/dynamic";

const AtelierConsole = dynamic(
  () => import("@/components/design-gallery/atelier-console"),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-screen flex items-center justify-center bg-[#f2ece0]">
        <p className="text-[#6b6355] text-sm font-mono animate-pulse">
          Loading preview…
        </p>
      </div>
    ),
  },
);

function PreviewBanner() {
  return (
    <div
      role="status"
      aria-label="Internal preview — sample data — actions disabled — not production navigation"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 9999,
        background: "rgba(10, 11, 22, 0.96)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(255,255,255,0.10)",
        padding: "8px 16px",
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap",
        fontFamily: "monospace",
      }}
    >
      <span
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.14em",
          padding: "3px 10px",
          borderRadius: 999,
          background: "rgba(238,106,58,0.16)",
          border: "1px solid rgba(238,106,58,0.42)",
          color: "rgba(238,106,58,0.95)",
          whiteSpace: "nowrap",
        }}
      >
        Internal preview
      </span>
      <span
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.14em",
          padding: "3px 10px",
          borderRadius: 999,
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.14)",
          color: "rgba(255,255,255,0.72)",
          whiteSpace: "nowrap",
        }}
      >
        Sample data
      </span>
      <span
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.14em",
          padding: "3px 10px",
          borderRadius: 999,
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.14)",
          color: "rgba(255,255,255,0.72)",
          whiteSpace: "nowrap",
        }}
      >
        Actions disabled
      </span>
      <span
        style={{
          fontSize: 10,
          color: "rgba(255,255,255,0.40)",
          letterSpacing: "0.08em",
          whiteSpace: "nowrap",
        }}
      >
        Atelier Console direction (DEC-20260709-006) — not production, not linked from navigation
      </span>
    </div>
  );
}

export default function RicoPreviewClient() {
  return (
    <div style={{ minHeight: "100dvh", background: "#f2ece0" }}>
      <PreviewBanner />
      <AtelierConsole />
    </div>
  );
}
