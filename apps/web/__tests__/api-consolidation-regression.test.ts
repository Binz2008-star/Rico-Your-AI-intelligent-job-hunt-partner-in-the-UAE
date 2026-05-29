import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, register, resendVerification, sendAgentChat, verifyLink, verifyLinkBatch } from "@/lib/api";

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

describe("register — ApiError on failure", () => {
  it("throws ApiError with statusCode 409 on duplicate email", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "Email already exists" }, 409));
    await expect(register("a@b.com", "pass")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && (e as ApiError).statusCode === 409,
    );
  });

  it("throws ApiError with statusCode 422 on validation error", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "Validation error" }, 422));
    await expect(register("bad", "pw")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && (e as ApiError).statusCode === 422,
    );
  });

  it("returns email and role on success", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ email: "a@b.com", role: "user" }, 200));
    const result = await register("a@b.com", "pass");
    expect(result.email).toBe("a@b.com");
    expect(result.role).toBe("user");
  });
});

describe("resendVerification — ApiError on failure", () => {
  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "Too many requests" }, 429));
    await expect(resendVerification("a@b.com")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && (e as ApiError).statusCode === 429,
    );
  });

  it("returns message on success", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ message: "Sent" }, 200));
    const result = await resendVerification("a@b.com");
    expect(result.message).toBe("Sent");
  });
});

describe("sendAgentChat — ApiError on failure, response shape", () => {
  it("throws ApiError on 401", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "Unauthorized" }, 401));
    await expect(sendAgentChat({ message: "hello" })).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && (e as ApiError).statusCode === 401,
    );
  });

  it("returns validated response shape on success", async () => {
    const payload = {
      success: true,
      message: "Done",
      actions: [],
      tool_used: "jobs",
      execution_time_ms: 120,
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(payload, 200));
    const result = await sendAgentChat({ message: "find jobs" });
    expect(result.success).toBe(true);
    expect(result.message).toBe("Done");
    expect(Array.isArray(result.actions)).toBe(true);
    expect(result.execution_time_ms).toBe(120);
  });

  it("defaults actions to [] and execution_time_ms to 0 when omitted", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, message: "ok" }, 200));
    const result = await sendAgentChat({ message: "test" });
    expect(result.actions).toEqual([]);
    expect(result.execution_time_ms).toBe(0);
  });
});

describe("verifyLink — ApiError on failure", () => {
  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "Server error" }, 500));
    await expect(verifyLink("https://example.com")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError,
    );
  });

  it("returns link result on success", async () => {
    const result = {
      status: "live",
      http_status: 200,
      error_message: null,
      verified_at: "2026-05-29T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(result, 200));
    const data = await verifyLink("https://example.com");
    expect(data.status).toBe("live");
    expect(data.http_status).toBe(200);
  });
});

describe("verifyLinkBatch — ApiError on failure", () => {
  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: "error" }, 500));
    await expect(verifyLinkBatch(["https://example.com"])).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError,
    );
  });

  it("returns map of url → result on success", async () => {
    const batch = {
      "https://a.com": { status: "live", http_status: 200, error_message: null, verified_at: "2026-05-29T00:00:00Z" },
      "https://b.com": { status: "expired", http_status: 404, error_message: "Not found", verified_at: "2026-05-29T00:00:00Z" },
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(batch, 200));
    const data = await verifyLinkBatch(["https://a.com", "https://b.com"]);
    expect(data["https://a.com"].status).toBe("live");
    expect(data["https://b.com"].status).toBe("expired");
  });
});
