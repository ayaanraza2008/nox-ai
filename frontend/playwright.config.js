import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    headless: true,
    viewport: { width: 1280, height: 900 },
    reducedMotion: "no-preference"
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173/core-smoke.html",
    reuseExistingServer: !process.env.CI,
    timeout: 30000
  }
});
