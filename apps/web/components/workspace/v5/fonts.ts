import { Space_Grotesk } from "next/font/google";

/**
 * Command Workspace v5 UI sans (PR 1, foundation). Space Grotesk carries the
 * v5 interface voice: nav labels, chips, buttons, micro-labels. Display serif
 * stays Fraunces via the shared atelier-kit loader (`atelierFraunces`) — do
 * not add a second Fraunces instance.
 *
 * Route-scoped by design: next/font only emits preload hints on routes that
 * actually render a component using this export (same pattern as the
 * design-gallery Atelier fonts), so importing it here changes nothing for
 * existing production routes.
 *
 * The `variable` literal must stay in sync with V5_FONT.sans in ./tokens.ts.
 */
export const v5SpaceGrotesk = Space_Grotesk({
    subsets: ["latin"],
    weight: ["300", "400", "500", "600", "700"],
    display: "swap",
    variable: "--font-space-grotesk",
});
