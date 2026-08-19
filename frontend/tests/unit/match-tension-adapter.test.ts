import { describe, expect, it } from 'vitest'
import { buildMatchTensionSceneData } from '~/utils/visualization/match-tension-adapter'

const baseScores = {
  cap_req_theory: 82,
  cap_req_cross: 72,
  cap_req_practice: 88,
  cap_req_digital: 91,
  cap_req_innovation: 76,
  cap_req_teamwork: 84,
  cap_req_social: 68,
  cap_req_growth: 86
}

describe('match tension visualization adapter', () => {
  it('classifies deficits, balanced dimensions and surpluses from the two score series', () => {
    const scene = buildMatchTensionSceneData({
      studentScores: baseScores,
      job: {
        id: 'job-1', title: '数据分析师',
        scores: { ...baseScores, cap_req_theory: 90, cap_req_cross: 73, cap_req_social: 60 }
      }
    })
    expect(scene.dimensions.map(item => item.id)).toEqual([
      'cap_req_theory',
      'cap_req_cross',
      'cap_req_practice',
      'cap_req_digital',
      'cap_req_innovation',
      'cap_req_teamwork',
      'cap_req_social',
      'cap_req_growth'
    ])

    expect(scene.dimensions).toHaveLength(8)
    expect(scene.dimensions.find(item => item.id === 'cap_req_theory')).toMatchObject({ gap: -8, status: 'deficit' })
    expect(scene.dimensions.find(item => item.id === 'cap_req_cross')).toMatchObject({ gap: -1, status: 'balanced' })
    expect(scene.dimensions.find(item => item.id === 'cap_req_social')).toMatchObject({ gap: 8, status: 'surplus' })
    expect(scene.summary).toMatchObject({ deficitCount: 1, balancedCount: 6, surplusCount: 1 })
    expect(scene.summary.largestDeficit?.id).toBe('cap_req_theory')
  })

  it('normalizes a complete 0-to-1 score series to the 0-to-100 contract', () => {
    const scene = buildMatchTensionSceneData({
      studentScores: { cap_req_theory: .82, cap_req_cross: .72 },
      job: { id: 'job-2', title: '研究助理', scores: { ...baseScores, cap_req_theory: 86 } }
    })

    expect(scene.dimensions.find(item => item.id === 'cap_req_theory')).toMatchObject({ studentScore: 82, requirementScore: 86, gap: -4, status: 'balanced' })
    expect(scene.dimensions.find(item => item.id === 'cap_req_cross')?.studentScore).toBe(72)
  })

  it('clamps invalid and out-of-range values without producing an unusable scene', () => {
    const scene = buildMatchTensionSceneData({
      studentScores: { cap_req_theory: Number.NaN, cap_req_digital: 140 },
      job: { id: '', title: '', scores: { ...baseScores, cap_req_theory: -8 } }
    })

    expect(scene.jobTitle).toBe('待选择岗位')
    expect(scene.dimensions.find(item => item.id === 'cap_req_theory')?.studentScore).toBe(0)
    expect(scene.dimensions.find(item => item.id === 'cap_req_digital')?.studentScore).toBe(100)
    expect(Number.isFinite(scene.summary.averageAbsoluteGap)).toBe(true)
  })

  it('changes the transition key when the selected job or its requirements change', () => {
    const first = buildMatchTensionSceneData({ studentScores: baseScores, job: { id: 'job-1', title: '岗位一', scores: baseScores } })
    const second = buildMatchTensionSceneData({ studentScores: baseScores, job: { id: 'job-2', title: '岗位二', scores: baseScores } })
    const updated = buildMatchTensionSceneData({ studentScores: baseScores, job: { id: 'job-1', title: '岗位一', scores: { ...baseScores, cap_req_growth: 92 } } })

    expect(first.transitionKey).not.toBe(second.transitionKey)
    expect(first.transitionKey).not.toBe(updated.transitionKey)
  })
})
