import { defineConfig } from '@playwright/test'

const port = Number(process.env.PLAYWRIGHT_PORT || 4321)
const baseURL = `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/visual-baseline.capture.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  outputDir: './test-results/visual-baseline',
  expect: { timeout: 20_000 },
  use: {
    baseURL,
    colorScheme: 'light',
    locale: 'zh-CN',
    reducedMotion: 'reduce',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: `pnpm exec nuxt dev --host 127.0.0.1 --port ${port}`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000
  }
})
