/**
 * Session-switch / send race — late destination history wipes a live turn.
 *
 * Production evidence (instrumented client-side reproduction, read-only):
 *   t+429ms   rail click starts GET history for the DESTINATION thread
 *   t+932ms   user sends a turn while that request is still in flight; the
 *             stream fetch rejects with TypeError("Failed to fetch")
 *   t+1461ms  DOM shows the optimistic user row + the network-error row with
 *             Retry; composer already cleared; rail still on the SOURCE thread
 *   t+7466ms  the destination history request finally resolves
 *   t+8470ms  both rows are gone — no error, no text, silent loss
 *
 * Cause (apps/web/app/command/page.tsx, loadSessionTranscript 1960-1990):
 * after `await fetchChatHistory(50, undefined, id)` the function
 * unconditionally runs setActiveChatSession / setHistoryState /
 * setMessages(mapped) / setInput(""), with no check on what happened during
 * the wait. `switchingSessionId` gates only the rail buttons — it is never
 * passed to CommandComposer (page.tsx:2854 passes only
 * `thinking || streamingActive`), so a send during a switch is accepted.
 *
 * The boot history path already carries the correct rule: applyHistory
 * (page.tsx:1102-1108) PREPENDS instead of wiping, commented "If the user
 * already started chatting while history was in flight". The multi-session
 * switch path never inherited it.
 *
 * Scope note: the network-error row with Retry is NOT what these tests
 * assert into existence — it already renders (page.tsx:1653-1655) and is
 * already covered by command-obsidian-noregression.test.tsx. Here it is the
 * *witness*: a visible, unambiguous live-turn artifact whose disappearance
 * after the late resolve is the defect.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";

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
const mockFetchChatSessions = vi.fn();
const mockFetchChatHistory = vi.fn();
const mockSendChat = vi.fn();
const mockSendChatPublic = vi.fn();
const mockSendChatStream = vi.fn();
const mockSendChatStreamPublic = vi.fn();
const mockPoll = vi.fn();

const FIXED_OP_ID = "op_web_test_switch_race_0001";

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        fetchMe: (...args: unknown[]) => mockFetchMe(...args),
        fetchChatSessions: (...args: unknown[]) => mockFetchChatSessions(...args),
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

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const SOURCE_ID = "sess-source-0001";
const DEST_ID = "sess-destination-0002";

const SOURCE_MARKER = "Source thread reply from the active conversation.";
const DEST_MARKER = "Destination thread reply that must not steal the pane.";
const LIVE_TURN = "what is my visa status for this role";

const SOURCE_ROWS = [
    { role: "user", content: "opening question on the source thread" },
    { role: "assistant", content: SOURCE_MARKER },
];
const DEST_ROWS = [
    { role: "user", content: "older question on the destination thread" },
    { role: "assistant", content: DEST_MARKER },
];

const SESSIONS = {
    // sessions[0] is the one the page auto-opens on boot (page.tsx:1126).
    sessions: [
        { id: SOURCE_ID, title: "Source thread", message_count: 2, user_turns: 1 },
        { id: DEST_ID, title: "Destination thread", message_count: 2, user_turns: 1 },
    ],
    total: 2,
};

/** A promise the test resolves by hand — the in-flight destination history. */
function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

/** The send's stream fetch rejects the way a dropped connection does. A
 *  fetch-level throw exits the for-await before any event, so neither
 *  in-stream fallback branch runs — this is the shape seen in production
 *  (zero POST /api/v1/rico/chat in seven days of backend logs). */
async function* failedFetchStream(): AsyncGenerator<unknown> {
    throw new TypeError("Failed to fetch");
}

let destHistory: ReturnType<typeof deferred<{ messages: typeof DEST_ROWS; total: number; has_more: boolean }>>;

beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-switch-race");

    destHistory = deferred();

    mockFetchMe.mockResolvedValue({ authenticated: true, role: "user", email: "u@test.com", name: "U" });
    mockFetchChatSessions.mockResolvedValue(SESSIONS);
    // fetchChatHistory(limit, cursor, sessionId)
    mockFetchChatHistory.mockImplementation(async (_limit: number, _cursor: unknown, sessionId?: string) => {
        if (sessionId === DEST_ID) return destHistory.promise;
        return { messages: SOURCE_ROWS, total: SOURCE_ROWS.length, has_more: false };
    });
    mockSendChatStream.mockImplementation(() => failedFetchStream());
    mockSendChatStreamPublic.mockImplementation(() => failedFetchStream());
    mockPoll.mockResolvedValue("terminal");
});

/* ── Harness helpers ─────────────────────────────────────────────────────── */

/** Message assertions are scoped to the transcript log: the conversation rail
 *  mirrors turn text as its row title, so unscoped queries double-match. */
function transcript() {
    return within(screen.getByRole("log", { name: /chat messages/i }));
}

function activeSessionId(): string | null {
    return screen.getByTestId("command-rail-current").getAttribute("data-session-id");
}

/** The one non-active rail row (full variant) — the destination thread. */
function destinationRow(): HTMLElement {
    return screen.getByTestId("command-rail-session");
}

