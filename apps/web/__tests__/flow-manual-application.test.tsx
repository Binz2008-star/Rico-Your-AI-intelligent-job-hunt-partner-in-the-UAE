import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const { fetchApplicationsMock, createManualApplicationMock, updateApplicationStatusMock } = vi.hoisted(() => ({
    fetchApplicationsMock: vi.fn(),
    createManualApplicationMock: vi.fn(),
    updateApplicationStatusMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    usePathname: () => "/flow",
    useSearchParams: () => new URLSearchParams(),
    redirect: vi.fn(),
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
    updateApplicationStatus: updateApplicationStatusMock,
}));

import FlowPage from "@/app/flow/page";

// FlowPage (and the DashboardShell it renders) read the language from
// LanguageContext, so every render must be wrapped in a LanguageProvider.
function renderFlow() {
    return render(
        <LanguageProvider>
            <FlowPage />
        </LanguageProvider>,
    );
}

beforeEach(() => {
    fetchApplicationsMock.mockReset();
    createManualApplicationMock.mockReset();
    updateApplicationStatusMock.mockReset();
    try {
        localStorage.removeItem("rico-language");
    } catch {
        // ignore
    }
});

afterEach(() => {
    try {
        localStorage.removeItem("rico-language");
    } catch {
        // ignore
    }
});

describe("Flow manual application tracking", () => {
    it("renders Track application button", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });

        renderFlow();

        expect(await screen.findByRole("button", { name: /Track application/i })).toBeInTheDocument();
    });

    it("opens modal when Track application button is clicked", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [] });

        const user = userEvent.setup();
        renderFlow();

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
        renderFlow();

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
        renderFlow();

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
        renderFlow();

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

describe("Flow Arabic / RTL localization", () => {
    beforeEach(() => {
        // LanguageProvider reads this on mount and switches to Arabic.
        localStorage.setItem("rico-language", "ar");
    });

    it("renders the page title and track button in Arabic", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [], total: 0 });

        renderFlow();

        // Title = مسار الطلبات, Track application = تتبع طلب
        expect(await screen.findByText("مسار الطلبات")).toBeInTheDocument();
        expect(
            await screen.findByRole("button", { name: /تتبع طلب/ }),
        ).toBeInTheDocument();
    });

    it("sets the document direction to RTL when Arabic is selected", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [], total: 0 });

        renderFlow();

        await screen.findByText("مسار الطلبات");
        await waitFor(() => {
            expect(document.documentElement.dir).toBe("rtl");
        });
    });

    it("renders the Arabic status label and next-action for an applied card", async () => {
        fetchApplicationsMock.mockResolvedValue({
            applications: [
                {
                    application_id: "1",
                    job_id: "job-1",
                    title: "Specialist, Petroleum Engineering",
                    company: "ADNOC",
                    location: "Dubai",
                    status: "applied",
                },
            ],
            total: 1,
        });

        renderFlow();

        // Applied = تم التقديم (status badge + count strip + dropdown option)
        expect((await screen.findAllByText("تم التقديم")).length).toBeGreaterThan(0);
        // Next-action for applied = follow-up reminder in Arabic
        expect(
            screen.getByText("لم يصلك رد خلال 5–7 أيام؟ أرسل متابعة."),
        ).toBeInTheDocument();
    });

    it("renders the modal labels and save button in Arabic", async () => {
        fetchApplicationsMock.mockResolvedValue({ applications: [], total: 0 });

        const user = userEvent.setup();
        renderFlow();

        await user.click(await screen.findByRole("button", { name: /تتبع طلب/ }));

        // Modal dialog (aria-label) + save button + a localized field label
        expect(screen.getByRole("dialog", { name: "تتبع طلب" })).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "حفظ الطلب" }),
        ).toBeInTheDocument();
        expect(screen.getByLabelText("المسمى الوظيفي *")).toBeInTheDocument();
    });
});
