/**
 * #1101 — client side of the private-response cache boundary.
 *
 * Pins that account-scoped fetches (identity, profile, CV/files,
 * applications, billing — everything in lib/api.ts) run with
 * `cache: "no-store"`, and that no future call site can silently bypass
 * the apiFetch wrapper.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchMe, requestJson } from "@/lib/api";
import { clearAuth } from "@/lib/auth";

describe("#1101 client no-store boundary", () => {
  const fetchSpy = vi.fn();

  beforeEach(() => {
    fetchSpy.mockReset();
    fetchSpy.mockResolvedValue(
      new Response(
        JSON.stringify({ email: null, role: "guest", authenticated: false }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requestJson sends cache: no-store", async () => {
    await requestJson("/api/v1/applications");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({ cache: "no-store" });
  });

  it("fetchMe (identity) sends cache: no-store", async () => {
    await fetchMe();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({ cache: "no-store" });
  });

  it("logout (clearAuth) sends cache: no-store", async () => {
    await clearAuth();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({ cache: "no-store" });
  });

  it("no raw `await fetch(` call sites remain in lib/api.ts", () => {
    // Static guard: every API call must go through apiFetch so a new
    // endpoint helper cannot silently drop the no-store boundary.
    const source = readFileSync(join(process.cwd(), "lib", "api.ts"), "utf8");
    expect(source.match(/await fetch\(/g)).toBeNull();
    expect((source.match(/await apiFetch\(/g) ?? []).length).toBeGreaterThan(0);
  });
});
