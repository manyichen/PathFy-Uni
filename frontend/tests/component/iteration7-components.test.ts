import { mount, type MountingOptions } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MatchCandidateCard from '~/components/match/MatchCandidateCard.vue'
import ReportTargetTabs from '~/components/report/ReportTargetTabs.vue'
import ReportConfigPanel from '~/components/report/ReportConfigPanel.vue'
import ReportMonthlyTimeline from '~/components/report/ReportMonthlyTimeline.vue'
import ReportAdjustmentNotice from '~/components/report/ReportAdjustmentNotice.vue'
import ReportMonthDetail from '~/components/report/ReportMonthDetail.vue'
import ProfileMaterialWorkbench from '~/components/profile/ProfileMaterialWorkbench.vue'
import PersonalityDimensions from '~/components/personality/PersonalityDimensions.vue'
import PersonalityRecommendedJobs from '~/components/personality/PersonalityRecommendedJobs.vue'

const stubs = {
  UCard: { template: '<section><slot name="header"/><slot/></section>' },
  UButton: { template: '<button type="button"><slot/></button>' },
  UBadge: { props: ['label'], template: '<span>{{ label }}<slot/></span>' },
  UIcon: { template: '<i />' },
  UFormField: { template: '<label><slot/></label>' },
  UInput: { template: '<input />' },
  USelect: { template: '<select />' },
  UTextarea: { template: '<textarea />' },
  UAlert: { template: '<div role="alert"><slot/></div>' }
}

function options<T>(props: T): MountingOptions<Record<string, unknown>> {
  return { props: props as Record<string, unknown>, global: { stubs } }
}

describe('iteration 7 component contracts', () => {
  it('lets keyboard users select a match candidate without triggering detail', async () => {
    const job = { id: 'job-1', title: '数据分析师', company: '示例科技' }
    const wrapper = mount(MatchCandidateCard, options({ job, rank: 1, score: 88, strengths: ['数字能力'] }))
    const select = wrapper.get('button')
    expect(select.text()).toContain('选择比较')
    await select.trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual([job])
    expect(wrapper.emitted('detail')).toBeUndefined()
  })

  it('keeps report tabs single-selected and supports arrow navigation', async () => {
    const targets = [
      { job_id: 'job-1', title: '数据分析师', match_preview: { match_score: 88 } },
      { job_id: 'job-2', title: '商业分析师', match_preview: { match_score: 82 } }
    ]
    const wrapper = mount(ReportTargetTabs, options({ targets, activeJobId: 'job-1', primaryJobId: 'job-1' }))
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map(tab => tab.attributes('aria-selected'))).toEqual(['true', 'false'])
    await tabs[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('select')?.[0]).toEqual(['job-2'])
  })

  it('lets users choose an explicit primary report target', async () => {
    const targets = [
      { job_id: 'job-1', title: '数据分析师' },
      { job_id: 'job-2', title: '商业分析师' }
    ]
    const wrapper = mount(ReportConfigPanel, options({
      collapsed: false,
      hasReport: false,
      status: '已选择 2 个目标',
      resumes: [],
      resumeId: undefined,
      goal: 'fit',
      targets,
      primaryJobId: 'job-1',
      loading: ''
    }))

    await wrapper.get('[aria-label="设为主目标"]').trigger('click')

    expect(wrapper.emitted('set-primary')?.[0]).toEqual(['job-2'])
    expect(wrapper.text()).toContain('主目标')
  })

  it('maps reviews and adjustments to the expected timeline month', async () => {
    const wrapper = mount(ReportMonthlyTimeline, options({
      line: { timeline: [{ month: 2, kind: 'review', label: '二月复盘' }] },
      adjustments: [{ anchor_review_month: 3, label: '三月调整' }],
      selectedMonth: 2
    }))
    expect(wrapper.get('[aria-label*="第2月"]').attributes('aria-current')).toBe('step')
    expect(wrapper.get('[aria-label*="第3月"]').attributes('aria-label')).toContain('有计划')
    await wrapper.get('[aria-label*="第3月"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual([3])
  })

  it('explains strong replanning with failed metrics and next action', () => {
    const wrapper = mount(ReportAdjustmentNotice, options({
      report: { evaluation: {} },
      adjustments: [{ replan_mode: 'strong', failed_rows: [{ label: '作品集完成度' }], plan_items: [{ milestone: '补齐作品集' }], execution_hints: ['本周完成案例复盘'] }]
    }))
    expect(wrapper.text()).toContain('强化调整')
    expect(wrapper.text()).toContain('作品集完成度')
    expect(wrapper.text()).toContain('本周完成案例复盘')
  })

  it('shows the verified action basis and pending next-month arrangement together', async () => {
    const wrapper = mount(ReportMonthDetail, options({
      month: 2,
      jobId: 'job-1',
      line: { timeline: [{ month: 1, kind: 'review', progress: 4 }, { month: 2, kind: 'review', progress: 11.5, detail: { review_text: '完成比赛提交', submitted: {}, action_completion: { done_count: 1, total_count: 2, completion_rate: 0.5 } } }] },
      adjustments: [],
      proposal: { proposal_id: 9, status: 'proposed', stale: false, changes: [{ id: 'change-1', kind: 'replace_target_plan', job_id: 'job-1', accepted: true, before: {}, after: { next_month_plan: { plan_month: 3, review_anchor_month: 2, phase_label: '能力补齐', items: [{ milestone: '完成建模作品复盘', custom_actions: [{ text: '整理一页项目说明' }] }] } } }] }
    }))
    expect(wrapper.text()).toContain('本月轨迹推进')
    expect(wrapper.text()).toContain('1 / 2')
    expect(wrapper.text()).toContain('第 3 月安排')
    expect(wrapper.text()).toContain('待你确认后生效')
    await wrapper.findAll('button').at(-1)!.trigger('click')
    expect(wrapper.emitted('openReview')).toHaveLength(1)
  })

  it('exposes profile file guidance and emits selected files', async () => {
    const wrapper = mount(ProfileMaterialWorkbench, {
      ...options({ files: [], loading: false, name: '小林', major: '计算机', text: '' }),
      props: { files: [], loading: false, name: '小林', major: '计算机', text: '', 'onUpdate:name': () => {}, 'onUpdate:major': () => {}, 'onUpdate:text': () => {} }
    })
    expect(wrapper.get('#profile-material-input').attributes('accept')).toContain('.pdf')
    expect(wrapper.get('#profile-file-help').text()).toContain('0/12')
    await wrapper.get('#profile-material-input').trigger('change')
    expect(wrapper.emitted('choose')).toHaveLength(1)
  })

  it('renders complete personality evidence sections only when data exists', () => {
    const dimensions = mount(PersonalityDimensions, options({ items: [{ dimension: '能量', type: 'I', characteristics: ['专注'], growth_suggestions: ['主动表达'] }] }))
    const jobs = mount(PersonalityRecommendedJobs, options({ jobs: ['数据分析师'], advice: '优先选择深度工作环境' }))
    expect(dimensions.text()).toContain('四维偏好解析')
    expect(dimensions.text()).toContain('主动表达')
    expect(jobs.text()).toContain('数据分析师')
  })
})
