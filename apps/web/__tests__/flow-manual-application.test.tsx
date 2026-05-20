import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchApplicationsMock, createManualApplicationMock } = vi.hoisted(() => ({
    fetchApplicationsMock: vi.fn(),
    createManualApplicationMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/components/layout/Navigation", () => ({
    Navigation: () => <nav>Navigation</nav>,
}));

vi.mock("@/components/layout/TopNav", () => ({
    TopNav: () => <header>TopNav</header>,
}));

vi.mock("@/components/ui/AuraGlow", () => ({
    AuraGlow: () => <div />,
}));

vi.mock("@/components/ui/MaterialIcon", () => ({
    MaterialIcon: ({ icon }: { icon: string }) => <span data-icon={icon}>{icon}</span>,
}));

vi.mock("@/lib/api", () => ({
    getApplications: fetchApplicationsMock,
    createManualApplication: createManualApplicationMock,
}));

import FlowPage from "@/app/flow/page";

beforeEach(() => {
    fetchApplicationsMock.mockReset();
    createManualApplicationMock.mockReset();
});

describe("Flow manual application tracking", () => {
    it("renders Track application button", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });

        render(<FlowPage />);

        expect(await screen.findByRole("button", { name: /Track application/i })).toBeInTheDocument();
    });

    it("opens modal when Track application button is clicked", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });

        const user = userEvent.setup();
        render(<FlowPage />);

        await user.click(await screen.findByRole("button", { name: /Track application/i }));

        expect(screen.getByRole("dialog", { name: /Track application/i })).toBeInTheDocument();
        expect(screen.getByLabelText(/Manual application form/i)).toBeInTheDocument();
    });

    it("submits form and calls createManualApplication", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });
        createManualApplicationMock.mockResolvedValue({
            status: "applied",
            job_id: "test-job-123",
            message: "Manual application record created",
        });

        const user = userEvent.setup();
        render(<FlowPage />);

        await user.click(await screen.findByRole("button", { name: /Track application/i }));

        const titleInput = screen.getByLabelText(/Job Title/i);
        await user.type(titleInput, "Senior Manager");

        const companyInput = screen.getByLabelText(/Company/i);
        await user.type(companyInput, "Test Company");

        const locationInput = screen.getByLabelText(/Location/i);
        await user.type(locationInput, "Dubai");

        const urlInput = screen.getByLabelText(/Job URL/i);
        await user.type(urlInput, "https://example.com/job");

        await user.click(screen.getByRole("button", { name: /Save application/i }));

        await waitFor(() => {
            expect(createManualApplicationMock).toHaveBeenCalledWith({
                title: "Senior Manager",
                company: "Test Company",
                location: "Dubai",
                url: "https://example.com/job",
                status: "applied",
            });
        });
    });

    it("refetches applications after successful submission", async () => {
        fetchApplicationsMock
            .mockResolvedValueOnce({ applications: [] })
            .mockResolvedValueOnce({ applications: [{ application_id: "1", title: "Senior Manager", company: "Test Company", status: "applied" }] });
        createManualApplicationMock.mockResolvedValue({
            status: "applied",
            job_id: "test-job-123",
            message: "Manual application record created",
        });

        const user = userEvent.setup();
        render(<FlowPage />);

        await user.click(await screen.findByRole("button", { name: /Track application/i }));

        const titleInput = screen.getByLabelText(/Job Title/i);
        await user.type(titleInput, "Senior Manager");

        const companyInput = screen.getByLabelText(/Company/i);
        await user.type(companyInput, "Test Company");

        const locationInput = screen.getByLabelText(/Location/i);
        await user.type(locationInput, "Dubai");

        await user.click(screen.getByRole("button", { name: /Save application/i }));

        await waitFor(() => {
            expect(fetchApplicationsMock).toHaveBeenCalledTimes(2);
        });
    });

    it("shows error state when submission fails", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });
        createManualApplicationMock.mockRejectedValue(new Error("Failed to create application"));

        const user = userEvent.setup();
        render(<FlowPage />);

        await user.click(await screen.findByRole("button", { name: /Track application/i }));

        const titleInput = screen.getByLabelText(/Job Title/i);
        await user.type(titleInput, "Senior Manager");

        const companyInput = screen.getByLabelText(/Company/i);
        await user.type(companyInput, "Test Company");

        await user.click(screen.getByRole("button", { name: /Save application/i }));

        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent(/Failed to create application/i);
    });
});
