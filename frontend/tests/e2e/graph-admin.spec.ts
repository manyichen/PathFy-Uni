import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/account/preferences', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, data: { preferences: { theme: 'system', hue: '192' } } })
  }))
  await page.route('**/api/graph/**', async route => {
    const url = new URL(route.request().url())
    let data: any = {}
    if (url.pathname === '/api/graph/stats') data = { jobs: 10, job_titles: 4 }
    else if (url.pathname === '/api/graph/guard') data = { graph_revision: 3, locked: false }
    else if (/\/api\/graph\/tasks\/\d+$/.test(url.pathname)) data = { id: 7, status: 'awaiting_confirmation', task_type: 'job_import', input_file_name: 'jobs.xlsx', input_sha256: 'abc', mode: 'merge', change_summary: { new_or_changed_jobs: 2 }, events: [{ id: 1, message: '等待确认', stage: 'confirmation', event_type: 'prepared', created_at: '2026-07-13' }] }
    else if (url.pathname === '/api/graph/tasks') data = { items: [{ id: 7, status: 'awaiting_confirmation', task_type: 'job_import', input_file_name: 'jobs.xlsx' }], total: 1, page: 1, page_size: 20 }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, data }) })
  })
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.setItem('auth_token', 'admin-token')
    localStorage.setItem('auth_user', JSON.stringify({ id: 1, username: '管理员', is_admin: true }))
  })
})

for (const [path, heading] of [
  ['/graph-admin', '图谱 Dashboard'],
  ['/graph-admin/update', '更新图谱'],
  ['/graph-admin/tasks', '历史任务队列'],
  ['/graph-admin/tasks/7', '任务 #7'],
] as const) {
  test(`${path} renders`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible()
  })
}
