/**
 * Focused unit tests for the approval confirmation contract.
 *
 * The moss "Approved / Saved" receipt must appear ONLY when the approve
 * mutation returns the server's explicit persisted status
 * `{ ok: true, status: "approved" }`. Absence from the pending-only queue is
 * NOT proof of approval, so the card has no queue-read fallback that could
 * render the receipt. An ambiguous request failure (which may have persisted
 * server-side) or any non-approved response lands in a single "unconfirmed"
 * state that never claims failure and never repeats the mutation — the only
 * offered action re-reads the queue.
 */
import { ApplicationDraftCard } from "@/components/queue/ApplicationDraftCard";
import type { ApplyActionResponse } from "@/lib/api";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/contexts/LanguageContext", () => ({ useLanguage: () => ({ language: "en" }) }));
vi.mock("@/lib/translations", () => ({ useTranslation: () => (k: string) => k }));
vi.mock("@/lib/utils", () => ({ cn: (...a: unknown[]) => a.filter(Boolean).join(" ") }));
vi.mock("@/components/atelier-kit/tokens", () => ({ ATELIER_FONT: { body: "", serif: "" } }));
vi.mock("@/components/ui/MaterialIcon", () => ({ MaterialIcon: () => null }));
vi.mock("@/components/workspace/theme", () => ({
    useWorkspaceTheme: () => ({
        dark: false,
        ink: "#000", ink40: "#666", ink55: "#555", ink70: "#333",
        red: "#cf3d17", hair: "#ddd", panel: "#fff", activeBg: "#f5f5f5",
    }),
}));

const draft = {
    id: "d1",
    job_title: "QHSE Manager",
    company: "Gulf Infrastructure Group",
    cover_letter: "Cover letter body",
    tailored_cv: "Tailored CV body",
    apply_url: "",
} as never;

const APPROVED: ApplyActionResponse = { ok: true, status: "approved" };

type Overrides = Partial<{
    onApprove: (id: string) => Promise<ApplyActionResponse>;
    onReloadQueue: () => void;
    onReject: (id: string) => Promise<void>;
}>;

function setup(over: Overrides = {}) {
    const onApprove = over.onApprove ?? vi.fn().mockResolvedValue(APPROVED);
    const onReloadQueue = over.onReloadQueue ?? vi.fn();
    const onResolved = vi.fn();
    const onReject = over.onReject ?? vi.fn().mockResolvedValue(undefined);
    render(
        <ApplicationDraftCard
            draft={draft}
            onApprove={onApprove}
            onResolved={onResolved}
            onReloadQueue={onReloadQueue}
            onReject={onReject}
        />,
    );
    return { onApprove, onReloadQueue, onResolved, onReject };
}
const clickApprove = () => fireEvent.click(screen.getByRole("button", { name: "draftApprove" }));
const clickDecline = () => fireEvent.click(screen.getByRole("button", { name: "draftDecline" }));

beforeEach(() => vi.clearAllMocks());

