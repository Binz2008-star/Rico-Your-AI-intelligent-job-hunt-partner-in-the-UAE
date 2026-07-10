import type { Metadata } from "next";
import RicoPreviewClient from "./_client";

/**
 * /rico-preview — INTERNAL PREVIEW route (DEC-20260709-006).
 *
 * Renders the merged Atelier Console reference (#924) behind a preview surface
 * for workspace-direction exploration. NOT production: internal, noindex, demo
 * data only, all actions disabled/reference-only. Not linked from production
 * navigation. Does not replace /command or /rico.
 */

export const metadata: Metadata = {
  title: "Rico Preview — Atelier Console (Internal)",
  description:
    "Internal preview of the Atelier Console workspace direction. Sample data only, actions disabled. Not production navigation.",
  robots: { index: false, follow: false },
};

export default function RicoPreviewPage() {
  return <RicoPreviewClient />;
}
