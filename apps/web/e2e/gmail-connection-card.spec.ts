/**
 * apps/web/e2e/gmail-connection-card.spec.ts
 * Playwright E2E for the Gmail read-only connector card on /settings
 * (Settings → Notifications tab). All backend calls are mocked — no real Gmail
 * endpoints, no tokens, no live OAuth. Captures state screenshots for review.
 *
 * Run:
 *   cd apps/web
 *   npx playwright test gmail-connection-card --project=chromium
 *   npx playwright test gmail-connection-card --project=mobile-chrome
 */
import { expect, test, type Page } from "@playwright/test";

const PROXY = "/proxy/api/v1";
const SHOT_DIR = process.env.GMAIL_SHOT_DIR || "e2e/screenshots/gmail";

type GmailStatus = {
    sync_enabled: boolean;
    enabled: boolean;
    connected: boolean;
    provider_email: string | null;
    scopes: string[];
    needs_reauth: boolean;
    recurring_sync_consent: boolean;
    last_sync_at: string | null;
};

function gmailStatus(overrides: Partial<GmailStatus> = {}): GmailStatus {
    return {
        sync_enabled: true,
        enabled: true,
        connected: false,
        provider_email: null,
        scopes: [],
        needs_reauth: false,
        recurring_sync_consent: false,
        last_sync_at: null,
        ...overrides,
    };
}

/** Wire the mocked backend. `status` is read live so a test can flip it.
 * The broad catch-all is registered FIRST so the specific routes below (added
 * later) take precedence — Playwright matches the most-recently-added route. */
async function mockBackend(page: Page, statusRef: { current: GmailStatus }) {
    // Everything the shell/settings touch → benign empty 200 so the page renders.
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
    await page.route(`${PROXY}/integrations/gmail/status`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(statusRef.current),
        }),
    );
    await page.route(`${PROXY}/integrations/gmail/consent`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ recurring_sync_consent: true }),
        }),
    );
    await page.route(`${PROXY}/integrations/gmail/disconnect`, (r) =>
        r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ disconnected: true, revoked_at_google: true }),
        }),
    );
}

async function openNotificationsTab(page: Page) {
    await page.goto("/settings");
    const tab = page.getByRole("tab", { name: /notifications|الإشعارات/i });
    // First /settings compile in dev + async auth mount can take a few seconds.
    await tab.first().waitFor({ state: "visible", timeout: 30000 });
    await tab.first().click();
    await expect(
        page.getByText(/Gmail read-only sync|مزامنة Gmail للقراءة فقط/i),
    ).toBeVisible({ timeout: 15000 });
}

test.describe("Gmail connector card — states", () => {
    test("disabled / coming-soon is fail-closed", async ({ page }) => {
        const ref = { current: gmailStatus({ sync_enabled: false, enabled: false }) };
        await mockBackend(page, ref);
        let connectCalled = false;
        await page.route(`${PROXY}/integrations/gmail/connect`, (r) => {
            connectCalled = true;
            return r.fulfill({ status: 503, contentType: "application/json", body: "{}" });
        });
        await openNotificationsTab(page);
        await expect(page.getByText(/Coming soon/i)).toBeVisible();
        await expect(page.getByRole("button", { name: /Connect Gmail/i })).toBeDisabled();
        await page.screenshot({ path: `${SHOT_DIR}/01-disabled.png`, fullPage: true });
        expect(connectCalled).toBe(false);
    });

    test("connected — consent not yet approved", async ({ page }) => {
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        await openNotificationsTab(page);
        await expect(page.getByText(/Recurring background sync: not approved/i)).toBeVisible();
        await page.screenshot({ path: `${SHOT_DIR}/02-connected-not-approved.png`, fullPage: true });
    });

    test("consent disclosure requires an explicit tick", async ({ page }) => {
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        await openNotificationsTab(page);
        await page.getByRole("button", { name: /Review & approve recurring sync/i }).click();
        const checkbox = page.getByRole("checkbox");
        await expect(checkbox).not.toBeChecked();
        await expect(page.getByRole("button", { name: /Approve recurring sync/i })).toBeDisabled();
        await page.screenshot({ path: `${SHOT_DIR}/03-consent.png`, fullPage: true });
        await checkbox.check();
        await expect(page.getByRole("button", { name: /Approve recurring sync/i })).toBeEnabled();
    });

    test("connected while sync disabled — truthful, Sync off, Disconnect on", async ({ page }) => {
        const ref = { current: gmailStatus({ sync_enabled: false, enabled: false, connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        await openNotificationsTab(page);
        await expect(page.getByText(/sync currently disabled/i)).toBeVisible();
        await expect(page.getByText(/Coming soon/i)).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Sync now/i })).toBeDisabled();
        await expect(page.getByRole("button", { name: /Connect Gmail/i })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /^Disconnect$/i })).toBeEnabled();
        await page.screenshot({ path: `${SHOT_DIR}/08-connected-sync-disabled.png`, fullPage: true });
    });

    test("connected — recurring approved shows revoke", async ({ page }) => {
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com", recurring_sync_consent: true }) };
        await mockBackend(page, ref);
        await openNotificationsTab(page);
        await expect(page.getByText(/Recurring background sync: approved/i)).toBeVisible();
        await expect(page.getByRole("button", { name: /Turn off recurring sync/i })).toBeVisible();
        await page.screenshot({ path: `${SHOT_DIR}/04-connected-approved.png`, fullPage: true });
    });

    test("consent failure does not claim success", async ({ page }) => {
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        await page.route(`${PROXY}/integrations/gmail/consent`, (r) =>
            r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) }),
        );
        await openNotificationsTab(page);
        await page.getByRole("button", { name: /Review & approve recurring sync/i }).click();
        await page.getByRole("checkbox").check();
        await page.getByRole("button", { name: /Approve recurring sync/i }).click();
        await expect(page.getByText(/Gmail action failed/i)).toBeVisible();
        await page.screenshot({ path: `${SHOT_DIR}/05-error.png`, fullPage: true });
    });

    test("disconnect requires confirmation", async ({ page }) => {
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        let disconnectCalled = false;
        await page.route(`${PROXY}/integrations/gmail/disconnect`, (r) => {
            disconnectCalled = true;
            return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ disconnected: true, revoked_at_google: true }) });
        });
        await openNotificationsTab(page);
        await page.getByRole("button", { name: /^Disconnect$/i }).click();
        await expect(page.getByText(/Disconnect Gmail\?/i)).toBeVisible();
        expect(disconnectCalled).toBe(false);
        await page.screenshot({ path: `${SHOT_DIR}/06-disconnect-confirm.png`, fullPage: true });
        await page.getByRole("button", { name: /Yes, disconnect/i }).click();
        await expect.poll(() => disconnectCalled).toBe(true);
    });

    test("Arabic RTL renders the consent copy", async ({ page }) => {
        await page.addInitScript(() => window.localStorage.setItem("rico-language", "ar"));
        const ref = { current: gmailStatus({ connected: true, provider_email: "someone@gmail.com" }) };
        await mockBackend(page, ref);
        await page.goto("/settings");
        const tab = page.getByRole("tab", { name: /الإشعارات|notifications/i });
        await tab.first().waitFor({ state: "visible", timeout: 30000 });
        await tab.first().click();
        await expect(page.getByRole("button", { name: /مراجعة واعتماد المزامنة المتكررة/ })).toBeVisible({ timeout: 15000 });
        await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
        await page.screenshot({ path: `${SHOT_DIR}/07-arabic-rtl.png`, fullPage: true });
    });
});
