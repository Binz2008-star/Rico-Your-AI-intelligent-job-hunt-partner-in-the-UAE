import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/command",
}));
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import CommandPage from "@/app/command/page";

type JsonValue = Record<string, unknown>;
type ResponseLike = { ok: boolean; status: number; json: () => Promise<JsonValue> };

function jsonResponse(body: JsonValue, status = 200): ResponseLike {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  localStorage.setItem("rico_sid", "test-session-01");
  vi.stubGlobal("fetch", fetchMock);
});

describe("/command auth-state containment (issue #281)", () => {
  it("signed-in user never sees public 'Sign in / Sign up free' links", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    // Once /me resolves, the authenticated controls appear. The logout affordance
    // is an accessible control (sidebar avatar button + mobile drawer item) labelled
    // "Log out", not visible "Sign out" text — assert on its accessible name.
    expect((await screen.findAllByRole("button", { name: /log out/i })).length).toBeGreaterThan(0);
    // …and the public links must NOT be rendered for a signed-in user.
    expect(screen.queryByText("Sign up free")).not.toBeInTheDocument();
    expect(screen.queryByText("Sign in")).not.toBeInTheDocument();
  });

  it("public user sees 'Sign in / Sign up free' only after the session check resolves", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    expect(await screen.findByText("Sign up free")).toBeInTheDocument();
    // "Sign in" renders in two responsive variants (compact top bar + slide-in
    // drawer), so assert presence rather than a single match.
    expect(screen.getAllByText("Sign in").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
  });

  it("/me resolving as authenticated always yields authenticated audience, never public", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /log out/i }).length).toBeGreaterThan(0);
    });
    // Authenticated user must never see public links — guards against fallback timeout
    // silently downgrading an authenticated session to guest (regression for 2 s timeout).
    expect(screen.queryByText("Sign up free")).not.toBeInTheDocument();
    expect(screen.queryByText("Sign in")).not.toBeInTheDocument();
  });

  it("while the session is still being checked, no public links flash", () => {
    // /me never resolves → component stays in the 'checking' state.
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return new Promise<ResponseLike>(() => {}); // pending forever
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    // During 'checking' a neutral placeholder is shown — neither auth state is revealed.
    expect(screen.queryByText("Sign up free")).not.toBeInTheDocument();
    expect(screen.queryByText("Sign in")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
  });
});
