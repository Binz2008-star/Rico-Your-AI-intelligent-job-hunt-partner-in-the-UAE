import { describe, expect, it, vi } from "vitest";
import { normalizeStreamDoneEvent, type ChatStreamEvent } from "@/lib/api";

/**
 * SSE↔JSON parity for the tolerance contract (#1191/#1193).
 *
 * The non-streaming path validates every reply through the tolerant
 * RicoChatResponseSchema; the SSE path used to yield the `done` payload as a
 * raw cast, so the same malformed field the JSON path would normalize
 * (unknown verification_status, junk scores, malformed match rows) could
 * reach the UI unnormalized. These tests pin the stream path to the same
 * contract: annotation fields degrade, rows are salvaged individually, and a
 * hopeless payload drops to text-only — a reply is never rejected.
 */

function doneEvent(response: unknown): ChatStreamEvent {
    return { type: "done", response } as ChatStreamEvent;
}

describe("normalizeStreamDoneEvent — SSE parity with the tolerant JSON path", () => {
    it("normalizes the done payload: numeric-string scores coerce, malformed rows are salvaged out", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const event = normalizeStreamDoneEvent(doneEvent({
                response: "Got it — I found matches.",
                type: "job_matches",
                matches: [
                    { title: "HSE Manager", company: "Gulf Contractor", score: "82", verification_status: "aggregator_untrusted" },
                    "not-a-match-row",
                    { title: "HSE Officer", company: "Marina Group", score: 74, verification_status: "live_verified" },
                ],
            }));
            expect(event.response?.matches).toHaveLength(2);
            expect(event.response?.matches?.[0].score).toBe(82);
            expect(event.response?.matches?.[0].verification_status).toBe("aggregator_untrusted");
            expect(event.response?.matches?.[1].verification_status).toBe("live_verified");
            expect(warn).toHaveBeenCalled();
        } finally {
            warn.mockRestore();
        }
    });

    it("normalizes an unknown verification_status to needs_source_verification (never promotes)", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const event = normalizeStreamDoneEvent(doneEvent({
                message: "assembled stream text",
                type: "conversational",
                response_source: "stream",
                matches: [{ title: "Safety Officer", verification_status: "brand_new_status" }],
            }));
            expect(event.response?.matches?.[0].verification_status).toBe("needs_source_verification");
        } finally {
            warn.mockRestore();
        }
    });

    it("drops a hopeless structured payload but keeps the done event (streamed text still renders)", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const event = normalizeStreamDoneEvent(doneEvent("not-an-object"));
            expect(event.type).toBe("done");
            expect(event.response).toBeUndefined();
            expect(warn).toHaveBeenCalled();
        } finally {
            warn.mockRestore();
        }
    });

    it("passes token and error events through by identity", () => {
        const token: ChatStreamEvent = { type: "token", text: "hel" };
        const error: ChatStreamEvent = { type: "error", error: "500" };
        expect(normalizeStreamDoneEvent(token)).toBe(token);
        expect(normalizeStreamDoneEvent(error)).toBe(error);
    });

    it("leaves a done event without a structured payload unchanged", () => {
        const done: ChatStreamEvent = { type: "done" };
        expect(normalizeStreamDoneEvent(done)).toBe(done);
    });
});
