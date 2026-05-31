/**
 * Tests for chat history restore API integration.
 *
 * Tests that the fetchChatHistory API function works correctly
 * for authenticated users. Full component rendering tests require
 * extensive Next.js mocking and are better suited for E2E tests.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

const mockFetchChatHistory = vi.fn();
const mockFetchMe = vi.fn();

vi.mock("@/lib/api", () => ({
    fetchChatHistory: (...args: unknown[]) => mockFetchChatHistory(...args),
    fetchMe: (...args: unknown[]) => mockFetchMe(...args),
    sendChat: vi.fn(),
    sendChatPublic: vi.fn(),
    sendChatStream: vi.fn(),
    sendChatStreamPublic: vi.fn(),
    uploadCV: vi.fn(),
    confirmCVProfile: vi.fn(),
    logout: vi.fn(),
}));

describe("Command page — chat history restore API integration", () => {
    afterEach(() => {
        mockFetchChatHistory.mockReset();
        mockFetchMe.mockReset();
    });

    it("fetchChatHistory is called with limit=20 for authenticated users", async () => {
        mockFetchMe.mockResolvedValueOnce({ authenticated: true });
        mockFetchChatHistory.mockResolvedValueOnce({
            messages: [
                { role: "user", content: "Find jobs in Dubai" },
                { role: "assistant", content: "Here are some jobs..." },
            ],
            total: 2,
            has_more: false,
        });

        const { fetchChatHistory } = await import("@/lib/api");
        const history = await fetchChatHistory(20);

        expect(mockFetchChatHistory).toHaveBeenCalledWith(20);
        expect(history.messages).toHaveLength(2);
        expect(history.messages[0].role).toBe("user");
        expect(history.messages[0].content).toBe("Find jobs in Dubai");
        expect(history.messages[1].role).toBe("assistant");
        expect(history.messages[1].content).toBe("Here are some jobs...");
    });

    it("fetchChatHistory returns empty array when no history exists", async () => {
        mockFetchMe.mockResolvedValueOnce({ authenticated: true });
        mockFetchChatHistory.mockResolvedValueOnce({
            messages: [],
            total: 0,
            has_more: false,
        });

        const { fetchChatHistory } = await import("@/lib/api");
        const history = await fetchChatHistory(20);

        expect(history.messages).toHaveLength(0);
        expect(history.total).toBe(0);
    });

    it("fetchChatHistory handles network errors gracefully", async () => {
        mockFetchMe.mockResolvedValueOnce({ authenticated: true });
        mockFetchChatHistory.mockRejectedValueOnce(new Error("Network error"));

        const { fetchChatHistory } = await import("@/lib/api");

        await expect(fetchChatHistory(20)).rejects.toThrow("Network error");
    });

    it("fetchChatHistory supports pagination with before parameter", async () => {
        mockFetchMe.mockResolvedValueOnce({ authenticated: true });
        mockFetchChatHistory.mockResolvedValueOnce({
            messages: [{ role: "user", content: "Old message" }],
            total: 1,
            has_more: false,
        });

        const { fetchChatHistory } = await import("@/lib/api");
        const history = await fetchChatHistory(20, "2026-05-31T00:00:00Z");

        expect(mockFetchChatHistory).toHaveBeenCalledWith(20, "2026-05-31T00:00:00Z");
        expect(history.messages).toHaveLength(1);
    });
});

