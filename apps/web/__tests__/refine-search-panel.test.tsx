/**
 * apps/web/__tests__/refine-search-panel.test.tsx
 *
 * P1 (2026-07-19): the "Refine search" card is a structured open_drawer
 * action; this panel is the flow behind it. Pins:
 * - role prefill from the search context;
 * - only the composed natural-language query reaches onSubmit — never any
 *   UI wording ("Refine search" must not exist in the submitted text);
 * - city selection changes the composed query (All UAE default);
 * - empty role cannot submit;
 * - Arabic language composes an Arabic query with Arabic city names.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

let mockLanguage: "en" | "ar" = "en";
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: mockLanguage, setLanguage: vi.fn() }),
}));

import { buildRefinedQuery, RefineSearchPanel } from "@/components/command/RefineSearchPanel";

function setup(overrides: Partial<Parameters<typeof RefineSearchPanel>[0]> = {}) {
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    render(
        <RefineSearchPanel
            initialRole="HSE Manager"
            onSubmit={onSubmit}
            onClose={onClose}
            {...overrides}
        />,
    );
    return { onSubmit, onClose };
}

beforeEach(() => {
    mockLanguage = "en";
});

describe("RefineSearchPanel", () => {
    it("prefills the role from the search context", () => {
        setup();
        expect(screen.getByTestId("refine-role-input")).toHaveValue("HSE Manager");
    });

    it("submits a composed query for All UAE by default and closes", async () => {
        const user = userEvent.setup();
        const { onSubmit, onClose } = setup();
        await user.click(screen.getByTestId("refine-submit"));
        expect(onSubmit).toHaveBeenCalledOnce();
        expect(onSubmit).toHaveBeenCalledWith("Find HSE Manager jobs in the UAE");
        expect(onClose).toHaveBeenCalledOnce();
    });

    it("city selection changes the composed query", async () => {
        const user = userEvent.setup();
        const { onSubmit } = setup();
        await user.click(screen.getByTestId("refine-city-abu-dhabi"));
        await user.click(screen.getByTestId("refine-submit"));
        expect(onSubmit).toHaveBeenCalledWith("Find HSE Manager jobs in Abu Dhabi");
    });

    it("edited role flows into the query", async () => {
        const user = userEvent.setup();
        const { onSubmit } = setup();
        const input = screen.getByTestId("refine-role-input");
        await user.clear(input);
        await user.type(input, "ESG Manager");
        await user.click(screen.getByTestId("refine-city-dubai"));
        await user.click(screen.getByTestId("refine-submit"));
        expect(onSubmit).toHaveBeenCalledWith("Find ESG Manager jobs in Dubai");
    });

    it("never leaks UI wording into the submitted query (P1 pin)", async () => {
        const user = userEvent.setup();
        const { onSubmit } = setup();
        await user.click(screen.getByTestId("refine-submit"));
        const sent = String(onSubmit.mock.calls[0][0]).toLowerCase();
        expect(sent).not.toContain("refine");
        expect(sent).not.toContain("drawer");
    });

    it("empty role disables submit and never calls onSubmit", async () => {
        const user = userEvent.setup();
        const { onSubmit } = setup({ initialRole: "" });
        const submit = screen.getByTestId("refine-submit");
        expect(submit).toBeDisabled();
        await user.click(submit);
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("Enter in the role input submits", async () => {
        const user = userEvent.setup();
        const { onSubmit } = setup();
        await user.type(screen.getByTestId("refine-role-input"), "{Enter}");
        expect(onSubmit).toHaveBeenCalledOnce();
    });

    it("cancel closes without submitting", async () => {
        const user = userEvent.setup();
        const { onSubmit, onClose } = setup();
        await user.click(screen.getByTestId("refine-cancel"));
        expect(onClose).toHaveBeenCalledOnce();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("composes an Arabic query with Arabic city names when language=ar", async () => {
        mockLanguage = "ar";
        const user = userEvent.setup();
        const { onSubmit } = setup({ initialRole: "مدير سلامة" });
        await user.click(screen.getByTestId("refine-city-dubai"));
        await user.click(screen.getByTestId("refine-submit"));
        expect(onSubmit).toHaveBeenCalledWith("ابحث عن وظائف مدير سلامة في دبي");
    });
});

describe("buildRefinedQuery", () => {
    it("EN with and without city", () => {
        expect(buildRefinedQuery("en", " QHSE Engineer ", "Sharjah")).toBe("Find QHSE Engineer jobs in Sharjah");
        expect(buildRefinedQuery("en", "QHSE Engineer", null)).toBe("Find QHSE Engineer jobs in the UAE");
    });

    it("AR with and without city", () => {
        expect(buildRefinedQuery("ar", "مهندس بيئة", "عجمان")).toBe("ابحث عن وظائف مهندس بيئة في عجمان");
        expect(buildRefinedQuery("ar", "مهندس بيئة", null)).toBe("ابحث عن وظائف مهندس بيئة في الإمارات");
    });
});
