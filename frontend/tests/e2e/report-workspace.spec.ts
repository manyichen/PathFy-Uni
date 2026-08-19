import { expect, test, type Page } from '@playwright/test'
import type { CareerReport, ReportPlan, ReportTarget, ReportTargetDecision } from '../../app/types/api'
import { fulfillJson, fulfillOk, installStableApiMocks, reportWorkspace, seedAuthenticatedSession } from './support/pathfy-fixtures'

const secondTarget: ReportTarget = {
  id: 'job-2', job_id: 'job-2', title: '商业分析师', display_title: '商业分析师', company: '未来零售', location: '杭州',
  match_preview: { match_score: 82, dimension_gaps: { cap_req_cross: 12, cap_req_social: 15 } },
  track_profile: { job_title: '商业分析师', hiring_visibility_0_100: 78, path_breadth_0_100: 88, resource_density_0_100: 72 }
}

function evidenceDecision(jobId: string, title: string, dimension: string, label: string): ReportTargetDecision {
  const claimId = `claim:${jobId}:risk:${dimension}`
  const factId = `profile:${dimension}`
  const requirementId = `job:${jobId}:${dimension}`
  const claims: ReportTargetDecision['claims'] = [{
    id: claimId, kind: 'risk', dimension, title: `${label}低于岗位标尺，仍需成果验证`, summary: '当前画像低于岗位标尺，但仍处于软容差范围。', impact: '通过项目和复盘反馈验证真实胜任度。', fact_refs: [factId, requirementId],
    facts: [
      { id: factId, label: '当前能力', value: 70, unit: '分', source_type: 'system_calculated', source_label: '系统计算', evidence_grade: 'B', observed_at: '2026-08-19 10:00:00', verified: true },
      { id: requirementId, label: '岗位要求', value: 78, unit: '分', source_type: 'system_calculated', source_label: '岗位快照', evidence_grade: 'B', observed_at: '2026-08-19 10:00:00', verified: true }
    ],
    priority: 8, quality: { grounded: true, evidence_grade: 'B', source_type: 'system_calculated', freshness: '2026-08-19 10:00:00' }
  }]
  const actions: ReportTargetDecision['actions'] = [{ id: `action:${jobId}:1`, job_id: jobId, item_index: 0, action_index: 0, title: `完成${label}验证项目`, kind: 'deliverable', focus_dimension: dimension, focus_label: label, deliverable: '项目链接与复盘记录', deadline: '第 4 周末', effort_hours: 4, acceptance_criteria: ['链接可访问'], evidence_required: true, evidence_grade_required: 'B', status: 'todo', source_claim_ids: [claimId], source_fact_refs: [factId] }]
  if (jobId === 'job-1') {
    for (const [index, item] of [
      ['cap_req_theory', '专业理论', 75, 32, '整理 Java 核心原理案例'],
      ['cap_req_growth', '学习成长', 80, 50, '建立双周学习复盘节奏']
    ].entries()) {
      const [strengthDimension, strengthLabel, current, required, actionTitle] = item as [string, string, number, number, string]
      const strengthClaimId = `claim:${jobId}:strength:${strengthDimension}`
      const currentId = `profile:${strengthDimension}`; const requiredId = `job:${jobId}:${strengthDimension}`
      claims.push({ id: strengthClaimId, kind: 'strength', dimension: strengthDimension, title: `${strengthLabel}是当前相对优势`, summary: `当前 ${current} 分，岗位要求 ${required} 分。`, impact: `把${strengthLabel}转化为可查看成果。`, fact_refs: [currentId, requiredId], facts: [
        { id: currentId, label: '当前能力', value: current, unit: '分', source_type: 'system_calculated', source_label: '系统计算', evidence_grade: 'B', verified: true },
        { id: requiredId, label: '岗位要求', value: required, unit: '分', source_type: 'system_calculated', source_label: '岗位快照', evidence_grade: 'B', verified: true }
      ], priority: current - required, quality: { grounded: true, evidence_grade: 'B', source_type: 'system_calculated' } })
      actions.push({ id: `action:${jobId}:${index + 2}`, job_id: jobId, item_index: index + 1, action_index: 0, title: actionTitle, kind: 'deliverable', focus_dimension: strengthDimension, focus_label: strengthLabel, deliverable: `${strengthLabel}成果说明`, deadline: `第 ${index + 2} 周末`, effort_hours: 3, acceptance_criteria: ['产物可查看'], evidence_required: true, evidence_grade_required: 'B', status: 'todo', source_claim_ids: [strengthClaimId], source_fact_refs: [currentId, requiredId] })
    }
  }
  return {
    job_id: jobId, display_title: title, role: jobId === 'job-1' ? 'primary' : 'alternative', role_label: jobId === 'job-1' ? '主目标' : '备选目标',
    judgement: { recommendation: jobId === 'job-1' ? '优先推进' : '保留备选', match_score: jobId === 'job-1' ? 78 : 82, reasons: [], risks: [`${label}仍需验证`], data_gaps: [] },
    claims,
    actions,
    primary_action_id: `action:${jobId}:1`, evidence_metrics: { coverage: 1, claim_grounding: 1, action_traceability: 1, fact_verification: 1, claim_count: claims.length, fact_count: claims.length * 2, action_count: actions.length, unlinked_action_count: 0 },
    freshness: { profile: { as_of: '2026-08-19 10:00:00', source_label: '画像快照', evidence_grade: 'B' } }
  }
}

