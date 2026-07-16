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

import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders as render } from "./test-utils";

import { JobMatchCardAtelier } from "@/components/command/JobMatchCardAtelier";
import { COMMAND_ATELIER } from "@/components/command/commandAtelierTheme";
import { WorkspaceThemeContext } from "@/components/workspace/theme";
import type { JobMatch } from "@/lib/api";

function renderCard(match: JobMatch, onAction = vi.fn()) {
    render(
        <WorkspaceThemeContext.Provider value={COMMAND_ATELIER.dark}>
            <JobMatchCardAtelier match={match} onAction={onAction} />
        </WorkspaceThemeContext.Provider>,
    );
    return onAction;
}

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

    it("routes SAVE and SKIP through onAction with the exact prompts", () => {
        const onAction = renderCard(STRONG_MATCH);

        fireEvent.click(screen.getByTestId("job-action-save"));
        expect(onAction).toHaveBeenCalledWith(
            "Save HSE Manager — Upstream Operations at ADNOC Onshore to my pipeline",
        );

        fireEvent.click(screen.getByTestId("job-action-skip"));
        expect(onAction).toHaveBeenCalledWith(
            "Skip HSE Manager — Upstream Operations at ADNOC Onshore",
        );
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
        renderCard({
            title: "Ops Lead",
            company: "Globex",
            score: 0.65,
            verification_status: "lead_needs_verification",
        });
        expect(screen.getByTestId("job-link-unavailable")).toBeTruthy();
        expect(screen.getByTestId("job-fallback-actions")).toBeTruthy();
    });
});
