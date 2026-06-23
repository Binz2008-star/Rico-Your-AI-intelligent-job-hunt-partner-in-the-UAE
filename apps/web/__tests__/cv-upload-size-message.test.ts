import { describe, expect, it } from "vitest";

import { translations } from "@/lib/translations";

// User-facing upload size copy: a clear "too large" message (EN + AR), the new
// 25 MB limit, and the generic CV error no longer pinning the reason on size.
describe("CV upload size messaging", () => {
  it("has a friendly English too-large message at 25MB", () => {
    const msg = translations.en.cmdCvTooLarge;
    expect(msg).toBeTruthy();
    expect(msg).toContain("25MB");
    expect(msg.toLowerCase()).toContain("too large");
    expect(msg.toLowerCase()).toContain("compress");
  });

  it("has a friendly Arabic too-large message at 25 ميغابايت", () => {
    const msg = translations.ar.cmdCvTooLarge;
    expect(msg).toBeTruthy();
    expect(msg).toContain("25 ميغابايت");
    expect(msg).toContain("كبير");
  });

  it("no longer blames size in the generic CV error", () => {
    expect(translations.en.cmdCvUploadErr).not.toContain("10 MB");
    expect(translations.ar.cmdCvUploadErr).not.toContain("10 ميغابايت");
  });

  it("onboarding hint shows the new 25 MB limit", () => {
    expect(translations.en.onboardingPdfOnly).toContain("25 MB");
    expect(translations.ar.onboardingPdfOnly).toContain("25 ميغابايت");
  });
});
