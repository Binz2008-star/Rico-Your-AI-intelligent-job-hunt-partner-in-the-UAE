/**
 * apps/web/e2e/opportunity-radar.spec.ts
 * Playwright E2E tests for Rico Opportunity Radar (/signals).
 *
 * All external API calls are mocked. No real job boards are hit.
 *
 * Run with:
 *   cd apps/web
 *   npx playwright test --project=chromium
 */
import { expect, test } from "@playwright/test";

// ── Mocked backend data ──────────────────────────────────────────────────────

const MOCK_JOBS = [
  {
    job_id: "job-1",
    title: "HSE Manager - Manufacturing",
    company: "Renew",
    location: "Dubai, UAE",
    salary_range: "AED 25-35k/mo",
    score: 86,
    reason: "Your HSE and manufacturing safety background fits this role.",
    tags: ["HSE", "Manufacturing", "UAE"],
    posted_at: "2026-05-24T00:00:00.000Z",
    apply_url: "https://example.com/apply",
    source_url: "https://example.com/job-1",
    verification_status: "",
    match_explanation: {
      verdict: "strong_fit",
      summary: "Strong fit for HSE Manager role",
      why_this_fits: ["HSE experience", "Manufacturing background"],
      worth_checking: ["Confirm salary range"],
      recommended_next_step: "Apply directly",
      confidence: "high",
    },
  },
  {
    job_id: "job-2",
    title: "Operations Lead",
    company: "Expired Corp",
    location: "Abu Dhabi, UAE",
    salary_range: "AED 20-28k/mo",
    score: 72,
    reason: "Operations background with lean manufacturing experience.",
    tags: ["Operations", "Leadership"],
    posted_at: "2026-05-20T00:00:00.000Z",
    apply_url: "https://example.com/expired",
    source_url: "https://example.com/expired",
    verification_status: "expired",
    match_explanation: {
      verdict: "worth_checking",
      summary: "Operations lead match",
      why_this_fits: ["Lean manufacturing"],
      worth_checking: [],
      recommended_next_step: "Review role details",
      confidence: "medium",
    },
  },
];

const MOCK_JOB_LIST_RESPONSE = {
  jobs: MOCK_JOBS,
  total: MOCK_JOBS.length,
  page: 1,
  limit: 12,
  pages: 1,
};

// The app routes client-side calls through /proxy/*
const PROXY_API = "/proxy/api/v1";

