import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkspacePalette } from "@/components/workspace/theme";
import type { GmailStatusResponse } from "@/lib/api";

/**
 * GmailConnectionCard — Gmail recurring-sync consent + connection-state readiness.
 *
 * Pins the truthful-state contract without enabling Gmail:
 *  - no connect/consent request is issued while the feature is disabled;
 *  - "connected" only renders when the backend reports it;
 *  - recurring background sync requires an explicit, never-preselected approval;
 *  - an unchecked approval cannot continue and calls no endpoint;
 *  - approval uses only the dedicated consent contract;
 *  - failures never claim success;
 *  - disconnect requires a confirmation step;
 *  - Arabic RTL copy renders;
 *  - no token/secret material appears in the browser-visible output.
 *
 * Backend is fully mocked — no live Gmail endpoints are touched.
 */

const {
    getGmailStatusMock,
    getGmailConnectUrlMock,
    disconnectGmailMock,
    syncGmailMock,
    setGmailRecurringSyncConsentMock,
} = vi.hoisted(() => ({
    getGmailStatusMock: vi.fn(),
    getGmailConnectUrlMock: vi.fn(),
    disconnectGmailMock: vi.fn(),
    syncGmailMock: vi.fn(),
    setGmailRecurringSyncConsentMock: vi.fn(),
}));

let currentLanguage: "en" | "ar" = "en";

vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: currentLanguage, setLanguage: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
    getGmailStatus: (...a: unknown[]) => getGmailStatusMock(...a),
    getGmailConnectUrl: (...a: unknown[]) => getGmailConnectUrlMock(...a),
    disconnectGmail: (...a: unknown[]) => disconnectGmailMock(...a),
    syncGmail: (...a: unknown[]) => syncGmailMock(...a),
    setGmailRecurringSyncConsent: (...a: unknown[]) =>
        setGmailRecurringSyncConsentMock(...a),
}));

// Imported AFTER the mocks are registered.
import { GmailConnectionCard } from "@/components/settings/GmailConnectionCard";

const palette = {
    ink: "#111111",
    bg: "#ffffff",
    red: "#b00020",
    hair: "#e5e5e5",
    ink55: "#555555",
    ink40: "#888888",
} as unknown as WorkspacePalette;

function status(overrides: Partial<GmailStatusResponse> = {}): GmailStatusResponse {
    return {
        sync_enabled: true,
        enabled: true,
        connected: false,
        provider_email: null,
        scopes: [],
        needs_reauth: false,
        recurring_sync_consent: false,
        last_sync_at: null,
        ...overrides,
    };
}

function renderCard(notify = vi.fn()) {
    render(<GmailConnectionCard palette={palette} notify={notify} />);
    return notify;
}

beforeEach(() => {
    currentLanguage = "en";
    getGmailStatusMock.mockReset().mockResolvedValue(status());
    getGmailConnectUrlMock.mockReset().mockResolvedValue({ auth_url: "https://x" });
    disconnectGmailMock
        .mockReset()
        .mockResolvedValue({ disconnected: true, revoked_at_google: true });
    syncGmailMock.mockReset().mockResolvedValue({ status: "started" });
    setGmailRecurringSyncConsentMock
        .mockReset()
        .mockResolvedValue({ recurring_sync_consent: true });
});

describe("disabled / fail-closed", () => {
    it("shows coming-soon and never calls connect when the feature is disabled", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ sync_enabled: false, enabled: false, connected: false }),
        );
        renderCard();

        expect(
            await screen.findByText(/Coming soon — Gmail sync is not enabled yet/i),
        ).toBeInTheDocument();

        const connect = screen.getByRole("button", { name: /Connect Gmail/i });
        expect(connect).toBeDisabled();

        // A disabled button issues no network call even if a click is attempted.
        await userEvent.click(connect);
        expect(getGmailConnectUrlMock).not.toHaveBeenCalled();

        // No consent affordance while not connected.
        expect(screen.queryByTestId("gmail-consent-section")).not.toBeInTheDocument();
    });
});

describe("truthful status", () => {
    it("renders connected only when the backend reports it", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, provider_email: "someone@gmail.com" }),
        );
        renderCard();
        expect(
            await screen.findByText(/Connected as someone@gmail.com/i),
        ).toBeInTheDocument();
        expect(screen.getByTestId("gmail-consent-section")).toBeInTheDocument();
    });

    it("does not claim connected when the backend says not connected", async () => {
        getGmailStatusMock.mockResolvedValue(status({ connected: false }));
        renderCard();
        expect(await screen.findByText(/Not connected/i)).toBeInTheDocument();
        expect(screen.queryByTestId("gmail-consent-section")).not.toBeInTheDocument();
    });

    it("connected while sync is disabled: truthful state, Sync/Connect off, Disconnect on", async () => {
        // The flag gates SYNC, not visibility: a live connection must still show
        // truthfully and stay revocable while RICO_ENABLE_GMAIL_SYNC is off.
        getGmailStatusMock.mockResolvedValue(
            status({
                sync_enabled: false,
                enabled: false,
                connected: true,
                provider_email: "someone@gmail.com",
            }),
        );
        renderCard();
        // Truthful: connected AND explicitly notes sync is disabled — never "disconnected".
        expect(
            await screen.findByText(/Connected as someone@gmail.com.*sync currently disabled/i),
        ).toBeInTheDocument();
        expect(screen.queryByText(/Coming soon/i)).not.toBeInTheDocument();
        // Sync is unavailable; there is no Connect button (already connected).
        expect(screen.getByRole("button", { name: /Sync now/i })).toBeDisabled();
        expect(screen.queryByRole("button", { name: /Connect Gmail/i })).not.toBeInTheDocument();
        // Disconnect stays available (ungated), and consent controls are present.
        expect(screen.getByRole("button", { name: /^Disconnect$/i })).toBeEnabled();
        expect(screen.getByTestId("gmail-consent-section")).toBeInTheDocument();
    });
});

