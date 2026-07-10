import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children: ReactNode }) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: { children: ReactNode }) => <p {...props}>{children}</p>,
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/ui/AuraGlow", () => ({ AuraGlow: ({ children }: { children: ReactNode }) => <>{children}</> }));
vi.mock("@/components/ui/GlassPanel", () => ({ GlassPanel: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
vi.mock("@/components/ui/MaterialIcon", () => ({ MaterialIcon: ({ icon }: { icon: string }) => <span>{icon}</span> }));
vi.mock("@/components/ui/PageTransition", () => ({
  PageTransition: ({ children }: { children: ReactNode }) => <>{children}</>,
  StaggerChildren: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const mockRegister = vi.fn();
const mockResendVerification = vi.fn();

// Pass ApiError through from the real module so instanceof checks in the component work.
vi.mock("@/lib/api", async (importActual) => {
  const actual = await importActual<typeof import("@/lib/api")>();
  return {
    ...actual,
    register: (...args: Parameters<typeof actual.register>) => mockRegister(...args),
    resendVerification: (...args: Parameters<typeof actual.resendVerification>) => mockResendVerification(...args),
  };
});

import { ApiError } from "@/lib/api";
import { SignupForm } from "@/components/auth/SignupForm";

function fillAndSubmit(email = "test@example.com", password = "Password1!") {
  fireEvent.change(screen.getByPlaceholderText("Your name"), { target: { value: "Test User" } });
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: email } });
  fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: /begin journey/i }));
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("SignupForm error mapping", () => {
  beforeEach(() => {
    render(<SignupForm />);
  });

  it("shows login link on 409 duplicate email", async () => {
    mockRegister.mockRejectedValueOnce(new ApiError("Email already registered", 409, {}));
    fillAndSubmit();
    await waitFor(
      () => expect(screen.getByText(/already registered/i)).toBeInTheDocument(),
      { timeout: 3000 },
    );
    expect(screen.getByRole("link", { name: /go to login/i })).toBeInTheDocument();
  });

  it("shows validation message on 400", async () => {
    // Empty backend message exercises the generic fallback copy: mapSignupError
    // uses `err.message || checkDetails`, so a non-empty message would render
    // verbatim and never reach the fallback this test asserts.
    mockRegister.mockRejectedValueOnce(new ApiError("", 400, {}));
    fillAndSubmit();
    await waitFor(
      () => expect(screen.getByText(/check your details/i)).toBeInTheDocument(),
      { timeout: 3000 },
    );
    expect(screen.queryByRole("link", { name: /go to login/i })).not.toBeInTheDocument();
  });

  it("shows validation message on 422", async () => {
    // Empty backend message exercises the generic fallback copy (see the 400 case).
    mockRegister.mockRejectedValueOnce(new ApiError("", 422, {}));
    fillAndSubmit();
    await waitFor(
      () => expect(screen.getByText(/check your details/i)).toBeInTheDocument(),
      { timeout: 3000 },
    );
  });

  it("shows generic error for unknown errors", async () => {
    mockRegister.mockRejectedValueOnce(new Error("Network failure"));
    fillAndSubmit();
    await waitFor(
      () => expect(screen.getByText(/couldn't create your account/i)).toBeInTheDocument(),
      { timeout: 3000 },
    );
    expect(screen.queryByRole("link", { name: /go to login/i })).not.toBeInTheDocument();
  });

  it("does not show login link for 500 ApiError", async () => {
    mockRegister.mockRejectedValueOnce(new ApiError("Server error", 500, {}));
    fillAndSubmit();
    await waitFor(
      () => expect(screen.getByText(/couldn't create your account/i)).toBeInTheDocument(),
      { timeout: 3000 },
    );
    expect(screen.queryByRole("link", { name: /go to login/i })).not.toBeInTheDocument();
  });
});

describe("SignupForm resend verification", () => {
  it("calls resendVerification with the registered email", async () => {
    render(<SignupForm />);
    mockRegister.mockResolvedValueOnce({ email: "a@b.com", role: "user", email_verification_required: true });
    mockResendVerification.mockResolvedValueOnce({ message: "Sent" });

    fillAndSubmit("a@b.com", "Password1!");

    // Wait for the post-register verification state (shows the registered email)
    await waitFor(
      () => expect(screen.getByText(/a@b\.com/)).toBeInTheDocument(),
      { timeout: 3000 },
    );

    const resendBtn = screen.getByRole("button", { name: /resend/i });
    fireEvent.click(resendBtn);

    await waitFor(
      () => expect(mockResendVerification).toHaveBeenCalledWith("a@b.com"),
      { timeout: 3000 },
    );
  });
});
