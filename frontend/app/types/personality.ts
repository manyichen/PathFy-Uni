export interface PersonalityQuestion {
  id: number
  question_text: string
  option_a: string
  option_b: string
  [key: string]: unknown
}

export interface PersonalityAnswer {
  question_id: number
  user_choice: 'A' | 'B'
}

export interface PersonalityAnalysis {
  type?: string
  name?: string
  summary?: string
  core_strengths?: string[]
  career_tendencies?: string[]
  workplace_relationships?: string[]
  development_areas?: string[]
  stress_response?: string
  [key: string]: unknown
}

export interface PersonalityDimensionAnalysis {
  dimension?: string
  type?: string
  name?: string
  description?: string
  characteristics?: string[]
  work_preference?: string[]
  growth_suggestions?: string[]
  [key: string]: unknown
}

export type PersonalityDimensionCode = 'EI' | 'SN' | 'TF' | 'JP'

export interface PersonalityDimensionScore {
  code: PersonalityDimensionCode
  label?: string
  left: string
  right: string
  left_count?: number
  right_count?: number
  left_score: number
  right_score: number
  dominant?: string
  confidence?: number
  preference_strength?: number
  borderline?: boolean
}

export type PersonalityPreferenceAxisCode =
  | 'interaction_intensity'
  | 'abstraction_preference'
  | 'analytical_decision'
  | 'structure_preference'

export interface PersonalityPreferenceAxis {
  code: PersonalityPreferenceAxisCode
  source_dimension?: PersonalityDimensionCode
  value: number
  preference_strength?: number
  measurement_quality?: number
  low_label?: string
  high_label?: string
}

export interface PersonalityResult {
  profile_id?: number
  mbti_type?: string
  personality_analysis?: string
  complete_analysis?: PersonalityAnalysis
  dimension_analysis?: PersonalityDimensionAnalysis[]
  dimension_scores?: PersonalityDimensionScore[]
  preference_axes?: PersonalityPreferenceAxis[]
  detailed_analysis?: {
    dimension_analysis?: PersonalityDimensionAnalysis[]
    dimension_scores?: PersonalityDimensionScore[]
    preference_axes?: PersonalityPreferenceAxis[]
    complete_analysis?: PersonalityAnalysis
    job_recommendations?: { recommended_jobs?: string[]; career_advice?: string; [key: string]: unknown }
    [key: string]: unknown
  }
  recommended_jobs?: string[]
  job_recommendations?: { recommended_jobs?: string[]; career_advice?: string; [key: string]: unknown }
  status?: 'measured' | 'legacy' | 'missing'
  result_status?: string
  question_set_version?: string
  scoring_version?: string
  answer_signature?: string
  is_active?: boolean
  personalization_enabled?: boolean
  completed_at?: string
  created_at?: string
  [key: string]: unknown
}
