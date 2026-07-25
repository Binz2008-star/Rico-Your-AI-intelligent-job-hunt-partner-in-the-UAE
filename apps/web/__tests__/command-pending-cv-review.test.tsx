import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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

// The Vault (/upload) uploads and redirects to /command?cv=ready. The confirm
// card is a chat message built only by an in-chat upload, so that redirect used
// to land on a panel announcing "CV Profile Ready" while nothing had been read,
// nothing could be confirmed, and My Files still said "No files yet". These
// tests hold both directions closed: the surface may claim only what the server
// just returned, and it may never deny an upload that genuinely exists.

type JsonValue = Record<string, unknown>;
type ResponseLike = { ok: boolean; status: number; json: () => Promise<JsonValue> };

function jsonResponse(body: JsonValue, status = 200): ResponseLike {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

const PREVIEW = {
  name: "Dana Merrick",
  email: "r@example.com",
  phone: null,
  current_role: "Head of Compliance",
  experience_years: 10,
  target_roles: [],
  skills_detected: ["compliance", "audit"],
  existing_skills: [],
  skills: ["compliance", "audit"],
  certifications: [],
  languages: [],
};

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

/** Every request the authenticated /command mount makes, with the pending-CV
 *  answer under the test's control. Unknown URLs resolve empty rather than
 *  throwing, so an unrelated mount fetch can never masquerade as a failure of
 *  the behavior under test. */
function installMock(pending: { body: JsonValue; status?: number }): void {
  fetchMock.mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/api/v1/me")) {
      return jsonResponse({ authenticated: true, role: "user", email: "u@u.com" });
    }
    if (url.includes("/api/v1/rico/pending-cv-upload")) {
      return jsonResponse(pending.body, pending.status ?? 200);
    }
    if (url.includes("/api/v1/rico/confirm-cv-profile")) {
      return jsonResponse({ ok: true, status: "confirmed", message: "Profile confirmed", profile: {} });
    }
    return jsonResponse({});
  });
}

const pendingRequests = () =>
  fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/v1/rico/pending-cv-upload"));

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  localStorage.setItem("rico_sid", "test-session-01");
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState(null, "", "/command?cv=ready");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/command");
});

describe("/command?cv=ready — the pending CV review", () => {
  it("rebuilds the confirm card from the server's pending artifact", async () => {
    installMock({
      body: {
        pending: true,
        state: "pending",
        preview_available: true,
        upload_id: "11111111-2222-3333-4444-555555555555",
        filename: "Dana_Merrick_CV.pdf",
        doc_type: "cv",
        expires_at: "2026-07-25T18:30:00+00:00",
        preview: PREVIEW,
      },
    });
    render(<CommandPage />);

    // The card the Vault upload could never reach, with its confirm button.
    expect(await screen.findByRole("button", { name: /use this profile/i })).toBeInTheDocument();
    // …and the label that keeps it honest while it is unconfirmed.
    expect(screen.getByText(/CV under review/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not saved yet/i).length).toBeGreaterThan(0);
    // Retention is only defensible if the user can see how long it lasts.
    expect(screen.getByText(/preview available until/i)).toBeInTheDocument();
    // The old panel claimed a built profile for every visitor — it must not
    // appear for a CV that has not been saved.
    expect(screen.queryByText(/CV Profile Ready/i)).not.toBeInTheDocument();
  });

  it("asks the server once and renders one card per artifact", async () => {
    installMock({
      body: {
        pending: true,
        state: "pending",
        preview_available: true,
        upload_id: "11111111-2222-3333-4444-555555555555",
        filename: "Dana_Merrick_CV.pdf",
        doc_type: "cv",
        preview: PREVIEW,
      },
    });
    render(<CommandPage />);

    await screen.findByRole("button", { name: /use this profile/i });
    await waitFor(() => expect(pendingRequests().length).toBe(1));
    expect(screen.getAllByRole("button", { name: /use this profile/i })).toHaveLength(1);
  });

  it("claims nothing when there is no pending artifact", async () => {
    installMock({ body: { pending: false, state: "absent" } });
    render(<CommandPage />);

    // The ordinary welcome, not a CV announcement — this is the state in which
    // the banner used to appear beside an empty My Files.
    await waitFor(() => expect(pendingRequests().length).toBe(1));
    await waitFor(() =>
      expect(screen.queryByText(/CV Profile Ready/i)).not.toBeInTheDocument(),
    );
    expect(screen.queryAllByText(/not saved yet/i)).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /use this profile/i })).not.toBeInTheDocument();
  });

  it("says an expired preview lapsed, never that the CV is absent", async () => {
    installMock({
      body: {
        pending: false,
        state: "expired",
        filename: "Dana_Merrick_CV.pdf",
        message: "expired",
      },
    });
    render(<CommandPage />);

    const text = await screen.findByText(/expired before it was confirmed/i);
    expect(text).toBeInTheDocument();
    expect(screen.queryByText(/CV Profile Ready/i)).not.toBeInTheDocument();
  });

  it("never tells the user their upload is gone when the store is unreadable", async () => {
    installMock({
      body: { ok: false, state: "unavailable", error_code: "pending_upload_unavailable" },
      status: 503,
    });
    render(<CommandPage />);

    const text = await screen.findByText(/has not been lost/i);
    expect(text).toBeInTheDocument();
    expect(screen.queryByText(/CV Profile Ready/i)).not.toBeInTheDocument();
  });

  it("keeps ?cv=ready across a reload and drops it only once confirm succeeds", async () => {
    installMock({
      body: {
        pending: true,
        state: "pending",
        preview_available: true,
        upload_id: "11111111-2222-3333-4444-555555555555",
        filename: "Dana_Merrick_CV.pdf",
        doc_type: "cv",
        preview: PREVIEW,
      },
    });
    render(<CommandPage />);

    const confirm = await screen.findByRole("button", { name: /use this profile/i });
    // Still present while the review is outstanding: it is what carries the
    // pending card across a refresh, and clearing it early strands the artifact.
    expect(window.location.search).toContain("cv=ready");

    const { default: userEvent } = await import("@testing-library/user-event");
    await userEvent.setup().click(confirm);

    await waitFor(() => expect(window.location.search).not.toContain("cv=ready"));
  });

  it("shows the saved-profile panel only when the CV is actually saved", async () => {
    installMock({ body: { pending: false, state: "already_saved", filename: "Dana_Merrick_CV.pdf" } });
    render(<CommandPage />);

    expect(await screen.findByText(/CV Profile Ready/i)).toBeInTheDocument();
    // Nothing is outstanding, so no review-required label.
    expect(screen.queryAllByText(/not saved yet/i)).toHaveLength(0);
  });
});
