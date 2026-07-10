import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import LandingPage from "@/components/LandingPage";
import { LanguageProvider } from "@/contexts/LanguageContext";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

function renderWithLanguage(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

describe("LandingPage", () => {
  it("renders the hero headline and human-friendly copy", () => {
    renderWithLanguage(<LandingPage />);

    // Hero headline (h1)
    expect(
      screen.getByRole("heading", {
        name: /Smarter UAE job hunting starts with your CV\./i,
      })
    ).toBeInTheDocument();
    // Problem/solution section headline
    expect(screen.getByText("Stop guessing which jobs fit you.")).toBeInTheDocument();
    // Three value-proposition cards
    expect(screen.getByText("Find better matches")).toBeInTheDocument();
    expect(screen.getByText("Know why they fit")).toBeInTheDocument();
    expect(screen.getByText("Track every move")).toBeInTheDocument();
    // Pricing + final CTA headlines
    expect(screen.getByText("Start free. Upgrade only when Rico helps.")).toBeInTheDocument();
    expect(screen.getByText("Upload your CV. Rico will show you what fits.")).toBeInTheDocument();
    // Bilingual / trust copy
    expect(screen.getByText("English + Arabic")).toBeInTheDocument();
    expect(
      screen.getByText("You stay in control. Rico never applies without your approval.")
    ).toBeInTheDocument();
  });

  it("preserves the primary onboarding and auth links", () => {
    renderWithLanguage(<LandingPage />);

    expect(screen.getByRole("link", { name: /Sign in/i })).toHaveAttribute("href", "/login");
    expect(
      screen.getAllByRole("link", { name: /Upload your CV/i }).some((link) => link.getAttribute("href") === "/upload")
    ).toBe(true);
    expect(
      screen.getAllByRole("link", { name: /Start free/i }).some((link) => link.getAttribute("href") === "/signup")
    ).toBe(true);
  });
});