// ── Setup mocks before every test ───────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // 1. Mock /jobs endpoint (used by useOrchestration → getSignals)
  await page.route(`${PROXY_API}/jobs**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_JOB_LIST_RESPONSE),
    });
  });

  // 2. Mock link verification batch endpoint
  await page.route(
    `${PROXY_API}/links/verify/batch`,
    async (route, request) => {
      const body = request.postDataJSON();
      const urls: string[] = body?.urls ?? [];
      const result: Record<string, unknown> = {};
      for (const url of urls) {
        if (url === "https://example.com/apply") {
          result[url] = {
            status: "live",
            http_status: 200,
            error_message: null,
            verified_at: new Date().toISOString(),
          };
        } else {
          result[url] = {
            status: "expired",
            http_status: 404,
            error_message: "Expired",
            verified_at: new Date().toISOString(),
          };
        }
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(result),
      });
    },
  );

  // 3. Mock profile endpoint (used by getTrajectory)
  await page.route(`${PROXY_API}/rico/profile`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profile_exists: true,
        name: "Test User",
        email: "test@example.com",
        current_role: "HSE Manager",
        target_roles: ["HSE Manager", "Operations Manager"],
        years_experience: 8,
        completeness_score: 0.85,
      }),
    });
  });

  // 4. Mock applications endpoint (used by getTrajectory)
  await page.route(`${PROXY_API}/applications**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        applications: [],
        total: 0,
        page: 1,
        limit: 50,
        pages: 1,
      }),
    });
  });

  // 5. Mock chat history endpoint (used by getTrajectory)
  await page.route(`${PROXY_API}/rico/chat/history**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ messages: [] }),
    });
  });

  // 6. Mock auth /me (optional, but avoids 401 noise)
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
});

// ── Tests ───────────────────────────────────────────────────────────────────

test.describe("Opportunity Radar /signals", () => {
  test("page title contains Rico", async ({ page }) => {
    await page.goto("/signals");
    await expect(page).toHaveTitle(/Rico/i);
  });

  // /signals redirects to /command (next.config.js). Card-dependent tests need
  // to be updated once opportunity-card data-testid elements are available in the
  // /command experience (feat/immersive-command-experience).
  test.describe.skip("card UI tests — pending /command integration", () => {
  test("page loads without error state", async ({ page }) => {
    await page.goto("/signals");
    // Wait for terminal state: either cards render or empty state shows
    await Promise.race([
      page.waitForSelector("[data-testid='opportunity-card']", {
        state: "visible",
        timeout: 5000,
      }),
      page.waitForSelector("text=No live signals yet", {
        state: "visible",
        timeout: 5000,
      }),
    ]);
    await expect(
      page.locator("text=Could not load live signals"),
    ).not.toBeVisible();
  });

  test("cards are in a single column on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
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
    expect(classes).toContain("xl:grid-cols-2");
    expect(classes).not.toContain("lg:grid-cols-3");
  });

  test("HSE Manager title uses break-normal and line-clamp constraints", async ({
    page,
  }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    const title = page
      .locator("[data-testid='opportunity-card']")
      .first()
      .locator("[data-testid='opportunity-card-title']");
    const text = await title.textContent();
    expect(text).toContain("HSE Manager");
    // Assert CSS constraints prevent bad wrapping instead of inspecting textContent
    const classAttr = await title.getAttribute("class");
    expect(classAttr).toContain("break-normal");
    expect(classAttr).not.toContain("break-all");
  });

  test("link badges appear for live job", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    const firstCard = page.locator("[data-testid='opportunity-card']").first();
    const badge = firstCard.locator("[data-testid='link-status-badge']");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText(/live|verified/i);
  });

  test("expired link card does not show View job", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });
    // job-2 has expired link, so PrimaryAction returns "Find similar live jobs" instead of "View job"
    const expiredCard = page.locator("[data-testid='opportunity-card']").nth(1);
    const viewJobBtn = expiredCard.locator("[data-testid='view-job-action']");
    await expect(viewJobBtn).not.toBeVisible();
    const findSimilarBtn = expiredCard.locator(
      "[data-testid='find-similar-action']",
    );
    await expect(findSimilarBtn).toBeVisible();
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

    const cardsBtn = page.locator("[data-testid='view-mode-toggle-card']");
    const focusBtn = page.locator("[data-testid='view-mode-toggle-list']");

    if ((await cardsBtn.count()) > 0 && (await focusBtn.count()) > 0) {
      await focusBtn.click();
      const grid = page.locator("[data-testid='signals-grid']");
      const classes = await grid.getAttribute("class");
      expect(classes).toContain("grid-cols-1");

      await cardsBtn.click();
      const classesAfter = await grid.getAttribute("class");
      expect(classesAfter).toContain("xl:grid-cols-2");
    }
  });

  }); // end test.describe.skip "card UI tests"

  test("no infinite API request loop for link verification", async ({
    page,
  }) => {
    let verifyCallCount = 0;
    await page.route(
      `${PROXY_API}/links/verify/batch`,
      async (route, request) => {
        verifyCallCount++;
        const body = request.postDataJSON();
        const urls: string[] = body?.urls ?? [];
        const result: Record<string, unknown> = {};
        for (const url of urls) {
          result[url] = {
            status: "live",
            http_status: 200,
            error_message: null,
            verified_at: new Date().toISOString(),
          };
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(result),
        });
      },
    );

    await page.goto("/signals");
    await page.waitForTimeout(3000);

    expect(verifyCallCount).toBeLessThanOrEqual(5);
  });

  test.skip("modal opens on card click and shows actions", async ({ page }) => {
    await page.goto("/signals");
    await page.waitForSelector("[data-testid='opportunity-card']", {
      state: "visible",
      timeout: 5000,
    });

    const firstCard = page.locator("[data-testid='opportunity-card']").first();
    await firstCard.click();

    const modal = page.locator("[data-testid='opportunity-detail-modal']");
    await expect(modal).toBeVisible();

    await expect(modal.locator("p").filter({ hasText: "86%" })).toBeVisible();
    await expect(
      modal.locator("[data-testid='view-job-action']"),
    ).toBeVisible();
  });
});
