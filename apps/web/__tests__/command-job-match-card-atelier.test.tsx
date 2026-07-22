/**
 * Atelier MATCH card (JobMatchCardAtelier) — re-applied on the merged Atelier
 * `/command` surface (#1060; DEC-20260716-001 retires the "Obsidian" naming).
 *
 * The authenticated `/command` surface renders the job-match card in the
 * canonical MATCH structure. This suite pins the contract that makes the
 * restyle safe:
 *
 *   1. The MATCH structure renders (display title, RICO PICKS pill on a strong
 *      score, ScorePip `FIT · n%`, accent "WHY IT FITS YOU" → bullets, italic
 *      "HONEST GAPS").
 *   2. The FIT % surfaces (real score only — no fabricated numeral).
 *   3. Every real affordance is preserved and wired: the apply link keeps its
 *      href + test id; SAVE / SKIP route through `onAction` (→ sendMessage →
 *      agent_runtime) with the exact prompts.
 *   4. No fabrication: the HONEST GAPS block is omitted when the match has no
 *      concerns, and the ScorePip / RICO PICKS are absent when no score ran.
 *
 * (Ported verbatim in behaviour from the pre-Atelier command-job-cards-obsidian
 * suite; the target file name command-job-cards-atelier.test.tsx is already used
 * by the unrelated Slice 4d AtelierCardScope suite, so this suite keeps a
 * distinct name.)
 */

import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders as render } from "./test-utils";

import { JobMatchCardAtelier } from "@/components/command/JobMatchCardAtelier";
import { WORKSPACE_THEME, WorkspaceThemeContext, type WorkspacePalette } from "@/components/workspace/theme";
import type { JobMatch } from "@/lib/api";

function renderCard(match: JobMatch, onAction = vi.fn()) {
    return renderCardTheme(match, WORKSPACE_THEME.dark, onAction);
}

function renderCardTheme(
    match: JobMatch,
    palette: WorkspacePalette = WORKSPACE_THEME.dark,
    onAction = vi.fn(),
) {
    render(
        <WorkspaceThemeContext.Provider value={palette}>
            <JobMatchCardAtelier match={match} onAction={onAction} />
        </WorkspaceThemeContext.Provider>,
    );
    return onAction;
}

/** No clean/trusted link → the card shows the safe fallback actions. */
const NO_LINK_MATCH: JobMatch = {
    title: "Ops Lead",
    company: "Globex",
    score: 0.65,
    verification_status: "lead_needs_verification",
};

const STRONG_MATCH: JobMatch = {
    title: "HSE Manager — Upstream Operations",
    company: "ADNOC Onshore",
    location: "Abu Dhabi · Ruwais",
    salary: "AED 32–38k / mo",
    score: 0.92,
    apply_url: "https://careers.adnoc.ae/jobs/hse-manager",
    verification_status: "live_verified",
    match_reasons: [
        "9 yrs upstream oil & gas — matches their required 7+",
        "ISO 45001 lead auditor is listed as a strong plus",
    ],
    match_concerns: ["No offshore rotation on your CV — role is 5/2 onshore, so fine"],
};

