import { expect, test, type Page } from '@playwright/test'
import { capabilityScores, fulfillCode, fulfillJson, fulfillOk, installStableApiMocks, seedAuthenticatedSession } from './support/pathfy-fixtures'

const jobs = [
  { id: 'job-1', title: '数据分析师', company: '示例科技', location: '上海', salary: '15-22K', ...capabilityScores },
  { id: 'job-2', title: '商业分析师', company: '未来零售', location: '杭州', salary: '14-20K', ...capabilityScores, cap_req_cross: 90 }
]

const matchResult = {
  student: { scores: capabilityScores },
  filters: { q: '数据', location_q: '上海', match_goal: 'fit' },
  stats: { scanned: 50, returned: 2 },
  jobs: jobs.map((job, index) => ({ ...job, match_preview: { match_score: 88 - index * 6, dimension_gaps: { cap_req_cross: 8 } } })),
  llm: { ok: true, model: 'deepseek-test', top5: [{ job_id: 'job-1', rank: 1, overall_fit_0_100: 94, one_line: '实践与数字能力高度匹配', strengths: ['数字能力'], gaps: ['行业经验'], risks: ['业务表达'], title: '数据分析师', company: '示例科技', location: '上海', salary: '15-22K', scores: capabilityScores }] }
}

const questions = Array.from({ length: 6 }, (_, index) => ({ id: index + 1, question_text: `测试问题 ${index + 1}`, option_a: '偏好 A', option_b: '偏好 B' }))
const personalityResult = {
  mbti_type: 'INTJ',
  dimension_analysis: [{ dimension: '能量来源', type: 'I', description: '偏好独立思考', characteristics: ['专注'], work_preference: ['深度工作'], growth_suggestions: ['主动沟通'] }],
  complete_analysis: { name: '建筑师', summary: '擅长系统思考。', core_strengths: ['战略思维'], career_tendencies: ['复杂问题分析'], workplace_relationships: ['重视专业协作'], development_areas: ['提高表达频率'], stress_response: '先独处梳理，再制定行动计划。' },
  recommended_jobs: ['数据分析师'],
  job_recommendations: { recommended_jobs: ['数据分析师'], career_advice: '优先选择允许深度工作的团队。' }
}

async function seedMatchCache(page: Page, result = matchResult) {
  await page.addInitScript((payload) => {
    localStorage.setItem('career_pj_match_v1_1', JSON.stringify({ v: 1, resumeId: 1, filters: { q: '数据', locationQ: '上海', goal: 'fit', refine: true }, result: payload }))
  }, result)
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
  await page.route('**/api/personality/questions', route => fulfillCode(route, questions))
  await page.route('**/api/jobs/job-*', route => fulfillOk(route, jobs.find(item => route.request().url().endsWith(item.id)) || jobs[0]))
})

