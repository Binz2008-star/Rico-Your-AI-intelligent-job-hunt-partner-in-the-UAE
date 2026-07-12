import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for Rico Hunt frontend E2E tests.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
    {
      name: "Mobile Chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    // E2E exercises the real application, so the dev server must run with the
    // pre-launch teaser gate OFF. Otherwise `/` redirects to `/explainer`
    // (which 404s under `next dev`), the webServer readiness probe on `/` never
    // succeeds, and Playwright times out before a single test runs.
    timeout: 120_000,
    env: { NEXT_PUBLIC_SITE_LIVE: "true" },
  },
});
