/**
 * /profile is the third CV upload entry point, and it must obey the same
 * contract as Command and Vault.
 *
 * It previously called uploadCV, announced "CV uploaded — Rico is reading it",
 * reloaded the file list and refreshed the profile — all before confirmation
 * had created any document. The success message was therefore issued for an
 * outcome the upload response cannot know, and the list it reloaded was still
 * empty. Three entry points, one state machine: an upload is not a save on any
 * of them, and only the server's pending answer may claim otherwise.
 */
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const {
    listUserFilesMock,
    pendingMock,
    uploadCVMock,
    getMySubscriptionMock,
} = vi.hoisted(() => ({
    listUserFilesMock: vi.fn(),
    pendingMock: vi.fn(),
    uploadCVMock: vi.fn(),
    getMySubscriptionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/profile",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    // The documents section is a rail tab; the CV upload control only exists
    // when it is the active one.
    useSearchParams: () => new URLSearchParams("section=documents"),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

vi.mock("@/lib/api", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    return {
        ...actual,
        listUserFiles: listUserFilesMock,
        fetchPendingCvUpload: pendingMock,
        uploadCV: uploadCVMock,
        getMySubscription: getMySubscriptionMock,
    };
});

import { ProfileEditorial } from "@/components/profile/ProfileEditorial";

const PROFILE = {
    user_id: "u@x.com",
    name: "Test User",
    email: "u@x.com",
    target_roles: [],
    preferred_cities: [],
    skills: [],
} as never;

const notify = vi.fn();
const refresh = vi.fn();

function renderProfile() {
    return render(
        <LanguageProvider>
            <ProfileEditorial profile={PROFILE} refresh={refresh} notify={notify} />
        </LanguageProvider>,
    );
}

/** The input is `display:none` and driven by a button, so userEvent refuses to
 *  interact with it. fireEvent.change dispatches the same event the component's
 *  onChange handler listens for. */
async function uploadAFile() {
    // The page has more than one file input (the avatar picker is the other),
    // so target the CV one by its accessible name rather than by position.
    const input = screen.getByLabelText("Upload CV") as HTMLInputElement;
    expect(input).not.toBeNull();
    const file = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    await act(async () => {
        fireEvent.change(input as HTMLInputElement);
    });
}

beforeEach(() => {
    listUserFilesMock.mockReset().mockResolvedValue({ files: [] });
    pendingMock.mockReset().mockResolvedValue({ pending: false, state: "absent" });
    uploadCVMock.mockReset().mockResolvedValue({ ok: true, status: "preview_ready" });
    getMySubscriptionMock.mockReset().mockResolvedValue(null);
    notify.mockReset();
    refresh.mockReset();
});

afterEach(cleanup);

describe("/profile — an upload is not a save", () => {
    it("never claims the CV is saved while it is only pending review", async () => {
        pendingMock.mockResolvedValue({
            pending: true,
            state: "pending",
            preview_available: true,
            upload_id: "11111111-2222-3333-4444-555555555555",
            filename: "cv.pdf",
        });
        renderProfile();
        await waitFor(() => expect(listUserFilesMock).toHaveBeenCalled());

        await uploadAFile();

        await waitFor(() => expect(notify).toHaveBeenCalled());
        const messages = notify.mock.calls.map(([m]) => String(m)).join(" | ");
        // The old copy asserted an outcome the upload response cannot know.
        expect(messages).not.toMatch(/Rico is reading it/i);
        expect(messages).toMatch(/confirm it to save it/i);
        expect(messages).toMatch(/nothing is stored yet/i);
        // The profile must not be refreshed for CV-derived facts that no
        // confirmed document can yet support.
        expect(refresh).not.toHaveBeenCalled();
    });

    it("shows the review-required banner and the step that actually saves it", async () => {
        pendingMock.mockResolvedValue({
            pending: true,
            state: "pending",
            preview_available: true,
            upload_id: "11111111-2222-3333-4444-555555555555",
            filename: "cv.pdf",
        });
        renderProfile();

        expect(await screen.findByText(/CV under review — not saved yet/i)).toBeInTheDocument();
        const action = screen.getByRole("link", { name: /review and save it/i });
        expect(action).toHaveAttribute("href", "/command?cv=ready");
        // …and the empty list stops telling them to upload a CV they uploaded.
        expect(screen.queryByText(/upload your CV so Rico can tailor matches/i)).not.toBeInTheDocument();
        expect(screen.getByText(/waiting for your confirmation/i)).toBeInTheDocument();
    });

    it("does not draw the banner when nothing is pending", async () => {
        renderProfile();
        await waitFor(() => expect(pendingMock).toHaveBeenCalled());
        await waitFor(() =>
            expect(screen.queryByText(/CV under review/i)).not.toBeInTheDocument(),
        );
        expect(screen.getByText(/upload your CV so Rico can tailor matches/i)).toBeInTheDocument();
    });

    it("reports a genuine save as a save, and only then refreshes the profile", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "already_saved", filename: "cv.pdf" });
        renderProfile();
        await waitFor(() => expect(listUserFilesMock).toHaveBeenCalled());

        await uploadAFile();

        await waitFor(() => expect(refresh).toHaveBeenCalled());
        const messages = notify.mock.calls.map(([m]) => String(m)).join(" | ");
        expect(messages).toMatch(/CV uploaded/i);
    });

    it("never reports success when no confirmable artifact survived the upload", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "absent" });
        renderProfile();
        await waitFor(() => expect(listUserFilesMock).toHaveBeenCalled());

        await uploadAFile();

        await waitFor(() => expect(notify).toHaveBeenCalled());
        const errorCalls = notify.mock.calls.filter(([, kind]) => kind === "error");
        expect(errorCalls.length).toBeGreaterThan(0);
        expect(refresh).not.toHaveBeenCalled();
    });

    it("never says the upload is gone when the store could not be read", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "unavailable" });
        renderProfile();
        await waitFor(() => expect(listUserFilesMock).toHaveBeenCalled());

        await uploadAFile();

        await waitFor(() => expect(notify).toHaveBeenCalled());
        const messages = notify.mock.calls.map(([m]) => String(m)).join(" | ");
        expect(messages).toMatch(/has not been lost/i);
    });
});
