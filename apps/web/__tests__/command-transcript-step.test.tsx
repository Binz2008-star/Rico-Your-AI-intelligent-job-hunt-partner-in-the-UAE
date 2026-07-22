/**
 * CommandTranscriptStep — slice C2/C3 presentation contracts.
 *
 *  1. Authenticated rows: the USER turn is a dark ink bubble (RicoUserBubble)
 *     and the plain-TEXT Rico turn is serif editorial prose (RicoReply); FAIL,
 *     stopped, and card rows keep their canonical treatment; children pass
 *     through where the row still owns them.
 *  2. The streaming caret renders only while a real stream is appending.
 *  3. CHECK/RUN progress rows render only from real agentic_ui.progress.
 *  4. The public surface stays on the pre-C2 CommandMessageRow presentation
 *     (gold pill user bubble) byte-for-byte.
 *  5. TranscriptWorkingRow: RUN row with the real operation label while one
 *     exists; the serif "Thinking…" shimmer otherwise — never a fabricated name.
 */

import {
    CommandTranscriptStep,
    TranscriptWorkingRow,
} from "@/components/command/CommandTranscriptStep";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: "en" }),
}));

const step = (message: Record<string, unknown>, children = "body", authenticated = true) =>
    render(
        <CommandTranscriptStep
            authenticated={authenticated}
            message={message as never}
            isFirstInGroup
            isStructured={false}
        >
            {children}
        </CommandTranscriptStep>,
    );

describe("CommandTranscriptStep (authenticated)", () => {
    it("user turn → dark ink bubble carrying the plain text (no gutter)", () => {
        const { container } = step({ role: "user", text: "Find me jobs" }, "Find me jobs");
        const row = screen.getByTestId("transcript-you-row");
        // The editorial bubble owns the text from message.text; the old mono
        // "you" gutter is gone.
        expect(row).toHaveTextContent("Find me jobs");
        expect(row).not.toHaveTextContent(/^you/i);
        expect(container.querySelector(".bg-ink")).not.toBeNull();
    });

    it("plain Rico turn → serif reply prose; caret only while streaming", () => {
        const { rerender } = step({ role: "rico", text: "Hi", streaming: true }, "Hi");
        const row = screen.getByTestId("transcript-rico-row");
        expect(row).toHaveTextContent("Hi");
        expect(row.querySelector(".serif")).not.toBeNull();
        expect(screen.getByTestId("transcript-streaming-caret")).toBeInTheDocument();
        rerender(
            <CommandTranscriptStep authenticated message={{ role: "rico", text: "Hi" } as never} isFirstInGroup isStructured={false}>
                Hi
            </CommandTranscriptStep>,
        );
        expect(screen.queryByTestId("transcript-streaming-caret")).not.toBeInTheDocument();
        // Settled → the ghost Copy affordance (RicoReply owns Copy now).
        expect(screen.getByText(/^Copy$/)).toBeInTheDocument();
    });

    it("error turn → FAIL gutter row", () => {
        step({ role: "rico", text: "Could not reach Rico.", isError: true }, "Could not reach Rico.");
        expect(screen.getByTestId("transcript-fail-row")).toHaveTextContent("fail");
    });

    it("stopped turn → muted stopped row", () => {
        step({ role: "rico", type: "stopped", text: "You stopped this reply." }, "You stopped this reply.");
        expect(screen.getByTestId("transcript-stopped-row")).toHaveTextContent(/you stopped this reply/i);
    });

    it("card turn keeps its children untouched behind a RICO gutter", () => {
        step(
            { role: "rico", type: "job_matches", matches: [{}] },
            <div data-testid="card-probe">card body</div> as never,
        );
        expect(screen.getByTestId("transcript-card-row")).toContainElement(screen.getByTestId("card-probe"));
    });

    it("CHECK/RUN progress rows render only from real agentic_ui.progress", () => {
        step({
            role: "rico",
            text: "done",
            agentic_ui: {
                actions: [], permission_request: null, proposed_changes: [], attachment_analysis: [],
                progress: [
                    { id: "a", label: "Reading your CV", status: "complete" },
                    { id: "b", label: "Searching matching roles", status: "running" },
                ],
            },
        });
        const progress = screen.getByTestId("transcript-progress");
        expect(progress).toHaveTextContent("Reading your CV");
        expect(progress).toHaveTextContent("Searching matching roles");
        expect(progress).toHaveTextContent("✓");
    });

    it("no progress data → no progress rows (anti-fabrication)", () => {
        step({ role: "rico", text: "plain" });
        expect(screen.queryByTestId("transcript-progress")).not.toBeInTheDocument();
    });
});

/**
 * TASK-20260723-001 — clarification / needs-input transcript treatment.
 * Classified ONLY from the real, explicit `type: "clarification"` field —
 * never from reply text — and must preserve the full reply + any options/
 * next_action chips (children) completely unchanged.
 */
