"use client";

/**
 * /design-preview hub (INTERNAL PREVIEW).
 *
 * Single entry point to review the whole Rico Atelier direction. Self-contained
 * (inline styles, no new deps, no shadcn): a labelled catalogue of every surface,
 * grouped by area. Each screen is either a LIVE interactive preview (opens a real
 * internal route) or a labelled design-reference screenshot (EN/AR, desktop/
 * mobile). All data is sample/demo; every action is disabled/reference-only.
 */

import { useState } from "react";

const IMG = (name: string) => `/design-preview/${name}.png`;

type Shot = { label: string; src: string };
type Screen = {
  title: string;
  note?: string;
  live?: { href: string; label: string };
  shots?: Shot[];
};
type Group = { id: string; title: string; screens: Screen[] };

const GROUPS: Group[] = [
  {
    id: "landing",
    title: "1 · Public landing",
    screens: [
      {
        title: "Landing",
        note: "Atelier marketing surface — hero, features, pricing teaser, CTA.",
        shots: [
          { label: "Desktop · EN", src: IMG("desktop-home-en-light") },
          { label: "Desktop · AR", src: IMG("desktop-home-ar-light") },
          { label: "Mobile · AR", src: IMG("mobile-home-ar-light") },
        ],
      },
    ],
  },
  {
    id: "auth",
    title: "2 · Auth",
    screens: [
      {
        title: "Login",
        shots: [
          { label: "Desktop · EN", src: IMG("en-auth-signin-desktop") },
          { label: "Desktop · AR", src: IMG("ar-auth-signin-desktop") },
          { label: "Mobile · EN", src: IMG("en-auth-signin-mobile") },
          { label: "Mobile · AR", src: IMG("ar-auth-signin-mobile") },
        ],
      },
      {
        title: "Signup",
        shots: [
          { label: "Desktop · EN", src: IMG("en-auth-signup-desktop") },
          { label: "Mobile · EN", src: IMG("en-auth-signup-mobile") },
        ],
      },
      {
        title: "Forgot password",
        shots: [
          { label: "Desktop · EN", src: IMG("en-auth-forgot-desktop") },
          { label: "Mobile · EN", src: IMG("en-auth-forgot-mobile") },
        ],
      },
      {
        title: "Check email / verify",
        shots: [
          { label: "Verify · Desktop", src: IMG("en-auth-verify-desktop") },
          { label: "Verify · Mobile", src: IMG("en-auth-verify-mobile") },
          { label: "Reset · Desktop", src: IMG("en-auth-reset-desktop") },
          { label: "Reset · Mobile", src: IMG("en-auth-reset-mobile") },
        ],
      },
    ],
  },
  {
    id: "onboarding",
    title: "3 · Onboarding (CV upload · profile confirm · target roles)",
    screens: [
      {
        title: "Onboarding flow",
        note: "First-run flow covering CV upload, profile confirmation, and target-role / preferences steps.",
        shots: [
          { label: "Desktop · EN", src: IMG("en-onboarding-desktop") },
          { label: "Desktop · AR", src: IMG("ar-onboarding-desktop") },
          { label: "Mobile · EN", src: IMG("en-onboarding-mobile") },
          { label: "Mobile · AR", src: IMG("ar-onboarding-mobile") },
        ],
      },
    ],
  },
  {
    id: "workspace",
    title: "4 · Authenticated workspace",
    screens: [
      {
        title: "Command / chat",
        note: "The flagship Atelier Console — live, interactive, scripted demo (text-reveal, pinned composer, near-bottom auto-follow).",
        live: { href: "/rico-preview", label: "Open live preview → /rico-preview" },
        shots: [
          { label: "Desktop · EN", src: IMG("en-command-desktop") },
          { label: "Desktop · AR", src: IMG("ar-command-desktop") },
          { label: "Mobile · EN", src: IMG("en-command-mobile") },
        ],
      },
      {
        title: "Dashboard / home",
        shots: [
          { label: "Dashboard · EN", src: IMG("desktop-dashboard-en-light") },
          { label: "Dashboard · AR", src: IMG("desktop-dashboard-ar-light") },
          { label: "Dashboard · Mobile AR", src: IMG("mobile-dashboard-ar-light") },
          { label: "App index · Desktop", src: IMG("en-app-index-desktop") },
          { label: "App index · Mobile", src: IMG("en-app-index-mobile") },
        ],
      },
      {
        title: "Profile",
        shots: [
          { label: "Desktop · EN", src: IMG("en-profile-desktop") },
          { label: "Desktop · AR", src: IMG("ar-profile-desktop") },
          { label: "Mobile · EN", src: IMG("en-profile-mobile") },
        ],
      },
      {
        title: "Settings",
        shots: [
          { label: "Desktop · EN", src: IMG("en-settings-desktop") },
          { label: "Desktop · AR", src: IMG("ar-settings-desktop") },
          { label: "Mobile · EN", src: IMG("en-settings-mobile") },
        ],
      },
      {
        title: "Applications / pipeline",
        shots: [
          { label: "Desktop · EN", src: IMG("en-applications-desktop") },
          { label: "Desktop · AR", src: IMG("ar-applications-desktop") },
          { label: "Mobile · EN", src: IMG("en-applications-mobile") },
        ],
      },
      {
        title: "Upload CV",
        shots: [
          { label: "Desktop · EN", src: IMG("en-upload-desktop") },
          { label: "Desktop · AR", src: IMG("ar-upload-desktop") },
          { label: "Mobile · EN", src: IMG("en-upload-mobile") },
        ],
      },
      {
        title: "Subscription / pricing",
        shots: [
          { label: "Desktop · EN", src: IMG("desktop-pricing-en-light") },
          { label: "Desktop · AR", src: IMG("desktop-pricing-ar-light") },
          { label: "Mobile · AR", src: IMG("mobile-pricing-ar-light") },
        ],
      },
    ],
  },
  {
    id: "support-legal",
    title: "5 · Support / legal",
    screens: [
      {
        title: "Support / contact",
        shots: [
          { label: "Desktop · EN", src: IMG("desktop-support-en-light") },
          { label: "Desktop · AR", src: IMG("desktop-support-ar-light") },
        ],
      },
      {
        title: "Privacy",
        note: "Shipped Atelier page (live).",
        live: { href: "/privacy", label: "Open live → /privacy" },
      },
      {
        title: "Refund policy",
        note: "Shipped Atelier page (live).",
        live: { href: "/refund-policy", label: "Open live → /refund-policy" },
      },
      {
        title: "Terms",
        note: "Shipped Atelier page (live).",
        live: { href: "/terms", label: "Open live → /terms" },
      },
    ],
  },
  {
    id: "states",
    title: "6 · States & design systems (empty · loading · error · mobile · RTL · light/dark)",
    screens: [
      {
        title: "Atelier Console — states",
        note: "Loading / text-reveal, empty and populated states are demonstrated live in the console.",
        live: { href: "/rico-preview", label: "Open live states → /rico-preview" },
        shots: [
          { label: "Rico states · Desktop", src: IMG("en-states-rico-desktop") },
          { label: "Rico states · Mobile", src: IMG("en-states-rico-mobile") },
        ],
      },
      {
        title: "App — states",
        shots: [
          { label: "App states · Desktop", src: IMG("en-states-app-desktop") },
          { label: "App states · Mobile", src: IMG("en-states-app-mobile") },
        ],
      },
      {
        title: "Design gallery (all variants)",
        note: "Live: Atelier Console, Nocturne, Rico Alive, and landing variants — with EN/AR + light/dark toggles.",
        live: { href: "/design-gallery", label: "Open live → /design-gallery" },
      },
    ],
  },
];

