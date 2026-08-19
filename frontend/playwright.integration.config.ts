import { defineConfig } from '@playwright/test'

const frontendPort = 4341
const backendPort = 5011

export default defineConfig({
  testDir: './tests/integration',
  workers: 1,
  expect: { timeout: 20_000 },
  use: { baseURL: `http://127.0.0.1:${frontendPort}`, trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'python ../backend/tests/frontend_integration_server.py',
      url: `http://127.0.0.1:${backendPort}/api/health`,
      env: { ...process.env, PATHFY_INTEGRATION_PORT: String(backendPort) },
      reuseExistingServer: true,
      timeout: 60_000
    },
    {
      command: `pnpm exec nuxt dev --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      env: { ...process.env, FLASK_BACKEND: `http://127.0.0.1:${backendPort}` },
      reuseExistingServer: true,
      timeout: 120_000
    }
  ]
})
