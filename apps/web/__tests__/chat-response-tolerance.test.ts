import { describe, expect, it, vi } from "vitest";
import {
    JobMatchSchema,
    KNOWN_VERIFICATION_STATUSES,
    RicoChatResponseSchema,
} from "@/lib/schemas";

/**
 * Complementary fail-open hardening on top of the #1191 verification_status
 * contract (production incident 2026-07-19 16:22Z).
 *
 * #1191 fixed the enum that rejected `aggregator_untrusted`; this suite pins
 * the REST of the same failure class: null/unknown confidence,
 * numeric-string/junk scores, null top-level booleans/records, and any one
 * malformed match row could still reject the ENTIRE reply at validateShape
 * and show the generic FAIL bubble. Annotation-grade fields may degrade —
 * never reject a reply (per-row salvage = batch-row-isolation, backend #887
 * philosophy).
 */

function productionMatch(verification_status: string) {
    return {
        title: "HSE Manager",
        company: "Gulf Contractor",
        location: "Dubai, UAE",
        score: 82,
        why: "Location and role match",
        actions: ["save", "skip"],
        confidence: "medium",
        match_reasons: ["HSE background"],
        match_concerns: [],
        missing_facts: [],
        recommended_action: "review",
        apply_url: "https://jooble.org/redirect/x",
        source_url: "https://jooble.org/job/x",
        verification_status,
    };
}

describe("production repro — 2026-07-19 16:22Z jooble payload (regression pin)", () => {
    it("a 23-match reply, all aggregator_untrusted, parses with values preserved", () => {
        const parsed = RicoChatResponseSchema.parse({
            response: "Got it — I found 23 matches.",
            type: "job_matches",
            matches: Array.from({ length: 23 }, () => productionMatch("aggregator_untrusted")),
        });
        expect(parsed.matches).toHaveLength(23);
        expect(parsed.matches?.[0].verification_status).toBe("aggregator_untrusted");
    });

    it("every value in the #1191 contract parses and is preserved", () => {
        for (const status of KNOWN_VERIFICATION_STATUSES) {
            const parsed = JobMatchSchema.safeParse(productionMatch(status));
            expect(parsed.success, `verification_status=${status}`).toBe(true);
            if (parsed.success) expect(parsed.data.verification_status).toBe(status);
        }
    });

    it("an unknown future status normalizes to needs_source_verification (never rejects, never promotes)", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const parsed = JobMatchSchema.parse(productionMatch("brand_new_status"));
            expect(parsed.verification_status).toBe("needs_source_verification");
            expect(warn).toHaveBeenCalled();
        } finally {
            warn.mockRestore();
        }
    });
});

describe("fail-open annotation fields (the rest of the failure class)", () => {
    it("unknown or null confidence degrades to undefined instead of rejecting", () => {
        for (const confidence of ["very_high", "", null, 3]) {
            const parsed = JobMatchSchema.safeParse({ ...productionMatch("live"), confidence });
            expect(parsed.success, `confidence=${String(confidence)}`).toBe(true);
            if (parsed.success) expect(parsed.data.confidence).toBeUndefined();
        }
    });

    it("numeric-string scores coerce; junk scores degrade to undefined", () => {
        expect(JobMatchSchema.parse({ ...productionMatch("live"), score: "85" }).score).toBe(85);
        expect(JobMatchSchema.parse({ ...productionMatch("live"), score: "hot" }).score).toBeUndefined();
    });

    it("null top-level booleans and records never reject the reply", () => {
        const parsed = RicoChatResponseSchema.parse({
            response: "ok",
            success: null,
            profile_context_present: null,
            entities: null,
            tool_args: null,
        });
        expect(parsed.success).toBeUndefined();
        expect(parsed.profile_context_present).toBeUndefined();
        expect(parsed.entities).toBeUndefined();
        expect(parsed.tool_args).toBeUndefined();
    });
});

describe("per-row salvage (batch-row-isolation)", () => {
    it("drops only the malformed match, keeps siblings, and warns", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const parsed = RicoChatResponseSchema.parse({
                response: "found roles",
                matches: [
                    productionMatch("aggregator_untrusted"),
                    "not-an-object-at-all",
                    productionMatch("live_verified"),
                ],
            });
            expect(parsed.matches).toHaveLength(2);
            expect(parsed.matches?.map((m) => m.verification_status)).toEqual([
                "aggregator_untrusted",
                "live_verified",
            ]);
            expect(warn).toHaveBeenCalled();
        } finally {
            warn.mockRestore();
        }
    });

    it("null and absent matches still normalize to undefined", () => {
        expect(RicoChatResponseSchema.parse({ response: "ok", matches: null }).matches).toBeUndefined();
        expect(RicoChatResponseSchema.parse({ response: "ok" }).matches).toBeUndefined();
    });
});
