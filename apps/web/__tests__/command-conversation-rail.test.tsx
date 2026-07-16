/**
 * CommandConversationRail — C1 correction contracts.
 *
 *  1. deriveConversationTitle is truthful: fallback when the user hasn't
 *     written, first real user turn otherwise, whitespace-collapsed and capped.
 *  2. No fabricated sessions: exactly one conversation entry, with the live
 *     message count.
 *  3. Real history states: authenticated "pending" → loading row;
 *     historyLoadError → truthful failure note (welcome fallback unchanged).
 *  4. New chat and the two-step Clear-history flow call the page's real
 *     handlers; Clear history is authenticated-only (server truth).
 */

import {
    CommandConversationRail,
    countUserTurns,
    deriveConversationTitle,
    hasRealConversation,
} from "@/components/command/CommandConversationRail";
import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: "en" }),
}));

const msg = (role: "user" | "rico", text: string) => ({ role, text });

const baseProps = {
    audience: "authenticated" as const,
    messages: [msg("rico", "Welcome back."), msg("user", "Find me HSE Manager jobs in Dubai")],
    historyState: "has_history" as const,
    historyLoadError: false,
    busy: false,
    confirmClear: false,
    clearingHistory: false,
    onNewChat: vi.fn(),
    onClearHistory: vi.fn(),
    onCancelClear: vi.fn(),
};

beforeEach(() => {
    baseProps.onNewChat = vi.fn();
    baseProps.onClearHistory = vi.fn();
    baseProps.onCancelClear = vi.fn();
});

describe("deriveConversationTitle", () => {
    it("returns the fallback when no user turn exists", () => {
        expect(deriveConversationTitle([msg("rico", "hi")], "New conversation")).toBe("New conversation");
        expect(deriveConversationTitle([], "fallback")).toBe("fallback");
    });

    it("uses the first real user turn, collapsed and capped", () => {
        expect(deriveConversationTitle([msg("user", "  Find   me\n jobs ")], "x")).toBe("Find me jobs");
        const long = "a".repeat(100);
        const title = deriveConversationTitle([msg("user", long)], "x");
        expect(title.length).toBeLessThanOrEqual(45);
        expect(title.endsWith("…")).toBe(true);
    });
});

describe("CommandConversationRail", () => {
    it("renders exactly one conversation entry with the real title and user-turn count", () => {
        render(<CommandConversationRail {...baseProps} />);
        const current = screen.getAllByTestId("command-rail-current");
        expect(current).toHaveLength(1);
        expect(current[0]).toHaveTextContent("Find me HSE Manager jobs in Dubai");
        // Count = real USER turns only (1), never messages.length (2).
        expect(screen.getByTestId("command-rail-turn-count")).toHaveTextContent("1");
        expect(screen.getByText("1 thread")).toBeInTheDocument();
    });

    /* ── Owner blocker: real-conversation truth model ─────────────────────── */

    it("welcome-only empty history: fallback title, no count, Clear History hidden", () => {
        render(
            <CommandConversationRail
                {...baseProps}
                historyState="empty"
                messages={[msg("rico", "Welcome back. What would you like to work on today?")]}
            />,
        );
        expect(countUserTurns([msg("rico", "welcome")])).toBe(0);
        expect(hasRealConversation([msg("rico", "welcome")], "empty")).toBe(false);
        // Fallback title allowed; the synthetic welcome is NOT a conversation:
        expect(screen.getByTestId("command-rail-current")).toHaveTextContent("New conversation");
        expect(screen.queryByTestId("command-rail-turn-count")).not.toBeInTheDocument();
        expect(screen.queryByTestId("command-rail-clear-history")).not.toBeInTheDocument();
    });

    it("first real user turn after the welcome: title flips, Clear History appears, count excludes the welcome", () => {
        const messages = [
            msg("rico", "Welcome back. What would you like to work on today?"),
            msg("user", "Find me HSE jobs in Abu Dhabi"),
        ];
        expect(hasRealConversation(messages, "empty")).toBe(true);
        render(<CommandConversationRail {...baseProps} historyState="empty" messages={messages} />);
        expect(screen.getByTestId("command-rail-current")).toHaveTextContent("Find me HSE jobs in Abu Dhabi");
        expect(screen.getByTestId("command-rail-turn-count")).toHaveTextContent("1"); // welcome excluded
        expect(screen.getByTestId("command-rail-clear-history")).toBeInTheDocument();
    });

    it("persisted server history: real conversation, rail reflects it, Clear History appears", () => {
        const messages = [
            msg("user", "Find me HSE Manager jobs in Dubai"),
            msg("rico", "Here are your top three."),
            msg("user", "Tailor my CV for the first one"),
        ];
        expect(hasRealConversation(messages, "has_history")).toBe(true);
        render(<CommandConversationRail {...baseProps} historyState="has_history" messages={messages} />);
        expect(screen.getByTestId("command-rail-current")).toHaveTextContent("Find me HSE Manager jobs in Dubai");
        expect(screen.getByTestId("command-rail-turn-count")).toHaveTextContent("2");
        expect(screen.getByTestId("command-rail-clear-history")).toBeInTheDocument();
    });

    it("shows the loading row while authenticated history is pending", () => {
        render(<CommandConversationRail {...baseProps} historyState="pending" messages={[]} />);
        expect(screen.getByTestId("command-rail-history-loading")).toBeInTheDocument();
        expect(screen.queryByTestId("command-rail-current")).not.toBeInTheDocument();
    });

    it("surfaces the real history-load failure note", () => {
        render(<CommandConversationRail {...baseProps} historyLoadError />);
        expect(screen.getByTestId("command-rail-history-error")).toHaveTextContent(/couldn't load saved history/i);
    });

    it("+ new calls the page's real New-chat handler and disables while busy", () => {
        const { rerender } = render(<CommandConversationRail {...baseProps} />);
        fireEvent.click(screen.getByTestId("command-rail-new-chat"));
        expect(baseProps.onNewChat).toHaveBeenCalledTimes(1);
        rerender(<CommandConversationRail {...baseProps} busy />);
        expect(screen.getByTestId("command-rail-new-chat")).toBeDisabled();
    });

    it("Clear history is two-step and wired to the real handlers", () => {
        const { rerender } = render(<CommandConversationRail {...baseProps} />);
        fireEvent.click(screen.getByTestId("command-rail-clear-history"));
        expect(baseProps.onClearHistory).toHaveBeenCalledTimes(1); // arms confirm in the page

        rerender(<CommandConversationRail {...baseProps} confirmClear />);
        fireEvent.click(screen.getByTestId("command-rail-clear-confirm"));
        expect(baseProps.onClearHistory).toHaveBeenCalledTimes(2); // second call performs the clear
        fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
        expect(baseProps.onCancelClear).toHaveBeenCalledTimes(1);
    });

    it("public audience gets no Clear-history control (server-history is authenticated-only)", () => {
        render(<CommandConversationRail {...baseProps} audience="public" />);
        expect(screen.queryByTestId("command-rail-clear-history")).not.toBeInTheDocument();
    });
});
