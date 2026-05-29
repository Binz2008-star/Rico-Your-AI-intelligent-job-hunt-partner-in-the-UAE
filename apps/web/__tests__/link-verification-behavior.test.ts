import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LinkVerificationResult } from "@/lib/api";

const mockVerifyLink = vi.fn<[string], Promise<LinkVerificationResult>>();
const mockVerifyLinkBatch = vi.fn<[string[]], Promise<Record<string, LinkVerificationResult>>>();

vi.mock("@/lib/api", () => ({
  verifyLink: (...args: [string]) => mockVerifyLink(...args),
  verifyLinkBatch: (...args: [string[]]) => mockVerifyLinkBatch(...args),
}));
vi.mock("@/lib/api/orchestration", () => ({}));

const { renderHook, act, waitFor } = await import("@testing-library/react");
const { useLinkVerification } = await import("@/hooks/useLinkVerification");

const LIVE: LinkVerificationResult = {
  status: "live",
  http_status: 200,
  error_message: null,
  verified_at: "2026-05-29T00:00:00Z",
};

const EXPIRED: LinkVerificationResult = {
  status: "expired",
  http_status: 404,
  error_message: "Not found",
  verified_at: "2026-05-29T00:00:00Z",
};

function makeSignal(id: string, applyUrl: string) {
  return {
    id,
    company: "ACME",
    role: "Engineer",
    matchScore: 80,
    momentum: "high" as const,
    location: "Dubai",
    timestamp: "2026-05-01T00:00:00Z",
    applyUrl,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

async function tickAndWait() {
  // Advance past the 500ms hook debounce
  await act(async () => {
    vi.advanceTimersByTime(600);
    // Flush all promises
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useLinkVerification — batch path", () => {
  it("calls verifyLinkBatch and maps results to signal IDs", async () => {
    const signals = [makeSignal("s1", "https://s1a.example.com"), makeSignal("s2", "https://s2a.example.com")];
    mockVerifyLinkBatch.mockResolvedValue({
      "https://s1a.example.com": LIVE,
      "https://s2a.example.com": EXPIRED,
    });

    const { result } = renderHook(() => useLinkVerification(signals));
    await tickAndWait();

    expect(mockVerifyLinkBatch).toHaveBeenCalled();
    expect(result.current.getLinkStatus("s1")).toBe("live");
    expect(result.current.getLinkStatus("s2")).toBe("expired");
  });

  it("falls back to individual verifyLink calls when batch throws", async () => {
    const signals = [makeSignal("s3", "https://s3a.example.com")];
    mockVerifyLinkBatch.mockRejectedValue(new Error("batch unavailable"));
    mockVerifyLink.mockResolvedValue(LIVE);

    const { result } = renderHook(() => useLinkVerification(signals));
    await tickAndWait();

    expect(mockVerifyLink).toHaveBeenCalledWith("https://s3a.example.com");
    expect(result.current.getLinkStatus("s3")).toBe("live");
  });

  it("sets needs_review when individual fallback also returns null (verifyLink throws)", async () => {
    const signals = [makeSignal("s4", "https://s4a.example.com")];
    mockVerifyLinkBatch.mockRejectedValue(new Error("batch fail"));
    mockVerifyLink.mockRejectedValue(new Error("link check failed"));

    const { result } = renderHook(() => useLinkVerification(signals));
    await tickAndWait();

    expect(result.current.getLinkStatus("s4")).toBe("needs_review");
  });
});

describe("useLinkVerification — signals without URLs", () => {
  it("skips signals that have no applyUrl or sourceUrl", async () => {
    const signals = [
      { id: "s6", company: "A", role: "B", matchScore: 50, momentum: "low" as const, location: "Dubai", timestamp: "" },
    ];

    const { result } = renderHook(() => useLinkVerification(signals));
    await tickAndWait();

    expect(result.current.getLinkStatus("s6")).toBeUndefined();
    expect(mockVerifyLinkBatch).not.toHaveBeenCalled();
    expect(mockVerifyLink).not.toHaveBeenCalled();
  });
});
