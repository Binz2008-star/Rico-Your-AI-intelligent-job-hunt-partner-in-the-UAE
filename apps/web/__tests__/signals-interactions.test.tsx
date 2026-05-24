import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/components/layout/TopNav", () => ({ TopNav: () => <div /> }));
vi.mock("@/components/layout/Navigation", () => ({ Navigation: () => <div /> }));
vi.mock("@/components/ui/AuraGlow", () => ({ AuraGlow: () => <div /> }));
vi.mock("@/components/ui/GlassPanel", () => ({ GlassPanel: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div> }));
vi.mock("@/components/ui/MaterialIcon", () => ({ MaterialIcon: ({ icon }: { icon: string }) => <span>{icon}</span> }));

vi.mock("@/hooks/useOrchestration", () => ({
  useOrchestration: () => ({
    isLoading: false,
    error: null,
    refetchSignals: vi.fn(),
    signals: [
      {
        id: "job-1",
        company: "Renew",
        role: "HSE Manager- Manufacturing",
        matchScore: 86,
        momentum: "high",
        location: "Dubai, UAE",
        timestamp: "2026-05-24T00:00:00.000Z",
        applyUrl: "https://example.com/apply",
        whyItFits: "Your HSE and manufacturing safety background fits this role.",
        missingFacts: ["Confirm salary range"],
        source: "Rico job search",
      },
    ],
  }),
}));

import SignalsPage from "@/app/signals/page";

describe("Signals interactions", () => {
  it("opens a detail drawer and exposes job-context actions", () => {
    render(<SignalsPage />);

    fireEvent.click(screen.getByRole("button", { name: /HSE Manager- Manufacturing/i }));

    expect(screen.getAllByText("HSE Manager- Manufacturing").length).toBeGreaterThan(1);
    expect(screen.getByText("Renew · Dubai, UAE")).toBeInTheDocument();
    expect(screen.getByText("Confirm salary range")).toBeInTheDocument();
    expect(screen.getAllByText("View job")[0]).toHaveAttribute("href", "https://example.com/apply");
    expect(screen.getAllByText("Prepare application")[0].closest("a")).toHaveAttribute(
      "href",
      expect.stringContaining("Prepare%20application")
    );
    expect(screen.getAllByText("Mark as applied")[0].closest("a")).toHaveAttribute(
      "href",
      expect.stringContaining("HSE%20Manager-")
    );
    expect(screen.queryByText("Live backend signal")).not.toBeInTheDocument();
  });
});
