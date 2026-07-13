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
    // Next.js dev server cold-compiles on first request and fetches Google
    // Fonts at boot; the default 60s wait is too tight for CI runners and
    // times out before any test starts. Give it headroom and surface the
    // server's own logs so a genuine boot failure is diagnosable, not silent.
    timeout: 180_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
