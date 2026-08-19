import type { PersonalityDimensionCode } from './personality'

export type PersonalityFingerprintMode = 'measured' | 'signature'

export interface PersonalityFingerprintAxis {
  code: PersonalityDimensionCode
  label: string
  left: string
  right: string
  leftScore: number
  rightScore: number
  dominant: string
  confidence: number
  measured: boolean
}

export interface PersonalityFingerprintSceneData {
  mbti: string
  mode: PersonalityFingerprintMode
  seed: number
  signatureId: string
  animationRevision: number
  axes: PersonalityFingerprintAxis[]
  traits: {
    energyDirection: number
    exploration: number
    decisionEdge: number
    structure: number
  }
}
