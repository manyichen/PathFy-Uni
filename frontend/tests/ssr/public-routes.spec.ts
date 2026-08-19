import { expect, test } from '@playwright/test'

for (const [path, text] of [['/', '职业规划智能体'], ['/login', '登录'], ['/register', '注册']] as const) {
  test(`${path} hydrates meaningful static HTML without mismatch`, async ({ page }) => {
    const hydrationErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error' && /hydration|mismatch/i.test(message.text())) hydrationErrors.push(message.text())
    })
    page.on('pageerror', error => hydrationErrors.push(error.message))

    const response = await page.goto(path, { waitUntil: 'domcontentloaded' })
    expect(await response?.text()).toContain(text)
    await expect(path === '/' ? page.getByRole('heading', { name: text }) : page.getByText(text, { exact: true }).first()).toBeVisible()
    expect(hydrationErrors).toEqual([])
  })
}

test('SPA fallback handles a protected deep link before client auth redirect', async ({ page }) => {
  await page.goto('/report', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/login\?redirect=(?:%2F|\/)report/)
  await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()
})
