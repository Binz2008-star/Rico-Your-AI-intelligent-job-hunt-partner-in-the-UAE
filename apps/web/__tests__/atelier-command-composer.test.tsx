/**
 * Slice 4a — Atelier Command Composer.
 *
 * Two layers:
 *  - Component contract (AtelierCommandComposer in isolation): render, keyboard
 *    (Enter / Shift+Enter / IME), attachment wiring, disabled/pending gating, RTL.
 *  - Page integration (/command authenticated vs guest): the Atelier composer is
 *    used only for the authenticated surface, the send path still trims, Ctrl+K
 *    focuses and Ctrl+J starts a new conversation, the public composer is
 *    unchanged, and no chat/streaming API function was replaced.
 */
import "@testing-library/jest-dom/vitest";
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { AtelierCommandComposer, type AtelierCommandComposerProps } from "@/components/command/AtelierCommandComposer";

// ── Page-integration mocks (hoisted, file-wide) ───────────────────────────────
const { fetchMeMock, fetchChatHistoryMock, sendChatStreamMock, sendChatMock } = vi.hoisted(() => ({
    fetchMeMock: vi.fn(),
    fetchChatHistoryMock: vi.fn().mockResolvedValue([]),
    // Empty stream → page falls back to sendChat; both receive the trimmed text.
    sendChatStreamMock: vi.fn(async function* () { /* yields nothing */ }),
    sendChatMock: vi.fn().mockRejectedValue(new Error("test-stop")),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => "/command",
}));
vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));
// Passthrough shell — keeps the page light and lets the composer fall back to the
// default (light) workspace theme; these tests assert behavior, not colors.
vi.mock("@/components/workspace/WorkspaceShell", () => ({
    WorkspaceShell: ({ children }: { children: React.ReactNode }) => <div data-testid="workspace-shell">{children}</div>,
}));
vi.mock("@/lib/api", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    return {
        ...actual,
        fetchMe: fetchMeMock,
        fetchChatHistory: fetchChatHistoryMock,
        sendChatStream: sendChatStreamMock,
        sendChat: sendChatMock,
    };
});

import CommandPage from "@/app/command/page";

// ── Component-contract helpers ────────────────────────────────────────────────
function makeProps(over: Partial<AtelierCommandComposerProps> = {}): AtelierCommandComposerProps {
    return {
        value: "",
        onValueChange: vi.fn(),
        onSend: vi.fn(),
        onCancel: vi.fn(),
        thinking: false,
        inputDisabled: false,
        canSend: false,
        placeholder: "Write to Rico…",
        textareaRef: React.createRef<HTMLTextAreaElement>(),
        attachInputId: "cv-file-upload",
        attachDisabled: false,
        attachTitle: "Upload your CV (PDF)",
        attachAriaLabel: "Upload CV",
        sendAriaLabel: "Send",
        cancelAriaLabel: "Cancel",
        ...over,
    };
}

function renderComposer(over: Partial<AtelierCommandComposerProps> = {}) {
    const props = makeProps(over);
    const utils = render(<AtelierCommandComposer {...props} />, { wrapper: LanguageProvider });
    return { props, ...utils };
}

beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("rico_sid", "test-session-4a");
    fetchChatHistoryMock.mockResolvedValue([]);
    sendChatMock.mockRejectedValue(new Error("test-stop"));
});

