import { defineConfig } from "@playwright/test"

const remote = process.env.STORYBOOK_URL
export default defineConfig({
  testDir: "./storybook-tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 4,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: remote ?? "http://localhost:6006",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
    screenshot: "only-on-failure",
    trace: "off",
  },
  projects: [
    { name: "dark-desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "light-desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "dark-mobile", use: { viewport: { width: 390, height: 844 } } },
    { name: "light-mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: remote
    ? undefined
    : {
        command: "python -m http.server 6006 --directory storybook-static",
        url: "http://localhost:6006",
        reuseExistingServer: true,
      },
})
