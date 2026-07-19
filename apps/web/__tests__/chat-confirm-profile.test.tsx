import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, screen, waitFor } from "@testing-library/react";
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

// ── Deterministic upload via a DEFERRED response (TASK-20260717-001) ──────────
// Root cause of the historical flake (CI 2026-07-16 ×3, 2026-07-19 ×4; the
// preview affordance "Use this profile" / "Edit before saving" timing out
// element-not-found): a bimodal LOST RENDER, not a slow one. The guest mount
// "welcome" effect ends in setMessages([welcome]) — a REPLACE, not an append
// (app/command/page.tsx). Under parallel-vitest CPU oversubscription that
// effect can land AFTER the upload's preview append and wipe it, so the card
// never appears — no timeout cures it (proven: a 40s findByText still failed,
// running the full 40s). The old retry loop guarded the wrong condition (it
// re-uploaded until the /upload-cv *request* was observed, but the loss happens
// AFTER, in response handling), and 8/8 in isolation vs ~1/4 under nproc*2 CPU
// hogs confirmed it is purely an ordering race.
//
// Cure — remove all wall-clock dependence by controlling the response ordering:
//   1. Mock is installed before render; the /upload-cv response is a DEFERRED
//      promise the test releases explicitly.
//   2. Wait for the welcome to render first — that proves the welcome effect
//      already ran (it is one-shot via promptSentRef), so it can no longer
//      REPLACE-wipe a later preview append.
//   3. Dispatch the upload and assert its request left (deterministic; the
//      accepted upload issues fetch synchronously).
//   4. Release the deferred response inside act() so the preview setMessages is
//      a single ordered flush, never a race with a mount effect.
//   5. Await the preview card AND its final content, not merely the request.
// No retries, no sleeps, no inflated timeouts — modest budgets suffice because
// the render is now race-free and therefore guaranteed to arrive.

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

// One-shot gate that defers the /upload-cv response for the current test.
let uploadGate: Deferred<void>;

function installMock(preview: JsonValue): void {
  fetchMock.mockImplementation(async (input) => {
    const url = String(input);

    if (url.includes("/api/v1/me")) {
      return jsonResponse({ authenticated: false, role: "guest", email: null, guest: true });
    }

    if (url.includes("/api/v1/rico/upload-cv")) {
      // Deferred: the response is released by the test, inside act(), only once
      // the mount welcome effect has provably already run.
      await uploadGate.promise;
      return jsonResponse({
        ok: true,
        status: "preview_ready",
        preview,
        filename: "cv.pdf",
        extraction_quality: "good",
        user_id: "public:test-session-01",
      });
    }

    if (url.includes("/api/v1/rico/confirm-cv-profile")) {
      return jsonResponse({ ok: true, status: "confirmed", message: "Profile confirmed", profile: {} });
    }

    if (url.includes("/api/v1/rico/chat/public")) {
      return jsonResponse({ reply: "unexpected" }, 500);
    }

    throw new Error(`Unhandled fetch: ${url}`);
  });
}

const uploadCvRequested = () =>
  fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/rico/upload-cv"));

// Matches the DEEPEST element whose text contains `substr` (a plain textContent
// includes-check also matches every ancestor, which throws "multiple elements").
const deepestWithText = (substr: string) => (_content: string, node: Element | null) => {
  if (!node) return false;
  if (!(node.textContent ?? "").includes(substr)) return false;
  return Array.from(node.children).every((c) => !(c.textContent ?? "").includes(substr));
};

// Deterministically drive an upload to a rendered preview card. See the block
// comment above for why each step is ordered exactly this way.
async function uploadAndRenderPreview(): Promise<void> {
  // 1. Mount fully settled: the public welcome has painted, so the one-shot
  //    welcome effect (setMessages([welcome]) REPLACE) has already fired and can
  //    no longer wipe the preview we are about to append.
  await screen.findByText(/Hi, I'm Rico/, {}, { timeout: 5000 });

  // 2. Dispatch the upload. The accepted upload issues its /upload-cv request
  //    synchronously; the response stays parked on uploadGate.
  const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
  expect(input).not.toBeNull();
  await userEvent.upload(
    input as HTMLInputElement,
    new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" }),
  );

  // 3. Prove the request left before releasing the response — no dependence on
  //    render timing.
  await waitFor(() => expect(uploadCvRequested()).toBe(true), { timeout: 5000 });

  // 4. Release the deferred response inside act() so the preview setMessages
  //    flushes as one ordered update, not a wall-clock race with mount effects.
  await act(async () => {
    uploadGate.resolve();
    await uploadGate.promise;
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  localStorage.setItem("rico_sid", "test-session-01");
  vi.stubGlobal("fetch", fetchMock);
  uploadGate = deferred<void>();
});

afterEach(() => {
  // Release any still-parked gate so a failed test cannot leave the component's
  // handleCVUpload suspended on a never-settling promise, then unmount and drop
  // the fetch stub so no timer/promise leaks across into the next test.
  uploadGate?.resolve();
  cleanup();
  vi.unstubAllGlobals();
});

describe("handleConfirmProfile", () => {
  it("calls confirm endpoint with proxy path, not absolute http URL", async () => {
    installMock({
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
    });

    render(<CommandPage />);

    await uploadAndRenderPreview();

    // Preview card AND its final content (the parsed role), not just the request.
    const useThisProfile = await screen.findByText("Use this profile", {}, { timeout: 5000 });
    expect(screen.getByText(deepestWithText("HSE Manager"))).toBeInTheDocument();

    await userEvent.click(useThisProfile);

    await waitFor(() => {
      const confirmCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("confirm-cv-profile"),
      );

      expect(confirmCall).toBeDefined();
      expect(String(confirmCall?.[0])).toMatch(
        /^\/proxy\/api\/v1\/rico\/confirm-cv-profile\?user_id=public%3Atest-session-01/,
      );
      expect(String(confirmCall?.[0])).not.toMatch(/^http/);
    });
  });
});

describe("Edit before saving", () => {
  it("does not call /chat/public when Edit button is clicked", async () => {
    installMock({
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
    });

    render(<CommandPage />);

    await uploadAndRenderPreview();

    const editButton = await screen.findByText("Edit before saving", {}, { timeout: 5000 });
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
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/rico/chat/public")),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("confirm-cv-profile")),
    ).toBe(false);
  });

  it("calls confirm-cv-profile with edited draft when Save profile is clicked", async () => {
    installMock({
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
    });

    render(<CommandPage />);

    await uploadAndRenderPreview();

    await userEvent.click(await screen.findByText("Edit before saving", {}, { timeout: 5000 }));

    const nameInput = screen.getByLabelText("Name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Roben Edwan");

    await userEvent.click(screen.getByText("Save profile"));

    await waitFor(() => {
      const confirmCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("confirm-cv-profile"),
      );

      expect(confirmCall).toBeDefined();
      const body = JSON.parse(String((confirmCall?.[1] as RequestInit | undefined)?.body ?? "{}"));
      expect(body.preview.name).toBe("Roben Edwan");
    });
  });
});
