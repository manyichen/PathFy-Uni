import { expect, test } from '@playwright/test'

const successEnvelope = {
  ok: true,
  code: 200,
  data: {
    token: 'journey-token',
    user: { id: 8, username: '路径用户', email: 'path@example.com', is_admin: false }
  }
}

test('renders the white-bird journey and reveals home only after authentication succeeds', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(successEnvelope)
  }))

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await expect(page.getByText('回来，继续向前。')).toBeVisible()
  await expect(page.locator('.auth-journey-canvas-layer canvas')).toBeVisible()

  await page.getByLabel('账号').fill('path@example.com')
  await page.getByLabel('密码').fill('path-pass')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  const layer = page.locator('.auth-journey-canvas-layer')
  await expect(layer).toHaveClass(/is-transitioning/)
  await page.waitForTimeout(180)
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/)
  await expect(page).toHaveURL(/\/$/, { timeout: 9_000 })
  await expect(page.getByRole('heading', { name: '职业规划智能体' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('auth_token'))).toBe('journey-token')
  expect(pageErrors).toEqual([])
})

test('keeps the form and plays the restrained error response when authentication fails', async ({ page }) => {
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ ok: false, code: 401, message: '账号或密码错误' })
  }))

  await page.goto('/login')
  await page.getByLabel('账号').fill('wrong@example.com')
  await page.getByLabel('密码').fill('wrong-pass')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page.getByText('账号或密码错误', { exact: true })).toBeVisible()
  await expect(page.locator('.auth-journey-canvas-layer')).toHaveAttribute('data-state', 'error')
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test('uses the compact registration composition on mobile without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/register')

  await expect(page.getByRole('heading', { name: '创建你的路径' })).toBeVisible()
  await expect(page.getByText('从一个起点，看见更多方向。')).toBeVisible()
  await expect(page.locator('.auth-journey-stage')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

test('shortens the success reveal for reduced-motion users', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(successEnvelope)
  }))

  await page.goto('/login')
  await page.getByLabel('账号').fill('path@example.com')
  await page.getByLabel('密码').fill('path-pass')
  const startedAt = Date.now()
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 1_200 })
  expect(Date.now() - startedAt).toBeLessThan(1_000)
})
