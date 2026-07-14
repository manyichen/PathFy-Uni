import { defineConfig } from '@playwright/test'

const port = Number(process.env.PLAYWRIGHT_PORT || 4321)
const baseURL = `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './tests/e2e',
  use: { baseURL, trace: 'retain-on-failure' },
  webServer: { command: `pnpm exec nuxt dev --host 127.0.0.1 --port ${port}`, url: baseURL, reuseExistingServer: true, timeout: 120_000 }
})
