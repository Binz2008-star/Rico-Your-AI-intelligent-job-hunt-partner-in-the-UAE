import { describe, expect, it, vi } from "vitest";

// The command page pulls in browser-only deps at module load; stub the ones that
// would otherwise fail in jsdom so we can import the pure helpers under test.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

import { formatTrajectory, looksLikeTrajectoryAnalysis } from "@/lib/trajectoryHelpers";
import type { TrajectoryForecast } from "@/lib/api/orchestration";

describe("looksLikeTrajectoryAnalysis", () => {
  it("matches the trajectory-analysis quick actions", () => {
    expect(looksLikeTrajectoryAnalysis("Analyze my current career trajectory.")).toBe(true);
    expect(looksLikeTrajectoryAnalysis("Map my best next career move based on my profile.")).toBe(true);
    expect(looksLikeTrajectoryAnalysis("analyse my trajectory")).toBe(true);
    expect(looksLikeTrajectoryAnalysis("show me my career trajectory")).toBe(true);
  });

  it("does not hijack ordinary chat or job-search messages", () => {
    expect(looksLikeTrajectoryAnalysis("Find me a backend engineer job in Dubai")).toBe(false);
    expect(looksLikeTrajectoryAnalysis("What jobs match my CV?")).toBe(false);
    expect(looksLikeTrajectoryAnalysis("Help me prepare for an interview")).toBe(false);
    expect(looksLikeTrajectoryAnalysis("hello")).toBe(false);
  });
});

describe("formatTrajectory", () => {
  const forecast: TrajectoryForecast = {
    currentPhase: "active-pipeline",
    nodes: [
      { id: "a", title: "Senior Engineer", description: "Current role", probability: 0.9, timeline: "Now", status: "current" },
      { id: "b", title: "Engineering Lead", description: "Primary target", probability: 0.6, timeline: "Build pipeline", status: "upcoming" },
    ],
  };

  it("renders each node with title, timeline, description, and rounded confidence", () => {
    const out = formatTrajectory(forecast);
    expect(out).toContain("Senior Engineer");
    expect(out).toContain("_(Now)_");
    expect(out).toContain("Current role");
    expect(out).toContain("Confidence: 90%");
    expect(out).toContain("Engineering Lead");
    expect(out).toContain("Confidence: 60%");
  });

  it("uses status markers (current/upcoming/completed)", () => {
    const out = formatTrajectory(forecast);
    expect(out).toContain("▶"); // current
    expect(out).toContain("○"); // upcoming
  });
});
