import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RicoReply } from "@/components/command/RicoReply";

/**
 * #1151 reply-presentation revision: Rico's answer is rendered as SAFE
 * structured markdown (react-markdown + remark-gfm + skipHtml, Atelier-styled),
 * not plain pre-wrapped text. These tests pin the user-visible upgrade —
 * hierarchy, lists, links, code, blockquotes — and the safety contract.
 */

const RICH = [
    "# Top heading",
    "",
    "## Section heading",
    "",
    "A paragraph with **bold** and *italic* and `inline code`.",
    "",
    "- first bullet",
    "- second bullet",
    "",
    "1. step one",
    "2. step two",
    "",
    "> a blockquote line",
    "",
    "```",
    "const x = 1;",
    "```",
    "",
    "See [Rico](https://ricohunt.com/jobs) for details.",
].join("\n");

describe("RicoReply structured markdown", () => {
    it("renders headings, lists, emphasis, code, and blockquote as real elements", () => {
        const { container } = render(<RicoReply text={RICH} />);

        expect(screen.getByRole("heading", { level: 1, name: "Top heading" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "Section heading" })).toBeInTheDocument();

        expect(container.querySelector("strong")).toHaveTextContent("bold");
        expect(container.querySelector("em")).toHaveTextContent("italic");

        // unordered + ordered lists with items
        const lists = container.querySelectorAll("ul, ol");
        expect(lists.length).toBe(2);
        expect(screen.getByText("first bullet").tagName).toBe("LI");
        expect(screen.getByText("step two").tagName).toBe("LI");

        // inline code + fenced block
        expect(container.querySelector("code")).toBeInTheDocument();
        expect(container.querySelector("pre")).toBeInTheDocument();
        expect(container.querySelector("pre")).toHaveTextContent("const x = 1;");

        // blockquote
        expect(container.querySelector("blockquote")).toHaveTextContent("a blockquote line");
    });

    it("renders links as sanitized, new-tab, noopener anchors", () => {
        render(<RicoReply text="See [Rico](https://ricohunt.com/jobs)." />);
        const link = screen.getByRole("link", { name: "Rico" });
        expect(link).toHaveAttribute("href", "https://ricohunt.com/jobs");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    });

    it("neutralizes dangerous link schemes (no javascript: href)", () => {
        const { container } = render(<RicoReply text="[click](javascript:alert(1))" />);
        // Not rendered as an anchor with the dangerous scheme.
        const anchor = container.querySelector("a");
        if (anchor) expect(anchor.getAttribute("href") ?? "").not.toContain("javascript:");
        expect(screen.getByText("click")).toBeInTheDocument();
    });

    it("drops raw HTML (skipHtml) so markup in the answer cannot inject elements", () => {
        const { container } = render(<RicoReply text={"Hello <img src=x onerror=alert(1)> world"} />);
        expect(container.querySelector("img")).toBeNull();
        expect(container.textContent).toContain("Hello");
        expect(container.textContent).toContain("world");
    });

    it("keeps the streaming caret while streaming and the Copy control once settled", () => {
        const { rerender } = render(<RicoReply text="## Answer\n\nBody." streaming />);
        expect(screen.getByTestId("transcript-streaming-caret")).toBeInTheDocument();

        rerender(<RicoReply text={"## Answer\n\nBody."} />);
        expect(screen.queryByTestId("transcript-streaming-caret")).toBeNull();
        expect(screen.getByText(/^Copy$/)).toBeInTheDocument();
    });

    it("still exposes prose under the serif contract the transcript relies on", () => {
        const { container } = render(<RicoReply text="Plain answer." streaming />);
        expect(container.querySelector(".serif")).not.toBeNull();
        expect(screen.getByText("Plain answer.").closest("p")).toHaveClass("serif");
    });
});