test('matching separates intelligent Top 5 from full results and opens unified detail', async ({ page }) => {
  await seedMatchCache(page)
  await page.goto('/match')
  await expect(page.getByRole('heading', { name: '智能推荐 Top 5' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
  await expect(page.getByText('业务表达')).toBeVisible()
  await page.getByRole('button', { name: '岗位详情' }).first().click()
  await expect(page.getByText('八维能力需求')).toBeVisible()
})

test('matching restores filters, strategy and results from history', async ({ page }) => {
  await page.route('**/api/match/history?*', route => fulfillOk(route, { items: [{ run_id: 9, resume_id: 1, student_name: '历史画像', q: '产品', location_q: '北京', match_goal: 'stretch', refine_with_llm: true, returned: 2, created_at: '2026-08-15T09:00:00' }] }))
  await page.route('**/api/match/history/9', route => fulfillOk(route, { ...matchResult, resume_id: 1, filters: { q: '产品', location_q: '北京', match_goal: 'stretch' } }))
  await page.goto('/match')
  await page.getByRole('button', { name: '查看匹配历史' }).click()
  await expect(page.getByText('关键词：产品')).toBeVisible()
  await page.getByRole('button', { name: /历史画像/ }).click()
  await expect(page.getByText('历史匹配条件与结果已完整恢复')).toBeVisible()
  await expect(page.getByPlaceholder('如：数据分析')).toHaveValue('产品')
  await expect(page.getByPlaceholder('如：上海')).toHaveValue('北京')
})

test('matching exposes snapshot persistence failure without losing results', async ({ page }) => {
  await seedMatchCache(page, { ...matchResult, snapshot_warning: 'match_snapshot_persist_failed:test' })
  await page.goto('/match')
  await expect(page.getByText('结果已生成，但快照保存失败')).toBeVisible()
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
})

test('matching keeps a failed request visible and supports an inline retry', async ({ page }) => {
  await seedMatchCache(page)
  let attempts = 0
  await page.route('**/api/match/preview', route => {
    attempts += 1
    return attempts === 1
      ? fulfillJson(route, { ok: false, message: '岗位数据服务暂时不可用，请稍后重试' }, 503)
      : fulfillOk(route, matchResult)
  })
  await page.goto('/match')
  await page.getByRole('button', { name: '开始匹配' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '匹配未完成' })).toContainText('岗位数据服务暂时不可用')
  await page.getByRole('button', { name: '重新匹配' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '匹配未完成' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
  expect(attempts).toBe(2)
})

test('AI refinement does not block coarse results and uses a separate request', async ({ page }) => {
  await seedMatchCache(page)
  const requests: Array<Record<string, unknown>> = []
  await page.route('**/api/match/preview', async route => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    requests.push(body)
    if (!body.refine_with_llm) return fulfillOk(route, { ...matchResult, llm: undefined })
    await new Promise(resolve => setTimeout(resolve, 900))
    return fulfillOk(route, matchResult)
  })

  await page.goto('/match')
  await page.getByRole('button', { name: '开始匹配' }).click()
  await expect(page.getByText('粗排已完成，AI 正在精排')).toBeVisible()
  await expect(page.getByText(/先分析前 20 个候选.*自动缩小到前 10 个候选/)).toBeVisible()
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '智能推荐 Top 5' })).toBeVisible()
  await expect(page.getByText('实践与数字能力高度匹配')).toBeVisible()

  expect(requests).toHaveLength(2)
  expect(requests[0]).toMatchObject({ refine_with_llm: false, persist_snapshot: false })
  expect(requests[1]).toMatchObject({ refine_with_llm: true, persist_snapshot: true })
})

test('AI timeout is reported accurately without hiding coarse results', async ({ page }) => {
  await seedMatchCache(page)
  await page.route('**/api/match/preview', route => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    return fulfillOk(route, body.refine_with_llm
      ? { ...matchResult, llm: { ok: false, error: "deepseek_http_error:APITimeoutError('Request timed out.')", top5: [] } }
      : { ...matchResult, llm: undefined })
  })

  await page.goto('/match')
  await page.getByRole('button', { name: '开始匹配' }).click()
  await expect(page.getByText(/AI 精排响应超过 90 秒/)).toBeVisible()
  await expect(page.getByText(/AI 精排服务连接失败/)).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
})

test('AI timeout falls back to a smaller pool and explains the degraded success', async ({ page }) => {
  await seedMatchCache(page)
  await page.route('**/api/match/preview', route => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    return fulfillOk(route, body.refine_with_llm
      ? {
          ...matchResult,
          llm: {
            ...matchResult.llm,
            retry_attempted: true,
            degraded: true,
            fallback_reason: 'timeout',
            initial_pool_size: 20,
            fallback_pool_size: 10
          }
        }
      : { ...matchResult, llm: undefined })
  })

  await page.goto('/match')
  await page.getByRole('button', { name: '开始匹配' }).click()
  await expect(page.getByText('已通过轻量模式完成精排')).toBeVisible()
  await expect(page.getByText(/候选池从 20 个缩小到 10 个/)).toBeVisible()
  await expect(page.getByRole('heading', { name: '智能推荐 Top 5' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '完整匹配结果' })).toBeVisible()
})

test('jobs assistant replaces results, saves an answer and returns to the normal list', async ({ page }) => {
  await page.route('**/api/jobs?*', route => fulfillOk(route, { jobs: [jobs[1]], total: 1, page: 1, page_size: 20, total_pages: 1 }))
  await page.route('**/api/jobs/assistant/chat', route => fulfillOk(route, { session_id: 3, jobs: [jobs[0]], assistant_message: { id: 31, role: 'assistant', content: '为你筛选了数据岗位。', is_saved: false } }))
  await page.route('**/api/jobs/assistant/messages/31/save', route => fulfillOk(route, {}))
  await page.goto('/jobs')
  await page.getByPlaceholder('输入岗位偏好或问题…').fill('数据岗位')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByText('当前展示 AI 助手筛选结果')).toBeVisible()
  await page.getByRole('button', { name: '保存回答与筛选结果' }).click()
  await expect(page.getByRole('button', { name: '已保存' })).toBeVisible()
  await page.getByRole('button', { name: '返回普通岗位列表' }).click()
  await expect(page.getByRole('heading', { name: '商业分析师' })).toBeVisible()
})

