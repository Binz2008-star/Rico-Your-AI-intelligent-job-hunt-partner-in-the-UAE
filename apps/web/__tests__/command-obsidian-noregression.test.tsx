/**
 * C1 interactive no-regression suite (owner directive 2026-07-16).
 *
 * Mounts the REAL CommandPage — real CommandObsidianShell, real
 * CommandConversationRail, real CommandComposer/CommandMessages/CommandRail,
 * real lib/api streaming (`sendChatStream` + `_readSSE`) — with fixtures at
 * the NETWORK BOUNDARY only (a stubbed global fetch serving JSON and real SSE
 * ReadableStreams). No lib/api mocking, no static screenshot components.
 *
 * Verifies the owner's C1 no-regression contract on the authenticated surface:
 *   1. type + send → user turn renders
 *   2. thinking state appears (stop control visible)
 *   3. streaming tokens render progressively
 *   4. completed response replaces the stream
 *   5. stop/cancel aborts a hung stream → real error + Retry affordance
 *   6. retry after a network error resends and succeeds
 *   7. New chat works (conversation rail control)
 *   8. Clear history works (two-step rail control → real DELETE)
 *   9. left + right panel toggles work
 *  10. language toggle flips dir/lang (EN ↔ AR)
 *  11. theme toggle flips the Obsidian mode
 */

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

import CommandPage from "@/app/command/page";

/* ── Network-boundary fixtures ───────────────────────────────────────────── */

type ResponseLike = {
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
    body?: ReadableStream<Uint8Array> | null;
};

function jsonResponse(body: unknown, status = 200): ResponseLike {
    return { ok: status >= 200 && status < 300, status, json: async () => body, body: null };
}

/** A real SSE body the test drives, wired to the request's abort signal the
 *  way a browser fetch is: aborting rejects the pending read. */
function manualSSE(signal?: AbortSignal | null) {
    const enc = new TextEncoder();
    let ctrl!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
        start(c) {
            ctrl = c;
            signal?.addEventListener("abort", () => {
                const e = new Error("The operation was aborted.");
                e.name = "AbortError";
                try {
                    ctrl.error(e);
                } catch {
                    /* already closed */
                }
            });
        },
    });
    return {
        response: { ok: true, status: 200, json: async () => ({}), body: stream } as ResponseLike,
        push: (event: Record<string, unknown>) =>
            ctrl.enqueue(enc.encode(`data: ${JSON.stringify(event)}\n\n`)),
        close: () => {
            try {
                ctrl.close();
            } catch {
                /* already closed/errored */
            }
        },
    };
}

/** Per-test queue of handlers for POST /rico/chat/stream. */
let streamHandlers: Array<(init?: RequestInit) => ResponseLike | Promise<ResponseLike>>;
let deleteHistoryCalls: number;

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

function installFetch() {
    fetchMock.mockImplementation(async (input, init) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/api/v1/me")) {
            return jsonResponse({ authenticated: true, role: "user", email: "u@u.com", name: "Ahmed" });
        }
        if (url.includes("/rico/chat/history")) {
            if (method === "DELETE") {
                deleteHistoryCalls += 1;
                return jsonResponse({});
            }
            return jsonResponse({ messages: [], total: 0, has_more: false });
        }
        if (url.includes("/rico/chat/stream")) {
            const handler = streamHandlers.shift();
            if (!handler) throw new Error("No stream fixture queued for this send");
            return handler(init);
        }
        // Everything else (mission bar, profile, stats…) degrades gracefully in
        // the page — serve a 404 so those layers take their real fallback paths.
        return jsonResponse({}, 404);
    });
}

beforeEach(() => {
    fetchMock.mockReset();
    streamHandlers = [];
    deleteHistoryCalls = 0;
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-01");
    vi.stubGlobal("fetch", fetchMock);
    installFetch();
});

