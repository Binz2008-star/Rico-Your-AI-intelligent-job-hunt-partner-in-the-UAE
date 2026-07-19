/**
 * Duplicate-search guard — command page behavior after a timed-out search.
 *
 * Production evidence (2026-07-19): the 45s client timeout auto-resent a job
 * search whose ~55s provider cascade was still running server-side — two
 * executions, two search_performed events, double provider cost for one
 * user intent. The fix: one user turn mints ONE operation_id shared by every
 * transport attempt, and after an aborted attempt the page WAITS on the
 * operation (poll → recover from history) instead of blindly re-sending.
 *
 * The stream mock aborts immediately — the same AbortError code path the
 * hard 45s timer triggers (page.tsx: setTimeout(() => controller.abort(),
 * 45_000) — unchanged by this fix). Poll budget semantics are unit-tested
 * separately in command-operation-poll.test.ts.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => "/command",
}));
vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: any) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

const mockFetchMe = vi.fn();
const mockFetchChatHistory = vi.fn();
const mockSendChat = vi.fn();
const mockSendChatPublic = vi.fn();
const mockSendChatStream = vi.fn();
const mockSendChatStreamPublic = vi.fn();
const mockPoll = vi.fn();

const FIXED_OP_ID = "op_web_test_fixed_0001";

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        fetchMe: (...args: unknown[]) => mockFetchMe(...args),
        fetchChatHistory: (...args: unknown[]) => mockFetchChatHistory(...args),
        sendChat: (...args: unknown[]) => mockSendChat(...args),
        sendChatPublic: (...args: unknown[]) => mockSendChatPublic(...args),
        sendChatStream: (...args: unknown[]) => mockSendChatStream(...args),
        sendChatStreamPublic: (...args: unknown[]) => mockSendChatStreamPublic(...args),
        pollOperationUntilSettled: (...args: unknown[]) => mockPoll(...args),
        mintOperationId: () => FIXED_OP_ID,
    };
});

import CommandPage from "@/app/command/page";

const SEARCH_TEXT = "find hse manager jobs in dubai";

function abortError(): Error {
    return Object.assign(new Error("The operation was aborted."), { name: "AbortError" });
}

/** Stream that aborts immediately — the timed-out-primary code path. */
async function* abortingStream(): AsyncGenerator<unknown> {
    throw abortError();
}

const EMPTY_HISTORY = { messages: [], total: 0, has_more: false };

async function typeSearchAndSend() {
    const ta = (await screen.findByTestId("composer-textarea")) as HTMLTextAreaElement;
    await userEvent.type(ta, `${SEARCH_TEXT}{Enter}`);
}

beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-01");
    mockFetchChatHistory.mockResolvedValue(EMPTY_HISTORY);
    mockSendChatStream.mockImplementation(() => abortingStream());
    mockSendChatStreamPublic.mockImplementation(() => abortingStream());
});

async function renderAuthenticated() {
    mockFetchMe.mockResolvedValue({ authenticated: true, role: "user", email: "u@test.com", name: "U" });
    render(<CommandPage />);
    // The history effect only runs once chatAudience === "authenticated" —
    // sending before that would be silently dropped by the composer guard.
    await waitFor(() => expect(mockFetchChatHistory).toHaveBeenCalled());
}

