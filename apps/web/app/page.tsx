"use client";

/**
 * page.tsx — official-site opening
 *
 * Owner directive (2026-07-16): EVERY guest visit to "/" hands off to the
 * film chooser (/explainer/index.html) — no once-per-session gate. The
 * chooser owns the rotation: a randomized non-repeating cycle across
 * option-2 / option-3 / option-3b persisted in localStorage. SEO preserved:
 * the landing stays in the prerendered HTML — the film hand-off is a client
 * decision on mount. See lib/openingFilm.ts.
 *
 * Auth redirect preserved VERBATIM:
 *   if (ready && user) router.replace("/command")
 */

import LandingPageV2 from "@/components/LandingPageV2";
import { useAuth } from "@/hooks/useAuth";
import { claimAfterFilmLanding, goToOpeningFilm } from "@/lib/openingFilm";
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
        // Arriving from a film that just finished (`/?after-film=1`) → the
        // landing renders once; the marker is consumed so a reload rotates.
        if (claimAfterFilmLanding()) {
            return;
        }
        // Guest → cinematic opening, on every visit. The chooser advances the
        // non-repeating rotation, so back-to-back visits get different films.
        setHandingOffToFilm(true);
        goToOpeningFilm();
    }, [ready, user, router]);

    // Near-black cover while the browser swaps to the film — matches the
    // films' own background so the hand-off reads as one cut, not a flash.
    if (handingOffToFilm) {
        return <div aria-hidden style={{ position: "fixed", inset: 0, background: "#070709" }} />;
    }

    return <LandingPageV2 />;
}
