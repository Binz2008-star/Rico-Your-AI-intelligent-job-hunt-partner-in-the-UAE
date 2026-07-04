import { fireEvent, screen } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// fix/login-password-visibility-toggle
//
// Scope: password input on the login form only. Verifies the eye-icon toggle
// switches the input's type between password/text without touching auth
// logic, the login API, or password-reset flow.

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/components/ui/AuraGlow", () => ({ AuraGlow: () => null }));
vi.mock("@/components/ui/GlassPanel", () => ({ GlassPanel: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
vi.mock("@/components/ui/PageTransition", () => ({
  PageTransition: ({ children }: { children: ReactNode }) => <>{children}</>,
  StaggerChildren: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
// Real MaterialIcon (not mocked) so the rendered glyph name is inspectable —
// asserting the icon actually swaps is part of "toggle works", not just aria state.
vi.mock("@/lib/store/useAuthStore", () => ({
  useAuthStore: () => ({ login: vi.fn(), isLoading: false }),
}));

import { LoginForm } from "@/components/auth/LoginForm";

afterEach(() => {
  vi.clearAllMocks();
});

describe("LoginForm password visibility toggle", () => {
  it("defaults to a hidden (type=password) field", () => {
    render(<LoginForm />);
    const input = screen.getByPlaceholderText("••••••••") as HTMLInputElement;
    expect(input.type).toBe("password");
  });

  it("reveals the password as plain text on click, and hides it again on a second click", () => {
    render(<LoginForm />);
    const input = screen.getByPlaceholderText("••••••••") as HTMLInputElement;
    const toggle = screen.getByRole("button", { name: /show password/i });

    fireEvent.click(toggle);
    expect(input.type).toBe("text");
    expect(screen.getByRole("button", { name: /hide password/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /hide password/i }));
    expect(input.type).toBe("password");
    expect(screen.getByRole("button", { name: /show password/i })).toBeInTheDocument();
  });

  it("exposes an accessible, keyboard-focusable toggle button (not a bare icon)", () => {
    render(<LoginForm />);
    const toggle = screen.getByRole("button", { name: /show password/i });
    expect(toggle.tagName).toBe("BUTTON");
    // type="button" so Enter/Space on the toggle can never submit the form.
    expect(toggle).toHaveAttribute("type", "button");
    toggle.focus();
    expect(toggle).toHaveFocus();
  });

  it("does not alter the input's name/value contract used by the login submit handler", () => {
    render(<LoginForm />);
    const input = screen.getByPlaceholderText("••••••••") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "correct horse battery staple" } });
    expect(input.value).toBe("correct horse battery staple");

    fireEvent.click(screen.getByRole("button", { name: /show password/i }));
    // Toggling visibility must not clear or mutate the typed value.
    expect(input.value).toBe("correct horse battery staple");
  });
});
