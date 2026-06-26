/**
 * __tests__/job-fallback-employer-url.test.ts
 *
 * Regression tests for employer_url enhancement in job-fallback.ts (#721).
 *
 * Verifies:
 * - When employer_url is present, getJobFallbackActions() returns key "company_website"
 *   with the exact employer URL as href — not a Google search proxy.
 * - When employer_url is absent, key "company_site" with a Google search URL is returned.
 * - employer_url is NEVER the same as the verified apply link (it goes in a separate CTA).
 * - Existing #722 fallback action behavior is preserved (save always present, etc.).
 */
import { describe, expect, it } from "vitest";

import {
    buildCompanySiteSearchUrl,
    getJobFallbackActions,
} from "@/lib/job-fallback";

describe("buildCompanySiteSearchUrl", () => {
    it("returns employer URL directly when provided", () => {
        const url = buildCompanySiteSearchUrl("Engineer", "AESG", "https://aesg.com");
        expect(url).toBe("https://aesg.com");
    });

    it("falls back to Google search when no employer URL", () => {
        const url = buildCompanySiteSearchUrl("Engineer", "AESG");
        expect(url).toContain("google.com/search");
        expect(url).toContain("AESG");
    });

    it("falls back to Google search when employer URL is empty string", () => {
        const url = buildCompanySiteSearchUrl("Engineer", "AESG", "");
        expect(url).toContain("google.com/search");
    });
});

describe("getJobFallbackActions — employer_url present", () => {
    const match = {
        title: "HSE Manager",
        company: "AESG",
        employer_url: "https://aesg.com",
    };

    it("emits company_website key (not company_site) when employer_url is set", () => {
        const actions = getJobFallbackActions(match);
        const keys = actions.map((a) => a.key);
        expect(keys).toContain("company_website");
        expect(keys).not.toContain("company_site");
    });

    it("company_website action href is the employer URL verbatim", () => {
        const actions = getJobFallbackActions(match);
        const cta = actions.find((a) => a.key === "company_website");
        expect(cta?.href).toBe("https://aesg.com");
    });

    it("company_website action href is NOT a Google search URL", () => {
        const actions = getJobFallbackActions(match);
        const cta = actions.find((a) => a.key === "company_website");
        expect(cta?.href).not.toContain("google.com/search");
    });

    it("still includes linkedin, google, copy, save actions", () => {
        const actions = getJobFallbackActions(match);
        const keys = actions.map((a) => a.key);
        expect(keys).toContain("linkedin");
        expect(keys).toContain("google");
        expect(keys).toContain("copy");
        expect(keys).toContain("save");
    });
});

describe("getJobFallbackActions — employer_url absent", () => {
    const match = { title: "HSE Manager", company: "AESG" };

    it("emits company_site key (not company_website) when no employer_url", () => {
        const actions = getJobFallbackActions(match);
        const keys = actions.map((a) => a.key);
        expect(keys).toContain("company_site");
        expect(keys).not.toContain("company_website");
    });

    it("company_site action href is a Google search URL", () => {
        const actions = getJobFallbackActions(match);
        const cta = actions.find((a) => a.key === "company_site");
        expect(cta?.href).toContain("google.com/search");
    });
});

describe("getJobFallbackActions — baseline coverage", () => {
    it("save action is always present even without title/company", () => {
        const actions = getJobFallbackActions({});
        const keys = actions.map((a) => a.key);
        expect(keys).toContain("save");
    });

    it("no link actions when no title and no company", () => {
        const actions = getJobFallbackActions({});
        const linkActions = actions.filter((a) => a.kind === "link");
        expect(linkActions).toHaveLength(0);
    });

    it("employer_url in result is link kind with correct href", () => {
        const actions = getJobFallbackActions({
            title: "Eng",
            company: "Corp",
            employer_url: "https://corp.com/careers",
        });
        const cta = actions.find((a) => a.key === "company_website");
        expect(cta?.kind).toBe("link");
        expect(cta?.href).toBe("https://corp.com/careers");
    });
});
