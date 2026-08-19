import { expect, test, type Page, type Route } from '@playwright/test'
import { fulfillOk, installStableApiMocks, seedAuthenticatedSession } from './support/pathfy-fixtures'
import { buildJobConstellationSceneData } from '../../app/utils/visualization/job-constellation-adapter'
import { layoutJobConstellationNodes } from '../../app/utils/visualization/scenes/job-constellation-scene'

const baseScores = {
  cap_req_theory: 50, cap_req_cross: 50, cap_req_practice: 50, cap_req_digital: 50,
  cap_req_innovation: 50, cap_req_teamwork: 50, cap_req_social: 50, cap_req_growth: 50
}

const jobs = [
  { id: 'job-1', title: '数据分析师', company: '示例科技', location: '上海', salary: '15-22K', score_avg: 50, scores: baseScores },
  {
    id: 'job-2', title: '数字产品经理', company: '未来网络', location: '上海', salary: '18-26K', score_avg: 53,
    scores: { cap_req_theory: 10, cap_req_cross: 90, cap_req_practice: 10, cap_req_digital: 90, cap_req_innovation: 90, cap_req_teamwork: 10, cap_req_social: 10, cap_req_growth: 10 }
  }
]

function jobApi(route: Route) {
  const url = new URL(route.request().url())
  if (url.pathname === '/api/jobs') {
    return fulfillOk(route, { jobs, total: 42, page: 1, page_size: 20, total_pages: 3 })
  }
  if (url.pathname === '/api/jobs/assistant/sessions') return fulfillOk(route, { sessions: [] })
  if (url.pathname === '/api/jobs/assistant/chat') {
    return fulfillOk(route, {
      session_id: 7,
      assistant_message: { id: 9, role: 'assistant', content: '已按数字产品方向筛选。' },
      jobs: [jobs[1]]
    })
  }
  if (url.pathname === '/api/jobs/job-1') {
    return fulfillOk(route, { ...jobs[0], industry: '互联网数据服务', demand: '负责业务数据分析与指标建设。' })
  }
  if (url.pathname === '/api/jobs/job-2') return fulfillOk(route, jobs[1])
  return fulfillOk(route, {})
}

async function openConstellation(page: Page) {
  await page.goto('/jobs')
  await expect(page.getByRole('heading', { name: '数据分析师' })).toBeVisible()
  await expect(page.locator('canvas.job-constellation-canvas')).toHaveCount(0)
  await page.getByRole('button', { name: '星群' }).click()
  await expect(page.getByRole('heading', { name: '岗位星群' })).toBeVisible()
  await page.getByRole('heading', { name: '岗位星群' }).scrollIntoViewIfNeeded()
  await expect(page.locator('canvas.job-constellation-canvas')).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.route('**/api/jobs**', jobApi)
})

test('job constellation uses the current result boundary and canvas selection opens existing detail', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') pageErrors.push(message.text()) })
  await openConstellation(page)

  await expect(page.getByText('2 个当前岗位', { exact: true })).toBeVisible()
  await expect(page.getByText(/\d+ 个活跃能力星域/, { exact: true })).toBeVisible()
  await expect(page.getByText(/节点大小表示岗位要求均值，不代表个人匹配度或推荐排名/)).toBeVisible()
  await expect(page.getByText(/全部筛选结果共 42 个/)).toBeVisible()

  const canvas = page.locator('canvas.job-constellation-canvas')
  const box = await canvas.boundingBox()
  if (!box) throw new Error('job constellation canvas has no layout box')
  const scene = buildJobConstellationSceneData({ jobs, totalAvailable: 42, page: 1, pageSize: 20 })
  const node = layoutJobConstellationNodes(scene, box.width, box.height).nodes.find(item => item.node.id === 'job-1')
  if (!node) throw new Error('job-1 is missing from constellation layout')
  await canvas.click({ position: { x: node.x, y: node.y } })

  await expect(page.getByRole('heading', { name: '数据分析师' })).toBeVisible()
  await expect(page.getByText('负责业务数据分析与指标建设。')).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('reduced motion renders a stable constellation and list mode remains available', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openConstellation(page)
  const canvas = page.locator('canvas.job-constellation-canvas')
  const firstFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  await page.waitForTimeout(160)
  const secondFrame = await canvas.evaluate(element => (element as HTMLCanvasElement).toDataURL())
  expect(secondFrame).toBe(firstFrame)

  await page.getByRole('button', { name: '列表' }).click()
  await expect(page.locator('canvas.job-constellation-canvas')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '数据分析师' })).toBeVisible()
})

