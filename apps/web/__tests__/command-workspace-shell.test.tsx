/**
 * /command chrome contract — PR 3 (Atelier program), re-pointed by slice C1 of
 * the Command Obsidian program (owner directive 2026-07-16).
 *
 * Authenticated (and the transient "checking" state) render inside the
 * route-scoped CommandObsidianShell (dark "Obsidian night" first); the
 * public/guest audience keeps the approved reference chrome (top bar + chat
 * column, no shell). Chat behavior itself is untouched by the chrome.
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
vi.mock("@/components/command/CommandObsidianShell", () => ({
  CommandObsidianShell: ({ children, busy, leftOpen, rightOpen }: any) => (
    <div
      data-testid="command-obsidian-shell"
      data-busy={String(busy ?? false)}
      data-leftopen={String(leftOpen ?? true)}
      data-rightopen={String(rightOpen ?? true)}
    >
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

describe("/command chrome — CommandObsidianShell (slice C1)", () => {
  it("authenticated audience renders inside the Obsidian shell with rails open and idle status", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    const shell = await screen.findByTestId("command-obsidian-shell");
    expect(shell).toHaveAttribute("data-busy", "false");
    expect(shell).toHaveAttribute("data-leftopen", "true");
    expect(shell).toHaveAttribute("data-rightopen", "true");
  });

  it("public audience keeps the reference chrome — no Obsidian shell", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true }, 200);
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    expect(await screen.findByText("Sign up free")).toBeInTheDocument();
    expect(screen.queryByTestId("command-obsidian-shell")).not.toBeInTheDocument();
  });

  it("the transient checking state already sits in the shell (no layout jump on auth resolve)", async () => {
    // /me never resolves → audience stays "checking".
    fetchMock.mockImplementation(() => new Promise<ResponseLike>(() => undefined));

    render(<CommandPage />);

    await waitFor(() => {
      expect(screen.getByTestId("command-obsidian-shell")).toBeInTheDocument();
    });
  });
});
