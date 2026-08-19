import type { CapabilityScorePatch } from './capability'
import type { JobTarget } from './job'
import type { MatchGoal } from './match'

export interface TrackProfile {
  job_title?: string
  hiring_visibility_0_100?: number
  path_breadth_0_100?: number
  resource_density_0_100?: number
  [key: string]: unknown
}

export interface ReportTarget extends JobTarget {
  match_preview?: { match_score?: number; dimension_gaps?: CapabilityScorePatch; [key: string]: unknown }
  track_profile?: TrackProfile
}

export interface ReportHistoryItem {
  report_id: number
  title?: string
  resume_id?: number
  primary_job_id?: string
  target_job_ids?: string[]
  target_titles?: string[]
  created_at?: string
  updated_at?: string
}

export interface ReportReview {
  review_id: number
  review_cycle?: string
  scope?: 'target' | 'all'
  job_id?: string
  metrics?: Record<string, unknown>
  adjustment?: ReportAdjustmentSummary
  review_status?: ReportReviewStatus
  created_at?: string
}

export type ReportReviewCycle = 'weekly' | 'monthly'
export type ReportReviewStatus = 'on_track' | 'partial' | 'overloaded' | 'evidence_missing' | 'goal_changed' | 'data_insufficient' | 'stalled'
export type ReportCandidateDecision = 'pending' | 'confirm' | 'ignore'

export interface ReportReviewCandidate {
  code: string
  label: string
  target?: string
  value: number
  source_text: string
  source_type: 'review_text' | 'system_calculation' | 'user_input'
  origin: string
  confidence: number
  decision: ReportCandidateDecision
}

export interface ReportReviewDraft {
  draft_id: number
  report_id: number
  status: 'draft' | 'confirmed' | 'cancelled'
  review_cycle: ReportReviewCycle
  scope: 'target' | 'all'
  job_id?: string | null
  review_text: string
  summary?: string
  candidates: ReportReviewCandidate[]
  requires_confirmation: boolean
}

export interface ReportPlanChange {
  id: string
  kind: 'replace_target_plan' | 'replace_growth_plan' | 'append_adjustments'
  job_id?: string | null
  before: unknown
  after: unknown
  accepted: boolean
  summary?: {
    kept?: Array<{ title: string; deadline?: string; effort_hours?: number }>
    added?: Array<{ title: string; deadline?: string; effort_hours?: number }>
    removed?: Array<{ title: string; deadline?: string; effort_hours?: number }>
    before_month?: number
    after_month?: number
  }
}

export interface ReportPlanProposal {
  proposal_id: number
  status: 'proposed' | 'accepted' | 'rejected'
  changes: ReportPlanChange[]
  stale: boolean
}

export interface ReportReviewConfirmation {
  draft_id: number
  review_id: number
  report_id: number
  review_cycle: ReportReviewCycle
  review_status: ReportReviewStatus
  evaluation: ReportMetricEvaluation
  submitted_metrics: Record<string, number>
  plan_proposal?: ReportPlanProposal | null
}

export interface ReportPlanVersion extends ReportPlanProposal {
  review_id?: number | null
  scope: 'target' | 'all'
  job_id?: string | null
  base_report_version: number
  current_report_version: number
  decision?: { accepted_change_ids?: string[] }
  created_at?: string
  decided_at?: string | null
}

