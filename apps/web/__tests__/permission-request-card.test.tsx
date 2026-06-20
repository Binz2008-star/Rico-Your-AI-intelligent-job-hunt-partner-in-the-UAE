/**
 * apps/web/__tests__/permission-request-card.test.tsx
 *
 * CAREER-OS-03: Unit tests for PermissionRequestCard component.
 *
 * Verifies:
 * - Card renders title, summary, risk badge, data_used, effects.
 * - Approve button calls onApprove with the approve_action.
 * - Cancel button calls onCancel.
 * - Review button renders only when review_action is present.
 * - Card hides itself (returns null) after a successful approval.
 * - disabled prop blocks approve and cancel interactions.
 * - Approve button shows "Executing…" while the promise is in-flight.
 * - Empty data_used / effects sections are omitted.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PermissionRequestCard } from "@/components/ui/rico/PermissionRequestCard";
import type { RicoChatAction, RicoPermissionRequest } from "@/lib/schemas";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeApproveAction(overrides: Partial<RicoChatAction> = {}): RicoChatAction {
    return {
        id: "approve-1",
        label: "Apply now",
        kind: "approve",
        impact: "high",
        requires_confirmation: false,
        payload: { action: "apply", job_key: "abc123" },
        ...overrides,
    };
}

function makeCancelAction(overrides: Partial<RicoChatAction> = {}): RicoChatAction {
    return {
        id: "cancel-1",
        label: "Cancel",
        kind: "cancel",
        impact: "low",
        requires_confirmation: false,
        payload: {},
        ...overrides,
    };
}

function makeRequest(overrides: Partial<RicoPermissionRequest> = {}): RicoPermissionRequest {
    return {
        id: "perm-001",
        title: "Apply to Senior Risk Manager",
        summary: "Rico will submit your application to Gulf Corp on your behalf.",
        risk_level: "high",
        data_used: ["Your CV", "Your profile"],
        effects: ["Application will be marked as applied"],
        approve_action: makeApproveAction(),
        cancel_action: makeCancelAction(),
        ...overrides,
    };
}

// ── Render ────────────────────────────────────────────────────────────────────

describe("PermissionRequestCard rendering", () => {
    it("renders the title", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByText("Apply to Senior Risk Manager")).toBeInTheDocument();
    });

    it("renders the summary", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByText("Rico will submit your application to Gulf Corp on your behalf.")).toBeInTheDocument();
    });

    it("renders the high risk badge", () => {
        render(<PermissionRequestCard request={makeRequest({ risk_level: "high" })} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("risk-badge")).toHaveTextContent("High risk");
    });

    it("renders the medium risk badge", () => {
        render(<PermissionRequestCard request={makeRequest({ risk_level: "medium" })} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("risk-badge")).toHaveTextContent("Medium risk");
    });

    it("renders data_used items", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("data-used-section")).toBeInTheDocument();
        expect(screen.getByText("Your CV")).toBeInTheDocument();
        expect(screen.getByText("Your profile")).toBeInTheDocument();
    });

    it("omits data_used section when empty", () => {
        render(<PermissionRequestCard request={makeRequest({ data_used: [] })} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.queryByTestId("data-used-section")).not.toBeInTheDocument();
    });

    it("renders effects items", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("effects-section")).toBeInTheDocument();
        expect(screen.getByText("Application will be marked as applied")).toBeInTheDocument();
    });

    it("omits effects section when empty", () => {
        render(<PermissionRequestCard request={makeRequest({ effects: [] })} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.queryByTestId("effects-section")).not.toBeInTheDocument();
    });

    it("renders approve button with approve_action label", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("permission-approve-btn")).toHaveTextContent("Apply now");
    });

    it("renders cancel button with cancel_action label", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByTestId("permission-cancel-btn")).toHaveTextContent("Cancel");
    });

    it("does not render review button when review_action is absent", () => {
        render(<PermissionRequestCard request={makeRequest({ review_action: undefined })} onApprove={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.queryByTestId("permission-review-btn")).not.toBeInTheDocument();
    });

    it("renders review button when review_action is present", () => {
        const reviewAction: RicoChatAction = {
            id: "review-1",
            label: "Review details",
            kind: "navigate",
            impact: "low",
            requires_confirmation: false,
            payload: {},
        };
        render(
            <PermissionRequestCard
                request={makeRequest({ review_action: reviewAction })}
                onApprove={vi.fn()}
                onCancel={vi.fn()}
            />,
        );
        expect(screen.getByTestId("permission-review-btn")).toHaveTextContent("Review details");
    });
});

// ── Interactions ──────────────────────────────────────────────────────────────

describe("PermissionRequestCard interactions", () => {
    it("calls onApprove with approve_action when approve clicked", async () => {
        const user = userEvent.setup();
        const handler = vi.fn().mockResolvedValue(undefined);
        render(<PermissionRequestCard request={makeRequest()} onApprove={handler} onCancel={vi.fn()} />);
        await user.click(screen.getByTestId("permission-approve-btn"));
        expect(handler).toHaveBeenCalledOnce();
        expect(handler).toHaveBeenCalledWith(makeApproveAction());
    });

    it("calls onCancel when cancel clicked", async () => {
        const user = userEvent.setup();
        const cancelHandler = vi.fn();
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={cancelHandler} />);
        await user.click(screen.getByTestId("permission-cancel-btn"));
        expect(cancelHandler).toHaveBeenCalledOnce();
    });

    it("hides the card (returns null) after successful approval", async () => {
        const user = userEvent.setup();
        const handler = vi.fn().mockResolvedValue(undefined);
        const { container } = render(
            <PermissionRequestCard request={makeRequest()} onApprove={handler} onCancel={vi.fn()} />,
        );
        await user.click(screen.getByTestId("permission-approve-btn"));
        await waitFor(() => expect(container).toBeEmptyDOMElement());
    });

    it("shows 'Executing…' while onApprove is in-flight", async () => {
        const user = userEvent.setup();
        let resolve!: () => void;
        const handler = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r; }));
        render(<PermissionRequestCard request={makeRequest()} onApprove={handler} onCancel={vi.fn()} />);
        await user.click(screen.getByTestId("permission-approve-btn"));
        expect(screen.getByTestId("permission-approve-btn")).toHaveTextContent("Executing…");
        resolve();
        await waitFor(() => expect(screen.queryByTestId("permission-request-card")).not.toBeInTheDocument());
    });

    it("approve button is disabled while executing", async () => {
        const user = userEvent.setup();
        let resolve!: () => void;
        const handler = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r; }));
        render(<PermissionRequestCard request={makeRequest()} onApprove={handler} onCancel={vi.fn()} />);
        await user.click(screen.getByTestId("permission-approve-btn"));
        expect(screen.getByTestId("permission-approve-btn")).toBeDisabled();
        resolve();
    });
});

// ── disabled prop ─────────────────────────────────────────────────────────────

describe("PermissionRequestCard disabled prop", () => {
    it("approve button is disabled when disabled=true", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} disabled />);
        expect(screen.getByTestId("permission-approve-btn")).toBeDisabled();
    });

    it("cancel button is still enabled when disabled=true (allows dismissal)", () => {
        render(<PermissionRequestCard request={makeRequest()} onApprove={vi.fn()} onCancel={vi.fn()} disabled />);
        expect(screen.getByTestId("permission-cancel-btn")).not.toBeDisabled();
    });

    it("does not call onApprove when disabled and clicked", async () => {
        const user = userEvent.setup();
        const handler = vi.fn();
        render(<PermissionRequestCard request={makeRequest()} onApprove={handler} onCancel={vi.fn()} disabled />);
        await user.click(screen.getByTestId("permission-approve-btn"));
        expect(handler).not.toHaveBeenCalled();
    });
});
