/**
 * Regression tests for BUG-6: status taxonomy mismatch between the /flow
 * list view and the Kanban board (and the chat pipeline summary).
 *
 * Root cause: each surface (list view badges, board columns, the chat
 * pipeline summary card, and StatusBadge's internal default labels) defined
 * its own copy of the status list / status->stage grouping, and these could
 * silently drift apart (e.g. the chat summary only recognized 5 of the 10
 * backend statuses; the board column groupings lived in a separate literal
 * from the list-view label table).
 *
 * Fix: apps/web/lib/applicationStatus.ts is now the single source of truth
 * for (a) the full list of statuses and (b) which stage/Kanban column each
 * status belongs to. Every consumer derives from it instead of redefining
 * its own list.
 */
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LanguageProvider } from "@/contexts/LanguageContext";
import {
    APPLICATION_STATUSES,
    STAGE_DEFS,
    STATUS_DEFAULT_LABEL,
    getStageForStatus,
    type StageKey,
} from "@/lib/applicationStatus";
import type { ApplicationStatus } from "@/types";
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

describe("BUG-6: canonical status taxonomy", () => {
    it("every status belongs to exactly one stage", () => {
        const seen = new Set<ApplicationStatus>();
        for (const stage of STAGE_DEFS) {
            for (const status of stage.statuses) {
                expect(seen.has(status)).toBe(false);
                seen.add(status);
            }
        }
        expect(seen.size).toBe(APPLICATION_STATUSES.length);
        for (const status of APPLICATION_STATUSES) {
            expect(seen.has(status)).toBe(true);
        }
    });

    it("getStageForStatus resolves a stage for every canonical status", () => {
        for (const status of APPLICATION_STATUSES) {
            expect(getStageForStatus(status)).toBeDefined();
        }
    });

    it("has a default label for every canonical status", () => {
        for (const status of APPLICATION_STATUSES) {
            expect(STATUS_DEFAULT_LABEL[status]).toBeTruthy();
        }
    });

    it("a 'saved' item's stage is the lead stage (not 'applied')", () => {
        expect(getStageForStatus("saved")).toBe("lead");
        expect(getStageForStatus("applied")).toBe("applied");
    });
});

function renderBadge(status: ApplicationStatus) {
    return render(
        <LanguageProvider>
            <StatusBadge status={status} />
        </LanguageProvider>,
    );
}

describe("BUG-6: StatusBadge default labels match the canonical taxonomy", () => {
    it.each(APPLICATION_STATUSES)("renders the canonical default label for status=%s", (status) => {
        renderBadge(status);
        expect(screen.getByText(STATUS_DEFAULT_LABEL[status])).toBeInTheDocument();
    });
});

// ── Cross-view consistency: /flow list view vs. board view ──
//
// The acceptance criterion is "no item appears as Applied in list but Lead
// in board" — i.e. the same application record must classify into the same
// stage no matter which view renders it. These tests render the real
// FlowPage (mocking only the network layer) with one synthetic application
// per canonical status, then assert list-view labels and board-view column
// placement agree for every single one.

const { fetchApplicationsMock, getApplicationStatsMock, fetchMeMock } = vi.hoisted(() => ({
    fetchApplicationsMock: vi.fn(),
    getApplicationStatsMock: vi.fn().mockResolvedValue({}),
    fetchMeMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    usePathname: () => "/flow",
    useSearchParams: () => new URLSearchParams(),
    redirect: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/components/layout/Navigation", () => ({
    Navigation: () => <nav>Navigation</nav>,
}));

vi.mock("@/components/layout/TopNav", () => ({
    TopNav: () => <header>TopNav</header>,
}));

vi.mock("@/components/ui/AuraGlow", () => ({
    AuraGlow: () => <div />,
}));

vi.mock("@/components/ui/MaterialIcon", () => ({
    MaterialIcon: ({ icon }: { icon: string }) => <span data-icon={icon}>{icon}</span>,
}));

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        fetchMe: fetchMeMock,
        getApplications: fetchApplicationsMock,
        createManualApplication: vi.fn(),
        updateApplicationStatus: vi.fn(),
        getApplicationStats: getApplicationStatsMock,
    };
});

import FlowPage from "@/app/flow/page";

function renderFlow() {
    return render(
        <LanguageProvider>
            <FlowPage />
        </LanguageProvider>,
    );
}