describe("CommandTranscriptStep — clarification (needs-input)", () => {
    it("clarification turn → distinct Needs-Input row, not the plain rico row", () => {
        step(
            { role: "rico", type: "clarification", text: "Which manager role should I search?" },
            <div data-testid="options-probe">chips here</div> as never,
        );
        const row = screen.getByTestId("transcript-needs-input-row");
        expect(row).toHaveTextContent("Needs your input");
        expect(row).toHaveTextContent("ask");
        expect(row).toContainElement(screen.getByTestId("options-probe"));
        expect(screen.queryByTestId("transcript-rico-row")).not.toBeInTheDocument();
        expect(screen.queryByTestId("transcript-fail-row")).not.toBeInTheDocument();
    });

    it("uses role=status and aria-live=polite, never assertive", () => {
        step({ role: "rico", type: "clarification", text: "Sign in first." });
        const row = screen.getByTestId("transcript-needs-input-row");
        expect(row).toHaveAttribute("role", "status");
        expect(row).toHaveAttribute("aria-live", "polite");
    });

    it("classification is gated strictly on type — never inferred from reply text, and wins over the generic card heuristics", () => {
        // Same message ALSO carries a non-empty matches array (which would
        // otherwise classify as "card") — type: "clarification" must still win.
        step({ role: "rico", type: "clarification", text: "Manager is too broad.", matches: [{}] });
        expect(screen.getByTestId("transcript-needs-input-row")).toBeInTheDocument();
        expect(screen.queryByTestId("transcript-card-row")).not.toBeInTheDocument();
    });

    it("a plain reply mentioning a question is NOT classified as needs-input (no text-based inference)", () => {
        step({ role: "rico", text: "Which manager role should I search?" });
        expect(screen.getByTestId("transcript-rico-row")).toBeInTheDocument();
        expect(screen.queryByTestId("transcript-needs-input-row")).not.toBeInTheDocument();
    });
});

describe("CommandTranscriptStep (public pass-through)", () => {
    it("public user turn keeps the pre-C2 gold pill presentation", () => {
        const { container } = step({ role: "user", text: "hello" }, "hello", false);
        expect(container.querySelector(".bg-gold")).not.toBeNull();
        expect(screen.queryByTestId("transcript-you-row")).not.toBeInTheDocument();
    });
});

describe("TranscriptWorkingRow", () => {
    it("renders the real operation label as a RUN row", () => {
        render(<TranscriptWorkingRow operationMessage="Searching UAE listings…" fallback="Working…" />);
        expect(screen.getByTestId("transcript-run-row")).toHaveTextContent("Searching UAE listings…");
        expect(screen.getByTestId("transcript-run-row")).toHaveTextContent("run");
    });

    it("renders the serif Thinking… shimmer when no operation label exists", () => {
        render(<TranscriptWorkingRow operationMessage={null} fallback="Working…" />);
        const waiting = screen.getByTestId("transcript-waiting-row");
        expect(waiting).toBeInTheDocument();
        expect(waiting).toHaveTextContent(/thinking/i);
        expect(screen.queryByTestId("transcript-run-row")).not.toBeInTheDocument();
    });
});

/**
 * History-replay suppression — a message hydrated from bulk history (initial
 * load or session switch) must not replay the entrance animation. Only rows
 * for genuinely new/live messages animate in.
 */
describe("CommandTranscriptStep — skipEntranceAnimation (history replay)", () => {
    it("you row: carries the entrance class by default, omits it when hydrated from history", () => {
        const { rerender } = render(
            <CommandTranscriptStep authenticated message={{ role: "user", text: "hi" } as never} isFirstInGroup isStructured={false}>
                hi
            </CommandTranscriptStep>,
        );
        expect(screen.getByTestId("transcript-you-row").className).toMatch(/animate-in/);

        rerender(
            <CommandTranscriptStep authenticated message={{ role: "user", text: "hi" } as never} isFirstInGroup isStructured={false} skipEntranceAnimation>
                hi
            </CommandTranscriptStep>,
        );
        expect(screen.getByTestId("transcript-you-row").className).not.toMatch(/animate-in/);
    });

    it("rico row: omits the entrance class when hydrated from history", () => {
        render(
            <CommandTranscriptStep authenticated message={{ role: "rico", text: "hi" } as never} isFirstInGroup isStructured={false} skipEntranceAnimation>
                hi
            </CommandTranscriptStep>,
        );
        expect(screen.getByTestId("transcript-rico-row").className).not.toMatch(/animate-in/);
    });

    it("needs-input row: omits the entrance class when hydrated from history", () => {
        render(
            <CommandTranscriptStep
                authenticated
                message={{ role: "rico", type: "clarification", text: "Which role?" } as never}
                isFirstInGroup
                isStructured={false}
                skipEntranceAnimation
            >
                Which role?
            </CommandTranscriptStep>,
        );
        const row = screen.getByTestId("transcript-needs-input-row");
        expect(row.parentElement?.className).not.toMatch(/animate-in/);
    });

    it("card row: omits the entrance class when hydrated from history", () => {
        render(
            <CommandTranscriptStep
                authenticated
                message={{ role: "rico", text: "", matches: [{}] } as never}
                isFirstInGroup
                isStructured={false}
                skipEntranceAnimation
            >
                card content
            </CommandTranscriptStep>,
        );
        expect(screen.getByTestId("transcript-card-row").className).not.toMatch(/animate-in/);
    });

    it("public/guest surface: CommandMessageRow also honors skipEntranceAnimation", () => {
        const { rerender } = render(
            <CommandTranscriptStep authenticated={false} message={{ role: "user", text: "hi" } as never} isFirstInGroup isStructured={false}>
                hi
            </CommandTranscriptStep>,
        );
        expect(document.querySelector('[dir="ltr"]')?.className).toMatch(/animate-in/);

        rerender(
            <CommandTranscriptStep authenticated={false} message={{ role: "user", text: "hi" } as never} isFirstInGroup isStructured={false} skipEntranceAnimation>
                hi
            </CommandTranscriptStep>,
        );
        expect(document.querySelector('[dir="ltr"]')?.className).not.toMatch(/animate-in/);
    });
});