export interface ReportPlanAction { action_uid?: string; text?: string; kind?: string; done?: boolean; done_at?: string | null; deliverable?: string; deadline?: string; effort_hours?: number; acceptance_rule?: string; evidence_type?: string; user_created?: boolean; user_edited?: boolean; user_edited_fields?: string[]; [key: string]: unknown }
export interface ReportRecommendationRef { id?: string; label?: string; resource_id?: string; resource_name?: string; resource_type?: string; resource_url?: string; competition_id?: string; competition_name?: string; competition_type?: string; official_url?: string; url?: string; difficulty?: string; skill_tag?: string; award_level?: string; [key: string]: unknown }
export interface ReportRecommendationSet { learning_resources?: ReportRecommendationRef[]; competitions?: ReportRecommendationRef[]; [key: string]: unknown }
export interface ReportRecommendations { by_target?: Array<ReportRecommendationSet & { job_id?: string }>; [key: string]: unknown }
export interface ReportPlanItem { order?: number; period?: string; focus_dimension?: string; focus_label?: string; milestone?: string; learning_path?: string[]; practice_plan?: string[]; learning_path_refs?: ReportRecommendationRef[]; practice_plan_refs?: ReportRecommendationRef[]; custom_actions?: ReportPlanAction[]; [key: string]: unknown }
export interface ReportPlanPhase { label?: string; period?: string; summary?: string; line_one_liner?: string; items?: ReportPlanItem[]; [key: string]: unknown }
export interface ReportNextMonthPlan { phase_key?: string; phase_label?: string; plan_month?: number; review_anchor_month?: number; replan_mode?: string; updated_at?: string; items?: ReportPlanItem[]; [key: string]: unknown }
export interface ReportPlan { job_id: string; line_id?: string; display_title?: string; job_title_name?: string; match_score?: number; current_plan_month?: number; dimension_gaps?: CapabilityScorePatch; phases?: Record<string, ReportPlanPhase>; next_month_plan?: ReportNextMonthPlan; recommendations?: ReportRecommendationSet; narrative?: { path_advice?: string; [key: string]: unknown }; [key: string]: unknown }
export interface ReportActionCompletionSnapshot { done_count?: number; total_count?: number; completion_rate?: number | null; has_completed_actions?: boolean; plan_months?: number[]; by_target?: Array<{ job_id?: string; plan_month?: number; done_count?: number; total_count?: number; completion_rate?: number | null }>; [key: string]: unknown }
export interface ReportReviewDetail { review_text?: string; submitted?: Record<string, unknown>; llm_summary?: string; pass_rate?: number | null; all_passed?: boolean; cycle_score?: number; evidence_count?: number; action_completion?: ReportActionCompletionSnapshot; progress_basis?: string; [key: string]: unknown }
export interface DevelopmentLinePoint { month: number; progress?: number; label?: string; kind?: string; review_id?: number | string; detail?: ReportReviewDetail; [key: string]: unknown }
export interface DevelopmentLine { line_id?: string; line_name?: string; target_job_id?: string; timeline?: DevelopmentLinePoint[]; [key: string]: unknown }
export interface DevelopmentAdjustment { id?: string; line_id?: string; target_job_id?: string; month?: number; anchor_review_month?: number; plan_month?: number; progress?: number; label?: string; focus_label?: string; kind?: string; replan_mode?: string; execution_hints?: string[]; plan_items?: ReportPlanItem[]; failed_rows?: Array<Record<string, unknown>>; [key: string]: unknown }
export interface ReportAdjustmentSummary { all_passed?: boolean; pass_rate?: number; failed_codes?: string[]; replan_mode?: string; consecutive_fail_months?: number; auto_adjustment?: { triggered?: boolean; reason?: string; extra_actions?: string[]; focus_dimensions?: string[]; focus_labels?: string[]; replan_mode?: string; [key: string]: unknown }; [key: string]: unknown }
export interface ReportEvaluationMetric { code?: string; label?: string; cycle?: string; description?: string; target?: string; [key: string]: unknown }

export type ReportEvidenceGrade = 'A' | 'B' | 'C' | 'D'
export type ReportTargetRole = 'primary' | 'alternative' | 'observe'
export type ReportActionStatus = 'todo' | 'done' | 'blocked' | 'skipped'

export interface ReportDecisionFact {
  id: string
  label: string
  value: number | string | null
  unit?: string
  source_type: string
  source_label: string
  evidence_grade: ReportEvidenceGrade
  observed_at?: string
  verified?: boolean
}

export interface ReportDecisionQuality {
  grounded: boolean
  evidence_grade: ReportEvidenceGrade
  source_type: string
  freshness?: string
}

export interface ReportDecisionClaim {
  id: string
  kind: 'gap' | 'strength' | 'risk' | 'opportunity'
  dimension?: string
  title: string
  summary: string
  impact: string
  fact_refs: string[]
  facts: ReportDecisionFact[]
  priority?: number
  priority_factors?: Record<string, number>
  quality: ReportDecisionQuality
}

export interface ReportDecisionAction {
  id: string
  job_id: string
  item_index: number
  action_index: number
  title: string
  kind: 'learn' | 'practice' | 'deliverable'
  focus_dimension?: string
  focus_label?: string
  deliverable: string
  deadline: string
  effort_hours: number
  acceptance_criteria: string[]
  evidence_required: boolean
  evidence_grade_required: ReportEvidenceGrade
  evidence_type?: 'project' | 'certificate' | 'feedback' | 'event' | 'other'
  status: ReportActionStatus
  done?: boolean
  done_at?: string | null
  source_claim_ids: string[]
  source_fact_refs?: string[]
  resource_refs?: string[]
}

export interface ReportFreshnessItem {
  as_of?: string
  source_label: string
  evidence_grade: ReportEvidenceGrade
}

