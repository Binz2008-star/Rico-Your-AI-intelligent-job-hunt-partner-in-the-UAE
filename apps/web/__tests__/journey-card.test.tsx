/**
 * JourneyCard (#965): the career journey stage + daily plan surfaced on the
 * authenticated dashboard.
 *
 * Contracts:
 *  - loading skeleton while the request is in flight
 *  - error state with a retry button that refetches
 *  - empty/new-user state (discovery, zero counts) with a Command Center CTA
 *  - populated state: current stage, canonical counts, today's actions with
 *    count interpolation (never fake numbers)
 *  - Arabic: stage + plan render from the ar translation table
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { JourneyCard } from "@/components/JourneyCard";
import type { JourneyToday } from "@/lib/api";

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

const getJourneyToday = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return { ...actual, getJourneyToday };
});

function journeyFixture(overrides: Partial<JourneyToday["journey"]> = {}, actions: JourneyToday["plan"]["actions"] = []): JourneyToday {
    const journey = {
        user_id: "u@test.com",
        state: "discovery" as const,
        saved_count: 0,
        prepared_count: 0,
        applied_count: 0,
        follow_up_due_count: 0,
        interviewing_count: 0,
        offer_count: 0,
        ...overrides,
    };
    return {
        journey,
        plan: { user_id: journey.user_id, state: journey.state, actions },
    };
}

function renderCard(language: "en" | "ar" = "en") {
    window.localStorage.setItem("rico-language", language);
    return render(
        <LanguageProvider>
            <JourneyCard />
        </LanguageProvider>,
    );
}

beforeEach(() => {
    getJourneyToday.mockReset();
    window.localStorage.clear();
});

describe("JourneyCard states", () => {
    it("shows a loading skeleton while the request is pending", () => {
        getJourneyToday.mockReturnValue(new Promise(() => {}));
        renderCard();
        expect(screen.getByTestId("journey-loading")).toBeInTheDocument();
    });

    it("shows the error state and retries on click", async () => {
        getJourneyToday
            .mockRejectedValueOnce(new Error("boom"))
            .mockResolvedValueOnce(
                journeyFixture({ state: "searching", saved_count: 2 }, [
                    { action: "apply", message: "x", priority: "high" },
                ]),
            );

        renderCard();
        await waitFor(() => expect(screen.getByTestId("journey-error")).toBeInTheDocument());

        await userEvent.click(screen.getByRole("button", { name: /retry/i }));
        await waitFor(() => expect(screen.getByTestId("journey-card")).toBeInTheDocument());
        expect(getJourneyToday).toHaveBeenCalledTimes(2);
    });

    it("shows the empty/new-user state with a Command Center CTA", async () => {
        getJourneyToday.mockResolvedValue(
            journeyFixture({}, [{ action: "search", message: "x", priority: "high" }]),
        );

        renderCard();
        await waitFor(() => expect(screen.getByTestId("journey-empty")).toBeInTheDocument());
        expect(screen.getByText("Your journey starts here")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /start with rico/i })).toHaveAttribute(
            "href",
            "/command",
        );
    });

    it("renders stage, counts, and count-interpolated plan actions", async () => {
        getJourneyToday.mockResolvedValue(
            journeyFixture(
                {
                    state: "applying",
                    saved_count: 4,
                    applied_count: 3,
                    follow_up_due_count: 2,
                },
                [
                    { action: "follow_up", message: "backend text", priority: "high" },
                    { action: "unknown_future_action", message: "backend fallback", priority: "low" },
                ],
            ),
        );

        renderCard();
        await waitFor(() => expect(screen.getByTestId("journey-card")).toBeInTheDocument());

        expect(screen.getByTestId("journey-stage")).toHaveTextContent("Applying");
        expect(screen.getByTestId("journey-count-saved")).toHaveTextContent("4");
        expect(screen.getByTestId("journey-count-applied")).toHaveTextContent("3");
        expect(screen.getByTestId("journey-count-followups")).toHaveTextContent("2");
        // follow_up interpolates the canonical follow_up_due_count
        expect(
            screen.getByText("Follow up on 2 applications (14+ days since applying)."),
        ).toBeInTheDocument();
        // unknown action types fall back to the backend-provided message
        expect(screen.getByText("backend fallback")).toBeInTheDocument();
        // stepper marks discovery..applying active, interviewing/offer inactive
        expect(screen.getByTestId("journey-step-applying")).toHaveAttribute("data-active", "true");
        expect(screen.getByTestId("journey-step-interviewing")).toHaveAttribute(
            "data-active",
            "false",
        );
    });

    it("renders Arabic stage and plan text when language is ar", async () => {
        getJourneyToday.mockResolvedValue(
            journeyFixture(
                { state: "interviewing", applied_count: 3, interviewing_count: 1 },
                [{ action: "interview_prep", message: "x", priority: "high" }],
            ),
        );

        renderCard("ar");
        await waitFor(() => expect(screen.getByTestId("journey-card")).toBeInTheDocument());
        expect(screen.getByTestId("journey-stage")).toHaveTextContent("المقابلات");
        expect(
            screen.getByText("استعد للمقابلات القادمة — يمكن لريكو توليد أسئلة خاصة بالدور."),
        ).toBeInTheDocument();
    });
});
