/**
 * __tests__/job-card-fallback.test.tsx
 *
 * Regression guard: a rendered job card must NEVER be a dead-end.
 *
 * When the provider returns only degraded results (rate_limited /
 * login_required / aggregator_untrusted / google_intermediary) with no clean
 * alternate link, the card's primary link resolves to "unavailable" by the
 * BUG-03 safety design (we never surface the bad provider URL as Apply). In
 * that state the card must still offer safe, honestly-labelled fallback
 * actions: search the company site / Google / LinkedIn, copy, and save.
 *
 * These tests assert that invariant against the exact production data shape
 * observed in the smoke run (all 5 stored rows were bad-primary with empty
 * alt_url), so a future change can't silently reintroduce dead-end cards.
 */
import { describe, expect, it } from "vitest";
import type { JobMatch } from "@/lib/api";
import {
    getJobFallbackActions,
    buildCompanySiteSearchUrl,
    buildLinkedInSearchUrl,
    buildGoogleSearchUrl,
    buildCopyText,
} from "@/lib/job-fallback";

// Mirror of JobMatchCard's link-resolution decision tree (command/page.tsx).
function _isGoogleIntermediary(u: string): boolean {
    if (!u) return false;
    try {
        const p = new URL(u);
        const h = p.hostname.replace(/^www\./, "");
        return h === "jobs.google.com" || (h === "google.com" && p.pathname.includes("/search"));
    } catch {
        return false;
    }
}

function resolveLinkHref(match: JobMatch): string {
    const clean = (u?: string) => (u && u !== "#" ? u.trim() : "");
    const applyUrl = clean(match.apply_url);
    const sourceUrl = (() => {
        const u = clean(match.source_url);
        return _isGoogleIntermediary(u) ? "" : u;
    })();
    const altUrl = (() => {
        const u = clean(match.alt_link);
        return _isGoogleIntermediary(u) ? "" : u;
    })();
    const vStatus = match.verification_status;
    const isBadPrimary =
        vStatus === "login_required" ||
        vStatus === "rate_limited" ||
        vStatus === "aggregator_untrusted" ||
        vStatus === "google_intermediary";

    if (applyUrl && !isBadPrimary) return applyUrl;
    if (sourceUrl && !isBadPrimary) return sourceUrl;
    if (vStatus === "google_intermediary" && altUrl) return altUrl;
    if (isBadPrimary && (altUrl || sourceUrl)) return altUrl || sourceUrl;
    return "";
}

// The exact stored rows from the 2026-06-22 07:13 smoke run.
const SMOKE_ROWS: JobMatch[] = [
    { title: "Environmental Manager", company: "Compass", apply_url: "https://ae.trabajo.org/job-1", alt_link: "", verification_status: "rate_limited" },
    { title: "Environmental Manager", company: "Global Corp", apply_url: "https://gulftalent.com/uae", alt_link: "", verification_status: "login_required" },
    { title: "EHS Manager", company: "Global Corp", apply_url: "https://gulftalent.com/uae", alt_link: "", verification_status: "login_required" },
    { title: "Senior Project Manager", company: "Fugro", apply_url: "https://ae.trabajo.org/job-2", alt_link: "", verification_status: "rate_limited" },
    { title: "Environmental Manager", company: "Careers at UAE", apply_url: "https://ae.jobrapido.com/x", alt_link: "", verification_status: "aggregator_untrusted" },
];

describe("job-card fallback — never a dead-end", () => {
    it("every degraded smoke-run row resolves to an unavailable primary link", () => {
        for (const row of SMOKE_ROWS) {
            expect(resolveLinkHref(row)).toBe("");
        }
    });

    it("every degraded smoke-run row still offers actionable fallbacks", () => {
        for (const row of SMOKE_ROWS) {
            const actions = getJobFallbackActions({ title: row.title, company: row.company });
            expect(actions.length).toBeGreaterThan(0);
            const keys = actions.map((a) => a.key);
            expect(keys).toEqual(
                expect.arrayContaining(["company_site", "linkedin", "google", "copy", "save"]),
            );
        }
    });

    it("never surfaces the bad provider URL in any fallback link", () => {
        for (const row of SMOKE_ROWS) {
            const actions = getJobFallbackActions({ title: row.title, company: row.company });
            for (const a of actions) {
                if (a.kind === "link") {
                    expect(a.href).not.toContain(new URL(row.apply_url!).hostname);
                }
            }
        }
    });
});

describe("job-card fallback — action availability", () => {
    it("offers all fallbacks when title and company are present", () => {
        const keys = getJobFallbackActions({ title: "HSE Manager", company: "Acme" }).map((a) => a.key);
        expect(keys).toEqual(["company_site", "linkedin", "google", "copy", "save"]);
    });

    it("always offers Save to applications even with no title or company", () => {
        const actions = getJobFallbackActions({});
        expect(actions.length).toBeGreaterThan(0);
        expect(actions.some((a) => a.key === "save")).toBe(true);
    });

    it("offers search fallbacks when only a title is present", () => {
        const keys = getJobFallbackActions({ title: "Data Analyst" }).map((a) => a.key);
        expect(keys).toContain("company_site");
        expect(keys).toContain("save");
    });
});

describe("job-card fallback — URL builders are safe searches", () => {
    it("company-site search targets Google with company + careers + title", () => {
        const url = buildCompanySiteSearchUrl("HSE Manager", "Acme");
        expect(url).toContain("https://www.google.com/search?q=");
        expect(decodeURIComponent(url)).toContain("Acme careers HSE Manager");
    });

    it("LinkedIn search targets the LinkedIn jobs search page", () => {
        const url = buildLinkedInSearchUrl("HSE Manager", "Acme");
        expect(url).toContain("https://www.linkedin.com/jobs/search/?keywords=");
        expect(decodeURIComponent(url)).toContain("HSE Manager Acme");
    });

    it("Google search includes role, company and 'jobs'", () => {
        const url = buildGoogleSearchUrl("HSE Manager", "Acme");
        expect(decodeURIComponent(url)).toContain("HSE Manager Acme jobs");
    });

    it("copy text joins title and company", () => {
        expect(buildCopyText("HSE Manager", "Acme")).toBe("HSE Manager — Acme");
    });
});
