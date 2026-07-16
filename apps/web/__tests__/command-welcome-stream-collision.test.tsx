/**
 * Regression: on a fresh page load the welcome turn was created with a
 * hardcoded id of 1 while the module-level nextId() counter still sat at 0.
 * sendMessage takes streamId = nextId() (= 1) synchronously, BEFORE React runs
 * the queued user-turn updater — so the first streamed reply's tokens were
 * map-appended into the welcome row as well as the stream row, corrupting the
 * welcome message for every user's first streamed turn after load.
 *
 * This file must stay ISOLATED (own module instance) so the counter genuinely
 * starts at 0 — do not merge these tests into another suite; a prior test's
 * sends would advance the counter and mask the collision.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

type ResponseLike = {
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
    body?: ReadableStream<Uint8Array> | null;
};

function jsonResponse(body: unknown, status = 200): ResponseLike {
    return { ok: status >= 200 && status < 300, status, json: async () => body, body: null };
}

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

let streamHandlers: Array<(init?: RequestInit) => ResponseLike | Promise<ResponseLike>>;

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

beforeEach(() => {
    fetchMock.mockReset();
    streamHandlers = [];
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-01");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (input, init) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/api/v1/me")) {
            return jsonResponse({ authenticated: true, role: "user", email: "u@u.com", name: "Ahmed" });
        }
        if (url.includes("/rico/chat/history")) {
            if (method === "DELETE") return jsonResponse({});
            return jsonResponse({ messages: [], total: 0, has_more: false });
        }
        if (url.includes("/rico/chat/stream")) {
            const handler = streamHandlers.shift();
            if (!handler) throw new Error("No stream fixture queued for this send");
            return handler(init);
        }
        return jsonResponse({}, 404);
    });
});

describe("first streamed turn after a fresh page load", () => {
    it("does not append stream tokens into the welcome message (id collision)", async () => {
        render(<CommandPage />);
        await screen.findByTestId("command-obsidian-shell");

        // Capture the welcome turn's exact rendered text before any send.
        const welcome = await screen.findByText(/Welcome back, Ahmed/);
        const welcomeText = welcome.textContent ?? "";
        expect(welcomeText.length).toBeGreaterThan(0);

        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        const user = userEvent.setup();
        await user.type(screen.getByRole("textbox"), "First question after load");
        await user.click(screen.getByLabelText("Send"));
        await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/rico/chat/stream"))).toBe(true));

        sse.push({ type: "token", text: "Alpha" });
        await screen.findByText(/Alpha/);
        sse.push({ type: "token", text: " Bravo" });
        sse.push({ type: "token", text: " Charlie" });
        await screen.findByText(/Alpha Bravo Charlie/);

        // The welcome row must be byte-identical to its pre-send text —
        // no token may have been appended into it.
        expect(screen.getByText(/Welcome back, Ahmed/).textContent).toBe(welcomeText);
        expect(welcomeText).not.toContain("Bravo");

        sse.push({
            type: "done",
            response: { response: "Alpha Bravo Charlie Done.", type: "chat" },
        });
        sse.close();
        await screen.findByText(/Charlie Done\./);
        expect(screen.getByText(/Welcome back, Ahmed/).textContent).toBe(welcomeText);
    });
});
