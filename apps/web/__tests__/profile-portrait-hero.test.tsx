/**
 * ProfileAtelier portrait — hero badges + Career section (Profile Dashboard
 * Atelier slice).
 *
 * Contracts:
 *  1. Hero metric badges derive from REAL ProfileResponse fields only
 *     (years experience, target-role count, visa, notice) and render nothing
 *     when the facts are absent — no fabricated summary data.
 *  2. Career is its own editorial section (role, company, experience,
 *     industries) and is hidden entirely when no career facts exist.
 *  3. Identity keeps name/email; salaries stay in Job Preferences (pinned by
 *     the existing profile-atelier integration test as well).
 *  4. The single Edit button still fires onEdit — the one edit entry point.
 */

import { ProfileAtelier } from "@/components/profile/ProfileAtelier";
import type { ProfileResponse } from "@/lib/api";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/theme", async () => {
    const actual = await vi.importActual<typeof import("@/components/workspace/theme")>(
        "@/components/workspace/theme",
    );
    return { ...actual, useWorkspaceTheme: () => actual.WORKSPACE_THEME.light };
});
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: "en" }),
}));

const FULL: ProfileResponse = {
    profile_exists: true,
    name: "Roben Edwan",
    email: "user@example.com",
    current_role: "Founder & General Manager",
    current_company: "Eco Technology",
    years_experience: 10,
    target_roles: ["HSE Manager", "ESG Manager", "Quality Manager"],
    preferred_cities: ["Dubai", "Abu Dhabi"],
    salary_expectation_aed: 25000,
    minimum_salary_aed: 15000,
    skills: ["ISO 14001", "NEBOSH"],
    industries: ["Environmental", "Oil & Gas"],
    visa_status: "Investor Visa",
    notice_period: "Immediate",
    completeness_score: 0.72,
};

const MINIMAL: ProfileResponse = {
    profile_exists: true,
    name: "New User",
    email: "new@example.com",
};

describe("ProfileAtelier — hero badges", () => {
    it("derives badges from real fields: experience, target-role count, visa, notice", () => {
        render(<ProfileAtelier profile={FULL} onEdit={() => {}} />);
        const badges = screen.getAllByTestId("profile-hero-badge").map((b) => b.textContent);
        expect(badges).toEqual([
            "10 yrs experience",
            "3 target roles",
            "Investor Visa",
            "Immediate",
        ]);
    });

    it("renders no badges when the facts are absent", () => {
        render(<ProfileAtelier profile={MINIMAL} onEdit={() => {}} />);
        expect(screen.queryAllByTestId("profile-hero-badge")).toHaveLength(0);
    });
});

describe("ProfileAtelier — Career section", () => {
    it("groups role, company, experience, and industries under Career", () => {
        render(<ProfileAtelier profile={FULL} onEdit={() => {}} />);
        const career = screen.getByTestId("profile-career-plate");
        expect(career.textContent).toContain("Career");
        expect(career.textContent).toContain("Founder & General Manager");
        expect(career.textContent).toContain("Eco Technology");
        expect(career.textContent).toContain("10");
        expect(career.textContent).toContain("Environmental");
        expect(career.textContent).toContain("Oil & Gas");
    });

    it("hides the Career plate entirely when no career facts exist", () => {
        render(<ProfileAtelier profile={MINIMAL} onEdit={() => {}} />);
        expect(screen.queryByTestId("profile-career-plate")).toBeNull();
    });

    it("keeps Identity (name/email) and Job Preferences (salaries) intact", () => {
        render(<ProfileAtelier profile={FULL} onEdit={() => {}} />);
        expect(screen.getByRole("heading", { name: "Roben Edwan" })).toBeTruthy();
        expect(screen.getByText("user@example.com")).toBeTruthy();
        expect(screen.getByText("25,000 AED")).toBeTruthy();
        expect(screen.getByText("15,000 AED")).toBeTruthy();
    });
});

describe("ProfileAtelier — single edit entry point", () => {
    it("fires onEdit from the hero Edit button", () => {
        const onEdit = vi.fn();
        render(<ProfileAtelier profile={FULL} onEdit={onEdit} />);
        screen.getByRole("button", { name: "Edit profile" }).click();
        expect(onEdit).toHaveBeenCalledTimes(1);
    });
});