export interface ReportTargetDecision {
  job_id: string
  display_title: string
  company?: string
  role: ReportTargetRole
  role_label: string
  judgement: {
    recommendation: string
    match_score: number
    reasons: string[]
    risks: string[]
    data_gaps: string[]
  }
  claims: ReportDecisionClaim[]
  actions: ReportDecisionAction[]
  outcome_evidence?: Array<{
    id: string
    review_id?: number | null
    evidence_type: string
    label: string
    value?: string
    source_url?: string
    source_text?: string
    verification_status: string
    created_at?: string
  }>
  primary_action_id?: string | null
  evidence_metrics?: {
    coverage: number
    claim_grounding: number
    action_traceability: number
    fact_verification: number
    claim_count: number
    fact_count: number
    action_count: number
    unlinked_action_count: number
    outcome_evidence_count?: number
  }
  freshness: Record<string, ReportFreshnessItem>
}

export interface ReportTargetComparisonRow {
  job_id: string
  display_title: string
  role: ReportTargetRole
  role_label: string
  match_score: number
  top_gap: string
  primary_action: string
  evidence_coverage: number
}

export interface ReportDecisionSupport {
  schema_version: 2
  generated_at?: string
  updated_at?: string
  fact_model: string
  target_decisions: ReportTargetDecision[]
  target_comparison: ReportTargetComparisonRow[]
  shared_actions: Array<{ dimension: string; label: string; target_count: number; reason: string }>
  evidence_legend: Array<{ grade: ReportEvidenceGrade; label: string; objective: boolean }>
}

export type ReportEnrichmentQualityStatus = 'accepted' | 'repaired' | 'fallback'
export interface ReportEnrichmentQuality {
  status: ReportEnrichmentQualityStatus
  score: number
  initial_score: number
  repair_score?: number
  repair_attempts: number
  checked_at?: string
  fallback_reason?: string
  dimensions: Record<string, number>
  issues: Array<{ code: string; severity: 'warning' | 'error'; repairable: boolean; job_id?: string; path?: string; count?: number }>
  stats?: Record<string, number>
}

export interface ReportInputSnapshotMeta {
  schema_version: 1 | 2
  captured_at: string
  sha256: string
  constraints?: { primary_job_id?: string; target_job_ids?: string[]; match_goal?: string; [key: string]: unknown }
  revisions?: Record<string, unknown>
  [key: string]: unknown
}

export type ReportFreshnessStatus = 'fresh' | 'aging' | 'stale' | 'outdated' | 'unknown'
export interface ReportLongitudinalInsights {
  schema_version: 1
  generated_at: string
  freshness: {
    overall_status: 'fresh' | 'aging' | 'stale'
    stale_domains: string[]
    aging_domains: string[]
    domains: Record<string, { status: ReportFreshnessStatus; as_of?: string | null; age_days?: number | null; source_label: string; reason: string; refresh_action: string }>
  }
  execution_profile: {
    diagnosis: string
    diagnosis_label: string
    confidence: 'low' | 'medium' | 'high'
    evidence_points: number
    confirmed_review_count: number
    action_event_count: number
    current_action_count: number
    current_done_count: number
    current_completion_rate?: number | null
    review_status_distribution: Record<string, number>
  }
  trends: {
    review_series: Array<{ review_id: number; cycle?: string; status: string; pass_rate?: number | null; confirmed_metric_count: number; created_at?: string }>
    review_status_distribution: Record<string, number>
    goal_change_count: number
    proposal_count: number
    decided_proposal_count: number
    proposal_acceptance_rate?: number | null
    partial_accept_count: number
    average_accepted_changes: number
    plan_stability: number
  }
  personalization: {
    enabled: boolean
    experiment: { key: string; variant: string }
    recommendation_active: boolean
    suggested_weekly_action_limit: number
    suggested_weekly_hours: number
    focus: string
    confidence: 'low' | 'medium' | 'high'
    learned_from: { confirmed_reviews: number; action_events: number; decided_proposals: number; excluded: string[] }
    explanation: string
  }
  reminders: Array<{ kind: string; severity: 'info' | 'warning'; label: string; due_at?: string | null; days?: number | null }>
  privacy: { learning_boundary: string; unconfirmed_draft_retention_days: number; confirmed_history_retention: string; exportable: boolean; deletable: boolean }
}

export interface ReportMetricEvaluation { pass_rate?: number | null; all_passed?: boolean; has_evidence?: boolean; evidence_complete?: boolean; evaluated_count?: number; missing_count?: number; rows?: Array<Record<string, unknown>>; [key: string]: unknown }

