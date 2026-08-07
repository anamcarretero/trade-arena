import {defineConfig} from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "line",
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: "node tests/e2e/mock-api.mjs",
      url: "http://127.0.0.1:18080/health/live",
      reuseExistingServer: false
    },
    {
      command: "pnpm dev --port 3100",
      url: "http://localhost:3100/es/pricing",
      reuseExistingServer: !process.env.CI,
      env: {
        SESSION_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        APP_BASE_URL: "http://localhost:3100",
        API_BASE_URL: "http://127.0.0.1:18080",
        AUTH0_DOMAIN: "test.eu.auth0.com",
        AUTH0_CLIENT_ID: "test-client",
        AUTH0_CLIENT_SECRET: "test-secret",
        BFF_SHARED_SECRET: "test-shared-secret"
      }
    }
  ]
});