describe("ApplicationDraftCard — canonical approval confirmation", () => {
    it("exposes the draft content panel as a keyboard-reachable tabpanel", () => {
        setup();
        const panel = screen.getByRole("tabpanel");
        expect(panel).toHaveAttribute("id", "panel-d1");
        expect(panel).toHaveAttribute("tabindex", "0");
        const selectedTab = screen.getByRole("tab", { name: "draftCoverLetter" });
        expect(selectedTab).toHaveAttribute("aria-controls", "panel-d1");
        expect(panel).toHaveAttribute("aria-labelledby", "tab-cover_letter-d1");
    });

    it("explicit response status=approved → verified receipt; onResolved fires", async () => {
        const { onApprove, onResolved } = setup();
        clickApprove();
        await waitFor(() => expect(screen.getByText("draftApproved")).toBeInTheDocument());
        expect(screen.getByText("Saved to your applications.")).toBeInTheDocument();
        expect(onApprove).toHaveBeenCalledTimes(1);
        expect(onResolved).toHaveBeenCalledWith("d1");
    });

    it("response ok but status is NOT approved → no receipt (unconfirmed)", async () => {
        const onApprove = vi.fn().mockResolvedValue({ ok: true, status: "pending" });
        const { onResolved } = setup({ onApprove });
        clickApprove();
        await waitFor(() =>
            expect(screen.getByText("Approval status could not be confirmed")).toBeInTheDocument(),
        );
        expect(screen.queryByText("draftApproved")).not.toBeInTheDocument();
        expect(screen.queryByText("Saved to your applications.")).not.toBeInTheDocument();
        expect(onResolved).not.toHaveBeenCalled();
    });

    it("queue absence alone never renders Approved: any non-approved status stays unconfirmed", async () => {
        // A draft that has left the pending queue could be approved OR rejected;
        // "not pending" is not "approved". The card has no queue-read path, so a
        // response whose status is not exactly "approved" never shows the receipt.
        const onApprove = vi.fn().mockResolvedValue({ ok: true, status: "removed" });
        const { onResolved } = setup({ onApprove });
        clickApprove();
        await waitFor(() =>
            expect(screen.getByText("Approval status could not be confirmed")).toBeInTheDocument(),
        );
        expect(screen.queryByText("draftApproved")).not.toBeInTheDocument();
        expect(onResolved).not.toHaveBeenCalled();
    });

    it("server persisted but client timed out → unresolved state (never claims failure)", async () => {
        const onApprove = vi.fn().mockRejectedValue(new Error("timeout"));
        const { onResolved } = setup({ onApprove });
        clickApprove();
        await waitFor(() =>
            expect(screen.getByText("Approval status could not be confirmed")).toBeInTheDocument(),
        );
        // Must NOT assert the approval failed / "didn't go through".
        expect(screen.queryByText(/didn't go through/i)).not.toBeInTheDocument();
        expect(screen.queryByText("draftApproved")).not.toBeInTheDocument();
        expect(onResolved).not.toHaveBeenCalled();
    });

    it("ambiguous failure never repeats the mutation; Reload queue re-reads only", async () => {
        const onApprove = vi.fn().mockRejectedValue(new Error("network"));
        const { onReloadQueue } = setup({ onApprove });
        clickApprove();
        await waitFor(() =>
            expect(screen.getByText("Approval status could not be confirmed")).toBeInTheDocument(),
        );
        expect(onApprove).toHaveBeenCalledTimes(1); // not auto-repeated

        // The only offered action refreshes the list — it must not re-invoke
        // the approval mutation.
        fireEvent.click(screen.getByRole("button", { name: /Reload queue/i }));
        expect(onReloadQueue).toHaveBeenCalledTimes(1);
        expect(onApprove).toHaveBeenCalledTimes(1);
    });

    it("double click sends exactly one mutation", async () => {
        let resolveApprove!: (v: ApplyActionResponse) => void;
        const onApprove = vi.fn().mockImplementation(
            () => new Promise<ApplyActionResponse>((resolve) => { resolveApprove = resolve; }),
        );
        setup({ onApprove });
        // Two synchronous clicks before the in-flight mutation resolves.
        clickApprove();
        clickApprove();
        expect(onApprove).toHaveBeenCalledTimes(1);

        resolveApprove(APPROVED);
        await waitFor(() => expect(screen.getByText("draftApproved")).toBeInTheDocument());
        expect(onApprove).toHaveBeenCalledTimes(1);
    });

    it("double click on Decline sends exactly one reject request", async () => {
        let resolveReject!: (v: void) => void;
        const onReject = vi.fn().mockImplementation(
            () => new Promise<void>((resolve) => { resolveReject = resolve; }),
        );
        setup({ onReject });
        // Two synchronous clicks before the in-flight reject resolves.
        clickDecline();
        clickDecline();
        expect(onReject).toHaveBeenCalledTimes(1);

        resolveReject();
        await waitFor(() => expect(screen.queryByRole("tabpanel")).not.toBeInTheDocument());
        expect(onReject).toHaveBeenCalledTimes(1);
    });

    it("unconfirmed state exposes NO control that repeats the approval mutation", async () => {
        const onApprove = vi.fn().mockRejectedValue(new Error("timeout"));
        setup({ onApprove });
        clickApprove();
        await waitFor(() =>
            expect(screen.getByText("Approval status could not be confirmed")).toBeInTheDocument(),
        );
        // The only actionable control is the read-only refresh; there is no
        // Approve / Decline / Try-again button that could re-fire a mutation.
        const buttons = screen.getAllByRole("button");
        expect(buttons).toHaveLength(1);
        expect(buttons[0]).toHaveAccessibleName(/Reload queue/i);
        expect(screen.queryByRole("button", { name: "draftApprove" })).not.toBeInTheDocument();
    });
});
