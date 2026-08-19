import { expect, test } from '@playwright/test'
import { fulfillCode, fulfillJson, fulfillOk, installStableApiMocks, preferences, profileDetail, seedAuthenticatedSession } from './support/pathfy-fixtures'

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
})

test('profile classifies selected files and provides explicit removal', async ({ page }) => {
  await page.goto('/profile')
  const input = page.locator('#profile-material-input')
  await input.setInputFiles([
    { name: '个人简历.pdf', mimeType: 'application/pdf', buffer: Buffer.from('resume') },
    { name: '英语证书.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('certificate') },
    { name: '课程成绩.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('scores') },
    { name: '数据项目说明.md', mimeType: 'text/markdown', buffer: Buffer.from('project') }
  ])
  for (const category of ['简历', '证书', '成绩', '项目']) await expect(page.getByText(category, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '移除 英语证书.jpg' }).click()
  await expect(page.getByText('英语证书.jpg')).toHaveCount(0)
})

test('profile upload failure preserves the complete draft', async ({ page }) => {
  await page.route('**/api/profile/upload', route => fulfillJson(route, { code: 500, msg: 'OCR 分析暂时失败' }, 500))
  await page.goto('/profile')
  await page.getByLabel('姓名').fill('小林')
  await page.getByLabel('专业').fill('软件工程')
  await page.getByPlaceholder('补充课程、项目、竞赛或职业目标').fill('参加过数据分析项目')
  await page.getByRole('button', { name: '生成能力画像' }).click()
  await expect(page.getByText('OCR 分析暂时失败')).toBeVisible()
  await expect(page.getByLabel('姓名')).toHaveValue('小林')
  await expect(page.getByLabel('专业')).toHaveValue('软件工程')
  await expect(page.getByPlaceholder('补充课程、项目、竞赛或职业目标')).toHaveValue('参加过数据分析项目')
})

test('profile history failure stays in the modal and can retry', async ({ page }) => {
  let historyCalls = 0
  let allowRestore = false
  await page.route('**/api/profile/resumes', route => {
    historyCalls += 1
    return fulfillCode(route, historyCalls === 1 ? [{ id: 1, name: '当前画像', major: '计算机' }] : [{ id: 2, name: '历史画像', major: '统计学', create_time: '2026-08-14T09:00:00' }])
  })
  await page.route('**/api/profile/result/2', route => {
    return allowRestore ? fulfillCode(route, { ...profileDetail, id: 2, resume_id: 2, name: '历史画像', major: '统计学' }) : fulfillJson(route, { code: 500, msg: '历史画像暂时不可用' }, 500)
  })
  await page.goto('/profile')
  await page.getByRole('button', { name: '历史画像' }).click()
  await page.getByRole('button', { name: /历史画像 · 统计学/ }).click()
  await expect(page.getByRole('dialog', { name: '历史能力画像' }).getByText('历史画像暂时不可用')).toBeVisible()
  allowRestore = true
  await page.getByRole('button', { name: /历史画像 · 统计学/ }).click()
  await expect(page.getByText('画像 #2', { exact: true }).first()).toBeVisible()
})

test('latest server portrait overrides a stale local cache', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('career_profile_portrait_v1_1', JSON.stringify({ v: 1, id: 1, resume_id: 1, name: '旧缓存姓名', major: '旧专业' })))
  await page.route('**/api/profile/resumes', route => fulfillCode(route, [{ id: 2, name: '服务器最新画像', major: '人工智能', create_time: '2026-08-15T10:00:00' }]))
  await page.route('**/api/profile/result/2', route => fulfillCode(route, { ...profileDetail, id: 2, resume_id: 2, name: '服务器最新画像', major: '人工智能' }))
  await page.goto('/profile')
  await expect(page.getByText('画像 #2')).toBeVisible()
  await expect(page.getByLabel('姓名')).toHaveValue('服务器最新画像')
})

test('profile dimensions include evidence, gaps and actionable next steps', async ({ page }) => {
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: '各维度详细分析' })).toBeVisible()
  await expect(page.getByText('材料与线索', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('个人简历.pdf').first()).toBeVisible()
  for (const label of ['当前判断', '关键缺口', '下一步行动', '应留下的证据', '完成标准']) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
  }
  await expect(page.getByRole('heading', { name: '成长路线图' })).toBeVisible()
  await expect(page.getByText(/3 个近期里程碑/)).toBeVisible()
  await expect(page.getByText(/3 个发展目标/)).toBeVisible()
})

test('account validates limits and visibly marks unsaved changes', async ({ page }) => {
  await page.goto('/account')
  const resultCount = page.getByLabel('结果数量')
  await resultCount.fill('101')
  await expect(page.getByText('有尚未保存的修改')).toBeVisible()
  await expect(page.getByText('请输入 1～100 的整数')).toBeVisible()
  await expect(page.getByRole('button', { name: '保存偏好' })).toBeDisabled()
})

test('account rolls back to the last server state when saving fails', async ({ page }) => {
  await page.route('**/api/account/preferences', route => route.request().method() === 'PATCH'
    ? fulfillJson(route, { ok: false, message: '偏好服务暂时不可用' }, 500)
    : fulfillOk(route, { stored: true, preferences, effective: preferences, limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 } }))
  await page.goto('/account')
  const resultCount = page.getByLabel('结果数量')
  await resultCount.fill('50')
  await page.getByRole('button', { name: '保存偏好' }).click()
  await expect(page.getByText(/偏好服务暂时不可用；修改已回滚/)).toBeVisible()
  await expect(resultCount).toHaveValue('30')
})

test('account submits only the typed preference whitelist', async ({ page }) => {
  let body: Record<string, unknown> = {}
  await page.route('**/api/account/preferences', async route => {
    if (route.request().method() !== 'PATCH') return fulfillOk(route, { stored: true, preferences, effective: preferences, limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 } })
    body = route.request().postDataJSON() as Record<string, unknown>
    return fulfillOk(route, { stored: true, preferences: { ...preferences, match_result_count: 40 }, effective: { ...preferences, match_result_count: 40 }, limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 } })
  })
  await page.goto('/account')
  await page.getByLabel('结果数量').fill('40')
  await page.getByRole('button', { name: '保存偏好' }).click()
  await expect(page.getByText('所有偏好均已保存')).toBeVisible()
  expect(body.match_result_count).toBe(40)
  expect(body).not.toHaveProperty('api_key')
  expect(body).not.toHaveProperty('credential_status')
})

test('profile and account have no horizontal overflow at 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const path of ['/profile', '/account']) {
    await page.goto(path)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})

test('header, history modal and file input support keyboard operation', async ({ page }) => {
  await page.goto('/profile')
  await page.getByLabel('PathFy 首页').focus()
  await expect(page.getByLabel('PathFy 首页')).toBeFocused()
  await page.getByRole('button', { name: '历史画像' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: '历史能力画像' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.locator('#profile-material-input').focus()
  await expect(page.locator('#profile-material-input')).toBeFocused()
})
