import { describe, expect, it } from 'vitest'
import { buildProfileEvidenceSceneData } from '~/utils/visualization/profile-evidence-adapter'

describe('profile evidence visualization adapter', () => {
  it('uses an honest overview mapping when the API only provides materials and final scores', () => {
    const scene = buildProfileEvidenceSceneData({
      materials: [
        { name: '个人简历.pdf', kind: '简历', chars: 3200 },
        { name: '课程项目.md', kind: '项目', chars: 1400 }
      ],
      scores: { cap_req_theory: 82, cap_req_practice: 91 }
    })

    expect(scene.mappingMode).toBe('overview')
    expect(scene.dimensions).toHaveLength(8)
    expect(scene.flows).toHaveLength(16)
    expect(scene.flows.every(flow => flow.inferred)).toBe(true)
    expect(scene.summary).toEqual({ materialCount: 2, dimensionCount: 8, explicitFlowCount: 0 })
  })

  it('prefers valid explicit contribution records and accepts dimension labels or keys', () => {
    const scene = buildProfileEvidenceSceneData({
      materials: [
        { id: 'resume-1', name: '个人简历.pdf', kind: '简历' },
        { id: 'project-1', name: '课程项目.md', kind: '项目' }
      ],
      analysis: {
        capability_evidence_contributions: [
          { material_id: 'resume-1', dimension: '团队协作', weight: 72, confidence: .88 },
          { material_name: '课程项目.md', capability_dimension: 'cap_req_digital', contribution: .9 },
          { material_id: 'missing', dimension: '实践技能', weight: .5 },
          { material_id: 'resume-1', dimension: '不存在的维度', weight: .5 }
        ]
      }
    })

    expect(scene.mappingMode).toBe('explicit')
    expect(scene.flows).toHaveLength(2)
    expect(scene.flows.map(flow => flow.dimension)).toEqual(['cap_req_teamwork', 'cap_req_digital'])
    expect(scene.flows.every(flow => !flow.inferred)).toBe(true)
    expect(scene.flows[0]).toMatchObject({ materialId: 'resume-1', weight: .72, confidence: .88 })
    expect(scene.summary.explicitFlowCount).toBe(2)
  })

  it('falls back to overview mode if none of the supplied contribution rows can be linked', () => {
    const scene = buildProfileEvidenceSceneData({
      materials: [{ id: 'resume-1', name: '个人简历.pdf' }],
      analysis: {
        evidence_contributions: [{ material_id: 'missing', dimension: '实践技能', weight: .8 }]
      }
    })

    expect(scene.mappingMode).toBe('overview')
    expect(scene.flows).toHaveLength(8)
    expect(scene.flows.every(flow => flow.inferred)).toBe(true)
  })

  it('keeps the scene usable when no material metadata is available', () => {
    const scene = buildProfileEvidenceSceneData({ scores: { cap_req_growth: 86 } })

    expect(scene.materials).toEqual([
      expect.objectContaining({ id: 'material:combined', name: '画像综合材料', kind: '综合分析' })
    ])
    expect(scene.flows).toHaveLength(8)
    expect(scene.animationRevision).toBe(0)
  })
})
