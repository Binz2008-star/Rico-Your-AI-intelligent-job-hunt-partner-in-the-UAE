/**
 * #1249 step 3 — ScheduledSearchCard component tests.
 *
 * Pins the card's contract: criteria line (city / min AED salary / cadence),
 * enabled vs paused state, honest salary rendering (unknown salary is
 * labeled, never invented), real source links on every result, one-click
 * pause/resume via the PATCH helper, and the destructive-delete inline
 * confirm step (no delete call before confirmation).
 */
import { ScheduledSearchCard } from "@/components/ScheduledSearchCard";
import type { ScheduledSearch } from "@/lib/api";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setEnabledMock = vi.fn(async () => undefined);
const deleteMock = vi.fn(async () => undefined);

vi.mock("@/lib/api", () => ({
    setScheduledSearchEnabled: (...args: unknown[]) => setEnabledMock(...args),
    deleteSavedSearch: (...args: unknown[]) => deleteMock(...args),
}));

function makeItem(overrides: Partial<ScheduledSearch["schedule"]> = {}): ScheduledSearch {
    return {
        id: "sched-1",
        query: "Scheduled daily job search — Dubai — 10000+ AED",
        schedule: {
            enabled: true,
            cadence: "daily",
            city: "Dubai",
            min_salary_aed: 10000,
            last_run_at: "2026-07-20T05:00:00+00:00",
            last_run_new: 2,
            last_results: [
                {
                    title: "HSE Manager",
                    company: "ACME Gulf",
                    location: "Dubai, AE",
                    score: 90,
                    link: "https://jobs.example.com/1",
                    salary_known: true,
                    salary_aed: 12000,
                    why: "Strong HSE match",
                },
                {
                    title: "Safety Lead",
                    company: "Falcon Industrial",
                    location: "Dubai, AE",
                    score: 82,
                    link: "https://jobs.example.com/2",
                    salary_known: false,
                    salary_aed: null,
                    why: "",
                },
            ],
            ...overrides,
        },
    };
}

describe("#1249: ScheduledSearchCard", () => {
    beforeEach(() => {
        setEnabledMock.mockClear();
        deleteMock.mockClear();
        localStorage.removeItem("rico-language");
    });

    it("renders criteria, active state, and run metadata", () => {
        render(<ScheduledSearchCard item={makeItem()} onChanged={() => {}} />);
        expect(screen.getByTestId("scheduled-search-criteria")).toHaveTextContent("Dubai");
        expect(screen.getByTestId("scheduled-search-criteria")).toHaveTextContent("AED 10,000+");
        expect(screen.getByTestId("scheduled-search-criteria")).toHaveTextContent("Daily");
        expect(screen.getByTestId("scheduled-search-state")).toHaveTextContent("Active");
    });

    it("labels unknown salary honestly and never invents a figure", () => {
        render(<ScheduledSearchCard item={makeItem()} onChanged={() => {}} />);
        const salaries = screen.getAllByTestId("scheduled-search-salary");
        expect(salaries[0]).toHaveTextContent("AED 12,000");
        expect(salaries[1]).toHaveTextContent("Salary not stated");
    });

    it("every result links to its real source URL", () => {
        render(<ScheduledSearchCard item={makeItem()} onChanged={() => {}} />);
        const links = screen.getAllByRole("link", { name: "View job" });
        expect(links.map((a) => a.getAttribute("href"))).toEqual([
            "https://jobs.example.com/1",
            "https://jobs.example.com/2",
        ]);
    });

    it("pause calls the PATCH helper with enabled=false and refreshes", async () => {
        const onChanged = vi.fn();
        render(<ScheduledSearchCard item={makeItem()} onChanged={onChanged} />);
        await userEvent.click(screen.getByTestId("scheduled-search-toggle"));
        expect(setEnabledMock).toHaveBeenCalledWith("sched-1", false);
        expect(onChanged).toHaveBeenCalled();
    });

    it("paused card offers Resume and calls enabled=true", async () => {
        render(
            <ScheduledSearchCard item={makeItem({ enabled: false })} onChanged={() => {}} />,
        );
        expect(screen.getByTestId("scheduled-search-state")).toHaveTextContent("Paused");
        await userEvent.click(screen.getByRole("button", { name: "Resume" }));
        expect(setEnabledMock).toHaveBeenCalledWith("sched-1", true);
    });

    it("delete is two-step: no API call before the inline confirm", async () => {
        const onChanged = vi.fn();
        render(<ScheduledSearchCard item={makeItem()} onChanged={onChanged} />);
        await userEvent.click(screen.getByTestId("scheduled-search-delete"));
        expect(deleteMock).not.toHaveBeenCalled(); // destructive → must confirm
        expect(screen.getByTestId("scheduled-search-confirm")).toBeInTheDocument();
        await userEvent.click(screen.getByTestId("scheduled-search-confirm-delete"));
        expect(deleteMock).toHaveBeenCalledWith("sched-1");
        expect(onChanged).toHaveBeenCalled();
    });

    it("cancel aborts the delete without any API call", async () => {
        render(<ScheduledSearchCard item={makeItem()} onChanged={() => {}} />);
        await userEvent.click(screen.getByTestId("scheduled-search-delete"));
        await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
        expect(deleteMock).not.toHaveBeenCalled();
        expect(screen.queryByTestId("scheduled-search-confirm")).not.toBeInTheDocument();
    });

    it("renders Arabic copy when rico-language=ar", () => {
        localStorage.setItem("rico-language", "ar");
        render(<ScheduledSearchCard item={makeItem()} onChanged={() => {}} />);
        expect(screen.getByTestId("scheduled-search-state")).toHaveTextContent("مفعّل");
        const salaries = screen.getAllByTestId("scheduled-search-salary");
        expect(salaries[1]).toHaveTextContent("الراتب غير معلن");
    });

    it("empty results show the no-results message, not a broken list", () => {
        render(
            <ScheduledSearchCard item={makeItem({ last_results: [], last_run_new: 0 })} onChanged={() => {}} />,
        );
        expect(screen.getByTestId("scheduled-search-empty")).toBeInTheDocument();
        expect(screen.queryByTestId("scheduled-search-result")).not.toBeInTheDocument();
    });
});
