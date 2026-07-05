"use client";

import LandingPageV2 from "@/components/LandingPageV2";
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

    return <LandingPageV2 />;
}
