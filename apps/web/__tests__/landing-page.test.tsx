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
  it("renders the cinematic Rico AI landing hierarchy", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        name: /Rico AI is your autonomous career operating system/i,
      })
    ).toBeInTheDocument();
    expect(screen.getByText("How Rico works")).toBeInTheDocument();
    expect(screen.getByText("What Rico remembers")).toBeInTheDocument();
    expect(screen.getByText("Opportunity engine")).toBeInTheDocument();
    expect(screen.getByText("You stay in control")).toBeInTheDocument();
  });

  it("preserves the primary onboarding and auth links", () => {
    render(<LandingPage />);

    expect(screen.getByRole("link", { name: /Sign in/i })).toHaveAttribute("href", "/login");
    expect(
      screen.getAllByRole("link", { name: /Sign up free/i }).some((link) => link.getAttribute("href") === "/signup")
    ).toBe(true);
    expect(
      screen.getAllByRole("link", { name: /Upload your CV/i }).some((link) => link.getAttribute("href") === "/upload")
    ).toBe(true);
  });
});
