import { screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "./test-utils";

/**
 * PR-V4-2a (+ folded 2b) — WorkspaceShell rail goal-mini + applications nav
 * count (TASK-20260719-008, DEC-20260719-002).
 *
 * Pins: fail-hidden contract (loading/error/disabled render NOTHING — shell
 * chrome identical to pre-PR); single cached fetch shared by goal-mini and
 * the count chip (the PR-V4-2b fold-in evidence); app-variant (/command) and
 * /dashboard never fetch; bilingual title; count chip hidden at zero.
 */

const { getMissionMock } = vi.hoisted(() => ({ getMissionMock: vi.fn() }));

vi.mock("@/lib/api", () => ({ getMission: getMissionMock }));

const { pathnameRef } = vi.hoisted(() => ({ pathnameRef: { current: "/profile" } }));

vi.mock("next/navigation", () => ({
    usePathname: () => pathnameRef.current,
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { _resetMissionSummaryCache } from "@/hooks/useMissionSummary";
import type { MissionState } from "@/lib/api";

const MISSION: MissionState = {
    goal: "Find Senior HSE Manager role in Dubai",
    target_roles: ["Senior HSE Manager"],
    target_locations: ["Dubai"],
    cv_status: "uploaded",
    jobs_saved: 4,
    applications_sent: 2,
    progress_score: 75,
    missing_factors: ["pipeline_active"],
    next_recommendation: "",
    blocking_reason: null,
};

beforeEach(() => {
    getMissionMock.mockReset();
    _resetMissionSummaryCache();
    window.localStorage.clear();
    pathnameRef.current = "/profile";
});

describe("WorkspaceShell rail goal-mini", () => {
    it("renders the derived goal title, progress, and /dashboard link once mission loads", async () => {
        getMissionMock.mockResolvedValue(MISSION);
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        const card = await screen.findByTestId("rail-goal-mini");
        expect(card).toHaveAttribute("href", "/dashboard");
        expect(screen.getByTestId("rail-goal-mini-title")).toHaveTextContent(
            "Find a Senior HSE Manager role in Dubai",
        );
        expect(card).toHaveTextContent("75%");
    });

    it("fail-hidden: a failed mission fetch renders no card and leaves the nav intact", async () => {
        getMissionMock.mockRejectedValue(new Error("401"));
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        await waitFor(() => expect(getMissionMock).toHaveBeenCalledTimes(1));
        expect(screen.queryByTestId("rail-goal-mini")).toBeNull();
        expect(screen.queryByTestId("nav-applications-count")).toBeNull();
        // All six nav destinations still render (desktop sidebar).
        for (const href of ["/command", "/profile", "/applications", "/upload", "/subscription", "/settings"]) {
            expect(screen.getAllByRole("link").some((a) => a.getAttribute("href") === href)).toBe(true);
        }
    });

    it("never fetches on /dashboard (goal panel already shows the data there)", async () => {
        pathnameRef.current = "/dashboard";
        getMissionMock.mockResolvedValue(MISSION);
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        await waitFor(() => expect(screen.queryByTestId("rail-goal-mini")).toBeNull());
        expect(getMissionMock).not.toHaveBeenCalled();
    });

    it("never fetches in the app variant (/command surface stays untouched)", async () => {
        pathnameRef.current = "/command";
        getMissionMock.mockResolvedValue(MISSION);
        renderWithProviders(<WorkspaceShell variant="app"><div /></WorkspaceShell>);

        await waitFor(() => expect(screen.queryByTestId("rail-goal-mini")).toBeNull());
        expect(getMissionMock).not.toHaveBeenCalled();
    });

    it("shares ONE cached fetch across consecutive shell mounts (2b fold-in evidence)", async () => {
        getMissionMock.mockResolvedValue(MISSION);
        const first = renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);
        await screen.findByTestId("rail-goal-mini");
        first.unmount();

        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);
        await screen.findByTestId("rail-goal-mini");
        expect(getMissionMock).toHaveBeenCalledTimes(1);
    });

    it("renders the Arabic title in Arabic mode", async () => {
        window.localStorage.setItem("rico-language", "ar");
        getMissionMock.mockResolvedValue(MISSION);
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        expect(await screen.findByTestId("rail-goal-mini-title")).toHaveTextContent(
            "إيجاد دور Senior HSE Manager في Dubai",
        );
    });
});

describe("WorkspaceShell applications nav count (folded PR-V4-2b)", () => {
    it("shows the applications count from the SAME mission fetch when > 0", async () => {
        getMissionMock.mockResolvedValue(MISSION);
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        const chip = await screen.findByTestId("nav-applications-count");
        expect(chip).toHaveTextContent("2");
        expect(getMissionMock).toHaveBeenCalledTimes(1);
    });

    it("renders no chip when the count is zero", async () => {
        getMissionMock.mockResolvedValue({ ...MISSION, applications_sent: 0 });
        renderWithProviders(<WorkspaceShell><div /></WorkspaceShell>);

        await screen.findByTestId("rail-goal-mini");
        expect(screen.queryByTestId("nav-applications-count")).toBeNull();
    });
});