test('refresh button requests a new random exploration batch', async ({ page }) => {
  let randomRequest = ''
  const randomJob = { ...jobs[0], id: 'random-job', title: '随机探索岗位' }
  await page.route('**/api/jobs?*', route => {
    const url = new URL(route.request().url())
    if (url.searchParams.get('sort') === 'random') {
      randomRequest = url.toString()
      return fulfillOk(route, { jobs: [randomJob], total: 42, page: 1, page_size: 20, total_pages: 3, seed: url.searchParams.get('seed') })
    }
    return fulfillOk(route, { jobs, total: 42, page: 1, page_size: 20, total_pages: 3 })
  })

  await openConstellation(page)
  await page.getByRole('button', { name: '随机探索一批岗位' }).click()

  await expect.poll(() => randomRequest).toContain('sort=random')
  expect(new URL(randomRequest).searchParams.get('seed')).toBeTruthy()
  await expect(page.getByRole('button', { name: /随机探索岗位/ })).toBeVisible()
})

test('assistant results replace the constellation boundary without inventing ranking data', async ({ page }) => {
  await openConstellation(page)
  await page.getByPlaceholder('输入岗位偏好或问题…').fill('只看数字产品方向')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('AI 筛选', { exact: true })).toBeVisible()
  await expect(page.getByText('1 个当前岗位', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /数字产品经理.*未来网络.*上海/ })).toBeVisible()
  await expect(page.getByText(/节点大小表示岗位要求均值，不代表个人匹配度或推荐排名/)).toBeVisible()
})

test('assistant result window can exceed twenty while the list remains paged', async ({ page }) => {
  const assistantJobs = Array.from({ length: 25 }, (_, index) => ({
    ...jobs[0],
    id: `assistant-job-${index + 1}`,
    title: `助手岗位 ${index + 1}`
  }))
  await page.route('**/api/jobs/assistant/chat', route => fulfillOk(route, {
    session_id: 8,
    assistant_message: { id: 10, role: 'assistant', content: '已返回完整筛选窗口。' },
    jobs: assistantJobs
  }))

  await page.goto('/jobs')
  await page.getByPlaceholder('输入岗位偏好或问题…').fill('给我更多岗位')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('共 25 个岗位，每页展示 20 个')).toBeVisible()
  await expect(page.locator('.job-card')).toHaveCount(20)
  await expect(page.getByRole('heading', { name: '助手岗位 21' })).toHaveCount(0)
})

test('desktop assistant column stays anchored while the job list scrolls', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 800 })
  const manyJobs = Array.from({ length: 30 }, (_, index) => ({
    ...jobs[0],
    id: `list-job-${index + 1}`,
    title: `列表岗位 ${index + 1}`
  }))
  await page.route('**/api/jobs?*', route => fulfillOk(route, {
    jobs: manyJobs,
    total: manyJobs.length,
    page: 1,
    page_size: 30,
    total_pages: 1
  }))

  await page.goto('/jobs')
  const assistant = page.locator('.assistant-column')
  await expect(assistant).toHaveCSS('position', 'sticky')
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await expect.poll(async () => Math.round((await assistant.boundingBox())?.y || 0)).toBe(76)
})
