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

    // [r, g, b, a] — alpha defaults to 1 when absent ("rgb(…)").
    const parseColor = (value: string) => {
      const channels = value.match(/\d+(?:\.\d+)?/g)?.map(Number);
      if (!channels || channels.length < 3) throw new Error(`Unsupported color: ${value}`);
      return [channels[0], channels[1], channels[2], channels.length >= 4 ? channels[3] : 1];
    };

    // The element's real backdrop: walk up through ancestors, collecting painted
    // background layers until an opaque one, then composite top-down. The old
    // implementation read document.body's background, which only matched while
    // /command painted its own full-bleed dark canvas over the dark body — the
    // light workspace shell paints its background on an inner div, not on body.
    const effectiveBackground = () => {
      const layers: number[][] = [];
      let node: Element | null = element;
      while (node) {
        const layer = parseColor(getComputedStyle(node).backgroundColor);
        if (layer[3] > 0) {
          layers.push(layer);
          if (layer[3] >= 1) break;
        }
        node = node.parentElement;
      }
      let out = [255, 255, 255];
      for (let i = layers.length - 1; i >= 0; i--) {
        const [r, g, b, a] = layers[i];
        out = [a * r + (1 - a) * out[0], a * g + (1 - a) * out[1], a * b + (1 - a) * out[2]];
      }
      return out;
    };

    const luminance = (rgb: number[]) => {
      const [r, g, b] = rgb.map((channel) => {
        const value = channel / 255;
        return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    const backdrop = effectiveBackground();
    const [fr, fg, fb, fa] = parseColor(getComputedStyle(element).color);
    // Composite a translucent text color over its backdrop before measuring.
    const text = [
      fa * fr + (1 - fa) * backdrop[0],
      fa * fg + (1 - fa) * backdrop[1],
      fa * fb + (1 - fa) * backdrop[2],
    ];

    const foreground = luminance(text);
    const background = luminance(backdrop);
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

      // The shortcut hint is desktop-only (mobile usability, 2026-07-18):
      // geometry anchors on the composer container, which exists on all widths.
      const isDesktop = scenario.viewport.width >= 768;
      const composerAnchor = page.getByTestId("atelier-composer");
      const composerHint = page.getByTestId("composer-hint");
      const messagePane = page.locator('[role="log"]');
      const textarea = page.getByTestId("composer-textarea");

      await expect(textarea).toBeEnabled();
      await textarea.fill("Find HSE jobs in Dubai");

      const composerBefore = await yPosition(composerAnchor);
      const paneBefore = await yPosition(messagePane);

      await textarea.press("Enter");
      await page.waitForTimeout(250);

      const composerDuring = await yPosition(composerAnchor);
      const paneDuring = await yPosition(messagePane);

      expect(Math.abs(composerDuring - composerBefore)).toBeLessThanOrEqual(2);
      expect(Math.abs(paneDuring - paneBefore)).toBeLessThanOrEqual(2);

      await expect(page.getByText("Done")).toBeVisible();

      const composerAfter = await yPosition(composerAnchor);
      const paneAfter = await yPosition(messagePane);

      expect(Math.abs(composerAfter - composerBefore)).toBeLessThanOrEqual(2);
      expect(Math.abs(paneAfter - paneBefore)).toBeLessThanOrEqual(2);
      if (isDesktop) {
        await expect(composerHint).toHaveText(scenario.hint);
        expect(await contrastRatio(page, '[data-testid="composer-hint"]')).toBeGreaterThanOrEqual(4.5);
      } else {
        // touch widths: desktop keyboard shortcuts must not be advertised
        await expect(composerHint).toBeHidden();
      }
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

  test("authenticated mobile resolves to the single WorkspaceShell chrome (no legacy header/dock)", async ({ page }) => {
    // Single-shell contract (2026-07-18): the legacy dark MobileCommandHeader
    // and MobileBottomNav must never render for the authenticated audience —
    // the shared WorkspaceShell mobile bar owns mobile navigation. The header
    // may exist transiently while auth resolves; the END state is what's pinned.
    await page.setViewportSize({ width: 390, height: 844 });
    await mockAuthenticatedCommand(page, { authDelayMs: 600 });
    await page.goto("/command");

    const textarea = page.getByTestId("composer-textarea");
    await expect(textarea).toBeEnabled();

    // exactly one mobile chrome owner: the shared workspace bar
    await expect(page.getByTestId("wsx-mobile-bar")).toHaveCount(1);
    await expect(page.getByTestId("command-mobile-header")).toHaveCount(0);
    // legacy fixed bottom dock is gone
    await expect(page.locator("nav.fixed.bottom-0")).toHaveCount(0);
    // composer is not pushed up by dock compensation and does not overlap nav
    const composerBox = await page.getByTestId("atelier-composer").boundingBox();
    expect(composerBox).not.toBeNull();
    expect(composerBox!.y + composerBox!.height).toBeLessThanOrEqual(844 + 1);
  });
});
