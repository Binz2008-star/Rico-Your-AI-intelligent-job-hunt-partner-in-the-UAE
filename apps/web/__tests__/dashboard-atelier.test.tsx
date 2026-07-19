import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "./test-utils";

/**
 * PR-V4-1 — /dashboard Overview goal panel + suggested next actions
 * (TASK-20260719-007, DEC-20260719-002).
 *
 * Pins: real-MissionState-only rendering; localized goal title derived from
 * STRUCTURED fields (never the English-only server `goal` string); milestone
 * pills mirroring the server's missing_factors tokens; suggested-next
 * derivation (priority order, dedupe, cap 3, never empty); explicit error +
 * retry (no zeroed panels on failure); real route hrefs only; AR rendering.
 */

const { getMissionMock } = vi.hoisted(() => ({ getMissionMock: vi.fn() }));

vi.mock("@/lib/api", () => ({ getMission: getMissionMock }));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

import {
    DashboardAtelier,
    deriveGoalTitle,
    deriveNextActions,
    NEXT_ACTION_HREF,
} from "@/components/workspace/DashboardAtelier";
import type { MissionState } from "@/lib/api";

const FULL_MISSION: MissionState = {
    goal: "Find Senior HSE Manager role in Dubai",
    target_roles: ["Senior HSE Manager"],
    target_locations: ["Dubai", "Abu Dhabi"],
    cv_status: "uploaded",
    jobs_saved: 4,
    applications_sent: 2,
    progress_score: 100,
    missing_factors: [],
    next_recommendation: "You're on track — keep applying.",
    blocking_reason: null,
};

const EMPTY_MISSION: MissionState = {
    goal: "Define your job search mission",
    target_roles: [],
    target_locations: [],
    cv_status: "missing",
    jobs_saved: 0,
    applications_sent: 0,
    progress_score: 0,
    missing_factors: ["cv_uploaded", "roles_set", "locations_set", "pipeline_active"],
    next_recommendation: "Upload your CV so Rico can match you to the right jobs.",
    blocking_reason: "CV is missing — Rico can't score job matches without it.",
};

beforeEach(() => {
    getMissionMock.mockReset();
    window.localStorage.clear();
});

afterEach(() => {
    vi.clearAllMocks();
});

describe("deriveNextActions (pure)", () => {
    it("all factors missing → upload CV, set goals, search jobs (in priority order, capped at 3)", () => {
        expect(deriveNextActions(EMPTY_MISSION)).toEqual(["upload_cv", "set_goals", "search_jobs"]);
    });

    it("complete mission with applications → review applications, keep going, review profile", () => {
        expect(deriveNextActions(FULL_MISSION)).toEqual(["review_applications", "keep_going", "review_profile"]);
    });

    it("only CV missing, with applications → upload CV first, then applications, then continue", () => {
        const m: MissionState = { ...FULL_MISSION, cv_status: "missing", missing_factors: ["cv_uploaded"] };
        expect(deriveNextActions(m)).toEqual(["upload_cv", "review_applications", "keep_going"]);
    });

    it("search_jobs and keep_going share /command — deduped by destination", () => {
        const m: MissionState = { ...FULL_MISSION, applications_sent: 0, missing_factors: ["pipeline_active"] };
        const keys = deriveNextActions(m);
        expect(keys).toEqual(["search_jobs", "review_profile"]);
        const hrefs = keys.map((k) => NEXT_ACTION_HREF[k]);
        expect(new Set(hrefs).size).toBe(hrefs.length);
        expect(keys).toContain("search_jobs");
        expect(keys).not.toContain("keep_going");
    });

    it("never empty and never more than 3, even with null mission", () => {
        const keys = deriveNextActions(null);
        expect(keys.length).toBeGreaterThan(0);
        expect(keys.length).toBeLessThanOrEqual(3);
    });
});

describe("deriveGoalTitle (pure, bilingual — never the English server string)", () => {
    it("role + city (EN)", () => {
        expect(deriveGoalTitle(FULL_MISSION, "en")).toBe("Find a Senior HSE Manager role in Dubai");
    });
    it("role only (EN)", () => {
        const m = { ...FULL_MISSION, target_locations: [] };
        expect(deriveGoalTitle(m, "en")).toBe("Find a Senior HSE Manager role in the UAE");
    });
    it("city only (AR)", () => {
        const m = { ...FULL_MISSION, target_roles: [] };
        expect(deriveGoalTitle(m, "ar")).toBe("إيجاد وظيفة في Dubai");
    });
    it("empty mission falls back to the set-first-mission copy", () => {
        expect(deriveGoalTitle(EMPTY_MISSION, "en")).toBe("Set your first mission");
        expect(deriveGoalTitle(EMPTY_MISSION, "ar")).toBe("حدّد مهمّتك الأولى");
    });
});

