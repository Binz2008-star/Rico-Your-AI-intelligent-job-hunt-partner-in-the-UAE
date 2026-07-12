import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "./test-utils";

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
    useRouter: () => ({ push: vi.fn() }),
}));

// Authenticated session so the /profile auth guard allows the page to render.
vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => ({
        user: { user_id: "u@test.com", name: "u", email: "u@test.com" },
        ready: true,
        logout: vi.fn(),
    }),
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

describe("Profile inline edit for identity/contact fields", () => {
    it("saves phone field and refreshes profile", async () => {
        fetchProfileMock
            .mockResolvedValueOnce({
                profile_exists: true,
                email: "user@example.com",
                phone: null,
            })
            .mockResolvedValueOnce({
                profile_exists: true,
                email: "user@example.com",
                phone: "+971501234567",
            });
        updateProfileMock.mockResolvedValue({
            status: "ok",
            updated_fields: ["phone"],
        });

        const user = userEvent.setup();
        render(<ProfilePage />);

        await user.click(await screen.findByRole("button", { name: "Edit profile" }));

        // Find phone field and click edit
        const phoneEditButton = await screen.findByLabelText("Edit phone");
        await user.click(phoneEditButton);

        const phoneInput = screen.getByLabelText("phone");
        await user.clear(phoneInput);
        await user.type(phoneInput, "+971501234567");

        const saveButton = screen.getByRole("button", { name: /^save$/i });
        await user.click(saveButton);

        await waitFor(() => {
            expect(updateProfileMock).toHaveBeenCalledWith({ phone: "+971501234567" });
        });

        await waitFor(() => {
            expect(fetchProfileMock.mock.calls.length).toBeGreaterThanOrEqual(2);
        });
    });

    it("validates minimum salary and saves valid value", async () => {
        fetchProfileMock.mockResolvedValue({
            profile_exists: true,
            email: "user@example.com",
            minimum_salary_aed: null,
            target_roles: ["Engineer"],
            preferred_cities: ["Dubai"],
            salary_expectation_aed: 20000,
        });
        updateProfileMock.mockResolvedValue({
            status: "ok",
            updated_fields: ["minimum_salary_aed"],
        });

        const user = userEvent.setup();
        render(<ProfilePage />);

        await user.click(await screen.findByRole("button", { name: "Edit profile" }));

        const salaryEditButton = await screen.findByLabelText("Edit min-salary");
        await user.click(salaryEditButton);

        const salaryInput = screen.getByLabelText("min-salary");
        await user.type(salaryInput, "15000");

        const saveButton = screen.getByRole("button", { name: /^save$/i });
        await user.click(saveButton);

        await waitFor(() => {
            expect(updateProfileMock).toHaveBeenCalledWith({ minimum_salary_aed: 15000 });
        });
    });

    it("rejects invalid minimum salary (non-numeric)", async () => {
        fetchProfileMock.mockResolvedValue({
            profile_exists: true,
            email: "user@example.com",
            minimum_salary_aed: null,
            target_roles: ["Engineer"],
            preferred_cities: ["Dubai"],
            salary_expectation_aed: 20000,
        });

        const user = userEvent.setup();
        render(<ProfilePage />);

        await user.click(await screen.findByRole("button", { name: "Edit profile" }));

        const salaryEditButton = await screen.findByLabelText("Edit min-salary");
        await user.click(salaryEditButton);

        const salaryInput = screen.getByLabelText("min-salary");
        await user.type(salaryInput, "invalid");

        const saveButton = screen.getByRole("button", { name: /^save$/i });
        await user.click(saveButton);

        await waitFor(() => {
            expect(screen.getByText(/valid salary/i)).toBeInTheDocument();
        });

        expect(updateProfileMock).not.toHaveBeenCalled();
    });

    it("shows an error when phone save fails", async () => {
        fetchProfileMock.mockResolvedValue({
            profile_exists: true,
            email: "user@example.com",
            phone: null,
        });
        updateProfileMock.mockRejectedValue(new Error("Could not save phone."));

        const user = userEvent.setup();
        render(<ProfilePage />);

        await user.click(await screen.findByRole("button", { name: "Edit profile" }));

        await user.click(await screen.findByLabelText("Edit phone"));
        await user.type(screen.getByLabelText("phone"), "+971501234567");
        await user.click(screen.getByRole("button", { name: /^save$/i }));

        expect(await screen.findByText(/could not save phone/i)).toBeInTheDocument();
    });

    it("does not render command edit links for inline editable fields", async () => {
        fetchProfileMock.mockResolvedValue({
            profile_exists: true,
            email: "user@example.com",
            phone: "+971501234567",
            telegram_username: "testuser",
            visa_status: "Employment Visa",
            notice_period: "1 month",
            minimum_salary_aed: 15000,
            current_company: "Test Company",
            linkedin_url: "https://linkedin.com/in/testuser",
        });

        render(<ProfilePage />);

        await screen.findByText("+971501234567");

        const commandLinks = screen
            .queryAllByRole("link")
            .filter((link) => link.getAttribute("href")?.startsWith("/command?prompt="));

        const inlineFieldPrompts = [
            "phone",
            "Telegram",
            "visa",
            "notice",
            "minimum salary",
            "current company",
            "linkedin",
        ];

        expect(
            commandLinks.some((link) =>
                inlineFieldPrompts.some((term) =>
                    link.getAttribute("href")?.toLowerCase().includes(term.toLowerCase())
                )
            )
        ).toBe(false);
    });
});
