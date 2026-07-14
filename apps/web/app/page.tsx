"use client";

/**
 * page.tsx — official-site opening
 *
 * Owner decision (2026-07-14): the waitlist funnel is retired; guests opening
 * the official site are greeted by one of the three launch films at random,
 * once per browser session (/explainer/index.html does the random pick on
 * every load). Same-session returns to "/" render the landing (no loop).
 * SEO preserved: the landing stays in the prerendered HTML — the film
 * hand-off is a client decision on mount. See lib/openingFilm.ts.
 *
 * Auth redirect preserved VERBATIM:
 *   if (ready && user) router.replace("/command")
 */

import LandingPageV2 from "@/components/LandingPageV2";
import { useAuth } from "@/hooks/useAuth";
import { claimOpeningFilm, goToOpeningFilm } from "@/lib/openingFilm";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function HomePage() {
    const router = useRouter();
    const { user, ready } = useAuth();
    const [handingOffToFilm, setHandingOffToFilm] = useState(false);

    useEffect(() => {
        if (!ready) return;
        if (user) {
            router.replace("/command");
            return;
        }
        // Guest first open this session → cinematic opening (random film).
        if (claimOpeningFilm()) {
            setHandingOffToFilm(true);
            goToOpeningFilm();
        }
    }, [ready, user, router]);

    // Near-black cover while the browser swaps to the film — matches the
    // films' own background so the hand-off reads as one cut, not a flash.
    if (handingOffToFilm) {
        return <div aria-hidden style={{ position: "fixed", inset: 0, background: "#070709" }} />;
    }

    return <LandingPageV2 />;
}