function richReport(): CareerReport {
  const report = structuredClone(reportWorkspace.reportSnapshot) as CareerReport
  const firstTarget = report.targets?.[0]
  const firstPlan = report.plans_by_target?.[0]
  if (!firstTarget || !firstPlan) throw new Error('report fixture is incomplete')
  firstPlan.line_id = 'data-line'
  firstPlan.next_month_plan = {
    ...firstPlan.next_month_plan,
    replan_mode: 'strong', review_anchor_month: 1,
    items: [{ focus_dimension: 'cap_req_practice', focus_label: '实践技能', milestone: '完成端到端分析作品', custom_actions: [{ text: '每周日提交一次进展复盘', kind: 'evidence', done: false }] }]
  }
  const secondPlan: ReportPlan = {
    job_id: 'job-2', line_id: 'business-line', display_title: '商业分析师', match_score: 82,
    next_month_plan: { plan_month: 3, phase_label: '业务强化', replan_mode: 'light', items: [{ focus_label: '商业表达', milestone: '完成一次业务复盘', custom_actions: [{ text: '输出一页业务结论', kind: 'project', done: false }] }] },
    phases: { early: { label: '前期', period: '1-3 个月', items: [{ focus_label: '商业表达', milestone: '形成业务分析框架' }] } }
  }
  report.targets = [firstTarget, secondTarget]
  report.plans_by_target = [firstPlan, secondPlan]
  report.development_lines = {
    axis: { x_min: 0, x_max: 12, y_min: 0, y_max: 100 },
    lines: [
      { line_id: 'data-line', line_name: '数据分析师成长线', target_job_id: 'job-1', timeline: [
        { month: 0, progress: 0, label: '起点', kind: 'origin' },
        { month: 1, progress: 38, label: '第1月', kind: 'review', review_id: 11, detail: { review_text: '完成了 SQL 专题与第一版看板。', submitted: { portfolio: 1 }, llm_summary: '实践有进展，但表达指标仍需加强。', pass_rate: 0.5 } }
      ] },
      { line_id: 'business-line', line_name: '商业分析师成长线', target_job_id: 'job-2', timeline: [
        { month: 0, progress: 0, label: '起点', kind: 'origin' },
        { month: 2, progress: 46, label: '第2月', kind: 'review', review_id: 12, detail: { review_text: '完成了业务拆解演练。', submitted: { interview: 2 }, pass_rate: 0.8 } }
      ] }
    ],
    adjustments: [
      { id: 'adj-1', line_id: 'data-line', target_job_id: 'job-1', anchor_review_month: 1, plan_month: 2, label: '强化项目表达与作品证据', kind: 'replan', replan_mode: 'strong', execution_hints: ['先完成作品集说明页'], plan_items: firstPlan.next_month_plan?.items, failed_rows: [{ code: 'interview', label: '项目表达', actual_value: 1, target_raw: 2 }] },
      { id: 'adj-2', line_id: 'business-line', target_job_id: 'job-2', anchor_review_month: 2, plan_month: 3, label: '加强商业表达', kind: 'replan', replan_mode: 'light', execution_hints: ['输出一页业务结论'], plan_items: secondPlan.next_month_plan?.items }
    ]
  }
  report.evaluation = {
    ...report.evaluation,
    last_replan_mode: 'strong', consecutive_fail_months: 2, latest_adjustment_actions: ['先完成作品集说明页'],
    latest_review: { review_id: 11, review_text: '完成了 SQL 专题与第一版看板。', evaluation: { pass_rate: .5, all_passed: false }, adjustment: { all_passed: false, failed_codes: ['interview'], replan_mode: 'strong', auto_adjustment: { triggered: true, reason: '项目表达未达标' } } }
  }
  report.longitudinal_insights = {
    schema_version: 1, generated_at: '2026-08-19T00:00:00Z',
    freshness: { overall_status: 'aging', stale_domains: ['profile'], aging_domains: ['resources'], domains: {
      profile: { status: 'outdated', as_of: '2026-08-18T00:00:00Z', age_days: 1, source_label: '当前能力画像', reason: '源数据在报告快照之后发生变化', refresh_action: '重新分析简历并刷新报告' },
      review: { status: 'fresh', as_of: '2026-08-18T00:00:00Z', age_days: 1, source_label: '最近确认复盘', reason: '仍在当前口径的有效期内', refresh_action: '完成周复盘或月复盘' }
    } },
    execution_profile: { diagnosis: 'time_capacity', diagnosis_label: '可用时间不足或任务过载', confidence: 'medium', evidence_points: 6, confirmed_review_count: 2, action_event_count: 4, current_action_count: 3, current_done_count: 1, current_completion_rate: .333, review_status_distribution: { overloaded: 1 } },
    trends: { review_series: [], review_status_distribution: { overloaded: 1 }, goal_change_count: 0, proposal_count: 2, decided_proposal_count: 2, proposal_acceptance_rate: .5, partial_accept_count: 1, average_accepted_changes: 1.5, plan_stability: .7 },
    personalization: { enabled: true, experiment: { key: 'career_pacing_v1', variant: 'personalized_v1' }, recommendation_active: true, suggested_weekly_action_limit: 2, suggested_weekly_hours: 5, focus: '缩小任务颗粒度，优先完成一个可验收产物', confidence: 'medium', learned_from: { confirmed_reviews: 2, action_events: 4, decided_proposals: 2, excluded: ['未确认候选指标'] }, explanation: '只使用确认历史' },
    reminders: [{ kind: 'review_due', severity: 'info', label: '建议完成一次周复盘，确认当前执行状态', due_at: null, days: null }],
    privacy: { learning_boundary: '仅使用已确认复盘、行动事件和计划决定', unconfirmed_draft_retention_days: 90, confirmed_history_retention: '保留至用户删除报告', exportable: true, deletable: true }
  }
  const decisions = [
    evidenceDecision('job-1', '数据分析师', 'cap_req_practice', '实践技能'),
    evidenceDecision('job-2', '商业分析师', 'cap_req_cross', '交叉能力')
  ]
  report.decision_support = {
    schema_version: 2, generated_at: '2026-08-19 10:00:00', fact_model: 'fact-claim-impact-action-deliverable-metric', target_decisions: decisions,
    target_comparison: decisions.map(item => ({ job_id: item.job_id, display_title: item.display_title, role: item.role, role_label: item.role_label, match_score: item.judgement.match_score, top_gap: item.claims[0]!.title, primary_action: item.actions[0]!.title, evidence_coverage: item.evidence_metrics!.coverage })),
    shared_actions: [], evidence_legend: [{ grade: 'B', label: '系统记录', objective: true }]
  }
  report.preference_strategy = {
    status: 'suggested', version: 'preference-v1', mbti_type: 'INTJ', influences_capability: false,
    disclaimer: '执行偏好只用于安排方式，不等同于能力评价。',
    sections: [{ code: 'collaboration', title: '协作方式', recommendation: '先书面同步，再集中讨论', alternative: '短会确认', rationale: '偏好结构化表达', source: { axis_code: 'IE', value: 62, preference_strength: .62 } }]
  }
  return report
}

