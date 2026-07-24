import { GuardrailWarnings } from "@/components/shared/GuardrailWarnings";
import { WORKSPACE_THEME } from "@/components/workspace/theme";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

const sampleWarnings = [
    {
        code: "salary_missing",
        field: "salary",
        message: "Salary is not set.",
        suggestion: "Add your expected salary.",
        message_ar: "",
        suggestion_ar: "",
    },
];

/** Convert a hex color to the rgb(...) form jsdom uses inside color-mix(). */
function toRgb(hex: string): string {
    const n = parseInt(hex.slice(1), 16);
    return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

/** Canonicalise a CSS color value for comparison (hex, rgb, rgba). */
function canonicalColor(value: string): string {
    if (value.startsWith("rgba(")) {
        const parts = value.match(/rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)/);
        if (!parts) return value;
        return `rgba(${parts[1]}, ${parts[2]}, ${parts[3]}, ${Number(parts[4])})`;
    }
    if (value.startsWith("#")) {
        const n = parseInt(value.slice(1), 16);
        return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
    }
    return value;
}

describe("GuardrailWarnings palette awareness", () => {
    it("falls back to amber Tailwind classes when no palette is provided", () => {
        render(<GuardrailWarnings warnings={sampleWarnings} language="en" />);
        const alert = screen.getByRole("alert");
        expect(alert.className).toContain("bg-amber-400/10");
        expect(alert.className).toContain("border-amber-400/30");
        const message = screen.getByText("Salary is not set.");
        expect(message.className).toContain("text-amber-100");
    });

    it("uses WorkspacePalette colors in light mode", () => {
        const palette = WORKSPACE_THEME.light;
        render(<GuardrailWarnings warnings={sampleWarnings} language="en" palette={palette} />);
        const alert = screen.getByRole("alert");
        expect(alert.style.backgroundColor).toBe(
            `color-mix(in srgb, ${toRgb(palette.red)} 10%, ${toRgb(palette.panel)})`,
        );
        expect(alert.style.borderColor).toBe(
            `color-mix(in srgb, ${toRgb(palette.red)} 35%, transparent)`,
        );
        // Review correction: pure palette.red text only reaches 3.73:1 against
        // this alert's tinted background in light mode (below WCAG AA's 4.5:1
        // for 12px bold text) — the message color is darkened with a touch of
        // palette.ink to reach ~4.7-5:1 while still reading as red.
        const message = screen.getByText("Salary is not set.");
        expect(message.style.color).toBe(
            `color-mix(in srgb, ${toRgb(palette.ink)} 18%, ${toRgb(palette.red)})`,
        );
        const suggestion = screen.getByText("Add your expected salary.");
        expect(canonicalColor(suggestion.style.color)).toBe(canonicalColor(palette.ink55));
    });

    it("meets WCAG AA contrast (>=4.5:1) for message text against its own background in light mode", () => {
        // Guards the actual accessibility property, not just "some color changed" —
        // computed the same way a WCAG contrast checker would (relative luminance).
        function relLum([r, g, b]: [number, number, number]) {
            const lin = (c: number) => {
                const s = c / 255;
                return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
            };
            return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
        }
        function contrast(a: [number, number, number], b: [number, number, number]) {
            const [l1, l2] = [relLum(a), relLum(b)].sort((x, y) => y - x);
            return (l1 + 0.05) / (l2 + 0.05);
        }
        function hexToRgb(hex: string): [number, number, number] {
            const n = parseInt(hex.slice(1), 16);
            return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
        }
        function mix(hex1: string, hex2: string, pct1: number): [number, number, number] {
            const [r1, g1, b1] = hexToRgb(hex1);
            const [r2, g2, b2] = hexToRgb(hex2);
            const p = pct1 / 100;
            return [r1 * p + r2 * (1 - p), g1 * p + g2 * (1 - p), b1 * p + b2 * (1 - p)];
        }
        const palette = WORKSPACE_THEME.light;
        const bg = mix(palette.red, palette.panel, 10);
        const textColor = mix(palette.ink, palette.red, 18);
        expect(contrast(textColor, bg)).toBeGreaterThanOrEqual(4.5);
    });

    it("uses WorkspacePalette colors in dark mode", () => {
        const palette = WORKSPACE_THEME.dark;
        render(<GuardrailWarnings warnings={sampleWarnings} language="en" palette={palette} />);
        const alert = screen.getByRole("alert");
        expect(alert.style.backgroundColor).toBe(
            `color-mix(in srgb, ${toRgb(palette.red)} 10%, ${toRgb(palette.panel)})`,
        );
        const message = screen.getByText("Salary is not set.");
        expect(canonicalColor(message.style.color)).toBe(canonicalColor(palette.red));
    });

    it("renders Arabic localized text when palette is provided", () => {
        const palette = WORKSPACE_THEME.light;
        const arWarnings = [
            {
                ...sampleWarnings[0],
                message_ar: "الراتب غير محدد.",
                suggestion_ar: "أضف راتبك المتوقع.",
            },
        ];
        render(<GuardrailWarnings warnings={arWarnings} language="ar" palette={palette} />);
        expect(screen.getByText("الراتب غير محدد.")).toBeInTheDocument();
        expect(screen.getByText("أضف راتبك المتوقع.")).toBeInTheDocument();
    });
});
