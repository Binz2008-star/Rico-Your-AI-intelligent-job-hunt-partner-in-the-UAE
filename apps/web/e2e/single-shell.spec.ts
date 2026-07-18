/**
 * apps/web/e2e/single-shell.spec.ts
 * Single-shell ownership proof (production defect, owner smoke 2026-07-18).
 *
 * Authenticated workspace routes must render EXACTLY ONE approved navigation
 * shell (WorkspaceShell). The legacy dark chrome — MobileCommandHeader and the
 * fixed MobileBottomNav dock — must not mount on any of them, on any width.
 *
 * All backend calls are mocked. Screenshots go to SINGLE_SHELL_SHOT_DIR (or a
 * local untracked default) and are never committed.
 *
 * Run:
 *   cd apps/web
 *   npx playwright test single-shell --project=chromium
 */
import { expect, test, type Page } from "@playwright/test";

const PROXY = "/proxy/api/v1";
const SHOT_DIR = process.env.SINGLE_SHELL_SHOT_DIR || "e2e/screenshots/single-shell";

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
    warnings: [],
};

async function mockBackend(page: Page) {
    // Catch-all FIRST so the specific routes below take precedence.
    await page.route(`${PROXY}/**`, (r) =>
        r.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    await page.route(`${PROXY}/me`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ email: "synthetic@test.dev", role: "user", authenticated: true, name: "Maryam" }),
        }),
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

/** Exactly one approved shell; zero legacy chrome. */
async function assertSingleShell(page: Page, { app = false }: { app?: boolean } = {}) {
    await expect(page.locator(".wsx-root")).toHaveCount(1);
    await expect(page.getByTestId("command-mobile-header")).toHaveCount(0);
    await expect(page.locator("nav.fixed.bottom-0")).toHaveCount(0);
    const viewport = page.viewportSize();
    if (viewport && viewport.width < 1024) {
        // one mobile chrome owner below lg
        await expect(page.getByTestId("wsx-mobile-bar")).toHaveCount(1);
        await expect(page.getByTestId("wsx-mobile-bar")).toBeVisible();
    }
    if (app) {
        await expect(page.getByTestId("command-obsidian-shell")).toHaveCount(1);
    }
}

const ROUTES: Array<{ path: string; app: boolean; ready: (page: Page) => Promise<void> }> = [
    { path: "/command", app: true, ready: async (p) => { await expect(p.getByTestId("composer-textarea")).toBeEnabled(); } },
    { path: "/profile", app: false, ready: async (p) => { await expect(p.getByLabel("Name")).toBeVisible(); } },
    { path: "/settings", app: false, ready: async (p) => { await expect(p.locator(".wsx-root")).toBeVisible(); } },
    { path: "/applications", app: false, ready: async (p) => { await expect(p.locator(".wsx-root")).toBeVisible(); } },
];

test.describe("single approved shell on authenticated workspace routes", () => {
    for (const route of ROUTES) {
        test(`${route.path} — mobile renders one shell, no legacy chrome`, async ({ page }) => {
            await page.setViewportSize({ width: 390, height: 844 });
            await mockBackend(page);
            await page.goto(route.path);
            await route.ready(page);
            await assertSingleShell(page, { app: route.app });
        });
    }

    test("/command mobile drawer carries nav + command actions (single owner)", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await mockBackend(page);
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeEnabled();
        await page.screenshot({ path: `${SHOT_DIR}/command-mobile-en.png`, fullPage: false });

        await page.getByTestId("wsx-mobile-bar").getByRole("button", { name: "Menu" }).click();
        // workspace navigation (one owner) + command actions in the same drawer
        await expect(page.getByRole("link", { name: "Profile" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Applications" })).toBeVisible();
        await expect(page.getByTestId("command-mobile-actions")).toBeVisible();
        await page.screenshot({ path: `${SHOT_DIR}/command-mobile-drawer-en.png`, fullPage: false });
    });

    test("/command desktop keeps the workspace sidebar + console bar (no legacy header)", async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await mockBackend(page);
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeEnabled();
        await expect(page.getByTestId("command-mobile-header")).toHaveCount(0);
        await expect(page.getByTestId("command-obsidian-topbar")).toBeVisible();
        await expect(page.locator(".wsx-root")).toHaveCount(1);
        await page.screenshot({ path: `${SHOT_DIR}/command-desktop-en.png`, fullPage: false });
    });

    test("AR RTL mobile keeps the single shell", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await mockBackend(page);
        await page.addInitScript(() => window.localStorage.setItem("rico-language", "ar"));
        await page.goto("/command");
        await expect(page.getByTestId("composer-textarea")).toBeEnabled();
        await assertSingleShell(page, { app: true });
        await expect(page.locator(".wsx-root")).toHaveAttribute("dir", "rtl");
        await page.screenshot({ path: `${SHOT_DIR}/command-mobile-ar.png`, fullPage: false });

        await page.goto("/profile");
        await assertSingleShell(page);
        await page.screenshot({ path: `${SHOT_DIR}/profile-mobile-ar.png`, fullPage: true });
    });

    test("public /command keeps its own reference chrome (out of scope, unchanged)", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.route(`${PROXY}/**`, (r) =>
            r.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
        );
        await page.route(`${PROXY}/me`, (r) => r.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
        await page.goto("/command");
        await expect(page.getByTestId("command-mobile-header")).toBeVisible();
        await expect(page.locator("nav.fixed.bottom-0")).toHaveCount(0);
    });
});
