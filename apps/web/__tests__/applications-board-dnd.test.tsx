/**
 * Focused tests for the /applications board drag-and-drop interaction.
 *
 * Scope: verify dnd-kit wiring, the canonical column-to-status mapping,
 * and that the existing status select remains the keyboard/accessibility fallback.
 */
import { LanguageProvider } from "@/contexts/LanguageContext";
import { APPLICATION_STATUSES } from "@/lib/applicationStatus";
import type { Application, ApplicationStatus } from "@/types";
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchApplicationsMock, getApplicationStatsMock, updateApplicationStatusMock, fetchMeMock } = vi.hoisted(() => ({
    fetchApplicationsMock: vi.fn(),
    getApplicationStatsMock: vi.fn().mockResolvedValue({}),
    updateApplicationStatusMock: vi.fn(),
    fetchMeMock: vi.fn(),
}));

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }));

vi.mock("next/navigation", () => ({
    useRouter: () => routerMock,
    usePathname: () => "/applications",
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
        updateApplicationStatus: updateApplicationStatusMock,
        getApplicationStats: getApplicationStatsMock,
    };
});

import ApplicationsPage from "@/app/applications/page";

function renderPage() {
    return render(
        <LanguageProvider>
            <ApplicationsPage />
        </LanguageProvider>,
    );
}

function appFor(status: ApplicationStatus, idx: number): Application {
    return {
        application_id: `app-${status}-${idx}`,
        job_id: `job-${status}-${idx}`,
        title: `Role ${status}`,
        company: "Acme",
        location: "Dubai",
        status,
    };
}

describe("Applications board DnD", () => {
    beforeEach(() => {
        fetchApplicationsMock.mockReset();
        getApplicationStatsMock.mockReset().mockResolvedValue({});
        updateApplicationStatusMock.mockReset().mockResolvedValue({ status: "applied" });
        fetchMeMock.mockReset().mockResolvedValue({ authenticated: true, guest: false, email: "test@example.com", role: "user" });
    });

    it("board cards render as draggable and columns render as droppable", async () => {
        const applications = [appFor("saved", 0), appFor("applied", 0), appFor("interview", 0)];
        fetchApplicationsMock.mockResolvedValue({ applications, total: applications.length });

        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Role saved");

        await user.click(screen.getByRole("button", { name: /Board/i }));

        const draggables = screen.getAllByRole("button", { name: /Drag application card/i });
        expect(draggables).toHaveLength(3);
        draggables.forEach((el) => {
            expect(el).toHaveAttribute("aria-roledescription", "draggable");
            expect(el).toHaveAttribute("tabIndex", "0");
        });

        const droppables = ["lead", "applied", "interview", "outcome"].map((key) =>
            document.querySelector(`[data-droppable-id="${key}"]`),
        );
        droppables.forEach((el) => expect(el).toBeInTheDocument());
    });

    it("uses the canonical column-to-status mapping for every stage", async () => {
        const { COLUMN_TARGET_STATUS } = await import("@/components/applications/ApplicationsAtelier");
        expect(COLUMN_TARGET_STATUS).toEqual({
            lead: "saved",
            applied: "applied",
            interview: "interview",
            outcome: "offer",
        });
    });

    it("keeps the status select as a working keyboard/accessibility fallback", async () => {
        const applications = [appFor("saved", 0), appFor("applied", 0)];
        fetchApplicationsMock.mockResolvedValue({ applications, total: applications.length });

        const user = userEvent.setup();
        renderPage();
        await screen.findByText("Role saved");

        await user.click(screen.getByRole("button", { name: /Board/i }));
        const column = document.querySelector('[data-droppable-id="lead"]') as HTMLElement;
        const select = within(column).getByRole("combobox");
        await user.selectOptions(select, "applied");

        expect(updateApplicationStatusMock).toHaveBeenCalledTimes(1);
        expect(updateApplicationStatusMock).toHaveBeenCalledWith(applications[0].job_id, { status: "applied" });
    });

    it("does not mark list-view cards as draggable", async () => {
        const applications = [appFor("saved", 0), appFor("applied", 0)];
        fetchApplicationsMock.mockResolvedValue({ applications, total: applications.length });

        renderPage();
        await screen.findByText("Role saved");

        // List view should have status selects but no draggable buttons.
        expect(screen.getAllByRole("combobox")).toHaveLength(2);
        expect(screen.queryAllByRole("button", { name: /Drag application card/i })).toHaveLength(0);
    });
});
