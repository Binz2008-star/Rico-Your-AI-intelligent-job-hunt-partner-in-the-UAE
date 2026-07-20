/**
 * apps/web/__tests__/command-v5-foundation.test.tsx
 *
 * Command Workspace v5 — PR 1 foundation guards:
 * 1. Drift guard: components/workspace/v5/motion.css (`.wsx5` custom
 *    properties) and tokens.ts (V5) must define the SAME colors — the CSS is
 *    what ships, the TS module is what code composes with.
 * 2. AA spot checks: the audited text pairs stay above WCAG AA thresholds
 *    (full gate: scripts/check-contrast-v5.mjs).
 * 3. RicoPresence: state/size attributes, status semantics, decorative mode.
 * 4. Mode accent map: all seven modes present; text accents come from the
 *    AA text-safe set only.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
    V5,
    V5_MODE_ACCENTS,
    V5ModeKey,
} from "@/components/workspace/v5/tokens";
import { RicoPresence } from "@/components/workspace/v5/RicoPresence";

type RGBA = [number, number, number, number];

function parseColor(value: string): RGBA | null {
    const hex = value.trim().match(/^#([0-9a-f]{6})$/i);
    if (hex) {
        const n = parseInt(hex[1], 16);
        return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
    }
    const rgba = value
        .trim()
        .match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)$/);
    if (rgba) return [+rgba[1], +rgba[2], +rgba[3], +rgba[4]];
    return null; // gradients etc. — not color literals
}

function cssVars(): Record<string, string> {
    const css = readFileSync(
        join(__dirname, "..", "components", "workspace", "v5", "motion.css"),
        "utf8",
    );
    const block = css.match(/\.wsx5\s*\{([\s\S]*?)\n\}/);
    if (!block) throw new Error("motion.css: .wsx5 token block not found");
    const out: Record<string, string> = {};
    for (const m of block[1].matchAll(/--wsx5-([\w-]+):\s*([^;]+);/g)) {
        out[m[1]] = m[2].trim();
    }
    return out;
}

describe("v5 foundation tokens", () => {
    it("motion.css and tokens.ts agree on every color token", () => {
        const vars = cssVars();
        for (const [key, tsValue] of Object.entries(V5)) {
            const tsColor = parseColor(tsValue);
            expect(tsColor, `V5.${key} should be a color literal`).not.toBeNull();
            expect(vars[key], `motion.css is missing --wsx5-${key}`).toBeDefined();
            const cssColor = parseColor(vars[key]);
            expect(cssColor, `--wsx5-${key} should be a color literal`).not.toBeNull();
            for (let i = 0; i < 4; i++) {
                expect(
                    Math.abs((tsColor as RGBA)[i] - (cssColor as RGBA)[i]),
                    `--wsx5-${key} drifted from V5.${key} (channel ${i})`,
                ).toBeLessThan(0.011);
            }
        }
    });

    it("audited text pairs stay above WCAG AA", () => {
        const lum = ([r, g, b]: number[]) => {
            const f = (c: number) => {
                const s = c / 255;
                return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
            };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
        };
        const over = (fg: RGBA, bg: RGBA) => fg.map((c, i) => (i < 3 ? c * fg[3] + bg[i] * (1 - fg[3]) : 1)) as RGBA;
        const ratio = (fgV: string, bgV: string) => {
            const bg = parseColor(bgV)!;
            const fg = over(parseColor(fgV)!, bg);
            const [l1, l2] = [lum(fg), lum(bg)];
            const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
            return (hi + 0.05) / (lo + 0.05);
        };
        expect(ratio(V5.ink55, V5.paper)).toBeGreaterThanOrEqual(4.5);
        expect(ratio(V5.terraText, V5.paper)).toBeGreaterThanOrEqual(4.5);
        expect(ratio(V5.electricText, V5.paper)).toBeGreaterThanOrEqual(4.5);
        expect(ratio(V5.lightInk58, V5.deepPanel2)).toBeGreaterThanOrEqual(4.5);
        expect(ratio(V5.onEmber, V5.emberBtnEnd)).toBeGreaterThanOrEqual(4.5);
    });

    it("mode accent map covers all seven modes with AA text accents only", () => {
        const modes: V5ModeKey[] = [
            "overview",
            "search",
            "applications",
            "documents",
            "interview",
            "learning",
            "activity",
        ];
        const textSafe = new Set<string>([
            V5.terraText,
            V5.amberText,
            V5.goldText,
            V5.electricText,
            V5.purpleText,
        ]);
        for (const m of modes) {
            const a = V5_MODE_ACCENTS[m];
            expect(a, `missing accents for mode ${m}`).toBeDefined();
            expect(textSafe.has(a.modeAText), `${m}.modeAText must be an AA text-safe token`).toBe(true);
        }
        expect(Object.keys(V5_MODE_ACCENTS)).toHaveLength(modes.length);
    });
});

describe("RicoPresence", () => {
    it("renders a polite status with a per-state default label", () => {
        render(<RicoPresence state="thinking" />);
        const el = screen.getByRole("status");
        expect(el).toHaveAttribute("aria-label", "Rico is thinking");
        expect(el).toHaveAttribute("data-state", "thinking");
        expect(el).toHaveAttribute("data-size", "md");
        expect(el.className).toContain("wsx5-orb");
    });

    it("accepts a localized label override", () => {
        render(<RicoPresence state="acting" label="ريكو يعمل الآن" />);
        expect(screen.getByRole("status")).toHaveAttribute("aria-label", "ريكو يعمل الآن");
    });

    it("decorative mode hides the orb from assistive tech", () => {
        const { container } = render(<RicoPresence state="ready" decorative />);
        expect(screen.queryByRole("status")).toBeNull();
        const el = container.querySelector(".wsx5-orb");
        expect(el).toHaveAttribute("aria-hidden", "true");
    });

    it("renders every state and size without crashing", () => {
        for (const state of ["ready", "thinking", "acting", "completed", "warning"] as const) {
            for (const size of ["sm", "md", "lg"] as const) {
                const { unmount, container } = render(<RicoPresence state={state} size={size} decorative />);
                const el = container.querySelector(".wsx5-orb");
                expect(el).toHaveAttribute("data-state", state);
                expect(el).toHaveAttribute("data-size", size);
                unmount();
            }
        }
    });
});
