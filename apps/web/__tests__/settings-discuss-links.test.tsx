import { fireEvent, screen } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * "Discuss with Rico" affordances on /settings.
 *
 * These links are the conversational entry point, NOT an execution path: the
 * chat has no mutation for match selectivity / daily limit / keywords (verified
 * in src/rico_chat_api.py — see the 2026-07-12 handoff), so the label must not
 * claim Rico will change the setting, and the href must be the real one-shot
 * /command?q=<prompt> deep link. This pins both facts.
 */

const { getSettings, getTelegramStatus, fetchProfile } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  getTelegramStatus: vi.fn(),
  fetchProfile: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, getSettings, getTelegramStatus, fetchProfile };
});

import { SettingsAtelier } from "@/components/settings/SettingsAtelier";

const USER = { user_id: "u@test.com", name: "Layla", email: "layla@test.com" };
const q = (prompt: string) => `/command?q=${encodeURIComponent(prompt)}`;

beforeEach(() => {
  vi.clearAllMocks();
  getSettings.mockResolvedValue({
    include_keywords: [],
    exclude_keywords: [],
    min_score: 65,
    max_daily_applies: 5,
    telegram_chat_id: "",
    score_threshold_apply: 80,
    score_threshold_watch: 60,
  });
  getTelegramStatus.mockResolvedValue({ opted_in: false, telegram_username: null });
  fetchProfile.mockResolvedValue({ profile_exists: true, email: "layla@test.com", name: "Layla", phone: "" });
});
afterEach(() => vi.clearAllMocks());

describe("/settings — Discuss with Rico links", () => {
  it("Account tab deep-links to /command?q= (not an execution claim)", async () => {
    render(<SettingsAtelier user={USER} />);
    const link = await screen.findByRole("link", { name: /Discuss your details with Rico/i });
    expect(link).toHaveAttribute("href", q("Help me update my account details."));
    // The corrected copy must never re-introduce an execution claim.
    expect(screen.queryByText(/Ask Rico to/i)).toBeNull();
  });

  it("Preferences tab: matching + daily links point at /command?q= and claim no execution", async () => {
    render(<SettingsAtelier user={USER} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Preferences" }));

    const matchLink = await screen.findByRole("link", { name: /Discuss matching with Rico/i });
    expect(matchLink).toHaveAttribute("href", q("Help me decide how strict my job matching should be."));

    const dailyLink = screen.getByRole("link", { name: /Discuss your daily pace with Rico/i });
    expect(dailyLink).toHaveAttribute("href", q("Help me decide how many roles to act on each day."));

    // No over-claiming labels anywhere on the panel.
    expect(screen.queryByText(/Ask Rico to make this stricter/i)).toBeNull();
  });

  it("Notifications tab deep-links to /command?q=", async () => {
    render(<SettingsAtelier user={USER} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Notifications" }));
    const link = await screen.findByRole("link", { name: /Discuss notifications with Rico/i });
    expect(link).toHaveAttribute("href", q("Help me set up how you notify me about new roles."));
  });
});
