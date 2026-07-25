/**
 * One contract, end to end: the backend's ownership-refusal shape must arrive
 * intact and map to an explicit conflict state — never to the generic chat error.
 *
 * The generic error ("I couldn't process your request…") reads as a transient
 * fault and carries a retry affordance. Retrying an ownership refusal cannot
 * succeed, so the two states must stay distinguishable at the boundary where the
 * client decides what to render.
 */
import { describe, expect, it } from "vitest";

import { RicoChatResponseSchema } from "../lib/schemas";
import {
    ACCOUNT_CONFLICT_ERROR,
    ACCOUNT_CONFLICT_TYPE,
    isAccountConflictResponse,
} from "../lib/accountConflict";

// Byte-for-byte the payload src/services/subscription_gating.account_conflict_response builds.
const BACKEND_CONFLICT_PAYLOAD = {
    type: "account_conflict",
    intent: "account_conflict",
    message:
        "This account could not be resolved unambiguously, so it cannot be used right now. Please contact support.",
    response_source: "subscription_gate",
    error: "ambiguous_account_ownership",
    next_action: "contact_support",
};

// What the two top-level chat handlers return for anything they catch.
const GENERIC_CHAT_ERROR = {
    type: "error",
    message: "I couldn't process your request. Reference: ERR-SYNTHETIC. Please try again or rephrase your message.",
};

describe("account-conflict contract", () => {
    it("survives response validation with its type and reason intact", () => {
        const parsed = RicoChatResponseSchema.safeParse(BACKEND_CONFLICT_PAYLOAD);
        expect(parsed.success).toBe(true);
        if (!parsed.success) return;
        expect(parsed.data.type).toBe(ACCOUNT_CONFLICT_TYPE);
        expect(parsed.data.error).toBe(ACCOUNT_CONFLICT_ERROR);
        expect(parsed.data.message).toContain("could not be resolved unambiguously");
    });

    it("is recognised as the explicit conflict state", () => {
        expect(isAccountConflictResponse(BACKEND_CONFLICT_PAYLOAD)).toBe(true);
    });

    it("is never confused with the generic chat error", () => {
        expect(isAccountConflictResponse(GENERIC_CHAT_ERROR)).toBe(false);
        expect(isAccountConflictResponse(null)).toBe(false);
        expect(isAccountConflictResponse(undefined)).toBe(false);
        expect(isAccountConflictResponse({ type: "job_matches" })).toBe(false);
    });

    it("carries no consumption figure the client could render", () => {
        for (const key of ["usage", "limit", "remaining", "plan", "reset_at"]) {
            expect(BACKEND_CONFLICT_PAYLOAD).not.toHaveProperty(key);
        }
    });
});
