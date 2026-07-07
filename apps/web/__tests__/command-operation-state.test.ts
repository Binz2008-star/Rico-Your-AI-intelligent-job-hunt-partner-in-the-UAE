/**
 * TC-11 regression: the optimistic "operation state" chip shown while the chat
 * server responds must not flash a job-search state for self-referential
 * profile/career questions. The tokens "role"/"position" are ambiguous (search
 * noun AND profile noun); the old flat classifier matched them under search, so
 * "what is my current role?" flashed "Searching UAE jobs…" before the real
 * profile answer arrived.
 */
import { describe, expect, it } from "vitest";

import { isRetryableJobSearchIntent, pickOperationState } from "@/app/command/operationState";

describe("pickOperationState (TC-11)", () => {
  it.each([
    "what is my current role?",
    "what's my role?",
    "what is my position?",
    "show me my target roles",
    "my position at the company",
    "what is my profile?",
    "review my profile",
    "improve my cv",
  ])("does NOT flash a job search for a profile/career self-query: %s", (msg) => {
    const guess = pickOperationState(msg.toLowerCase());
    expect(guess?.state).not.toBe("searching");
    expect(guess?.messageKey).not.toBe("cmdWorkingJobs");
  });

  it.each([
    "what is my current role?",
    "what is my position?",
    "review my profile",
    "my experience and skills",
  ])("routes a profile self-query to the reading/profile chip: %s", (msg) => {
    expect(pickOperationState(msg.toLowerCase())).toEqual({
      state: "reading",
      messageKey: "cmdWorkingProfile",
    });
  });

  it.each([
    "find me a job",
    "search for developer roles",
    "find jobs from my CV",
    "show me job openings",
    "developer roles in Dubai", // bare role noun, no self-reference
    "find me HSE Officer roles in Dubai",
    "sales manager position in Dubai based on my CV", // CV modifier, still a search
    "cybersecurity career role in Dubai", // "career" + role, still a search
    "finance career roles in Abu Dhabi",
  ])("still flashes search for an explicit job hunt: %s", (msg) => {
    expect(pickOperationState(msg.toLowerCase())).toEqual({
      state: "searching",
      messageKey: "cmdWorkingJobs",
    });
  });

  it("keeps the other operation buckets intact", () => {
    expect(pickOperationState("upgrade my plan")?.state).toBe("checking");
    expect(pickOperationState("track my application status")?.state).toBe("reviewing");
    expect(pickOperationState("what should i do next in my career")?.state).toBe("extracting");
    expect(pickOperationState("help me prep for an interview")?.state).toBe("extracting");
    expect(pickOperationState("hello there")).toBeNull();
  });
});

describe("isRetryableJobSearchIntent — decoupled timeout/retry guard (TC-11 item 7 + Codex P2s)", () => {
  // Must NOT be retried as a search — profile/self-reference (item 7) and
  // applied/saved/opened lifecycle lists (Codex P2s).
  it.each([
    "what is my current role?",
    "what is my profile?",
    "what is my position?",
    "what's my role?",
    "review my profile",
    "improve my cv",
    "my position at the company",
    "show me my target roles",
    "show my applied jobs", // Codex P2 — applied lifecycle
    "status of my applied jobs",
    "show my saved jobs", // Codex P2 — saved lifecycle
    "my saved jobs",
    "jobs I opened without applying",
  ])("does NOT retry as a job search: %s", (msg) => {
    expect(isRetryableJobSearchIntent(msg)).toBe(false);
  });

  // Must retry as a search — real job hunts, including CV-based, career-role,
  // comparison-to-current-role, and subscription-word phrasing (Codex P2s), plus Arabic.
  it.each([
    "find me HSE Officer roles in Dubai",
    "search for developer jobs",
    "developer roles in Dubai",
    "sales manager position in Dubai based on my CV",
    "cybersecurity career role in Dubai",
    "finance career roles in Abu Dhabi",
    "roles similar to my current role in Dubai", // Codex P2 — comparison basis
    "positions like my current position",
    "find jobs with relocation package", // Codex P2 — subscription word in a search
    "ابحث عن وظائف", // Arabic: "search for jobs"
  ])("retries as a job search: %s", (msg) => {
    expect(isRetryableJobSearchIntent(msg)).toBe(true);
  });
});
