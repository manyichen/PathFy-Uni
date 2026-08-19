import type { CapabilityDimension } from './capability'

export type ProfileEvidenceMappingMode = 'explicit' | 'overview'

export interface ProfileEvidenceMaterialNode {
  id: string
  name: string
  kind: string
  status: string
  chars: number
  weight: number
}

export interface ProfileEvidenceDimensionNode {
  id: CapabilityDimension
  label: string
  score: number
}

export interface ProfileEvidenceFlow {
  id: string
  materialId: string
  dimension: CapabilityDimension
  weight: number
  confidence?: number
  excerpt?: string
  inferred: boolean
}

export interface ProfileEvidenceSceneData {
  materials: ProfileEvidenceMaterialNode[]
  dimensions: ProfileEvidenceDimensionNode[]
  flows: ProfileEvidenceFlow[]
  mappingMode: ProfileEvidenceMappingMode
  animationRevision: number
  summary: {
    materialCount: number
    dimensionCount: number
    explicitFlowCount: number
  }
}
