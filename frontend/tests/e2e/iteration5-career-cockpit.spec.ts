import { expect, test } from '@playwright/test'
import { installStableApiMocks, matchWorkspace, reportWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await page.addInitScript(({ match, report }) => {
    localStorage.setItem('career_pj_match_v1_1', JSON.stringify(match))
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify(report))
  }, { match: matchWorkspace, report: reportWorkspace })
  await installStableApiMocks(page)
})

test('semantic cockpit tokens respond to light, dark and custom hue', async ({ page }) => {
  await page.goto('/profile')
  const colors = await page.evaluate(() => {
    const probe = document.createElement('div')
    probe.style.background = 'var(--pathfy-capability)'
    document.body.append(probe)
    const read = () => getComputedStyle(probe).backgroundColor
    const light = read()
    document.documentElement.classList.add('dark')
    const dark = read()
    document.documentElement.style.setProperty('--pathfy-hue', '320')
    const custom = read()
    const tokens = ['--pathfy-capability', '--pathfy-gap', '--pathfy-success', '--pathfy-risk', '--pathfy-route', '--pathfy-evidence', '--pathfy-surface-workbench']
      .map(name => getComputedStyle(document.documentElement).getPropertyValue(name).trim())
    probe.remove()
    return { light, dark, custom, tokens }
  })
  expect(colors.tokens).not.toContain('')
  expect(colors.dark).not.toBe(colors.light)
  expect(colors.custom).not.toBe(colors.dark)
})

test('home exposes three first-screen entries and the five-stage workflow', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: '继续能力画像' })).toBeVisible()
  await expect(page.getByRole('link', { name: '继续岗位探索' })).toBeVisible()
  await expect(page.getByRole('link', { name: '继续生涯报告' })).toBeVisible()
  const workflow = page.getByRole('navigation', { name: '职业规划工作流' })
  await expect(workflow.getByRole('link')).toHaveCount(5)
})

test('profile and matching share the same information hierarchy', async ({ page }) => {
  await page.goto('/profile')
  await expect(page.getByText('01 · Primary View')).toBeVisible()
  await expect(page.getByText('02 · Supporting Evidence')).toBeVisible()
  await expect(page.getByText('03 · Next Action')).toBeVisible()
  await expect(page.getByRole('navigation', { name: '职业规划工作流' }).getByRole('link', { name: /画像/ })).toHaveAttribute('aria-current', 'step')

  await page.goto('/match')
  await expect(page.getByText('排名结果与比较依据')).toBeVisible()
  await expect(page.getByText('第 1 名 · 八维粗排')).toBeVisible()
  await expect(page.getByText('排名依据：').first()).toBeVisible()
})

test('report first screen answers status, target, largest gap and next action', async ({ page }) => {
  await page.goto('/report')
  for (const label of ['当前状态', '当前目标', '最大差距', '下一步']) await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
  await expect(page.getByText('数据分析师', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('社会网络 10 分')).toBeVisible()
  await expect(page.getByText('每周日提交一次进展复盘', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('88 匹配 · 10 最大差距')).toBeVisible()
})

test('route workspace exposes the real report path through keyboard navigation', async ({ page }) => {
  await page.goto('/report')
  const routeTab = page.getByRole('tab', { name: /路线/ })
  await routeTab.focus()
  await page.keyboard.press('Enter')
  await expect(routeTab).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: '12 个月已验证成长轨迹' })).toBeVisible()
  await expect(page.locator('canvas.report-path-canvas')).toBeVisible()
})

test('reduced motion removes the decorative hero wave animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const animation = await page.locator('.home-hero-waves use').first().evaluate(element => getComputedStyle(element).animationName)
  expect(animation).toBe('none')
})

test('cockpit pages remain free of horizontal document overflow at target viewports', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    for (const path of ['/', '/profile', '/match', '/report']) {
      await page.goto(path)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, `${path} at ${viewport.width}px`).toBeLessThanOrEqual(1)
    }
  }
})
