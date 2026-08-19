import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReportDecisionEvidence from '~/components/report/ReportDecisionEvidence.vue'
import ReportTargetComparison from '~/components/report/ReportTargetComparison.vue'
import ReportWorkspaceTabs from '~/components/report/ReportWorkspaceTabs.vue'
import type { ReportDecisionSupport, ReportTargetDecision } from '~/types/api'

const stubs = {
  UAlert: { props: ['title', 'description'], template: '<div>{{ title }}{{ description }}</div>' },
  UBadge: { props: ['label'], template: '<span>{{ label }}</span>' },
  UCard: { template: '<section><slot name="header"/><slot/></section>' },
  UIcon: { template: '<i />' }
}

const decision: ReportTargetDecision = {
  job_id: 'job-1', display_title: '数据分析师', role: 'primary', role_label: '主目标',
  judgement: { recommendation: '优先推进', match_score: 78, reasons: ['数字素养是优势'], risks: ['实践技能是差距'], data_gaps: [] },
  claims: [{
    id: 'claim-1', kind: 'gap', title: '实践技能是当前首要补齐项', summary: '当前 55 分，岗位要求 80 分。', impact: '影响项目交付。', fact_refs: ['profile:practice'], priority: 12,
    facts: [{ id: 'profile:practice', label: '当前能力', value: 55, unit: '分', source_type: 'system_calculated', source_label: '系统计算', evidence_grade: 'B', observed_at: '2026-08-19' }],
    quality: { grounded: true, evidence_grade: 'B', source_type: 'system_calculated', freshness: '2026-08-19' }
  }],
  actions: [], primary_action_id: null,
  freshness: { profile: { as_of: '2026-08-19', source_label: '画像快照', evidence_grade: 'B' } }
}

const support: ReportDecisionSupport = {
  schema_version: 2, fact_model: 'fact-claim-impact-action-deliverable-metric', target_decisions: [decision],
  target_comparison: [{ job_id: 'job-1', display_title: '数据分析师', role: 'primary', role_label: '主目标', match_score: 78, top_gap: '实践技能', primary_action: '完成分析作品', evidence_coverage: 1 }],
  shared_actions: [{ dimension: 'cap_req_practice', label: '实践技能', target_count: 2, reason: '可以跨目标复用' }],
  evidence_legend: [{ grade: 'B', label: '系统记录', objective: true }]
}

describe('career report V2 components', () => {
  it('switches between four accessible report workspaces', async () => {
    const wrapper = mount(ReportWorkspaceTabs, { props: { modelValue: 'action', evidenceCount: 3, reviewCount: 1 }, global: { stubs } })
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(4)
    expect(tabs[0]?.attributes('aria-selected')).toBe('true')
    await tabs[1]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['evidence'])
  })

  it('renders expandable claims with source grade and freshness', () => {
    const wrapper = mount(ReportDecisionEvidence, { props: { decision }, global: { stubs } })
    expect(wrapper.text()).toContain('实践技能是当前首要补齐项')
    expect(wrapper.text()).toContain('当前能力')
    expect(wrapper.text()).toContain('系统计算')
    expect(wrapper.text()).toContain('画像快照')
    expect(wrapper.find('details').exists()).toBe(true)
  })

  it('renders a mobile-safe target comparison and shared action', () => {
    const wrapper = mount(ReportTargetComparison, { props: { support }, global: { stubs } })
    expect(wrapper.text()).toContain('多目标决策矩阵')
    expect(wrapper.text()).toContain('完成分析作品')
    expect(wrapper.text()).toContain('跨目标复用')
  })
})
