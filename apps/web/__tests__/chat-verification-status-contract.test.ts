/**
 * verification_status contract — regression for the 2026-07-19 production
 * incident: the schema's stale 2-value enum rejected a valid REST-fallback
 * chat response carrying `verification_status: "aggregator_untrusted"`,
 * validateShape threw ("Invalid authenticated Rico chat response" —
 * lib/api.ts) and the user saw a generic error although the server had
 * executed exactly one search and stored the full reply.
 *
 * Pins:
 * 1. The (sanitized) production payload shape now parses.
 * 2. Every current backend status value passes verbatim.
 * 3. An unknown future value is never promoted to a trusted status —
 *    it normalizes to 'needs_source_verification' with a console warning —
 *    and never discards the response wholesale.
 * 4. The REST fallback path (sendChat → validateShape) resolves and keeps
 *    matches + message intact.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KNOWN_VERIFICATION_STATUSES, RicoChatResponseSchema } from "@/lib/schemas";
import { sendChat } from "@/lib/api";

/** Shape-faithful, sanitized replica of the stored production reply
 * (rico_chat_history row 023f6f96…, 16:22:43Z) — personal profile wording
 * removed; structure, keys, and the failing field value preserved. */
function productionShapedPayload(verificationStatus: string): Record<string, unknown> {
    return {
        type: "job_matches",
        intent: "search_jobs",
        message: "Got it — I will target the requested roles in the UAE. I found 1 match(es) with provider data available.",
        matches: [
            {
                title: "Head of Trading Risk",
                company: "Bybit",
                score: 0.0,
                apply_url: "https://jooble.org/jdp/0000000000000000000",
                source_url: "https://jooble.org/jdp/0000000000000000000",
                alt_link: "",
                employer_url: "",
                usable_link: "",
                link_unavailable: true,
                link_unavailable_reason: "untrusted_aggregator",
                apply_verified: false,
                verification_status: verificationStatus,
                company_quality: "ok",
                actions: ["Prepare application", "Save", "Ask why", "Skip"],
                confidence: "low",
                match_reasons: ["Location: United Arab Emirates."],
                match_concerns: ["Role title doesn't clearly match the saved targets."],
                missing_facts: ["salary range"],
                recommended_action: "Review the risk areas before applying.",
                verdict: "weak_fit",
                summary: "Looks weaker against the current profile signals.",
                match_explanation: {
                    verdict: "weak_fit",
                    summary: "Looks weaker against the current profile signals.",
                    why_this_fits: ["Role title appears relevant enough to review."],
                    worth_checking: ["Salary is not listed."],
                    recommended_next_step: "Skip this role or refine the target role.",
                    confidence: "low",
                },
                location: "United Arab Emirates",
                employment_type: "Full-time",
                description: "&nbsp;...Responsibilities \r\n~ Team Leadership & Strategy",
                fallback_cta: [
                    { action: "open_url", label: "Search on Google", url: "https://www.google.com/search?q=x" },
                    { action: "copy_text", label: "Copy title & company", text: "Head of Trading Risk — Bybit" },
                    { action: "save_job", label: "Save to pipeline", message: "save Head of Trading Risk at Bybit" },
                ],
            },
        ],
        entities: { job_title: "HSE Manager", from_cv_profile: true },
        operation_id: "op_web_00000000000000000000000000000000",
        operation_status: "completed",
        operation_type: "job_search",
        result_count: 1,
        search_query: "HSE Manager",
        broadened: false,
        rate_limited: false,
        integrity_filtered: { total: 21, by_reason: { title_role_mismatch: 21 } },
    };
}

beforeEach(() => {
    vi.restoreAllMocks();
});

describe("verification_status contract", () => {
    it("accepts the production payload that previously failed (aggregator_untrusted)", () => {
        const result = RicoChatResponseSchema.safeParse(productionShapedPayload("aggregator_untrusted"));
        expect(result.success).toBe(true);
        if (result.success) {
            // The response is never dropped wholesale: matches + message intact.
            expect(result.data.matches).toHaveLength(1);
            expect(result.data.matches![0].verification_status).toBe("aggregator_untrusted");
            expect(result.data.message).toContain("I found 1 match(es)");
        }
    });

    it("accepts every current backend status value verbatim", () => {
        for (const status of KNOWN_VERIFICATION_STATUSES) {
            const result = RicoChatResponseSchema.safeParse(productionShapedPayload(status));
            expect(result.success, `status "${status}" must parse`).toBe(true);
            if (result.success) {
                expect(result.data.matches![0].verification_status).toBe(status);
            }
        }
    });

    it("covers the owner-required five backend values", () => {
        for (const required of [
            "live_verified",
            "login_required",
            "rate_limited",
            "aggregator_untrusted",
            "needs_source_verification",
        ]) {
            expect(KNOWN_VERIFICATION_STATUSES).toContain(required);
        }
    });

    it("normalizes an unknown future value to needs_source_verification — never to a trusted status, never dropping the response", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        const result = RicoChatResponseSchema.safeParse(productionShapedPayload("brand_new_status_v9"));
        expect(result.success).toBe(true);
        if (result.success) {
            const normalized = result.data.matches![0].verification_status;
            expect(normalized).toBe("needs_source_verification");
            expect(normalized).not.toBe("live_verified");
            expect(result.data.matches).toHaveLength(1);
        }
        expect(warn).toHaveBeenCalledTimes(1);
        expect(String(warn.mock.calls[0][0])).toContain("brand_new_status_v9");
    });

    it("treats empty/absent status as absent (optional), not an error", () => {
        for (const empty of ["", undefined]) {
            const payload = productionShapedPayload("x");
            (payload.matches as Record<string, unknown>[])[0].verification_status = empty;
            const result = RicoChatResponseSchema.safeParse(payload);
            expect(result.success).toBe(true);
            if (result.success) {
                expect(result.data.matches![0].verification_status).toBeUndefined();
            }
        }
    });
});

describe("REST fallback path stays visible (sendChat → validateShape)", () => {
    it("resolves with matches and message intact for the incident payload", async () => {
        const fetchMock = vi.fn(async () => ({
            ok: true,
            status: 200,
            json: async () => productionShapedPayload("aggregator_untrusted"),
        }));
        vi.stubGlobal("fetch", fetchMock);

        const res = await sendChat("find hse manager jobs", undefined, "op_web_test_contract_1");
        expect(res.type).toBe("job_matches");
        expect(res.matches).toHaveLength(1);
        expect(res.message).toContain("I found 1 match(es)");
    });
});
