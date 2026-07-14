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

test('personality test stays collapsed until the user starts it', async ({ page }) => {
  await page.route('**/api/personality/questions', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, data: [{ id: 1, question_text: '更喜欢哪种工作方式？', option_a: '独立思考', option_b: '团队讨论' }] })
  }))
  await page.goto('/personality')
  await expect(page.getByRole('button', { name: '开始测试' })).toBeVisible()
  await expect(page.getByText('更喜欢哪种工作方式？')).not.toBeVisible()
  await page.getByRole('button', { name: '开始测试' }).click()
  await expect(page.getByText('更喜欢哪种工作方式？')).toBeVisible()
})

test('logout requires confirmation', async ({ page }) => {
  await page.goto('/jobs')
  await page.getByRole('button', { name: '退出' }).click()
  await expect(page.getByRole('heading', { name: '确认退出登录' })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认退出' })).toBeVisible()
})

test('jobs keeps the assistant visible without an extra click', async ({ page }) => {
  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: 'AI 岗位助手' })).toBeVisible()
  await expect(page.getByPlaceholder('输入岗位偏好或问题…')).toBeVisible()
})
