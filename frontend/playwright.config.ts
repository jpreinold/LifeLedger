import { defineConfig, devices } from '@playwright/test'

const deployed = process.env.E2E_MODE === 'deployed'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: deployed && process.env.CI ? 'line' : process.env.CI ? 'github' : 'list',
  timeout: deployed ? 180_000 : 30_000,
  use: {
    baseURL: deployed ? process.env.E2E_BASE_URL : 'http://127.0.0.1:4173',
    trace: deployed ? 'off' : 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: deployed ? 'off' : 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: deployed ? undefined : {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
})
