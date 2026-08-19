import { describe, expect, it } from 'vitest'
import { buildCareerGraphData } from '~/utils/visualization/career-graph-adapter'

describe('career graph visualization adapter', () => {
  it('merges promotion stages and lateral routes into one stable graph', () => {
    const graph = buildCareerGraphData({
      currentJob: { id: 'job-1', title: '数据分析师', company: '示例科技' },
      promotion: {
        routes: [
          {
            id: 'route-1',
            route_title: '专业路线',
            confidence: 0.86,
            stages: [
              { stage: 1, role: '高级数据分析师', milestone: '独立负责分析项目' },
              { stage: 2, role: '数据分析负责人', milestone: '负责团队交付' }
            ]
          }
        ]
      },
      lateral: {
        routes: [
          { id: 'lateral-1', target_title: '商业分析师', cap_similarity: 0.78, rationale: '通用分析能力可迁移' }
        ]
      }
    })

    expect(graph.nodes.map(node => node.title)).toEqual(expect.arrayContaining([
      '数据分析师', '高级数据分析师', '数据分析负责人', '商业分析师'
    ]))
    expect(graph.edges.filter(edge => edge.kind === 'promotion')).toHaveLength(2)
    expect(graph.edges.filter(edge => edge.kind === 'lateral')[0]?.confidence).toBe(.78)
    expect(graph.summary).toEqual({ promotionCount: 1, lateralCount: 1, hasTransition: false })
  })

  it('deduplicates shared roles and upgrades an explicit target node', () => {
    const graph = buildCareerGraphData({
      currentJob: { id: 'job-1', title: '前端开发' },
      targetJob: { id: 'job-2', title: '产品经理', company: '目标公司' },
      promotion: {
        routes: [
          { confidence: 72, stages: [{ role: '技术负责人' }] },
          { confidence: .68, stages: [{ role: '技术负责人' }] }
        ]
      },
      lateral: { routes: [{ target_title: '产品经理', score: 81 }] },
      transition: { to_job: { id: 'job-2', title: '产品经理' }, advice: { summary: '补充产品实践' } }
    })

    expect(graph.nodes.filter(node => node.title === '技术负责人')).toHaveLength(1)
    expect(graph.nodes.find(node => node.title === '产品经理')).toMatchObject({ kind: 'target', description: '目标公司' })
    expect(graph.edges.find(edge => edge.kind === 'transition')?.description).toBe('补充产品实践')
    expect(graph.summary.hasTransition).toBe(true)
  })

  it('always returns a usable current node for incomplete API data', () => {
    const graph = buildCareerGraphData({ promotion: { routes: [] }, lateral: { routes: [] } })
    expect(graph.nodes).toHaveLength(1)
    expect(graph.nodes[0]).toMatchObject({ kind: 'current', title: '当前岗位' })
    expect(graph.currentNodeId).toBe(graph.nodes[0]?.id)
  })
})
