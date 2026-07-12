import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * ProfileAtelier (PR 5B) — read "working portrait" + inline Edit mode wired to
 * the real fetchProfile()/updateProfile() endpoints. Replaces the removed
 * per-field inline-edit tests (the previous /profile UI they asserted no longer
 * exists).
 */

const { fetchProfile, updateProfile } = vi.hoisted(() => ({
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchProfile, updateProfile };
});

import { ProfileAtelier } from "@/components/workspace/ProfileAtelier";
import { WorkspaceThemeContext, WORKSPACE_THEME } from "@/components/workspace/theme";

function renderInTheme() {
  return render(
    <WorkspaceThemeContext.Provider value={WORKSPACE_THEME.light}>
      <ProfileAtelier />
    </WorkspaceThemeContext.Provider>,
  );
}

const PROFILE = {
  profile_exists: true,
  name: "Layla Al-Marri",
  current_role: "Senior Product Manager",
  industries: ["Fintech"],
  target_roles: ["Product Lead"],
  preferred_cities: ["Dubai"],
  salary_expectation_aed: 42000,
  years_experience: 6,
  skills: ["Payments"],
  completeness_score: 0.82,
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("ProfileAtelier", () => {
  it("renders the working portrait from real profile data", async () => {
    fetchProfile.mockResolvedValue(PROFILE);
    renderInTheme();
    await screen.findByText("Layla Al-Marri");
    expect(screen.getByText(/Senior Product Manager/)).toBeInTheDocument();
    expect(screen.getByText("Payments")).toBeInTheDocument();
    expect(screen.getByText("Product Lead")).toBeInTheDocument();
    // Read mode — no Save button until Edit is pressed.
    expect(screen.queryByText("Save changes")).toBeNull();
  });

  it("Edit reveals inputs and Save PATCHes only the changed field", async () => {
    fetchProfile.mockResolvedValue(PROFILE);
    updateProfile.mockResolvedValue({ status: "ok", updated_fields: ["name"] });
    const user = userEvent.setup();
    renderInTheme();
    await screen.findByText("Layla Al-Marri");

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const nameInput = screen.getByDisplayValue("Layla Al-Marri");
    await user.clear(nameInput);
    await user.type(nameInput, "Layla A. Al-Marri");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    // Only the changed field is sent (name), not the untouched ones.
    expect(updateProfile).toHaveBeenCalledWith({ name: "Layla A. Al-Marri" });
  });

  it("does not PATCH when Save is pressed with no changes", async () => {
    fetchProfile.mockResolvedValue(PROFILE);
    const user = userEvent.setup();
    renderInTheme();
    await screen.findByText("Layla Al-Marri");
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(updateProfile).not.toHaveBeenCalled();
  });
});
