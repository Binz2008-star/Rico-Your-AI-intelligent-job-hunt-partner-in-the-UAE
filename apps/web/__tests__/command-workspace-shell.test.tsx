/**
 * PR 3 — /command chrome contract (Atelier full-site migration program).
 *
 * Authenticated (and the transient "checking" state) render inside the
 * WorkspaceShell rail in its full-height app variant, dark-first; the
 * public/guest audience keeps the approved reference chrome (top bar + chat
 * column, no workspace shell). Chat behavior itself is untouched by PR 3.
 */

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
vi.mock("@/components/workspace/WorkspaceShell", () => ({
  WorkspaceShell: ({ children, variant, defaultDark }: any) => (
    <div data-testid="workspace-shell" data-variant={variant ?? "document"} data-defaultdark={String(defaultDark ?? false)}>
      {children}
    </div>
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

describe("/command chrome — WorkspaceShell app variant (PR 3)", () => {
  it("authenticated audience renders inside the WorkspaceShell app variant, dark-first", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    const shell = await screen.findByTestId("workspace-shell");
    expect(shell).toHaveAttribute("data-variant", "app");
    expect(shell).toHaveAttribute("data-defaultdark", "true");
  });

  it("public audience keeps the reference chrome — no WorkspaceShell", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true }, 200);
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    expect(await screen.findByText("Sign up free")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-shell")).not.toBeInTheDocument();
  });

  it("the transient checking state already sits in the shell (no layout jump on auth resolve)", async () => {
    // /me never resolves → audience stays "checking".
    fetchMock.mockImplementation(() => new Promise<ResponseLike>(() => undefined));

    render(<CommandPage />);

    await waitFor(() => {
      expect(screen.getByTestId("workspace-shell")).toBeInTheDocument();
    });
  });
});
