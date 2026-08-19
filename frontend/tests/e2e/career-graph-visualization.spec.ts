import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'career-graph-e2e')
    localStorage.setItem('auth_user', JSON.stringify({ id: 1, username: '图谱测试用户', email: 'graph@example.com' }))
  })

  await page.route('**://*/api/**', route => {
    const url = new URL(route.request().url())
    let data: unknown = {}

    if (url.pathname === '/api/auth/me') {
      data = { user: { id: 1, username: '图谱测试用户', email: 'graph@example.com' } }
    } else if (url.pathname === '/api/jobs/options') {
      data = { total: 1, page: 1, page_size: 20, jobs: [{ id: 'job-1', title: 'C/C++', company: '示例科技', location: '上海', salary: '15-20K' }] }
    } else if (url.pathname === '/api/jobs/job-1/promotion-path') {
      data = {
        job: { id: 'job-1', title: 'C/C++', company: '示例科技' },
        routes: [
          {
            id: 'route-1', route_title: '开发路线', confidence: .86,
            stages: [
              { stage: 1, role: 'C/C++初级工程师' },
              { stage: 2, role: 'C/C++开发工程师' },
              { stage: 3, role: '高级C/C++开发工程师' }
            ]
          },
          {
            id: 'route-2', route_title: '嵌入式路线', confidence: .82,
            stages: [
              { stage: 1, role: 'C/C++初级工程师' },
              { stage: 2, role: '嵌入式开发工程师' },
              { stage: 3, role: '高级嵌入式工程师 / 嵌入式架构师' }
            ]
          },
          {
            id: 'route-3', route_title: '系统路线', confidence: .8,
            stages: [
              { stage: 1, role: 'C/C++工程师' },
              { stage: 2, role: '系统开发工程师' },
              { stage: 3, role: '底层架构师 / 驱动开发专家' }
            ]
          }
        ]
      }
    } else if (url.pathname === '/api/jobs/job-1/lateral-paths') {
      data = {
        job: { id: 'job-1', title: 'C/C++', company: '示例科技' },
        routes: ['Java', '前端开发', '科研人员', '风电工程师', '测试工程师', '软件测试'].map((target_title, index) => ({
          id: `lateral-${index + 1}`,
          from_title: 'C/C++',
          target_title,
          cap_similarity: .9 - index * .04,
          rationale: '能力画像相近'
        }))
      }
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, code: 200, data }) })
  })
})

test('career graph renders lazily and keeps the complete list fallback', async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await page.goto('/graph')
  await page.getByRole('button', { name: '选择当前岗位' }).click()
  await page.getByRole('button', { name: /C\/C\+\+.*示例科技/ }).click()
  await page.getByRole('button', { name: '分析路径' }).click()

  await expect(page.getByRole('heading', { name: '职业路径星图' })).toBeVisible()
  const shell = page.locator('.p5-scene-shell')
  const canvas = page.locator('canvas.career-graph-canvas')
  await expect(canvas).toBeVisible()
  await expect.poll(() => consoleErrors).toEqual([])
  await expect(shell).toHaveAttribute('data-p5-scene-status', 'ready')
  await expect(page.getByText('15 个关系节点', { exact: true })).toBeVisible()
  await expect(page.getByText('嵌入式开发工程师', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('动态图谱暂时不可用。')).toBeHidden()

  const canvasSize = await canvas.evaluate(element => ({ width: element.clientWidth, height: element.clientHeight }))
  const currentPoint = { x: canvasSize.width / 2, y: canvasSize.height * .54 + 36 }
  await canvas.hover({ position: currentPoint })
  await expect.poll(() => canvas.evaluate(element => getComputedStyle(element).cursor)).toBe('pointer')

  const beforeZoom = await canvas.screenshot()
  await page.mouse.wheel(0, -120)
  await page.waitForTimeout(120)
  const afterZoom = await canvas.screenshot()
  expect(afterZoom.equals(beforeZoom)).toBe(false)

  const lateralSpread = Math.min(270, canvasSize.width * .3)
  const lateralAngle = Math.PI * .12
  const javaWorldY = 80 + Math.sin(lateralAngle) * Math.min(155, canvasSize.height * .22)
  const javaPoint = {
    x: currentPoint.x + Math.cos(lateralAngle) * lateralSpread * 1.1,
    y: currentPoint.y + (javaWorldY - 36) * 1.1
  }
  await canvas.click({ position: javaPoint })
  await expect(page.locator('.career-node-detail h3')).toHaveText('Java')

  const beforeDrag = await canvas.screenshot()
  await page.mouse.move(currentPoint.x + (await canvas.boundingBox())!.x, currentPoint.y + (await canvas.boundingBox())!.y)
  await page.mouse.down()
  await page.mouse.move(currentPoint.x + (await canvas.boundingBox())!.x + 80, currentPoint.y + (await canvas.boundingBox())!.y + 35, { steps: 5 })
  await page.mouse.up()
  await page.waitForTimeout(120)
  const afterDrag = await canvas.screenshot()
  expect(afterDrag.equals(beforeDrag)).toBe(false)

  await page.setViewportSize({ width: 1180, height: 820 })
  await expect(shell).toHaveAttribute('data-p5-scene-status', 'ready')
  await expect(page.getByText('动态图谱暂时不可用。')).toBeHidden()

  await page.getByRole('tab', { name: '列表' }).click()
  await expect(page.getByRole('heading', { name: '晋升路径' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '横向换岗' })).toBeVisible()
  await page.getByRole('tab', { name: '图谱' }).click()
  await expect(page.locator('canvas.career-graph-canvas')).toBeVisible()
  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('career graph stops loading and renders partial data when one path source fails', async ({ page }) => {
  await page.route('**/api/jobs/job-1/promotion-path**', route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ ok: false, message: '晋升路径查询超时，请稍后重试' })
  }))

  await page.goto('/graph')
  await page.getByRole('button', { name: '选择当前岗位' }).click()
  await page.getByRole('button', { name: /C\/C\+\+.*示例科技/ }).click()
  await page.getByRole('button', { name: '分析路径' }).click()

  await expect(page.getByText('部分路径数据暂时不可用')).toBeVisible()
  await expect(page.getByRole('heading', { name: '职业路径星图' })).toBeVisible()
  await expect(page.getByText('Java', { exact: true }).last()).toBeVisible()
  await expect(page.getByRole('button', { name: '分析路径' })).toBeEnabled()
  await expect(page.getByText('正在并行分析职业路径')).toBeHidden()

  await page.getByRole('tab', { name: '列表' }).click()
  await expect(page.getByRole('heading', { name: '横向换岗' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '晋升路径' })).toBeHidden()
})
