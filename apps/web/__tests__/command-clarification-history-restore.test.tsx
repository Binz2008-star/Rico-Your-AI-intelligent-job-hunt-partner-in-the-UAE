/**
 * TASK-20260723-001 — history-restore fix regression coverage.
 *
 * parseHistoryContent()'s generic structured-response fallback used to drop
 * the backend's explicit `type` field entirely, so a `type: "clarification"`
 * message survived a LIVE send correctly (classified as "needs_input") but
 * silently downgraded to plain "rico" prose the moment it was reloaded from
 * history or reached via a Sessions-rail switch — exactly the "operation
 * paused, not failed" signal this feature exists to preserve, lost on the one
 * path (history restore) real users hit on every reload.
 *
 * These tests exercise the REAL page pipeline (CommandPage → fetchChatHistory
 * mock → parseHistoryContent/mapHistoryToMessages → classifyMessage), not a
 * synthetic message object, so they actually cover the regression — the
 * existing command-transcript-step.test.tsx suite tests the presentational
 * component in isolation and cannot catch a bug in the parsing pipeline that
 * feeds it.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
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

const CLARIFICATION_ROW = {
    role: "assistant",
    content: JSON.stringify({
        type: "clarification",
        message: "Manager is too broad for a live job search. Which manager role should I search?",
        options: [{ action: "send_message", label: "Operations Manager", message: "Operations Manager" }],
        next_action: "choose_role",
    }),
};

const PLAIN_ROW = {
    role: "assistant",
    content: JSON.stringify({ message: "Here's a quick tip for your search." }),
};

const JOB_MATCHES_ROW = {
    role: "assistant",
    content: JSON.stringify({
        type: "job_matches",
        message: "Found a match.",
        matches: [{ title: "Accountant", company: "Atelier Co" }],
    }),
};

const OPTIONS_ROW = {
    role: "assistant",
    content: JSON.stringify({
        type: "options",
        message: "What would you like to do?",
        options: [{ action: "send_message", label: "Upload CV", message: "__cv_upload__" }],
    }),
};

const APPLICATION_STATUS_ROW = {
    role: "assistant",
    content: JSON.stringify({
        type: "application_status",
        message: "Here are your applications.",
        applications: [{ title: "Analyst", company: "Delta LLC", status: "applied" }],
    }),
};

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

function mockHistoryOnly(rows: Array<{ role: string; content: string }>) {
    fetchMock.mockImplementation(async (input, init) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/api/v1/me")) {
            return jsonResponse({ authenticated: true, role: "user", email: "u@u.com", name: "Ahmed" });
        }
        if (url.includes("/rico/chat/sessions")) {
            return jsonResponse({}, 404); // legacy unscoped fallback path
        }
        if (url.includes("/rico/chat/history")) {
            if (method === "DELETE") return jsonResponse({});
            return jsonResponse({ messages: rows, total: rows.length, has_more: false });
        }
        return jsonResponse({}, 404);
    });
}

beforeEach(() => {
    fetchMock.mockReset();
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-01");
    vi.stubGlobal("fetch", fetchMock);
});

describe("history-restore: type is preserved through parseHistoryContent (real pipeline)", () => {
    it("a stored clarification row renders as the needs-input row, not plain rico, on initial load", async () => {
        mockHistoryOnly([CLARIFICATION_ROW]);
        render(<CommandPage />);

        const row = await screen.findByTestId("transcript-needs-input-row");
        expect(row).toHaveTextContent("Needs your input");
        expect(row).toHaveTextContent("ask");
        expect(row).toHaveTextContent("Manager is too broad for a live job search.");
        expect(screen.getByRole("button", { name: "Operations Manager" })).toBeInTheDocument();
        expect(screen.queryByTestId("transcript-rico-row")).not.toBeInTheDocument();

        // History-hydrated → entrance animation suppressed, no re-announce.
        expect(row.parentElement?.className).not.toMatch(/animate-in/);
    });

    it("a normal generic history reply (no type) still renders as plain rico", async () => {
        mockHistoryOnly([PLAIN_ROW]);
        render(<CommandPage />);

        await screen.findByTestId("transcript-rico-row");
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();
        expect(screen.getByTestId("transcript-rico-row")).toHaveTextContent("Here's a quick tip for your search.");
    });

    it("job_matches history rows are unaffected (still classify as card)", async () => {
        mockHistoryOnly([JOB_MATCHES_ROW]);
        render(<CommandPage />);

        const card = await screen.findByTestId("transcript-card-row");
        expect(within(card).getAllByText("Accountant").length).toBeGreaterThan(0);
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();
    });

    it("options/help-type history rows are unaffected (options preserved, plain rico presentation)", async () => {
        mockHistoryOnly([OPTIONS_ROW]);
        render(<CommandPage />);

        const row = await screen.findByTestId("transcript-rico-row");
        expect(within(row).getByRole("button", { name: "Upload CV" })).toBeInTheDocument();
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();
    });

    it("application_status history rows are unaffected (still classify as card)", async () => {
        mockHistoryOnly([APPLICATION_STATUS_ROW]);
        render(<CommandPage />);

        await screen.findByTestId("transcript-card-row");
        expect(screen.getByText(/Here are your applications/)).toBeInTheDocument();
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();
    });
});

describe("history-restore: no duplicate announcement/animation across a Sessions-rail switch", () => {
    it("a clarification reached via session switch (not initial load) still renders as needs-input with entrance animation suppressed", async () => {
        fetchMock.mockImplementation(async (input, init) => {
            const url = String(input);
            const method = (init?.method ?? "GET").toUpperCase();
            if (url.includes("/api/v1/me")) {
                return jsonResponse({ authenticated: true, role: "user", email: "u@u.com", name: "Ahmed" });
            }
            if (url.includes("/rico/chat/sessions")) {
                return jsonResponse({
                    sessions: [
                        { id: "session-a", title: "Session A", message_count: 2, user_turns: 1 },
                        { id: "session-b", title: "Session B", message_count: 2, user_turns: 1 },
                    ],
                    total: 2,
                });
            }
            if (url.includes("/rico/chat/history")) {
                if (method === "DELETE") return jsonResponse({});
                const sessionId = new URL(url, "http://x").searchParams.get("session_id");
                if (sessionId === "session-b") {
                    return jsonResponse({ messages: [CLARIFICATION_ROW], total: 1, has_more: false });
                }
                return jsonResponse({
                    messages: [{ role: "assistant", content: JSON.stringify({ message: "Session A reply" }) }],
                    total: 1,
                    has_more: false,
                });
            }
            return jsonResponse({}, 404);
        });

        render(<CommandPage />);
        await screen.findByText("Session A reply");
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();

        const user = userEvent.setup();
        await user.click(screen.getByRole("button", { name: /session b/i }));

        const row = await screen.findByTestId("transcript-needs-input-row");
        expect(within(row).getByText(/Manager is too broad/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Operations Manager" })).toBeInTheDocument();
        // Reached via session switch, not a live send — must not replay the
        // entrance animation or re-announce.
        expect(row.parentElement?.className).not.toMatch(/animate-in/);

        await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("session_id=session-b"))).toBe(true));
    });
});