const STAGE_COLUMN_LABEL: Record<StageKey, string> = {
    lead: "Leads",
    applied: "Applied",
    interview: "Interview",
    outcome: "Outcome",
};

function titleFor(status: ApplicationStatus) {
    return `Role for ${status}`;
}

describe("BUG-6: /flow list view and board view classify the same records identically", () => {
    beforeEach(() => {
        fetchApplicationsMock.mockReset();
        getApplicationStatsMock.mockReset().mockResolvedValue({});
        fetchMeMock.mockReset().mockResolvedValue({ authenticated: true, guest: false, email: "test@example.com", role: "user" });
    });

    it("every status's list-view badge and board-view column agree on its stage, for all 10 statuses", async () => {
        const applications = APPLICATION_STATUSES.map((status, idx) => ({
            application_id: `app-${idx}`,
            job_id: `job-${idx}`,
            title: titleFor(status),
            company: "Acme",
            location: "Dubai",
            status,
        }));
        fetchApplicationsMock.mockResolvedValue({ applications, total: applications.length });

        const user = userEvent.setup();
        renderFlow();

        // List view (default): every item must render its own exact status
        // label in its badge. Each card's status <select> also contains an
        // <option> with the same text for every status, so we can't just
        // grep the page for the label — scope the lookup to the badge slot
        // that sits next to this item's title (sibling of the title block,
        // not the <select>).
        for (const status of APPLICATION_STATUSES) {
            const titleEl = await screen.findByText(titleFor(status));
            const headerRow = titleEl.parentElement!.parentElement as HTMLElement;
            const badgeContainer = headerRow.children[1] as HTMLElement;
            expect(within(badgeContainer).getByText(STATUS_DEFAULT_LABEL[status])).toBeInTheDocument();
        }

        // Switch to board view.
        await user.click(screen.getByRole("button", { name: /Board/i }));

        // Each status's card must land in exactly the board column that
        // matches its canonical stage (lib/applicationStatus.ts), and must
        // NOT appear in any other column — directly encodes "no item shows
        // Applied in list but Lead in board." Column headers are <h3>
        // elements (an accessible heading), which lets us find them
        // unambiguously even though the same label text also appears inside
        // every card's status <select> options.
        for (const status of APPLICATION_STATUSES) {
            const expectedStage = getStageForStatus(status)!;
            for (const stage of STAGE_DEFS) {
                const columnHeading = screen.getByRole("heading", { name: STAGE_COLUMN_LABEL[stage.key] });
                const columnRoot = columnHeading.closest("div")?.parentElement as HTMLElement;
                const cardInColumn = within(columnRoot).queryByText(titleFor(status));
                if (stage.key === expectedStage) {
                    expect(cardInColumn).toBeInTheDocument();
                } else {
                    expect(cardInColumn).not.toBeInTheDocument();
                }
            }
        }
    });

    it("board column counts sum to the total application count, and each matches its stage's item count (no item lost or duplicated)", async () => {
        // Two items per status (20 total) so column counts are non-trivial
        // (not just "1 per column").
        const applications = APPLICATION_STATUSES.flatMap((status, idx) => [
            { application_id: `app-${idx}-a`, job_id: `job-${idx}-a`, title: `${titleFor(status)} A`, company: "Acme", location: "Dubai", status },
            { application_id: `app-${idx}-b`, job_id: `job-${idx}-b`, title: `${titleFor(status)} B`, company: "Acme", location: "Dubai", status },
        ]);
        fetchApplicationsMock.mockResolvedValue({ applications, total: applications.length });

        const user = userEvent.setup();
        renderFlow();
        await screen.findByText(`${titleFor(APPLICATION_STATUSES[0])} A`);

        await user.click(screen.getByRole("button", { name: /Board/i }));

        let totalAcrossColumns = 0;
        for (const stage of STAGE_DEFS) {
            const columnHeading = screen.getByRole("heading", { name: STAGE_COLUMN_LABEL[stage.key] });
            const headerRow = columnHeading.parentElement as HTMLElement;
            const countText = within(headerRow).getByText(/^\d+$/).textContent;
            const renderedCount = Number(countText);
            const expectedCount = stage.statuses.length * 2; // 2 synthetic items per status
            expect(renderedCount).toBe(expectedCount);
            totalAcrossColumns += renderedCount;
        }
        expect(totalAcrossColumns).toBe(applications.length);
    });
});
