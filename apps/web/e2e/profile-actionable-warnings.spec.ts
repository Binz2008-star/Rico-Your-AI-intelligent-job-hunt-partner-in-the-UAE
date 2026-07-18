/**
 * apps/web/e2e/profile-actionable-warnings.spec.ts
 * Playwright E2E for the actionable profile warnings panel (Profile Phase 4B)
 * on /profile. All backend calls are mocked — no real API, no credentials.
 * Captures review screenshots (desktop EN + AR RTL); screenshots are written
 * to PROFILE_WARN_SHOT_DIR (or a local untracked default) and never committed.
 *
 * Run:
 *   cd apps/web
 *   npx playwright test profile-actionable-warnings --project=chromium
 */
import { expect, test, type Page } from "@playwright/test";

const PROXY = "/proxy/api/v1";
const SHOT_DIR = process.env.PROFILE_WARN_SHOT_DIR || "e2e/screenshots/profile-warnings";

const WARNINGS = [
    {
        code: "too_many_target_roles",
        field: "target_roles",
        severity: "recommendation",
        message: "You have 5 target roles.",
        suggestion: "Choose up to 3 primary roles.",
        message_ar: "لديك 5 أدوار مستهدفة.",
        suggestion_ar: "اختر حتى 3 أدوار اساسية.",
    },
    {
        code: "minimum_fit_score_high",
        field: "min_score",
        severity: "important",
        message: "Minimum fit score is 80%.",
        suggestion: "Use 60% or lower.",
        message_ar: "الحد الادنى لدرجة الملاءمة هو 80%.",
        suggestion_ar: "استخدم 60% أو أقل.",
    },
    {
        code: "invalid_uae_city",
        field: "preferred_cities",
        severity: "blocking",
        message: "City value 'Cairo' is not recognized as a UAE city.",
        suggestion: "Choose a UAE city such as Dubai or Abu Dhabi.",
        message_ar: "قيمة المدينة 'Cairo' ليست مدينة إماراتية معروفة.",
        suggestion_ar: "اختر مدينة إماراتية مثل دبي أو أبو ظبي.",
    },
];

const PROFILE = {
    profile_exists: true,
    email: "synthetic@test.dev",
    user_id: "synthetic-user",
    name: "Maryam Haddad",
    phone: "+971500000000",
    telegram_username: "maryam_test",
    target_roles: ["Data Analyst"],
    preferred_cities: ["Cairo"],
    salary_expectation_aed: 20000,
    minimum_salary_aed: 15000,
    skills: ["SQL", "Python"],
    visa_status: "Employment visa",
    notice_period: "30 days",
    years_experience: 6,
    current_role: "Analyst",
    current_company: "Synthetic Co",
    linkedin_url: "https://linkedin.com/in/synthetic",
    completeness_score: 82,
    warnings: WARNINGS,
};

async function mockBackend(page: Page) {
    // Catch-all FIRST so specific routes below (added later) take precedence.
    await page.route(`${PROXY}/**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    await page.route(`${PROXY}/me`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                email: "synthetic@test.dev",
                role: "user",
                authenticated: true,
                name: "Maryam",
            }),
        }),
    );
    await page.route(`${PROXY}/rico/profile`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(PROFILE) }),
    );
    await page.route(`${PROXY}/user/files**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ files: [], total: 0 }) }),
    );
    await page.route(`${PROXY}/subscription/me`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                subscription: {
                    user_id: "synthetic-user",
                    plan: "free",
                    subscription_status: "inactive",
                    paddle_customer_id: null,
                    paddle_subscription_id: null,
                    current_period_start: null,
                    current_period_end: null,
                    cancel_at: null,
                    canceled_at: null,
                    entitlements: {},
                    updated_at: "2026-07-03T00:00:00Z",
                },
                plan: null,
                is_active: false,
            }),
        }),
    );
}

test.describe("actionable profile warnings", () => {
    test("desktop EN: three tiers render, field jump focuses the exact field", async ({ page }) => {
        await mockBackend(page);
        await page.goto("/profile");

        const panel = page.getByRole("region", { name: /affecting your job matches/ });
        await expect(panel).toBeVisible();
        await expect(panel.getByText("3 items are affecting your job matches")).toBeVisible();

        // severity order: blocking first
        const items = panel.getByRole("listitem");
        await expect(items).toHaveCount(3);
        await expect(items.nth(0)).toHaveAttribute("data-warning-severity", "blocking");
        await expect(items.nth(0).getByText("Blocking")).toBeVisible();
        await expect(items.nth(2)).toHaveAttribute("data-warning-severity", "recommendation");

        // blocking has no Review later; non-blocking does
        await expect(items.nth(0).getByRole("button", { name: "Review later" })).toHaveCount(0);
        await expect(items.nth(2).getByRole("button", { name: "Review later" })).toBeVisible();

        await page.screenshot({ path: `${SHOT_DIR}/desktop-en-panel.png`, fullPage: true });

        // field jump: navigates to ?section=goals and focuses the field container
        await panel.getByRole("button", { name: "Go to Cities" }).click();
        await expect(page).toHaveURL(/section=goals/);
        await expect(page.getByRole("heading", { name: "Career goals" })).toBeVisible();
        const anchor = page.locator("#profile-field-preferred_cities");
        await expect(anchor).toBeFocused();
        await page.screenshot({ path: `${SHOT_DIR}/desktop-en-field-focus.png`, fullPage: true });
    });

    test("AR RTL: Arabic summary and messages render in a rtl document", async ({ page }) => {
        await mockBackend(page);
        await page.addInitScript(() => window.localStorage.setItem("rico-language", "ar"));
        await page.goto("/profile");

        await expect(page.getByText("3 أمور تؤثر على مطابقة الوظائف")).toBeVisible();
        await expect(page.getByText("قيمة المدينة 'Cairo' ليست مدينة إماراتية معروفة.")).toBeVisible();
        await expect(page.locator("[dir=rtl]").first()).toBeVisible();
        await page.screenshot({ path: `${SHOT_DIR}/desktop-ar-panel.png`, fullPage: true });
    });
});
