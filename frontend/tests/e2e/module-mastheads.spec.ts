import { expect, test } from '@playwright/test'
import { installStableApiMocks, reportWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

const modules = [
  { path: '/jobs', title: '岗位探索', mark: '01', edition: '岗位星图' },
  { path: '/profile', title: '学生就业能力画像', mark: '02', edition: '能力档案' },
  { path: '/match', title: '人岗匹配', mark: '03', edition: '匹配工作台' },
  { path: '/graph', title: '职业关联图谱', mark: '04', edition: '路径图谱' },
  { path: '/report', title: '我的生涯计划', mark: '05', edition: '生涯档案' },
  { path: '/personality', title: '职业性格测试', mark: '06', edition: '偏好档案' },
  { path: '/account', title: '个人中心', mark: '07', edition: '个人设置' }
]

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await page.addInitScript(report => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify(report))
  }, reportWorkspace)
  await installStableApiMocks(page)
})

test('primary modules use contextual archive mastheads instead of generic headings', async ({ page }) => {
  for (const module of modules) {
    await page.goto(module.path)
    const masthead = page.locator('.cockpit-page-header')
    await expect(masthead).toBeVisible()
    await expect(masthead.getByRole('heading', { name: module.title })).toBeVisible()
    await expect(masthead.locator('.cockpit-page-mark')).toHaveText(module.mark)
    await expect(masthead.getByText(module.edition, { exact: true })).toBeVisible()
    await expect(masthead.locator('.cockpit-page-mark')).toHaveText(/^0[1-7]$/)
  }
})

test('archive mastheads do not create horizontal overflow on desktop or mobile', async ({ page }) => {
  test.setTimeout(120_000)
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    for (const module of modules) {
      await page.goto(module.path)
      await expect(page.locator('.cockpit-page-header')).toBeVisible()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, `${module.path} at ${viewport.width}px`).toBeLessThanOrEqual(2)
    }
  }
})

test('home planning entry and report preview share one continuous workbench card', async ({ page }) => {
  await page.goto('/')
  const workbench = page.locator('.home-planning-workbench')
  await expect(workbench).toBeVisible()
  await expect(workbench.getByRole('heading', { name: '选择一个入口，直接开始规划' })).toBeVisible()
  await expect(workbench.getByRole('heading', { name: '报告不是终点，它是下一次行动的桌面' })).toBeVisible()
  await expect(workbench.locator('.module-browser')).toHaveCount(1)
  await expect(workbench.locator('.workroom')).toHaveCount(1)
  await expect(workbench).toHaveCSS('overflow', 'hidden')
})

test('header actions stay on the bottom row and numbered marks share one metric', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/graph')
  const graphMark = page.locator('.cockpit-page-mark')
  const graphBox = await graphMark.boundingBox()
  await expect(graphMark).toHaveCSS('font-variant-numeric', /tabular-nums/)

  await page.goto('/report')
  const header = page.locator('.cockpit-page-header')
  const reportMark = header.locator('.cockpit-page-mark')
  const reportBox = await reportMark.boundingBox()
  const actions = header.locator('.cockpit-page-actions')
  const toolbar = header.locator('.report-header-toolbar')
  const title = header.getByRole('heading', { name: '我的生涯计划' })
  const actionsBox = await actions.boundingBox()
  const titleBox = await title.boundingBox()

  await expect(actions).toHaveCSS('flex-wrap', 'nowrap')
  await expect(reportMark).toHaveCSS('opacity', '0.48')
  await expect(toolbar).toBeVisible()
  await expect(toolbar).toHaveCSS('display', 'flex')
  await expect(toolbar.getByRole('button', { name: 'AI 增强' })).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '编辑并导出 PDF' })).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '永久删除报告' })).toBeVisible()
  expect(graphBox && reportBox ? Math.abs(graphBox.height - reportBox.height) : Number.POSITIVE_INFINITY).toBeLessThanOrEqual(1)
  expect(actionsBox && titleBox ? actionsBox.y > titleBox.y : false).toBe(true)
})