describe("AtelierCommandComposer — component contract", () => {
    it("renders the Atelier composer (input, send button, hint, char count)", () => {
        renderComposer({ value: "hi", canSend: true });
        expect(screen.getByTestId("atelier-command-composer")).toBeInTheDocument();
        expect(screen.getByLabelText("Message Rico")).toBeInTheDocument();
        expect(screen.getByTestId("composer-send")).toBeInTheDocument();
        // Hint built internally (default modKey = Ctrl in jsdom) + live char count.
        expect(screen.getByText(/Ctrl\+J new/i)).toBeInTheDocument();
        expect(screen.getByText(/2 chars/i)).toBeInTheDocument();
    });

    it("(3) Enter invokes the send callback", () => {
        const onSend = vi.fn();
        renderComposer({ value: "hello", canSend: true, onSend });
        fireEvent.keyDown(screen.getByLabelText("Message Rico"), { key: "Enter" });
        expect(onSend).toHaveBeenCalledTimes(1);
    });

    it("(4) Shift+Enter does not send (newline)", () => {
        const onSend = vi.fn();
        renderComposer({ value: "hello", canSend: true, onSend });
        fireEvent.keyDown(screen.getByLabelText("Message Rico"), { key: "Enter", shiftKey: true });
        expect(onSend).not.toHaveBeenCalled();
    });

    it("(5) Enter during IME composition does not send", () => {
        const onSend = vi.fn();
        renderComposer({ value: "مرحبا", canSend: true, onSend });
        fireEvent.keyDown(screen.getByLabelText("Message Rico"), { key: "Enter", isComposing: true });
        expect(onSend).not.toHaveBeenCalled();
    });

    it("(6) the attachment control triggers the existing hidden file input", () => {
        const onAttachClick = vi.fn();
        render(
            <LanguageProvider>
                <input id="cv-file-upload" type="file" data-testid="hidden-file" onClick={onAttachClick} />
                <AtelierCommandComposer {...makeProps()} />
            </LanguageProvider>,
        );
        // Native <label htmlFor> activation dispatches a click on the associated input.
        fireEvent.click(screen.getByTestId("composer-attach"));
        expect(onAttachClick).toHaveBeenCalled();
    });

    it("(7) send is blocked when canSend is false, and hidden while thinking", () => {
        const onSend = vi.fn();
        const { rerender } = renderComposer({ value: "", canSend: false, onSend });
        const sendBtn = screen.getByTestId("composer-send");
        expect(sendBtn).toBeDisabled();
        fireEvent.click(sendBtn);
        expect(onSend).not.toHaveBeenCalled();

        rerender(<AtelierCommandComposer {...makeProps({ value: "x", canSend: true, thinking: true, onSend })} />);
        expect(screen.queryByTestId("composer-send")).not.toBeInTheDocument();
        expect(screen.getByTestId("composer-cancel")).toBeInTheDocument();
    });

    it("(10) Arabic renders RTL with the Arabic hint", async () => {
        localStorage.setItem("rico-language", "ar");
        renderComposer({ value: "مرحبا" });
        await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
        expect(screen.getByTestId("atelier-command-composer")).toBeInTheDocument();
        // Hint is rebuilt in Arabic by the component (uses useLanguage()).
        expect(screen.getByText(/جديد/)).toBeInTheDocument();
        expect(screen.getByText(/حرف/)).toBeInTheDocument();
    });
});

describe("/command integration — Atelier composer (slice 4a)", () => {
    function authenticated() {
        fetchMeMock.mockResolvedValue({ authenticated: true, role: "user", email: "u@u.com" });
    }
    function guest() {
        fetchMeMock.mockResolvedValue({ authenticated: false, role: "guest", email: null, guest: true });
    }

    it("(1) authenticated /command renders the Atelier composer", async () => {
        authenticated();
        render(<CommandPage />, { wrapper: LanguageProvider });
        expect(await screen.findByTestId("atelier-command-composer")).toBeInTheDocument();
    });

    it("(2) the send path forwards the trimmed text to the existing chat API", async () => {
        authenticated();
        render(<CommandPage />, { wrapper: LanguageProvider });
        await screen.findByTestId("atelier-command-composer");
        const textarea = screen.getByLabelText("Message Rico");
        fireEvent.change(textarea, { target: { value: "  hello world  " } });
        fireEvent.keyDown(textarea, { key: "Enter" });
        await waitFor(() => expect(sendChatStreamMock).toHaveBeenCalled());
        const streamArg = sendChatStreamMock.mock.calls[0]?.[0];
        const chatArg = sendChatMock.mock.calls[0]?.[0];
        expect(streamArg ?? chatArg).toBe("hello world");
    });

    it("(8) Ctrl+K focuses the composer textarea", async () => {
        authenticated();
        render(<CommandPage />, { wrapper: LanguageProvider });
        await screen.findByTestId("atelier-command-composer");
        const textarea = screen.getByLabelText("Message Rico");
        expect(textarea).not.toHaveFocus();
        fireEvent.keyDown(window, { key: "k", ctrlKey: true });
        expect(textarea).toHaveFocus();
    });

    it("(9) Ctrl+J starts a new conversation (clears the composer)", async () => {
        authenticated();
        render(<CommandPage />, { wrapper: LanguageProvider });
        await screen.findByTestId("atelier-command-composer");
        const textarea = screen.getByLabelText("Message Rico") as HTMLTextAreaElement;
        fireEvent.change(textarea, { target: { value: "draft in progress" } });
        expect(textarea.value).toBe("draft in progress");
        fireEvent.keyDown(window, { key: "j", ctrlKey: true });
        await waitFor(() => expect((screen.getByLabelText("Message Rico") as HTMLTextAreaElement).value).toBe(""));
    });

    it("(11) guest/public keeps the original composer — no Atelier composer", async () => {
        guest();
        render(<CommandPage />, { wrapper: LanguageProvider });
        // Public composer renders its textarea; the Atelier one must be absent.
        await waitFor(() => expect(screen.getByLabelText("Message Rico")).toBeInTheDocument());
        expect(screen.queryByTestId("atelier-command-composer")).not.toBeInTheDocument();
    });

    it("(12) no chat/streaming API function was replaced", async () => {
        const api = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
        expect(typeof api.sendChat).toBe("function");
        expect(typeof api.sendChatStream).toBe("function");
        expect(typeof api.sendChatPublic).toBe("function");
        expect(typeof api.sendChatStreamPublic).toBe("function");
    });
});
