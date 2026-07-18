import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders as render } from "./test-utils";

/**
 * Actionable profile warnings (Profile Phase 4B).
 *
 * Pins the workflow built on the backend-authoritative severity contract
 * (Phase 4A, #1164):
 *  - severity rendering for all three tiers (blocking / important /
 *    recommendation), backend value authoritative, unknown → important;
 *  - stable field-identifier mapping: profile-owned fields (target_roles,
 *    preferred_cities) deep-link to /profile?section=goals + focus/highlight
 *    the exact field container; settings-owned fields link to /settings;
 *  - URL preservation on warning-driven navigation;
 *  - unsaved draft survives warning-driven navigation;
 *  - refreshed profile response drives the list: resolved warnings disappear,
 *    the live count updates, and the panel hides when none remain;
 *  - blocking warnings cannot be deferred; important/recommendation get a
 *    session-scoped "Review later" that never claims resolution;
 *  - English and Arabic (RTL) rendering.
 */

// Stateful next/navigation mock (same contract as profile-editorial.test.tsx).
const { navState, pushMock, replaceMock } = vi.hoisted(() => {
    const state = { params: new URLSearchParams(), listeners: new Set<() => void>() };
    const set = (url: string) => {
        const qs = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
        state.params = new URLSearchParams(qs);
        state.listeners.forEach((l) => l());
    };
    return {
        navState: state,
        pushMock: vi.fn((url: string) => set(url)),
        replaceMock: vi.fn((url: string) => set(url)),
    };
});

vi.mock("next/navigation", async () => {
    const React = await import("react");
    return {
        usePathname: () => "/profile",
        useRouter: () => ({ push: pushMock, replace: replaceMock }),
        useSearchParams: () =>
            React.useSyncExternalStore(
                (cb: () => void) => {
                    navState.listeners.add(cb);
                    return () => navState.listeners.delete(cb);
                },
                () => navState.params,
                () => navState.params,
            ),
    };
});

const { fetchProfileMock, updateProfileMock, listUserFilesMock, getMySubscriptionMock } = vi.hoisted(() => ({
    fetchProfileMock: vi.fn(),
    updateProfileMock: vi.fn(),
    listUserFilesMock: vi.fn(),
    getMySubscriptionMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => ({
        user: { user_id: "synthetic@test.dev", name: "Maryam", email: "synthetic@test.dev" },
        ready: true,
        logout: vi.fn(),
    }),
}));

vi.mock("@/components/settings/GmailConnectionCard", () => ({
    GmailConnectionCard: () => <div data-testid="gmail-card-stub">Gmail</div>,
}));

vi.mock("@/lib/api", () => ({
    ApiError: class ApiError extends Error {
        statusCode: number;
        constructor(message: string, statusCode: number) {
            super(message);
            this.statusCode = statusCode;
        }
    },
    fetchProfile: fetchProfileMock,
    updateProfile: updateProfileMock,
    listUserFiles: listUserFilesMock,
    deleteUserFile: vi.fn(),
    setPrimaryFile: vi.fn(),
    uploadCV: vi.fn(),
    getMySubscription: getMySubscriptionMock,
}));

import ProfilePage from "@/app/profile/page";

/** The three tiers, on synthetic warnings mirroring the backend contract. */
const BLOCKING_CITY = {
    code: "invalid_uae_city",
    field: "preferred_cities",
    severity: "blocking",
    message: "City value 'Cairo' is not recognized as a UAE city.",
    suggestion: "Choose a UAE city such as Dubai or Abu Dhabi.",
    message_ar: "قيمة المدينة 'Cairo' ليست مدينة إماراتية معروفة.",
    suggestion_ar: "اختر مدينة إماراتية مثل دبي أو أبو ظبي.",
};
const RECOMMENDATION_ROLES = {
    code: "too_many_target_roles",
    field: "target_roles",
    severity: "recommendation",
    message: "You have 5 target roles.",
    suggestion: "Choose up to 3 primary roles.",
    message_ar: "لديك 5 أدوار مستهدفة.",
    suggestion_ar: "اختر حتى 3 أدوار اساسية.",
};
const IMPORTANT_SCORE = {
    code: "minimum_fit_score_high",
    field: "min_score",
    severity: "important",
    message: "Minimum fit score is 80%.",
    suggestion: "Use 60% or lower.",
    message_ar: "الحد الادنى لدرجة الملاءمة هو 80%.",
    suggestion_ar: "استخدم 60% أو أقل.",
};
const ALL_WARNINGS = [RECOMMENDATION_ROLES, IMPORTANT_SCORE, BLOCKING_CITY];

