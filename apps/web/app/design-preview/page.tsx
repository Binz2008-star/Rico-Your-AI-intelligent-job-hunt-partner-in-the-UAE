import type { Metadata } from "next";
import DesignPreviewClient from "./_client";

/**
 * /design-preview — INTERNAL PREVIEW hub (single entry point).
 *
 * One page from which the owner can review the whole Rico "Atelier" direction:
 * live interactive previews (the Atelier Console at /rico-preview, the design
 * variants at /design-gallery, the live Atelier legal pages) plus labelled
 * design-reference screenshots for every other surface (landing, auth,
 * onboarding, workspace, support/legal, states) in EN/AR desktop/mobile.
 *
 * NOT production: internal, noindex, sample/demo data only, all actions
 * disabled/reference-only. Not linked from production navigation. Replaces no
 * production route.
 */

export const metadata: Metadata = {
  title: "Rico — Design Preview (Internal)",
  description:
    "Internal preview hub for the Rico Atelier direction. Sample data only, actions disabled. Not production navigation.",
  robots: { index: false, follow: false },
};

export default function DesignPreviewPage() {
  return <DesignPreviewClient />;
}
