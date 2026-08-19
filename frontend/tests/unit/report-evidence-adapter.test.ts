import { describe, expect, it } from 'vitest'
import type { ReportTargetDecision } from '~/types/report'
import { buildReportEvidenceSceneData } from '~/utils/visualization/report-evidence-adapter'

function decision(): ReportTargetDecision {
  return {
    job_id: 'job-1', display_title: 'Java 工程师', role: 'primary', role_label: '主目标',
    judgement: { recommendation: '谨慎推进', match_score: 82, reasons: [], risks: [], data_gaps: [] },
    claims: [{
      id: 'claim-risk', kind: 'risk', dimension: 'cap_req_digital', title: '数字素养仍需验证', summary: '当前 70，要求 78', impact: '用项目验证',
      fact_refs: ['profile:cap_req_digital', 'job:job-1:cap_req_digital'],
      facts: [
        { id: 'profile:cap_req_digital', label: '当前能力', value: 70, unit: '分', source_type: 'profile', source_label: '能力画像', evidence_grade: 'B', verified: true },
        { id: 'job:job-1:cap_req_digital', label: '岗位要求', value: 78, unit: '分', source_type: 'job', source_label: '岗位快照', evidence_grade: 'B', verified: true }
      ],
      quality: { grounded: true, evidence_grade: 'B', source_type: 'computed' }
    }],
    actions: [
      { id: 'action-linked', job_id: 'job-1', item_index: 0, action_index: 0, title: '完成项目', kind: 'practice', deliverable: '项目链接', deadline: '本月', effort_hours: 4, acceptance_criteria: ['可访问'], evidence_required: true, evidence_grade_required: 'B', status: 'todo', source_claim_ids: ['claim-risk'], source_fact_refs: ['profile:cap_req_digital'] },
      { id: 'action-unlinked', job_id: 'job-1', item_index: 0, action_index: 1, title: '泛化行动', kind: 'learn', deliverable: '笔记', deadline: '本月', effort_hours: 2, acceptance_criteria: ['完成'], evidence_required: true, evidence_grade_required: 'C', status: 'todo', source_claim_ids: [], source_fact_refs: [] }
    ],
    evidence_metrics: { coverage: .68, claim_grounding: 1, action_traceability: .5, fact_verification: 1, claim_count: 1, fact_count: 2, action_count: 2, unlinked_action_count: 1 },
    freshness: {}
  }
}

describe('report evidence visualization adapter', () => {
  it('organizes facts, conclusion and actions into a quantitative capability row', () => {
    const scene = buildReportEvidenceSceneData(decision())
    const row = scene.rows[0]

    expect(row).toMatchObject({
      dimensionLabel: '数字素养', state: 'verify', currentScore: 70, requiredScore: 78,
      signedDelta: -8, rawGap: 8, comparisonLabel: '低于标尺 8 分 · 尚在软容差内',
      closureState: 'in_progress', chainConnected: true
    })
    expect(row?.actions.map(action => action.id)).toEqual(['action-linked'])
    expect(scene.orphanActions.map(action => action.id)).toEqual(['action-unlinked'])
  })

  it('separates chain completeness from real outcome evidence', () => {
    const scene = buildReportEvidenceSceneData(decision())

    expect(scene.selectedRowId).toBe('claim-risk')
    expect(scene.summary).toMatchObject({ coverage: .68, comparableCount: 1, riskCount: 1, actionCount: 2, linkedActionCount: 1, unlinkedActionCount: 1, outcomeEvidenceCount: 0 })
  })

  it('marks a completed checkbox as awaiting review rather than verified evidence', () => {
    const input = decision()
    input.actions[0]!.done = true
    input.actions[0]!.status = 'done'
    const scene = buildReportEvidenceSceneData(input)

    expect(scene.rows[0]?.closureState).toBe('awaiting_review')
    expect(scene.rows[0]?.closureLabel).toContain('待复盘验真')
    expect(scene.summary.outcomeEvidenceCount).toBe(0)
  })

  it('returns an honest empty state when there is no decision', () => {
    const scene = buildReportEvidenceSceneData(undefined)
    expect(scene.rows).toEqual([])
    expect(scene.summary.coverage).toBe(0)
  })
})
