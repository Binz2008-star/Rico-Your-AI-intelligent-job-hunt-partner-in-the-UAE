/**
 * Regression: JobMatchCardAtelier's "Mark as Applied" must never show success
 * unless the backend's structured response explicitly confirms the
 * application was PERSISTED — never inferred from message text, HTTP status,
 * a non-error response type, or the mere absence of an exception.
 *
 * Bug (shipped in commit 7225e1c0 / PR #1321, live in production): sendMessage's
 * applyDoneResponse set settledOk = true for ANY non-empty, non-rate-limited,
 * non-fallback reply — including `type: "application_status_update_failed"`,
 * which is a normal conversational reply the backend returns when the DB
 * write failed. That made the card claim "Applied" even when nothing was
 * persisted.
 *
 * Fix: settledOk is now `res.type === "application_status_update" &&
 * res.job_status === "applied"` — the one explicit, backend-verified signal
 * (see src/rico_chat_api.py:_handle_application_status_update).
 *
 * These tests exercise the REAL wiring end-to-end (CommandPage → onMarkApplied
 * → sendMessage → applyDoneResponse → settledOk → the promise JobMatchCardAtelier
 * awaits) rather than mocking onMarkApplied directly, so they actually cover
 * the bug that shipped — the existing card-level suite
 * (command-job-match-card-atelier.test.tsx) mocks onMarkApplied and therefore
 * cannot catch this class of defect.
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
        error: () => {
            const e = new Error("stream failed");
            try {
                ctrl.error(e);
            } catch {
                /* already closed */
            }
        },
        close: () => {
            try {
                ctrl.close();
            } catch {
                /* already closed/errored */
            }
        },
    };
}

const JOB_MATCH_HISTORY_ROW = {
    role: "assistant",
    content: JSON.stringify({
        type: "job_matches",
        message: "Here's a match for you.",
        matches: [{ title: "Senior Accountant", company: "Atelier Holdings", apply_url: "https://example.com/apply/1" }],
    }),
};

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
            return jsonResponse({ messages: [JOB_MATCH_HISTORY_ROW], total: 1, has_more: false });
        }
        if (url.includes("/rico/chat/stream")) {
            const handler = streamHandlers.shift();
            if (!handler) throw new Error("No stream fixture queued for this send");
            return handler(init);
        }
        return jsonResponse({}, 404);
    });
});

async function renderWithJobCard() {
    render(<CommandPage />);
    // Mark as Applied only appears once the user has opened the apply link
    // (JobMatchCardAtelier: `{linkOpened && applyState !== "success" && (...)}`).
    const applyLink = await screen.findByTestId("job-link-apply");
    await userEvent.click(applyLink);
    return screen.findByTestId("job-mark-applied");
}

describe("Mark as Applied — persistence-contract integrity", () => {
    it("shows success only when the backend confirms real persistence (type + job_status)", async () => {
        const button = await renderWithJobCard();
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        await userEvent.click(button);
        await waitFor(() => expect(sse).toBeDefined());

        sse.push({
            type: "done",
            response: {
                type: "application_status_update",
                message: "Application marked as submitted. You can track it from Applications.",
                job_status: "applied",
            },
        });
        sse.close();

        expect(await screen.findByTestId("job-mark-applied-success")).toBeInTheDocument();
        expect(screen.queryByTestId("job-mark-applied-error")).not.toBeInTheDocument();
    });

    it("does NOT show success on a conversational reply where persistence failed (application_status_update_failed)", async () => {
        const button = await renderWithJobCard();
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        await userEvent.click(button);
        await waitFor(() => expect(sse).toBeDefined());

        // A normal, non-error, non-empty conversational reply — this is
        // exactly the shape that fooled the old settledOk = true logic.
        sse.push({
            type: "done",
            response: {
                type: "application_status_update_failed",
                message: "I understand you submitted this application, but I could not save it right now. Please try again shortly.",
                job_status: null,
            },
        });
        sse.close();

        expect(await screen.findByTestId("job-mark-applied-error")).toBeInTheDocument();
        expect(screen.queryByTestId("job-mark-applied-success")).not.toBeInTheDocument();
    });

    it("does NOT show success on a clarification response (e.g. missing job context)", async () => {
        const button = await renderWithJobCard();
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        await userEvent.click(button);
        await waitFor(() => expect(sse).toBeDefined());

        sse.push({
            type: "done",
            response: {
                type: "clarification",
                message: "Which job are you referring to?",
            },
        });
        sse.close();

        expect(await screen.findByTestId("job-mark-applied-error")).toBeInTheDocument();
        expect(screen.queryByTestId("job-mark-applied-success")).not.toBeInTheDocument();
    });

    it("shows an error on a transport failure (stream error + JSON fallback also fails)", async () => {
        const button = await renderWithJobCard();
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        // After the stream errors, sendMessage falls back to the plain JSON
        // endpoint (same URL prefix) — make that fail too.
        fetchMock.mockImplementation(async (input, init) => {
            const url = String(input);
            const method = (init?.method ?? "GET").toUpperCase();
            if (url.includes("/api/v1/me")) {
                return jsonResponse({ authenticated: true, role: "user", email: "u@u.com", name: "Ahmed" });
            }
            if (url.includes("/rico/chat/history")) {
                if (method === "DELETE") return jsonResponse({});
                return jsonResponse({ messages: [JOB_MATCH_HISTORY_ROW], total: 1, has_more: false });
            }
            if (url.includes("/rico/chat/stream")) {
                const handler = streamHandlers.shift();
                if (!handler) throw new Error("No stream fixture queued for this send");
                return handler(init);
            }
            if (url.includes("/rico/chat") && method === "POST") {
                throw new Error("network down");
            }
            return jsonResponse({}, 404);
        });

        await userEvent.click(button);
        await waitFor(() => expect(sse).toBeDefined());
        sse.error();

        expect(await screen.findByTestId("job-mark-applied-error")).toBeInTheDocument();
        expect(screen.queryByTestId("job-mark-applied-success")).not.toBeInTheDocument();
    });

    it("a second click while pending does not fire a duplicate send", async () => {
        const button = await renderWithJobCard();
        let sse!: ReturnType<typeof manualSSE>;
        streamHandlers.push((init) => {
            sse = manualSSE(init?.signal);
            return sse.response;
        });

        const user = userEvent.setup();
        await user.click(button);
        await waitFor(() => expect(sse).toBeDefined());
        const streamCallsAfterFirstClick = fetchMock.mock.calls.filter(([u]) => String(u).includes("/rico/chat/stream")).length;

        // Card is now "pending" — a second click must be a no-op (guarded in
        // JobMatchCardAtelier.handleMarkApplied).
        await user.click(button);
        await new Promise((r) => setTimeout(r, 0));
        const streamCallsAfterSecondClick = fetchMock.mock.calls.filter(([u]) => String(u).includes("/rico/chat/stream")).length;
        expect(streamCallsAfterSecondClick).toBe(streamCallsAfterFirstClick);

        sse.push({
            type: "done",
            response: { type: "application_status_update", message: "Applied.", job_status: "applied" },
        });
        sse.close();
        expect(await screen.findByTestId("job-mark-applied-success")).toBeInTheDocument();

        // Once applied, the button itself is gone (not just disabled) — a
        // third click isn't merely a no-op, it's structurally impossible.
        expect(screen.queryByTestId("job-mark-applied")).not.toBeInTheDocument();
    });
});
