"use client";

/**
 * page.tsx
 *
 * Only change from previous version:
 *   - import LandingPageV2  →  import LandingPageV3
 *
 * Auth redirect is preserved VERBATIM:
 *   if (ready && user) router.replace("/command")
 *
 * LandingPageV2 is NOT deleted — this file simply no longer imports it.
 */

import LandingPageV3 from "@/components/LandingPageV3";
import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function HomePage() {
    const router = useRouter();
    const { user, ready } = useAuth();

    useEffect(() => {
        if (ready && user) {
            router.replace("/command");
        }
    }, [ready, user, router]);

    return <LandingPageV3 />;
}
