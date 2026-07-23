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
        const message = screen.getByText("Salary is not set.");
        expect(canonicalColor(message.style.color)).toBe(canonicalColor(palette.red));
        const suggestion = screen.getByText("Add your expected salary.");
        expect(canonicalColor(suggestion.style.color)).toBe(canonicalColor(palette.ink55));
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
