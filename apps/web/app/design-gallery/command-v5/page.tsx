import type { Metadata } from "next";
import { assertInternalPreviewAccess } from "@/lib/internalPreview";
import { atelierFraunces, atelierNaskhArabic, atelierSansArabic } from "@/components/atelier-kit/fonts";
import { v5SpaceGrotesk } from "@/components/workspace/v5/fonts";
import CommandV5Specimen from "./_specimen";

/**
 * Command Workspace v5 — PR 1 foundation specimen (internal preview only;
 * production requests 404 via assertInternalPreviewAccess, same as every
 * /design-gallery surface). This is the review target for the v5 visual
 * foundation: tokens, typography, surfaces, motion primitives and the Rico
 * presence indicator — no chat logic, no data, no production routes.
 *
 * Fonts are loaded HERE, route-scoped (the established gallery pattern):
 * production pages never render this component, so their font set is
 * untouched. Fraunces + Arabic companions reuse the shared atelier-kit
 * loaders; Space Grotesk is the one new v5 face.
 */
export const metadata: Metadata = {
    title: "Command v5 Foundation — Rico Internal",
    description: "Internal design specimen. Not linked from production navigation.",
    robots: { index: false, follow: false },
};

export default function CommandV5FoundationPage() {
    assertInternalPreviewAccess();
    return (
        <div
            className={`${atelierFraunces.variable} ${atelierNaskhArabic.variable} ${atelierSansArabic.variable} ${v5SpaceGrotesk.variable}`}
        >
            <CommandV5Specimen />
        </div>
    );
}
