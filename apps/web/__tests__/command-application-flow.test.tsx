import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { sendChatMock, sendChatPublicMock, pushMock } = vi.hoisted(() => ({
    sendChatMock: vi.fn(),
    sendChatPublicMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api", () => ({
    ApiError: class ApiError extends Error {
        statusCode?: number;
        constructor(message: string, statusCode?: number) {
            super(message);
            this.statusCode = statusCode;
        }
    },
    confirmCVProfile: vi.fn(),
    fetchMe: vi.fn(),
    logout: vi.fn(),
    sendChat: sendChatMock,
    sendChatPublic: sendChatPublicMock,
    uploadCV: vi.fn(),
}));

import CommandPage from "@/app/command/page";

function mockBrowserApis() {
    window.matchMedia = vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
    });
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
}

async function renderJobMatches() {
    sendChatMock.mockResolvedValueOnce({
        message: "Here are some jobs",
        type: "job_matches",
        matches: [
            {
                title: "Senior Engineer",
                company: "Tech Corp",
                location: "Dubai",
                score: 85,
                job_key: "job-123",
                actions: ["Prepare application", "Save", "Mark as applied"],
            },
        ],
    });

    const user = userEvent.setup();
    render(<CommandPage />);

    const input = screen.getByLabelText("Message Rico");
    await user.type(input, "find jobs{enter}");

    await waitFor(() => {
        expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
    });

    return user;
}

beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK", "true");
    sendChatMock.mockReset();
    sendChatPublicMock.mockReset();
    pushMock.mockReset();
    mockBrowserApis();
});

describe("Command page application flow", () => {
    it("sends Prepare application with selected job context", async () => {
        const user = await renderJobMatches();

        await user.click(screen.getByRole("button", { name: "Prepare application" }));

        await waitFor(() => {
            expect(sendChatMock).toHaveBeenLastCalledWith(
                "prepare application for Senior Engineer at Tech Corp",
                expect.any(AbortSignal),
            );
        });
    });

    it("sends Save with selected job context", async () => {
        const user = await renderJobMatches();

        await user.click(screen.getByRole("button", { name: "Save" }));

        await waitFor(() => {
            expect(sendChatMock).toHaveBeenLastCalledWith(
                "save — Senior Engineer at Tech Corp",
                expect.any(AbortSignal),
            );
        });
    });

    it("sends Mark as applied with selected job context", async () => {
        const user = await renderJobMatches();

        await user.click(screen.getByRole("button", { name: "Mark as applied" }));

        await waitFor(() => {
            expect(sendChatMock).toHaveBeenLastCalledWith(
                "mark as applied — Senior Engineer at Tech Corp",
                expect.any(AbortSignal),
            );
        });
    });
});
