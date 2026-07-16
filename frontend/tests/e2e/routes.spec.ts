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

test('graph and report share the rich job picker', async ({ page }) => {
  await page.route('**/api/jobs/options**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, data: { total: 1, page: 1, page_size: 20, jobs: [{ id: 'job-1', title: '数据分析师', company: '示例科技', location: '上海', salary: '15-20K', experience_years: 2 }] } })
  }))
  await page.goto('/graph')
  await page.getByRole('button', { name: '选择当前岗位' }).click()
  await expect(page.getByText('示例科技')).toBeVisible()
  await expect(page.getByText('2 年经验', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: /数据分析师/ }).click()
  await expect(page.getByText('示例科技 · 上海')).toBeVisible()

  await page.goto('/report')
  await page.getByRole('button', { name: '岗位库' }).click()
  await expect(page.getByText('示例科技')).toBeVisible()
})

test('report keeps the development line chart and guidance copy', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify({
      v: 1,
      reportSnapshot: {
        generated_at: '2026-07-14T12:00:00',
        targets: [],
        development_lines: { lines: [{ line_id: 'line-1', line_name: '数据分析师发展线', timeline: [{ month: 0, progress: 0, label: '起点' }, { month: 3, progress: 35, label: '完成项目' }] }] },
        plans_by_target: [],
        evaluation: { metrics: [] }
      }
    }))
  })
  await page.goto('/report')
  await expect(page.getByRole('heading', { name: '发展线与复盘节点' })).toBeVisible()
  expect(pageErrors).toEqual([])
  await expect(page.locator('canvas').first()).toBeVisible()
  await expect(page.getByText('折线不是预测结果')).toBeVisible()
})
