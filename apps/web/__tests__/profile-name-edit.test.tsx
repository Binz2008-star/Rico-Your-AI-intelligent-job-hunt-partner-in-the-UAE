import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchProfileMock, updateProfileMock } = vi.hoisted(() => ({
    fetchProfileMock: vi.fn(),
    updateProfileMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/components/DashboardShell", () => ({
    DashboardShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/StatusCard", () => ({
    StatusCard: ({ title, children }: { title: string; children: ReactNode }) => (
        <section>
            <h2>{title}</h2>
            {children}
        </section>
    ),
}));

vi.mock("@/components/shared/EmptyState", () => ({
    EmptyState: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock("@/components/shared/ErrorState", () => ({
    ErrorState: ({ variant, onRetry }: { variant: string; onRetry: () => void }) => (
        <button type="button" onClick={onRetry}>
            {variant}
        </button>
    ),
}));

vi.mock("@/components/shared/LoadingState", () => ({
    LoadingState: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock("@/lib/api", () => ({
    fetchProfile: fetchProfileMock,
    updateProfile: updateProfileMock,
}));

import ProfilePage from "@/app/profile/page";

beforeEach(() => {
    fetchProfileMock.mockReset();
    updateProfileMock.mockReset();
});

describe("Profile name inline edit", () => {
    it("saves name directly without routing through chat and refreshes the profile view", async () => {
        // fetchProfile has several callers on this page (the page's own mount
        // load, the save refresh, and the sidebar-readiness hook), so model it as
        // returning current server state rather than positional once-values: the
        // name is empty until the save persists it, then reflects the saved value.
        updateProfileMock.mockResolvedValue({
            status: "ok",
            updated_fields: ["name"],
        });
        fetchProfileMock.mockImplementation(async () => ({
            profile_exists: true,
            name: updateProfileMock.mock.calls.length > 0 ? "Roben Nihad" : "",
            email: "user@example.com",
        }));

        const user = userEvent.setup();
        render(<ProfilePage />);

        await user.click(await screen.findByRole("button", { name: "Edit name" }));

        const input = await screen.findByLabelText("Name");
        // The edit field seeds its draft from the current profile name, so clear
        // any pre-filled value before typing — otherwise userEvent.type appends
        // and produces a doubled name.
        await user.clear(input);
        await user.type(input, "  Roben Nihad  ");

        // fetchProfile is also called by the sidebar-readiness hook
        // (useSidebarStatus), so assert the save triggers a *fresh* refresh
        // relative to the count before saving rather than a brittle global total.
        const fetchCallsBeforeSave = fetchProfileMock.mock.calls.length;
        await user.click(screen.getByRole("button", { name: /^save$/i }));

        await waitFor(() => {
            expect(updateProfileMock).toHaveBeenCalledWith({ name: "Roben Nihad" });
        });
        await waitFor(() => {
            expect(fetchProfileMock.mock.calls.length).toBeGreaterThan(fetchCallsBeforeSave);
        });
        // The saved name surfaces in more than one place (profile header + the
        // inline field), so assert at least one occurrence renders.
        expect((await screen.findAllByText("Roben Nihad")).length).toBeGreaterThan(0);
        expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    });
});
