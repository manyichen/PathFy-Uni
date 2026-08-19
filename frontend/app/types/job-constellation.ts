import type { CapabilityDimension } from './capability'

export type JobConstellationSourceKind = 'list' | 'assistant'

export interface JobConstellationNode {
  id: string
  title: string
  company: string
  location: string
  salary: string
  groupKey: string
  groupLabel: string
  requirementAverage: number
  projectedX: number
  projectedY: number
  radius: number
  scores: Record<CapabilityDimension, number>
  selected: boolean
}

export interface JobConstellationGroup {
  key: string
  label: string
  color: string
  count: number
}

export interface JobConstellationEdge {
  id: string
  source: string
  target: string
  similarity: number
  groupKey: string
}

export interface JobConstellationSceneData {
  nodes: JobConstellationNode[]
  groups: JobConstellationGroup[]
  edges: JobConstellationEdge[]
  selectedId: string
  sourceKind: JobConstellationSourceKind
  resultLabel: string
  totalAvailable: number
  page: number
  pageSize: number
  transitionKey: string
  animationRevision: number
  summary: {
    resultCount: number
    regionCount: number
    minimumRequirement: number
    maximumRequirement: number
  }
}