async function seedRichReport(page: Page, activeJobId = 'job-1', selectedMonth = 1, reportOverride?: CareerReport) {
  const report = reportOverride || richReport()
  await page.addInitScript(({ workspace, snapshot, active, month }) => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify({ ...workspace, reportSnapshot: snapshot, activeJobId: active, selectedCanvasMonth: month }))
  }, { workspace: reportWorkspace, snapshot: report, active: activeJobId, month: selectedMonth })
  await page.route('**/api/report/42', route => fulfillOk(route, { report_id: 42, resume_id: 1, primary_job_id: 'job-1', target_job_ids: ['job-1', 'job-2'], report, llm_enrich_pending: false }))
}

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
})

test('action and review workspaces expose generative visual landmarks', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await expect(page.getByText('GENERATIVE TRACE / 本月行动纹样')).toBeVisible()
  await expect(page.getByText('行动纹样', { exact: true })).toBeVisible()
  await expect(page.getByText('LONGITUDINAL SIGNAL / 长期校准')).toBeVisible()
  await page.getByRole('tab', { name: /复盘/ }).click()
  await expect(page.getByText('PLAN SIGNAL / 计划转向信号')).toBeVisible()
  await expect(page.getByText('EVALUATION CONSTELLATION')).toBeVisible()
  await expect(page.getByText('事实回声')).toBeVisible()
  await expect(page.getByText('01 / RAW NOTE')).toBeVisible()
})

