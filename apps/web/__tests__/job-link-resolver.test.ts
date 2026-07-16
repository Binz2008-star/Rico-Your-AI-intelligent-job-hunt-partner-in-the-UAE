/**
 * resolveJobLink — the SHARED primary apply-link decision tree used by BOTH the
 * public `JobMatchCard` (app/command/page.tsx) and the authenticated
 * `JobMatchCardAtelier`. Extracted into lib/job-fallback.ts so the two cards
 * are single-sourced and their trust behaviour (BUG-03) can never drift.
 *
 * This suite is the parameterized PARITY TABLE the reviewer asked for: it walks
 * EVERY branch of the apply/source/alt/unavailable decision — verified direct
 * apply, UNtrusted apply (BUG-03), source-only, alt (google_intermediary), the
 * degraded-primary alt fallback, and the no-link (fallback-actions) case —
 * asserting the resolved href, the (locale-independent) label KEY, the test id,
 * the trust flag, and the secondary-source flag. Because the label is returned
 * as a translation KEY, these assertions are language-agnostic and pin the
 * exact contract both cards render.
 */

import { describe, expect, it } from "vitest";

import type { JobMatch } from "@/lib/api";
import {
    isGoogleIntermediary,
    resolveJobLink,
    type JobLinkLabelKey,
    type JobLinkTestId,
} from "@/lib/job-fallback";

const APPLY = "https://careers.example.com/jobs/123";
const SOURCE = "https://boards.example.com/listing/123";
const ALT = "https://www.linkedin.com/jobs/view/123";
const GOOGLE = "https://www.google.com/search?q=hse+manager";

interface Row {
    name: string;
    match: Partial<JobMatch>;
    expect: {
        linkHref: string;
        linkLabelKey: JobLinkLabelKey;
        linkTestId: JobLinkTestId;
        isBadPrimary: boolean;
        showSource: boolean;
    };
}

