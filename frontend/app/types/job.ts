import type { CapabilityScorePatch, CapabilityScores } from './capability'

export interface WorkstyleEvidence {
  text: string
  source?: string
}

export interface JobWorkstyleAxis {
  code: 'interaction_intensity' | 'abstraction_preference' | 'analytical_decision' | 'structure_preference' | string
  value: number
  confidence: number
  low_label: string
  high_label: string
  evidence: WorkstyleEvidence[]
  source?: string
  inherited_from_job_title?: boolean
}

export interface JobWorkstyleProfile {
  status: 'available' | 'insufficient_evidence'
  axes: JobWorkstyleAxis[]
  axis_count: number
  evidenced_axis_count: number
  inherited_from_job_title?: boolean
  scoring_version?: string
  snapshot_version?: string
  updated_at?: string
}

export interface JobCard {
  id: string
  title: string
  company: string
  location: string
  salary: string
  scores: CapabilityScores
  score_avg?: number
  conf_avg?: number
  workstyle?: JobWorkstyleProfile
  [key: string]: unknown
}

export interface JobDetail extends JobCard {
  industry?: string
  company_type?: string
  company_size?: string
  company_detail?: string
  demand?: string
  experience_text?: string
  experience_years?: number
  internship_req?: string
  updated_date?: string
  source_url?: string
  requirements?: Array<{ name: string; label?: string; level?: string }>
  cap_evidence?: string[]
}

export interface JobTarget {
  id?: string
  job_id?: string
  title?: string
  display_title?: string
  company?: string
  location?: string
  salary?: string
  score_avg?: number
  source?: string
  scores?: CapabilityScorePatch
  [key: string]: unknown
}

export interface JobOption extends JobTarget {
  id: string
  title: string
}

export interface JobListResult {
  jobs: JobCard[]
  total: number
  page: number
  page_size: number
  total_pages: number
  seed?: string
}

export interface JobAssistantMessage {
  id?: number
  role: 'user' | 'assistant' | string
  content: string
  error?: boolean
  is_saved?: boolean
  created_at?: string
  result_job_ids_json?: string[]
  [key: string]: unknown
}

export interface JobAssistantSession {
  id: number
  title?: string
  created_at?: string
  updated_at?: string
  last_message_at?: string
  [key: string]: unknown
}

export interface JobAssistantResponse {
  session_id?: number
  assistant_message?: JobAssistantMessage
  user_message?: JobAssistantMessage
  reply?: string
  message?: string
  jobs?: JobCard[]
  messages?: JobAssistantMessage[]
  session?: JobAssistantSession
  filters?: Record<string, unknown>
  [key: string]: unknown
}
