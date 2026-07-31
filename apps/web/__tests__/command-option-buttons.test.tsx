import { OptionButtons } from "@/components/command/OptionButtons";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/theme", () => ({
    useWorkspaceTheme: () => ({
        dark: false,
        bg: "#F2ECE0",
        panel: "#F6F0E5",
        rail: "#EAE1CD",
        inset: "#EAE1CD",
        ink: "#14110D",
        ink70: "#3A342C",
        ink55: "#6B6355",
        ink40: "rgba(20,17,13,0.40)",
        hair: "#D3C9B4",
        activeBg: "rgba(20,17,13,0.05)",
        track: "#E0D6BF",
        red: "#CF3D17",
    }),
}));

const useLanguageMock = vi.fn(() => ({ language: "en" }));
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => useLanguageMock(),
}));

const baseOptions = [
    { action: "search", label: "Search", message: "Find me jobs" },
    { action: "upload", label: "Upload CV" },
    { action: "save", label: "Save search" },
];

const renderButtons = (onAction = vi.fn()) =>
    render(<OptionButtons options={baseOptions} onAction={onAction} />);

describe("OptionButtons", () => {
    it("renders every supplied option", () => {
        renderButtons();
        expect(screen.getAllByRole("button")).toHaveLength(baseOptions.length);
        for (const opt of baseOptions) {
            expect(screen.getByText(opt.label)).toBeInTheDocument();
        }
    });

    it("sends opt.message when present", async () => {
        const onAction = vi.fn();
        renderButtons(onAction);
        await userEvent.click(screen.getByText("Search"));
        expect(onAction).toHaveBeenCalledOnce();
        expect(onAction).toHaveBeenCalledWith("Find me jobs");
    });

    it("falls back to opt.label when message is absent", async () => {
        const onAction = vi.fn();
        renderButtons(onAction);
        await userEvent.click(screen.getByText("Upload CV"));
        expect(onAction).toHaveBeenCalledOnce();
        expect(onAction).toHaveBeenCalledWith("Upload CV");
    });

    it("renders duplicate action values without losing buttons", () => {
        const onAction = vi.fn();
        const dups = [
            { action: "help", label: "Help" },
            { action: "help", label: "Help again" },
        ];
        render(<OptionButtons options={dups} onAction={onAction} />);
        expect(screen.getAllByRole("button")).toHaveLength(2);
    });

    it("sets RTL direction for Arabic labels", () => {
        useLanguageMock.mockReturnValue({ language: "ar" });
        const { container } = renderButtons();
        const root = container.firstChild as HTMLElement;
        expect(root).toHaveAttribute("dir", "rtl");
        useLanguageMock.mockReturnValue({ language: "en" });
    });

    it("activates via keyboard (Enter) after focus", async () => {
        const onAction = vi.fn();
        renderButtons(onAction);
        const button = screen.getByText("Save search");
        button.focus();
        expect(button).toHaveFocus();
        await userEvent.keyboard("{Enter}");
        expect(onAction).toHaveBeenCalledOnce();
        expect(onAction).toHaveBeenCalledWith("Save search");
    });

    it("does not use gold, lime, or sample values and renders as a real button", () => {
        renderButtons();
        const buttons = screen.getAllByRole("button");
        for (const button of buttons) {
            expect(button.tagName).toBe("BUTTON");
            expect(button).toHaveAttribute("type", "button");
            expect(button.className).not.toMatch(/\bgold\b/);
            expect(button.className).not.toMatch(/\blime\b/);
            expect(button.className).not.toMatch(/sample/);
            expect(button.textContent).not.toMatch(/DEMO|demo|Sample|sample/);
        }
    });
});
