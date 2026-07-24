/**
 * Focused unit tests for the approval read-back hardening.
 * The moss "Verified/Approved" receipt must appear ONLY after a canonical
 * read-back confirms the draft is persisted-approved (absent from the queue),
 * never on approval-mutation success alone.
 */
import { ApplicationDraftCard } from "@/components/queue/ApplicationDraftCard";
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

function setup(over: Partial<{ onApprove: () => Promise<void>; onConfirm: () => Promise<boolean> }> = {}) {
    const onApprove = over.onApprove ?? vi.fn().mockResolvedValue(undefined);
    const onConfirm = over.onConfirm ?? vi.fn().mockResolvedValue(true);
    const onResolved = vi.fn();
    const onReject = vi.fn().mockResolvedValue(undefined);
    render(
        <ApplicationDraftCard draft={draft} onApprove={onApprove} onConfirm={onConfirm} onResolved={onResolved} onReject={onReject} />,
    );
    return { onApprove, onConfirm, onResolved, onReject };
}
const clickApprove = () => fireEvent.click(screen.getByRole("button", { name: "draftApprove" }));

beforeEach(() => vi.clearAllMocks());

describe("ApplicationDraftCard — canonical approval read-back", () => {
    it("exposes the draft content panel as a keyboard-reachable tabpanel", () => {
        setup();
        const panel = screen.getByRole("tabpanel");
        expect(panel).toHaveAttribute("id", "panel-d1");
        expect(panel).toHaveAttribute("tabindex", "0");
        // the selected tab controls the panel and labels it
        const selectedTab = screen.getByRole("tab", { name: "draftCoverLetter" });
        expect(selectedTab).toHaveAttribute("aria-controls", "panel-d1");
        expect(panel).toHaveAttribute("aria-labelledby", "tab-cover_letter-d1");
    });

    it("approve ok + read-back confirms → verified receipt; onResolved fires; no re-mutation", async () => {
        const { onApprove, onConfirm, onResolved } = setup();
        clickApprove();
        await waitFor(() => expect(screen.getByText("draftApproved")).toBeInTheDocument());
        expect(screen.getByText("Saved to your applications.")).toBeInTheDocument();
        expect(onApprove).toHaveBeenCalledTimes(1);
        expect(onConfirm).toHaveBeenCalledTimes(1);
        expect(onResolved).toHaveBeenCalledWith("d1");
    });

    it("approve ok + read-back NOT confirmed → no verified; Retry check re-runs read-back ONLY", async () => {
        const onConfirm = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
        const { onApprove, onResolved } = setup({ onConfirm });
        clickApprove();
        await waitFor(() => expect(screen.getByText("Approved — but not yet confirmed")).toBeInTheDocument());
        expect(screen.queryByText("draftApproved")).not.toBeInTheDocument();
        expect(onResolved).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: /Retry check/i }));
        await waitFor(() => expect(screen.getByText("draftApproved")).toBeInTheDocument());
        expect(onApprove).toHaveBeenCalledTimes(1);   // mutation NEVER repeated
        expect(onConfirm).toHaveBeenCalledTimes(2);    // read-back retried
    });

    it("approve ok + read-back throws → verify-failed (never shows verified)", async () => {
        const onConfirm = vi.fn().mockRejectedValue(new Error("network"));
        setup({ onConfirm });
        clickApprove();
        await waitFor(() => expect(screen.getByText("Approved — but not yet confirmed")).toBeInTheDocument());
        expect(screen.queryByText("draftApproved")).not.toBeInTheDocument();
    });

    it("approve fails → error state; Try again re-runs the mutation", async () => {
        const onApprove = vi.fn().mockRejectedValueOnce(new Error("500")).mockResolvedValueOnce(undefined);
        const onConfirm = vi.fn().mockResolvedValue(true);
        setup({ onApprove, onConfirm });
        clickApprove();
        await waitFor(() => expect(screen.getByText("Approval didn't go through")).toBeInTheDocument());
        expect(onConfirm).not.toHaveBeenCalled(); // never read-back when mutation failed

        fireEvent.click(screen.getByRole("button", { name: /Try again/i }));
        await waitFor(() => expect(screen.getByText("draftApproved")).toBeInTheDocument());
        expect(onApprove).toHaveBeenCalledTimes(2);
    });
});
