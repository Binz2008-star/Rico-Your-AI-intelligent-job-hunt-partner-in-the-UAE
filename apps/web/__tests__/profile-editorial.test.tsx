import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "./test-utils";

/**
 * /profile editorial rebuild (owner design 2026-07-17).
 *
 * Pins the real-data wiring contract:
 *  - every rendered fact comes from ProfileResponse / user files /
 *    subscription APIs (no sample data, no retired plan copy)
 *  - edits accumulate into one dirty draft; Save issues a single PATCH with
 *    only the changed fields; Discard restores the loaded profile
 *  - validation: numeric salary/years, max 4 target roles, UAE-only cities
 *  - documents: set-primary and two-step delete hit the real endpoints
 */

const {
    fetchProfileMock,
    updateProfileMock,
    listUserFilesMock,
    deleteUserFileMock,
    setPrimaryFileMock,
    uploadCVMock,
    getMySubscriptionMock,
} = vi.hoisted(() => ({
    fetchProfileMock: vi.fn(),
    updateProfileMock: vi.fn(),
    listUserFilesMock: vi.fn(),
    deleteUserFileMock: vi.fn(),
    setPrimaryFileMock: vi.fn(),
    uploadCVMock: vi.fn(),
    getMySubscriptionMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

// Authenticated session so the /profile auth guard allows the page to render.
vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => ({
        user: { user_id: "synthetic@test.dev", name: "Maryam", email: "synthetic@test.dev" },
        ready: true,
        logout: vi.fn(),
    }),
}));

// The Gmail connector card has its own dedicated tests; stub it here so this
// suite never touches the gmail endpoints.
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
    deleteUserFile: deleteUserFileMock,
    setPrimaryFile: setPrimaryFileMock,
    uploadCV: uploadCVMock,
    getMySubscription: getMySubscriptionMock,
}));

import ProfilePage from "@/app/profile/page";

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
};

const FILES = {
    files: [
        {
            id: "f1",
            user_id: "synthetic-user",
            filename: "cv-main.pdf",
            original_filename: "Maryam_CV.pdf",
            doc_type: "cv",
            file_size: 284_000,
            label: null,
            is_primary: true,
            updated_at: "2026-07-10T08:00:00Z",
            created_at: "2026-07-01T08:00:00Z",
        },
        {
            id: "f2",
            user_id: "synthetic-user",
            filename: "cover.docx",
            original_filename: "Cover_letter.docx",
            doc_type: "cover_letter",
            file_size: 46_000,
            label: "Base template",
            is_primary: false,
            updated_at: "2026-06-20T08:00:00Z",
            created_at: "2026-06-20T08:00:00Z",
        },
    ],
    total: 2,
};

const ACTIVE_SUBSCRIPTION = {
    subscription: {
        user_id: "synthetic-user",
        plan: "pro",
        subscription_status: "active",
        paddle_customer_id: "ctm_1",
        paddle_subscription_id: "sub_1",
        current_period_start: "2026-07-03T00:00:00Z",
        current_period_end: "2026-08-03T00:00:00Z",
        cancel_at: null,
        canceled_at: null,
        entitlements: {},
        updated_at: "2026-07-03T00:00:00Z",
    },
    plan: {
        id: "plan_pro",
        plan: "pro",
        name: "Rico Monthly",
        price_monthly: 21.5,
        currency: "USD",
        features: [],
        entitlements: {},
        is_popular: true,
    },
    is_active: true,
};

const FREE_SUBSCRIPTION = {
    subscription: { ...ACTIVE_SUBSCRIPTION.subscription, plan: "free", subscription_status: "inactive", current_period_end: null },
    plan: null,
    is_active: false,
};

beforeEach(() => {
    vi.clearAllMocks();
    fetchProfileMock.mockResolvedValue(BASE_PROFILE);
    listUserFilesMock.mockResolvedValue(FILES);
    getMySubscriptionMock.mockResolvedValue(ACTIVE_SUBSCRIPTION);
    updateProfileMock.mockResolvedValue({ status: "ok", updated_fields: [] });
    setPrimaryFileMock.mockResolvedValue({ ok: true });
    deleteUserFileMock.mockResolvedValue({ ok: true });
});

