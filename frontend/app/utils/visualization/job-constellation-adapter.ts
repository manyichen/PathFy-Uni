import { capabilityDimensions, type CapabilityDimension } from '~/types/capability'
import type { JobCard } from '~/types/job'
import type {
  JobConstellationEdge,
  JobConstellationGroup,
  JobConstellationNode,
  JobConstellationSceneData,
  JobConstellationSourceKind
} from '~/types/job-constellation'

interface JobConstellationSource {
  jobs?: JobCard[]
  selectedId?: string | null
  sourceKind?: JobConstellationSourceKind
  totalAvailable?: number
  page?: number
  pageSize?: number
  query?: string
  sort?: string
  animationRevision?: number
}

const capabilityRegions = [
  { id: 'research', label: '专业深研', color: '#38bdf8', value: (scores: Record<CapabilityDimension, number>) => scores.cap_req_theory },
  { id: 'engineering', label: '实践工程', color: '#2dd4bf', value: (scores: Record<CapabilityDimension, number>) => scores.cap_req_practice },
  { id: 'digital', label: '数字技术', color: '#818cf8', value: (scores: Record<CapabilityDimension, number>) => scores.cap_req_digital },
  { id: 'innovation', label: '创新跨域', color: '#c084fc', value: (scores: Record<CapabilityDimension, number>) => (scores.cap_req_cross + scores.cap_req_innovation) / 2 },
  { id: 'collaboration', label: '协作连接', color: '#fb7185', value: (scores: Record<CapabilityDimension, number>) => (scores.cap_req_teamwork + scores.cap_req_social) / 2 },
  { id: 'growth', label: '成长进阶', color: '#f59e0b', value: (scores: Record<CapabilityDimension, number>) => scores.cap_req_growth }
] as const

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function text(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function stableKey(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

function normalizedScores(job: JobCard): Record<CapabilityDimension, number> {
  const values = capabilityDimensions.map(dimension => number(job.scores?.[dimension]))
  const maximum = Math.max(0, ...values)
  const scale = maximum > 0 && maximum <= 1 ? 100 : 1
  return Object.fromEntries(capabilityDimensions.map((dimension, index) => [
    dimension,
    Math.max(0, Math.min(100, values[index]! * scale))
  ])) as Record<CapabilityDimension, number>
}

function average(scores: Record<CapabilityDimension, number>): number {
  return capabilityDimensions.reduce((sum, dimension) => sum + scores[dimension], 0) / capabilityDimensions.length
}

function dominantRegion(scores: Record<CapabilityDimension, number>, jobId: string) {
  const ranked = capabilityRegions.map(region => ({ region, value: region.value(scores) }))
  const maximum = Math.max(...ranked.map(item => item.value))
  const tied = ranked.filter(item => Math.abs(item.value - maximum) < .001)
  return tied[Math.floor(Number.parseInt(stableKey(jobId), 36) % tied.length)]?.region || capabilityRegions[0]
}

function projection(scores: Record<CapabilityDimension, number>) {
  const foundational = (scores.cap_req_theory + scores.cap_req_practice + scores.cap_req_growth) / 3
  const exploratory = (scores.cap_req_cross + scores.cap_req_digital + scores.cap_req_innovation) / 3
  const individual = (scores.cap_req_theory + scores.cap_req_practice + scores.cap_req_digital + scores.cap_req_innovation) / 4
  const collaborative = (scores.cap_req_teamwork + scores.cap_req_social + scores.cap_req_growth) / 3
  return {
    projectedX: Math.max(-1, Math.min(1, (exploratory - foundational) / 100)),
    projectedY: Math.max(-1, Math.min(1, (collaborative - individual) / 100))
  }
}

function vectorDistance(left: JobConstellationNode, right: JobConstellationNode): number {
  const squared = capabilityDimensions.reduce((sum, dimension) => {
    const difference = left.scores[dimension] - right.scores[dimension]
    return sum + difference ** 2
  }, 0)
  return Math.sqrt(squared) / Math.sqrt(capabilityDimensions.length * 100 ** 2)
}

function closestEdges(nodes: JobConstellationNode[]): JobConstellationEdge[] {
  const edges = new Map<string, JobConstellationEdge>()
  const grouped = new Map<string, JobConstellationNode[]>()
  for (const node of nodes) grouped.set(node.groupKey, [...(grouped.get(node.groupKey) || []), node])
  for (const [groupKey, groupNodes] of grouped) {
    if (groupNodes.length < 2) continue
    for (const node of groupNodes) {
      const closest = groupNodes
        .filter(candidate => candidate.id !== node.id)
        .map(candidate => ({ candidate, distance: vectorDistance(node, candidate) }))
        .sort((left, right) => left.distance - right.distance || left.candidate.id.localeCompare(right.candidate.id))[0]
      if (!closest) continue
      const ids = [node.id, closest.candidate.id].sort()
      const id = `${ids[0]}:${ids[1]}`
      edges.set(id, {
        id,
        source: ids[0]!,
        target: ids[1]!,
        similarity: Math.max(0, Math.min(1, 1 - closest.distance)),
        groupKey
      })
    }
  }
  return [...edges.values()].sort((left, right) => left.id.localeCompare(right.id))
}

export function buildJobConstellationSceneData(source: JobConstellationSource): JobConstellationSceneData {
  const jobs = Array.isArray(source.jobs) ? source.jobs.filter(job => String(job?.id || '').trim()) : []
  const selectedId = String(source.selectedId || '')

  const nodes = jobs.map((job): JobConstellationNode => {
    const scores = normalizedScores(job)
    const requirementAverage = average(scores)
    const location = text(job.location, '地点未标注')
    const region = dominantRegion(scores, String(job.id))
    return {
      id: String(job.id),
      title: text(job.title, '未命名岗位'),
      company: text(job.company, '未知公司'),
      location,
      salary: text(job.salary, '薪资面议'),
      groupKey: `capability:${region.id}`,
      groupLabel: region.label,
      requirementAverage,
      ...projection(scores),
      radius: 6 + requirementAverage / 100 * 7,
      scores,
      selected: String(job.id) === selectedId
    }
  }).sort((left, right) => {
    const leftIndex = capabilityRegions.findIndex(region => region.label === left.groupLabel)
    const rightIndex = capabilityRegions.findIndex(region => region.label === right.groupLabel)
    return leftIndex - rightIndex || left.id.localeCompare(right.id)
  })

  const groups = capabilityRegions.map((region): JobConstellationGroup => ({
    key: `capability:${region.id}`,
    label: region.label,
    color: region.color,
    count: nodes.filter(node => node.groupKey === `capability:${region.id}`).length
  }))
  const requirementValues = nodes.map(node => node.requirementAverage)
  const sourceKind = source.sourceKind === 'assistant' ? 'assistant' : 'list'
  const page = Math.max(1, Math.floor(number(source.page) || 1))
  const pageSize = Math.max(1, Math.floor(number(source.pageSize) || Math.max(1, nodes.length)))
  const transitionParts = [sourceKind, String(source.query || '').trim(), String(source.sort || 'default'), page, ...nodes.map(node => node.id)]

  return {
    nodes,
    groups,
    edges: closestEdges(nodes),
    selectedId,
    sourceKind,
    resultLabel: sourceKind === 'assistant' ? 'AI 助手当前筛选结果' : `普通列表第 ${page} 页`,
    totalAvailable: Math.max(nodes.length, Math.floor(number(source.totalAvailable))),
    page,
    pageSize,
    transitionKey: transitionParts.join('|'),
    animationRevision: Math.max(0, Math.floor(number(source.animationRevision))),
    summary: {
      resultCount: nodes.length,
      regionCount: groups.filter(group => group.count > 0).length,
      minimumRequirement: requirementValues.length ? Math.min(...requirementValues) : 0,
      maximumRequirement: requirementValues.length ? Math.max(...requirementValues) : 0
    }
  }
}
