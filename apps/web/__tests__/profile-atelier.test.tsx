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

vi.mock("next/navigation", () => ({
    usePathname: () => "/profile",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// Authenticated session so the /profile auth guard allows the page to render.
vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => ({
        user: { user_id: "u@test.com", name: "u", email: "u@test.com" },
        ready: true,
        logout: vi.fn(),
    }),
}));

vi.mock("@/components/layout/AppShell", () => ({
    AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
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

describe("Profile Atelier read portrait", () => {
    it("defaults to the read-only portrait and toggles to the existing inline editor on Edit, then back to Cancel", async () => {
        updateProfileMock.mockResolvedValue({
            status: "ok",
            updated_fields: ["name"],
        });
        fetchProfileMock.mockResolvedValue({
            profile_exists: true,
            name: "Test User",
            email: "user@example.com",
            phone: "+971501234567",
            telegram_username: "testuser",
            visa_status: "Employment Visa",
            notice_period: "1 month",
            current_role: "Engineer",
            current_company: "Test Company",
            linkedin_url: "https://linkedin.com/in/testuser",
            target_roles: ["Engineer", "Manager"],
            preferred_cities: ["Dubai"],
            salary_expectation_aed: 25000,
            minimum_salary_aed: 15000,
            years_experience: 5,
            skills: ["React", "TypeScript"],
        });

        const user = userEvent.setup();
        render(<ProfilePage />);

        // Read portrait is the default view.
        await waitFor(() => expect(fetchProfileMock).toHaveBeenCalled());
        expect(await screen.findByRole("heading", { name: "Test User" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Edit profile" })).toBeInTheDocument();

        // Edit opens the existing production inline editor.
        await user.click(screen.getByRole("button", { name: "Edit profile" }));
        expect(await screen.findByRole("button", { name: "Cancel editing" })).toBeInTheDocument();
        expect(await screen.findByRole("button", { name: "Edit name" })).toBeInTheDocument();

        // Edit an inline field and save.
        await user.click(screen.getByRole("button", { name: "Edit name" }));
        const input = await screen.findByLabelText("Name");
        await user.clear(input);
        await user.type(input, "Updated User");
        await user.click(screen.getByRole("button", { name: /^save$/i }));

        await waitFor(() => {
            expect(updateProfileMock).toHaveBeenCalledWith({ name: "Updated User" });
        });

        // Cancel returns to the read portrait.
        await user.click(screen.getByRole("button", { name: "Cancel editing" }));
        expect(await screen.findByRole("button", { name: "Edit profile" })).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Test User" })).toBeInTheDocument();
    });
});