describe("JobMatchCardAtelier MATCH structure", () => {
    it("renders the MATCH structure with title, RICO PICKS, meta, WHY and GAPS", () => {
        renderCard(STRONG_MATCH);

        expect(screen.getByTestId("opportunity-card")).toBeTruthy();
        expect(screen.getByTestId("opportunity-card-title").textContent).toBe(
            "HSE Manager — Upstream Operations",
        );
        // RICO PICKS pill on a strong (≥0.8) score
        expect(screen.getByTestId("job-rico-picks").textContent).toContain("RICO PICKS");
        // mono meta line carries real fields
        expect(screen.getByText("ADNOC Onshore")).toBeTruthy();
        expect(screen.getByText("Abu Dhabi · Ruwais")).toBeTruthy();
        expect(screen.getByText("AED 32–38k / mo")).toBeTruthy();
        // WHY IT FITS YOU — every real reason as a bullet
        expect(screen.getByText("WHY IT FITS YOU")).toBeTruthy();
        expect(
            screen.getByText("9 yrs upstream oil & gas — matches their required 7+"),
        ).toBeTruthy();
        expect(
            screen.getByText("ISO 45001 lead auditor is listed as a strong plus"),
        ).toBeTruthy();
        // HONEST GAPS — the real concern
        expect(screen.getByText("HONEST GAPS")).toBeTruthy();
        expect(
            screen.getByText("No offshore rotation on your CV — role is 5/2 onshore, so fine"),
        ).toBeTruthy();
    });

    it("shows the ScorePip as FIT · n% from the real score", () => {
        renderCard(STRONG_MATCH);
        const pip = screen.getByTestId("job-score");
        expect(pip.textContent).toBe("FIT · 92%");
        expect(pip.getAttribute("data-score-tier")).toBe("strong");
    });

    it("keeps the verified apply link with its href and test id", () => {
        renderCard(STRONG_MATCH);
        const apply = screen.getByTestId("job-link-apply") as HTMLAnchorElement;
        expect(apply.getAttribute("href")).toBe("https://careers.adnoc.ae/jobs/hse-manager");
    });

    it("renders NO save/skip buttons (phase 5 of #1262 — spoken instead)", () => {
        // The results message speaks the equivalent ("save the first job" /
        // "skip the second one"); the backend routes those deterministically.
        renderCard(STRONG_MATCH);
        expect(screen.queryByTestId("job-action-save")).toBeNull();
        expect(screen.queryByTestId("job-action-skip")).toBeNull();
    });

    it("mid-tier score (0.6–0.79) renders a ScorePip but NO RICO PICKS pill", () => {
        renderCard({ ...STRONG_MATCH, score: 0.72, match_concerns: undefined });
        const pip = screen.getByTestId("job-score");
        expect(pip.textContent).toBe("FIT · 72%");
        expect(pip.getAttribute("data-score-tier")).toBe("mid");
        expect(screen.queryByTestId("job-rico-picks")).toBeNull();
    });

    it("omits the HONEST GAPS block entirely when there are no concerns (no fabrication)", () => {
        renderCard({ ...STRONG_MATCH, match_concerns: undefined });
        expect(screen.queryByTestId("job-honest-gaps")).toBeNull();
        expect(screen.queryByText("HONEST GAPS")).toBeNull();
    });

    it("hides the ScorePip and RICO PICKS when no scorer ran (score null)", () => {
        renderCard({ ...STRONG_MATCH, score: null });
        expect(screen.queryByTestId("job-score")).toBeNull();
        expect(screen.queryByTestId("job-rico-picks")).toBeNull();
    });

    it("falls back to the single `why` string when match_reasons is absent", () => {
        renderCard({
            ...STRONG_MATCH,
            match_reasons: undefined,
            why: "Strong overlap with your logistics background.",
        });
        expect(screen.getByText("WHY IT FITS YOU")).toBeTruthy();
        expect(
            screen.getByText("Strong overlap with your logistics background."),
        ).toBeTruthy();
    });

    it("shows the safe fallback actions (never a dead-end) when there is no clean link", () => {
        renderCard(NO_LINK_MATCH);
        expect(screen.getByTestId("job-link-unavailable")).toBeTruthy();
        expect(screen.getByTestId("job-fallback-actions")).toBeTruthy();
    });
});

/**
 * GAP 1 — the authenticated Atelier card must carry the Atelier **sun-red**
 * accent from the workspace palette (`c.red`), NOT the retired `gold` token, on
 * the subcomponents the reviewer flagged: the Verified badge, the fallback
 * focus ring, and the fallback Save action. Verified in BOTH the shared
 * workspace light (#C6492E) and dark (#E0895A) palettes.
 *
 * jsdom serializes standard colour props to `rgb()/rgba()` and stores custom
 * properties (`--tw-ring-color`) verbatim — so the ring assertion pins the
 * exact sun-red hex, and the badge/Save assertions pin the sun-red RGB channel.
 */
