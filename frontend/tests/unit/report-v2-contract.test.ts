import { describe, expect, it } from 'vitest'
import { careerReportSchema, reportDecisionSupportSchema } from '~/composables/api/useReportApi'

describe('career report V2 contract', () => {
  it('accepts a grounded fact-claim-action chain', () => {
    const result = reportDecisionSupportSchema.parse({
      schema_version: 2,
      fact_model: 'fact-claim-impact-action-deliverable-metric',
      target_decisions: [{
        job_id: 'job-1', display_title: '数据分析师', role: 'primary', role_label: '主目标',
        judgement: { recommendation: '优先推进', match_score: 78, reasons: [], risks: [], data_gaps: [] },
        claims: [{
          id: 'claim-1', kind: 'gap', title: '实践技能需补齐', summary: '差距 19 分', impact: '影响项目交付', fact_refs: ['fact-1'],
          facts: [{ id: 'fact-1', label: '有效差距', value: 19, unit: '分', source_type: 'system_calculated', source_label: '系统计算', evidence_grade: 'B' }],
          quality: { grounded: true, evidence_grade: 'B', source_type: 'system_calculated' }
        }],
        actions: [{
          id: 'action-1', job_id: 'job-1', item_index: 0, action_index: 0, title: '完成项目', kind: 'deliverable', deliverable: 'README 与截图', deadline: '第 1 周末', effort_hours: 4,
          acceptance_criteria: ['README 可访问'], evidence_required: true, evidence_grade_required: 'B', status: 'todo', done: false, done_at: null, source_claim_ids: ['claim-1']
        }],
        primary_action_id: 'action-1', freshness: { profile: { source_label: '画像快照', evidence_grade: 'B' } }
      }],
      target_comparison: [{ job_id: 'job-1', display_title: '数据分析师', role: 'primary', role_label: '主目标', match_score: 78, top_gap: '实践技能', primary_action: '完成项目', evidence_coverage: 1 }],
      shared_actions: [], evidence_legend: [{ grade: 'B', label: '系统记录', objective: true }]
    })

    expect(result.target_decisions[0]?.actions[0]?.deliverable).toBe('README 与截图')
    expect(result.target_decisions[0]?.actions[0]?.done_at).toBeNull()
  })

  it('rejects an ungraded fact', () => {
    expect(() => reportDecisionSupportSchema.parse({ schema_version: 2, fact_model: 'x', target_decisions: [], target_comparison: [], shared_actions: [], evidence_legend: [{ grade: 'E', label: '未知', objective: false }] })).toThrow()
  })

  it('validates the immutable snapshot and enrichment quality envelope', () => {
    const parsed = careerReportSchema.parse({
      input_snapshot: { schema_version: 1, captured_at: '2026-08-19 10:00:00', sha256: 'a'.repeat(64) },
      enrichment_quality: {
        status: 'repaired', score: 82, initial_score: 68, repair_attempts: 1,
        dimensions: { traceability: 35, specificity: 15, actionability: 17, coverage: 10, consistency: 5 },
        issues: [{ code: 'vague_actions', severity: 'warning', repairable: true, count: 2 }]
      }
    })
    expect(parsed.enrichment_quality?.status).toBe('repaired')
    expect(() => careerReportSchema.parse({ input_snapshot: { schema_version: 1, captured_at: 'x', sha256: 'short' } })).toThrow()
  })

  it('accepts report snapshot v2 with a frozen preference strategy', () => {
    const parsed = careerReportSchema.parse({
      input_snapshot: { schema_version: 2, captured_at: '2026-08-19 10:00:00', sha256: 'b'.repeat(64), personality_profile_id: 7, preference_profile: { status: 'measured', axes: [] } },
      preference_strategy: { status: 'suggested', version: 'preference-strategy-v1', influences_capability: false, disclaimer: '不改变能力要求', sections: [{ code: 'structure_preference', title: '时间组织方式', recommendation: '固定检查点', alternative: '短冲刺', rationale: '来自连续偏好值' }] }
    })
    expect(parsed.input_snapshot?.schema_version).toBe(2)
    expect((parsed as Record<string, unknown>).preference_strategy).toBeTruthy()
  })
})