describe("recurring-sync consent", () => {
    it("requires an explicit, never-preselected approval before recurring sync", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, recurring_sync_consent: false }),
        );
        renderCard();

        expect(
            await screen.findByText(/Recurring background sync: not approved yet/i),
        ).toBeInTheDocument();

        // Open the disclosure panel.
        await userEvent.click(
            screen.getByRole("button", { name: /Review & approve recurring sync/i }),
        );

        const checkbox = screen.getByRole("checkbox");
        expect(checkbox).not.toBeChecked(); // never preselected

        const grant = screen.getByRole("button", { name: /Approve recurring sync/i });
        expect(grant).toBeDisabled(); // unchecked → cannot continue

        await userEvent.click(grant);
        expect(setGmailRecurringSyncConsentMock).not.toHaveBeenCalled();
    });

    it("uses only the dedicated consent contract once approved", async () => {
        getGmailStatusMock
            .mockResolvedValueOnce(status({ connected: true, recurring_sync_consent: false }))
            .mockResolvedValue(status({ connected: true, recurring_sync_consent: true }));
        const notify = renderCard();

        await userEvent.click(
            await screen.findByRole("button", { name: /Review & approve recurring sync/i }),
        );
        await userEvent.click(screen.getByRole("checkbox"));
        const grant = screen.getByRole("button", { name: /Approve recurring sync/i });
        expect(grant).toBeEnabled();
        await userEvent.click(grant);

        expect(setGmailRecurringSyncConsentMock).toHaveBeenCalledTimes(1);
        expect(setGmailRecurringSyncConsentMock).toHaveBeenCalledWith(true);
        await waitFor(() =>
            expect(notify).toHaveBeenCalledWith(
                expect.stringMatching(/approved/i),
                "success",
            ),
        );
    });

    it("revoke is available when approved and uses granted=false", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, recurring_sync_consent: true }),
        );
        renderCard();
        const revoke = await screen.findByRole("button", {
            name: /Turn off recurring sync/i,
        });
        await userEvent.click(revoke);
        expect(setGmailRecurringSyncConsentMock).toHaveBeenCalledWith(false);
    });

    it("a consent failure does not claim success", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, recurring_sync_consent: false }),
        );
        setGmailRecurringSyncConsentMock.mockRejectedValue(new Error("boom"));
        const notify = renderCard();

        await userEvent.click(
            await screen.findByRole("button", { name: /Review & approve recurring sync/i }),
        );
        await userEvent.click(screen.getByRole("checkbox"));
        await userEvent.click(
            screen.getByRole("button", { name: /Approve recurring sync/i }),
        );

        await waitFor(() =>
            expect(notify).toHaveBeenCalledWith(
                expect.stringMatching(/failed/i),
                "error",
            ),
        );
        expect(notify).not.toHaveBeenCalledWith(
            expect.anything(),
            "success",
        );
    });
});

describe("disconnect confirmation", () => {
    it("requires a confirmation step before disconnecting", async () => {
        getGmailStatusMock.mockResolvedValue(status({ connected: true }));
        renderCard();

        await userEvent.click(
            await screen.findByRole("button", { name: /^Disconnect$/i }),
        );
        // Confirmation region appears; the network call has NOT happened yet.
        expect(screen.getByTestId("gmail-disconnect-confirm")).toBeInTheDocument();
        expect(disconnectGmailMock).not.toHaveBeenCalled();

        await userEvent.click(
            screen.getByRole("button", { name: /Yes, disconnect/i }),
        );
        expect(disconnectGmailMock).toHaveBeenCalledTimes(1);
    });

    it("cancel aborts the disconnect", async () => {
        getGmailStatusMock.mockResolvedValue(status({ connected: true }));
        renderCard();
        await userEvent.click(
            await screen.findByRole("button", { name: /^Disconnect$/i }),
        );
        await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
        expect(screen.queryByTestId("gmail-disconnect-confirm")).not.toBeInTheDocument();
        expect(disconnectGmailMock).not.toHaveBeenCalled();
    });
});

describe("accessibility & i18n", () => {
    it("renders Arabic RTL consent copy", async () => {
        currentLanguage = "ar";
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, recurring_sync_consent: false }),
        );
        renderCard();
        expect(
            await screen.findByRole("button", {
                name: /مراجعة واعتماد المزامنة المتكررة/,
            }),
        ).toBeInTheDocument();
    });

    it("consent checkbox is keyboard-operable", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, recurring_sync_consent: false }),
        );
        renderCard();
        await userEvent.click(
            await screen.findByRole("button", { name: /Review & approve recurring sync/i }),
        );
        const checkbox = screen.getByRole("checkbox");
        checkbox.focus();
        expect(checkbox).toHaveFocus();
        await userEvent.keyboard(" "); // space toggles a focused checkbox
        expect(checkbox).toBeChecked();
        expect(
            screen.getByRole("button", { name: /Approve recurring sync/i }),
        ).toBeEnabled();
    });
});

describe("no secret leakage", () => {
    it("never renders token/secret material", async () => {
        getGmailStatusMock.mockResolvedValue(
            status({ connected: true, provider_email: "someone@gmail.com" }),
        );
        const { container } = render(
            <GmailConnectionCard palette={palette} notify={vi.fn()} />,
        );
        await screen.findByText(/Connected as someone@gmail.com/i);
        expect(container.innerHTML).not.toMatch(/refresh_token|encrypted|Bearer\s|gAAAAA/i);
    });
});