describe.each([
    /* Artifact palette (applied 2026-07-21): sun #CF3D17 light / #EE6A3A dark. */
    ["workspace light", WORKSPACE_THEME.light, "rgb(207, 61, 23)", "#CF3D17"],
    ["workspace dark", WORKSPACE_THEME.dark, "rgb(238, 106, 58)", "#EE6A3A"],
] as const)("JobMatchCardAtelier accent = Atelier sun-red — %s", (_label, palette, rgb, hex) => {
    // "rgb(207, 61, 23)" → "rgba(207, 61, 23," — the alpha-agnostic channel prefix.
    const channel = rgb.replace("rgb(", "rgba(").replace(")", ",");

    it("renders the Verified badge in sun-red (border + text), not gold", () => {
        renderCardTheme(STRONG_MATCH, palette);
        const badge = screen.getByTestId("job-badge-verified");
        expect(badge.className).not.toMatch(/gold/);
        expect(badge.style.color).toBe(rgb);
        expect(badge.style.border).toContain(channel);
    });

    it("renders the fallback Save action in sun-red (border/background/text), not gold", () => {
        renderCardTheme(NO_LINK_MATCH, palette);
        const save = screen.getByTestId("job-fallback-save");
        expect(save.className).not.toMatch(/gold/);
        expect(save.style.color).toBe(rgb);
        expect(save.style.border).toContain(channel);
        expect(save.style.background).toContain(channel);
    });

    it("drives the fallback focus ring from the sun-red hex, not the gold token", () => {
        renderCardTheme(NO_LINK_MATCH, palette);
        // The Save button and every fallback link/copy chip carry the sun-red ring.
        const save = screen.getByTestId("job-fallback-save");
        expect(save.style.getPropertyValue("--tw-ring-color")).toBe(`${hex}80`);
        const link = screen.getByTestId("job-fallback-google");
        expect(link.className).not.toMatch(/ring-gold/);
        expect(link.style.getPropertyValue("--tw-ring-color")).toBe(`${hex}80`);
    });
});

/**
 * GAP 2 — Arabic screen-reader parity. Visible labels were already translated,
 * but the aria-labels / accessible strings (including the fallback links'
 * "{title} at {company}" join) were hardcoded English. This suite renders the
 * card in Arabic and asserts the aria-labels are localized (Arabic "لدى" join,
 * no hardcoded " at ") and that the document direction is RTL.
 */
describe("JobMatchCardAtelier — Arabic / RTL accessibility (GAP 2)", () => {
    beforeEach(() => {
        // LanguageProvider reads this on mount and switches the tree to Arabic.
        localStorage.setItem("rico-language", "ar");
    });
    afterEach(() => {
        localStorage.removeItem("rico-language");
    });

    it("localizes the card + apply-link aria-labels and sets dir=rtl", async () => {
        renderCardTheme(STRONG_MATCH);
        // Wait for the Arabic switch (the card aria-label re-renders localized;
        // the old SAVE-label marker is gone — phase 5 of #1262), then RTL.
        await waitFor(() =>
            expect(
                screen.getByTestId("opportunity-card").getAttribute("aria-label") ?? "",
            ).toContain("وظيفة مطابقة:"),
        );
        await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));

        const cardAria = screen.getByTestId("opportunity-card").getAttribute("aria-label") ?? "";
        expect(cardAria).toContain("وظيفة مطابقة:"); // "Job match:"
        expect(cardAria).toContain("لدى"); // Arabic "at" join
        expect(cardAria).not.toContain(" at "); // no hardcoded English join

        const applyAria = screen.getByTestId("job-link-apply").getAttribute("aria-label") ?? "";
        expect(applyAria).toContain("تقدّم"); // Arabic "Apply" label
        expect(applyAria).toContain("لدى");
        expect(applyAria).not.toContain(" at ");
    });

    it("localizes the fallback link aria-labels (no hardcoded 'at' construction)", async () => {
        renderCardTheme(NO_LINK_MATCH);
        // Arabic-switch gate: the fallback Google chip's localized label.
        await screen.findByText("ابحث في Google");

        const googleAria = screen.getByTestId("job-fallback-google").getAttribute("aria-label") ?? "";
        expect(googleAria).toContain("ابحث في Google"); // Arabic label
        expect(googleAria).toContain("لدى"); // Arabic "at" join
        expect(googleAria).not.toContain(" at ");
    });
});
