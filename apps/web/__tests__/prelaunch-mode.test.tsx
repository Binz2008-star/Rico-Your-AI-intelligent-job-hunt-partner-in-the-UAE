import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WaitlistForm } from "@/components/waitlist/WaitlistForm";
import { getLaunchMode, isWaitlistMode } from "@/lib/launch-mode";
import {
  isProxyRequest,
  isPublicDuringWaitlist,
} from "@/lib/prelaunch-paths";
import { renderWithProviders as render } from "./test-utils";


describe("pre-launch server policy helpers", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("defaults missing and invalid values to live mode", () => {
    vi.stubEnv("RICO_LAUNCH_MODE", "");
    expect(getLaunchMode()).toBe("live");
    expect(isWaitlistMode()).toBe(false);

    vi.stubEnv("RICO_LAUNCH_MODE", "unexpected");
    expect(getLaunchMode()).toBe("live");
  });

  it("enables waitlist mode only through the exact server-side value", () => {
    vi.stubEnv("RICO_LAUNCH_MODE", " WAITLIST ");
    expect(getLaunchMode()).toBe("waitlist");
    expect(isWaitlistMode()).toBe(true);
  });

  it("keeps only the approved public and recovery surfaces reachable", () => {
    expect(isPublicDuringWaitlist("/")).toBe(true);
    expect(isPublicDuringWaitlist("/login")).toBe(true);
    expect(isPublicDuringWaitlist("/privacy")).toBe(true);
    expect(isPublicDuringWaitlist("/signup")).toBe(false);
    expect(isPublicDuringWaitlist("/command")).toBe(false);
    expect(isPublicDuringWaitlist("/onboarding")).toBe(false);
    expect(isPublicDuringWaitlist("/proxy/api/v1/auth/login")).toBe(true);
    expect(isPublicDuringWaitlist("/proxy/api/v1/rico/chat/public")).toBe(false);
  });

  it("identifies every proxy path for backend-authoritative enforcement", () => {
    expect(isProxyRequest("/proxy")).toBe(true);
    expect(isProxyRequest("/proxy/api/v1/jobs")).toBe(true);
    expect(isProxyRequest("/api/waitlist/register")).toBe(false);
  });
});


describe("WaitlistForm", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    window.history.replaceState({}, "", "/?utm_source=qa&referral_code=friend");
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("requires consent before submission", async () => {
    const user = userEvent.setup();
    render(<WaitlistForm />);

    await user.type(screen.getByPlaceholderText("Email address *"), "person@example.com");
    expect(screen.getByRole("button", { name: "Reserve early access" })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts normalized form fields and approved attribution to the backend proxy", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        message: "Your early-access request has been recorded.",
      }),
    });
    const user = userEvent.setup();
    render(<WaitlistForm />);

    await user.type(screen.getByPlaceholderText("Email address *"), "person@example.com");
    await user.type(screen.getByPlaceholderText("First name (optional)"), "Person");
    await user.type(screen.getByPlaceholderText("Target role (optional)"), "Product Manager");
    await user.selectOptions(screen.getByRole("combobox"), "Dubai");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Reserve early access" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/proxy/api/v1/waitlist/register");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      email: "person@example.com",
      first_name: "Person",
      target_role: "Product Manager",
      location: "Dubai",
      consent: true,
      source: {
        utm_source: "qa",
        referral_code: "friend",
        landing_path: "/",
      },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Your place is reserved.");
  });

  it("shows a safe error without losing the form", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Registration is temporarily unavailable." }),
    });
    const user = userEvent.setup();
    render(<WaitlistForm />);

    await user.type(screen.getByPlaceholderText("Email address *"), "person@example.com");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Reserve early access" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Registration is temporarily unavailable.",
    );
    expect(screen.getByPlaceholderText("Email address *")).toHaveValue("person@example.com");
  });
});
