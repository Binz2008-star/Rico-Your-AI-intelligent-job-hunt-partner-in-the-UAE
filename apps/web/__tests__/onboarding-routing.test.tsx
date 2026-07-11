import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

/**
 * /onboarding routing + guard behavior (DEC-20260710-004).
 *
 * The onboarding page routes on the backend-owned completion signal from
 * GET /api/v1/onboarding/status (`complete`) — never on `profile_exists`, and
 * it never re-implements completion rules. These tests pin:
 *   - completed / legacy-complete → /command
 *   - incomplete (even with profile_exists=true) → onboarding UI
 *   - unauthenticated → signup with return path
 *   - status failure → recoverable UI (Retry / Continue to Rico), no loop
 *   - skip → /command without a completion mutation
 *   - submit success → /command; submit failure → no success, stays on form
 *   - valid CV vs non-CV rejection
 *   - EN/AR + RTL
 */

const { push, replace } = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const { fetchOnboardingStatus, uploadCV, submitOnboarding, confirmCVProfile } = vi.hoisted(() => ({
  fetchOnboardingStatus: vi.fn(),
  uploadCV: vi.fn(),
  submitOnboarding: vi.fn(),
  confirmCVProfile: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, refresh: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchOnboardingStatus, uploadCV, submitOnboarding, confirmCVProfile };
});

import OnboardingPage from "@/app/onboarding/page";

const STATUS = {
  completed: { status: "completed", complete: true, source: "persisted", missing_fields: [], profile_exists: true, profile_completeness: 1 },
  legacyComplete: { status: "completed", complete: true, source: "derived_legacy", missing_fields: [], profile_exists: true, profile_completeness: 1 },
  // profile_exists TRUE but complete FALSE — the trap the correction guards against.
  partialExists: { status: "in_progress", complete: false, source: "persisted", missing_fields: ["preferred_cities"], profile_exists: true, profile_completeness: 0.4 },
  pendingShell: { status: "pending", complete: false, source: "derived_legacy", missing_fields: ["target_roles", "preferred_cities", "years_experience", "skills"], profile_exists: false, profile_completeness: 0 },
} as const;

const CV_PARSED = {
  ok: true,
  status: "preview_ready",
  document_type: "cv",
  filename: "cv.pdf",
  upload_id: "artifact-uuid-1",
  parsed: { text: "", emails: [], phones: [], skills: ["Python"], certifications: [], languages: [] },
  preview: {
    name: "Test User",
    email: null,
    phone: null,
    current_role: "Engineer",
    experience_years: 5,
    target_roles: ["Backend Engineer"],
    skills_detected: ["Python"],
    existing_skills: [],
    skills: ["Python"],
    certifications: [],
    languages: [],
  },
};

async function renderIncompleteReachForm() {
  fetchOnboardingStatus.mockResolvedValue(STATUS.partialExists);
  uploadCV.mockResolvedValue(CV_PARSED);
  const utils = render(<OnboardingPage />);
  await screen.findByText("Start with your CV");
  const input = utils.container.querySelector("#cv-upload") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "cv.pdf", { type: "application/pdf" })] } });
  await screen.findByText("Profile extracted");
  return utils;
}

beforeEach(() => {
  vi.clearAllMocks();
  // LanguageContext persists to localStorage; reset so an Arabic test does not
  // leak the language into a later English assertion.
  localStorage.clear();
});
afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("onboarding completion guard", () => {
  it("routes a completed (persisted) user to /command", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.completed);
    render(<OnboardingPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/command"));
  });

  it("routes a legacy-complete user (source=derived_legacy) to /command", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.legacyComplete);
    render(<OnboardingPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/command"));
  });

  it("keeps a profile_exists=true but incomplete user on onboarding (routes on complete, not profile_exists)", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.partialExists);
    render(<OnboardingPage />);
    await screen.findByText("Start with your CV");
    expect(replace).not.toHaveBeenCalledWith("/command");
    expect(push).not.toHaveBeenCalledWith("/command");
  });

  it("redirects an unauthenticated user to signup with the return path", async () => {
    fetchOnboardingStatus.mockRejectedValue(new ApiError("Not authenticated", 401));
    render(<OnboardingPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/signup?next=%2Fonboarding"));
  });

  it("shows a recoverable state on status failure without looping, then Retry recovers", async () => {
    fetchOnboardingStatus.mockRejectedValue(new ApiError("internal", 503));
    render(<OnboardingPage />);
    await screen.findByText("We couldn't load your setup");
    // No redirect happened — no loop, no completion assumption.
    expect(replace).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    fetchOnboardingStatus.mockResolvedValueOnce(STATUS.completed);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/command"));
  });

  it("'Continue to Rico' on the failure card routes to /command without any completion write", async () => {
    fetchOnboardingStatus.mockRejectedValue(new ApiError("internal", 503));
    render(<OnboardingPage />);
    await screen.findByText("We couldn't load your setup");
    fireEvent.click(screen.getByRole("button", { name: "Continue to Rico" }));
    expect(push).toHaveBeenCalledWith("/command");
    expect(submitOnboarding).not.toHaveBeenCalled();
  });
});

