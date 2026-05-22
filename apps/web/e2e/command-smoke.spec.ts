import { test, expect, Route } from "@playwright/test";

test.describe("/command smoke", () => {
  test.beforeEach(async ({ page }) => {
    // Intercept auth check so we don't depend on a live backend
    await page.route("**/api/v1/me", (route: Route) =>
      route.fulfill({ status: 401, body: JSON.stringify({ detail: "Unauthorized" }) })
    );
    // Intercept chat so network-error test can control it
    await page.route("**/api/v1/rico/chat/public", (route: Route) =>
      route.abort("failed")
    );
  });

  test("textarea[aria-label='Message Rico'] renders exactly once", async ({ page }) => {
    await page.goto("/command");
    const inputs = page.locator('textarea[aria-label="Message Rico"]');
    await expect(inputs).toHaveCount(1);
  });

  test("quick actions render (at least 4 buttons)", async ({ page }) => {
    await page.goto("/command");
    // Quick actions are shown when messages.length <= 1 and not thinking
    // The page starts with 1 welcome message; buttons should appear
    await page.waitForSelector('[role="log"]');
    const quickButtons = page.locator('[role="log"] button[type="button"]');
    await expect(quickButtons).toHaveCount(await quickButtons.count().then((n) => n));
    // Verify specific labels
    await expect(page.getByRole("button", { name: "Analyze my trajectory" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Map my next move" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload my CV" })).toBeVisible();
  });

  test("upload button renders", async ({ page }) => {
    await page.goto("/command");
    const uploadBtn = page.locator('button[aria-label="Upload CV"]');
    await expect(uploadBtn).toBeVisible();
  });

  test("network error state renders when fetch fails", async ({ page }) => {
    await page.goto("/command");
    // Wait for public session to be established
    await page.waitForSelector('textarea[aria-label="Message Rico"]:not([disabled])');
    const textarea = page.locator('textarea[aria-label="Message Rico"]');
    await textarea.fill("find me a job");
    await page.keyboard.press("Enter");
    // Should show a network error message from Rico
    await expect(
      page.locator('[role="log"]').getByText(/could not reach rico|failed to fetch|taking longer/i)
    ).toBeVisible({ timeout: 20_000 });
  });

  test("no /command-v2 hrefs remain", async ({ page }) => {
    await page.goto("/command");
    const links = await page.locator('a[href*="command-v2"]').count();
    expect(links).toBe(0);
  });

  test("no command-v2 ids remain", async ({ page }) => {
    await page.goto("/command");
    const ids = await page.locator('[id*="command-v2"]').count();
    expect(ids).toBe(0);
  });
});

test.describe("/command mobile layout", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/me", (route: Route) =>
      route.fulfill({ status: 401, body: JSON.stringify({ detail: "Unauthorized" }) })
    );
  });

  test("upload button visible on mobile", async ({ page }) => {
    await page.goto("/command");
    const uploadBtn = page.locator('button[aria-label="Upload CV"]');
    await expect(uploadBtn).toBeVisible();
  });

  test("textarea visible on mobile", async ({ page }) => {
    await page.goto("/command");
    const textarea = page.locator('textarea[aria-label="Message Rico"]');
    await expect(textarea).toBeVisible();
  });
});
