import { expect, test } from '@playwright/test'
import {
  adminUser,
  fulfillJson,
  installStableApiMocks,
  reportWorkspace,
  seedAuthenticatedSession,
  standardUser
} from './support/pathfy-fixtures'

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
})

test('match history failure is shown inline in the report import dialog', async ({ page }) => {
  await page.route('**/api/match/history**', route => fulfillJson(route, {
    ok: false,
    code: 500,
    message: '匹配历史服务暂时不可用'
  }, 500))

  await page.goto('/report')
  await page.getByRole('button', { name: '导入匹配数据' }).click()

  await expect(page.getByText('匹配记录加载失败')).toBeVisible()
  await expect(page.getByText('匹配历史服务暂时不可用').first()).toBeVisible()
  await expect(page.locator('h1', { hasText: '职业生涯发展报告' })).toBeVisible()
})

test('report generation failure preserves the selected resume and target', async ({ page }) => {
  await page.addInitScript(workspace => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify({
      ...workspace,
      reportId: undefined,
      reportSnapshot: undefined
    }))
  }, reportWorkspace)
  await page.route('**/api/report/generate', route => fulfillJson(route, {
    ok: false,
    code: 503,
    message: '报告生成服务暂时不可用'
  }, 503))

  await page.goto('/report')
  await expect(page.getByText('数据分析师').first()).toBeVisible()
  await page.getByRole('button', { name: '生成 / 重新生成报告' }).click()

  await expect(page.getByText('报告生成服务暂时不可用').first()).toBeVisible()
  await expect(page.getByText('数据分析师').first()).toBeVisible()
  await expect(page.getByText('视觉基线用户 · 计算机科学与技术').first()).toBeVisible()
})

test('profile resume failure keeps the page usable', async ({ page }) => {
  await page.route('**/api/profile/resumes', route => fulfillJson(route, {
    code: 500,
    msg: '画像列表加载失败'
  }, 500))

  await page.goto('/profile')

  await expect(page.getByRole('heading', { name: '学生就业能力画像' })).toBeVisible()
  await expect(page.getByText('还没有能力画像')).toBeVisible()
  await expect(page.getByRole('button', { name: '生成能力画像' })).toBeVisible()
})

test('401 clears the local session and redirects to login', async ({ page }) => {
  await page.route(/\/api\/jobs(?:\?.*)?$/, route => fulfillJson(route, {
    ok: false,
    code: 401,
    message: '登录状态已失效'
  }, 401))

  await page.goto('/jobs')

  await expect(page).toHaveURL(/\/login\?redirect=%2Fjobs$/)
  await expect.poll(() => page.evaluate(() => localStorage.getItem('auth_token'))).toBeNull()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('auth_user'))).toBeNull()
})

test('a non-admin user cannot enter graph administration', async ({ page }) => {
  let graphRequestCount = 0
  await page.route('**/api/graph/**', async (route) => {
    graphRequestCount += 1
    await fulfillJson(route, { ok: false, code: 403, message: '权限不足' }, 403)
  })

  await page.goto('/graph-admin')

  await expect(page).toHaveURL(/\/$/)
  expect(graphRequestCount).toBe(0)
})

test('graph admin API 403 is readable and does not leave a loading screen', async ({ page }) => {
  await page.route('**/api/graph/**', route => fulfillJson(route, {
    ok: false,
    code: 403,
    message: '当前账户没有图谱读取权限'
  }, 403))

  await page.goto('/')
  await page.evaluate(user => {
    localStorage.setItem('auth_user', JSON.stringify(user))
  }, adminUser)
  await page.goto('/graph-admin')

  await expect(page.getByRole('heading', { name: '图谱 Dashboard' })).toBeVisible()
  await expect(page.getByText('Dashboard 加载失败', { exact: true })).toBeVisible()
  await expect(page.getByText(/当前账户没有图谱读取权限/).first()).toBeVisible()
  await expect(page.locator('.animate-pulse')).toHaveCount(0)
})
