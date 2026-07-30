import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const langState = vi.hoisted(() => ({ current: "en" as "en" | "ar" }));
const setLanguage = vi.hoisted(() => vi.fn());

vi.mock("@/app/_atelier/atelier-tokens.css", () => ({}));
vi.mock("@/app/_atelier/atelier-support.css", () => ({}));

vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: langState.current, setLanguage }),
}));

import { AboutContent } from "@/app/about/AboutContent";

beforeEach(() => {
  langState.current = "en";
  setLanguage.mockClear();
});

describe("/about Atelier island", () => {
  it("renders the English public page content", () => {
    const { container } = render(<AboutContent />);

    expect(container.firstChild).toHaveClass("atelier", "atl-doc");
    expect(container.firstChild).toHaveAttribute("dir", "ltr");
    expect(container.firstChild).toHaveAttribute("lang", "en");

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

  it("toggles language to Arabic from the English page", () => {
    render(<AboutContent />);
    const toggle = screen.getByRole("button", { name: /Switch to Arabic/i });
    fireEvent.click(toggle);
    expect(setLanguage).toHaveBeenCalledWith("ar");
  });

  it("toggles language to English from the Arabic page", () => {
    langState.current = "ar";
    render(<AboutContent />);
    const toggle = screen.getByRole("button", { name: /Switch to English/i });
    fireEvent.click(toggle);
    expect(setLanguage).toHaveBeenCalledWith("en");
  });

  it("preserves expected navigation and CTA hrefs", () => {
    render(<AboutContent />);
    const hrefs = screen.getAllByRole("link").map((el) => el.getAttribute("href"));

    ["/", "/contact", "/faq", "/terms", "/privacy"].forEach((href) => {
      expect(hrefs).toContain(href);
    });
  });

  it("does not render legacy glass classes", () => {
    const { container } = render(<AboutContent />);
    expect(container.querySelector(".aura-glow")).not.toBeInTheDocument();
    expect(container.querySelector(".glass-panel")).not.toBeInTheDocument();
  });
});
