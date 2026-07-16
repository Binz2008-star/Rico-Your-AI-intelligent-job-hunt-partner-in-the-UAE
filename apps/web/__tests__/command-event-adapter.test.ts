/**
 * CommandEventAdapter — slice C2 pure-mapping contracts.
 *
 * Anti-fabrication is the core contract: every canonical row kind must be
 * derivable ONLY from real production state; absent state yields nothing.
 */

import {
    classifyMessage,
    deriveStatus,
    realProgressRows,
    runLabel,
    type TranscriptMessageLike,
} from "@/components/command/CommandEventAdapter";
import { describe, expect, it } from "vitest";

const rico = (extra: Partial<TranscriptMessageLike> = {}): TranscriptMessageLike => ({
    role: "rico",
    text: "hello",
    ...extra,
});

describe("classifyMessage", () => {
    it("maps real user turns to YOU", () => {
        expect(classifyMessage({ role: "user", text: "find jobs" })).toBe("you");
    });

    it("maps plain Rico text to RICO — including streaming turns", () => {
        expect(classifyMessage(rico())).toBe("rico");
        expect(classifyMessage(rico({ streaming: true }))).toBe("rico");
        expect(classifyMessage(rico({ type: "options" }))).toBe("rico");
    });

    it("maps real error turns to FAIL and real stopped turns to STOPPED", () => {
        expect(classifyMessage(rico({ isError: true }))).toBe("fail");
        expect(classifyMessage(rico({ type: "stopped" }))).toBe("stopped");
    });

    it("maps card-bearing turns to CARD (presentation unchanged until C4/C5)", () => {
        expect(classifyMessage(rico({ type: "job_matches", matches: [{}] }))).toBe("card");
        expect(classifyMessage(rico({ type: "profile_preview", preview: {} }))).toBe("card");
        expect(classifyMessage(rico({ type: "application_status", applications: [{}] }))).toBe("card");
        expect(classifyMessage(rico({ profile_gaps: ["city"] }))).toBe("card");
        expect(
            classifyMessage(rico({ agentic_ui: { actions: [], permission_request: { id: "p1" } as never, progress: [], proposed_changes: [], attachment_analysis: [] } })),
        ).toBe("card");
    });

    it("never invents a card: empty agentic_ui stays a plain RICO row", () => {
        expect(
            classifyMessage(rico({ agentic_ui: { actions: [], permission_request: null, progress: [], proposed_changes: [], attachment_analysis: [] } })),
        ).toBe("rico");
    });
});

describe("realProgressRows — no fabricated PLAN/TOOL events", () => {
    it("returns exactly the API-sent progress items", () => {
        const progress = [{ id: "s1", label: "Reading your CV", status: "complete" as const }];
        expect(realProgressRows(rico({ agentic_ui: { actions: [], permission_request: null, progress, proposed_changes: [], attachment_analysis: [] } }))).toEqual(progress);
    });

    it("returns nothing when the API sent nothing", () => {
        expect(realProgressRows(rico())).toEqual([]);
        expect(realProgressRows(rico({ agentic_ui: null }))).toEqual([]);
    });
});

describe("deriveStatus — real state only", () => {
    it("ready when idle, working while thinking, replying while streaming", () => {
        expect(deriveStatus({ thinking: false, streaming: false })).toBe("ready");
        expect(deriveStatus({ thinking: true, streaming: false })).toBe("working");
        expect(deriveStatus({ thinking: false, streaming: true })).toBe("replying");
        expect(deriveStatus({ thinking: true, streaming: true })).toBe("replying");
    });
});

describe("runLabel — safe operational language only", () => {
    it("passes through the real operation-state message", () => {
        expect(runLabel("Searching matching roles…", "Working…")).toBe("Searching matching roles…");
    });
    it("falls back to the generic working label — never a fabricated tool name", () => {
        expect(runLabel(null, "Working…")).toBe("Working…");
        expect(runLabel("   ", "Working…")).toBe("Working…");
    });
});