export interface CareerReport {
  generated_at?: string
  llm_enrich_pending?: boolean
  summary?: string
  overview?: string
  narrative?: { text?: string; [key: string]: unknown }
  targets?: ReportTarget[]
  development_lines?: { axis?: { x_min?: number; x_max?: number; y_min?: number; y_max?: number; [key: string]: unknown }; lines?: DevelopmentLine[]; adjustments?: DevelopmentAdjustment[]; [key: string]: unknown }
  plans_by_target?: ReportPlan[]
  recommendations?: ReportRecommendations
  evaluation?: { metrics?: ReportEvaluationMetric[]; latest_review?: { review_id?: number; review_text?: string; scope?: 'target' | 'all'; job_id?: string; submitted_metrics?: Record<string, unknown>; evaluation?: ReportMetricEvaluation; adjustment?: ReportAdjustmentSummary; llm_extract?: { summary?: string; [key: string]: unknown }; created_at?: string; [key: string]: unknown }; latest_reviews_by_target?: Record<string, Record<string, unknown>>; latest_adjustment_actions?: string[]; last_replan_mode?: string; consecutive_fail_months?: number; consecutive_fail_months_by_scope?: Record<string, number>; [key: string]: unknown }
  decision_support?: ReportDecisionSupport
  input_snapshot?: ReportInputSnapshotMeta
  enrichment_quality?: ReportEnrichmentQuality
  enrichment?: { completed_at?: string; quality_status?: ReportEnrichmentQualityStatus; quality_score?: number; input_snapshot_sha256?: string; [key: string]: unknown }
  longitudinal_insights?: ReportLongitudinalInsights
  preference_strategy?: ReportPreferenceStrategy
  [key: string]: unknown
}

export interface ReportPreferenceStrategySection {
  code: string
  title: string
  recommendation: string
  alternative: string
  rationale: string
  user_edited?: boolean
  source?: { axis_code?: string; value?: number; preference_strength?: number }
}

export interface ReportPreferenceStrategy {
  status: 'missing' | 'suggested' | 'accepted' | 'edited'
  version: string
  personality_profile_id?: number
  mbti_type?: string
  sections: ReportPreferenceStrategySection[]
  influences_capability: false
  disclaimer: string
  calibration?: {
    status: 'insufficient_cycles' | 'stable' | 'review_recommended'
    completed_cycles: number
    required_cycles: number
    message?: string
    candidate_axes?: Array<{ axis_code: string; signal_code: string; direction: 'lower' | 'higher'; ratings: number[] }>
  }
}

export interface ReportImportFromMatchResponse { run_id: number; resume_id: number; match_goal?: MatchGoal | string; source?: string; targets: ReportTarget[] }
export interface ReportGenerateResponse { report_id: number; title?: string; primary_job_id?: string; target_job_ids?: string[]; report: CareerReport; llm_enrich_pending?: boolean }
export interface ReportDetailResponse extends ReportGenerateResponse { resume_id?: number; created_at?: string; updated_at?: string; configuration?: Record<string, unknown> }
export type ReportEnrichmentState = 'pending' | 'queued' | 'running' | 'completed' | 'failed'
export type ReportRefreshScope = 'full' | 'narrative' | 'resources' | 'plan'
export interface ReportEnrichmentStatus {
  report_id: number
  status: ReportEnrichmentState
  attempt?: number
  requested_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  error?: string
  timing_ms?: Record<string, number>
  stage?: string
  progress?: number
  quality?: ReportEnrichmentQuality
  scope?: ReportRefreshScope
}

export type ReportPdfActionScope = 'all' | 'todo' | 'done'

export interface ReportPdfExportSections {
  overview: boolean
  actions: boolean
  evidence: boolean
  route: boolean
  review: boolean
  resources: boolean
  preference: boolean
}

export interface ReportPdfExportOptions {
  document_title: string
  executive_summary: string
  closing_note: string
  selected_target_job_ids: string[]
  sections: ReportPdfExportSections
  action_scope: ReportPdfActionScope
  show_source_details: boolean
  show_resource_links: boolean
}

export interface ReportHistoryResponse { items: ReportHistoryItem[] }
export interface ReportReviewsResponse { items: ReportReview[] }
export interface PublicInfoSource { title?: string; url?: string; [key: string]: unknown }
export interface PublicInfoResponse { summary?: string; sources?: PublicInfoSource[]; [key: string]: unknown }
export interface PublicInfoState { loading?: boolean; error?: string; data?: PublicInfoResponse }
