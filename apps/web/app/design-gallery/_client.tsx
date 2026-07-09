"use client";

/**
 * INTERNAL DESIGN GALLERY — /design-gallery
 *
 * Hidden internal route for previewing landing page design variants side by side.
 * NOT linked from production navigation.
 * NOT indexed (noindex set in page.tsx metadata).
 *
 * Variants:
 *  - Current Production  → LandingPageV2  (what app/page.tsx renders)
 *  - Classic             → LandingPage
 *  - Nocturne            → LandingPageNocturne
 *
 * LandingPage and LandingPageNocturne require LanguageProvider context — wrapped below.
 * LandingPageV2 is standalone (no context dependency).
 * All three are dynamically imported (ssr: false) because they are client-only components
 * with canvas, framer-motion, and window-dependent hooks.
 */

import { LanguageProvider } from "@/contexts/LanguageContext";
import dynamic from "next/dynamic";
import { useState } from "react";

const LandingPageV2 = dynamic(
  () => import("@/components/LandingPageV2"),
  { ssr: false, loading: () => <LoadingShell /> }
);

const LandingPage = dynamic(
  () => import("@/components/LandingPage"),
  { ssr: false, loading: () => <LoadingShell /> }
);

const LandingPageNocturne = dynamic(
  () => import("@/components/LandingPageNocturne"),
  { ssr: false, loading: () => <LoadingShell /> }
);

const RicoAlivePrototype = dynamic(
  () => import("@/components/design-gallery/RicoAlivePrototype"),
  { ssr: false, loading: () => <LoadingShell /> }
);

const CommandConceptSandbox = dynamic(
  () => import("@/components/design-gallery/command-concept-sandbox"),
  { ssr: false, loading: () => <LoadingShell /> }
);

function LoadingShell() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b0d1c]">
      <p className="text-white/30 text-sm font-mono animate-pulse">Loading design variant…</p>
    </div>
  );
}

type VariantKey = "v2" | "classic" | "nocturne" | "rico-alive" | "command-concept";

interface Variant {
  key: VariantKey;
  label: string;
  description: string;
  status?: "production" | "prototype" | "draft";
  category?: string;
  riskLevel?: "none" | "low" | "medium" | "high" | "prototype-only";
  productionSafeNotes?: string;
  prototypeOnlyNotes?: string;
}

const VARIANTS: Variant[] = [
  {
    key: "v2",
    label: "Current Production",
    description: "LandingPageV2 — what / renders today",
  },
  {
    key: "classic",
    label: "Classic",
    description: "LandingPage — original design",
  },
  {
    key: "nocturne",
    label: "Nocturne",
    description: "LandingPageNocturne — Nocturne design system",
    status: "production",
    category: "landing",
    riskLevel: "none",
    productionSafeNotes: "Production component. No changes made here.",
  },
  {
    key: "rico-alive",
    label: "Rico Alive ✦ Prototype",
    description: "RicoAlivePrototype — AI thinking states, job cards, safety gate, chat thread. Bilingual EN/AR. All data is SAMPLE/DEMO.",
    status: "prototype",
    category: "command-concept",
    riskLevel: "prototype-only",
    productionSafeNotes: "Zero production routes, backend, auth, or billing touched. Isolated standalone component.",
    prototypeOnlyNotes: "All data is simulated. No real AI calls. No provider names exposed. Uses framer-motion + Tailwind only — no new packages.",
  },
  {
    key: "command-concept",
    label: "Command Concept ✦ Reference",
    description: "CommandConceptSandbox — Tool Activity Timeline, Explainable Match Card, Safety Approval Surface, Chat Thread. Bilingual EN/AR. All data is SAMPLE/DEMO.",
    status: "prototype",
    category: "command-concept",
    riskLevel: "prototype-only",
    productionSafeNotes: "Zero production routes, backend, auth, or billing touched. Isolated standalone component, promoted from design-handoffs/approved-for-gallery/command-concept-sandbox/ after owner review (2026-07-08).",
    prototypeOnlyNotes: "Approved as Design Reference — requires production adaptation. All actions (apply, save, approve, send) are disabled/reference-only; nothing is wired to /command or any real action.",
  },
];

