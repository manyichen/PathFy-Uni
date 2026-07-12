import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'e2e-token')
    localStorage.setItem('auth_user', JSON.stringify({ id: 1, username: '测试用户', email: 'test@example.com' }))
  })
  await page.route('**/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, code: 200, data: { jobs: [], items: [] } }) }))
})

for (const [path, heading] of [
  ['/', '从能力画像到职业行动计划'], ['/jobs', '岗位探索'], ['/profile', '学生就业能力画像'],
  ['/personality', '职业性格测试'], ['/match', '人岗匹配'], ['/graph', '职业关联图谱'], ['/report', '职业生涯发展报告']
] as const) {
  test(`${path} renders`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible()
  })
}
