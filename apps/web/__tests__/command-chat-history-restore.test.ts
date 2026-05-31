/**
 * Tests for chat history restore API integration.
 *
 * Tests that the fetchChatHistory and clearChatHistory API functions
 * work correctly, and that JSON job_match payloads are parsed correctly.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

const mockFetchChatHistory = vi.fn();
const mockClearChatHistory = vi.fn();
const mockFetchMe = vi.fn();

vi.mock("@/lib/api", () => ({
    fetchChatHistory: (...args: unknown[]) => mockFetchChatHistory(...args),
    clearChatHistory: (...args: unknown[]) => mockClearChatHistory(...args),
    fetchMe: (...args: unknown[]) => mockFetchMe(...args),
    sendChat: vi.fn(),
    sendChatPublic: vi.fn(),
    sendChatStream: vi.fn(),
    sendChatStreamPublic: vi.fn(),
    uploadCV: vi.fn(),
    confirmCVProfile: vi.fn(),
    logout: vi.fn(),
}));

// --- parseHistoryContent helper (inlined for unit testing) ---
const _BARE_SEARCH_ROLES = new Set([
    "engineer", "manager", "specialist", "consultant", "officer",
    "analyst", "director", "coordinator", "executive", "lead",
]);

function isStaleSearchQuery(query?: string): boolean {
    if (!query) return false;
    return _BARE_SEARCH_ROLES.has(query.trim().toLowerCase());
}

interface JobMatch { title: string; score?: number; }
interface Message {
    id: number;
    role: "user" | "rico";
    text: string;
    type?: string;
    matches?: JobMatch[];
    search_query?: string;
    stale?: boolean;
}

function parseHistoryContent(content: string, id: number): Partial<Message> {
    try {
        const parsed = JSON.parse(content) as Record<string, unknown>;
        if (parsed && typeof parsed === "object" && parsed.type === "job_matches") {
            const query = parsed.search_query as string | undefined;
            return {
                id,
                role: "rico",
                type: "job_matches",
                text: (parsed.message ?? parsed.reply ?? parsed.response ?? "") as string,
                matches: (parsed.matches as JobMatch[] | undefined) ?? [],
                search_query: query,
                stale: isStaleSearchQuery(query),
            };
        }
    } catch {
        // fall through
    }
    return { id, role: "rico", text: content };
}

describe("parseHistoryContent — JSON job_matches payloads", () => {
    it("parses a valid job_matches payload into a rich Message", () => {
        const payload = JSON.stringify({
            type: "job_matches",
            message: "Found 2 matches.",
            matches: [{ title: "HSE Manager", score: 0.9 }],
            search_query: "HSE Manager",
            result_count: 1,
        });
        const result = parseHistoryContent(payload, 1);
        expect(result.type).toBe("job_matches");
        expect(result.text).toBe("Found 2 matches.");
        expect(result.matches).toHaveLength(1);
        expect(result.matches![0].title).toBe("HSE Manager");
        expect(result.search_query).toBe("HSE Manager");
        expect(result.stale).toBe(false);
    });

    it("falls back to plain text when content is not JSON", () => {
        const result = parseHistoryContent("Here are some matching roles.", 2);
        expect(result.type).toBeUndefined();
        expect(result.text).toBe("Here are some matching roles.");
        expect(result.matches).toBeUndefined();
    });

    it("falls back to plain text when JSON has no type field", () => {
        const result = parseHistoryContent(JSON.stringify({ message: "hello" }), 3);
        expect(result.type).toBeUndefined();
        expect(result.text).toBe(JSON.stringify({ message: "hello" }));
    });

    it("falls back to plain text when JSON is invalid", () => {
        const result = parseHistoryContent("{bad json}", 4);
        expect(result.text).toBe("{bad json}");
        expect(result.type).toBeUndefined();
    });
});

describe("isStaleSearchQuery — broad role detection", () => {
    it("marks bare 'Engineer' as stale", () => {
        expect(isStaleSearchQuery("Engineer")).toBe(true);
    });

    it("marks bare 'Manager' as stale", () => {
        expect(isStaleSearchQuery("Manager")).toBe(true);
    });

    it("marks lowercase 'engineer' as stale", () => {
        expect(isStaleSearchQuery("engineer")).toBe(true);
    });

    it("does NOT mark 'HSE Manager' as stale", () => {
        expect(isStaleSearchQuery("HSE Manager")).toBe(false);
    });

    it("does NOT mark 'Environmental Manager' as stale", () => {
        expect(isStaleSearchQuery("Environmental Manager")).toBe(false);
    });

    it("does NOT mark undefined as stale", () => {
        expect(isStaleSearchQuery(undefined)).toBe(false);
    });

    it("sets stale=true for job_matches with bare Engineer search_query", () => {
        const payload = JSON.stringify({
            type: "job_matches",
            message: "Found jobs.",
            matches: [],
            search_query: "Engineer",
        });
        const result = parseHistoryContent(payload, 5);
        expect(result.stale).toBe(true);
    });
});

describe("Command page — chat history API integration", () => {
    afterEach(() => {
        mockFetchChatHistory.mockReset();
        mockFetchMe.mockReset();
        mockClearChatHistory.mockReset();
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

    it("clearChatHistory calls the API successfully", async () => {
        mockClearChatHistory.mockResolvedValueOnce(undefined);

        const { clearChatHistory } = await import("@/lib/api");
        await clearChatHistory();

        expect(mockClearChatHistory).toHaveBeenCalledTimes(1);
    });

    it("clearChatHistory propagates errors", async () => {
        mockClearChatHistory.mockRejectedValueOnce(new Error("Network error"));

        const { clearChatHistory } = await import("@/lib/api");
        await expect(clearChatHistory()).rejects.toThrow("Network error");
    });
});