describe("DashboardAtelier — goal panel (real data only)", () => {
    it("renders the derived goal title, progress, milestones, and edit link for a full mission", async () => {
        getMissionMock.mockResolvedValue(FULL_MISSION);
        renderWithProviders(<DashboardAtelier />);

        expect(await screen.findByTestId("dashboard-goal-title")).toHaveTextContent(
            "Find a Senior HSE Manager role in Dubai",
        );
        expect(screen.getByTestId("dashboard-goal-scope")).toHaveTextContent(
            "Senior HSE Manager · Dubai · Abu Dhabi",
        );

        const bar = screen.getByRole("progressbar");
        expect(bar).toHaveAttribute("aria-valuenow", "100");

        const pills = screen.getAllByTestId("dashboard-milestone");
        expect(pills).toHaveLength(4);
        for (const pill of pills) expect(pill).toHaveAttribute("data-done", "true");

        expect(screen.getByTestId("dashboard-goal-edit")).toHaveAttribute("href", "/profile?section=goals");
    });

    it("marks exactly the server-reported missing factors as not done", async () => {
        getMissionMock.mockResolvedValue({
            ...FULL_MISSION,
            progress_score: 50,
            missing_factors: ["locations_set", "pipeline_active"],
        });
        renderWithProviders(<DashboardAtelier />);

        const pills = await screen.findAllByTestId("dashboard-milestone");
        const doneStates = pills.map((p) => p.getAttribute("data-done"));
        expect(doneStates).toEqual(["true", "true", "false", "false"]);
        expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    });

    it("empty mission shows the fallback title and the bootstrap action set", async () => {
        getMissionMock.mockResolvedValue(EMPTY_MISSION);
        renderWithProviders(<DashboardAtelier />);

        expect(await screen.findByTestId("dashboard-goal-title")).toHaveTextContent("Set your first mission");

        const actions = screen.getAllByTestId("dashboard-next-action");
        expect(actions.map((a) => a.getAttribute("href"))).toEqual([
            "/upload",
            "/profile?section=goals",
            "/command",
        ]);
    });
});

describe("DashboardAtelier — suggested next actions", () => {
    it("caps at 3 and links only to existing routes", async () => {
        getMissionMock.mockResolvedValue(FULL_MISSION);
        renderWithProviders(<DashboardAtelier />);

        const actions = await screen.findAllByTestId("dashboard-next-action");
        expect(actions).toHaveLength(3);
        expect(actions.map((a) => a.getAttribute("href"))).toEqual([
            "/applications",
            "/command",
            "/profile",
        ]);
        // PR-V4-3 scope guard: no Ask Rico ?q= deep-links in this slice.
        for (const a of actions) expect(a.getAttribute("href")).not.toContain("?q=");
    });
});

describe("DashboardAtelier — failure honesty", () => {
    it("renders an explicit error with retry — no zeroed panels pretending to be data", async () => {
        getMissionMock.mockRejectedValueOnce(new Error("network down"));
        getMissionMock.mockResolvedValueOnce(FULL_MISSION);
        renderWithProviders(<DashboardAtelier />);

        expect(await screen.findByTestId("dashboard-error")).toBeInTheDocument();
        expect(screen.queryByTestId("dashboard-goal-title")).toBeNull();
        expect(screen.queryByTestId("dashboard-next-action")).toBeNull();

        fireEvent.click(screen.getByTestId("dashboard-retry"));
        await waitFor(() => expect(getMissionMock).toHaveBeenCalledTimes(2));
        expect(await screen.findByTestId("dashboard-goal-title")).toHaveTextContent(
            "Find a Senior HSE Manager role in Dubai",
        );
        expect(screen.queryByTestId("dashboard-error")).toBeNull();
    });
});

describe("DashboardAtelier — Ask Rico deep-link (PR-V4-3)", () => {
    it("links to /command with the encoded English guidance prompt", async () => {
        getMissionMock.mockResolvedValue(FULL_MISSION);
        renderWithProviders(<DashboardAtelier />);

        const link = await screen.findByTestId("dashboard-ask-rico");
        expect(link).toHaveAttribute(
            "href",
            `/command?q=${encodeURIComponent("Help me decide my next step toward my goal.")}`,
        );
        expect(link).toHaveTextContent("Ask Rico");
    });

    it("links to /command with the encoded Arabic prompt in Arabic mode", async () => {
        window.localStorage.setItem("rico-language", "ar");
        getMissionMock.mockResolvedValue(FULL_MISSION);
        renderWithProviders(<DashboardAtelier />);

        const link = await screen.findByTestId("dashboard-ask-rico");
        expect(link).toHaveAttribute(
            "href",
            `/command?q=${encodeURIComponent("ساعدني في تحديد خطوتي التالية نحو هدفي.")}`,
        );
    });

    it("does not render while the mission failed to load (error state)", async () => {
        getMissionMock.mockRejectedValue(new Error("down"));
        renderWithProviders(<DashboardAtelier />);

        await screen.findByTestId("dashboard-error");
        expect(screen.queryByTestId("dashboard-ask-rico")).toBeNull();
    });
});

describe("DashboardAtelier — Arabic", () => {
    it("renders the localized goal title and actions in Arabic", async () => {
        window.localStorage.setItem("rico-language", "ar");
        getMissionMock.mockResolvedValue(EMPTY_MISSION);
        renderWithProviders(<DashboardAtelier />);

        expect(await screen.findByTestId("dashboard-goal-title")).toHaveTextContent("حدّد مهمّتك الأولى");
        const actions = screen.getAllByTestId("dashboard-next-action");
        expect(actions[0]).toHaveTextContent("ارفع سيرتك الذاتية");
    });
});