describe("onboarding CV upload + form", () => {
  it("accepts a valid CV and advances to the extracted-data form", async () => {
    await renderIncompleteReachForm();
    expect(screen.getByText("Profile extracted")).toBeInTheDocument();
  });

  it("rejects a non-CV classified upload and stays on the upload step", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.partialExists);
    uploadCV.mockResolvedValue({ ok: true, status: "classified", document_type: "job_description" });
    const { container } = render(<OnboardingPage />);
    await screen.findByText("Start with your CV");
    const input = container.querySelector("#cv-upload") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "jd.pdf", { type: "application/pdf" })] } });
    await screen.findByText(/doesn't look like a CV/i);
    expect(screen.getByText("Start with your CV")).toBeInTheDocument();
  });

  it("skip routes to /command WITHOUT persisting onboarding or confirming the CV", async () => {
    await renderIncompleteReachForm();
    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(push).toHaveBeenCalledWith("/command");
    expect(submitOnboarding).not.toHaveBeenCalled();
    expect(confirmCVProfile).not.toHaveBeenCalled();
  });

  it("submit success routes to /command", async () => {
    await renderIncompleteReachForm();
    submitOnboarding.mockResolvedValue({ status: "completed", updated_fields: ["skills"] });
    fireEvent.click(screen.getByRole("button", { name: /Complete profile/i }));
    await waitFor(() => expect(submitOnboarding).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/command"));
  });

  it("'Complete My Profile' confirms the uploaded CV through the SAME canonical path /command uses, BEFORE submitOnboarding", async () => {
    // #963: onboarding's explicit confirmation action must call
    // confirm-cv-profile with the extracted preview/filename/upload_id, and
    // it must run before submitOnboarding so a user-edited field (written by
    // submitOnboarding) always overwrites the extracted one, never the
    // reverse.
    await renderIncompleteReachForm();
    submitOnboarding.mockResolvedValue({ status: "completed", updated_fields: ["skills"] });
    fireEvent.click(screen.getByRole("button", { name: /Complete profile/i }));
    await waitFor(() => expect(confirmCVProfile).toHaveBeenCalled());
    await waitFor(() => expect(submitOnboarding).toHaveBeenCalled());

    expect(confirmCVProfile).toHaveBeenCalledWith({
      preview: CV_PARSED.preview,
      filename: CV_PARSED.filename,
      doc_type: "cv",
      upload_id: CV_PARSED.upload_id,
    });
    const confirmOrder = confirmCVProfile.mock.invocationCallOrder[0];
    const submitOrder = submitOnboarding.mock.invocationCallOrder[0];
    expect(confirmOrder).toBeLessThan(submitOrder);
  });

  it("onboarding submit fails safely if confirmCVProfile fails (e.g. rejected artifact)", async () => {
    // #975 blocker 1: confirm-cv-profile now rejects an untrusted artifact
    // with a non-200. The onboarding handler must fail safely: no
    // submitOnboarding call, no /command navigation, no false completion --
    // the user stays on the form with the error surfaced, exactly like any
    // other confirm failure.
    await renderIncompleteReachForm();
    confirmCVProfile.mockRejectedValueOnce(
      new ApiError("Please upload the CV again before confirming.", 409),
    );
    fireEvent.click(screen.getByRole("button", { name: /Complete profile/i }));
    await waitFor(() => expect(confirmCVProfile).toHaveBeenCalled());
    expect(submitOnboarding).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalledWith("/command");
    expect(screen.getByText("Please upload the CV again before confirming.")).toBeInTheDocument();
  });

  it("submit failure keeps the form and shows no success state", async () => {
    await renderIncompleteReachForm();
    submitOnboarding.mockRejectedValue(new Error("save failed"));
    fireEvent.click(screen.getByRole("button", { name: /Complete profile/i }));
    await waitFor(() => expect(submitOnboarding).toHaveBeenCalled());
    expect(push).not.toHaveBeenCalledWith("/command");
    // Stays on the form and surfaces the failure — no success state.
    expect(screen.getByText("Profile extracted")).toBeInTheDocument();
    expect(screen.getByText("save failed")).toBeInTheDocument();
  });
});

describe("onboarding i18n / RTL", () => {
  it("switches to Arabic and mirrors the island to RTL", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.partialExists);
    const { container } = render(<OnboardingPage />);
    await screen.findByText("Start with your CV");

    fireEvent.click(screen.getByRole("button", { name: "عربي" }));
    const island = container.querySelector(".atl-onb") as HTMLElement;
    await waitFor(() => expect(island.getAttribute("dir")).toBe("rtl"));
    expect(screen.getByText("ابدأ بسيرتك الذاتية")).toBeInTheDocument();
  });

  it("exposes a keyboard-focusable file input on the upload step", async () => {
    fetchOnboardingStatus.mockResolvedValue(STATUS.pendingShell);
    const { container } = render(<OnboardingPage />);
    await screen.findByText("Start with your CV");
    const input = container.querySelector("#cv-upload") as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input.type).toBe("file");
    input.focus();
    expect(input).toHaveFocus();
  });
});
