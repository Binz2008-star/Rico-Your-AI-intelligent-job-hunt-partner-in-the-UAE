import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware } from "../middleware";

// Teaser mode is ON by default (NEXT_PUBLIC_SITE_LIVE unset → SITE_LIVE=false).
// A redirect sets a `location` header; NextResponse.next() does not.
function call(url: string) {
  return middleware(new NextRequest(url));
}

describe("teaser gate — email verification & legal allowlist (P0 #1005)", () => {
  it("does NOT redirect /verify-email and keeps the ?token query intact", () => {
    const res = call("https://ricohunt.com/verify-email?token=abc");
    // Allowed → passes through untouched, so the token is preserved (no redirect
    // that would drop the query by rewriting to /explainer/).
    expect(res.headers.get("location")).toBeNull();
  });

  it("keeps /privacy and /terms reachable during the teaser", () => {
    for (const path of ["/privacy", "/terms"]) {
      const res = call(`https://ricohunt.com${path}`);
      expect(res.headers.get("location")).toBeNull();
    }
  });

  it("keeps the other auth-recovery doors open (login/signup/forgot/reset)", () => {
    for (const path of ["/login", "/signup", "/forgot-password", "/reset-password"]) {
      const res = call(`https://ricohunt.com${path}`);
      expect(res.headers.get("location")).toBeNull();
    }
  });

  it("still gates a normal app route (/dashboard) to the teaser film", () => {
    const res = call("https://ricohunt.com/dashboard");
    expect(res.headers.get("location")).toContain("/explainer");
  });
});
