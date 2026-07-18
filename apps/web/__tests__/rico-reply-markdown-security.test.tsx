import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RicoReply } from "@/components/command/RicoReply";
import { RicoReplyMarkdown } from "@/components/command/RicoReplyMarkdown";

/**
 * #1151 mandatory security + streaming gate for the structured reply renderer.
 *
 * The renderer is safe *by construction*: react-markdown with `skipHtml` (raw
 * HTML nodes are dropped — no dangerouslySetInnerHTML anywhere) plus a link
 * ALLOWLIST (`safeHref` permits only http/https/mailto/relative; every other
 * scheme, including obfuscated/encoded ones, becomes an inert <span>). These
 * tests pin that contract so a future refactor can't silently open an XSS hole,
 * and prove partial streaming markdown never throws.
 */

// ---------------------------------------------------------------------------
// 1. Raw HTML is never executed / injected (skipHtml)
// ---------------------------------------------------------------------------
describe("RicoReplyMarkdown — raw HTML is inert", () => {
    it("drops <script> tags (no <script> element, no execution surface)", () => {
        const { container } = render(<RicoReplyMarkdown text={"Before <script>window.__pwned=1</script> after"} />);
        expect(container.querySelector("script")).toBeNull();
        // The document was never mutated by an inline handler.
        expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
        expect(container.textContent).toContain("Before");
        expect(container.textContent).toContain("after");
    });

    it("drops event-handler-bearing tags like <img onerror=…>", () => {
        const { container } = render(<RicoReplyMarkdown text={"x <img src=q onerror=alert(1)> y"} />);
        expect(container.querySelector("img")).toBeNull();
        expect(container.querySelector("[onerror]")).toBeNull();
    });

    it("cannot inject arbitrary classes, inline styles, or raw elements", () => {
        const { container } = render(
            <RicoReplyMarkdown
                text={'<div class="evil-injected">a</div>\n\n<span style="position:fixed;inset:0">b</span>'}
            />,
        );
        // No raw div/span carrying attacker-chosen class or style survived.
        expect(container.querySelector(".evil-injected")).toBeNull();
        expect(container.querySelector('[style*="fixed"]')).toBeNull();
        expect(container.querySelector("style")).toBeNull();
        // Every element that IS present comes from our component map — spot-check
        // that no element carries an inline style attribute at all.
        expect(container.querySelector("[style]")).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// 2. Dangerous URL schemes are blocked; safe ones are sanitized
// ---------------------------------------------------------------------------
describe("RicoReplyMarkdown — link scheme allowlist", () => {
    const dangerous: Array<[string, string]> = [
        ["javascript:", "[click](javascript:alert(1))"],
        ["entity-encoded javascript", "[click](java&#115;cript:alert(1))"],
        ["colon-entity javascript", "[click](javascript&#58;alert(1))"],
        ["data: html", "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"],
        ["vbscript:", "[click](vbscript:msgbox(1))"],
        ["file:", "[click](file:///etc/passwd)"],
    ];

    it.each(dangerous)("neutralizes %s into an inert span (no executable href)", (_label, md) => {
        const { container } = render(<RicoReplyMarkdown text={md} />);
        const anchor = container.querySelector("a");
        if (anchor) {
            const href = anchor.getAttribute("href") ?? "";
            expect(href).not.toMatch(/^(javascript|data|vbscript|file):/i);
        }
        // Label text still shown to the user, just not clickable.
        expect(screen.getByText("click")).toBeInTheDocument();
    });

    it("keeps normal https links clickable, new-tab, and rel-hardened", () => {
        render(<RicoReplyMarkdown text={"See [Rico](https://ricohunt.com/jobs)."} />);
        const link = screen.getByRole("link", { name: "Rico" });
        expect(link).toHaveAttribute("href", "https://ricohunt.com/jobs");
        expect(link).toHaveAttribute("target", "_blank");
        // Safe rel: both noopener and noreferrer.
        const rel = link.getAttribute("rel") ?? "";
        expect(rel).toContain("noopener");
        expect(rel).toContain("noreferrer");
    });

    it("allows mailto and in-app relative links, still rel-hardened", () => {
        const { container } = render(
            <RicoReplyMarkdown text={"[mail](mailto:a@b.com) and [jobs](/jobs)"} />,
        );
        const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
        expect(hrefs).toContain("mailto:a@b.com");
        expect(hrefs).toContain("/jobs");
        container.querySelectorAll("a").forEach((a) => {
            expect(a.getAttribute("rel") ?? "").toContain("noopener");
        });
    });
});

// ---------------------------------------------------------------------------
// 3. Incomplete streaming markdown must never crash
// ---------------------------------------------------------------------------
describe("RicoReplyMarkdown — partial streaming input is safe", () => {
    const partials: Array<[string, string, string]> = [
        ["unmatched bold marker", "Analysis: **strong start", "strong start"],
        ["incomplete link", "See [Rico", "Rico"],
        ["incomplete inline code", "Value is `x", "x"],
        ["incomplete fenced code block", "```\nconst x = 1;", "const x = 1;"],
        ["lone heading hash mid-stream", "## Se", "Se"],
        ["unterminated emphasis", "a _partial", "partial"],
    ];

    it.each(partials)("renders %s without throwing", (_label, md, visible) => {
        let container: HTMLElement | null = null;
        expect(() => {
            container = render(<RicoReplyMarkdown text={md} />).container;
        }).not.toThrow();
        expect(container!.textContent).toContain(visible);
    });

    it("renders the same partials through the full RicoReply while streaming", () => {
        for (const [, md] of partials) {
            expect(() => render(<RicoReply text={md} streaming />)).not.toThrow();
        }
    });
});

// ---------------------------------------------------------------------------
// 4. Copy/Regenerate operate on the ORIGINAL raw answer; motion contracts hold
// ---------------------------------------------------------------------------
describe("RicoReply — copy/regenerate/streaming contracts", () => {
    let writeText: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            value: { writeText },
            configurable: true,
        });
    });
    afterEach(() => {
        vi.restoreAllMocks();
    });

    const RAW = "## Heading\n\nBody with **bold**, a `code` chip and [a link](https://ricohunt.com).";

    it("Copy writes the ORIGINAL raw markdown, not the rendered text", () => {
        render(<RicoReply text={RAW} />);
        fireEvent.click(screen.getByRole("button", { name: "Copy" }));
        expect(writeText).toHaveBeenCalledTimes(1);
        expect(writeText).toHaveBeenCalledWith(RAW); // raw string, markdown syntax intact
    });

    it("Regenerate invokes the original callback unchanged", () => {
        const onRegenerate = vi.fn();
        render(<RicoReply text={RAW} canRegenerate onRegenerate={onRegenerate} />);
        fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
        expect(onRegenerate).toHaveBeenCalledTimes(1);
    });

    it("hides Copy/Regenerate while streaming and shows the caret", () => {
        render(<RicoReply text={RAW} canRegenerate onRegenerate={() => {}} streaming />);
        expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
        expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
        expect(screen.getByTestId("transcript-streaming-caret")).toBeInTheDocument();
    });

    it("streaming caret honours reduced motion (motion-reduce disables the blink)", () => {
        render(<RicoReply text={RAW} streaming />);
        const caret = screen.getByTestId("transcript-streaming-caret");
        expect(caret.className).toContain("animate-caret");
        expect(caret.className).toContain("motion-reduce:animate-none");
    });

    it("Copy reflects the current answer text (memo/dep correctness)", () => {
        // Independent renders: the button briefly shows "Copied" after a click,
        // so we don't re-query the same instance — we prove each mounted reply
        // copies its own text.
        const first = render(<RicoReply text={"first"} />);
        fireEvent.click(screen.getByRole("button", { name: "Copy" }));
        expect(writeText).toHaveBeenLastCalledWith("first");
        first.unmount();

        render(<RicoReply text={"second"} />);
        fireEvent.click(screen.getByRole("button", { name: "Copy" }));
        expect(writeText).toHaveBeenLastCalledWith("second");
    });
});
