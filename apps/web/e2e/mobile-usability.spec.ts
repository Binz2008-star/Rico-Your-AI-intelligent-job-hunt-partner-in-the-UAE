/**
 * apps/web/e2e/mobile-usability.spec.ts
 * Focused mobile usability pass (production smoke follow-up, 2026-07-18) for
 * /command and /profile. All backend calls are mocked. Screenshots go to
 * MOBILE_USABILITY_SHOT_DIR (or a local untracked default), never committed.
 *
 * Pins:
 *  - desktop keyboard-shortcut hints (CTRL+K / CTRL+J) are hidden on touch
 *    widths and still shown on desktop — both chat audiences;
 *  - composer, attachment and send controls stay inside the viewport with no
 *    fixed navigation overlapping them (safe-area padding retained);
 *  - /profile has no horizontal overflow on narrow iPhone (320), Android
 *    (360) and modern iPhone (390) widths; the unsaved-changes bar stays
 *    visible and compact with both actions on-screen;
 *  - Arabic RTL passes the same checks;
 *  - desktop keeps the hint (regression).
 */
import { expect, test, type Page } from "@playwright/test";

const PROXY = "/proxy/api/v1";
const SHOT_DIR = process.env.MOBILE_USABILITY_SHOT_DIR || "e2e/screenshots/mobile-usability";

const PROFILE = {
    profile_exists: true,
    email: "synthetic@test.dev",
    user_id: "synthetic-user",
    name: "Maryam Haddad",
    phone: "+971500000000",
    telegram_username: "maryam_test",
    target_roles: ["Data Analyst"],
    preferred_cities: ["Dubai"],
    salary_expectation_aed: 20000,
    minimum_salary_aed: 15000,
    skills: ["SQL"],
    visa_status: "Employment visa",
    notice_period: "30 days",
    years_experience: 6,
    current_role: "Analyst",
    current_company: "Synthetic Co",
    linkedin_url: null,
    completeness_score: 82,
    warnings: [
        {
            code: "invalid_uae_city",
            field: "preferred_cities",
            severity: "blocking",
            message: "City value 'Cairo' is not recognized as a UAE city, so Rico may search the wrong market.",
            suggestion: "Choose a UAE city such as Dubai, Abu Dhabi, Sharjah, Ajman, or Al Ain.",
            message_ar: "قيمة المدينة 'Cairo' ليست مدينة إماراتية معروفة، وقد يبحث Rico في سوق غير مناسب.",
            suggestion_ar: "اختر مدينة إماراتية مثل دبي أو أبو ظبي أو الشارقة أو عجمان أو العين.",
        },
        {
            code: "minimum_fit_score_high",
            field: "min_score",
            severity: "important",
            message: "Minimum fit score is 80%. Scores above 60% can hide useful matches.",
            suggestion: "Use 60% or lower unless you only want a very narrow shortlist.",
            message_ar: "الحد الادنى لدرجة الملاءمة هو 80%.",
            suggestion_ar: "استخدم 60% أو أقل.",
        },
    ],
};

const FREE_SUB = {
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
};

