import { describe, expect, it } from "vitest";

import { buildMissionToday, PROFILE_READY_THRESHOLD } from "../lib/mission/today";

describe("buildMissionToday", () => {
  it("returns no actions when nothing is pending and the profile is ready", () => {
    const actions = buildMissionToday({
      pendingDrafts: 0,
      followUpsDue: 0,
      completenessScore: 1,
      newMatches: 0,
    });
    expect(actions).toEqual([]);
  });

  it("orders drafts > follow-ups > profile > matches", () => {
    const actions = buildMissionToday({
      pendingDrafts: 2,
      followUpsDue: 1,
      completenessScore: 0.5,
      newMatches: 9,
    });
    expect(actions.map((a) => a.kind)).toEqual([
      "approve_draft",
      "follow_up",
      "complete_profile",
      "review_matches",
    ]);
  });

  it("omits the profile nudge when the score is unknown (null)", () => {
    const actions = buildMissionToday({
      pendingDrafts: 0,
      followUpsDue: 0,
      completenessScore: null,
      newMatches: 0,
    });
    expect(actions.find((a) => a.kind === "complete_profile")).toBeUndefined();
  });

  it("omits the profile nudge at or above the readiness threshold", () => {
    const actions = buildMissionToday({
      pendingDrafts: 0,
      followUpsDue: 0,
      completenessScore: PROFILE_READY_THRESHOLD,
      newMatches: 0,
    });
    expect(actions.find((a) => a.kind === "complete_profile")).toBeUndefined();
  });

  it("carries counts and destinations through for badge display", () => {
    const actions = buildMissionToday({
      pendingDrafts: 3,
      followUpsDue: 0,
      completenessScore: 1,
      newMatches: 0,
    });
    expect(actions[0]).toMatchObject({ kind: "approve_draft", count: 3, href: "/queue" });
  });
});
