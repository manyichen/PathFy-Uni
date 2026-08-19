import { defineConfig } from '@playwright/test'

const port = 4331

export default defineConfig({
  testDir: './tests/ssr',
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    command: 'node scripts/serve-static-fallback.mjs',
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: true,
    timeout: 60_000
  }
})
