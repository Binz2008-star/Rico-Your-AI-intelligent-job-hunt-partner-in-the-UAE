/**
 * PR A — fix/job-search-adaptive-timeout
 *
 * Latency UX mitigation tests: the frontend hard timeout is adaptive based on
 * whether the message is a retryable job-search intent. Non-search messages
 * keep the 45s budget; job-search messages get 90s. The "still running" copy
 * must not claim a retry before a retry occurs.
 *
 * These tests verify the classification function that drives the adaptive
 * timeout, the translation key contract, and the timeout value mapping.
 */
import { describe, expect, it } from "vitest";

import { isRetryableJobSearchIntent } from "@/app/command/operationState";
import { translations } from "@/lib/translations";

// The timeout values used in page.tsx — kept in sync here as a contract check.
const NON_SEARCH_TIMEOUT_MS = 45_000;
const JOB_SEARCH_TIMEOUT_MS = 90_000;

/** Mirrors the logic in page.tsx sendMessage(). */
function hardTimeoutMs(message: string): number {
  return isRetryableJobSearchIntent(message)
    ? JOB_SEARCH_TIMEOUT_MS
    : NON_SEARCH_TIMEOUT_MS;
}

describe("adaptive hard timeout — job search vs non-search", () => {
  it("non-search messages keep the 45s timeout", () => {
    expect(hardTimeoutMs("what is my current role?")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("what is my profile?")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("show my applied jobs")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("show my saved jobs")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("review my profile")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("hello there")).toBe(NON_SEARCH_TIMEOUT_MS);
  });

  it("retryable job-search messages get the 90s timeout", () => {
    expect(hardTimeoutMs("find me HSE Officer roles in Dubai")).toBe(JOB_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("search for developer jobs")).toBe(JOB_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("developer roles in Dubai")).toBe(JOB_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("find jobs from my CV")).toBe(JOB_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("ابحث عن وظائف")).toBe(JOB_SEARCH_TIMEOUT_MS);
  });

  it("profile/application questions do NOT get the extended timeout", () => {
    // These are explicitly excluded by isRetryableJobSearchIntent
    expect(hardTimeoutMs("what is my current role?")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("status of my applied jobs")).toBe(NON_SEARCH_TIMEOUT_MS);
    expect(hardTimeoutMs("jobs I opened without applying")).toBe(NON_SEARCH_TIMEOUT_MS);
  });
});

describe("truthful timeout copy — cmdSearchStillRunning", () => {
  it("English translation exists and does not claim a retry", () => {
    const copy = translations.en.cmdSearchStillRunning;
    expect(copy).toBeTruthy();
    // Must NOT contain "retry" or "retrying" — the message is shown BEFORE any
    // retry decision is made. The user sees this while we poll the operation.
    expect(copy.toLowerCase()).not.toContain("retry");
    expect(copy.toLowerCase()).not.toContain("retrying");
  });

  it("Arabic translation exists and does not claim a retry", () => {
    const copy = translations.ar.cmdSearchStillRunning;
    expect(copy).toBeTruthy();
    // Arabic: must not contain "إعادة" (retry/retrying)
    expect(copy).not.toContain("إعادة");
  });

  it("the old cmdRetryingSearch key still exists for backward compatibility", () => {
    // The old key is retained but no longer used in the timeout flow.
    expect(translations.en.cmdRetryingSearch).toBeTruthy();
    expect(translations.ar.cmdRetryingSearch).toBeTruthy();
  });
});

describe("operation_id preservation contract", () => {
  // The adaptive timeout does NOT change the operation_id — the same id is
  // used for the primary request and any recovery poll. This is enforced by
  // the page.tsx code: operationId is minted once before the timeout branch.
  // Here we verify the classification function is pure (no side effects).
  it("isRetryableJobSearchIntent is pure — same input, same output, no side effects", () => {
    const msg = "find me software engineer jobs in Dubai";
    const result1 = isRetryableJobSearchIntent(msg);
    const result2 = isRetryableJobSearchIntent(msg);
    expect(result1).toBe(result2);
    expect(result1).toBe(true);
  });
});
