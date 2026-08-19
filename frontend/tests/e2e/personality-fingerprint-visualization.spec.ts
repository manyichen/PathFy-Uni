import { expect, test, type Page } from '@playwright/test'
import { fulfillCode, installStableApiMocks, seedAuthenticatedSession } from './support/pathfy-fixtures'

const questions = Array.from({ length: 8 }, (_, index) => ({
  id: index + 1,
  question_text: `人格问题 ${index + 1}`,
  option_a: '偏好 A',
  option_b: '偏好 B'
}))

const measuredResult = {
  profile_id: 31,
  mbti_type: 'ENTJ',
  personality_analysis: '善于组织信息并推动目标落地。',
  complete_analysis: { name: '指挥官', summary: '偏好从全局结构出发，快速形成可执行方案。' },
  dimension_scores: [
    { code: 'EI', label: '能量来源', left: 'E', right: 'I', left_score: 75, right_score: 25, dominant: 'E', confidence: .5 },
    { code: 'SN', label: '信息偏好', left: 'S', right: 'N', left_score: 20, right_score: 80, dominant: 'N', confidence: .6 },
    { code: 'TF', label: '决策方式', left: 'T', right: 'F', left_score: 65, right_score: 35, dominant: 'T', confidence: .3 },
    { code: 'JP', label: '生活方式', left: 'J', right: 'P', left_score: 55, right_score: 45, dominant: 'J', confidence: .1 }
  ],
  dimension_analysis: [],
  recommended_jobs: []
}

async function seedPersonalityResult(page: Page, result: Record<string, unknown>) {
  await page.addInitScript((payload) => {
    localStorage.setItem('career_personality_v1_1', JSON.stringify({
      v: 1,
      answers: { 1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B', 6: 'A', 7: 'B', 8: 'A' },
      result: payload,
      started: true,
      currentQuestionIndex: 7,
      questionSignature: '1:2:3:4:5:6:7:8'
    }))
  }, result)
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.route('**/api/personality/questions', route => fulfillCode(route, questions))
})

test('measured personality result renders a stable data-derived fingerprint', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await seedPersonalityResult(page, measuredResult)

  await page.goto('/personality')
  await expect(page.getByRole('heading', { name: '人格视觉指纹' })).toBeVisible()
  await expect(page.getByText('真实倾向比例', { exact: true })).toBeVisible()
  await expect(page.getByText('N 80%', { exact: true })).toBeVisible()
  await expect(page.getByText(/不是心理诊断/)).toBeVisible()
  const canvas = page.locator('canvas.personality-fingerprint-canvas')
  await expect(canvas).toBeVisible()
  await page.waitForTimeout(100)
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())

  await page.reload()
  const restoredCanvas = page.locator('canvas.personality-fingerprint-canvas')
  await expect(restoredCanvas).toBeVisible()
  await page.waitForTimeout(100)
  const restoredFrame = await restoredCanvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  expect(restoredFrame).toBe(firstFrame)
  expect(pageErrors).toEqual([])
})

test('legacy result is explicitly presented as a non-measured type signature', async ({ page }) => {
  await seedPersonalityResult(page, { ...measuredResult, profile_id: 32, mbti_type: 'ISFP', dimension_scores: undefined })
  await page.goto('/personality')

  await expect(page.getByText('类型视觉签名', { exact: true })).toBeVisible()
  await expect(page.getByText('I · 类型预设', { exact: true })).toBeVisible()
  await expect(page.getByText(/不代表精确心理测量/)).toBeVisible()
  await expect(page.locator('canvas.personality-fingerprint-canvas')).toBeVisible()
})

test('fingerprint remains static when reduced motion is requested', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await seedPersonalityResult(page, measuredResult)
  await page.goto('/personality')

  const canvas = page.locator('canvas.personality-fingerprint-canvas')
  await expect(canvas).toBeVisible()
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  await page.waitForTimeout(180)
  const secondFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  expect(secondFrame).toBe(firstFrame)
})
