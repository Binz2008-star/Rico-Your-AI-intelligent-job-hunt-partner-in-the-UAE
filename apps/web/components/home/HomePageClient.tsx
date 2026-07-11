"use client";

import LandingPageV2 from "@/components/LandingPageV2";
import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Existing live homepage behavior, extracted unchanged so the server page can
 * select between the live landing and the pre-launch waitlist surface. */
export function HomePageClient() {
  const router = useRouter();
  const { user, ready } = useAuth();

  useEffect(() => {
    if (ready && user) {
      router.replace("/command");
    }
  }, [ready, user, router]);

  return <LandingPageV2 />;
}