test('opens reactive preference suggestions and discards cancelled edits safely', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  const strategy = page.locator('.strategy-card')
  await expect(strategy.getByRole('heading', { name: '按你更自然的方式，把同一目标做出来' })).toBeVisible()
  await strategy.getByRole('button', { name: '编辑', exact: true }).click()
  await strategy.locator('textarea').first().fill('临时修改但不保存')
  await strategy.getByRole('button', { name: '取消', exact: true }).click()
  await expect(strategy.getByText('先书面同步，再集中讨论', { exact: true })).toBeVisible()
  await expect(strategy.getByText('临时修改但不保存', { exact: true })).toBeHidden()
})

test('keeps five long report targets and header actions inside the desktop viewport', async ({ page }) => {
  const report = richReport()
  const baseTarget = report.targets![0]!
  const basePlan = report.plans_by_target![0]!
  report.targets = [
    baseTarget,
    ...[
      ['job-2', '测试工程师 · 肩石磁能科技有限责任公司'],
      ['job-3', '软件测试 · 中教智网（北京）信息技术有限公司'],
      ['job-4', '硬件测试 · 无锡芯领域微电子有限公司'],
      ['job-5', '软件测试 · 无锡市软测认证有限公司南京分公司']
    ].map(([jobId, displayTitle]) => ({ ...baseTarget, id: jobId, job_id: jobId, title: displayTitle, display_title: displayTitle }))
  ]
  report.plans_by_target = report.targets.map(target => ({ ...basePlan, job_id: String(target.job_id), display_title: target.display_title }))
  await page.setViewportSize({ width: 1280, height: 900 })
  await seedRichReport(page, 'job-1', 1, report)
  await page.goto('/report')
  await expect(page.getByRole('button', { name: '编辑并导出 PDF' })).toBeVisible()
  await expect(page.getByRole('tab', { name: /无锡市软测认证/ })).toBeVisible()

  const widths = await page.evaluate(() => {
    const toolbar = document.querySelector<HTMLElement>('.report-header-toolbar')!
    const targets = document.querySelector<HTMLElement>('.target-tabs')!
    return {
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      toolbarOverflow: toolbar.scrollWidth - toolbar.clientWidth,
      toolbarRight: toolbar.getBoundingClientRect().right - window.innerWidth,
      targetsOverflow: targets.scrollWidth - targets.clientWidth
    }
  })
  expect(widths.documentOverflow).toBeLessThanOrEqual(1)
  expect(widths.toolbarOverflow).toBeLessThanOrEqual(1)
  expect(widths.toolbarRight).toBeLessThanOrEqual(1)
  expect(widths.targetsOverflow).toBeLessThanOrEqual(1)
})

