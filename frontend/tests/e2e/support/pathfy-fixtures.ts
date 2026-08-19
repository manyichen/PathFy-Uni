import type { Page, Route } from '@playwright/test'

export const standardUser = {
  id: 1,
  username: '视觉基线用户',
  email: 'visual@example.com',
  is_admin: false
}

export const adminUser = {
  ...standardUser,
  username: '图谱管理员',
  email: 'admin@example.com',
  is_admin: true
}

export const preferences = {
  theme: 'light',
  hue: '192',
  allow_external_llm: true,
  default_match_goal: 'fit',
  default_refine_with_llm: false,
  match_result_count: 30,
  report_copywriter: true,
  report_public_info: true,
  report_auto_replan: true,
  report_graph_recommendations: true,
  report_recommendation_llm: true,
  learning_resource_count: 5,
  competition_count: 3
}

export const capabilityScores = {
  cap_req_theory: 82,
  cap_req_cross: 72,
  cap_req_practice: 88,
  cap_req_digital: 91,
  cap_req_innovation: 76,
  cap_req_teamwork: 84,
  cap_req_social: 68,
  cap_req_growth: 86
}

export const profileDetail = {
  id: 1,
  resume_id: 1,
  name: '视觉基线用户',
  major: '计算机科学与技术',
  ...capabilityScores,
  completeness: 86,
  competitiveness: 83,
  detailed_analysis: {
    overall_evaluation: '具备扎实的数据分析与工程实践能力，适合从真实业务问题中持续积累可验证成果。',
    completeness_analysis: '课程、项目与竞赛证据覆盖较完整。',
    competitiveness_analysis: '数字素养和实践技能是当前主要优势。',
    material_summary: [
      { name: '个人简历.pdf', kind: '简历', status: 'ok', chars: 3280 },
      { name: '课程项目说明.md', kind: '项目', status: 'ok', chars: 1560 }
    ],
    advantage_dimensions: [
      { dimension: '数字素养', score: 91 },
      { dimension: '实践技能', score: 88 }
    ],
    weakness_dimensions: [
      { dimension: '社会网络', score: 68 },
      { dimension: '交叉学科', score: 72 }
    ],
    short_term_plan: [
      { title: '补齐作品集', description: '整理一个可复现的数据分析项目并记录业务结论。' },
      { title: '强化表达', description: '每周完成一次五分钟项目复盘演练。' }
    ],
    long_term_goals: [
      { goal: '形成稳定的数据产品能力', description: '把分析、工程和业务判断沉淀为可迁移的方法。' }
    ],
    dimension_analysis: Object.entries(capabilityScores).map(([dimension, score]) => ({
      dimension,
      score,
      level: score >= 85 ? '优势' : '良好',
      interpretation: '已有材料提供了稳定证据，下一步应通过真实项目继续验证。'
    })),
    industry_match: [
      { industry: '互联网数据服务', match_score: 89, description: '岗位密度高，能够充分发挥数据处理与协作优势。' },
      { industry: '企业数字化', match_score: 84, description: '适合在业务场景中积累数据产品经验。' }
    ],
    material_keywords: ['Python', 'SQL', '数据可视化', '团队协作', '机器学习']
  }
}

export const matchWorkspace = {
  v: 1,
  resumeId: 1,
  filters: { q: '数据', locationQ: '上海', goal: 'fit', refine: false },
  result: {
    student: { scores: capabilityScores },
    jobs: [
      {
        job: {
          id: 'job-1', title: '数据分析师', company: '示例科技', location: '上海',
          scores: { ...capabilityScores, cap_req_social: 74, cap_req_theory: 86 }
        },
        match_score: 88,
        reason: '数字素养和实践技能高度吻合，建议补充行业分析案例。'
      },
      {
        job: {
          id: 'job-2', title: '商业分析师', company: '未来零售', location: '杭州',
          scores: { ...capabilityScores, cap_req_cross: 84, cap_req_social: 80 }
        },
        match_score: 82,
        reason: '综合能力匹配，仍需加强商业表达和跨团队推动经验。'
      }
    ]
  }
}

const reportTarget = {
  id: 'job-1',
  job_id: 'job-1',
  title: '数据分析师',
  display_title: '数据分析师',
  company: '示例科技',
  location: '上海',
  salary: '15-22K',
  scores: capabilityScores,
  match_preview: {
    match_score: 88,
    dimension_gaps: { cap_req_theory: 4, cap_req_cross: 8, cap_req_social: 10 }
  },
  track_profile: {
    job_title: '数据分析师',
    hiring_visibility_0_100: 86,
    path_breadth_0_100: 80,
    resource_density_0_100: 84
  }
}

