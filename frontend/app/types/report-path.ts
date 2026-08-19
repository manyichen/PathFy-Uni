import type { ReportEnrichmentState } from './report'

export type ReportPathNodeKind = 'origin' | 'plan' | 'review' | 'adjustment'
export type ReportPathAnimationKind = 'none' | 'build' | 'append'

export interface ReportPathNode {
  id: string
  kind: ReportPathNodeKind
  month: number
  label: string
  selected: boolean
  reviewId?: string
  linkedMonth?: number
  replanMode?: string
  progress?: number
  evidenceCount?: number
}

export interface ReportPathEdge {
  id: string
  sourceId: string
  targetId: string
  kind: 'sequence' | 'replan'
}

export interface ReportGrowthPoint {
  id: string
  month: number
  progress: number
  label: string
  kind: 'origin' | 'planned' | 'verified'
  selected: boolean
  evidenceCount?: number
  reviewId?: string
}

export interface ReportPathPhaseBand {
  id: string
  label: string
  startMonth: number
  endMonth: number
}

export type ReportGrowthDataState = 'unmeasured' | 'single_review' | 'tracked'

export interface ReportPathSceneData {
  reportId: number
  lineId: string
  title: string
  transitionKey: string
  animationRevision: number
  animationKind: ReportPathAnimationKind
  selectedMonth: number
  currentMonth: number
  nodes: ReportPathNode[]
  edges: ReportPathEdge[]
  actualPoints: ReportGrowthPoint[]
  plannedPoints: ReportGrowthPoint[]
  phases: ReportPathPhaseBand[]
  enrichment: {
    status: ReportEnrichmentState
    label: string
  }
  summary: {
    eventCount: number
    planCount: number
    reviewCount: number
    adjustmentCount: number
    actualPointCount: number
    plannedPointCount: number
    latestVerifiedMonth?: number
    latestVerifiedProgress?: number
    dataState: ReportGrowthDataState
  }
}
