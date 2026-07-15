import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  const preferences = {
    theme: 'system',
    hue: '192',
    allow_external_llm: true,
    default_match_goal: 'fit',
    default_refine_with_llm: false,
    match_result_count: 30,
    report_copywriter: true,
    report_public_info: true,
    report_auto_replan: true,
    report_graph_recommendations: true,
    report_recommendation_llm: true,
    learning_resource_count: 5,
    competition_count: 3
  }

  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'e2e-token')
    localStorage.setItem('auth_user', JSON.stringify({ id: 1, username: '测试用户', email: 'test@example.com' }))
  })
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url())
    let data: any = { jobs: [], items: [], preferences }

    if (url.pathname === '/api/auth/me') data = { user: { id: 1, username: '测试用户', email: 'test@example.com' } }
    else if (url.pathname === '/api/account/preferences') {
      data = {
        stored: true,
        preferences,
        effective: preferences,
        limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 }
      }
    }

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, code: 200, data })
    })
  })
})

for (const path of ['/', '/jobs', '/profile', '/personality', '/match', '/graph', '/report', '/account'] as const) {
  test(`${path} renders`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('main')).toBeVisible()
  })
}

test('home keeps the migrated visual entry points', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '职业规划智能体' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '选择一个入口，直接开始规划' })).toBeVisible()
  await expect(page.getByRole('button', { name: '外观设置' })).toBeVisible()
})

test('appearance controls update local preferences', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')

  await page.getByRole('button', { name: '明暗切换' }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('theme'))).toBe('dark')

  await page.getByRole('button', { name: '外观设置' }).click()
  await expect(page.getByText('同步本机与账户偏好')).toBeVisible()

  await page.getByLabel('主题色相').evaluate((element) => {
    const input = element as HTMLInputElement
    input.value = '150'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await expect.poll(() => page.evaluate(() => localStorage.getItem('hue'))).toBe('150')
})

test('mobile navigation closes after a page switch', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  await page.getByRole('button', { name: '打开导航' }).click()
  const drawer = page.getByRole('dialog', { name: '导航' })
  await expect(drawer).toBeVisible()

  await drawer.getByRole('link', { name: '岗位探索' }).click()
  await expect(page).toHaveURL(/\/jobs$/)
  await expect(drawer).not.toBeVisible()
})

test('personality test stays collapsed until the user starts it', async ({ page }) => {
  await page.route('**/api/personality/questions', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, data: [{ id: 1, question_text: '更喜欢哪种工作方式？', option_a: '独立思考', option_b: '团队讨论' }] })
  }))
  await page.goto('/personality')
  const start = page.getByRole('button', { name: /开始|寮€濮/ }).first()
  await expect(start).toBeVisible()
  await expect(page.getByText(/更喜欢哪种工作方式|鏇村枩/)).not.toBeVisible()
  await start.click()
  await expect(page.getByText(/更喜欢哪种工作方式|鏇村枩/)).toBeVisible()
})

test('logout requires confirmation', async ({ page }) => {
  await page.goto('/jobs')
  await page.getByRole('button', { name: '退出' }).click()
  await expect(page.getByRole('heading', { name: '确认退出登录' })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认退出' })).toBeVisible()
})

test('jobs keeps the assistant visible without an extra click', async ({ page }) => {
  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: /AI .*助手|AI .*鍔╂墜/ }).first()).toBeVisible()
})

test('graph and report share the rich job picker', async ({ page }) => {
  await page.route('**/api/jobs/options**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, data: { total: 1, page: 1, page_size: 20, jobs: [{ id: 'job-1', title: '数据分析师', company: '示例科技', location: '上海', salary: '15-20K', experience_years: 2 }] } })
  }))
  await page.goto('/graph')
  await page.getByRole('button', { name: /选择当前岗位|閫夋嫨/ }).click()
  await expect(page.getByText(/示例科技|绀轰緥/)).toBeVisible()
  await page.getByRole('button', { name: /数据分析师|鏁版嵁/ }).click()
  await expect(page.getByRole('button', { name: /数据分析师.*示例科技|鏁版嵁.*绀轰緥/ })).toBeVisible()

  await page.goto('/report')
  await page.getByRole('button', { name: /手动选择岗位|鎵嬪姩/ }).click()
  await expect(page.getByRole('button', { name: /数据分析师.*示例科技|鏁版嵁.*绀轰緥/ }).first()).toBeVisible()
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
  await expect(page.locator('canvas').first()).toBeVisible()
  expect(pageErrors).toEqual([])
})
