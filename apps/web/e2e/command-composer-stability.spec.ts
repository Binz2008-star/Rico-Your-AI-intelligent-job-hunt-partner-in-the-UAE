import { expect, test, type Locator, type Page } from "@playwright/test";

const PROXY_API = "/proxy/api/v1";

const HISTORY_MESSAGES = Array.from({ length: 24 }, (_, index) => ({
  role: index % 2 === 0 ? "user" : "assistant",
  content:
    index % 2 === 0
      ? `User history message ${index}`
      : `Rico history response ${index}. This longer response wraps across several lines and forces the command message pane to scroll.`,
}));

async function mockAuthenticatedCommand(
  page: Page,
  {
    authDelayMs = 0,
    streamDelayMs = 1_200,
    messagesRemaining = 9,
  }: {
    authDelayMs?: number;
    streamDelayMs?: number;
    messagesRemaining?: number;
  } = {},
) {
  await page.route(`${PROXY_API}/me`, async (route) => {
    if (authDelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, authDelayMs));
    }
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
    await new Promise((resolve) => setTimeout(resolve, streamDelayMs));
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body:
        'data: {"type":"token","text":"Done"}\n\n' +
        `data: {"type":"done","response":{"response":"Done","type":"chat","messages_remaining":${messagesRemaining}}}\n\n`,
    });
  });
}

async function yPosition(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!.y;
}

async function contrastRatio(page: Page, selector: string) {
  return page.evaluate((targetSelector) => {
    const element = document.querySelector(targetSelector);
    if (!element) throw new Error(`Missing element: ${targetSelector}`);

    const parseRgb = (value: string) => {
      const channels = value.match(/\d+(?:\.\d+)?/g)?.slice(0, 3).map(Number);
      if (!channels || channels.length !== 3) throw new Error(`Unsupported color: ${value}`);
      return channels;
    };
    const luminance = (rgb: number[]) => {
      const [r, g, b] = rgb.map((channel) => {
        const value = channel / 255;
        return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    const foreground = luminance(parseRgb(getComputedStyle(element).color));
    const background = luminance(parseRgb(getComputedStyle(document.body).backgroundColor));
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  }, selector);
}

test.describe("/command composer stability", () => {
  test.describe.configure({ mode: "serial" });

  for (const scenario of [
    { name: "desktop English", language: "en", viewport: { width: 1366, height: 768 }, hint: /ENTER TO SEND/ },
    { name: "mobile Arabic", language: "ar", viewport: { width: 390, height: 844 }, hint: /للإرسال/ },
  ] as const) {
    test(`keeps the composer anchored during pending response on ${scenario.name}`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      await page.addInitScript((language) => {
        localStorage.setItem("rico-language", language);
      }, scenario.language);
      await mockAuthenticatedCommand(page);

      await page.goto("/command");

      const composerHint = page.getByTestId("composer-hint");
      const messagePane = page.locator('[role="log"]');
      const textarea = page.getByTestId("composer-textarea");

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
      await expect(composerHint).toHaveText(scenario.hint);
      expect(await contrastRatio(page, '[data-testid="composer-hint"]')).toBeGreaterThanOrEqual(4.5);
      await expect(page.getByText(/openai|deepseek|provider/i)).toHaveCount(0);
    });
  }

  test("keeps the message pane and composer fixed when the slow-request banner appears", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await mockAuthenticatedCommand(page, { streamDelayMs: 11_000 });
    await page.goto("/command");

    const slowBanner = page.getByTestId("command-slow-banner");
    const composerHint = page.getByTestId("composer-hint");
    const messagePane = page.locator('[role="log"]');
    const textarea = page.getByTestId("composer-textarea");

    await expect(textarea).toBeEnabled();
    await textarea.fill("Find HSE jobs in Dubai");
    const composerBefore = await yPosition(composerHint);
    const paneBefore = await yPosition(messagePane);

    await textarea.press("Enter");
    await expect(slowBanner).toHaveClass(/(^|\s)visible(\s|$)/, { timeout: 9_000 });
    await expect(slowBanner).toBeVisible();

    expect(Math.abs((await yPosition(composerHint)) - composerBefore)).toBeLessThanOrEqual(2);
    expect(Math.abs((await yPosition(messagePane)) - paneBefore)).toBeLessThanOrEqual(2);
  });

  test("keeps mobile header geometry stable while authentication resolves", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockAuthenticatedCommand(page, { authDelayMs: 600 });
    await page.goto("/command");

    const header = page.getByTestId("command-mobile-header");
    const brand = page.getByTestId("command-mobile-brand");
    const authSlot = page.getByTestId("command-mobile-auth-slot");
    const textarea = page.getByTestId("composer-textarea");

    const headerBefore = await header.boundingBox();
    const brandBefore = await brand.boundingBox();
    const slotBefore = await authSlot.boundingBox();
    expect(headerBefore).not.toBeNull();
    expect(brandBefore).not.toBeNull();
    expect(slotBefore).not.toBeNull();

    await expect(textarea).toBeEnabled();

    const headerAfter = await header.boundingBox();
    const brandAfter = await brand.boundingBox();
    const slotAfter = await authSlot.boundingBox();
    expect(headerAfter).not.toBeNull();
    expect(brandAfter).not.toBeNull();
    expect(slotAfter).not.toBeNull();

    expect(Math.abs(headerAfter!.height - headerBefore!.height)).toBeLessThanOrEqual(1);
    expect(Math.abs(brandAfter!.x - brandBefore!.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(slotAfter!.x - slotBefore!.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(slotAfter!.width - slotBefore!.width)).toBeLessThanOrEqual(1);
  });
});
