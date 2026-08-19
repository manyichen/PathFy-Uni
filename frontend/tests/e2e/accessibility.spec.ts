import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { installStableApiMocks, matchWorkspace, reportWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

async function expectNoSeriousViolations(page: Page) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const violations = result.violations.filter(item => ['critical', 'serious'].includes(item.impact || ''))
  const summary = violations.map(item => `${item.id}: ${item.nodes.map(node => node.target.join(' ')).join(', ')}`).join('\n')
  expect(violations, summary).toEqual([])
}

test('public entry has no serious automated WCAG violations', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '职业规划智能体' })).toBeVisible()
  await expectNoSeriousViolations(page)
  await page.evaluate(() => document.documentElement.classList.add('dark'))
  await page.waitForTimeout(600)
  await expectNoSeriousViolations(page)
})

test('authenticated profile, match and report workspaces pass automated WCAG scan', async ({ page }) => {
  await seedAuthenticatedSession(page)
  await page.addInitScript(({ match, report }) => {
    localStorage.setItem('career_pj_match_v1_1', JSON.stringify(match))
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify(report))
  }, { match: matchWorkspace, report: reportWorkspace })
  await installStableApiMocks(page)

  for (const path of ['/profile', '/match', '/report']) {
    await page.goto(path)
    await expect(page.getByRole('main')).toBeVisible()
    // Nuxt dev keeps HMR and on-demand icon requests alive; wait for the rendered workspace instead.
    await page.waitForTimeout(600)
    await expectNoSeriousViolations(page)
  }
})

test('core actions remain usable at a 200 percent equivalent viewport', async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 450 })
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.goto('/profile')
  await expect(page.getByRole('button', { name: '生成能力画像' })).toBeVisible()
  await expect(page.getByRole('button', { name: '历史画像' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(2)
})
