import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60000,
  reporter: [
    ["list"],
    ["json", { outputFile: "../reports/browser-tests.json" }],
  ],
  use: {
    baseURL: process.env.UI_URL || "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 1000 },
    headless: true,
    launchOptions: process.env.CHROME_EXECUTABLE
      ? {
          executablePath: process.env.CHROME_EXECUTABLE,
          args: ["--no-sandbox"],
        }
      : {},
  },
  webServer: process.env.CI
    ? {
        command: "npm run dev",
        url: "http://127.0.0.1:5173",
        reuseExistingServer: true,
      }
    : undefined,
});
