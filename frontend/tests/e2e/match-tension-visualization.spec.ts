import { expect, test } from '@playwright/test'
import { installStableApiMocks, matchWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.addInitScript((workspace) => {
    localStorage.setItem('career_pj_match_v1_1', JSON.stringify({
      v: 1,
      resumeId: 1,
      filters: { q: '数据', locationQ: '上海', goal: 'fit', refine: true },
      result: workspace.result
    }))
  }, matchWorkspace)
})

test('match tension field renders lazily and transitions when the selected job changes', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))

  await page.goto('/match')
  const selectButtons = page.getByRole('button', { name: '选择比较' })
  await selectButtons.first().click()

  await expect(page.getByRole('heading', { name: '能力张力场' })).toBeVisible()
  await expect(page.getByText(/节点旁同时标注画像分与岗位要求分/)).toBeVisible()
  await page.getByRole('heading', { name: '能力张力场' }).scrollIntoViewIfNeeded()
  await expect(page.locator('canvas.match-tension-canvas')).toBeVisible()
  await page.getByRole('button', { name: '查看完整岗位详情' }).scrollIntoViewIfNeeded()
  await expect(page.locator('.comparison-panel canvas')).toHaveCount(1)
  await expect(page.getByText('八维能力雷达图', { exact: true })).toHaveCount(0)
  expect(await page.locator('.match-comparison-float').evaluate(element => getComputedStyle(element).position)).toBe('sticky')

  await selectButtons.nth(1).click()
  await expect(page.locator('.comparison-panel h3', { hasText: '商业分析师' })).toBeVisible()
  await expect(page.getByText('当前最大缺口：交叉学科 12 分')).toBeVisible()
  await page.getByRole('button', { name: '重播张力变化' }).click()
  await expect(page.locator('canvas.match-tension-canvas')).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('match tension field is immediately static when reduced motion is requested', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/match')
  await page.getByRole('button', { name: '选择比较' }).first().click()
  await page.getByRole('heading', { name: '能力张力场' }).scrollIntoViewIfNeeded()

  const canvas = page.locator('canvas.match-tension-canvas')
  await expect(canvas).toBeVisible()
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  await page.waitForTimeout(180)
  const secondFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  expect(secondFrame).toBe(firstFrame)
})
