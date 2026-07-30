import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const langState = vi.hoisted(() => ({ current: "en" as "en" | "ar" }));

vi.mock("@/app/_atelier/atelier-tokens.css", () => ({}));
vi.mock("@/app/_atelier/atelier-support.css", () => ({}));

vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: langState.current, setLanguage: vi.fn() }),
}));

import { AboutContent } from "@/app/about/AboutContent";

beforeEach(() => {
  langState.current = "en";
});

describe("/about Atelier island", () => {
  it("renders the English public page content", () => {
    const { container } = render(<AboutContent />);

    expect(container.firstChild).toHaveClass("atelier", "atl-doc");
    expect(container.firstChild).toHaveAttribute("dir", "ltr");

    expect(screen.getByText(/Our Story/i)).toBeInTheDocument();
    expect(screen.getByText(/Built for the UAE job market/i)).toBeInTheDocument();
    expect(screen.getByText(/We're a small team and we read every message/i)).toBeInTheDocument();

    const cta = screen.getByRole("link", { name: /Send a message/i });
    expect(cta).toHaveAttribute("href", "/contact");
  });

  it("renders the Arabic RTL page content", () => {
    langState.current = "ar";
    const { container } = render(<AboutContent />);

    expect(container.firstChild).toHaveAttribute("dir", "rtl");
    expect(container.firstChild).toHaveAttribute("lang", "ar");

    expect(screen.getByText(/قصتنا/)).toBeInTheDocument();
    expect(screen.getByText(/بُني لسوق العمل في الإمارات/)).toBeInTheDocument();
    expect(screen.getByText(/نحن فريق صغير ونقرأ كل رسالة/)).toBeInTheDocument();

    const cta = screen.getByRole("link", { name: /أرسل رسالة/ });
    expect(cta).toHaveAttribute("href", "/contact");
  });

  it("does not import legacy glass components", () => {
    const { container } = render(<AboutContent />);
    expect(container.querySelector(".aura-glow")).not.toBeInTheDocument();
    expect(container.querySelector(".glass-panel")).not.toBeInTheDocument();
  });
});
