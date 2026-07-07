import type { Metadata } from "next";
import { Amiri, Fraunces, IBM_Plex_Sans_Arabic } from "next/font/google";
import AtelierSpecimen from "./_specimen";

/**
 * Atelier V2 fonts are loaded HERE, scoped to this route only. next/font emits
 * preload hints tied to the routes that use the font, so production pages
 * (which never render this component) are unaffected — no change to the global
 * app/layout.tsx font set. EN body/mono reuse the global Inter / IBM Plex Mono
 * variables already on <body>.
 */
const fraunces = Fraunces({
    subsets: ["latin"],
    weight: ["300", "400", "500", "600"],
    variable: "--font-atl-display",
    display: "swap",
});

const amiri = Amiri({
    subsets: ["arabic"],
    weight: ["400", "700"],
    variable: "--font-atl-display-ar",
    display: "swap",
});

const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
    subsets: ["arabic"],
    weight: ["400", "500", "600"],
    variable: "--font-atl-body-ar",
    display: "swap",
});

export const metadata: Metadata = {
    title: "Atelier V2 — Design System Specimen (Internal)",
    description:
        "Internal Atelier V2 token & component specimen for the Rico V2 cutover. Not linked from production navigation. Not indexed.",
    robots: { index: false, follow: false },
};

export default function AtelierSpecimenPage() {
    return (
        <div className={`${fraunces.variable} ${amiri.variable} ${ibmPlexSansArabic.variable}`}>
            <AtelierSpecimen />
        </div>
    );
}
