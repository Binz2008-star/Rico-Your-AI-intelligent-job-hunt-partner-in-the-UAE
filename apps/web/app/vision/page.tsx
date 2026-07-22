import type { Metadata } from "next";
import { VisionPrototype } from "./VisionPrototype";

/**
 * /vision — the Rico Bureau interactive prototype (owner directive
 * 2026-07-22: full-ownership redesign exploration, delivered as a working
 * prototype, not a report). Self-contained route: synthetic data only, no
 * backend calls, no changes to production surfaces. The motion vocabulary
 * demonstrated here (understanding / context / searching / reading /
 * verifying / evidence / approval / completion / uncertainty / recovery)
 * is the candidate interaction language for the real Command surface.
 */
export const metadata: Metadata = {
    title: "Rico — the Bureau (vision prototype)",
    robots: { index: false, follow: false },
};

export default function VisionPage() {
    return <VisionPrototype />;
}