const TABLE: Row[] = [
    {
        // Branch 1 — verified direct apply (highest trust).
        name: "verified direct apply → job-link-apply/cmdApply",
        match: { apply_url: APPLY, verification_status: "live_verified" },
        expect: {
            linkHref: APPLY,
            linkLabelKey: "cmdApply",
            linkTestId: "job-link-apply",
            isBadPrimary: false,
            showSource: false,
        },
    },
    {
        // Branch 1 + secondary — apply + a differing trusted source_url shows the
        // secondary "View source" link alongside the primary Apply.
        name: "verified apply + differing source → shows secondary source",
        match: { apply_url: APPLY, source_url: SOURCE, verification_status: "live_verified" },
        expect: {
            linkHref: APPLY,
            linkLabelKey: "cmdApply",
            linkTestId: "job-link-apply",
            isBadPrimary: false,
            showSource: true,
        },
    },
    {
        // BUG-03 — an UNtrusted apply_url must NEVER surface as a verified Apply
        // link. With no alt/source to fall back to, the card is link-unavailable.
        name: "UNtrusted apply (aggregator_untrusted), no alt/source → no link (BUG-03)",
        match: { apply_url: APPLY, verification_status: "aggregator_untrusted" },
        expect: {
            linkHref: "",
            linkLabelKey: "",
            linkTestId: "",
            isBadPrimary: true,
            showSource: false,
        },
    },
    {
        // BUG-03 — degraded primary with an alt link falls back to the alt as an
        // honestly-labelled "Alt link", NOT the untrusted apply_url.
        name: "UNtrusted apply + alt (login_required) → job-link-alt/cmdApplyAlt (not the apply_url)",
        match: { apply_url: APPLY, alt_link: ALT, verification_status: "login_required" },
        expect: {
            linkHref: ALT,
            linkLabelKey: "cmdApplyAlt",
            linkTestId: "job-link-alt",
            isBadPrimary: true,
            showSource: false,
        },
    },
    {
        // BUG-03 — rate_limited primary with only a source_url falls back to the
        // source as an "Alt link" (still never labelled a verified apply).
        name: "rate_limited primary + source only → job-link-alt/cmdApplyAlt",
        match: { source_url: SOURCE, verification_status: "rate_limited" },
        expect: {
            linkHref: SOURCE,
            linkLabelKey: "cmdApplyAlt",
            linkTestId: "job-link-alt",
            isBadPrimary: true,
            showSource: false,
        },
    },
    {
        // Branch 2 — no apply_url, trusted source_url → "View source".
        name: "source-only, trusted → job-link-source/cmdViewSource",
        match: { source_url: SOURCE, verification_status: "live_verified" },
        expect: {
            linkHref: SOURCE,
            linkLabelKey: "cmdViewSource",
            linkTestId: "job-link-source",
            isBadPrimary: false,
            showSource: false,
        },
    },
    {
        // Branch 3 — google_intermediary with an alt → honest "Search" link.
        name: "google_intermediary + alt → job-link-alt/cmdApplySearch",
        match: { alt_link: ALT, verification_status: "google_intermediary" },
        expect: {
            linkHref: ALT,
            linkLabelKey: "cmdApplySearch",
            linkTestId: "job-link-alt",
            isBadPrimary: true,
            showSource: false,
        },
    },
    {
        // Branch 5 — nothing usable (needs verification, no URLs) → no link, the
        // card falls back to the safe fallback actions (never a dead-end).
        name: "no urls, lead_needs_verification → no link (fallback actions)",
        match: { verification_status: "lead_needs_verification" },
        expect: {
            linkHref: "",
            linkLabelKey: "",
            linkTestId: "",
            isBadPrimary: false,
            showSource: false,
        },
    },
    {
        // Placeholder "#" apply_url is treated as no URL → no link.
        name: "placeholder '#' apply_url → no link",
        match: { apply_url: "#" },
        expect: {
            linkHref: "",
            linkLabelKey: "",
            linkTestId: "",
            isBadPrimary: false,
            showSource: false,
        },
    },
    {
        // A Google-search source_url is stripped (not a real listing) — with a
        // clean apply_url the Apply link stands and no secondary source shows.
        name: "google-search source_url is stripped → no secondary source",
        match: { apply_url: APPLY, source_url: GOOGLE, verification_status: "live_verified" },
        expect: {
            linkHref: APPLY,
            linkLabelKey: "cmdApply",
            linkTestId: "job-link-apply",
            isBadPrimary: false,
            showSource: false,
        },
    },
];

describe("resolveJobLink — apply/source/alt/unavailable parity table", () => {
    it.each(TABLE)("$name", ({ match, expect: exp }) => {
        const r = resolveJobLink(match);
        expect(r.linkHref).toBe(exp.linkHref);
        expect(r.linkLabelKey).toBe(exp.linkLabelKey);
        expect(r.linkTestId).toBe(exp.linkTestId);
        expect(r.isBadPrimary).toBe(exp.isBadPrimary);
        expect(r.showSource).toBe(exp.showSource);
    });

    it("never surfaces an untrusted apply_url as the primary href (BUG-03 invariant)", () => {
        // Across every degraded verification status, the raw apply_url must not
        // become the surfaced primary link.
        const degraded = [
            "login_required",
            "rate_limited",
            "aggregator_untrusted",
            "google_intermediary",
        ] as const;
        for (const status of degraded) {
            const r = resolveJobLink({ apply_url: APPLY, verification_status: status });
            expect(r.linkHref).not.toBe(APPLY);
            expect(r.linkTestId).not.toBe("job-link-apply");
            expect(r.isBadPrimary).toBe(true);
        }
    });

    it("strips Google-intermediary source/alt URLs from the trusted slots", () => {
        expect(isGoogleIntermediary("https://jobs.google.com/xyz")).toBe(true);
        expect(isGoogleIntermediary(GOOGLE)).toBe(true);
        expect(isGoogleIntermediary(SOURCE)).toBe(false);
        const r = resolveJobLink({ source_url: GOOGLE, verification_status: "live_verified" });
        expect(r.sourceUrl).toBe("");
        expect(r.linkHref).toBe("");
    });
});