test('restores the active target and selected month after refresh', async ({ page }) => {
  await seedRichReport(page, 'job-2', 2)
  await page.goto('/report')
  await expect(page.getByRole('tab', { name: /商业分析师/ })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: /路线/ }).click()
  await expect(page.getByRole('heading', { name: '第 2 月详情' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('tab', { name: /商业分析师/ })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: /路线/ }).click()
  await expect(page.getByRole('heading', { name: '第 2 月详情' })).toBeVisible()
})

test('switches target-specific plan, gap and track profile together', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await page.getByRole('tab', { name: /商业分析师/ }).click()
  await expect(page.getByText('输出一页业务结论').first()).toBeVisible()
  await page.getByRole('tab', { name: /依据/ }).click()
  await expect(page.getByText('路径宽度')).toBeVisible()
  await page.getByRole('tab', { name: /路线/ }).click()
  await expect(page.getByText('商业表达').first()).toBeVisible()
})

test('shows a quantitative evidence board and routes outcome collection to review', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await page.getByRole('tab', { name: /依据/ }).click()
  await expect(page.getByRole('heading', { name: /能力差值如何变成行动.*又如何留下真实成果/ })).toBeVisible()
  await expect(page.getByText('链路已连通 · 成果待补')).toBeVisible()
  await expect(page.getByText(/B 级系统依据/).first()).toBeVisible()
  await page.locator('[data-p5-scene-status]').scrollIntoViewIfNeeded()
  await expect(page.locator('[data-p5-scene-status="ready"]')).toBeVisible()
  await expect(page.getByRole('heading', { name: '能力差距与岗位要求' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '资源与成果入口' })).toBeVisible()
  await page.getByRole('button', { name: '去复盘补成果' }).click()
  await expect(page.getByRole('tab', { name: /复盘/ })).toHaveAttribute('aria-selected', 'true')
})

test('shows evidence-bounded longitudinal pacing and freshness', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await expect(page.getByRole('heading', { name: '长期校准' })).toBeVisible()
  await expect(page.getByText('可用时间不足或任务过载')).toBeVisible()
  await expect(page.getByText('每周最多 2 项 · 约 5 小时')).toBeVisible()
  await expect(page.getByText('源数据已变化')).toBeVisible()
})

test('opens a reviewed month with original text and metrics', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await page.getByRole('tab', { name: /路线/ }).click()
  await page.locator('.trajectory-events button[data-kind="review"]').click()
  await expect(page.getByText('完成了 SQL 专题与第一版看板。')).toBeVisible()
  await expect(page.getByText(/portfolio：1/)).toBeVisible()
})

test('explains automatic replan mode, trigger and next action', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await page.getByRole('tab', { name: /复盘/ }).click()
  await expect(page.getByText('强化调整')).toBeVisible()
  await expect(page.getByText('已触发')).toBeVisible()
  await expect(page.getByText('先完成作品集说明页').first()).toBeVisible()
})

test('loads public information only for the active target', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/track-public-info', route => fulfillOk(route, { summary: '近三个月数据分析岗位需求保持活跃。', sources: [{ title: '招聘趋势', url: 'https://example.com/trend' }] }))
  await page.goto('/report')
  await page.getByRole('tab', { name: /依据/ }).click()
  await page.getByRole('button', { name: '公开信息' }).click()
  await expect(page.getByText('近三个月数据分析岗位需求保持活跃。')).toBeVisible()
  await expect(page.getByRole('link', { name: '招聘趋势' })).toBeVisible()
})

