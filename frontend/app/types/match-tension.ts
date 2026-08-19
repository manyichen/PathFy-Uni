import type { CapabilityDimension } from './capability'

export type MatchTensionStatus = 'deficit' | 'balanced' | 'surplus'

export interface MatchTensionDimension {
  id: CapabilityDimension
  label: string
  studentScore: number
  requirementScore: number
  gap: number
  intensity: number
  status: MatchTensionStatus
}

export interface MatchTensionSceneData {
  jobId: string
  jobTitle: string
  transitionKey: string
  animationRevision: number
  dimensions: MatchTensionDimension[]
  summary: {
    deficitCount: number
    balancedCount: number
    surplusCount: number
    averageAbsoluteGap: number
    largestDeficit?: MatchTensionDimension
  }
}
