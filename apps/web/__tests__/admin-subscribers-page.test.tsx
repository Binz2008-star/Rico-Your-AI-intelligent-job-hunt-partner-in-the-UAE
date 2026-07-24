import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "./test-utils";

/**
 * /admin/subscribers page behavior:
 *  - a normal (non-owner) user is redirected away (direct navigation blocked);
 *  - the owner sees the table;
 *  - auto-refresh pauses while the tab is hidden and resumes when visible.
 */

const { replace, fetchMe, fetchSubscribers, fetchSubscribersSummary } = vi.hoisted(() => ({
    replace: vi.fn(),
    fetchMe: vi.fn(),
    fetchSubscribers: vi.fn(),
    fetchSubscribersSummary: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
    usePathname: () => "/admin/subscribers",
}));
vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return { ...actual, fetchMe, fetchSubscribers, fetchSubscribersSummary };
});

import AdminSubscribersPage from "@/app/admin/subscribers/page";

const summaryPayload = {
    summary: {
        total_users: 3,
        free_users: 1,
        active_subscribers: 1,
        trialing_subscribers: 0,
        past_due_subscribers: 1,
        canceling_subscribers: 0,
        canceled_subscribers: 0,
        expired_subscribers: 0,
        payment_failed_subscribers: 0,
        needs_reconciliation: 0,
        new_subscriptions_this_month: 1,
        cancellations_this_month: 0,
        approximate_mrr_usd: 21.5,
        currency: "USD",
        mrr_is_approximate: true,
    },
    last_billing_sync: "2026-07-24T10:00:00Z",
    generated_at: "2026-07-24T10:00:00Z",
    truncated: false,
    usage_available: true,
};

const listPayload = {
    subscribers: [
        {
            name: "Alpha",
            email: "alpha@x.com",
            user_id_masked: "••42",
            plan: "rico_monthly",
            status: "active",
            paddle_customer_ref: "ctm_01…a1b2",
            paddle_subscription_ref: "sub_01…c3d4",
            subscription_start: "2026-07-01T00:00:00Z",
            next_renewal: "2026-08-01T00:00:00Z",
            cancellation_effective: null,
            canceled_at: null,
            usage: {
                ai_messages: { used: 12, allowance: 300 },
                saved_jobs: { used: 3, allowance: 100 },
                cv_documents: { used: 1, allowance: 5 },
                other_documents: { used: 0, allowance: 10 },
            },
            last_activity: "2026-07-24T09:00:00Z",
            last_billing_sync: "2026-07-24T10:00:00Z",
            reconciliation: "ok",
        },
    ],
    total: 3,
    filtered_total: 1,
    limit: 200,
    offset: 0,
    filter: "all",
    last_billing_sync: "2026-07-24T10:00:00Z",
    generated_at: "2026-07-24T10:00:00Z",
    truncated: false,
    usage_available: true,
};

function setVisibility(state: "visible" | "hidden") {
    Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => {
    vi.clearAllMocks();
    fetchSubscribersSummary.mockResolvedValue(summaryPayload);
    fetchSubscribers.mockResolvedValue(listPayload);
    setVisibility("visible");
});
afterEach(() => vi.clearAllMocks());

describe("/admin/subscribers page", () => {
    it("redirects a normal (non-owner) user to /dashboard and never loads data", async () => {
        fetchMe.mockResolvedValue({ email: "u@x.com", role: "user", authenticated: true, is_owner: false });
        render(<AdminSubscribersPage />);
        await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
        expect(fetchSubscribers).not.toHaveBeenCalled();
    });

    it("redirects an unauthenticated visitor to /login", async () => {
        fetchMe.mockResolvedValue({ email: null, role: "guest", authenticated: false, guest: true });
        render(<AdminSubscribersPage />);
        await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
        expect(fetchSubscribers).not.toHaveBeenCalled();
    });

    it("renders the table for the owner", async () => {
        fetchMe.mockResolvedValue({ email: "o@x.com", role: "user", authenticated: true, is_owner: true });
        render(<AdminSubscribersPage />);
        await waitFor(() => expect(fetchSubscribers).toHaveBeenCalled());
        // Rendered in both the desktop table and the mobile card layout.
        expect((await screen.findAllByText("alpha@x.com")).length).toBeGreaterThan(0);
        expect(replace).not.toHaveBeenCalled();
    });

    it("pauses auto-refresh while hidden and resumes when visible again", async () => {
        fetchMe.mockResolvedValue({ email: "o@x.com", role: "user", authenticated: true, is_owner: true });
        render(<AdminSubscribersPage />);
        await waitFor(() => expect(fetchSubscribers).toHaveBeenCalled());

        const baseline = fetchSubscribers.mock.calls.length;

        // Hidden: becoming hidden must NOT trigger a load.
        setVisibility("hidden");
        await Promise.resolve();
        expect(fetchSubscribers.mock.calls.length).toBe(baseline);

        // Visible again: resume triggers an immediate refresh.
        setVisibility("visible");
        await waitFor(() => expect(fetchSubscribers.mock.calls.length).toBeGreaterThan(baseline));
    });
});
