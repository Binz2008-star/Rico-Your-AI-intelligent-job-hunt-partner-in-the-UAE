import QueuePage from "@/app/queue/page";
import { QueueAtelier } from "@/components/queue/QueueAtelier";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
    getApplicationQueue: vi.fn(),
    getFollowUpReminders: vi.fn(),
    approveApplication: vi.fn(),
    rejectApplication: vi.fn(),
}));

const auth = vi.hoisted((): {
    value: { user: { email: string } | null; authorized: boolean };
} => ({
    value: { user: { email: "owner@example.com" }, authorized: true },
}));

const translate = vi.hoisted(() => (key: string) => key);

vi.mock("@/lib/api", () => ({ ...api }));

vi.mock("@/hooks/useRequireAuth", () => ({
    useRequireAuth: () => auth.value,
}));

vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: "en" }),
}));

vi.mock("@/lib/translations", () => ({
    useTranslation: () => translate,
}));

vi.mock("@/components/workspace/theme", () => ({
    useWorkspaceTheme: () => ({
        bg: "#F1EADD",
        panel: "#F7F1E6",
        rail: "#EDE5D6",
        inset: "#EAE1D0",
        ink: "#1F1B15",
        ink70: "rgba(31,27,21,0.70)",
        ink55: "rgba(31,27,21,0.52)",
        ink40: "rgba(31,27,21,0.38)",
        hair: "rgba(31,27,21,0.16)",
        activeBg: "rgba(31,27,21,0.06)",
        track: "rgba(31,27,21,0.10)",
        red: "#C6492E",
    }),
}));

vi.mock("@/components/workspace/WorkspaceShell", () => ({
    WorkspaceShell: ({ children }: { children: React.ReactNode }) => <div data-testid="workspace-shell">{children}</div>,
}));

vi.mock("@/components/auth/AuthGate", () => ({
    AuthGate: () => <div data-testid="auth-gate">checking</div>,
}));

vi.mock("@/components/queue/ApplicationDraftCard", () => ({
    ApplicationDraftCard: ({ draft }: { draft: { id: string; job_title: string } }) => (
        <article data-testid={`draft-${draft.id}`}>{draft.job_title}</article>
    ),
}));

vi.mock("@/components/ui/MaterialIcon", () => ({
    MaterialIcon: ({ icon }: { icon: string }) => <span aria-hidden="true">{icon}</span>,
}));

vi.mock("@/components/atelier-kit/primitives", () => ({
    Mono: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/atelier-kit/tokens", () => ({
    ATELIER_FONT: { body: "sans-serif", serif: "serif" },
}));

const draft = {
    id: "draft-1",
    job_title: "QHSE Manager",
    company: "Example Co",
    cover_letter: "Cover letter",
    tailored_cv: "Tailored CV",
    apply_url: "https://example.com/job",
};

describe("/queue Atelier migration", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        auth.value = { user: { email: "owner@example.com" }, authorized: true };
        api.getApplicationQueue.mockResolvedValue([]);
        api.getFollowUpReminders.mockResolvedValue([]);
    });

    it("never renders the private WorkspaceShell before authorization", () => {
        auth.value = { user: null, authorized: false };
        render(<QueuePage />);
        expect(screen.getByTestId("auth-gate")).toBeInTheDocument();
        expect(screen.queryByTestId("workspace-shell")).toBeNull();
    });

    it("renders the authenticated page inside WorkspaceShell", () => {
        render(<QueuePage />);
        expect(screen.getByTestId("workspace-shell")).toBeInTheDocument();
    });

    it("shows the Atelier empty state after loading", async () => {
        render(<QueueAtelier />);
        expect(await screen.findByText("queueEmptyTitle")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /queueAskRico/ })).toHaveAttribute("href", "/command");
    });

    it("renders queued drafts and follow-up reminders", async () => {
        api.getApplicationQueue.mockResolvedValue([draft]);
        api.getFollowUpReminders.mockResolvedValue([{ ...draft, id: "follow-1" }]);
        render(<QueueAtelier />);
        expect(await screen.findByTestId("draft-draft-1")).toBeInTheDocument();
        expect(screen.getByText("queueFollowUpDue")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /queueSendFollowUp/ })).toHaveAttribute("href", draft.apply_url);
    });

    it("shows an error and retries without reloading the window", async () => {
        api.getApplicationQueue.mockRejectedValueOnce(new Error("network"));
        render(<QueueAtelier />);
        expect(await screen.findByText("queueErrLoad")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "queueRetry" }));
        await waitFor(() => expect(api.getApplicationQueue).toHaveBeenCalledTimes(2));
    });

    it("uses the private queue APIs only after the authorized content mounts", async () => {
        auth.value = { user: null, authorized: false };
        const { rerender } = render(<QueuePage />);
        expect(api.getApplicationQueue).not.toHaveBeenCalled();
        auth.value = { user: { email: "owner@example.com" }, authorized: true };
        rerender(<QueuePage />);
        await waitFor(() => expect(api.getApplicationQueue).toHaveBeenCalledTimes(1));
    });
});