export const reportWorkspace = {
  v: 1,
  resumeId: 1,
  selectedResumeId: 1,
  targets: [reportTarget],
  selectedTargets: [reportTarget],
  goal: 'fit',
  reportId: 42,
  reportSnapshot: {
    generated_at: '2026-08-15T10:30:00',
    narrative: { text: '当前画像与数据分析师方向匹配良好。建议用三个月完成一个端到端作品集，再通过复盘持续提高业务表达。' },
    targets: [reportTarget],
    development_lines: {
      lines: [{
        line_id: 'data-line',
        line_name: '数据分析师成长线',
        timeline: [
          { month: 0, progress: 15, label: '能力盘点' },
          { month: 1, progress: 38, label: '专题训练' },
          { month: 3, progress: 68, label: '作品集完成' },
          { month: 6, progress: 88, label: '稳定投递' }
        ]
      }]
    },
    plans_by_target: [{
      job_id: 'job-1',
      display_title: '数据分析师',
      match_score: 88,
      narrative: { path_advice: '以业务问题为入口，建立从取数、分析到建议落地的完整证据链。' },
      next_month_plan: {
        phase_label: '基础强化',
        plan_month: 1,
        items: [{
          focus_label: '实践技能',
          milestone: '完成一个可公开演示的数据分析专题',
          learning_path: ['复习 SQL 窗口函数', '掌握指标体系设计'],
          practice_plan: ['完成数据清洗', '制作交互式看板'],
          custom_actions: [{ text: '每周日提交一次进展复盘', done: false }]
        }]
      },
      phases: {
        short: { label: '短期', period: '1-3 个月', summary: '补齐作品集与表达', items: [] },
        middle: { label: '中期', period: '3-6 个月', summary: '形成业务分析闭环', items: [] },
        long: { label: '长期', period: '6-12 个月', summary: '稳定输出可投递成果', items: [] }
      },
      recommendations: {
        learning_resources: [{ id: 'r-1', label: 'SQL 数据分析实战', resource_url: 'https://example.com/sql' }],
        competitions: [{ id: 'c-1', label: '高校数据分析挑战赛', official_url: 'https://example.com/competition' }]
      }
    }],
    evaluation: {
      metrics: [
        { code: 'portfolio', label: '作品集完成度', cycle: '每月', target: '完成 1 个端到端项目' },
        { code: 'interview', label: '项目表达', cycle: '双周', target: '完成 2 次模拟讲解' }
      ]
    }
  }
}

export async function seedAuthenticatedSession(page: Page, user = standardUser) {
  await page.addInitScript((sessionUser) => {
    if (!localStorage.getItem('auth_token')) localStorage.setItem('auth_token', 'e2e-token')
    if (!localStorage.getItem('auth_user')) localStorage.setItem('auth_user', JSON.stringify(sessionUser))
    if (!localStorage.getItem('theme')) localStorage.setItem('theme', 'light')
    if (!localStorage.getItem('hue')) localStorage.setItem('hue', '192')
  }, user)
}

export function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

export function fulfillOk(route: Route, data: unknown, status = 200) {
  return fulfillJson(route, { ok: status < 400, code: status, data }, status)
}

export function fulfillCode(route: Route, data: unknown, status = 200) {
  return fulfillJson(route, { code: status, data }, status)
}

export async function installStableApiMocks(page: Page) {
  await page.route('**://*/api/**', (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === '/api/account/preferences') {
      return fulfillOk(route, {
        stored: true,
        preferences,
        effective: preferences,
        limits: { match_result_count: 100, learning_resource_count: 20, competition_count: 10 }
      })
    }
    if (url.pathname === '/api/profile/resumes') {
      return fulfillCode(route, [{ id: 1, name: '视觉基线用户', major: '计算机科学与技术' }])
    }
    if (url.pathname === '/api/profile/result/1') return fulfillCode(route, profileDetail)
    if (url.pathname === '/api/report/42') {
      return fulfillOk(route, {
        report_id: 42,
        resume_id: 1,
        primary_job_id: 'job-1',
        target_job_ids: ['job-1'],
        report: reportWorkspace.reportSnapshot,
        llm_enrich_pending: false
      })
    }
    if (url.pathname === '/api/auth/me') return fulfillOk(route, { user: standardUser })
    if (url.pathname === '/api/graph/stats') {
      return fulfillOk(route, {
        jobs: 1280, job_count: 1280, jobtitle_count: 86, company_count: 312,
        skill_count: 438, learningresource_count: 125, competition_count: 34,
        capability_missing: 42, capability_stale: 18, low_confidence: 27, salary_stale: 16,
        curated_promotions: 92, auto_promotions: 38, curated_lateral: 74, auto_lateral: 51,
        inferred_jobs: 24, low_frequency_titles: 11
      })
    }
    if (url.pathname === '/api/graph/guard') {
      return fulfillOk(route, { graph_revision: 18, locked: false, updated_at: '2026-08-15T09:30:00' })
    }
    if (url.pathname === '/api/graph/tasks') {
      const status = url.searchParams.get('status')
      const counts: Record<string, number> = { queued: 2, running: 1, awaiting_confirmation: 3, failed: 1 }
      return fulfillOk(route, {
        items: status ? [] : [{ id: 27, status: 'succeeded', task_type: 'job_import', input_file_name: 'jobs_202608.xlsx', created_at: '2026-08-15T08:20:00' }],
        total: status ? counts[status] || 0 : 1,
        page: 1,
        page_size: 20
      })
    }

    return fulfillOk(route, { jobs: [], items: [], sessions: [], total: 0, total_pages: 1, preferences })
  })
}