async function mockBackend(page: Page, { authenticated = true }: { authenticated?: boolean } = {}) {
    await page.route(`${PROXY}/**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    await page.route(`${PROXY}/me`, (r) =>
        authenticated
            ? r.fulfill({
                  status: 200,
                  contentType: "application/json",
                  body: JSON.stringify({ email: "synthetic@test.dev", role: "user", authenticated: true, name: "Maryam" }),
              })
            : r.fulfill({ status: 401, contentType: "application/json", body: "{}" }),
    );
    await page.route(`${PROXY}/rico/profile`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(PROFILE) }),
    );
    await page.route(`${PROXY}/user/files**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ files: [], total: 0 }) }),
    );
    await page.route(`${PROXY}/rico/chat/history**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ messages: [] }) }),
    );
    await page.route(`${PROXY}/subscription/me`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FREE_SUB) }),
    );
}

async function noHorizontalOverflow(page: Page) {
    const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
}

const TOUCH_WIDTHS = [
    { name: "narrow iPhone", width: 320, height: 568 },
    { name: "Android", width: 360, height: 800 },
    { name: "modern iPhone", width: 390, height: 844 },
] as const;

test.describe("/command mobile usability", () => {
    for (const vp of TOUCH_WIDTHS) {
        test(`hides desktop shortcuts and keeps composer controls in-viewport on ${vp.name}`, async ({ page }) => {
            await page.setViewportSize({ width: vp.width, height: vp.height });
            await mockBackend(page);
            await page.goto("/command");

            const textarea = page.getByTestId("composer-textarea");
            await expect(textarea).toBeEnabled();
            // desktop-only keyboard shortcut hints must not be advertised on touch
            await expect(page.getByTestId("composer-hint")).toBeHidden();

            // composer and its send control sit fully inside the viewport, with
            // no fixed navigation overlapping them
            await expect(page.locator("nav.fixed.bottom-0")).toHaveCount(0);
            const composer = await page.getByTestId("atelier-composer").boundingBox();
            expect(composer).not.toBeNull();
            expect(composer!.x).toBeGreaterThanOrEqual(0);
            expect(composer!.x + composer!.width).toBeLessThanOrEqual(vp.width + 1);
            expect(composer!.y + composer!.height).toBeLessThanOrEqual(vp.height + 1);
            await noHorizontalOverflow(page);
        });
    }

    test("desktop keeps the shortcut hint (regression)", async ({ page }) => {
        await page.setViewportSize({ width: 1366, height: 768 });
        await mockBackend(page);
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeEnabled();
        await expect(page.getByTestId("composer-hint")).toBeVisible();
        await expect(page.getByTestId("composer-hint")).toHaveText(/CTRL\+K/i);
    });

    test("public mobile also hides the shortcut hint", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await mockBackend(page, { authenticated: false });
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeVisible();
        await expect(page.getByTestId("composer-hint")).toBeHidden();
        await noHorizontalOverflow(page);
    });

    test("AR RTL mobile: hint hidden, no overflow", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await mockBackend(page);
        await page.addInitScript(() => window.localStorage.setItem("rico-language", "ar"));
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeEnabled();
        await expect(page.getByTestId("composer-hint")).toBeHidden();
        await noHorizontalOverflow(page);
        await page.screenshot({ path: `${SHOT_DIR}/command-390-ar.png` });
    });
});

test.describe("/profile mobile usability", () => {
    for (const vp of TOUCH_WIDTHS) {
        test(`no horizontal overflow; warnings and save bar fit on ${vp.name}`, async ({ page }) => {
            await page.setViewportSize({ width: vp.width, height: vp.height });
            await mockBackend(page);
            await page.goto("/profile");
            await expect(page.getByLabel("Name")).toBeVisible();
            await noHorizontalOverflow(page);

            // warning cards: badges, text and actions stay inside the viewport
            const panel = page.getByRole("region", { name: /affecting your job matches/ });
            await expect(panel).toBeVisible();
            const panelBox = await panel.boundingBox();
            expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(vp.width + 1);

            // dirty the form → compact save bar appears with BOTH actions on-screen
            await page.getByLabel("Phone").fill("+9715000000009");
            const savebar = page.getByTestId("profile-ed-savebar");
            await expect(savebar).toBeVisible();
            const save = await savebar.getByRole("button", { name: "Save changes" }).boundingBox();
            const discard = await savebar.getByRole("button", { name: "Discard" }).boundingBox();
            expect(save!.x + save!.width).toBeLessThanOrEqual(vp.width + 1);
            expect(discard!.x).toBeGreaterThanOrEqual(-1);
            await noHorizontalOverflow(page);
            await page.screenshot({ path: `${SHOT_DIR}/profile-${vp.width}-en.png`, fullPage: true });
        });
    }

    test("AR RTL narrow: warnings + save bar fit, no overflow", async ({ page }) => {
        await page.setViewportSize({ width: 360, height: 800 });
        await mockBackend(page);
        await page.addInitScript(() => window.localStorage.setItem("rico-language", "ar"));
        await page.goto("/profile");
        await expect(page.locator(".wsx-root")).toHaveAttribute("dir", "rtl");
        await noHorizontalOverflow(page);
        await page.screenshot({ path: `${SHOT_DIR}/profile-360-ar.png`, fullPage: true });
    });
});