describe("duplicate-search guard — authenticated timeout path", () => {
    it("does not re-send while the operation is still running (T1)", async () => {
        mockPoll.mockResolvedValue("still_running");
        await renderAuthenticated();

        await typeSearchAndSend();

        await waitFor(() => expect(mockPoll).toHaveBeenCalled());
        // Waiting on a live operation must never start a second backend search.
        expect(mockSendChat).not.toHaveBeenCalled();
        expect(mockSendChatStream).toHaveBeenCalledTimes(1);
        // Manual-retry affordance surfaces via the existing timeout message.
        await screen.findByText(/taking longer than usual/i);
    });

    it("shares ONE minted operation_id across the turn's attempts (T2)", async () => {
        mockPoll.mockResolvedValue("still_running");
        await renderAuthenticated();

        await typeSearchAndSend();

        await waitFor(() => expect(mockPoll).toHaveBeenCalled());
        // sendChatStream(message, signal, language, operationId)
        expect(mockSendChatStream.mock.calls[0][3]).toBe(FIXED_OP_ID);
        // pollOperationUntilSettled(operationId, signal)
        expect(mockPoll.mock.calls[0][0]).toBe(FIXED_OP_ID);
    });

    it("recovers the late result bound to the EXACT operation_id — never the newest row", async () => {
        mockPoll.mockResolvedValue("completed");
        const exactRow = {
            role: "assistant",
            content: JSON.stringify({
                type: "job_matches",
                operation_id: FIXED_OP_ID,
                message: "I found 5 strong UAE job matches for you.",
                matches: [{ title: "QHSE Manager", company: "Combi Lift", score: 90 }],
            }),
        };
        // NEWER decoy from a different turn/conversation — must NOT be rendered.
        const decoyRow = {
            role: "assistant",
            content: JSON.stringify({
                type: "job_matches",
                operation_id: "op_web_some_other_turn",
                message: "Decoy result from another turn.",
                matches: [],
            }),
        };
        mockFetchChatHistory.mockImplementation(async (limit: number) =>
            limit === 10
                ? { messages: [exactRow, decoyRow], total: 2, has_more: false }
                : EMPTY_HISTORY,
        );
        await renderAuthenticated();

        await typeSearchAndSend();

        await screen.findByText("I found 5 strong UAE job matches for you.");
        expect(screen.queryByText("Decoy result from another turn.")).toBeNull();
        // The late result was recovered, not silently discarded — and without
        // a second execution.
        expect(mockSendChat).not.toHaveBeenCalled();
    });

    it("falls back to ONE guard-protected re-send when the exact result row is not visible", async () => {
        mockPoll.mockResolvedValue("completed");
        // History only holds rows from other turns — no exact-operation match.
        const decoyRow = {
            role: "assistant",
            content: JSON.stringify({
                type: "job_matches",
                operation_id: "op_web_some_other_turn",
                message: "Decoy result from another turn.",
                matches: [],
            }),
        };
        mockFetchChatHistory.mockImplementation(async (limit: number) =>
            limit === 10
                ? { messages: [decoyRow], total: 1, has_more: false }
                : EMPTY_HISTORY,
        );
        // The server guard answers the duplicate send with the completed
        // status instead of re-executing.
        mockSendChat.mockResolvedValue({
            type: "search_status",
            message: "That search already finished — its results are saved in this conversation.",
        });
        await renderAuthenticated();

        await typeSearchAndSend();

        await waitFor(() => expect(mockSendChat).toHaveBeenCalledTimes(1));
        expect(mockSendChat.mock.calls[0][2]).toBe(FIXED_OP_ID);
        expect(screen.queryByText("Decoy result from another turn.")).toBeNull();
    });

    it("allows exactly one retry after a terminal operation, same id (T3)", async () => {
        mockPoll.mockResolvedValue("terminal");
        mockSendChat.mockResolvedValue({ type: "response", message: "retried ok" });
        await renderAuthenticated();

        await typeSearchAndSend();

        await waitFor(() => expect(mockSendChat).toHaveBeenCalledTimes(1));
        // sendChat(message, signal, operationId, language) — same turn id, so
        // the server-side guard keeps the final word even on a stale view.
        expect(mockSendChat.mock.calls[0][2]).toBe(FIXED_OP_ID);
        await screen.findByText("retried ok");
    });

    it("stops cleanly when the user cancels during the wait (T5)", async () => {
        mockPoll.mockResolvedValue("aborted");
        await renderAuthenticated();

        await typeSearchAndSend();

        await screen.findByText("You stopped this reply.");
        expect(mockSendChat).not.toHaveBeenCalled();
    });

    it("leaves a normal fast search unchanged (T4)", async () => {
        mockSendChatStream.mockImplementation(async function* () {
            yield {
                type: "done",
                response: { type: "job_matches", message: "Found 2 matches.", matches: [] },
            };
        });
        await renderAuthenticated();

        await typeSearchAndSend();

        await screen.findByText("Found 2 matches.");
        expect(mockPoll).not.toHaveBeenCalled();
        expect(mockSendChat).not.toHaveBeenCalled();
        expect(mockSendChatStream).toHaveBeenCalledTimes(1);
    });
});

describe("duplicate-search guard — public path unchanged", () => {
    it("keeps the legacy single retry for guests (no polling; guests never run real searches)", async () => {
        mockFetchMe.mockResolvedValue({ authenticated: false, role: "guest", email: null, guest: true });
        mockSendChatPublic.mockResolvedValue({ type: "response", message: "public retry ok" });
        render(<CommandPage />);
        await screen.findByText("Sign up free");

        await typeSearchAndSend();

        await waitFor(() => expect(mockSendChatPublic).toHaveBeenCalledTimes(1));
        expect(mockPoll).not.toHaveBeenCalled();
        // The public retry also carries the turn's operation_id so the
        // server-side guard applies if a real search ever runs for guests.
        expect(mockSendChatPublic.mock.calls[0][3]).toBe(FIXED_OP_ID);
        await screen.findByText("public retry ok");
    });
});
