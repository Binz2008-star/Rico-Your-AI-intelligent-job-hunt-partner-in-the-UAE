import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getApplicationStats } from "@/lib/api";

/**
 * Regression test for the pipeline canonical-source fix: getApplicationStats()
 * used to strip the backend's `total` field, forcing every consumer (sidebar
 * widget, /flow header) to re-derive "total" from a partial sum of named
 * status fields — guaranteeing the two could disagree (chat/sidebar/flow
 * showing different tracked-application counts for the same user).
 */

const mockFetch = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});
afterEach(() => {
  vi.restoreAllMocks();
  mockFetch.mockReset();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getApplicationStats — canonical total passthrough", () => {
  it("passes the backend's total through unmodified", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        total: 50,
        by_status: { applied: 3, saved: 47 },
        applied: 3,
        saved: 47,
        interview: 0,
        rejected: 0,
        offer: 0,
        follow_up_due: 0,
      }),
    );

    const stats = await getApplicationStats();

    expect(stats.total).toBe(50);
  });

  it("does not double-count total into named status fields", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        total: 3,
        by_status: { applied: 3 },
        applied: 3,
        saved: 0,
        interview: 0,
        rejected: 0,
        offer: 0,
        follow_up_due: 0,
      }),
    );

    const stats = await getApplicationStats();

    expect(stats.applied).toBe(3);
    expect(stats.total).toBe(3);
  });

  it("still drops the nested by_status object (not a flat number)", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        total: 1,
        by_status: { saved: 1 },
        saved: 1,
      }),
    );

    const stats = await getApplicationStats();

    expect(stats.by_status).toBeUndefined();
    expect(stats.saved).toBe(1);
  });
});
