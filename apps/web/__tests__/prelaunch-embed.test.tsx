import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

// eslint-disable-next-line @typescript-eslint/no-var-requires
import nextConfig from "../next.config.js";
import { WaitlistLanding } from "@/components/waitlist/WaitlistLanding";
import { renderWithProviders as render } from "./test-utils";

type HeaderRule = { source: string; headers: { key: string; value: string }[] };

function headerMap(headers: { key: string; value: string }[]) {
  const map: Record<string, string> = {};
  for (const h of headers) map[h.key.toLowerCase()] = h.value;
  return map;
}

describe("launch-film framing headers", () => {
  it("permits same-origin framing for /explainer/* and denies it for the rest of the app", async () => {
    const rules = (await (nextConfig as { headers: () => Promise<HeaderRule[]> }).headers());

    const explainer = rules.find((r) => r.source === "/explainer/:path*");
    const app = rules.find((r) => r.source.includes("(?!explainer/)"));

    expect(explainer, "an explicit /explainer/:path* header rule must exist").toBeTruthy();
    expect(app, "the strict app rule must exclude /explainer/").toBeTruthy();

    const eh = headerMap(explainer!.headers);
    const ah = headerMap(app!.headers);

    // Launch film → embeddable in a same-origin iframe.
    expect(eh["x-frame-options"]).toBe("SAMEORIGIN");
    expect(eh["content-security-policy-report-only"]).toContain("frame-ancestors 'self'");

    // Every other page → never framable.
    expect(ah["x-frame-options"]).toBe("DENY");
    expect(ah["content-security-policy-report-only"]).toContain("frame-ancestors 'none'");
    expect(app!.source).toContain("(?!explainer/)");

    // The exception must not weaken the shared protections.
    expect(eh["x-content-type-options"]).toBe("nosniff");
    expect(eh["strict-transport-security"]).toContain("max-age=");
  });
});

describe("WaitlistLanding shows the film and the form together", () => {
  it("renders the embedded same-origin film and the waitlist form on one page", () => {
    render(<WaitlistLanding />);

    const frame = document.querySelector('iframe[src="/explainer/index.html"]');
    expect(frame, "the launch film must be embedded in-page").toBeTruthy();
    expect(frame?.getAttribute("title")).toBe("Rico — Launch Film");

    // The film is capped inside the copy column, not a standalone full-width banner
    // that would push the form below a huge empty area.
    expect(document.querySelector(".atl-waitlist-copy .atl-waitlist-film")).toBeTruthy();

    // The waitlist form stays present alongside the film.
    expect(screen.getByRole("button", { name: "Reserve early access" })).toBeTruthy();
    expect(screen.getByPlaceholderText("Email address *")).toBeTruthy();
  });
});