const BASE_PROFILE = {
    profile_exists: true,
    email: "synthetic@test.dev",
    user_id: "synthetic-user",
    name: "Maryam Haddad",
    phone: "+971500000000",
    telegram_username: "maryam_test",
    target_roles: ["Data Analyst"],
    preferred_cities: ["Dubai"],
    salary_expectation_aed: 20000,
    minimum_salary_aed: 15000,
    skills: ["SQL", "Python"],
    industries: null,
    visa_status: "Employment visa",
    notice_period: "30 days",
    years_experience: 6,
    current_role: "Analyst",
    current_company: "Synthetic Co",
    linkedin_url: "https://linkedin.com/in/synthetic",
    completeness_score: 82,
    warnings: ALL_WARNINGS,
};

beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    navState.params = new URLSearchParams();
    fetchProfileMock.mockResolvedValue(BASE_PROFILE);
    listUserFilesMock.mockResolvedValue({ files: [], total: 0 });
    getMySubscriptionMock.mockResolvedValue({
        subscription: {
            user_id: "synthetic-user",
            plan: "free",
            subscription_status: "inactive",
            paddle_customer_id: null,
            paddle_subscription_id: null,
            current_period_start: null,
            current_period_end: null,
            cancel_at: null,
            canceled_at: null,
            entitlements: {},
            updated_at: "2026-07-03T00:00:00Z",
        },
        plan: null,
        is_active: false,
    });
    updateProfileMock.mockResolvedValue({ status: "ok" });
});

async function renderLoaded() {
    const view = render(<ProfilePage />);
    await screen.findByLabelText("Name");
    return view;
}

const panel = () => screen.getByRole("region", { name: /affecting your job matches/ });

describe("severity rendering", () => {
    it("renders every tier with its backend-assigned severity badge, blocking first", async () => {
        await renderLoaded();
        const items = within(panel()).getAllByRole("listitem");
        expect(items).toHaveLength(3);
        // sorted: blocking → important → recommendation, regardless of API order
        expect(items[0]).toHaveAttribute("data-warning-severity", "blocking");
        expect(within(items[0]!).getByText("Blocking")).toBeInTheDocument();
        expect(items[1]).toHaveAttribute("data-warning-severity", "important");
        expect(within(items[1]!).getByText("Important")).toBeInTheDocument();
        expect(items[2]).toHaveAttribute("data-warning-severity", "recommendation");
        expect(within(items[2]!).getByText("Suggestion")).toBeInTheDocument();
    });

    it("renders message and suggestion for each warning", async () => {
        await renderLoaded();
        expect(screen.getByText(BLOCKING_CITY.message)).toBeInTheDocument();
        expect(screen.getByText(BLOCKING_CITY.suggestion)).toBeInTheDocument();
    });

    it("treats an unknown severity as important (mirrors the backend fail-safe)", async () => {
        fetchProfileMock.mockResolvedValue({
            ...BASE_PROFILE,
            warnings: [{ ...IMPORTANT_SCORE, severity: "mystery_tier" }],
        });
        await renderLoaded();
        const item = within(panel()).getAllByRole("listitem")[0]!;
        expect(item).toHaveAttribute("data-warning-severity", "important");
    });

    it("summary shows the live count with plural handling", async () => {
        await renderLoaded();
        expect(screen.getByText("3 items are affecting your job matches")).toBeInTheDocument();
        expect(screen.getByText("Review them to improve result quality.")).toBeInTheDocument();
    });

    it("uses the singular summary for exactly one warning", async () => {
        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, warnings: [BLOCKING_CITY] });
        await renderLoaded();
        expect(screen.getByText("1 item is affecting your job matches")).toBeInTheDocument();
    });
});

describe("field mapping and direct navigation", () => {
    it("profile-owned fields navigate to ?section=goals, focus and highlight the exact field", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        await user.click(screen.getByRole("button", { name: "Go to Cities" }));

        // navigated via the URL contract
        expect(pushMock).toHaveBeenCalled();
        expect(pushMock.mock.calls.at(-1)![0]).toContain("section=goals");
        // the goals section rendered and the exact field container got focus + flash
        await waitFor(() => {
            const anchor = document.getElementById("profile-field-preferred_cities");
            expect(anchor).not.toBeNull();
            expect(anchor).toHaveFocus();
            expect(anchor!.className).toContain("profile-ed-field-flash");
        });
        // screen readers hear the move
        expect(screen.getByRole("status")).toHaveTextContent("Moved to Cities");
    });

    it("target-roles warnings focus the target-roles field container", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await user.click(screen.getByRole("button", { name: "Go to Target roles" }));
        await waitFor(() => {
            expect(document.getElementById("profile-field-target_roles")).toHaveFocus();
        });
    });

    it("settings-owned fields link to /settings instead of a profile section", async () => {
        await renderLoaded();
        const link = screen.getByRole("link", { name: "Open Settings" });
        expect(link).toHaveAttribute("href", "/settings");
    });

    it("preserves unrelated query parameters on warning-driven navigation", async () => {
        navState.params = new URLSearchParams("ref=email&foo=bar");
        const user = userEvent.setup();
        await renderLoaded();
        await user.click(screen.getByRole("button", { name: "Go to Target roles" }));
        const url = pushMock.mock.calls.at(-1)![0];
        expect(url).toContain("section=goals");
        expect(url).toContain("ref=email");
        expect(url).toContain("foo=bar");
    });

    it("keeps unsaved edits intact across warning-driven navigation", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const name = screen.getByLabelText("Name");
        await user.clear(name);
        await user.type(name, "Draft Name");
        await screen.findByTestId("profile-ed-savebar");

        await user.click(screen.getByRole("button", { name: "Go to Cities" }));
        await waitFor(() => expect(screen.getByRole("heading", { name: "Career goals" })).toBeInTheDocument());
        // no prompt, and the draft survives the section change
        await user.selectOptions(screen.getByRole("combobox", { name: "Sections" }), "about");
        expect(screen.getByLabelText("Name")).toHaveValue("Draft Name");
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();
    });
});

