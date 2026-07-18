import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "./test-utils";

/**
 * /profile editorial rebuild (owner design 2026-07-17) + TRUE section
 * navigation (Phase 3, 2026-07-18).
 *
 * Pins:
 *  - real-data wiring: every rendered fact comes from ProfileResponse / user
 *    files / subscription APIs (no sample data, no retired plan copy)
 *  - dirty draft: edits accumulate; Save issues a single PATCH with only the
 *    changed fields; Discard restores the loaded profile; numeric/role/city
 *    validation
 *  - TRUE section navigation: exactly one section renders, driven by ?section=;
 *    valid/invalid/missing fallback + canonicalization; unrelated params (incl.
 *    Gmail callback) preserved; unsaved edits survive section switches; dirty
 *    leave/refresh is guarded; scroll no longer drives the active section.
 */

// Stateful next/navigation mock: `?section=` lives in a tiny external store so
// router.push/replace re-render the consumer through useSyncExternalStore,
// mirroring real App-Router navigation (deep link, switch, back-to-URL).
const { navState, pushMock, replaceMock, setUrl } = vi.hoisted(() => {
    const state = { params: new URLSearchParams(), listeners: new Set<() => void>() };
    const set = (url: string) => {
        const qs = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
        state.params = new URLSearchParams(qs);
        state.listeners.forEach((l) => l());
    };
    return {
        navState: state,
        setUrl: set,
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

/** Seed the initial URL before render (deep-link tests). */
function seedUrl(query = "") {
    navState.params = new URLSearchParams(query);
}

/** Navigate sections via the mobile selector (the mocked Link is a plain <a>,
 *  so the selector is the interactive control that drives router.push). */
async function gotoSection(user: ReturnType<typeof userEvent.setup>, id: string) {
    await user.selectOptions(screen.getByRole("combobox", { name: "Sections" }), id);
}

const sectionHeading = (name: string) => screen.queryByRole("heading", { name });

beforeEach(() => {
    vi.clearAllMocks();
    seedUrl(""); // clean /profile by default
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
    it("renders hero identity and the default About section from the real APIs only", async () => {
        await renderLoaded();

        // hero: honest verified-EMAIL badge + strength from completeness_score
        expect(screen.getByText("Verified email")).toBeInTheDocument();
        expect(screen.queryByText(/Verified identity/)).toBeNull();
        expect(screen.getByRole("progressbar", { name: "Profile strength" })).toHaveAttribute("aria-valuenow", "82");
        expect(screen.getByText("Analyst · Synthetic Co")).toBeInTheDocument();

        // default section = About; its fields are bound to the loaded profile
        expect(sectionHeading("About you")).toBeInTheDocument();
        expect(screen.getByLabelText("Name")).toHaveValue("Maryam Haddad");
        expect(screen.getByLabelText("Phone")).toHaveValue("+971500000000");

        // no unsaved-changes bar before any edit
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
    });

    it("documents section shows files from /api/v1/user/files after navigating to it", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "documents");

        await waitFor(() => expect(screen.getByText("Maryam_CV.pdf")).toBeInTheDocument());
        expect(screen.getByText("Cover_letter.docx")).toBeInTheDocument();
        expect(screen.getByText("Primary")).toBeInTheDocument();
    });

    it("billing section shows authoritative subscription facts (no retired plan copy)", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "billing");

        await waitFor(() => expect(screen.getByText("Rico Monthly")).toBeInTheDocument());
        expect(screen.getByText(/21\.50/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Manage plan" })).toHaveAttribute("href", "/subscription");
        expect(screen.queryByText(/Rico Pro/)).toBeNull();
        expect(screen.queryByText(/AED 29|AED 49|\$29/)).toBeNull();
    });

    it("shows the Free plan card only after the API confirms an inactive subscription", async () => {
        getMySubscriptionMock.mockResolvedValue(FREE_SUBSCRIPTION);
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "billing");
        await waitFor(() => expect(screen.getByText("Free")).toBeInTheDocument());
        expect(screen.queryByText("Rico Monthly")).toBeNull();
    });

    it("never shows 'Free' while the subscription request is still loading", async () => {
        getMySubscriptionMock.mockReturnValue(new Promise(() => {}));
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "billing");
        expect(sectionHeading("Billing")).toBeInTheDocument();
        expect(screen.getByText("Loading...")).toBeInTheDocument();
        expect(screen.queryByText("Free")).toBeNull();
        expect(screen.queryByText("Rico Monthly")).toBeNull();
    });

    it("shows an explicit unavailable state (never 'Free') when the subscription request fails", async () => {
        getMySubscriptionMock.mockRejectedValue(new Error("network"));
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "billing");
        expect(await screen.findByText("Billing status unavailable — try again later.")).toBeInTheDocument();
        expect(screen.queryByText("Free")).toBeNull();
    });
});