export default function DesignGalleryClient() {
  const [active, setActive] = useState<VariantKey>("v2");

  return (
    <div style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* ── Control bar ────────────────────────────────────────────────────── */}
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 9999,
          background: "rgba(10, 11, 22, 0.95)",
          backdropFilter: "blur(16px)",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          padding: "10px 20px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        {/* Internal badge */}
        <span
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            padding: "3px 10px",
            borderRadius: 999,
            background: "rgba(240,169,74,0.12)",
            border: "1px solid rgba(240,169,74,0.30)",
            color: "rgba(240,169,74,0.9)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
          role="status"
          aria-label="Internal preview only — not production navigation"
        >
          Internal preview only — not production navigation
        </span>

        {/* Link to the Atelier V2 design-system specimen (PR A1). Isolated,
            noindex sub-route; does not alter these landing variants. */}
        <a
          href="/design-gallery/atelier"
          style={{
            fontSize: 11,
            fontFamily: "monospace",
            padding: "5px 14px",
            borderRadius: 999,
            border: "1px solid rgba(207,61,23,0.40)",
            background: "rgba(207,61,23,0.12)",
            color: "rgba(238,106,58,0.95)",
            textDecoration: "none",
            whiteSpace: "nowrap",
          }}
        >
          Atelier V2 ✦ design system
        </a>

        <div style={{ flex: 1 }} />

        {/* Variant selector */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {VARIANTS.map((v) => {
            const isActive = active === v.key;
            return (
              <button
                key={v.key}
                onClick={() => setActive(v.key)}
                title={v.description}
                style={{
                  fontSize: 11,
                  padding: "5px 14px",
                  borderRadius: 999,
                  border: isActive
                    ? "1px solid rgba(240,169,74,0.40)"
                    : "1px solid rgba(255,255,255,0.10)",
                  background: isActive
                    ? "rgba(240,169,74,0.12)"
                    : "transparent",
                  color: isActive
                    ? "rgba(240,169,74,1)"
                    : "rgba(255,255,255,0.45)",
                  cursor: "pointer",
                  fontWeight: isActive ? 600 : 400,
                  transition: "all 0.15s ease",
                  whiteSpace: "nowrap",
                }}
              >
                {v.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Active variant info bar ─────────────────────────────────────────── */}
      {(() => {
        const v = VARIANTS.find((v) => v.key === active);
        return (
          <div
            style={{
              background: "rgba(10,11,22,0.85)",
              borderBottom: "1px solid rgba(255,255,255,0.05)",
              padding: "6px 20px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", fontFamily: "monospace" }}>
              Viewing:
            </span>
            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.55)", fontFamily: "monospace" }}>
              {v?.description}
            </span>
            {v?.status && (
              <span style={{
                fontSize: 9, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.12em",
                padding: "2px 8px", borderRadius: 999,
                background: v.status === "prototype" ? "rgba(129,140,248,0.12)" : "rgba(255,255,255,0.06)",
                border: v.status === "prototype" ? "1px solid rgba(129,140,248,0.28)" : "1px solid rgba(255,255,255,0.10)",
                color: v.status === "prototype" ? "rgba(129,140,248,0.9)" : "rgba(255,255,255,0.35)",
              }}>
                {v.status}
              </span>
            )}
            {v?.riskLevel && (
              <span style={{
                fontSize: 9, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.12em",
                padding: "2px 8px", borderRadius: 999,
                background: "rgba(111,233,208,0.08)", border: "1px solid rgba(111,233,208,0.20)",
                color: "rgba(111,233,208,0.70)",
              }}>
                risk: {v.riskLevel}
              </span>
            )}
            {v?.prototypeOnlyNotes && (
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.22)", fontStyle: "italic" }}>
                {v.prototypeOnlyNotes}
              </span>
            )}
          </div>
        );
      })()}

      {/* ── Design variant render area ──────────────────────────────────────── */}
      <div key={active}>
        {active === "v2" && <LandingPageV2 />}

        {active === "classic" && (
          <LanguageProvider>
            <LandingPage />
          </LanguageProvider>
        )}

        {active === "nocturne" && (
          <LanguageProvider>
            <LandingPageNocturne />
          </LanguageProvider>
        )}

        {active === "rico-alive" && <RicoAlivePrototype />}

        {active === "command-concept" && <CommandConceptSandbox />}
      </div>
    </div>
  );
}