/** Every rail row (full + compact variants) for a given thread. */
function railRows(sessionId: string): HTMLButtonElement[] {
    return Array.from(
        document.querySelectorAll<HTMLButtonElement>(`button[data-session-id="${sessionId}"]`),
    );
}

/** Barrier: loadSessionTranscript clears switchingSessionId in its `finally`,
 *  i.e. strictly AFTER every state write the late resolve performs. Waiting
 *  for the rail rows to re-enable therefore proves the late-history handler
 *  has fully run — on the current code and on any fixed version alike. */
async function waitForSwitchSettled() {
    await waitFor(() => {
        const rows = railRows(DEST_ID);
        expect(rows.length).toBeGreaterThan(0);
        rows.forEach((row) => expect(row.disabled).toBe(false));
    });
}

async function mountOnSourceThread() {
    render(<CommandPage />);
    await screen.findByTestId("command-obsidian-shell");
    // Multi-session rail only appears after fetchChatSessions resolves
    // (page.tsx:1120-1129); the source transcript proves history landed.
    await screen.findByTestId("command-rail-session");
    await transcript().findByText(SOURCE_MARKER);
    expect(activeSessionId()).toBe(SOURCE_ID);
}

/** Send a turn through the real composer (Enter path → handleKeyDown →
 *  handleSend → sendMessage). */
async function sendLiveTurn(text: string) {
    const textarea = await screen.findByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: text } });
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter" });
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("session-switch / send race — a late destination history must not wipe a live turn", () => {
    it("A: keeps the optimistic user row and the network-error/Retry row after the delayed destination history resolves", async () => {
        await mountOnSourceThread();

        // 1. Start a switch whose history request stays pending.
        fireEvent.click(destinationRow());
        await waitFor(() =>
            expect(mockFetchChatHistory).toHaveBeenCalledWith(50, undefined, DEST_ID),
        );
        // The pane still shows the SOURCE transcript — the switch is pending,
        // not applied.
        expect(transcript().queryByText(DEST_MARKER)).toBeNull();
        expect(activeSessionId()).toBe(SOURCE_ID);

        // 2. Send a turn while that request is in flight. The composer is not
        //    gated on switchingSessionId, so the turn is accepted.
        await sendLiveTurn(LIVE_TURN);

        // 3. The stream fails — optimistic user row + visible error/Retry row.
        await transcript().findByText(LIVE_TURN);
        await transcript().findByText(/could not reach rico/i);
        await screen.findByLabelText(/retry/i);
        // Still on the source thread: the switch has not applied yet.
        expect(activeSessionId()).toBe(SOURCE_ID);

        // 4. Now the destination history finally arrives.
        destHistory.resolve({ messages: DEST_ROWS, total: DEST_ROWS.length, has_more: false });
        await waitForSwitchSettled();

        // 5. The live turn must survive it.
        expect(transcript().queryByText(LIVE_TURN)).not.toBeNull();
        expect(transcript().queryByText(/could not reach rico/i)).not.toBeNull();
        expect(screen.queryByLabelText(/retry/i)).not.toBeNull();

        // 6. The destination transcript must not have overwritten the pane.
        expect(transcript().queryByText(DEST_MARKER)).toBeNull();

        // 7. The originally active thread stays selected.
        expect(activeSessionId()).toBe(SOURCE_ID);
    });

    it("B: the late history neither replays setMessages(destinationHistory), nor clears the live turn, nor moves the active thread", async () => {
        await mountOnSourceThread();

        fireEvent.click(destinationRow());
        await waitFor(() =>
            expect(mockFetchChatHistory).toHaveBeenCalledWith(50, undefined, DEST_ID),
        );

        await sendLiveTurn(LIVE_TURN);
        await transcript().findByText(LIVE_TURN);
        await transcript().findByText(/could not reach rico/i);

        // The send was ACCEPTED during the wait — that is the precondition the
        // late-history handler has to respect.
        expect(mockSendChatStream).toHaveBeenCalledTimes(1);

        destHistory.resolve({ messages: DEST_ROWS, total: DEST_ROWS.length, has_more: false });
        await waitForSwitchSettled();

        // B1 — no visible equivalent of setMessages(destinationHistory): the
        // destination rows must not be rendered at all.
        expect(transcript().queryByText(DEST_MARKER)).toBeNull();
        expect(
            transcript().queryByText("older question on the destination thread"),
        ).toBeNull();

        // B2 — the live turn is neither cleared nor replaced.
        expect(transcript().queryByText(LIVE_TURN)).not.toBeNull();
        expect(transcript().queryByText(/could not reach rico/i)).not.toBeNull();
        expect(screen.queryByLabelText(/retry/i)).not.toBeNull();
        // The pane is not empty/greeting-only either.
        expect(transcript().queryByText(SOURCE_MARKER)).not.toBeNull();

        // B3 — the active thread did not change after a send was accepted
        // during the wait.
        expect(activeSessionId()).toBe(SOURCE_ID);
        expect(destinationRow().getAttribute("data-session-id")).toBe(DEST_ID);
    });
});