describe("profile editorial — true section navigation", () => {
    it("renders exactly one section at a time", async () => {
        await renderLoaded();
        expect(sectionHeading("About you")).toBeInTheDocument();
        // no other section heading is in the DOM (rail labels are links, not headings)
        for (const other of ["Career", "Skills", "CV & documents", "Career goals", "Integrations", "Account & security", "Billing"]) {
            expect(sectionHeading(other)).toBeNull();
        }
    });

    it("every valid section is reachable and renders alone", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        const cases: Array<[string, string]> = [
            ["about", "About you"],
            ["career", "Career"],
            ["skills", "Skills"],
            ["documents", "CV & documents"],
            ["goals", "Career goals"],
            ["integrations", "Integrations"],
            ["security", "Account & security"],
            ["billing", "Billing"],
        ];
        for (const [slug, heading] of cases) {
            await gotoSection(user, slug);
            await waitFor(() => expect(sectionHeading(heading)).toBeInTheDocument());
        }
    });

    it("a direct deep link renders the requested section", async () => {
        seedUrl("section=goals");
        await renderLoaded();
        expect(sectionHeading("Career goals")).toBeInTheDocument();
        expect(sectionHeading("About you")).toBeNull();
    });

    it("a missing section falls back to About (URL left clean, no rewrite)", async () => {
        seedUrl("");
        await renderLoaded();
        expect(sectionHeading("About you")).toBeInTheDocument();
        expect(replaceMock).not.toHaveBeenCalled();
    });

    it("an invalid section falls back to About and canonicalizes the URL with replace", async () => {
        seedUrl("section=bogus");
        await renderLoaded();
        await waitFor(() => expect(replaceMock).toHaveBeenCalled());
        expect(replaceMock.mock.calls[0]![0]).toContain("section=about");
        expect(sectionHeading("About you")).toBeInTheDocument();
        expect(pushMock).not.toHaveBeenCalled(); // canonicalization never pushes history
    });

    it("preserves unrelated query params when switching section", async () => {
        seedUrl("section=about&ref=email&foo=bar");
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "skills");
        const url = pushMock.mock.calls.at(-1)![0];
        expect(url).toContain("section=skills");
        expect(url).toContain("ref=email");
        expect(url).toContain("foo=bar");
    });

    it("a Gmail callback opens Integrations, keeps ?gmail=, and leaves the Gmail card available", async () => {
        seedUrl("gmail=connected");
        await renderLoaded();
        await waitFor(() => expect(sectionHeading("Integrations")).toBeInTheDocument());
        // canonicalized to integrations while preserving the gmail callback param
        await waitFor(() => expect(replaceMock).toHaveBeenCalled());
        expect(replaceMock.mock.calls[0]![0]).toContain("section=integrations");
        expect(replaceMock.mock.calls[0]![0]).toContain("gmail=connected");
        expect(screen.getByTestId("gmail-card-stub")).toBeInTheDocument();
    });

    it("an explicit valid section wins even when a Gmail callback is present", async () => {
        seedUrl("section=billing&gmail=connected");
        await renderLoaded();
        expect(sectionHeading("Billing")).toBeInTheDocument();
        expect(sectionHeading("Integrations")).toBeNull();
        expect(replaceMock).not.toHaveBeenCalled();
    });

    it("the active section is URL-driven — scrolling does not change it", async () => {
        seedUrl("section=skills");
        await renderLoaded();
        expect(sectionHeading("Skills")).toBeInTheDocument();
        window.dispatchEvent(new Event("scroll"));
        // no IntersectionObserver/scroll-spy: the section is unchanged by scroll
        expect(sectionHeading("Skills")).toBeInTheDocument();
        expect(sectionHeading("Billing")).toBeNull();
    });
});

