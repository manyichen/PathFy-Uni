import { expect, test, type Page } from '@playwright/test'
import { installStableApiMocks, seedAuthenticatedSession } from './support/pathfy-fixtures'

declare global {
  interface Window {
    __workflowExperienceEvents?: Array<{ name: string; stage?: string }>
  }
}

async function openExperience(page: Page) {
  await page.goto('/')
  const trigger = page.getByRole('button', { name: '体验五阶段职业路径' })
  await expect(page.locator('canvas.home-workflow-experience-canvas')).toHaveCount(0)
  await trigger.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: '职业规划五阶段路径体验' })).toBeVisible()
  await expect(page.locator('canvas.home-workflow-experience-canvas')).toBeVisible()
  return { trigger, dialog }
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.addInitScript(() => {
    window.__workflowExperienceEvents = []
    window.addEventListener('pathfy:workflow-experience', (event) => {
      const detail = (event as CustomEvent<{ name: string; stage?: string }>).detail
      window.__workflowExperienceEvents?.push({ name: detail.name, stage: detail.stage })
    })
  })
})

test('active home workflow experience stays illustrative and links canvas stages to real modules', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') pageErrors.push(message.text()) })
  const { trigger, dialog } = await openExperience(page)

  await expect(dialog.getByText(/不读取或推测你的个人材料、画像和规划进度/)).toBeVisible()
  await expect(dialog.getByRole('button', { name: /材料.*建立证据/ })).toHaveAttribute('aria-current', 'step')

  const canvas = page.locator('canvas.home-workflow-experience-canvas')
  const box = await canvas.boundingBox()
  if (!box) throw new Error('home workflow experience canvas has no layout box')
  const index = 2
  const padding = box.width < 560 ? 34 : 58
  const x = padding + (box.width - padding * 2) * index / 4
  const y = box.height * .54 + Math.sin(index * 1.32 - .7) * Math.min(38, box.height * .095)
  await canvas.click({ position: { x, y } })
  await expect(dialog.getByRole('heading', { name: '匹配 · 比较岗位' })).toBeVisible()
  await expect(dialog.getByRole('link', { name: '进入匹配模块' })).toHaveAttribute('href', '/match')

  await dialog.getByRole('button', { name: /复盘.*校准路线/ }).click()
  await expect(dialog.getByRole('heading', { name: '复盘 · 校准路线' })).toBeVisible()
  await expect(dialog.getByText(/根据真实完成情况继续修正计划/)).toBeVisible()
  await dialog.getByRole('button', { name: '关闭流程演示' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(trigger).toBeFocused()

  const eventNames = await page.evaluate(() => window.__workflowExperienceEvents || [])
  expect(eventNames).toEqual(expect.arrayContaining([
    expect.objectContaining({ name: 'open', stage: 'material' }),
    expect.objectContaining({ name: 'stage', stage: 'match' }),
    expect.objectContaining({ name: 'complete', stage: 'review' }),
    expect.objectContaining({ name: 'exit', stage: 'review' })
  ]))
  expect(pageErrors).toEqual([])
})

test('reduced motion keeps the home workflow experience static and manual', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const { dialog } = await openExperience(page)
  const canvas = page.locator('canvas.home-workflow-experience-canvas')
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  await page.waitForTimeout(1550)
  const secondFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())

  expect(secondFrame).toBe(firstFrame)
  await expect(dialog.getByRole('button', { name: /材料.*建立证据/ })).toHaveAttribute('aria-current', 'step')
  await expect(dialog.getByRole('button', { name: '继续流程演示' })).toBeDisabled()
  await dialog.getByRole('button', { name: '下一步' }).click()
  await expect(dialog.getByRole('heading', { name: '画像 · 识别能力' })).toBeVisible()
})
