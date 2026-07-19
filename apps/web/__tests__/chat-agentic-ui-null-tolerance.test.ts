/**
 * agentic_ui null-tolerance (2026-07-19 profile-report incident).
 *
 * Backends before the _finalize fix send `agentic_ui: null` for card-less
 * text replies. That null rejected the ENTIRE reply ("expected object,
 * received null"): the SSE done payload was silently dropped and the REST
 * fallback threw — the user saw the generic error bubble while the full
 * reply sat persisted in chat history. The schema must normalize null to
 * "absent" like every other tolerant field, keep real objects unchanged,
 * and keep accepting the new backend's omitted key.
 */
import { describe, expect, it } from "vitest";
import { RicoChatResponseSchema } from "../lib/schemas";

const textReply = {
    type: "text",
    message: "أهلاً بك. إليك تقرير ملفك الشخصي…",
    response_source: "deepseek",
    provider: "deepseek",
    model: "deepseek-v4-flash",
    openai_available: true,
    deepseek_available: true,
    hf_available: false,
    provider_available: true,
    openai_model: "deepseek-v4-flash",
    active_provider: "deepseek",
    profile_context_present: true,
    jotform_form_id: "",
    success: true,
};

describe("RicoChatResponseSchema agentic_ui tolerance", () => {
    it("normalizes agentic_ui: null to absent instead of rejecting the reply (THE incident shape)", () => {
        const parsed = RicoChatResponseSchema.safeParse({ ...textReply, agentic_ui: null });
        expect(parsed.success).toBe(true);
        if (parsed.success) expect(parsed.data.agentic_ui).toBeUndefined();
    });

    it("accepts the new backend contract: key omitted entirely", () => {
        const parsed = RicoChatResponseSchema.safeParse(textReply);
        expect(parsed.success).toBe(true);
        if (parsed.success) expect(parsed.data.agentic_ui).toBeUndefined();
    });

    it("keeps a real agentic_ui object unchanged", () => {
        const parsed = RicoChatResponseSchema.safeParse({
            ...textReply,
            type: "job_matches",
            agentic_ui: { actions: [], progress: [] },
        });
        expect(parsed.success).toBe(true);
        if (parsed.success) {
            expect(parsed.data.agentic_ui).toBeDefined();
            expect(parsed.data.agentic_ui?.actions).toEqual([]);
        }
    });
});