describe("profile editorial — unsaved-edit contract", () => {
    it("unsaved field values survive a section switch (and back)", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const name = screen.getByLabelText("Name");
        await user.clear(name);
        await user.type(name, "Draft Name");

        // leave About → Career → back to About; the draft must persist
        await gotoSection(user, "career");
        await waitFor(() => expect(sectionHeading("Career")).toBeInTheDocument());
        await gotoSection(user, "about");
        await waitFor(() => expect(sectionHeading("About you")).toBeInTheDocument());

        expect(screen.getByLabelText("Name")).toHaveValue("Draft Name");
        // the dirty save bar is still present — the edit was never discarded
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();
    });

    it("guards a dirty refresh/leave via beforeunload, and does not guard a clean one", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        // clean: beforeunload is not prevented
        const cleanEvt = new Event("beforeunload", { cancelable: true });
        window.dispatchEvent(cleanEvt);
        expect(cleanEvt.defaultPrevented).toBe(false);

        // make an edit → dirty
        await user.type(screen.getByLabelText("Phone"), "9");
        await screen.findByTestId("profile-ed-savebar");

        const dirtyEvt = new Event("beforeunload", { cancelable: true });
        window.dispatchEvent(dirtyEvt);
        expect(dirtyEvt.defaultPrevented).toBe(true);
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

        await waitFor(() => expect(updateProfileMock).toHaveBeenCalledWith({ phone: "+971511111111" }));
        expect(updateProfileMock).toHaveBeenCalledTimes(1);
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

    it("clearing a numeric field shows a validation message, keeps the edit, and never silently reverts", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "career");

        const years = screen.getByLabelText("Experience");
        await user.clear(years);
        const savebar = await screen.findByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));

        expect(await screen.findByText(/Clearing this field isn't supported yet/)).toBeInTheDocument();
        expect(updateProfileMock).not.toHaveBeenCalled();
        expect(screen.getByLabelText("Experience")).toHaveValue("");
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();
    });

    it("rejects a non-numeric years value inline and never calls the API", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "career");

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
        await gotoSection(user, "goals");

        for (const role of ["PM", "QA", "BA", "DevOps"]) {
            await user.click(screen.getByRole("button", { name: "+ Add role" }));
            await user.type(screen.getByRole("textbox", { name: "Add role" }), `${role}{Enter}`);
            await user.keyboard("{Escape}");
        }
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
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "integrations");
        expect(screen.getByText(/Telegram username added/)).toBeInTheDocument();
        expect(screen.queryByText(/alerts connected/i)).toBeNull();
    });

    it("flags an edited, unsaved username (edited in About) as not yet saved (shown in Integrations)", async () => {
        const user = userEvent.setup();
        await renderLoaded();

        const tg = screen.getByLabelText("Telegram");
        await user.clear(tg);
        await user.type(tg, "new_handle");

        // the unsaved draft persists across the section switch
        await gotoSection(user, "integrations");
        expect(screen.getByText(/Username not yet saved/)).toBeInTheDocument();
        expect(screen.queryByText(/Telegram username added/)).toBeNull();
    });

    it("shows the opt-in hint when no username is saved", async () => {
        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, telegram_username: null });
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "integrations");
        expect(screen.getByText(/Add your Telegram username/)).toBeInTheDocument();
        expect(screen.queryByText(/Telegram username added/)).toBeNull();
    });
});

describe("profile editorial — documents", () => {
    it("set-primary calls the real endpoint and reloads the list", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "documents");
        await screen.findByText("Cover_letter.docx");

        await user.click(screen.getByRole("button", { name: /Set primary/ }));
        await waitFor(() => expect(setPrimaryFileMock).toHaveBeenCalledWith("f2"));
        expect(listUserFilesMock).toHaveBeenCalledTimes(2);
    });

    it("delete requires an explicit second confirming click", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await gotoSection(user, "documents");
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
        expect(alert.closest(".profile-ed-warnings")).not.toBeNull();
    });

    it("renders no warnings container when there are none", async () => {
        await renderLoaded();
        expect(screen.queryByRole("alert")).toBeNull();
        expect(document.querySelector(".profile-ed-warnings")).toBeNull();
    });
});
