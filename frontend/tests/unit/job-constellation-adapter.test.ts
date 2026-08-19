import { describe, expect, it } from 'vitest'
import type { JobCard } from '../../app/types/job'
import { buildJobConstellationSceneData } from '../../app/utils/visualization/job-constellation-adapter'
import { layoutJobConstellationNodes } from '../../app/utils/visualization/scenes/job-constellation-scene'

function job(id: string, location: string, values: number[], scoreAvg?: number): JobCard {
  const [theory, cross, practice, digital, innovation, teamwork, social, growth] = values
  return {
    id,
    title: `${id}岗位`,
    company: `${id}公司`,
    location,
    salary: '15-20K',
    score_avg: scoreAvg,
    scores: {
      cap_req_theory: theory!, cap_req_cross: cross!, cap_req_practice: practice!, cap_req_digital: digital!,
      cap_req_innovation: innovation!, cap_req_teamwork: teamwork!, cap_req_social: social!, cap_req_growth: growth!
    }
  }
}

describe('job constellation visualization adapter', () => {
  it('groups by dominant capability region while preserving truthful projections and locations', () => {
    const result = buildJobConstellationSceneData({
      jobs: [
        job('a', '上海', [40, 80, 45, 90, 85, 70, 65, 55]),
        job('b', '北京', [80, 30, 85, 45, 35, 40, 35, 70])
      ]
    })

    expect(result.groups.map(group => group.label)).toEqual([
      '专业深研', '实践工程', '数字技术', '创新跨域', '协作连接', '成长进阶'
    ])
    expect(result.nodes.find(node => node.id === 'a')).toMatchObject({ groupLabel: '数字技术', location: '上海' })
    expect(result.nodes.find(node => node.id === 'b')).toMatchObject({ groupLabel: '实践工程', location: '北京' })
    expect(result.nodes.find(node => node.id === 'a')?.projectedX).toBeGreaterThan(0)
    expect(result.nodes.find(node => node.id === 'b')?.projectedX).toBeLessThan(0)
  })

  it('normalizes complete zero-to-one capability vectors before deriving node size', () => {
    const result = buildJobConstellationSceneData({ jobs: [job('a', '上海', [.8, .8, .8, .8, .8, .8, .8, .8], 12)] })
    const node = result.nodes[0]!

    expect(node.requirementAverage).toBe(80)
    expect(node.radius).toBeCloseTo(11.6)
  })

  it('connects each job only to a nearest capability neighbor inside the same capability region', () => {
    const result = buildJobConstellationSceneData({ jobs: [
      job('a', '上海', [90, 40, 45, 40, 40, 40, 40, 40]),
      job('b', '北京', [88, 41, 45, 40, 40, 40, 40, 40]),
      job('c', '上海', [40, 40, 90, 40, 40, 40, 40, 40])
    ] })

    expect(result.edges).toHaveLength(1)
    expect(result.edges[0]).toMatchObject({ source: 'a', target: 'b' })
    expect(result.edges[0]?.similarity).toBeGreaterThan(.95)
  })

  it('keeps selection out of the transition key and reports the current result boundary', () => {
    const jobs = [job('a', '', [50, 50, 50, 50, 50, 50, 50, 50])]
    const initial = buildJobConstellationSceneData({ jobs, selectedId: '', totalAvailable: 73, page: 2, pageSize: 20, query: '数据' })
    const selected = buildJobConstellationSceneData({ jobs, selectedId: 'a', totalAvailable: 73, page: 2, pageSize: 20, query: '数据' })

    expect(selected.transitionKey).toBe(initial.transitionKey)
    expect(selected.nodes[0]?.selected).toBe(true)
    expect(selected.nodes[0]?.location).toBe('地点未标注')
    expect(selected.groups).toHaveLength(6)
    expect(selected.summary.regionCount).toBe(1)
    expect(selected.summary.resultCount).toBe(1)
    expect(selected.totalAvailable).toBe(73)
  })

  it('separates a dense capability region instead of stacking nodes on one point', () => {
    const jobs = Array.from({ length: 17 }, (_, index) => job(
      `dense-${index}`,
      `地点-${String(index).padStart(2, '0')}`,
      [92, 44, 42, 40, 38, 36, 34, 46]
    ))
    const scene = buildJobConstellationSceneData({ jobs })
    for (const width of [800, 1280]) {
      const layout = layoutJobConstellationNodes(scene, width, 520)
      const denseNodes = layout.nodes.filter(item => item.node.groupLabel === '专业深研')

      expect(denseNodes).toHaveLength(17)
      for (let left = 0; left < denseNodes.length; left += 1) {
        for (let right = left + 1; right < denseNodes.length; right += 1) {
          const first = denseNodes[left]!
          const second = denseNodes[right]!
          const distance = Math.hypot(first.x - second.x, first.y - second.y)
          expect(distance).toBeGreaterThanOrEqual(first.node.radius + second.node.radius + 7)
        }
      }
    }
  })
})