async function renderLoaded() {
    render(<ProfilePage />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Maryam Haddad" })).toBeInTheDocument());
}

describe("profile editorial — real-data rendering", () => {
    it("renders hero identity, sections, documents, and billing from the real APIs only", async () => {
        await renderLoaded();

        // hero: honest verified-EMAIL badge (backend verifies email ownership,
        // not identity) + strength from completeness_score
        expect(screen.getByText("Verified email")).toBeInTheDocument();
        expect(screen.queryByText(/Verified identity/)).toBeNull();
        expect(screen.getByRole("progressbar", { name: "Profile strength" })).toHaveAttribute("aria-valuenow", "82");
        expect(screen.getByText("Analyst · Synthetic Co")).toBeInTheDocument();

        // numbered editorial sections
        for (const title of ["About you", "Career", "Skills", "CV & documents", "Career preferences", "Integrations", "Account & security", "Billing"]) {
            expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
        }

        // form fields bound to the loaded profile
        expect(screen.getByLabelText("Name")).toHaveValue("Maryam Haddad");
        expect(screen.getByLabelText("Phone")).toHaveValue("+971500000000");
        expect(screen.getByLabelText("Current role")).toHaveValue("Analyst");

        // documents from /api/v1/user/files
        await waitFor(() => expect(screen.getByText("Maryam_CV.pdf")).toBeInTheDocument());
        expect(screen.getByText("Cover_letter.docx")).toBeInTheDocument();
        expect(screen.getByText("Primary")).toBeInTheDocument();

        // billing facts come from GET /api/v1/subscription/me
        await waitFor(() => expect(screen.getByText("Rico Monthly")).toBeInTheDocument());
        expect(screen.getByText(/21\.50/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Manage plan" })).toHaveAttribute("href", "/subscription");

        // authoritative billing facts: retired plan copy must never render
        expect(screen.queryByText(/Rico Pro/)).toBeNull();
        expect(screen.queryByText(/AED 29|AED 49|\$29/)).toBeNull();

        // no unsaved-changes bar before any edit
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
    });

    it("shows the Free plan card only after the API confirms an inactive subscription", async () => {
        getMySubscriptionMock.mockResolvedValue(FREE_SUBSCRIPTION);
        await renderLoaded();
        await waitFor(() => expect(screen.getByText("Free")).toBeInTheDocument());
        expect(screen.queryByText("Rico Monthly")).toBeNull();
        expect(screen.getByRole("link", { name: "Manage plan" })).toHaveAttribute("href", "/subscription");
    });

    it("never shows 'Free' while the subscription request is still loading", async () => {
        getMySubscriptionMock.mockReturnValue(new Promise(() => {}));
        await renderLoaded();
        expect(screen.getByRole("heading", { name: "Billing" })).toBeInTheDocument();
        expect(screen.getByText("Loading...")).toBeInTheDocument();
        expect(screen.queryByText("Free")).toBeNull();
        expect(screen.queryByText("Rico Monthly")).toBeNull();
    });

    it("shows an explicit unavailable state (never 'Free') when the subscription request fails", async () => {
        getMySubscriptionMock.mockRejectedValue(new Error("network"));
        await renderLoaded();
        expect(await screen.findByText("Billing status unavailable — try again later.")).toBeInTheDocument();
        expect(screen.queryByText("Free")).toBeNull();
        expect(screen.getByRole("link", { name: "Manage plan" })).toHaveAttribute("href", "/subscription");
    });
});

describe("profile editorial — dirty draft save flow", () => {
    it("edits accumulate into one PATCH containing only the changed fields", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const phone = screen.getByLabelText("Phone");
        await user.clear(phone);
        await user.type(phone, "+971511111111");

        const savebar = await screen.findByTestId("profile-ed-savebar");
        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, phone: "+971511111111" });
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        await waitFor(() =>
            expect(updateProfileMock).toHaveBeenCalledWith({ phone: "+971511111111" }),
        );
        expect(updateProfileMock).toHaveBeenCalledTimes(1);
        // refreshed profile matches the draft → the bar clears
        await waitFor(() => expect(screen.queryByTestId("profile-ed-savebar")).toBeNull());
    });

    it("Discard restores the loaded profile without any API call", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const name = screen.getByLabelText("Name");
        await user.clear(name);
        await user.type(name, "Changed Name");
        const savebar = await screen.findByTestId("profile-ed-savebar");

        await user.click(within(savebar).getByRole("button", { name: "Discard" }));
        expect(screen.getByLabelText("Name")).toHaveValue("Maryam Haddad");
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
        expect(updateProfileMock).not.toHaveBeenCalled();
    });

    it("clearing a numeric field shows a validation message, keeps the edit visible, and never silently reverts", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const years = screen.getByLabelText("Experience");
        await user.clear(years);
        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        expect(await screen.findByText(/Clearing this field isn't supported yet/)).toBeInTheDocument();
        expect(updateProfileMock).not.toHaveBeenCalled();
        // the user's edit stays visible — no silent revert to the saved value
        expect(screen.getByLabelText("Experience")).toHaveValue("");
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();
    });

    it("rejects a non-numeric years value inline and never calls the API", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const years = screen.getByLabelText("Experience");
        await user.clear(years);
        await user.type(years, "six");
        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        expect(await screen.findByText("Enter a valid number of years.")).toBeInTheDocument();
        expect(updateProfileMock).not.toHaveBeenCalled();
    });

    it("enforces the 4-target-role cap and UAE-only cities", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        // add 4 more roles (5 total) via the chip editor
        for (const role of ["PM", "QA", "BA", "DevOps"]) {
            await user.click(screen.getByRole("button", { name: "+ Add role" }));
            await user.type(screen.getByRole("textbox", { name: "Add role" }), `${role}{Enter}`);
            await user.keyboard("{Escape}");
        }
        // add a non-UAE city
        await user.click(screen.getByRole("button", { name: "+ Add city" }));
        await user.type(screen.getByRole("textbox", { name: "Add city" }), "Cairo{Enter}");
        await user.keyboard("{Escape}");

        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        expect(await screen.findByText(/Maximum 4 target roles/)).toBeInTheDocument();
        expect(await screen.findByText(/Only UAE cities are supported/)).toBeInTheDocument();
        expect(updateProfileMock).not.toHaveBeenCalled();
    });
});