test('refreshes only the selected report partition', async ({ page }) => {
  await seedRichReport(page)
  let requestedScope = ''
  await page.route('**/api/report/42/enrichment', async route => {
    if (route.request().method() === 'POST') {
      requestedScope = String((await route.request().postDataJSON()).scope || '')
      return fulfillOk(route, { report_id: 42, status: 'queued', attempt: 2, scope: requestedScope }, 202)
    }
    return fulfillOk(route, { report_id: 42, status: 'completed', attempt: 2, scope: requestedScope, progress: 100 })
  })
  await page.goto('/report')
  await page.getByRole('tab', { name: /依据/ }).click()
  await page.getByRole('button', { name: '仅刷新资源' }).click()
  await expect.poll(() => requestedScope).toBe('resources')
})

test('public information failure does not block the report', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/track-public-info', route => fulfillJson(route, { ok: false, code: 503, message: '公开信息服务不可用' }, 503))
  await page.goto('/report')
  await page.getByRole('tab', { name: /依据/ }).click()
  await page.getByRole('button', { name: '公开信息' }).click()
  await expect(page.getByText('当前岗位公开信息加载失败')).toBeVisible()
  await expect(page.getByRole('heading', { name: '能力差距' })).toBeVisible()
})

test('persists an optimistic action check', async ({ page }) => {
  await seedRichReport(page)
  let savedDone = false
  await page.route('**/api/report/42/plan-actions/done', async route => { savedDone = Boolean((await route.request().postDataJSON()).done); return fulfillOk(route, { saved: true }) })
  await page.goto('/report')
  const action = page.getByRole('checkbox', { name: '每周日提交一次进展复盘' }).first()
  await action.click()
  await expect(action).toBeChecked()
  await expect.poll(() => savedDone).toBe(true)
})

test('rolls an optimistic action back when saving fails', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/42/plan-actions/done', route => fulfillJson(route, { ok: false, code: 500, message: '行动保存失败' }, 500))
  await page.goto('/report')
  const action = page.getByRole('checkbox', { name: '每周日提交一次进展复盘' }).first()
  await action.click()
  await expect(action).not.toBeChecked()
  await expect(page.getByText('行动保存失败').first()).toBeVisible()
})

test('retries history loading inside the modal', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/report/my/list**', route => ++attempts <= 2 ? fulfillJson(route, { ok: false, code: 500, message: '历史服务忙' }, 500) : fulfillOk(route, { items: [{ report_id: 42, title: '数据方向报告' }] }))
  await page.goto('/report')
  await page.getByRole('button', { name: '历史报告' }).click()
  await expect(page.getByText('历史报告加载失败')).toBeVisible()
  await page.getByRole('button', { name: '重试' }).click()
  await expect(page.getByText('数据方向报告')).toBeVisible()
})

test('keeps the report skeleton when AI enrich fails', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/42/enrichment', route => route.request().method() === 'POST'
    ? fulfillOk(route, { report_id: 42, status: 'queued', attempt: 1 }, 202)
    : fulfillOk(route, { report_id: 42, status: 'failed', attempt: 1, error: 'AI 增强服务忙' }))
  await page.goto('/report')
  await page.getByRole('button', { name: 'AI 增强' }).click()
  await expect(page.getByText('报告骨架已保留')).toBeVisible()
  await expect(page.getByRole('button', { name: '重试 AI 增强' })).toBeVisible()
  await expect(page.getByRole('tab', { name: /数据分析师/ })).toBeVisible()
})

test('shows a retry state after PDF export fails', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/42/export/pdf', route => fulfillJson(route, { ok: false, code: 500, message: 'PDF 生成失败' }, 500))
  await page.goto('/report')
  await page.getByRole('button', { name: '编辑并导出 PDF' }).click()
  await expect(page.getByRole('heading', { name: '编辑并导出 PDF' })).toBeVisible()
  await page.getByRole('button', { name: '生成并下载 PDF' }).click()
  const dialog = page.getByRole('dialog', { name: '编辑并导出 PDF' })
  await expect(dialog.getByText('PDF 导出失败')).toBeVisible()
  await expect(dialog.getByText(/PDF 生成失败/)).toBeVisible()
  await expect(dialog.getByText('已保留当前编辑内容，可直接重试。')).toBeVisible()
  await expect(dialog.getByRole('button', { name: '生成并下载 PDF' })).toBeEnabled()
})

