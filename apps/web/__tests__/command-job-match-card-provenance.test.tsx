/**
 * Atelier MATCH card — source-provenance line (backend search dedup).
 *
 * The backend collapses duplicate postings and annotates the survivor with
 * `sources` (provider labels) and `duplicate_count`. This suite pins the card's
 * contract for surfacing that provenance truthfully:
 *
 *   1. A single source renders "via {source}".
 *   2. Multiple deduped sources render "via {first} · on {count} sources".
 *   3. No source label → the provenance line is omitted entirely (never
 *      fabricated), matching the no-fabrication rule used elsewhere on the card.
 *   4. The line carries an accessible aria-label listing all sources.
 */
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders as render } from "./test-utils";

import { JobMatchCardAtelier } from "@/components/command/JobMatchCardAtelier";
import { WORKSPACE_THEME, WorkspaceThemeContext } from "@/components/workspace/theme";
import type { JobMatch } from "@/lib/api";

function renderCard(match: JobMatch) {
    render(
        <WorkspaceThemeContext.Provider value={WORKSPACE_THEME.dark}>
            <JobMatchCardAtelier match={match} onAction={vi.fn()} />
        </WorkspaceThemeContext.Provider>,
    );
}

const BASE: JobMatch = {
    title: "Data Engineer",
    company: "Acme",
    location: "Dubai",
    score: 0.72,
    verification_status: "live_verified",
};

describe("JobMatchCardAtelier source provenance", () => {
    it("shows a single source as 'via {source}'", () => {
        renderCard({ ...BASE, sources: ["LinkedIn"] });
        const el = screen.getByTestId("job-provenance");
        expect(el.textContent).toContain("LinkedIn");
        expect(el.textContent).not.toContain("sources");
    });

    it("shows the count when a posting was deduped across multiple sources", () => {
        renderCard({ ...BASE, sources: ["LinkedIn", "Bayt"], duplicate_count: 3 });
        const el = screen.getByTestId("job-provenance");
        expect(el.textContent).toContain("LinkedIn");
        expect(el.textContent).toContain("3");
        // aria-label lists every source for screen readers.
        expect(el.getAttribute("aria-label")).toContain("Bayt");
    });

    it("omits the provenance line entirely when no source is present", () => {
        renderCard(BASE);
        expect(screen.queryByTestId("job-provenance")).toBeNull();
    });

    it("ignores blank source entries rather than rendering an empty 'via'", () => {
        renderCard({ ...BASE, sources: ["", "  "] });
        expect(screen.queryByTestId("job-provenance")).toBeNull();
    });
});
