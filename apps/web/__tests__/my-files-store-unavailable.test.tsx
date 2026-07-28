/**
 * My Files must not tell a user their account is empty when the read failed.
 *
 * `UploadAtelier` is the authenticated "My files" surface. It has four states
 * that a user can tell apart only if the component keeps them apart:
 *
 *   loading            — the read is in flight
 *   loaded-non-empty   — an authoritative read returned documents
 *   loaded-empty       — an authoritative read proved the account holds nothing
 *   unavailable        — the read did not complete, so nothing is known
 *
 * The defect these tests pin: a failed read was rendered as `loaded-empty`,
 * i.e. "No files yet — upload your CV to get started". That is absence
 * guidance derived from no evidence, and it is what makes a user believe an
 * outage deleted their CV. Binding rule (AI_WORKSPACE/ARCHITECTURE.md):
 *
 *     READ FAILURE != VERIFIED ABSENCE.
 *
 * The unavailable state must therefore be visible, truthful in both English
 * and Arabic, retryable, and free of any claim about what the account holds —
 * while Retry re-runs the same read and mutates nothing.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { translations } from "@/lib/translations";

const {
    listUserFilesMock,
    fetchProfileMock,
    uploadCVMock,
    uploadUserFileMock,
    deleteUserFileMock,
    setPrimaryFileMock,
    updateUserFileMock,
} = vi.hoisted(() => ({
    listUserFilesMock: vi.fn(),
    fetchProfileMock: vi.fn(),
    uploadCVMock: vi.fn(),
    uploadUserFileMock: vi.fn(),
    deleteUserFileMock: vi.fn(),
    setPrimaryFileMock: vi.fn(),
    updateUserFileMock: vi.fn(),
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
        uploadCV: uploadCVMock,
        uploadUserFile: uploadUserFileMock,
        deleteUserFile: deleteUserFileMock,
        setPrimaryFile: setPrimaryFileMock,
        updateUserFile: updateUserFileMock,
    };
});

import { ApiError } from "@/lib/api";
import { UploadAtelier } from "@/components/upload/UploadAtelier";

const EN = translations.en;
const AR = translations.ar;

const CV_DOC = {
    id: "doc-1",
    user_id: "u@test",
    filename: "cv.pdf",
    original_filename: "cv.pdf",
    doc_type: "cv" as const,
    file_size: 1024,
    is_primary: true,
    label: null,
    current_role: null,
};

/** The 503 the backend returns when the document store could not be read. */
function unavailableError(): ApiError {
    return new ApiError("We couldn't load your files right now.", 503, {
        detail: { type: "files_unavailable", state: "unavailable", retryable: true },
    });
}

function renderMyFiles() {
    return render(
        <LanguageProvider>
            <UploadAtelier />
        </LanguageProvider>,
    );
}

/** Every mutation the surface can perform. None may fire on a failed read. */
function expectNoMutations() {
    expect(uploadCVMock).not.toHaveBeenCalled();
    expect(uploadUserFileMock).not.toHaveBeenCalled();
    expect(deleteUserFileMock).not.toHaveBeenCalled();
    expect(setPrimaryFileMock).not.toHaveBeenCalled();
    expect(updateUserFileMock).not.toHaveBeenCalled();
}

beforeEach(() => {
    vi.clearAllMocks();
    fetchProfileMock.mockResolvedValue(null);
    localStorage.clear();
});

afterEach(() => {
    localStorage.clear();
});

