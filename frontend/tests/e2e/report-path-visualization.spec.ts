import { expect, test, type Page } from '@playwright/test'
import type { CareerReport } from '../../app/types/report'
import { fulfillOk, installStableApiMocks, reportWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

function eventReport(): CareerReport {
  const report = structuredClone(reportWorkspace.reportSnapshot) as CareerReport
  const plan = report.plans_by_target?.[0]
  if (plan) plan.line_id = 'data-line'
  report.llm_enrich_pending = false
  report.development_lines = {
    axis: { x_min: 0, x_max: 12, y_min: 0, y_max: 100 },
    lines: [{
      line_id: 'data-line',
      line_name: '数据分析师真实路径',
      target_job_id: 'job-1',
      timeline: [
        { month: 0, label: '报告生成', kind: 'origin' },
        { month: 1, label: '作品集计划', kind: 'plan' },
        { month: 2, progress: 46, label: '月度复盘', kind: 'review', review_id: 11, detail: { review_text: '完成了第一版作品集。', submitted: { portfolio: 1 } } }
      ]
    }],
    adjustments: [{
      id: 'adj-1', line_id: 'data-line', target_job_id: 'job-1',
      anchor_review_month: 2, plan_month: 3, label: '加强项目表达', kind: 'replan', replan_mode: 'strong',
      execution_hints: ['补充五分钟项目讲解']
    }]
  }
  return report
}

async function seedReport(page: Page, selectedMonth = 0) {
  const report = eventReport()
  await page.addInitScript(({ workspace, snapshot, month }) => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify({
      ...workspace,
      reportSnapshot: snapshot,
      report: snapshot,
      activeJobId: 'job-1',
      selectedMonth: month,
      selectedCanvasMonth: month
    }))
  }, { workspace: reportWorkspace, snapshot: report, month: selectedMonth })
  await page.route('**/api/report/42', route => fulfillOk(route, {
    report_id: 42,
    resume_id: 1,
    primary_job_id: 'job-1',
    target_job_ids: ['job-1'],
    report,
    llm_enrich_pending: false
  }))
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
})

test('report path renders only real events and synchronizes canvas selection with month detail', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') pageErrors.push(message.text()) })
  await seedReport(page)
  await page.goto('/report')
  await page.getByRole('tab', { name: /路线/ }).click()

  await expect(page.getByRole('heading', { name: '12 个月已验证成长轨迹' })).toBeVisible()
  await expect(page.getByText('ROUTE SIGNATURE / REVIEW-BASED')).toBeVisible()
  await expect(page.getByText('VERIFIED POSITION')).toBeVisible()
  await expect(page.getByText('MONTH MARKERS')).toBeVisible()
  await expect(page.getByText('复盘数据驱动', { exact: true })).toBeVisible()
  await expect(page.getByText('次真实写入', { exact: true })).toBeVisible()
  await expect(page.getByText('次已记录变更', { exact: true })).toBeVisible()
  await expect(page.getByText(/没有复盘就不画线/)).toBeVisible()
  await page.getByRole('heading', { name: '12 个月已验证成长轨迹' }).scrollIntoViewIfNeeded()
  const canvas = page.locator('canvas.report-path-canvas')
  await expect(canvas).toBeVisible()
  await page.waitForTimeout(100)
  expect(pageErrors).toEqual([])

  const box = await canvas.boundingBox()
  if (!box) throw new Error('report path canvas has no layout box')
  const x = 42 + (2 / 12) * (box.width - 76)
  const y = 54 + (1 - .46) * (box.height - 102)
  await canvas.click({ position: { x, y } })
  await expect(page.getByRole('heading', { name: '第 2 月详情' })).toBeVisible()
  await expect(page.getByText('SELECTED COORDINATE / 已选坐标')).toBeVisible()
  await expect(page.getByText('完成了第一版作品集。')).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('restored report path is immediately static, including reduced-motion mode', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await seedReport(page, 2)
  await page.goto('/report')
  await page.getByRole('tab', { name: /路线/ }).click()

  await page.getByRole('heading', { name: '12 个月已验证成长轨迹' }).scrollIntoViewIfNeeded()
  const canvas = page.locator('canvas.report-path-canvas')
  await expect(canvas).toBeVisible()
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  await page.waitForTimeout(180)
  const secondFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  expect(secondFrame).toBe(firstFrame)
  await expect(page.getByRole('heading', { name: '第 2 月详情' })).toBeVisible()
})