/* ── styling helpers (inline; theme-neutral internal chrome) ─────────────── */

const chip = (bg: string, border: string, color: string): React.CSSProperties => ({
  fontSize: 10,
  fontFamily: "monospace",
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  padding: "3px 10px",
  borderRadius: 999,
  background: bg,
  border: `1px solid ${border}`,
  color,
  whiteSpace: "nowrap",
});

function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        background: "rgba(8,9,16,0.88)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        cursor: "zoom-out",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Design reference — enlarged"
        style={{
          maxWidth: "96vw",
          maxHeight: "92vh",
          borderRadius: 8,
          boxShadow: "0 30px 80px -20px rgba(0,0,0,0.6)",
        }}
      />
    </div>
  );
}

export default function DesignPreviewClient() {
  const [zoom, setZoom] = useState<string | null>(null);

  return (
    <div
      style={{
        minHeight: "100dvh",
        background: "#f2ece0",
        color: "#14110d",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
      }}
    >
      {/* Sticky internal-preview header */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "rgba(10,11,22,0.96)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(255,255,255,0.10)",
          padding: "10px 20px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <span style={chip("rgba(238,106,58,0.16)", "rgba(238,106,58,0.42)", "rgba(238,106,58,0.95)")}>
          Internal preview
        </span>
        <span style={chip("rgba(255,255,255,0.06)", "rgba(255,255,255,0.14)", "rgba(255,255,255,0.72)")}>
          Sample data
        </span>
        <span style={chip("rgba(255,255,255,0.06)", "rgba(255,255,255,0.14)", "rgba(255,255,255,0.72)")}>
          Actions disabled
        </span>
        <span style={{ fontSize: 11, fontFamily: "monospace", color: "rgba(255,255,255,0.45)", whiteSpace: "nowrap" }}>
          Rico Design Preview — one place to review the whole direction (DEC-20260709-006). Not production.
        </span>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "28px 20px 80px" }}>
        <h1 style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 30, fontWeight: 400, letterSpacing: "-0.02em", margin: "0 0 6px" }}>
          Rico — Design Preview
        </h1>
        <p style={{ fontSize: 14, color: "#3a342c", maxWidth: 760, lineHeight: 1.6, margin: "0 0 8px" }}>
          A single internal entry point for reviewing the whole Rico Atelier direction.
          <strong> Live</strong> tiles open real interactive internal previews;
          <strong> Reference</strong> tiles are design screenshots (EN/AR · desktop/mobile).
          Everything here is sample/demo with actions disabled — it replaces no production route.
        </p>

        {/* Quick jump */}
        <nav style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "14px 0 26px" }}>
          {GROUPS.map((g) => (
            <a
              key={g.id}
              href={`#${g.id}`}
              style={{
                ...chip("#faf6ec", "#d3c9b4", "#3a342c"),
                textDecoration: "none",
                cursor: "pointer",
              }}
            >
              {g.title}
            </a>
          ))}
        </nav>

        {GROUPS.map((g) => (
          <section key={g.id} id={g.id} style={{ scrollMarginTop: 64, marginBottom: 36 }}>
            <h2 style={{ fontFamily: "Georgia, serif", fontSize: 19, fontWeight: 400, borderBottom: "1px solid #d3c9b4", paddingBottom: 8, marginBottom: 16 }}>
              {g.title}
            </h2>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
              {g.screens.map((s) => (
                <div
                  key={s.title}
                  style={{
                    background: "#faf6ec",
                    border: "1px solid #d3c9b4",
                    borderRadius: 12,
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{s.title}</span>
                    {s.live ? (
                      <span style={chip("rgba(16,140,90,0.12)", "rgba(16,140,90,0.35)", "rgb(20,110,72)")}>Live</span>
                    ) : (
                      <span style={chip("rgba(207,61,23,0.10)", "rgba(207,61,23,0.30)", "#b23a1a")}>Reference</span>
                    )}
                  </div>

                  {s.note && <p style={{ fontSize: 12.5, color: "#6b6355", margin: 0, lineHeight: 1.5 }}>{s.note}</p>}

                  {s.live && (
                    <a
                      href={s.live.href}
                      style={{
                        display: "inline-block",
                        fontSize: 12,
                        fontFamily: "monospace",
                        padding: "7px 12px",
                        borderRadius: 8,
                        background: "#14110d",
                        color: "#f2ece0",
                        textDecoration: "none",
                        width: "fit-content",
                      }}
                    >
                      {s.live.label}
                    </a>
                  )}

                  {s.shots && s.shots.length > 0 && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8 }}>
                      {s.shots.map((sh) => (
                        <figure key={sh.src} style={{ margin: 0 }}>
                          <button
                            onClick={() => setZoom(sh.src)}
                            title="Click to enlarge"
                            style={{
                              display: "block",
                              width: "100%",
                              padding: 0,
                              border: "1px solid #d3c9b4",
                              borderRadius: 6,
                              overflow: "hidden",
                              background: "#fff",
                              cursor: "zoom-in",
                            }}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={sh.src}
                              alt={`${s.title} — ${sh.label} (design reference)`}
                              loading="lazy"
                              style={{ display: "block", width: "100%", height: "auto" }}
                            />
                          </button>
                          <figcaption style={{ fontSize: 10, fontFamily: "monospace", color: "#6b6355", marginTop: 4, textAlign: "center" }}>
                            {sh.label}
                          </figcaption>
                        </figure>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}

        <footer style={{ marginTop: 40, paddingTop: 16, borderTop: "1px solid #d3c9b4", fontSize: 12, color: "#6b6355", lineHeight: 1.6 }}>
          Reference tiles are design screenshots from the approved Atelier package; they are not live
          production screens. Live tiles are internal, noindex, reference-only routes. No real chat, job
          search, save, apply, follow-up, or CV action runs anywhere. Turning reference surfaces into live
          interactive previews is planned as separate route-group preview PRs (see the PR description).
        </footer>
      </main>

      {zoom && <Lightbox src={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