describe("My Files — unavailable document store", () => {
    it("shows a truthful unavailable state with Retry instead of an empty account", async () => {
        listUserFilesMock.mockRejectedValue(unavailableError());

        renderMyFiles();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent(EN.filesUnavailableTitle);
        expect(
            screen.getByRole("button", { name: new RegExp(EN.retry, "i") }),
        ).toBeInTheDocument();
    });

    it("never renders absence copy or upload-your-first-CV guidance on a failed read", async () => {
        listUserFilesMock.mockRejectedValue(unavailableError());

        renderMyFiles();

        await screen.findByRole("alert");
        expect(screen.queryByText(EN.filesEmpty)).not.toBeInTheDocument();
        expect(screen.queryByText(EN.filesEmptyHint)).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: new RegExp(EN.uploadYourCV, "i") }),
        ).not.toBeInTheDocument();
    });

    it("treats any failed read as unavailable, not as an empty account", async () => {
        // 500/404 are read failures too: neither carries evidence about what the
        // account holds, so neither may become "no files yet".
        for (const status of [500, 404]) {
            listUserFilesMock.mockRejectedValue(new ApiError("boom", status, {}));
            const { unmount } = renderMyFiles();

            await screen.findByRole("alert");
            expect(screen.queryByText(EN.filesEmpty)).not.toBeInTheDocument();

            unmount();
            vi.clearAllMocks();
            fetchProfileMock.mockResolvedValue(null);
        }
    });

    it("is truthful in Arabic and shows no Arabic absence guidance", async () => {
        localStorage.setItem("rico-language", "ar");
        listUserFilesMock.mockRejectedValue(unavailableError());

        renderMyFiles();

        await waitFor(() =>
            expect(screen.getByRole("alert")).toHaveTextContent(AR.filesUnavailableTitle),
        );
        expect(screen.queryByText(AR.filesEmpty)).not.toBeInTheDocument();
        expect(screen.queryByText(AR.filesEmptyHint)).not.toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: new RegExp(AR.retry) }),
        ).toBeInTheDocument();
    });

    it("does not retry on a loop — one failed read stays one read", async () => {
        listUserFilesMock.mockRejectedValue(unavailableError());

        renderMyFiles();

        await screen.findByRole("alert");
        await new Promise((resolve) => setTimeout(resolve, 60));
        expect(listUserFilesMock).toHaveBeenCalledTimes(1);
        expectNoMutations();
    });

    it("Retry re-runs the read only, and recovers when the store comes back", async () => {
        listUserFilesMock.mockRejectedValueOnce(unavailableError());

        renderMyFiles();
        await screen.findByRole("alert");
        expectNoMutations();

        listUserFilesMock.mockResolvedValueOnce({ files: [CV_DOC], total: 1 });
        fireEvent.click(screen.getByRole("button", { name: new RegExp(EN.retry, "i") }));

        await waitFor(() => expect(screen.getByText("cv.pdf")).toBeInTheDocument());
        expect(listUserFilesMock).toHaveBeenCalledTimes(2);
        // Retry is a read. It must not upload, delete, rename or re-prime anything.
        expectNoMutations();
    });
});

describe("My Files — authoritative reads still render as before", () => {
    it("a verified empty account still gets the empty state and its upload CTA", async () => {
        // The positive control: without this, the assertions above could pass
        // simply because the empty state never renders at all.
        listUserFilesMock.mockResolvedValue({ files: [], total: 0 });

        renderMyFiles();

        expect(await screen.findByText(EN.filesEmpty)).toBeInTheDocument();
        expect(screen.getByText(EN.filesEmptyHint)).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: new RegExp(EN.uploadYourCV, "i") }),
        ).toBeInTheDocument();
        // Probed via Retry, which only the unavailable state offers, so these
        // two controls stay independent of the new unavailable copy and are
        // green both before and after the fix.
        expect(
            screen.queryByRole("button", { name: new RegExp(EN.retry, "i") }),
        ).not.toBeInTheDocument();
    });

    it("a non-empty account renders its documents and no unavailable state", async () => {
        listUserFilesMock.mockResolvedValue({ files: [CV_DOC], total: 1 });

        renderMyFiles();

        expect(await screen.findByText("cv.pdf")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: new RegExp(EN.retry, "i") }),
        ).not.toBeInTheDocument();
        expect(screen.queryByText(EN.filesEmpty)).not.toBeInTheDocument();
    });
});
