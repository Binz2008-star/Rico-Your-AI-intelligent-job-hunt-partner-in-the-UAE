import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Auth guard for authenticated-only account pages (/settings, /profile,
 * /applications).
 *
 * Confirmed production bugs this pins:
 *  - guest direct access to /settings rendered the private AppShell
 *  - guest direct access to /profile fired a private request and showed a
 *    misleading connection error
 *
 * Required behavior:
 *  - wait for auth readiness; render a neutral loader (AuthGate) meanwhile
 *  - guest → /login?next=<encoded path>, never the private shell, no private API
 *  - authenticated users retain normal access
 */

const { replace, push, pathnameMock } = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  pathnameMock: vi.fn(() => "/"),
}));
const authState = vi.hoisted(() => ({ current: { user: null as unknown, ready: false, logout: vi.fn() } }));
const { getSettings, getTelegramStatus, fetchProfile, getApplications, getApplicationStats } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  getTelegramStatus: vi.fn(),
  fetchProfile: vi.fn(),
  getApplications: vi.fn(),
  getApplicationStats: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push, refresh: vi.fn() }),
  usePathname: () => pathnameMock(),
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => authState.current,
}));
// Mock the private shell so a test can distinguish "private shell rendered"
// from the neutral AuthGate without pulling in the whole sidebar tree.
vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, getSettings, getTelegramStatus, fetchProfile, getApplications, getApplicationStats };
});

import SettingsPage from "@/app/settings/page";
import ProfilePage from "@/app/profile/page";
import ApplicationsPage from "@/app/applications/page";

function asGuest() {
  authState.current = { user: null, ready: true, logout: vi.fn() };
}
function asChecking() {
  authState.current = { user: null, ready: false, logout: vi.fn() };
}
function asAuthed() {
  authState.current = {
    user: { user_id: "u@test.com", name: "u", email: "u@test.com" },
    ready: true,
    logout: vi.fn(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getSettings.mockResolvedValue({ include_keywords: [], exclude_keywords: [], min_score: 0, max_daily_applies: 0, telegram_chat_id: "" });
  getTelegramStatus.mockResolvedValue({ opted_in: false, telegram_username: null });
  fetchProfile.mockResolvedValue({ profile_exists: false, email: "u@test.com" });
  getApplications.mockResolvedValue({ applications: [], total: 0 });
  getApplicationStats.mockResolvedValue({ total: 0 });
});
afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("/settings auth guard", () => {
  beforeEach(() => pathnameMock.mockReturnValue("/settings"));

  it("redirects a guest to /login with the return path and never renders the shell or fires the API", async () => {
    asGuest();
    render(<SettingsPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fsettings"));
    // /settings uses the WorkspaceShell (Shell C); its <main> landmark stands in
    // for "private shell rendered". The neutral loader renders no <main>.
    expect(screen.queryByRole("main")).toBeNull();
    expect(getSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows a neutral loader while auth is still resolving (no shell, no API, no redirect)", async () => {
    asChecking();
    render(<SettingsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("main")).toBeNull();
    expect(getSettings).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders the page and loads settings for an authenticated user", async () => {
    asAuthed();
    render(<SettingsPage />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("/applications auth guard", () => {
  beforeEach(() => pathnameMock.mockReturnValue("/applications"));

  it("redirects a guest to /login with the return path and never renders the shell or fires the API", async () => {
    asGuest();
    render(<ApplicationsPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fapplications"));
    // /applications uses the WorkspaceShell (Shell C); its <main> landmark
    // stands in for "private shell rendered". The neutral loader has no <main>.
    expect(screen.queryByRole("main")).toBeNull();
    expect(getApplications).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows a neutral loader while auth is still resolving (no shell, no API, no redirect)", async () => {
    asChecking();
    render(<ApplicationsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("main")).toBeNull();
    expect(getApplications).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders the page and loads applications for an authenticated user", async () => {
    asAuthed();
    render(<ApplicationsPage />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    await waitFor(() => expect(getApplications).toHaveBeenCalled());
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("/profile auth guard", () => {
  beforeEach(() => pathnameMock.mockReturnValue("/profile"));

  it("redirects a guest to /login with the return path and never fires the profile request", async () => {
    asGuest();
    render(<ProfilePage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fprofile"));
    expect(screen.queryByTestId("app-shell")).toBeNull();
    expect(fetchProfile).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows a neutral loader while auth is still resolving (no shell, no request, no redirect)", async () => {
    asChecking();
    render(<ProfilePage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByTestId("app-shell")).toBeNull();
    expect(fetchProfile).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders the page and loads the profile for an authenticated user", async () => {
    asAuthed();
    render(<ProfilePage />);
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    await waitFor(() => expect(fetchProfile).toHaveBeenCalled());
    expect(replace).not.toHaveBeenCalled();
  });
});
