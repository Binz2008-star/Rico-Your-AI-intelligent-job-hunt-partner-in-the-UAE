/**
 * apps/web/__tests__/chat-action-card.test.tsx
 *
 * CAREER-OS-02: Unit tests for ChatActionsRow / ChatActionCard component.
 *
 * Verifies:
 * - navigate and chat_continue actions are interactive.
 * - open_drawer, high-impact, requires_confirmation, and unknown kinds are disabled.
 * - Empty actions list renders nothing.
 * - disabled prop suppresses all interactions.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
    default: ({
        children,
        href,
        ...props
    }: { children: React.ReactNode; href: string } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

import { ChatActionsRow } from "@/components/ui/rico/ChatActionCard";
import type { RicoChatAction } from "@/lib/schemas";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function navigateAction(overrides: Partial<RicoChatAction> = {}): RicoChatAction {
    return {
        id: "nav-1",
        label: "View jobs",
        kind: "navigate",
        impact: "low",
        requires_confirmation: false,
        href: "/jobs",
        payload: {},
        ...overrides,
    };
}

function chatContinueAction(overrides: Partial<RicoChatAction> = {}): RicoChatAction {
    return {
        id: "cc-1",
        label: "Find jobs",
        kind: "chat_continue",
        impact: "low",
        requires_confirmation: false,
        payload: { message: "Find UAE jobs that match my CV" },
        ...overrides,
    };
}

function openDrawerAction(): RicoChatAction {
    return {
        id: "od-1",
        label: "Preview",
        kind: "open_drawer",
        impact: "low",
        requires_confirmation: false,
        payload: {},
    };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ChatActionsRow", () => {
    it("renders nothing when actions array is empty", () => {
        const { container } = render(
            <ChatActionsRow actions={[]} onChatContinue={vi.fn()} />,
        );
        expect(container).toBeEmptyDOMElement();
    });

    it("renders the actions row wrapper when actions exist", () => {
        render(
            <ChatActionsRow actions={[navigateAction()]} onChatContinue={vi.fn()} />,
        );
        expect(screen.getByTestId("chat-actions-row")).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Suggested actions" })).toBeInTheDocument();
    });
});

describe("navigate action", () => {
    it("renders an internal href as an anchor link", () => {
        render(
            <ChatActionsRow actions={[navigateAction()]} onChatContinue={vi.fn()} />,
        );
        const link = screen.getByTestId("action-card-navigate");
        expect(link).toBeInTheDocument();
        expect(link).toHaveAttribute("href", "/jobs");
        expect(link.tagName).toBe("A");
    });

    it("adds target=_blank for external hrefs", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction({ href: "https://example.com/jobs" })]}
                onChatContinue={vi.fn()}
            />,
        );
        const link = screen.getByTestId("action-card-navigate");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
    });

    it("renders disabled when href is absent", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction({ href: undefined })]}
                onChatContinue={vi.fn()}
            />,
        );
        const btn = screen.getByTestId("action-card-disabled");
        expect(btn).toBeDisabled();
    });

    it("renders disabled when href is an unsafe scheme", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction({ href: "javascript:alert(1)" })]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });
});

describe("chat_continue action", () => {
    it("calls onChatContinue with payload.message when clicked", async () => {
        const user = userEvent.setup();
        const handler = vi.fn();
        render(
            <ChatActionsRow
                actions={[chatContinueAction()]}
                onChatContinue={handler}
            />,
        );
        await user.click(screen.getByTestId("action-card-chat-continue"));
        expect(handler).toHaveBeenCalledOnce();
        expect(handler).toHaveBeenCalledWith("Find UAE jobs that match my CV");
    });

    it("falls back to action.label when payload.message is absent", async () => {
        const user = userEvent.setup();
        const handler = vi.fn();
        render(
            <ChatActionsRow
                actions={[chatContinueAction({ payload: {} })]}
                onChatContinue={handler}
            />,
        );
        await user.click(screen.getByTestId("action-card-chat-continue"));
        expect(handler).toHaveBeenCalledWith("Find jobs");
    });
});

describe("disabled kinds", () => {
    it("open_drawer renders as disabled button", () => {
        render(
            <ChatActionsRow actions={[openDrawerAction()]} onChatContinue={vi.fn()} />,
        );
        const btn = screen.getByTestId("action-card-disabled");
        expect(btn).toBeDisabled();
        expect(btn).toHaveAttribute("title", "Coming soon");
    });

    it("high-impact navigate is disabled even with valid href", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction({ impact: "high" })]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });

    it("requires_confirmation chat_continue is disabled", () => {
        render(
            <ChatActionsRow
                actions={[chatContinueAction({ requires_confirmation: true })]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });

    it("approve kind renders disabled", () => {
        render(
            <ChatActionsRow
                actions={[
                    {
                        id: "approve-1",
                        label: "Approve",
                        kind: "approve",
                        impact: "high",
                        requires_confirmation: true,
                        payload: {},
                    },
                ]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });

    it("cancel kind renders disabled", () => {
        render(
            <ChatActionsRow
                actions={[
                    {
                        id: "cancel-1",
                        label: "Cancel",
                        kind: "cancel",
                        impact: "low",
                        requires_confirmation: false,
                        payload: {},
                    },
                ]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });

    it("submit kind renders disabled", () => {
        render(
            <ChatActionsRow
                actions={[
                    {
                        id: "submit-1",
                        label: "Save search",
                        kind: "submit",
                        impact: "low",
                        requires_confirmation: false,
                        payload: {},
                    },
                ]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
    });
});

describe("disabled prop", () => {
    it("disables a normally-interactive navigate action", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction()]}
                onChatContinue={vi.fn()}
                disabled
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
        expect(screen.queryByTestId("action-card-navigate")).not.toBeInTheDocument();
    });

    it("disables a normally-interactive chat_continue action", async () => {
        const handler = vi.fn();
        render(
            <ChatActionsRow
                actions={[chatContinueAction()]}
                onChatContinue={handler}
                disabled
            />,
        );
        expect(screen.getByTestId("action-card-disabled")).toBeDisabled();
        expect(screen.queryByTestId("action-card-chat-continue")).not.toBeInTheDocument();
        expect(handler).not.toHaveBeenCalled();
    });
});

describe("multiple actions", () => {
    it("renders all actions in the row", () => {
        render(
            <ChatActionsRow
                actions={[navigateAction(), chatContinueAction(), openDrawerAction()]}
                onChatContinue={vi.fn()}
            />,
        );
        expect(screen.getByTestId("action-card-navigate")).toBeInTheDocument();
        expect(screen.getByTestId("action-card-chat-continue")).toBeInTheDocument();
        expect(screen.getByTestId("action-card-disabled")).toBeInTheDocument();
        expect(screen.getByText("View jobs")).toBeInTheDocument();
        expect(screen.getByText("Find jobs")).toBeInTheDocument();
        expect(screen.getByText("Preview")).toBeInTheDocument();
    });
});