describe("profile editorial — honest Telegram status", () => {
    it("describes a SAVED username as 'added' — never as a connection claim", async () => {
        await renderLoaded();
        expect(screen.getByText(/Telegram username added/)).toBeInTheDocument();
        expect(screen.queryByText(/alerts connected/i)).toBeNull();
    });

    it("flags an edited, unsaved username as not yet saved", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const tg = screen.getByLabelText("Telegram");
        await user.clear(tg);
        await user.type(tg, "new_handle");

        expect(screen.getByText(/Username not yet saved/)).toBeInTheDocument();
        expect(screen.queryByText(/Telegram username added/)).toBeNull();
    });

    it("shows the opt-in hint when no username is saved", async () => {
        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, telegram_username: null });
        await renderLoaded();
        expect(screen.getByText(/Add your Telegram username/)).toBeInTheDocument();
        expect(screen.queryByText(/Telegram username added/)).toBeNull();
    });
});

describe("profile editorial — documents", () => {
    it("set-primary calls the real endpoint and reloads the list", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await screen.findByText("Cover_letter.docx");

        await user.click(screen.getByRole("button", { name: /Set primary/ }));
        await waitFor(() => expect(setPrimaryFileMock).toHaveBeenCalledWith("f2"));
        expect(listUserFilesMock).toHaveBeenCalledTimes(2);
    });

    it("delete requires an explicit second confirming click", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await screen.findByText("Cover_letter.docx");

        const deleteButtons = screen.getAllByRole("button", { name: "Delete" });
        await user.click(deleteButtons[deleteButtons.length - 1]!);
        expect(deleteUserFileMock).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "Confirm delete" }));
        await waitFor(() => expect(deleteUserFileMock).toHaveBeenCalledWith("f2"));
    });
});

describe("profile editorial — guardrail warnings", () => {
    it("wraps the warnings alert in the palette-scoped container so its text is legible on the editorial paper", async () => {
        fetchProfileMock.mockResolvedValue({
            ...BASE_PROFILE,
            warnings: [
                { code: "min_score", field: "matching", message: "Minimum fit score is 60%.", suggestion: "Scores above 80% are strong matches." },
            ],
        });
        await renderLoaded();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Minimum fit score is 60%.");
        // The alert must sit inside .profile-ed-warnings, which the component's
        // scoped CSS targets to override GuardrailWarnings' dark-app amber text.
        expect(alert.closest(".profile-ed-warnings")).not.toBeNull();
    });

    it("renders no warnings container when there are none", async () => {
        await renderLoaded();
        expect(screen.queryByRole("alert")).toBeNull();
        expect(document.querySelector(".profile-ed-warnings")).toBeNull();
    });
});