async function mountAuthenticated() {
    render(<CommandPage />);
    // Authenticated shell up + welcome turn rendered (history fixture is empty).
    await screen.findByTestId("command-obsidian-shell");
    await screen.findByTestId("command-rail-current");
    // Message assertions are scoped to the transcript log — the conversation
    // rail truthfully mirrors the first user turn as its title, so unscoped
    // text queries would double-match.
    return within(screen.getByRole("log", { name: /chat messages/i }));
}

function composerTextbox() {
    // The composer textarea is the page's only textbox.
    return screen.getByRole("textbox");
}

async function sendText(text: string) {
    fireEvent.change(composerTextbox(), { target: { value: text } });
    fireEvent.click(screen.getByLabelText("Send"));
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("C1 no-regression — real CommandPage over network fixtures", () => {
    it("send → user turn, thinking, streaming tokens, completed response", async () => {
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });
        const log = await mountAuthenticated();

        await sendText("Hello Rico");

        // 1. user turn renders
        await log.findByText("Hello Rico");
        // 2. thinking state: the composer swaps to the real stop control
        await screen.findByTestId("cancel-button");

        // 3. tokens render progressively
        sse.push({ type: "token", text: "Salam" });
        await log.findByText("Salam");
        sse.push({ type: "token", text: " — checking your profile now." });
        await log.findByText(/Salam — checking your profile now\./);

        // 4. done replaces the stream with the completed response
        sse.push({
            type: "done",
            response: { response: "Salam — profile checked. Ready when you are.", type: "chat" },
        });
        sse.close();
        await log.findByText(/profile checked\. Ready when you are\./);
        await waitFor(() => expect(screen.queryByTestId("cancel-button")).not.toBeInTheDocument());
        // streaming leftovers must be gone
        expect(log.queryByText(/^Salam — checking your profile now\.$/)).not.toBeInTheDocument();
    });

    it("stop/cancel aborts a hung stream → real timeout error with Retry", async () => {
        streamHandlers.push((init) => manualSSE(init?.signal).response); // hangs until abort
        const log = await mountAuthenticated();

        await sendText("Hello Rico");
        const stop = await screen.findByTestId("cancel-button");
        fireEvent.click(stop);

        // Real AbortError path: timeout-style message flagged retryable
        await log.findByText(/taking longer than usual/i);
        await screen.findByLabelText(/retry/i);
        expect(screen.queryByTestId("cancel-button")).not.toBeInTheDocument();
    });

    it("retry after a network error resends the same text and succeeds", async () => {
        // First send: the stream fetch itself fails like a dropped connection.
        streamHandlers.push(() => {
            throw Object.assign(new TypeError("Failed to fetch"), {});
        });
        // Retry: works, completes without tokens (done-only legacy path).
        streamHandlers.push((init) => {
            const sse = manualSSE(init?.signal);
            queueMicrotask(() => {
                sse.push({ type: "done", response: { response: "Recovered after retry.", type: "chat" } });
                sse.close();
            });
            return sse.response;
        });
        const log = await mountAuthenticated();

        await sendText("Hello again");
        await log.findByText(/could not reach rico/i);

        fireEvent.click(await screen.findByLabelText(/retry/i));
        await log.findByText("Recovered after retry.");
        // The retried user text appears twice in the transcript (original + resent turn)
        expect(log.getAllByText("Hello again").length).toBeGreaterThanOrEqual(2);
    });

    it("New chat (conversation rail) resets the transcript to the real greeting", async () => {
        streamHandlers.push((init) => {
            const sse = manualSSE(init?.signal);
            queueMicrotask(() => {
                sse.push({ type: "done", response: { response: "First answer.", type: "chat" } });
                sse.close();
            });
            return sse.response;
        });
        const log = await mountAuthenticated();

        await sendText("Start something");
        await log.findByText("First answer.");

        fireEvent.click(screen.getByTestId("command-rail-new-chat"));
        await log.findByText(/new chat started/i);
        expect(log.queryByText("First answer.")).not.toBeInTheDocument();
        expect(log.queryByText("Start something")).not.toBeInTheDocument();
    });

    it("Clear history (conversation rail, two-step) empties the transcript via the real DELETE", async () => {
        streamHandlers.push((init) => {
            const sse = manualSSE(init?.signal);
            queueMicrotask(() => {
                sse.push({ type: "done", response: { response: "Noted.", type: "chat" } });
                sse.close();
            });
            return sse.response;
        });
        const log = await mountAuthenticated();

        // Welcome-only transcript is NOT a real conversation — no Clear History.
        await log.findByText(/welcome back/i);
        expect(screen.queryByTestId("command-rail-clear-history")).not.toBeInTheDocument();
        expect(screen.queryByTestId("command-rail-turn-count")).not.toBeInTheDocument();

        // A real user turn makes it a conversation; the control appears.
        await sendText("Remember my target role");
        const sent = await log.findByText("Remember my target role");
        await log.findByText("Noted.");

        fireEvent.click(screen.getByTestId("command-rail-clear-history")); // arm
        fireEvent.click(await screen.findByTestId("command-rail-clear-confirm")); // perform

        await waitFor(() => expect(deleteHistoryCalls).toBe(1));
        await waitFor(() => expect(sent).not.toBeInTheDocument());
    });

    it("left and right panel toggles collapse/expand the rails", async () => {
        await mountAuthenticated();

        const leftToggle = screen.getByLabelText("Toggle sessions rail");
        const leftRail = screen.getByTestId("command-obsidian-leftrail");
        expect(leftToggle).toHaveAttribute("aria-expanded", "true");
        expect(leftRail.className).toContain("lg:w-[260px]");
        fireEvent.click(leftToggle);
        expect(leftToggle).toHaveAttribute("aria-expanded", "false");
        expect(leftRail.className).toContain("lg:w-0");

        const rightToggle = screen.getByLabelText("Toggle shortlist rail");
        const rightRail = screen.getByTestId("command-rail");
        expect(rightRail.className).toContain("lg:flex");
        fireEvent.click(rightToggle);
        expect(rightToggle).toHaveAttribute("aria-expanded", "false");
        expect(screen.getByTestId("command-rail").className).not.toContain("lg:flex");
    });

    it("language toggle flips the shell to Arabic RTL and back", async () => {
        await mountAuthenticated();
        const shell = screen.getByTestId("command-obsidian-shell");

        fireEvent.click(screen.getByRole("button", { name: "عربي" }));
        await waitFor(() => expect(shell).toHaveAttribute("dir", "rtl"));
        expect(shell).toHaveAttribute("lang", "ar");

        fireEvent.click(screen.getByRole("button", { name: "EN" }));
        await waitFor(() => expect(shell).toHaveAttribute("dir", "ltr"));
    });

    it("theme toggle flips between Obsidian night and dawn", async () => {
        await mountAuthenticated();
        const shell = screen.getByTestId("command-obsidian-shell");
        expect(shell).toHaveAttribute("data-obsidian-mode", "dark");

        fireEvent.click(screen.getByLabelText("Light mode"));
        expect(shell).toHaveAttribute("data-obsidian-mode", "light");
        fireEvent.click(screen.getByLabelText("Dark mode"));
        expect(shell).toHaveAttribute("data-obsidian-mode", "dark");
    });

    it("history-load failure surfaces truthfully in the conversation rail (welcome fallback unchanged)", async () => {
        fetchMock.mockImplementation(async (input, init) => {
            const url = String(input);
            const method = (init?.method ?? "GET").toUpperCase();
            if (url.includes("/api/v1/me")) {
                return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
            }
            if (url.includes("/rico/chat/history") && method === "GET") {
                return jsonResponse({ detail: "boom" }, 500);
            }
            return jsonResponse({}, 404);
        });

        render(<CommandPage />);
        await screen.findByTestId("command-obsidian-shell");
        await screen.findByTestId("command-rail-history-error");
        // Real fallback behavior preserved: the welcome turn still renders.
        await screen.findByText(/welcome back/i);
    });
});
