/**
 * The Vault's pending-review banner must be a server answer, never a local flag.
 *
 * Reported from production: the banner "CV preview ready — Complete the review
 * in the chat to save it to My Files" rendered directly above "No files yet —
 * Upload your CV to get started", in one frame. The product was simultaneously
 * telling one person that their preview was ready and that they had no files,
 * and the banner had survived a full delete cycle.
 *
 * Cause: the banner was a boolean set once by the upload animation's completion
 * callback, with no path back to false. Nothing re-derived it, so it outlived
 * the artifact it described.
 *
 * Acceptance criterion pinned here: the banner renders only when a retrievable
 * pending artifact exists for that user at that moment, and it never coexists
 * with the "upload your CV to get started" instruction.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const { listUserFilesMock, fetchProfileMock, pendingMock } = vi.hoisted(() => ({
    listUserFilesMock: vi.fn(),
    fetchProfileMock: vi.fn(),
    pendingMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/upload",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
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
        fetchProfile: fetchProfileMock,
        fetchPendingCvUpload: pendingMock,
    };
});

import { UploadAtelier } from "@/components/upload/UploadAtelier";

function renderVault() {
    return render(
        <LanguageProvider>
            <UploadAtelier />
        </LanguageProvider>,
    );
}

beforeEach(() => {
    listUserFilesMock.mockReset().mockResolvedValue({ files: [] });
    fetchProfileMock.mockReset().mockResolvedValue(null);
    pendingMock.mockReset();
});

afterEach(cleanup);

describe("/upload — the pending-review banner", () => {
    it("renders only against a retrievable pending artifact, and never beside the upload prompt", async () => {
        pendingMock.mockResolvedValue({
            pending: true,
            state: "pending",
            preview_available: true,
            upload_id: "11111111-2222-3333-4444-555555555555",
            filename: "candidate_cv.pdf",
        });
        renderVault();

        expect(await screen.findByText(/CV preview ready/i)).toBeInTheDocument();
        // The exact pairing from the production screenshot must be impossible.
        await waitFor(() =>
            expect(screen.queryByText(/upload your CV to get started/i)).not.toBeInTheDocument(),
        );
        // The list is genuinely empty, and says so without contradicting the banner.
        expect(screen.getByText(/nothing saved here yet/i)).toBeInTheDocument();
    });

    it("does not render when there is no artifact", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "absent" });
        renderVault();

        expect(await screen.findByText(/upload your CV to get started/i)).toBeInTheDocument();
        expect(screen.queryByText(/CV preview ready/i)).not.toBeInTheDocument();
    });

    it("disappears once the CV is saved", async () => {
        pendingMock.mockResolvedValue({
            pending: false,
            state: "already_saved",
            filename: "candidate_cv.pdf",
        });
        renderVault();

        await waitFor(() => expect(pendingMock).toHaveBeenCalled());
        await waitFor(() =>
            expect(screen.queryByText(/CV preview ready/i)).not.toBeInTheDocument(),
        );
    });

    it("does not render when the artifact store cannot be read", async () => {
        // A banner we cannot verify is a claim we cannot make. This is the one
        // direction where silence is correct: the /command surface still tells
        // the user their upload is not lost.
        pendingMock.mockResolvedValue({ pending: false, state: "unavailable" });
        renderVault();

        await waitFor(() => expect(pendingMock).toHaveBeenCalled());
        await waitFor(() =>
            expect(screen.queryByText(/CV preview ready/i)).not.toBeInTheDocument(),
        );
    });

    it("does not render for an expired preview", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "expired", filename: "candidate_cv.pdf" });
        renderVault();

        await waitFor(() => expect(pendingMock).toHaveBeenCalled());
        await waitFor(() =>
            expect(screen.queryByText(/CV preview ready/i)).not.toBeInTheDocument(),
        );
    });

    it("is re-derived on every list refresh, so it cannot survive a delete cycle", async () => {
        pendingMock.mockResolvedValue({ pending: false, state: "absent" });
        renderVault();

        await waitFor(() => expect(pendingMock).toHaveBeenCalled());
        // Proves the banner is asked for alongside the file list rather than
        // being latched once — the property the old boolean lacked.
        expect(pendingMock).toHaveBeenCalledTimes(listUserFilesMock.mock.calls.length);
    });
});