test('jobs list keeps a Neo4j failure visible and reloads successfully', async ({ page }) => {
  let attempts = 0
  let allowSuccess = false
  await page.route('**/api/jobs?*', route => {
    attempts += 1
    return allowSuccess
      ? fulfillOk(route, { jobs: [jobs[0]], total: 1, page: 1, page_size: 20, total_pages: 1 })
      : fulfillJson(route, { ok: false, message: '岗位数据服务暂时不可用，请稍后重试' }, 503)
  })
  await page.goto('/jobs')
  await expect(page.getByRole('alert').filter({ hasText: '岗位列表加载失败' })).toContainText('岗位数据服务暂时不可用')
  allowSuccess = true
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '岗位列表加载失败' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '数据分析师' })).toBeVisible()
  expect(attempts).toBeGreaterThanOrEqual(2)
})

test('jobs assistant can retry a failed question', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/jobs/assistant/chat', route => {
    attempts += 1
    return attempts === 1 ? fulfillJson(route, { ok: false, message: '助手暂时不可用' }, 500) : fulfillOk(route, { session_id: 4, jobs: [], assistant_message: { id: 41, role: 'assistant', content: '重试成功' } })
  })
  await page.goto('/jobs')
  await page.getByPlaceholder('输入岗位偏好或问题…').fill('帮我筛选')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByRole('button', { name: '重试上一条问题' })).toBeVisible()
  await page.getByRole('button', { name: '重试上一条问题' }).click()
  await expect(page.getByText('重试成功')).toBeVisible()
})

test('personality restores an in-progress test for the same question set', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('career_personality_v1_1', JSON.stringify({ v: 1, answers: { 1: 'A' }, started: true, currentQuestionIndex: 1, questionSignature: '1:2:3:4:5:6' })))
  await page.goto('/personality')
  await expect(page.getByText('第 2 题')).toBeVisible()
  await expect(page.getByText('1/6')).toBeVisible()
  await page.reload()
  await expect(page.getByText('第 2 题')).toBeVisible()
})

test('personality resets stale answers when the question set changes', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('career_personality_v1_1', JSON.stringify({ v: 1, answers: { 1: 'A' }, started: true, currentQuestionIndex: 1, questionSignature: '1:2:99' })))
  await page.goto('/personality')
  await expect(page.getByRole('button', { name: '开始测试' })).toBeVisible()
  const cache = await page.evaluate(() => JSON.parse(localStorage.getItem('career_personality_v1_1') || '{}'))
  expect(cache.data?.answers || cache.answers).toEqual({})
})

test('personality result restores all detailed categories without empty placeholders', async ({ page }) => {
  await page.addInitScript((result) => localStorage.setItem('career_personality_v1_1', JSON.stringify({ v: 1, answers: {}, result, started: true, currentQuestionIndex: 0 })), personalityResult)
  await page.goto('/personality')
  for (const heading of ['四维偏好解析', '核心优势', '职业倾向', '职场关系', '成长建议', '压力应对', '岗位探索线索与职业建议']) await expect(page.getByRole('heading', { name: heading })).toBeVisible()
})

test('personality recommendation opens the real job library with its search query', async ({ page }) => {
  await page.addInitScript((result) => localStorage.setItem('career_personality_v1_1', JSON.stringify({ v: 1, answers: {}, result, started: true, currentQuestionIndex: 0 })), { ...personalityResult, profile_id: 9 })
  await page.goto('/personality')
  await page.getByRole('link', { name: '带着偏好探索岗位' }).click()

  await expect(page).toHaveURL(/\/jobs\?.*q=/)
  await expect(page.getByPlaceholder('岗位、公司或地点')).toHaveValue('数据分析师')
  await expect(page.getByText('已带入人格测评的岗位探索线索')).toBeVisible()
})

