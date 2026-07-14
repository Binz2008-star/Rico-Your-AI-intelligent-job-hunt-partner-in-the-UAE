/**
 * PR 4 — CommandComposer contract (Atelier full-site migration program).
 *
 * Verifies the presentational contract of the extracted CommandComposer:
 *   - Send button is disabled when input is empty, checking, or hasPendingPermission.
 *   - Cancel (✕) button replaces send while thinking=true.
 *   - Quota notice appears when messagesRemaining <= 10 (authenticated).
 *   - Public sign-up CTA renders when showSignUpCta=true.
 *   - Upload error renders as an alert.
 *   - The component exposes the expected aria-label on the textarea.
 *
 * All tests use the minimal prop set — no message state, no API calls.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { CommandComposer } from "@/components/command/CommandComposer";
import type { CommandComposerProps } from "@/components/command/CommandComposer";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function t(key: string): string {
  const map: Record<string, string> = {
    cmdSignUpCta: "Save your profile and track applications.",
    cmdSignUpFree: "Sign up free",
    cmdMsgLimitReached: "Message limit reached",
    cmdMsgLimitOne: "1 message left",
    cmdMsgLimitFew: "{n} messages left",
    cmdUpgrade: "Upgrade",
    cmdCancelRequest: "Cancel request",
    cmdUploadCvTitle: "Upload CV",
    cmdUploadCvAriaLabel: "Upload CV or document",
    cmdPlaceholderChecking: "Connecting...",
    cmdPlaceholderReady: "Message Rico",
    cmdHint: "Rico AI · your career partner",
    send: "Send",
  };
  return map[key] ?? key;
}

const baseProps: CommandComposerProps = {
  showSignUpCta: false,
  input: "",
  onInputChange: vi.fn(),
  textareaRef: React.createRef(),
  fileInputRef: React.createRef(),
  thinking: false,
  chatAudience: "authenticated",
  hasPendingPermission: false,
  messagesRemaining: null,
  uploadError: null,
  onKeyDown: vi.fn(),
  onSend: vi.fn(),
  onCancel: vi.fn(),
  onCVUpload: vi.fn(),
  t: t as (key: import("@/lib/translations").TranslationKey) => string,
  signupHref: "/signup",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CommandComposer — send button state", () => {
  it("send button is disabled when input is empty", () => {
    render(<CommandComposer {...baseProps} input="" />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("send button is enabled when input has non-whitespace text", () => {
    render(<CommandComposer {...baseProps} input="hello" />);
    expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled();
  });

  it("send button is disabled when chatAudience is checking", () => {
    render(<CommandComposer {...baseProps} input="hello" chatAudience="checking" />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("send button is disabled when hasPendingPermission is true", () => {
    render(<CommandComposer {...baseProps} input="hello" hasPendingPermission={true} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("CommandComposer — cancel button (thinking state)", () => {
  it("shows cancel button instead of send while thinking", () => {
    render(<CommandComposer {...baseProps} thinking={true} />);
    expect(screen.getByRole("button", { name: "Cancel request" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });

  it("shows send button when not thinking", () => {
    render(<CommandComposer {...baseProps} thinking={false} input="hi" />);
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel request" })).not.toBeInTheDocument();
  });
});

describe("CommandComposer — quota notice", () => {
  it("shows quota notice when messagesRemaining <= 10 and authenticated", () => {
    render(<CommandComposer {...baseProps} messagesRemaining={5} chatAudience="authenticated" />);
    expect(screen.getByRole("status")).toHaveTextContent("5 messages left");
  });

  it("shows 'limit reached' text when messagesRemaining is 0", () => {
    render(<CommandComposer {...baseProps} messagesRemaining={0} chatAudience="authenticated" />);
    expect(screen.getByRole("status")).toHaveTextContent("Message limit reached");
  });

  it("does not show quota notice when messagesRemaining is null", () => {
    render(<CommandComposer {...baseProps} messagesRemaining={null} />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not show quota notice when messagesRemaining > 10", () => {
    render(<CommandComposer {...baseProps} messagesRemaining={11} chatAudience="authenticated" />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not show quota notice for public audience even when remaining <= 10", () => {
    render(<CommandComposer {...baseProps} messagesRemaining={3} chatAudience="public" />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("CommandComposer — public sign-up CTA", () => {
  it("renders sign-up CTA when showSignUpCta is true", () => {
    render(<CommandComposer {...baseProps} showSignUpCta={true} signupHref="/signup?from=/command" />);
    expect(screen.getByText("Sign up free")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign up free" })).toHaveAttribute("href", "/signup?from=/command");
  });

  it("does not render sign-up CTA when showSignUpCta is false", () => {
    render(<CommandComposer {...baseProps} showSignUpCta={false} />);
    expect(screen.queryByText("Sign up free")).not.toBeInTheDocument();
  });
});

describe("CommandComposer — upload error", () => {
  it("renders upload error as an alert when present", () => {
    render(<CommandComposer {...baseProps} uploadError="File too large" />);
    expect(screen.getByRole("alert")).toHaveTextContent("File too large");
  });

  it("does not render an alert when uploadError is null", () => {
    render(<CommandComposer {...baseProps} uploadError={null} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("CommandComposer — accessibility", () => {
  it("textarea has the expected aria-label", () => {
    render(<CommandComposer {...baseProps} />);
    expect(screen.getByRole("textbox", { name: "Message Rico" })).toBeInTheDocument();
  });

  it("upload label has the expected aria-label", () => {
    render(<CommandComposer {...baseProps} />);
    expect(screen.getByRole("button", { name: "Upload CV or document" })).toBeInTheDocument();
  });
});
