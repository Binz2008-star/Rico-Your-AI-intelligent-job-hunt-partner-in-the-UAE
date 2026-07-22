/**
 * ProfileAvatar — profile picture change/remove (owner request 2026-07-21).
 *
 * Pins: initials fallback when no avatar; stored avatar renders as an image;
 * upload routes through uploadAvatar and only switches the preview after the
 * server confirms; remove routes through deleteAvatar; failures surface an
 * inline alert and never fake success.
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders } from "./test-utils";

const { getAvatarMock, uploadAvatarMock, deleteAvatarMock } = vi.hoisted(() => ({
    getAvatarMock: vi.fn(),
    uploadAvatarMock: vi.fn(),
    deleteAvatarMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
    getAvatar: getAvatarMock,
    uploadAvatar: uploadAvatarMock,
    deleteAvatar: deleteAvatarMock,
}));

import { ProfileAvatar } from "@/components/profile/ProfileAvatar";

beforeEach(() => {
    getAvatarMock.mockReset();
    uploadAvatarMock.mockReset();
    deleteAvatarMock.mockReset();
});

describe("ProfileAvatar", () => {
    it("shows the initials fallback when no avatar is stored", async () => {
        getAvatarMock.mockResolvedValue({ avatar: null });
        renderWithProviders(<ProfileAvatar initials="RE" />);
        await waitFor(() => expect(getAvatarMock).toHaveBeenCalled());
        expect(screen.getByText("RE")).toBeInTheDocument();
        expect(screen.queryByTestId("profile-avatar-image")).toBeNull();
        expect(screen.queryByTestId("profile-avatar-remove")).toBeNull();
    });

    it("renders the stored avatar image and the remove control", async () => {
        getAvatarMock.mockResolvedValue({ avatar: "data:image/png;base64,QUJD" });
        renderWithProviders(<ProfileAvatar initials="RE" />);
        const img = await screen.findByTestId("profile-avatar-image");
        expect(img).toHaveAttribute("src", "data:image/png;base64,QUJD");
        expect(screen.getByTestId("profile-avatar-remove")).toBeInTheDocument();
    });

    it("uploads a picked file and switches the preview only on server confirm", async () => {
        getAvatarMock.mockResolvedValue({ avatar: null });
        uploadAvatarMock.mockResolvedValue({ ok: true, avatar: "data:image/jpeg;base64,TkVX" });
        const { container } = renderWithProviders(<ProfileAvatar initials="RE" />);
        await waitFor(() => expect(getAvatarMock).toHaveBeenCalled());

        const input = container.querySelector('input[type="file"]') as HTMLInputElement;
        const file = new File([new Uint8Array([0xff, 0xd8, 0xff, 0x00])], "me.jpg", { type: "image/jpeg" });
        fireEvent.change(input, { target: { files: [file] } });

        await waitFor(() => expect(uploadAvatarMock).toHaveBeenCalledTimes(1));
        const img = await screen.findByTestId("profile-avatar-image");
        expect(img).toHaveAttribute("src", "data:image/jpeg;base64,TkVX");
    });

    it("upload failure keeps the fallback and surfaces an alert — no fake success", async () => {
        getAvatarMock.mockResolvedValue({ avatar: null });
        uploadAvatarMock.mockRejectedValue(new Error("413"));
        const { container } = renderWithProviders(<ProfileAvatar initials="RE" />);
        await waitFor(() => expect(getAvatarMock).toHaveBeenCalled());

        const input = container.querySelector('input[type="file"]') as HTMLInputElement;
        fireEvent.change(input, {
            target: { files: [new File([new Uint8Array([1])], "big.png", { type: "image/png" })] },
        });

        await waitFor(() => expect(uploadAvatarMock).toHaveBeenCalled());
        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.queryByTestId("profile-avatar-image")).toBeNull();
        expect(screen.getByText("RE")).toBeInTheDocument();
    });

    it("remove routes through deleteAvatar and restores the initials", async () => {
        getAvatarMock.mockResolvedValue({ avatar: "data:image/png;base64,QUJD" });
        deleteAvatarMock.mockResolvedValue({ ok: true, deleted: true });
        renderWithProviders(<ProfileAvatar initials="RE" />);
        await screen.findByTestId("profile-avatar-image");

        fireEvent.click(screen.getByTestId("profile-avatar-remove"));
        await waitFor(() => expect(deleteAvatarMock).toHaveBeenCalledTimes(1));
        expect(screen.queryByTestId("profile-avatar-image")).toBeNull();
        expect(screen.getByText("RE")).toBeInTheDocument();
    });
});