test('profile presents capability and work preference as separate portrait layers', async ({ page }) => {
  await page.route('**/api/personality/me/latest', route => fulfillCode(route, {
    ...personalityResult,
    profile_id: 9,
    status: 'measured',
    personalization_enabled: true,
    completed_at: '2026-08-19T10:00:00',
    preference_axes: [
      { code: 'interaction_intensity', value: 30, low_label: '独立恢复', high_label: '互动恢复' },
      { code: 'abstraction_preference', value: 75, low_label: '具体事实', high_label: '模式可能' },
      { code: 'analytical_decision', value: 70, low_label: '关系价值', high_label: '规则分析' },
      { code: 'structure_preference', value: 65, low_label: '灵活开放', high_label: '计划确定' }
    ]
  }))

  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: '个人职业画像' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '工作偏好画像' })).toBeVisible()
  await expect(page.getByText('INTJ · 连续测量')).toBeVisible()
  await expect(page.getByText(/不修改任何能力分数/)).toBeVisible()
})

test('match explanation is visible while capability ranking remains primary', async ({ page }) => {
  const explained = {
    ...matchResult,
    preference_context: { mode: 'explain', status: 'measured', personality_profile_id: 9, mbti_type: 'INTJ', influenced_ranking: false },
    jobs: matchResult.jobs.map(job => ({
      ...job,
      match_preview: { ...job.match_preview, preference_fit: { status: 'insufficient_job_evidence', influenced_ranking: false, axes: [] } }
    }))
  }
  await seedMatchCache(page, explained)
  await page.goto('/match')

  await expect(page.getByText('INTJ 工作偏好已附加到本次匹配')).toBeVisible()
  await expect(page.getByText(/岗位工作环境证据待补充/).first()).toBeVisible()
  await expect(page.getByText(/粗排只看八维能力/)).toBeVisible()
})

test('available workstyle fit exposes a score and its source evidence without changing rank language', async ({ page }) => {
  const preferenceFit = {
    status: 'available', score: 91.2, confidence: 0.8, confidence_level: 'high', influenced_ranking: false,
    axes: [{ code: 'interaction_intensity', user_value: 70, job_value: 75, preference_strength: 0.4, fit: 98, confidence: 0.8, explanation: '岗位偏高频互动，与当前偏好方向一致。', evidence: [{ text: '需要持续参与客户访谈和跨团队评审' }] }]
  }
  await seedMatchCache(page, {
    ...matchResult,
    preference_context: { mode: 'explain', status: 'measured', mbti_type: 'INTJ', influenced_ranking: false, jobs_with_preference_fit: 2 },
    jobs: matchResult.jobs.map(job => ({ ...job, match_preview: { ...job.match_preview, preference_fit: preferenceFit } }))
  })
  await page.goto('/match')
  await expect(page.getByText('适配 91 · 证据较充分').first()).toBeVisible()
  await expect(page.getByText(/本次有 2 个岗位达到解释门槛/)).toBeVisible()
  await page.getByText('查看逐轴证据').first().click()
  await expect(page.getByText(/客户访谈和跨团队评审/).first()).toBeVisible()
})

test('job detail distinguishes work environment from capability requirements', async ({ page }) => {
  await page.route('**/api/jobs/job-1', route => fulfillOk(route, {
    ...jobs[0],
    workstyle: {
      status: 'available', axis_count: 2, evidenced_axis_count: 2, inherited_from_job_title: true,
      axes: [{ code: 'structure_preference', value: 78, confidence: 0.82, low_label: '灵活探索', high_label: '计划确定', inherited_from_job_title: true, evidence: [{ text: '岗位族流程包含固定月度里程碑' }] }]
    }
  }))
  await seedMatchCache(page)
  await page.goto('/match')
  await page.getByRole('button', { name: '岗位详情' }).first().click()
  await expect(page.getByText('岗位工作环境画像')).toBeVisible()
  await expect(page.getByText('含岗位族继承数据')).toBeVisible()
  await expect(page.getByText(/固定月度里程碑/)).toBeVisible()
})

test('job detail stops loading after a graph failure and can retry in place', async ({ page }) => {
  let attempts = 0
  await page.unroute('**/api/jobs/job-*')
  await page.route('**/api/jobs/job-1', route => {
    attempts += 1
    return attempts === 1
      ? fulfillJson(route, { ok: false, message: '岗位详情数据服务响应超时，请稍后重试' }, 503)
      : fulfillOk(route, jobs[0])
  })
  await seedMatchCache(page)
  await page.goto('/match')
  await page.getByRole('button', { name: '岗位详情' }).first().click()
  await expect(page.getByText('岗位详情暂时无法加载')).toBeVisible()
  await expect(page.getByText(/响应超时/)).toBeVisible()
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByRole('dialog').getByText('示例科技', { exact: true })).toBeVisible()
  await expect.poll(() => attempts).toBe(2)
})
