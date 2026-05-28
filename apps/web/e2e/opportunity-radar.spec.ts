/**
 * apps/web/e2e/opportunity-radar.spec.ts
 * Playwright E2E tests for Rico Opportunity Radar (/signals).
 *
 * Run with:
 *   cd apps/web
 *   npx playwright test
 *
 * Prerequisites:
 *   npm install -D @playwright/test
 *   npx playwright install
 */
import { expect, test } from "@playwright/test";

// Mocked signals data — deterministic, no real job boards hit
const MOCK_SIGNALS = [
  {
    id: "job-1",
    company: "Renew",
    role: "HSE Manager - Manufacturing",
    matchScore: 86,
    momentum: "high",
    location: "Dubai, UAE",
    timestamp: "2026-05-24T00:00:00.000Z",
    applyUrl: "https://example.com/apply",
    whyItFits: "Your HSE and manufacturing safety background fits this role.",
    missingFacts: ["Confirm salary range"],
    source: "Rico job search",
  },
  {
    id: "job-2",
    company: "Expired Corp",
    role: "Operations Lead",
    matchScore: 72,
    momentum: "medium",
    location: "Abu Dhabi, UAE",
    timestamp: "2026-05-20T00:00:00.000Z",
    applyUrl: "",
    whyItFits: "Operations background with lean manufacturing experience.",
    missingFacts: [],
    source: "Rico job search",
  },
];

// Intercept the signals API and return mocked data
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/signals**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ signals: MOCK_SIGNALS }),
    });
  });

  await page.route("**/api/v1/links/verify**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        "job-1": { status: "live", http_status: 200 },
        "job-2": {
          status: "expired",
          http_status: 200,
          error_message: "Expired on Indeed",
        },
      }),
    });
  });
});

test.describe("Opportunity Radar /signals", () => {
  test("page title is Opportunity Radar", async ({ page }) => {
    await page.goto("/signals");
    await expect(page).toHaveTitle(/Opportunity Radar/i);
  });

  test("page loads without error state", async ({ page }) => {
    await page.goto("/signals");
    // Should not show "Could not load live signals" error
    await expect(
      page.locator("text=Could not load live signals"),
    ).not.toBeVisible();
  });

  test("cards are in a single column on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/signals");
    // Wait for cards to render
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    // On mobile, should be single column (grid-cols-1)
    const grid = page.locator("[data-testid='signals-grid']");
    const classes = await grid.getAttribute("class");
    expect(classes).toContain("grid-cols-1");
  });

  test("desktop uses max 2 columns, not 3", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    const grid = page.locator("[data-testid='signals-grid']");
    const classes = await grid.getAttribute("class");
    // Should have xl:grid-cols-2, should NOT have lg:grid-cols-3
    expect(classes).toContain("xl:grid-cols-2");
    expect(classes).not.toContain("lg:grid-cols-3");
  });

  test("HSE Manager title does not break vertically", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    const title = page
      .locator("[data-testid='opportunity-card']")
      .first()
      .locator("[data-testid='opportunity-card-title']");
    // Check title text is present as a continuous phrase, not broken
    const text = await title.textContent();
    expect(text).toContain("HSE Manager");
    // Ensure no single-letter wrapping (heuristic: title should not contain single-char lines)
    expect(text).not.toMatch(/^\w\s*$/m);
  });

  test("link badges appear for live job", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    // First card (live) should have a link status badge
    const firstCard = page.locator("[data-testid='opportunity-card']").first();
    const badge = firstCard.locator("[data-testid='link-status-badge']");
    await expect(badge).toBeVisible();
    const badgeText = await badge.textContent();
    expect(badgeText).toMatch(/live|verified/i);
  });

  test("expired link card does not show View job", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    // Find the expired card (job-2)
    const expiredCard = page.locator("[data-testid='opportunity-card']").nth(1);
    const viewJobBtn = expiredCard.locator("[data-testid='view-job-action']");
    await expect(viewJobBtn).not.toBeVisible();
  });

  test("live card shows View job", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    const liveCard = page.locator("[data-testid='opportunity-card']").first();
    const viewJobBtn = liveCard.locator("[data-testid='view-job-action']");
    await expect(viewJobBtn).toBeVisible();
  });

  test("Cards / Focus list toggle works", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });

    // Find toggle buttons
    const cardsBtn = page.locator("[data-testid='view-mode-toggle-card']");
    const focusBtn = page.locator("[data-testid='view-mode-toggle-list']");

    // If toggle exists, test it
    if ((await cardsBtn.count()) > 0 && (await focusBtn.count()) > 0) {
      // Click Focus list
      await focusBtn.click();
      // Cards should switch to list/focus layout (single column)
      const grid = page.locator("[data-testid='signals-grid']");
      const classes = await grid.getAttribute("class");
      expect(classes).toContain("grid-cols-1");

      // Click back to Cards
      await cardsBtn.click();
      const classesAfter = await grid.getAttribute("class");
      expect(classesAfter).toContain("xl:grid-cols-2");
    }
  });

  test("no infinite API request loop for link verification", async ({
    page,
  }) => {
    let verifyCallCount = 0;
    await page.route("**/api/v1/links/verify**", async (route) => {
      verifyCallCount++;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          "job-1": { status: "live", http_status: 200 },
          "job-2": { status: "expired", http_status: 200 },
        }),
      });
    });

    await page.goto("/signals");
    await page.waitForTimeout(3000); // Wait for any polling

    // Should not have excessive link verify calls (> 10 is suspicious)
    expect(verifyCallCount).toBeLessThanOrEqual(10);
  });

  test("modal opens on card click and shows actions", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });

    const firstCard = page.locator("[data-testid='opportunity-card']").first();
    await firstCard.click();

    // Modal should appear
    const modal = page.locator("[data-testid='opportunity-detail-modal']");
    await expect(modal).toBeVisible();

    // Should show match score
    await expect(modal.locator("text=86%")).toBeVisible();

    // Should show action buttons
    await expect(
      modal.locator("[data-testid='view-job-action']"),
    ).toBeVisible();
  });
});
