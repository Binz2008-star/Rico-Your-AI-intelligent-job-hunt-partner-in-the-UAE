import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import userEvent from "@testing-library/user-event";

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

function jsonResponse(body: JsonValue, status = 200): ResponseLike {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

type ResponseLike = {
  ok: boolean;
  status: number;
  json: () => Promise<JsonValue>;
};

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  localStorage.setItem("rico_sid", "test-session-01");
  vi.stubGlobal("fetch", fetchMock);
});

// ── Deterministic upload (TASK-20260717-001) ─────────────────────────────────
// The historical flake: the preview affordance ("Use this profile" / "Edit
// before saving") times out element-not-found (CI 2026-07-16 ×3, 2026-07-19
// ×2). In-session stress reproduction surfaced two independent causes, each
// cured separately:
//   1. LOST UPLOAD — a single dispatched upload can be dropped silently:
//      handleCVUpload returns early while chatAudience === "checking" (the
//      "Sign up free" pre-wait implies audience === "public" at ITS render,
//      but a late re-render can still race the upload), and an upload
//      dispatched onto a just-detached input during a composer re-render goes
//      nowhere. Cure: this helper retries the fresh-query → upload sequence
//      until the accepted upload's /api/v1/rico/upload-cv request is observed
//      on the fetch mock — an accepted upload issues it immediately.
//   2. CPU STARVATION — with the upload provably accepted, the preview card
//      can still take >5s to render on loaded runners (reproduced locally at
//      5.4s under parallel vitest load). Cure: 15s affordance timeouts under
//      a 30s per-test budget.
const uploadCvCalled = () =>
  fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/rico/upload-cv"));

async function uploadCVUntilAccepted() {
  const file = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });
  for (let attempt = 0; attempt < 20 && !uploadCvCalled(); attempt++) {
    const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    if (input) await userEvent.upload(input, file);
    if (uploadCvCalled()) break;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  expect(uploadCvCalled()).toBe(true);
}

describe("handleConfirmProfile", () => {
  it("calls confirm endpoint with proxy path, not absolute http URL", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true });
      }

      if (url.includes("/api/v1/rico/upload-cv")) {
        return jsonResponse({
          ok: true,
          status: "preview_ready",
          preview: {
            name: "Test",
            email: "t@t.com",
            phone: "0501234567",
            current_role: "HSE Manager",
            experience_years: 5,
            target_roles: [],
            skills_detected: ["hse"],
            existing_skills: [],
            skills: ["hse"],
            certifications: [],
            languages: [],
          },
          filename: "cv.pdf",
          extraction_quality: "good",
          user_id: "public:test-session-01",
        });
      }

      if (url.includes("/api/v1/rico/confirm-cv-profile")) {
        return jsonResponse({ ok: true, status: "confirmed", message: "Profile confirmed", profile: {} });
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    // Wait for the initial /me auth check to resolve out of the "checking"
    // audience before uploading — handleCVUpload silently drops files while
    // chatAudience === "checking", which would otherwise race this upload.
    await screen.findByText("Sign up free");

    await uploadCVUntilAccepted();

    await userEvent.click(await screen.findByText("Use this profile", {}, { timeout: 15000 }));

    await waitFor(() => {
      const confirmCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("confirm-cv-profile")
      );

      expect(confirmCall).toBeDefined();
      expect(String(confirmCall?.[0])).toMatch(
        /^\/proxy\/api\/v1\/rico\/confirm-cv-profile\?user_id=public%3Atest-session-01/
      );
      expect(String(confirmCall?.[0])).not.toMatch(/^http/);
    });
  }, 30000);
});

describe("Edit before saving", () => {
  it("does not call /chat/public when Edit button is clicked", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true });
      }

      if (url.includes("/api/v1/rico/upload-cv")) {
        return jsonResponse({
          ok: true,
          status: "preview_ready",
          preview: {
            name: "Test",
            email: "t@t.com",
            phone: "0501234567",
            current_role: null,
            experience_years: 3,
            target_roles: [],
            skills_detected: ["safety"],
            existing_skills: [],
            skills: ["safety"],
            certifications: [],
            languages: [],
          },
          filename: "cv.pdf",
          extraction_quality: "good",
          user_id: "public:test-session-01",
        });
      }

      if (url.includes("/api/v1/rico/chat/public")) {
        return jsonResponse({ reply: "unexpected" }, 500);
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    // Wait for the initial /me auth check to resolve out of the "checking"
    // audience before uploading — handleCVUpload silently drops files while
    // chatAudience === "checking", which would otherwise race this upload.
    await screen.findByText("Sign up free");

    await uploadCVUntilAccepted();

    const editButton = await screen.findByText("Edit before saving", {}, { timeout: 15000 });
    // Count everything except /api/v1/me: newly-mounted components re-check
    // auth via useAuth (one fetchMe per mount), so the raw call count is
    // timing-dependent. Edit must stay purely local for every OTHER endpoint.
    const nonAuthCalls = () =>
      fetchMock.mock.calls.filter(([url]) => !String(url).includes("/api/v1/me")).length;
    const callsBefore = nonAuthCalls();

    await userEvent.click(editButton);

    await waitFor(() => {
      expect(screen.getByText("Edit profile")).toBeInTheDocument();
    });

    expect(nonAuthCalls()).toBe(callsBefore);
    expect(screen.queryByText("Edit before saving")).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/rico/chat/public"))
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("confirm-cv-profile"))
    ).toBe(false);
  }, 30000);

  it("calls confirm-cv-profile with edited draft when Save profile is clicked", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);

      if (url.includes("/api/v1/me")) {
        return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true });
      }

      if (url.includes("/api/v1/rico/upload-cv")) {
        return jsonResponse({
          ok: true,
          status: "preview_ready",
          preview: {
            name: "",
            email: "t@t.com",
            phone: "0501234567",
            current_role: "",
            experience_years: 3,
            target_roles: [],
            skills_detected: ["safety"],
            existing_skills: [],
            skills: ["safety"],
            certifications: [],
            languages: [],
          },
          filename: "cv.pdf",
          extraction_quality: "good",
          user_id: "public:test-session-01",
        });
      }

      if (url.includes("/api/v1/rico/confirm-cv-profile")) {
        return jsonResponse({ ok: true, status: "confirmed", message: "Profile confirmed", profile: {} });
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    render(<CommandPage />);

    // Wait for the initial /me auth check to resolve out of the "checking"
    // audience before uploading — handleCVUpload silently drops files while
    // chatAudience === "checking", which would otherwise race this upload.
    await screen.findByText("Sign up free");

    await uploadCVUntilAccepted();

    await userEvent.click(await screen.findByText("Edit before saving", {}, { timeout: 15000 }));

    const nameInput = screen.getByLabelText("Name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Roben Edwan");

    await userEvent.click(screen.getByText("Save profile"));

    await waitFor(() => {
      const confirmCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("confirm-cv-profile")
      );

      expect(confirmCall).toBeDefined();
      const body = JSON.parse(String((confirmCall?.[1] as RequestInit | undefined)?.body ?? "{}"));
      expect(body.preview.name).toBe("Roben Edwan");
    });
  }, 30000);
});
