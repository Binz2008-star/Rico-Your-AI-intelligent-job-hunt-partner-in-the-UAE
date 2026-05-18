import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

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
    fetchProfileMock
      .mockResolvedValueOnce({
        profile_exists: true,
        name: "",
        email: "user@example.com",
      })
      .mockResolvedValueOnce({
        profile_exists: true,
        name: "Roben Nihad",
        email: "user@example.com",
      });
    updateProfileMock.mockResolvedValue({
      status: "ok",
      updated_fields: ["name"],
    });

    const user = userEvent.setup();
    render(<ProfilePage />);

    await user.click(await screen.findByRole("button", { name: "Edit" }));

    const input = screen.getByLabelText("Name");
    await user.type(input, "  Roben Nihad  ");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateProfileMock).toHaveBeenCalledWith({ name: "Roben Nihad" });
    });
    await waitFor(() => {
      expect(fetchProfileMock).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText("Roben Nihad")).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });
});
