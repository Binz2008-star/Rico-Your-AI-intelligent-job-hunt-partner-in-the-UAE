import { expect, test, type Locator, type Page } from "@playwright/test";

const PROXY_API = "/proxy/api/v1";

const HISTORY_MESSAGES = Array.from({ length: 24 }, (_, index) => ({
  role: index % 2 === 0 ? "user" : "assistant",
  content:
    index % 2 === 0
      ? `User history message ${index}`
      : `Rico history response ${index}. This longer response wraps across several lines and forces the command message pane to scroll.`,
}));

async function mockAuthenticatedCommand(page: Page) {
  await page.route(`${PROXY_API}/me`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        email: "test@example.com",
        role: "user",
        authenticated: true,
      }),
    });
  });

  await page.route(`${PROXY_API}/rico/chat/history**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        messages: HISTORY_MESSAGES,
        total: HISTORY_MESSAGES.length,
        has_more: false,
      }),
    });
  });

  await page.route(`${PROXY_API}/rico/chat/stream`, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body:
        'data: {"type":"token","text":"Done"}\n\n' +
        'data: {"type":"done","response":{"response":"Done","type":"chat"}}\n\n',
    });
  });
}

async function yPosition(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!.y;
}

test.describe("/command composer stability", () => {
  for (const scenario of [
    { name: "desktop English", language: "en", viewport: { width: 1366, height: 768 } },
    { name: "mobile Arabic", language: "ar", viewport: { width: 390, height: 844 } },
  ] as const) {
    test(`keeps the composer anchored during pending response on ${scenario.name}`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      await page.addInitScript((language) => {
        localStorage.setItem("rico-language", language);
      }, scenario.language);
      await mockAuthenticatedCommand(page);

      await page.goto("/command");

      const composerHint = page.locator("#command-input-hint");
      const messagePane = page.locator('[role="log"]');
      const textarea = page.locator('textarea[aria-label="Message Rico"]');

      await expect(textarea).toBeEnabled();
      await textarea.fill("Find HSE jobs in Dubai");

      const composerBefore = await yPosition(composerHint);
      const paneBefore = await yPosition(messagePane);

      await textarea.press("Enter");
      await page.waitForTimeout(250);

      const composerDuring = await yPosition(composerHint);
      const paneDuring = await yPosition(messagePane);

      expect(Math.abs(composerDuring - composerBefore)).toBeLessThanOrEqual(2);
      expect(Math.abs(paneDuring - paneBefore)).toBeLessThanOrEqual(2);

      await expect(page.getByText("Done")).toBeVisible();

      const composerAfter = await yPosition(composerHint);
      const paneAfter = await yPosition(messagePane);

      expect(Math.abs(composerAfter - composerBefore)).toBeLessThanOrEqual(2);
      expect(Math.abs(paneAfter - paneBefore)).toBeLessThanOrEqual(2);
      await expect(page.getByText(/openai|deepseek|provider/i)).toHaveCount(0);
    });
  }
});
