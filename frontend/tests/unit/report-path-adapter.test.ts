import { describe, expect, it } from 'vitest'
import { buildReportPathSceneData } from '~/utils/visualization/report-path-adapter'

const line = {
  line_id: 'data-line',
  line_name: '数据分析师成长线',
  timeline: [
    { month: 0, label: '起点', kind: 'origin' },
    { month: 1, label: '首月计划', kind: 'plan' },
    { month: 2, label: '月度复盘', kind: 'review', review_id: 11 }
  ]
}

describe('report path visualization adapter', () => {
  it('maps only real timeline events and preserves their event kinds', () => {
    const scene = buildReportPathSceneData({ reportId: 42, line, selectedMonth: 2 })

    expect(scene.nodes).toHaveLength(3)
    expect(scene.nodes.map(node => node.kind)).toEqual(['origin', 'plan', 'review'])
    expect(scene.nodes.find(node => node.kind === 'review')).toMatchObject({ month: 2, reviewId: '11', selected: true })
    expect(scene.summary).toMatchObject({ eventCount: 3, planCount: 1, reviewCount: 1, adjustmentCount: 0 })
    expect(scene.actualPoints).toEqual([{ id: 'growth-origin', month: 0, progress: 0, label: '报告起点', kind: 'origin', selected: false }])
    expect(scene.summary.dataState).toBe('unmeasured')
  })

  it('never fabricates a 0—100 curve from phase nodes and only plots explicit progress', () => {
    const scene = buildReportPathSceneData({
      line: {
        ...line,
        nodes: [{ label: '短期' }, { label: '中期' }, { label: '目标' }],
        timeline: [
          { month: 0, progress: 0, label: '起点', kind: 'origin' },
          { month: 1, label: '没有数值的计划', kind: 'plan' },
          { month: 2, progress: 18, label: '确认复盘', kind: 'review', review_id: 12, detail: { submitted: { project_completion: 70 } } }
        ]
      },
      plan: { job_id: 'job-1', phases: { early: { label: '基础期', period: '1-3 个月' }, middle: { label: '实践期', period: '4-6 个月' } } }
    })

    expect(scene.actualPoints.map(point => [point.month, point.progress])).toEqual([[0, 0], [2, 18]])
    expect(scene.plannedPoints).toEqual([])
    expect(scene.phases).toEqual([
      { id: 'phase:early', label: '基础期', startMonth: 1, endMonth: 3 },
      { id: 'phase:middle', label: '实践期', startMonth: 4, endMonth: 6 }
    ])
    expect(scene.summary).toMatchObject({ actualPointCount: 1, plannedPointCount: 0, latestVerifiedProgress: 18, dataState: 'single_review' })
  })

  it('branches a real adjustment from its review anchor without inventing other months', () => {
    const scene = buildReportPathSceneData({
      reportId: 42,
      line,
      adjustments: [{ id: 'adj-1', anchor_review_month: 2, plan_month: 3, label: '加强项目表达', replan_mode: 'strong' }]
    })

    const adjustment = scene.nodes.find(node => node.kind === 'adjustment')
    expect(adjustment).toMatchObject({ month: 2, linkedMonth: 3, label: '加强项目表达', replanMode: 'strong' })
    expect(scene.edges.find(edge => edge.kind === 'replan')).toMatchObject({ sourceId: 'review:2:11', targetId: adjustment?.id })
    expect(scene.nodes.some(node => node.month === 3)).toBe(false)
  })

  it('uses a truthful enrichment state and creates only the report origin when no line exists', () => {
    const pending = buildReportPathSceneData({ reportId: 7, report: { llm_enrich_pending: true } })
    const completed = buildReportPathSceneData({ reportId: 7, report: { llm_enrich_pending: false } })

    expect(pending.enrichment).toEqual({ status: 'pending', label: 'AI 内容待处理' })
    expect(completed.enrichment).toEqual({ status: 'completed', label: 'AI 内容已处理' })
    expect(pending.nodes).toEqual([{ id: 'origin:0:generated', kind: 'origin', month: 0, progress: 0, label: '报告起点', selected: true }])
  })

  it('changes its transition key only when the report path events change', () => {
    const first = buildReportPathSceneData({ reportId: 42, line, enrichState: 'queued', selectedMonth: 0 })
    const selection = buildReportPathSceneData({ reportId: 42, line, enrichState: 'completed', selectedMonth: 2 })
    const appended = buildReportPathSceneData({ reportId: 42, line: { ...line, timeline: [...line.timeline, { month: 3, kind: 'review', review_id: 12 }] } })

    expect(first.transitionKey).toBe(selection.transitionKey)
    expect(first.transitionKey).not.toBe(appended.transitionKey)
  })
})
