import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders as render } from "./test-utils";

/**
 * Route-exit dirty-state protection (Profile track Phase 4).
 *
 * Browser Back/forward that EXITS /profile cannot be blocked safely in the
 * Next 14 App Router without a history trap that would break in-profile
 * section back/forward (#1161's documented residual). Protection is therefore
 * restore-based: the dirty draft is mirrored to per-tab sessionStorage, so any
 * route exit — Back included — cannot destroy unsaved edits; returning to
 * /profile restores the draft and the unsaved-changes bar.
 *
 * Pins:
 *  - a dirty edit is mirrored (keyed to the account email);
 *  - save success and Discard both remove the mirror;
 *  - a remount (route return) restores the stored draft + savebar;
 *  - a stored draft from a DIFFERENT account is ignored AND wiped;
 *  - corrupt storage never crashes and yields a clean start;
 *  - a stored draft identical to the loaded profile stays clean;
 *  - the existing #1161 guards (no prompt when clean / on section switch)
 *    remain pinned by profile-editorial.test.tsx — unchanged here.
 */

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
    // ProfileAvatar (hero) — resolves to no avatar; suites assert the form, not the photo.
    getAvatar: () => Promise.resolve({ avatar: null }),
    uploadAvatar: () => Promise.resolve({ ok: true, avatar: "" }),
    deleteAvatar: () => Promise.resolve({ ok: true, deleted: false }),
    fetchProfile: fetchProfileMock,
    updateProfile: updateProfileMock,
    listUserFiles: listUserFilesMock,
    deleteUserFile: vi.fn(),
    setPrimaryFile: vi.fn(),
    uploadCV: vi.fn(),
    getMySubscription: getMySubscriptionMock,
}));

import ProfilePage from "@/app/profile/page";

const DRAFT_KEY = "rico-profile-draft";

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
    warnings: [],
};

beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
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

function storedDraft(): { email: string; draft: Record<string, unknown> } | null {
    const raw = window.sessionStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
}

describe("dirty-draft mirroring", () => {
    it("mirrors a dirty edit to sessionStorage keyed to the account email", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        expect(storedDraft()).toBeNull(); // clean → nothing stored

        await user.type(screen.getByLabelText("Phone"), "9");
        await screen.findByTestId("profile-ed-savebar");

        await waitFor(() => {
            const stored = storedDraft();
            expect(stored).not.toBeNull();
            expect(stored!.email).toBe("synthetic@test.dev");
            expect(stored!.draft.phone).toBe("+9715000000009");
        });
    });

    it("save success removes the mirror", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, phone: "+9715000000009" });
        await user.type(screen.getByLabelText("Phone"), "9");
        const savebar = await screen.findByTestId("profile-ed-savebar");
        expect(storedDraft()).not.toBeNull();

        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));
        await waitFor(() => expect(screen.queryByTestId("profile-ed-savebar")).toBeNull());
        expect(storedDraft()).toBeNull();
    });

    it("Discard removes the mirror", async () => {
        const user = userEvent.setup();
        await renderLoaded();
        await user.type(screen.getByLabelText("Phone"), "9");
        const savebar = await screen.findByTestId("profile-ed-savebar");
        expect(storedDraft()).not.toBeNull();

        await user.click(within(savebar).getByRole("button", { name: "Discard" }));
        await waitFor(() => expect(screen.queryByTestId("profile-ed-savebar")).toBeNull());
        expect(storedDraft()).toBeNull();
    });
});

describe("restore on return (route-exit protection)", () => {
    it("a fresh mount restores a stored same-account draft with the unsaved bar", async () => {
        window.sessionStorage.setItem(
            DRAFT_KEY,
            JSON.stringify({
                email: "synthetic@test.dev",
                draft: { name: "Draft Survived Back", phone: "+971500000000" },
            }),
        );
        await renderLoaded();

        expect(screen.getByLabelText("Name")).toHaveValue("Draft Survived Back");
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();
        // untouched fields keep the loaded profile's values
        expect(screen.getByLabelText("Phone")).toHaveValue("+971500000000");
    });

    it("ignores AND wipes a stored draft from a different account", async () => {
        window.sessionStorage.setItem(
            DRAFT_KEY,
            JSON.stringify({ email: "someone-else@test.dev", draft: { name: "Foreign Draft" } }),
        );
        await renderLoaded();

        expect(screen.getByLabelText("Name")).toHaveValue("Maryam Haddad");
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
        expect(window.sessionStorage.getItem(DRAFT_KEY)).toBeNull(); // wiped
    });

    it("corrupt storage never crashes and yields a clean start", async () => {
        window.sessionStorage.setItem(DRAFT_KEY, "{not json");
        await renderLoaded();
        expect(screen.getByLabelText("Name")).toHaveValue("Maryam Haddad");
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
    });

    it("a stored draft identical to the loaded profile stays clean (no phantom dirty)", async () => {
        window.sessionStorage.setItem(
            DRAFT_KEY,
            JSON.stringify({
                email: "synthetic@test.dev",
                draft: { name: "Maryam Haddad", phone: "+971500000000" },
            }),
        );
        await renderLoaded();
        expect(screen.queryByTestId("profile-ed-savebar")).toBeNull();
        // and the clean state clears the leftover mirror
        await waitFor(() => expect(window.sessionStorage.getItem(DRAFT_KEY)).toBeNull());
    });

    it("restored drafts keep working with section navigation and the save flow", async () => {
        window.sessionStorage.setItem(
            DRAFT_KEY,
            JSON.stringify({ email: "synthetic@test.dev", draft: { years_experience: "12" } }),
        );
        const user = userEvent.setup();
        await renderLoaded();
        expect(screen.getByTestId("profile-ed-savebar")).toBeInTheDocument();

        await user.selectOptions(screen.getByRole("combobox", { name: "Sections" }), "career");
        expect(screen.getByLabelText("Experience")).toHaveValue("12");

        fetchProfileMock.mockResolvedValue({ ...BASE_PROFILE, years_experience: 12 });
        const savebar = screen.getByTestId("profile-ed-savebar");
        await user.click(within(savebar).getByRole("button", { name: "Save changes" }));
        await waitFor(() => expect(updateProfileMock).toHaveBeenCalledWith({ years_experience: 12 }));
        await waitFor(() => expect(window.sessionStorage.getItem(DRAFT_KEY)).toBeNull());
    });
});
