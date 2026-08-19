import type { CapabilityScorePatch } from './capability'
import type { JobCard } from './job'

export type MatchGoal = 'fit' | 'stretch'
export type PreferenceMode = 'off' | 'explain' | 'tie_break'

export type PreferenceFitStatus =
  | 'not_enabled'
  | 'missing_user_profile'
  | 'personalization_disabled'
  | 'legacy_user_profile'
  | 'insufficient_job_evidence'
  | 'available'

export interface MatchPreferenceFit {
  status: PreferenceFitStatus
  score?: number
  confidence?: number
  confidence_level?: 'medium' | 'high'
  evidenced_axes?: number
  required_axes?: number
  axes?: Array<{
    code: string
    user_value: number
    job_value: number
    preference_strength: number
    fit: number
    confidence: number
    evidence: Array<{ text: string; source?: string }>
    source?: string
    inherited_from_job_title?: boolean
    explanation: string
  }>
  influenced_ranking: boolean
  algorithm_version?: string
}

export interface MatchPreferenceContext {
  mode: PreferenceMode
  status: 'off' | 'missing' | 'legacy' | 'disabled' | 'invalid' | 'measured'
  personality_profile_id?: number
  mbti_type?: string
  completed_at?: string
  personalization_enabled?: boolean
  influenced_ranking: boolean
  algorithm_version?: string
  workstyle_snapshot_version?: string
  minimum_evidenced_axes?: number
  minimum_fit_confidence?: number
  jobs_with_workstyle_evidence?: number
  jobs_with_preference_fit?: number
  workstyle_coverage?: number
  tie_break?: {
    requested: boolean; eligible: boolean; applied: boolean; reason: string; system_enabled: boolean
    minimum_coverage: number; max_ability_gap: number; experiment_key: string
    experiment_variant: 'tie_break' | 'control' | string; experiment_bucket: number; ranking_version: string
    original_ability_order: string[]; preference_order: string[]
    changes: Array<{ job_id: string; ability_rank: number; preference_rank: number }>; changed_jobs: number
  }
}

export interface MatchPreview {
  match_score?: number
  dimension_gaps?: CapabilityScorePatch
  preference_fit?: MatchPreferenceFit
  ability_rank?: number
  preference_rank?: number
  [key: string]: unknown
}

export interface MatchCandidate {
  id?: string
  job: JobCard
  match_score: number
  reason?: string
  explanation?: string
  match_preview?: MatchPreview
  [key: string]: unknown
}

export interface MatchRecommendation {
  job_id: string
  rank: number
  overall_fit_0_100: number
  one_line?: string
  strengths: string[]
  gaps: string[]
  risks: string[]
  llm_fallback?: boolean
  job: JobCard
}

export interface MatchLlmResult {
  ok: boolean
  error?: string
  error_code?: 'timeout' | 'rate_limit' | 'authentication' | 'quota' | 'network' | 'invalid_response' | 'bad_request' | 'not_configured' | 'unknown'
  model?: string
  pool_size?: number
  retry_attempted?: boolean
  degraded?: boolean
  fallback_reason?: string
  fallback_mode?: 'local' | string
  notice?: string
  initial_pool_size?: number
  fallback_pool_size?: number
  top5: MatchRecommendation[]
}

export interface MatchPreviewResult {
  student: { scores: CapabilityScorePatch; [key: string]: unknown }
  jobs: MatchCandidate[]
  filters?: { q?: string; location_q?: string; match_goal?: MatchGoal | string }
  stats?: { scanned?: number; returned?: number; [key: string]: unknown }
  llm?: MatchLlmResult
  snapshot_warning?: string
  run_id?: number
  resume_id?: number
  created_at?: string
  preference_context?: MatchPreferenceContext
  [key: string]: unknown
}

export interface MatchHistoryItem {
  run_id: number
  resume_id?: number
  student_name?: string
  match_goal?: MatchGoal | string
  q?: string
  location_q?: string
  refine_with_llm?: boolean
  llm_ok?: boolean
  returned?: number
  created_at?: string
  preference_mode?: PreferenceMode
  personality_profile_id?: number
  preference_status?: string
  preference_experiment_variant?: string
  [key: string]: unknown
}

export interface MatchHistoryResponse {
  items: MatchHistoryItem[]
}

export interface MatchRunRequest {
  resume_id: number
  q?: string
  location_q?: string
  match_goal: MatchGoal
  refine_with_llm: boolean
  persist_snapshot?: boolean
  personality_profile_id?: number
  preference_mode?: PreferenceMode
}
