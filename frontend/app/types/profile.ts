import type { CapabilityScorePatch } from './capability'

export interface ResumeOption {
  id: number
  name?: string
  major?: string
  education?: string
  created_at?: string
  create_time?: string
  scores?: CapabilityScorePatch
  completeness?: number
  competitiveness?: number
  score_avg?: number
  [key: string]: unknown
}

export interface ProfileMaterial {
  name?: string
  kind?: string
  status?: string
  chars?: number
  [key: string]: unknown
}

export interface ProfileDimensionAnalysis {
  dimension?: string
  name?: string
  label?: string
  score?: number
  value?: number
  level?: string
  stage?: string
  rank?: number
  average_score?: number
  relative_to_average?: number
  interpretation?: string
  analysis?: string
  description?: string
  judgement?: string
  development_gap?: string
  evidence_clues?: string[]
  next_actions?: string[]
  expected_evidence?: string
  success_metric?: string
  [key: string]: unknown
}

export interface ProfileEvidenceContributionRecord {
  material_id?: string
  materialId?: string
  material_name?: string
  materialName?: string
  dimension?: string
  capability_dimension?: string
  capabilityDimension?: string
  weight?: number
  contribution?: number
  score?: number
  confidence?: number
  excerpt?: string
  [key: string]: unknown
}

export interface ProfileAnalysis {
  overall_evaluation?: string
  completeness_analysis?: string
  competitiveness_analysis?: string
  material_summary?: ProfileMaterial[]
  capability_evidence_contributions?: ProfileEvidenceContributionRecord[]
  evidence_contributions?: ProfileEvidenceContributionRecord[]
  material_contributions?: ProfileEvidenceContributionRecord[]
  advantage_dimensions?: ProfileDimensionAnalysis[]
  weakness_dimensions?: ProfileDimensionAnalysis[]
  short_term_plan?: Array<string | Record<string, unknown>>
  long_term_goals?: Array<string | Record<string, unknown>>
  dimension_analysis?: ProfileDimensionAnalysis[]
  industry_match?: Array<string | Record<string, unknown>>
  material_keywords?: Array<string | Record<string, unknown>>
  [key: string]: unknown
}

export interface ProfileDetail extends ResumeOption {
  resume_id?: number
  detailed_analysis?: ProfileAnalysis
  materials?: ProfileMaterial[]
}
