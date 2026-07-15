/**
 * CommandStates + card atelier branches — slice 4c tests
 *
 * Covers:
 *  1.  CommandWorkingState: public keeps rico-thinking-row verbatim; Atelier
 *      renders the shimmer state with the mark and an accessible status.
 *  2.  AtelierStreamCaret renders the sun-red caret.
 *  3.  CommandOptionChips: public keeps gold classes; Atelier chips fire
 *      their callbacks; sm size used by role-confirmation.
 *  4.  CommandRetryButton: both surfaces keep aria-label + disabled contract.
 *  5.  CommandRateLimitNotice: both surfaces render children.
 *  6.  CommandSlowBanner: the e2e-pinned visible/invisible class contract
 *      holds on BOTH surfaces; testid preserved.
 *  7.  ChatActionsRow atelier: enabled chip carries Atelier presentation and
 *      still fires onChatContinue; disabled reason contract preserved.
 *  8.  PermissionRequestCard atelier: approve flow still calls onApprove;
 *      testids preserved.
 *  9.  AttachmentAnalysisCard atelier: testid + content preserved.
 * 10.  ProposedChangeCard atelier: save flow still calls onSubmit.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import {
    AtelierStreamCaret,
    CommandOptionChips,
    CommandRateLimitNotice,
    CommandRetryButton,
    CommandSlowBanner,
    CommandWorkingState,
} from "@/components/command/CommandStates";
import { AttachmentAnalysisCard } from "@/components/ui/rico/AttachmentAnalysisCard";
import { ChatActionsRow } from "@/components/ui/rico/ChatActionCard";
import { PermissionRequestCard } from "@/components/ui/rico/PermissionRequestCard";
import { ProposedChangeCard } from "@/components/ui/rico/ProposedChangeCard";
import type { RicoChatAction, RicoPermissionRequest } from "@/lib/schemas";

vi.mock("next/link", () => ({
    default: ({ href, children, ...rest }: { href: string; children: React.ReactNode;[k: string]: unknown }) => (
        <a href={href} {...rest}>{children}</a>
    ),
}));

describe("CommandWorkingState", () => {
    it("public surface keeps the legacy thinking row", () => {
        const { container } = render(<CommandWorkingState atelier={false} message="Working" />);
        expect(container.querySelector(".rico-thinking-row")).not.toBeNull();
        expect(container.querySelector(".rico-orb")).not.toBeNull();
        expect(screen.queryByTestId("atelier-working-state")).toBeNull();
    });

    it("Atelier surface renders mark + shimmer with accessible status", () => {
        const { container } = render(<CommandWorkingState atelier message="Searching jobs" />);
        const state = screen.getByTestId("atelier-working-state");
        expect(state.getAttribute("role")).toBe("status");
        expect(state.getAttribute("aria-label")).toBe("Searching jobs");
        expect(screen.getByTestId("atelier-rico-mark")).toBeTruthy();
        expect(container.querySelector(".atl4c-shimmer")?.textContent).toBe("Searching jobs");
        expect(container.querySelector(".rico-thinking-row")).toBeNull();
    });
});

describe("AtelierStreamCaret", () => {
    it("renders the caret", () => {
        render(<AtelierStreamCaret />);
        const caret = screen.getByTestId("atelier-stream-caret");
        expect(caret.getAttribute("aria-hidden")).toBe("true");
        expect(caret.style.background).toBeTruthy();
    });
});

describe("CommandOptionChips", () => {
    const options = [
        { key: "a", label: "Yes, this role", onClick: vi.fn() },
        { key: "b", label: "No, search anyway", onClick: vi.fn() },
    ];

    it("public surface keeps the gold chip classes", () => {
        const { container } = render(<CommandOptionChips atelier={false} options={options} />);
        expect(container.querySelector(".border-gold\\/30")).not.toBeNull();
        expect(screen.queryByTestId("atelier-option-chips")).toBeNull();
    });

    it("Atelier chips fire their callbacks", async () => {
        const user = userEvent.setup();
        render(<CommandOptionChips atelier options={options} size="sm" />);
        expect(screen.getByTestId("atelier-option-chips")).toBeTruthy();
        await user.click(screen.getByText("Yes, this role"));
        expect(options[0].onClick).toHaveBeenCalledTimes(1);
    });
});

describe("CommandRetryButton", () => {
    it("keeps aria-label and disabled contract on both surfaces", () => {
        const onClick = vi.fn();
        const { rerender } = render(
            <CommandRetryButton atelier={false} onClick={onClick} disabled={false} label="Retry" icon={<svg />} />,
        );
        expect(screen.getByLabelText("Retry")).toBeTruthy();
        rerender(
            <CommandRetryButton atelier onClick={onClick} disabled label="Retry" icon={<svg />} />,
        );
        const btn = screen.getByTestId("atelier-retry-button") as HTMLButtonElement;
        expect(btn.disabled).toBe(true);
        expect(btn.getAttribute("aria-label")).toBe("Retry");
    });
});

describe("CommandRateLimitNotice", () => {
    it("renders children on both surfaces", () => {
        const { rerender } = render(
            <CommandRateLimitNotice atelier={false}><span>limited</span></CommandRateLimitNotice>,
        );
        expect(screen.getByText("limited")).toBeTruthy();
        rerender(<CommandRateLimitNotice atelier><span>limited</span></CommandRateLimitNotice>);
        expect(screen.getByTestId("atelier-rate-limit-notice")).toBeTruthy();
        expect(screen.getByText("limited")).toBeTruthy();
    });
});

describe("CommandSlowBanner", () => {
    it.each([false, true])("keeps the e2e visible/invisible class contract (atelier=%s)", (atelier) => {
        const { rerender } = render(
            <CommandSlowBanner atelier={atelier} shown={false} label="Waking up" />,
        );
        const banner = screen.getByTestId("command-slow-banner");
        expect(banner.className).toContain("invisible");
        expect(banner.getAttribute("aria-hidden")).toBe("true");
        rerender(<CommandSlowBanner atelier={atelier} shown label="Waking up" />);
        expect(banner.className).toMatch(/(^|\s)visible(\s|$)/);
        expect(banner.getAttribute("aria-hidden")).toBe("false");
    });
});

describe("ChatActionsRow — atelier", () => {
    const actions: RicoChatAction[] = [
        {
            id: "a1",
            label: "Find similar jobs",
            kind: "chat_continue",
            impact: "low",
            requires_confirmation: false,
            payload: { message: "Find similar jobs" },
        },
        {
            id: "a2",
            label: "Apply now",
            kind: "approve",
            impact: "high",
            requires_confirmation: true,
            payload: {},
        },
    ];

    it("enabled chip fires onChatContinue; gated action keeps disabled-reason contract", async () => {
        const user = userEvent.setup();
        const onChatContinue = vi.fn();
        render(<ChatActionsRow actions={actions} onChatContinue={onChatContinue} atelier />);
        const chip = screen.getByTestId("action-card-chat-continue");
        expect(chip.className).toContain("atl4c-action");
        await user.click(chip);
        expect(onChatContinue).toHaveBeenCalledWith("Find similar jobs");
        const gated = screen.getByTestId("action-card-disabled") as HTMLButtonElement;
        expect(gated.disabled).toBe(true);
        expect(gated.getAttribute("data-disabled-reason")).toContain("permission card");
    });
});

describe("PermissionRequestCard — atelier", () => {
    const request: RicoPermissionRequest = {
        id: "perm-1",
        title: "Apply to QHSE Manager",
        summary: "Rico will submit your application.",
        risk_level: "high",
        data_used: ["Your CV"],
        effects: ["Application marked as applied"],
        approve_action: {
            id: "ap-1", label: "Apply now", kind: "approve", impact: "high",
            requires_confirmation: false, payload: {},
        },
        cancel_action: {
            id: "ca-1", label: "Cancel", kind: "cancel", impact: "low",
            requires_confirmation: false, payload: {},
        },
    };

    it("approve flow still calls onApprove with the approve action", async () => {
        const user = userEvent.setup();
        const onApprove = vi.fn().mockResolvedValue(undefined);
        render(
            <PermissionRequestCard request={request} onApprove={onApprove} onCancel={vi.fn()} atelier />,
        );
        expect(screen.getByTestId("permission-request-card")).toBeTruthy();
        expect(screen.getByTestId("risk-badge").textContent).toBe("High risk");
        await user.click(screen.getByTestId("permission-approve-btn"));
        await waitFor(() => expect(onApprove).toHaveBeenCalledWith(request.approve_action));
    });
});

describe("AttachmentAnalysisCard — atelier", () => {
    it("renders purpose, confidence, and warnings", () => {
        render(
            <AttachmentAnalysisCard
                atelier
                analyses={[{
                    id: "att-1",
                    purpose: "application_evidence",
                    confidence: 0.9,
                    filename: "confirmation.png",
                    extracted_summary: "Your application was sent.",
                    warnings: ["Screenshot only — verify in your email"],
                }] as never}
            />,
        );
        const card = screen.getByTestId("attachment-analysis-card");
        expect(card).toBeTruthy();
        expect(screen.getByText("Application Confirmation")).toBeTruthy();
        expect(screen.getByText("90% confidence")).toBeTruthy();
        expect(screen.getByText("Screenshot only — verify in your email")).toBeTruthy();
    });
});

describe("ProposedChangeCard — atelier", () => {
    it("save flow still calls onSubmit", async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn().mockResolvedValue(undefined);
        const submitAction: RicoChatAction = {
            id: "s1", label: "Save", kind: "submit", impact: "medium",
            requires_confirmation: false, payload: {}, endpoint: "/api/v1/rico/profile",
        };
        render(
            <ProposedChangeCard
                atelier
                changes={[{ field: "target_role", current_value: "PM", proposed_value: "Senior PM" }] as never}
                submitAction={submitAction}
                onSubmit={onSubmit}
                onCancel={vi.fn()}
            />,
        );
        expect(screen.getByTestId("proposed-change-card")).toBeTruthy();
        await user.click(screen.getByTestId("proposed-change-save"));
        await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(submitAction));
    });
});
