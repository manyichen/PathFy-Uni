import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReportSummaryCard from '~/components/report/ReportSummaryCard.vue'
import type { CareerReport } from '~/types/api'

const stubs = {
  UAlert: { props: ['title', 'description'], template: '<div>{{ title }} {{ description }}</div>' },
  UBadge: { props: ['label'], template: '<span>{{ label }}</span>' },
  UButton: { template: '<button><slot /></button>' },
  UCard: { template: '<section><slot /></section>' },
  UIcon: { template: '<i />' }
}

function report(status: 'accepted' | 'repaired' | 'fallback'): CareerReport {
  return {
    generated_at: '2026-08-19 10:00:00', targets: [], plans_by_target: [],
    enrichment_quality: {
      status, score: status === 'accepted' ? 94 : 82, initial_score: 65, repair_attempts: 1,
      dimensions: { traceability: 35, specificity: 15, actionability: 17, coverage: 10, consistency: 5 }, issues: []
    }
  }
}

describe('report enrichment quality disclosure', () => {
  it('shows a passed quality score', () => {
    const wrapper = mount(ReportSummaryCard, { props: { report: report('accepted'), reportId: 9, goal: 'fit' }, global: { stubs } })
    expect(wrapper.text()).toContain('AI 内容已通过 · 94 分')
  })

  it('explains deterministic fallback without exposing model errors', () => {
    const wrapper = mount(ReportSummaryCard, { props: { report: report('fallback'), reportId: 9, goal: 'fit' }, global: { stubs } })
    expect(wrapper.text()).toContain('当前为规则版')
    expect(wrapper.text()).toContain('AI 输出未达到质量门槛')
    expect(wrapper.text()).not.toContain('prompt')
  })

  it('emits a bounded partition refresh scope', async () => {
    const wrapper = mount(ReportSummaryCard, { props: { report: report('accepted'), reportId: 9, goal: 'fit' }, global: { stubs } })
    await wrapper.get('button:nth-of-type(2)').trigger('click')
    expect(wrapper.emitted('refresh')?.[0]).toEqual(['resources'])
  })
})
