import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'
import {
  adminUser,
  fulfillOk,
  installStableApiMocks,
  matchWorkspace,
  preferences,
  reportWorkspace,
  seedAuthenticatedSession
} from './support/pathfy-fixtures'

const viewports = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'dark-hue-1440', width: 1440, height: 900, theme: 'dark', hue: '320' }
] as const

const pages = [
  { name: 'home', path: '/', heading: '职业规划智能体', admin: false },
  { name: 'profile', path: '/profile', heading: '学生就业能力画像', admin: false },
  { name: 'match', path: '/match', heading: '人岗匹配', admin: false },
  { name: 'report', path: '/report', heading: '职业生涯发展报告', admin: false },
  { name: 'graph-admin', path: '/graph-admin', heading: '图谱 Dashboard', admin: true }
] as const

test.describe.configure({ mode: 'serial' })

for (const viewport of viewports) {
  test(`capture ${viewport.name} visual baseline`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await seedAuthenticatedSession(page)
    if ('theme' in viewport) {
      await page.addInitScript(({ theme, hue }) => {
        localStorage.setItem('theme', theme)
        localStorage.setItem('hue', hue)
      }, { theme: viewport.theme, hue: viewport.hue })
    }
    await page.addInitScript(({ match, report }) => {
      localStorage.setItem('career_pj_match_v1_1', JSON.stringify(match))
      localStorage.setItem('career_report_workspace_v1_1', JSON.stringify(report))
    }, { match: matchWorkspace, report: reportWorkspace })
    await installStableApiMocks(page)
    if ('theme' in viewport) {
      await page.route('**/api/account/preferences', route => fulfillOk(route, {
        stored: true,
        preferences: { ...preferences, theme: viewport.theme, hue: viewport.hue },
        effective: { ...preferences, theme: viewport.theme, hue: viewport.hue },
        limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 }
      }))
    }

    const outputDirectory = resolve('tests', 'visual-baseline', viewport.name)
    await mkdir(outputDirectory, { recursive: true })

    for (const target of pages) {
      if (target.admin) {
        await page.evaluate(user => {
          localStorage.setItem('auth_user', JSON.stringify(user))
        }, adminUser)
      }

      await page.goto(target.path)
      await expect(page.getByRole('heading', { name: target.heading }).first()).toBeVisible()
      await page.addStyleTag({
        content: `
          *, *::before, *::after {
            animation-delay: 0s !important;
            animation-duration: 0s !important;
            caret-color: transparent !important;
            transition-delay: 0s !important;
            transition-duration: 0s !important;
          }
        `
      })

      if (target.name === 'match') {
        await page.getByRole('button', { name: '选择比较' }).first().click()
      }
      if (target.name === 'report') await expect(page.locator('canvas').first()).toBeVisible()
      await page.evaluate(() => window.scrollTo(0, 0))
      // Nuxt dev keeps HMR and icon/font requests alive, so networkidle is not a stable visual-ready signal.
      await page.waitForTimeout(500)

      await page.screenshot({
        path: resolve(outputDirectory, `${target.name}.png`),
        fullPage: true,
        animations: 'disabled'
      })
    }
  })
}