test('edits a temporary PDF copy and submits structured export options', async ({ page }) => {
  await seedRichReport(page)
  let exportBody: Record<string, unknown> = {}
  await page.route('**/api/report/42/export/pdf', async route => {
    exportBody = await route.request().postDataJSON()
    await route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n% test' })
  })
  await page.goto('/report')
  await page.getByRole('button', { name: '编辑并导出 PDF' }).click()
  await page.getByLabel('PDF 标题').fill('我的求职行动档案')
  await page.getByLabel('判断依据').uncheck()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '生成并下载 PDF' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('career_report_42.pdf')
  expect(exportBody.document_title).toBe('我的求职行动档案')
  expect(exportBody.selected_target_job_ids).toEqual(['job-1', 'job-2'])
  expect((exportBody.sections as Record<string, boolean>).evidence).toBe(false)
  await expect(page.getByRole('heading', { name: '编辑并导出 PDF' })).toBeHidden()
})

test('exports the complete personal report data bundle', async ({ page }) => {
  await seedRichReport(page)
  await page.route('**/api/report/42/export/data', route => fulfillOk(route, {
    report: { id: 42 }, reviews: [{ id: 11 }], review_drafts: [], plan_versions: [],
    evidence_records: [], action_events: [], experiment_assignments: [], exported_at: '2026-08-19T00:00:00Z'
  }))
  await page.goto('/report')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出我的数据' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('career_report_42_data.json')
  await expect(page.getByText('报告数据已导出', { exact: true })).toBeVisible()
})

test('requires the exact report id before permanent deletion', async ({ page }) => {
  await seedRichReport(page)
  let confirmedReportId = 0
  await page.route('**/api/report/42', async route => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    confirmedReportId = Number((await route.request().postDataJSON()).confirm_report_id || 0)
    return fulfillOk(route, { report_id: 42, deleted: true, recoverable: false })
  })
  await page.goto('/report')
  await page.getByRole('button', { name: '永久删除报告' }).click()
  await expect(page.getByRole('heading', { name: '永久删除生涯报告' })).toBeVisible()
  const confirmButton = page.getByRole('button', { name: '永久删除', exact: true })
  await expect(confirmButton).toBeDisabled()
  await page.getByPlaceholder('42').fill('41')
  await expect(confirmButton).toBeDisabled()
  await page.getByPlaceholder('42').fill('42')
  await expect(confirmButton).toBeEnabled()
  await confirmButton.click()
  await expect.poll(() => confirmedReportId).toBe(42)
  await expect(page.getByText('尚未生成生涯报告')).toBeVisible()
  await expect(page.getByText('报告及关联数据已永久删除', { exact: true })).toBeVisible()
})