describe("state behavior after save", () => {
    it("a refreshed profile response removes resolved warnings and updates the count", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        expect(screen.getByText("3 items are affecting your job matches")).toBeInTheDocument();

        // fix the city and save: the refreshed authoritative response carries
        // only the remaining warnings
        fetchProfileMock.mockResolvedValue({
            ...BASE_PROFILE,
            phone: "+971511111111",
            warnings: [IMPORTANT_SCORE],
        });
        await user.type(screen.getByLabelText("Phone"), "9");
        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        await waitFor(() => {
            expect(screen.getByText("1 item is affecting your job matches")).toBeInTheDocument();
        });
        expect(screen.queryByText(BLOCKING_CITY.message)).toBeNull();
        expect(screen.queryByText(RECOMMENDATION_ROLES.message)).toBeNull();
        expect(screen.getByText(IMPORTANT_SCORE.message)).toBeInTheDocument();
    });

    it("hides the panel entirely when the refreshed response has no warnings", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, phone: "+971511111111", warnings: [] });
        await user.type(screen.getByLabelText("Phone"), "9");
        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        await waitFor(() => {
            expect(screen.queryByRole("region", { name: /affecting your job matches/ })).toBeNull();
        });
        expect(document.querySelector(".profile-ed-warnings")).toBeNull();
    });
});

describe("review later semantics", () => {
    it("blocking warnings expose no Review later control", async () => {
        await renderLoaded();
        const blockingItem = within(panel())
            .getAllByRole("listitem")
            .find((li) => li.getAttribute("data-warning-severity") === "blocking")!;
        expect(within(blockingItem).queryByRole("button", { name: "Review later" })).toBeNull();
        // non-blocking items DO expose it
        const importantItem = within(panel())
            .getAllByRole("listitem")
            .find((li) => li.getAttribute("data-warning-severity") === "important")!;
        expect(within(importantItem).getByRole("button", { name: "Review later" })).toBeInTheDocument();
    });

    it("Review later hides a non-blocking warning for the session without claiming it is resolved", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const importantItem = within(panel())
            .getAllByRole("listitem")
            .find((li) => li.getAttribute("data-warning-severity") === "important")!;
        await user.click(within(importantItem).getByRole("button", { name: "Review later" }));

        // hidden from the active list; count updates; deferral is labelled as
        // set-aside (session-scoped), never as fixed/resolved
        expect(screen.queryByText(IMPORTANT_SCORE.message)).toBeNull();
        expect(screen.getByText("2 items are affecting your job matches")).toBeInTheDocument();
        expect(screen.getByText("1 set aside until your next visit")).toBeInTheDocument();

        // restorable — nothing was lost
        await user.click(screen.getByRole("button", { name: "Show" }));
        expect(screen.getByText(IMPORTANT_SCORE.message)).toBeInTheDocument();
        expect(screen.getByText("3 items are affecting your job matches")).toBeInTheDocument();
    });

    it("blocking warnings stay prominent (first) even after deferring others", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        const recItem = within(panel())
            .getAllByRole("listitem")
            .find((li) => li.getAttribute("data-warning-severity") === "recommendation")!;
        await user.click(within(recItem).getByRole("button", { name: "Review later" }));
        const remaining = within(panel()).getAllByRole("listitem");
        expect(remaining[0]).toHaveAttribute("data-warning-severity", "blocking");
    });
});

describe("Arabic (RTL)", () => {
    it("renders the Arabic summary, severity labels, messages, and actions", async () => {
        window.localStorage.setItem("rico-language", "ar");
        render(<ProfilePage />);

        expect(await screen.findByText("3 أمور تؤثر على مطابقة الوظائف")).toBeInTheDocument();
        expect(screen.getByText("راجعها لتحصل على نتائج أدق.")).toBeInTheDocument();
        expect(screen.getByText(BLOCKING_CITY.message_ar)).toBeInTheDocument();
        expect(screen.getByText(BLOCKING_CITY.suggestion_ar)).toBeInTheDocument();
        expect(screen.getByText("يحجب النتائج")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "افتح الإعدادات" })).toHaveAttribute("href", "/settings");
        expect(screen.getAllByRole("button", { name: /انتقل إلى/ }).length).toBeGreaterThanOrEqual(1);
    });
});
