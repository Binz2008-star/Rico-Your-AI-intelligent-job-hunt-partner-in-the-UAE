import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import LandingPage from "@/components/LandingPage";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("LandingPage", () => {
  it("renders the hero headline and human-friendly copy", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        name: /Upload your CV\.\s+Let Rico run your job search smarter\./i,
      })
    ).toBeInTheDocument();
    expect(screen.getByText("How Rico works")).toBeInTheDocument();
    // Five-step flow with plain job-seeker language (step titles; "Upload your CV" also appears in CTA buttons)
    expect(screen.getAllByText("Upload your CV").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Build your career profile")).toBeInTheDocument();
    expect(screen.getByText("Find matching UAE jobs")).toBeInTheDocument();
    expect(screen.getByText("Track your applications")).toBeInTheDocument();
    expect(screen.getByText("Get guidance and alerts")).toBeInTheDocument();
    // Section labels
    expect(screen.getByText("Rico remembers your career goals")).toBeInTheDocument();
    expect(screen.getByText("Smart job matching")).toBeInTheDocument();
    expect(screen.getByText("You stay in control")).toBeInTheDocument();
    // Bilingual / trust copy
    expect(screen.getAllByText(/in English and Arabic/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Rico never applies silently/i).length).toBeGreaterThanOrEqual(1);
  });

  it("preserves the primary onboarding and auth links", () => {
    render(<LandingPage />);

    expect(screen.getByRole("link", { name: /Sign in/i })).toHaveAttribute("href", "/login");
    expect(
      screen.getAllByRole("link", { name: /Upload your CV/i }).some((link) => link.getAttribute("href") === "/upload")
    ).toBe(true);
    expect(
      screen.getAllByRole("link", { name: /Start free/i }).some((link) => link.getAttribute("href") === "/signup")
    ).toBe(true);
  });
});
