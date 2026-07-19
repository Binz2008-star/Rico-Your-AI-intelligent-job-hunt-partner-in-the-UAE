/**
 * /applications stage-semantic accents (Command Workspace v4 alignment).
 *
 * Pins the accent contract mapped onto PRODUCTION tokens only
 * (DEC-20260719-002 boundary 3):
 *   sun    = states needing the user (interview / offer / follow_up_due)
 *   muted  = closed outcomes (rejected / decision_made)
 *   neutral= lead + applied states
 * and that the list rows and board cards both carry it, so the two views
 * can never disagree.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const { fetchApplicationsMock, getApplicationStatsMock } = vi.hoisted(() => ({
    fetchApplicationsMock: vi.fn(),
    getApplicationStatsMock: vi.fn().mockResolvedValue({}),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    usePathname: () => "/applications",
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...actual,
        getApplications: fetchApplicationsMock,
        getApplicationStats: getApplicationStatsMock,
        updateApplicationStatus: vi.fn(),
        createManualApplication: vi.fn(),
    };
});

import { ApplicationsAtelier, STATUS_ACCENT } from "@/components/applications/ApplicationsAtelier";

const app = (id: string, status: string) => ({
    application_id: id,
    job_id: `job-${id}`,
    title: `Role ${id}`,
    company: "Synthetic Co",
    location: "Dubai",
    apply_url: "",
    status,
});

function mockApps(apps: ReturnType<typeof app>[]) {
    fetchApplicationsMock.mockResolvedValue({
        applications: apps,
        total: apps.length,
        page: 1,
        limit: 50,
        pages: 1,
    });
}

function renderPage() {
    return render(
        <LanguageProvider>
            <ApplicationsAtelier />
        </LanguageProvider>,
    );
}

beforeEach(() => {
    vi.clearAllMocks();
    getApplicationStatsMock.mockResolvedValue({});
});

describe("STATUS_ACCENT contract", () => {
    it("sun marks exactly the states that need the user", () => {
        expect(
            Object.entries(STATUS_ACCENT).filter(([, a]) => a === "sun").map(([s]) => s).sort(),
        ).toEqual(["follow_up_due", "interview", "offer"]);
    });

    it("muted marks exactly the closed outcomes", () => {
        expect(
            Object.entries(STATUS_ACCENT).filter(([, a]) => a === "muted").map(([s]) => s).sort(),
        ).toEqual(["decision_made", "rejected"]);
    });

    it("every canonical status has an accent (taxonomy can't drift silently)", async () => {
        const { APPLICATION_STATUSES } = await import("@/lib/applicationStatus");
        for (const s of APPLICATION_STATUSES) {
            expect(STATUS_ACCENT[s], `missing accent for ${s}`).toBeDefined();
        }
    });
});

describe("list rows carry the stage-tagged chip", () => {
    it("renders sun / neutral / muted chips per status", async () => {
        mockApps([app("1", "interview"), app("2", "applied"), app("3", "rejected")]);
        renderPage();
        await waitFor(() => {
            expect(screen.getAllByTestId("application-status-chip")).toHaveLength(3);
        });
        const chips = screen.getAllByTestId("application-status-chip");
        const byStatus = Object.fromEntries(chips.map((el) => [el.getAttribute("data-status"), el]));
        expect(byStatus["interview"]).toHaveAttribute("data-accent", "sun");
        expect(byStatus["applied"]).toHaveAttribute("data-accent", "neutral");
        expect(byStatus["rejected"]).toHaveAttribute("data-accent", "muted");
    });
});

describe("board cards carry the same accent", () => {
    it("accent dots match STATUS_ACCENT in board view", async () => {
        mockApps([app("1", "follow_up_due"), app("2", "saved"), app("3", "decision_made")]);
        renderPage();
        await waitFor(() => {
            expect(screen.getByRole("button", { name: /board/i })).toBeInTheDocument();
        });
        await userEvent.click(screen.getByRole("button", { name: /board/i }));
        await waitFor(() => {
            expect(screen.getAllByTestId("board-card-accent")).toHaveLength(3);
        });
        const accents = screen.getAllByTestId("board-card-accent").map((el) => el.getAttribute("data-accent")).sort();
        expect(accents).toEqual(["muted", "neutral", "sun"]);
    });
});
