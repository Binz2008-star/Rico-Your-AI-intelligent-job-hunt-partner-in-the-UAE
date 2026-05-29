import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider } from "@/contexts/ThemeContext";
import { ThemeToggle } from "@/components/ThemeToggle";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = "";
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle (Rico Site v2)", () => {
  it("defaults to dark and offers to switch to light", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );
    // Dark is the default → the control invites switching to light.
    expect(screen.getByLabelText("Switch to light mode")).toBeInTheDocument();
  });

  it("toggles to light, applies the .light class, and persists the choice", async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    await userEvent.click(screen.getByLabelText("Switch to light mode"));

    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("rico-theme")).toBe("light");
    // Control now invites switching back to dark.
    expect(screen.getByLabelText("Switch to dark mode")).toBeInTheDocument();
  });

  it("renders without crashing when no ThemeProvider is mounted (safe fallback)", () => {
    render(<ThemeToggle />);
    // Fallback resolves dark → still shows the 'switch to light' affordance.
    expect(screen.getByLabelText("Switch to light mode")).toBeInTheDocument();
  });
});
