import type { JobCard } from './job'

export type CareerGraphNodeKind = 'current' | 'promotion' | 'lateral' | 'target'
export type CareerGraphEdgeKind = 'promotion' | 'lateral' | 'transition'

export interface CareerGraphNode {
  id: string
  title: string
  kind: CareerGraphNodeKind
  depth: number
  routeIndex: number
  score?: number
  description?: string
}

export interface CareerGraphEdge {
  id: string
  source: string
  target: string
  kind: CareerGraphEdgeKind
  confidence?: number
  description?: string
}

export interface CareerGraphData {
  nodes: CareerGraphNode[]
  edges: CareerGraphEdge[]
  currentNodeId: string
  targetNodeId?: string
  selectedNodeId?: string
  summary: {
    promotionCount: number
    lateralCount: number
    hasTransition: boolean
  }
}

export interface CareerJobReference {
  id?: string
  title?: string
  company?: string
  location?: string
  salary?: string
  [key: string]: unknown
}

export interface CareerPromotionStage {
  stage?: number
  label?: string
  role?: string
  period?: string
  milestone?: string
  actions?: string[]
  [key: string]: unknown
}

export interface CareerPromotionRoute {
  id?: string
  job_title?: string
  route_title?: string
  route_text?: string
  target_title?: string
  confidence?: number
  rationale?: string
  stages?: CareerPromotionStage[]
  nodes?: CareerJobReference[]
  [key: string]: unknown
}

export interface CareerPromotionResponse {
  job?: CareerJobReference
  routes?: CareerPromotionRoute[]
  paths?: Array<{ nodes?: CareerJobReference[]; [key: string]: unknown }>
  [key: string]: unknown
}

export interface CareerLateralRoute {
  id?: string
  from_title?: string
  target_title?: string
  score?: number
  cap_similarity?: number
  rationale?: string
  [key: string]: unknown
}

export interface CareerLateralResponse {
  job?: CareerJobReference
  job_title?: string
  routes?: CareerLateralRoute[]
  [key: string]: unknown
}

export interface CareerTransitionResponse {
  from_job?: CareerJobReference
  to_job?: CareerJobReference
  analysis?: Record<string, unknown>
  advice?: Record<string, unknown>
  [key: string]: unknown
}

export interface CareerGraphSource {
  currentJob?: Pick<JobCard, 'id' | 'title' | 'company' | 'location'> | CareerJobReference
  targetJob?: Pick<JobCard, 'id' | 'title' | 'company' | 'location'> | CareerJobReference
  promotion?: CareerPromotionResponse
  lateral?: CareerLateralResponse
  transition?: CareerTransitionResponse
}
