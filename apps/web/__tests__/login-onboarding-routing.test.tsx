import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

/**
 * Post-login routing (DEC-20260710-004).
 *
 * After a successful login the app asks the backend for the completion signal
 * and routes: complete → /command, incomplete → /onboarding. A status failure
 * must NOT assume completion — it routes to /onboarding, whose own guard
 * recovers (and bounces already-complete users to /command).
 */

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
const { login } = vi.hoisted(() => ({ login: vi.fn() }));
const { fetchOnboardingStatus } = vi.hoisted(() => ({ fetchOnboardingStatus: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@/lib/store/useAuthStore", () => ({
  useAuthStore: () => ({ login, isLoading: false }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchOnboardingStatus };
});

import { LoginForm } from "@/components/auth/LoginForm";

function submitLogin() {
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "u@test.com" } });
  fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: "pw" } });
  const form = document.querySelector("form") as HTMLFormElement;
  fireEvent.submit(form);
}

beforeEach(() => {
  vi.clearAllMocks();
  login.mockResolvedValue(undefined);
});

describe("LoginForm post-login routing", () => {
  it("routes a completed user to /command", async () => {
    fetchOnboardingStatus.mockResolvedValue({ status: "completed", complete: true, source: "persisted", missing_fields: [], profile_exists: true, profile_completeness: 1 });
    render(<LoginForm />);
    submitLogin();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/command"));
  });

  it("routes an incomplete user to /onboarding", async () => {
    fetchOnboardingStatus.mockResolvedValue({ status: "in_progress", complete: false, source: "persisted", missing_fields: ["skills"], profile_exists: true, profile_completeness: 0.4 });
    render(<LoginForm />);
    submitLogin();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/onboarding"));
  });

  it("routes a legacy-complete user (derived_legacy) to /command", async () => {
    fetchOnboardingStatus.mockResolvedValue({ status: "completed", complete: true, source: "derived_legacy", missing_fields: [], profile_exists: true, profile_completeness: 1 });
    render(<LoginForm />);
    submitLogin();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/command"));
  });

  it("routes to /onboarding when the status check fails (never assumes completion)", async () => {
    fetchOnboardingStatus.mockRejectedValue(new ApiError("internal", 503));
    render(<LoginForm />);
    submitLogin();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/onboarding"));
    expect(push).not.toHaveBeenCalledWith("/command");
  });
});
