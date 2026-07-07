/**
 * TC-11 regression: the optimistic "operation state" chip shown while the chat
 * server responds must not flash a job-search state for self-referential
 * profile/career questions. The tokens "role"/"position" are ambiguous (search
 * noun AND profile noun); the old flat classifier matched them under search, so
 * "what is my current role?" flashed "Searching UAE jobs…" before the real
 * profile answer arrived.
 */
import { describe, expect, it } from "vitest";

import { pickOperationState } from "@/app/command/operationState";

describe("pickOperationState (TC-11)", () => {
  it.each([
    "what is my current role?",
    "what's my role?",
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