test('requires confirmation before resetting the workspace', async ({ page }) => {
  await seedRichReport(page)
  await page.goto('/report')
  await page.getByRole('button', { name: '清空工作区' }).click()
  await expect(page.getByRole('heading', { name: '清空报告工作区' })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  await expect(page.getByRole('tab', { name: /数据分析师/ })).toBeVisible()
  await page.getByRole('button', { name: '清空工作区' }).click()
  await page.getByRole('button', { name: '确认清空' }).click()
  await expect(page.getByText('尚未生成生涯报告')).toBeVisible()
})

test('generates a report from the preserved target configuration', async ({ page }) => {
  const report = richReport()
  report.llm_enrich_pending = true
  let enrichmentCompleted = false
  await page.addInitScript(({ workspace, target }) => {
    localStorage.setItem('career_report_workspace_v1_1', JSON.stringify({ ...workspace, reportId: undefined, reportSnapshot: undefined, targets: [target], selectedTargets: [target] }))
  }, { workspace: reportWorkspace, target: report.targets?.[0] })
  await page.route('**/api/report/generate', route => fulfillOk(route, { report_id: 77, primary_job_id: 'job-1', target_job_ids: ['job-1'], report, llm_enrich_pending: true }))
  await page.route('**/api/report/77/enrichment', route => route.request().method() === 'POST'
    ? fulfillOk(route, { report_id: 77, status: 'queued', attempt: 1 }, 202)
    : fulfillOk(route, { report_id: 77, status: enrichmentCompleted ? 'completed' : 'running', attempt: 1 }))
  await page.route('**/api/report/77', route => fulfillOk(route, { report_id: 77, primary_job_id: 'job-1', target_job_ids: ['job-1'], report: { ...report, llm_enrich_pending: false }, llm_enrich_pending: false }))
  await page.goto('/report')
  await page.getByRole('button', { name: '生成 / 重新生成报告' }).click()
  await expect(page.getByText('编号 77，按月持续校准')).toBeVisible()
  await expect(page.getByRole('tab', { name: /数据分析师/ })).toBeVisible()
  await expect(page.getByText('AI 增强正在后台执行')).toBeVisible()
  await expect(page.getByRole('button', { name: 'AI 增强中…' })).toBeVisible()
  enrichmentCompleted = true
  await expect(page.getByRole('button', { name: 'AI 增强', exact: true })).toBeVisible({ timeout: 5_000 })
})

test('confirms review facts before accepting a plan proposal', async ({ page }) => {
  await seedRichReport(page)
  let submittedText = ''
  let confirmedValue = 0
  let proposalDecision = ''
  await page.route('**/api/report/review-drafts', async route => {
    submittedText = String((await route.request().postDataJSON()).review_text || '')
    return fulfillOk(route, {
      draft_id: 9, report_id: 42, status: 'draft', review_cycle: 'monthly', scope: 'target', job_id: 'job-1',
      review_text: submittedText, requires_confirmation: true,
      candidates: [{ code: 'delivery_output', label: '成果数量', target: '>= 2', value: 2, source_text: '进行了两次项目讲解', source_type: 'review_text', origin: 'deepseek', confidence: .82, decision: 'pending' }]
    })
  })
  await page.route('**/api/report/review-drafts/9/confirm', async route => {
    confirmedValue = Number((await route.request().postDataJSON()).candidates?.[0]?.value || 0)
    return fulfillOk(route, {
      draft_id: 9, review_id: 13, report_id: 42, review_cycle: 'monthly', review_status: 'on_track', evaluation: { pass_rate: 1 }, submitted_metrics: { delivery_output: confirmedValue },
      plan_proposal: { proposal_id: 7, status: 'proposed', stale: false, changes: [{ id: 'chg_1', kind: 'replace_target_plan', job_id: 'job-1', before: {}, after: {}, accepted: true }] }
    })
  })
  await page.route('**/api/report/plan-proposals/7/decision', async route => {
    proposalDecision = String((await route.request().postDataJSON()).decision || '')
    return fulfillOk(route, { proposal_id: 7, report_id: 42, status: 'accepted', accepted_change_ids: ['chg_1'] })
  })
  await page.goto('/report')
  await page.getByRole('tab', { name: /复盘/ }).click()
  const input = page.getByPlaceholder('本月完成了什么、能力哪里进步、有没有新成果、下月准备做什么…')
  await input.fill('本月完成作品集，并进行了两次项目讲解。')
  await page.getByRole('button', { name: '生成可核对草稿' }).click()
  await expect.poll(() => submittedText).toContain('本月完成作品集')
  await expect(page.getByText('进行了两次项目讲解')).toBeVisible()
  await page.getByRole('button', { name: '确认采用' }).click()
  await page.getByRole('button', { name: '确认复盘事实' }).click()
  await expect.poll(() => confirmedValue).toBe(2)
  await expect(input).toHaveValue('')
  await expect(page.getByText('尚未生效')).toBeVisible()
  await page.getByRole('button', { name: '应用所选变更' }).click()
  await expect.poll(() => proposalDecision).toBe('accept')
  await expect(page.getByText('已应用所选计划变更').first()).toBeVisible()
})
