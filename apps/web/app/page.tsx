import { HomePageClient } from "@/components/home/HomePageClient";
import { WaitlistLanding } from "@/components/waitlist/WaitlistLanding";
import { isWaitlistMode } from "@/lib/launch-mode";

/**
 * The existing landing remains intact in live mode. Waitlist mode is selected
 * server-side so the public page never flashes the live product CTA first.
 */
export default function HomePage() {
  return isWaitlistMode() ? <WaitlistLanding /> : <HomePageClient />;
}
