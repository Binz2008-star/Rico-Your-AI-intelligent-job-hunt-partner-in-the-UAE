/**
 * Regression tests for the "Analyze my current career trajectory" command routing bug.
 *
 * ROOT CAUSE: orchestrationApi.executeCommand() sends the message text to
 * sendAgentChat() → /api/v1/agent/chat. The backend has no trajectory-specific
 * intent handler, so the request falls through to the generic LLM path with
 * no profile or application context injected.
 *
 * The separate orchestrationApi.getTrajectory() path builds a real data-driven
 * trajectory from profile + applications + history, but executeCommand() never
 * calls it — the two paths are completely disconnected.
 *
 * These tests pin the current (broken) behaviour so any fix is clearly visible,
 * and provide a spec for what the correct behaviour should be.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

const mockSendAgentChat = vi.fn();
const mockGetTrajectory = vi.fn();

vi.mock("@/lib/api", () => ({
  sendAgentChat: (...args: unknown[]) => mockSendAgentChat(...args),
  fetchChatHistory: vi.fn().mockResolvedValue({ messages: [] }),
  fetchProfile: vi.fn().mockResolvedValue(null),
  getApplications: vi.fn().mockResolvedValue(null),
  getJobs: vi.fn().mockResolvedValue(null),
  uploadCV: vi.fn(),
}));

const { orchestrationApi } = await import("@/lib/api/orchestration");

// Patch getTrajectory on the singleton after import
const originalGetTrajectory = orchestrationApi.getTrajectory;
afterEach(() => {
  orchestrationApi.getTrajectory = originalGetTrajectory;
  mockSendAgentChat.mockReset();
  mockGetTrajectory.mockReset();
});

describe("orchestrationApi.executeCommand — trajectory command routing", () => {
  it("sends the raw text to sendAgentChat without trajectory data (current behaviour)", async () => {
    mockSendAgentChat.mockResolvedValueOnce({
      success: true,
      message: "Here is a generic response about your career.",
      actions: [],
      execution_time_ms: 0,
    });

    const result = await orchestrationApi.executeCommand(
      "Analyze my current career trajectory.",
    );

    expect(mockSendAgentChat).toHaveBeenCalledWith({
      message: "Analyze my current career trajectory.",
    });
    // Response comes back but carries no actual trajectory nodes
    expect(result.success).toBe(true);
  });

  it("does NOT call getTrajectory during executeCommand (current behaviour — bug)", async () => {
    mockSendAgentChat.mockResolvedValueOnce({
      success: true,
      message: "generic",
      actions: [],
      execution_time_ms: 0,
    });
    orchestrationApi.getTrajectory = mockGetTrajectory;

    await orchestrationApi.executeCommand("Analyze my current career trajectory.");

    // BUG: getTrajectory is never called, so live profile/application context
    // is never injected into the agent chat message.
    expect(mockGetTrajectory).not.toHaveBeenCalled();
  });
});

describe("orchestrationApi.getTrajectory — standalone data path works", () => {
  it("returns empty nodes when fetchProfile returns null", async () => {
    // fetchProfile mock returns null (already mocked above)
    const result = await orchestrationApi.getTrajectory();
    // Null profile → profile-pending phase, empty nodes
    expect(result.nodes).toEqual([]);
    expect(result.currentPhase).toBe("profile-pending");
  });
});
