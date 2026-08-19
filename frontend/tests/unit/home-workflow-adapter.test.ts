import { describe, expect, it } from 'vitest'
import { buildHomeWorkflowSceneData } from '../../app/utils/visualization/home-workflow-adapter'

describe('home workflow experience adapter', () => {
  it('exposes the fixed five-stage product workflow in order', () => {
    const result = buildHomeWorkflowSceneData()
    expect(result.stages.map(stage => stage.key)).toEqual(['material', 'profile', 'match', 'plan', 'review'])
    expect(result.stages.map(stage => stage.to)).toEqual(['/profile', '/profile', '/match', '/report', '/report#review'])
  })

  it('contains only forward workflow relations and the truthful review feedback loop', () => {
    const result = buildHomeWorkflowSceneData()
    expect(result.edges.filter(edge => edge.kind === 'forward')).toHaveLength(4)
    expect(result.edges.filter(edge => edge.kind === 'feedback')).toEqual([
      { id: 'review-profile', source: 'review', target: 'profile', kind: 'feedback' }
    ])
  })

  it('clamps malformed stage positions to a valid product stage', () => {
    expect(buildHomeWorkflowSceneData({ activeIndex: -30 }).activeStage.key).toBe('material')
    expect(buildHomeWorkflowSceneData({ activeIndex: 99 }).activeStage.key).toBe('review')
    expect(buildHomeWorkflowSceneData({ activeStage: 'match' }).activeIndex).toBe(2)
  })

  it('uses stage and replay revision as the bounded transition key', () => {
    const initial = buildHomeWorkflowSceneData({ activeStage: 'plan', animationRevision: 0 })
    const replayed = buildHomeWorkflowSceneData({ activeStage: 'plan', animationRevision: 1 })
    expect(initial.transitionKey).toBe('plan:0')
    expect(replayed.transitionKey).toBe('plan:1')
    expect(replayed.activeStage.description).toContain('可验证任务')
  })
})
