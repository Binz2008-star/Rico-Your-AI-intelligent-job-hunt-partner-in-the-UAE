/**
 * CV storage-quota error mapping — contract tests.
 *
 * The backend (src/services/subscription_gating.py enforce_document_quota)
 * rejects uploads over the plan's CV limit with HTTP 422 and a STRUCTURED
 * dict detail (sentinel: detail.detail === "cv_storage_limit_exceeded").
 * Before this fix, /command mapped every non-413 upload failure to the
 * generic "Could not process your CV" copy — factually wrong for quota.
 *
 * Fixtures below mirror the real backend payload byte-for-byte (no
 * self-fulfilling mocks): these tests exercise the exact JSON a production
 * 422 carries.
 *
 * Contracts:
 *  - getCvQuotaError returns metadata ONLY for the exact quota sentinel on a
 *    422 ApiError; every other error/value → null (413 and generic paths in
 *    /command stay unchanged by construction).
 *  - extractDetail keeps its string/array behavior exactly, and now also
 *    surfaces `message` from object-shaped details.
 *  - cvQuotaCountSuffix appends " (used/limit)" only when BOTH counts are
 *    valid finite numbers (0 is valid).
 */

import {
    ApiError,
    cvQuotaCountSuffix,
    extractDetail,
    getCvQuotaError,
} from "@/lib/api";
import { describe, expect, it } from "vitest";

/** Exact shape raised by enforce_document_quota (subscription_gating.py). */
const QUOTA_BODY = {
    detail: {
        detail: "cv_storage_limit_exceeded",
        plan: "pro",
        used: 5,
        limit: 5,
        upgrade_hint: "Upgrade to Rico Monthly for up to 5 CVs",
        doc_type: "cv",
        message:
            "You have reached your CV storage limit (5/5) on the Pro plan. " +
            "Upgrade to Rico Monthly for up to 5 CVs.",
    },
};

describe("getCvQuotaError — recognizes only the exact quota sentinel", () => {
    it("returns structured metadata for the real quota 422 payload", () => {
        const err = new ApiError("422 /api/v1/rico/upload-cv", 422, QUOTA_BODY);
        expect(getCvQuotaError(err)).toEqual({
            used: 5,
            limit: 5,
            plan: "pro",
            message: QUOTA_BODY.detail.message,
        });
    });

    it("still recognizes the sentinel when optional fields are missing", () => {
        const err = new ApiError("422", 422, {
            detail: { detail: "cv_storage_limit_exceeded" },
        });
        expect(getCvQuotaError(err)).toEqual({
            used: undefined,
            limit: undefined,
            plan: undefined,
            message: undefined,
        });
    });

    it("returns null for the empty-file 422 (string detail)", () => {
        const err = new ApiError("Uploaded file is empty", 422, {
            detail: "Uploaded file is empty",
        });
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for the executable-file 422 (string detail)", () => {
        const err = new ApiError("Executable files are not accepted", 422, {
            detail: "Executable files are not accepted",
        });
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for an unrelated object-detail 422 (other quota)", () => {
        const err = new ApiError("422", 422, {
            detail: {
                detail: "other_document_limit_exceeded",
                plan: "free",
                used: 2,
                limit: 2,
                message: "You have reached your document storage limit (2/2).",
            },
        });
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for a FastAPI validation-array quota lookalike", () => {
        const err = new ApiError("422", 422, {
            detail: [
                { msg: "cv_storage_limit_exceeded", loc: ["body", "file"], type: "value_error" },
            ],
        });
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for a 413 even with a quota-shaped body", () => {
        const err = new ApiError("413", 413, QUOTA_BODY);
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for a 500 even with a quota-shaped body", () => {
        const err = new ApiError("500", 500, QUOTA_BODY);
        expect(getCvQuotaError(err)).toBeNull();
    });

    it("returns null for a plain Error", () => {
        expect(getCvQuotaError(new Error("network down"))).toBeNull();
    });

    it("returns null for unknown values", () => {
        expect(getCvQuotaError(null)).toBeNull();
        expect(getCvQuotaError(undefined)).toBeNull();
        expect(getCvQuotaError("cv_storage_limit_exceeded")).toBeNull();
        expect(getCvQuotaError(422)).toBeNull();
        expect(getCvQuotaError({})).toBeNull();
    });

    it("drops non-number counts and non-string plan/message instead of passing them through", () => {
        const err = new ApiError("422", 422, {
            detail: {
                detail: "cv_storage_limit_exceeded",
                used: "5",
                limit: null,
                plan: 3,
                message: { text: "nope" },
            },
        });
        expect(getCvQuotaError(err)).toEqual({
            used: undefined,
            limit: undefined,
            plan: undefined,
            message: undefined,
        });
    });
});

describe("extractDetail — object extension preserves existing behavior", () => {
    it("returns string details unchanged (existing behavior)", () => {
        expect(extractDetail("Uploaded file is empty", "fallback")).toBe(
            "Uploaded file is empty",
        );
    });

    it("returns the first msg from validation arrays unchanged (existing behavior)", () => {
        expect(
            extractDetail(
                [{ msg: "field required", loc: ["body", "file"] }],
                "fallback",
            ),
        ).toBe("field required");
        expect(extractDetail([{ message: "alt message" }], "fallback")).toBe("alt message");
        expect(extractDetail([], "fallback")).toBe("fallback");
    });

    it("surfaces message from object-shaped details (new)", () => {
        expect(extractDetail(QUOTA_BODY.detail, "fallback")).toBe(
            QUOTA_BODY.detail.message,
        );
    });

    it("falls back for objects without a string message, and for null/undefined", () => {
        expect(extractDetail({ detail: "x" }, "fallback")).toBe("fallback");
        expect(extractDetail({ message: 42 }, "fallback")).toBe("fallback");
        expect(extractDetail(null, "fallback")).toBe("fallback");
        expect(extractDetail(undefined, "fallback")).toBe("fallback");
    });
});

describe("cvQuotaCountSuffix — appended only when both counts are valid", () => {
    it("formats ' (used/limit)' when both are finite numbers", () => {
        expect(cvQuotaCountSuffix({ used: 5, limit: 5 })).toBe(" (5/5)");
        expect(cvQuotaCountSuffix({ used: 0, limit: 1 })).toBe(" (0/1)");
    });

    it("returns empty string when either count is missing or invalid", () => {
        expect(cvQuotaCountSuffix({ used: 5 })).toBe("");
        expect(cvQuotaCountSuffix({ limit: 5 })).toBe("");
        expect(cvQuotaCountSuffix({})).toBe("");
        expect(cvQuotaCountSuffix({ used: NaN, limit: 5 })).toBe("");
        expect(cvQuotaCountSuffix({ used: Infinity, limit: 5 })).toBe("");
    });
});
