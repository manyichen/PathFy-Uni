import { z } from 'zod'
import type {
  PublicInfoResponse,
  ReportDetailResponse,
  ReportEnrichmentStatus,
  ReportGenerateResponse,
  ReportHistoryItem,
  ReportImportFromMatchResponse,
  ReportPlanVersion,
  ReportPdfExportOptions,
  ReportRefreshScope,
  ReportReview,
  ReportReviewConfirmation,
  ReportReviewDraft,
  ReportTarget
} from '~/types/report'
import { asArray, asNumber, asRecord, asString } from '~/utils/normalizers'

const scoreMapSchema = z.record(z.string(), z.coerce.number())
const reportActionSchema = z.object({
  action_uid: z.string().optional(), text: z.string().optional(), kind: z.string().optional(), done: z.boolean().optional(), done_at: z.string().nullable().optional(),
  deliverable: z.string().optional(), deadline: z.string().optional(), effort_hours: z.coerce.number().optional(), acceptance_rule: z.string().optional(),
  user_created: z.boolean().optional(), user_edited: z.boolean().optional(), user_edited_fields: z.array(z.string()).optional()
}).passthrough()
const reportPlanItemSchema = z.object({
  focus_dimension: z.string().optional(), focus_label: z.string().optional(), milestone: z.string().optional(),
  custom_actions: z.array(reportActionSchema).optional(), learning_path_refs: z.array(z.object({}).passthrough()).optional(),
  practice_plan_refs: z.array(z.object({}).passthrough()).optional()
}).passthrough()
const reportPlanSchema = z.object({
  job_id: z.string(), display_title: z.string().optional(), match_score: z.coerce.number().optional(),
  dimension_gaps: scoreMapSchema.optional(),
  next_month_plan: z.object({ plan_month: z.coerce.number().optional(), phase_label: z.string().optional(), replan_mode: z.string().optional(), items: z.array(reportPlanItemSchema).optional() }).passthrough().optional(),
  phases: z.record(z.string(), z.object({ items: z.array(reportPlanItemSchema).optional() }).passthrough()).optional()
}).passthrough()
const reportTargetSchema = z.object({
  id: z.string().optional(), job_id: z.string().optional(), title: z.string().optional(), display_title: z.string().optional(),
  company: z.string().optional(), location: z.string().optional(),
  match_preview: z.object({ match_score: z.coerce.number().optional(), dimension_gaps: scoreMapSchema.optional(), student_scores: scoreMapSchema.optional(), job_requirement_scores: scoreMapSchema.optional() }).passthrough().optional()
}).passthrough()
const decisionFactSchema = z.object({
  id: z.string(), label: z.string(), value: z.union([z.number(), z.string(), z.null()]), unit: z.string().optional(),
  source_type: z.string(), source_label: z.string(), evidence_grade: z.enum(['A', 'B', 'C', 'D']),
  observed_at: z.string().optional(), verified: z.boolean().optional()
})
const decisionClaimSchema = z.object({
  id: z.string(), kind: z.enum(['gap', 'strength', 'risk', 'opportunity']), dimension: z.string().optional(),
  title: z.string(), summary: z.string(), impact: z.string(), fact_refs: z.array(z.string()), facts: z.array(decisionFactSchema),
  priority: z.coerce.number().optional(), priority_factors: z.record(z.string(), z.coerce.number()).optional(),
  quality: z.object({ grounded: z.boolean(), evidence_grade: z.enum(['A', 'B', 'C', 'D']), source_type: z.string(), freshness: z.string().optional() })
})
const decisionActionSchema = z.object({
  id: z.string(), job_id: z.string(), item_index: z.coerce.number(), action_index: z.coerce.number(), title: z.string(),
  kind: z.enum(['learn', 'practice', 'deliverable']), focus_dimension: z.string().optional(), focus_label: z.string().optional(),
  deliverable: z.string(), deadline: z.string(), effort_hours: z.coerce.number(), acceptance_criteria: z.array(z.string()),
  evidence_required: z.boolean(), evidence_grade_required: z.enum(['A', 'B', 'C', 'D']),
  evidence_type: z.enum(['project', 'certificate', 'feedback', 'event', 'other']).optional(),
  status: z.enum(['todo', 'done', 'blocked', 'skipped']), done: z.boolean().optional(), done_at: z.string().nullable().optional(), source_claim_ids: z.array(z.string()),
  source_fact_refs: z.array(z.string()).optional(), resource_refs: z.array(z.string()).optional()
})
const freshnessSchema = z.record(z.string(), z.object({ as_of: z.string().optional(), source_label: z.string(), evidence_grade: z.enum(['A', 'B', 'C', 'D']) }))
const enrichmentQualitySchema = z.object({
  status: z.enum(['accepted', 'repaired', 'fallback']), score: z.coerce.number(), initial_score: z.coerce.number(),
  repair_score: z.coerce.number().optional(), repair_attempts: z.coerce.number(), checked_at: z.string().optional(), fallback_reason: z.string().optional(),
  dimensions: z.record(z.string(), z.coerce.number()),
  issues: z.array(z.object({ code: z.string(), severity: z.enum(['warning', 'error']), repairable: z.boolean(), job_id: z.string().optional(), path: z.string().optional(), count: z.coerce.number().optional() })),
  stats: z.record(z.string(), z.coerce.number()).optional()
})
export const reportDecisionSupportSchema = z.object({
  schema_version: z.literal(2), generated_at: z.string().optional(), updated_at: z.string().optional(), fact_model: z.string(),
  target_decisions: z.array(z.object({
    job_id: z.string(), display_title: z.string(), company: z.string().optional(), role: z.enum(['primary', 'alternative', 'observe']), role_label: z.string(),
    judgement: z.object({ recommendation: z.string(), match_score: z.coerce.number(), reasons: z.array(z.string()), risks: z.array(z.string()), data_gaps: z.array(z.string()) }),
    claims: z.array(decisionClaimSchema), actions: z.array(decisionActionSchema),
    outcome_evidence: z.array(z.object({ id: z.string(), review_id: z.coerce.number().nullable().optional(), evidence_type: z.string(), label: z.string(), value: z.string().optional(), source_url: z.string().optional(), source_text: z.string().optional(), verification_status: z.string(), created_at: z.string().optional() })).optional(),
    primary_action_id: z.string().nullable().optional(),
    evidence_metrics: z.object({
      coverage: z.coerce.number(), claim_grounding: z.coerce.number(), action_traceability: z.coerce.number(), fact_verification: z.coerce.number(),
      claim_count: z.coerce.number(), fact_count: z.coerce.number(), action_count: z.coerce.number(), unlinked_action_count: z.coerce.number(), outcome_evidence_count: z.coerce.number().optional()
    }).optional(), freshness: freshnessSchema
  })),
  target_comparison: z.array(z.object({
    job_id: z.string(), display_title: z.string(), role: z.enum(['primary', 'alternative', 'observe']), role_label: z.string(),
    match_score: z.coerce.number(), top_gap: z.string(), primary_action: z.string(), evidence_coverage: z.coerce.number()
  })),
  shared_actions: z.array(z.object({ dimension: z.string(), label: z.string(), target_count: z.coerce.number(), reason: z.string() })),
  evidence_legend: z.array(z.object({ grade: z.enum(['A', 'B', 'C', 'D']), label: z.string(), objective: z.boolean() }))
})
const reportLongitudinalInsightsSchema = z.object({
  schema_version: z.literal(1),
  generated_at: z.string(),
  freshness: z.object({
    overall_status: z.enum(['fresh', 'aging', 'stale']),
    stale_domains: z.array(z.string()),
    aging_domains: z.array(z.string()),
    domains: z.record(z.string(), z.object({
      status: z.enum(['fresh', 'aging', 'stale', 'outdated', 'unknown']),
      as_of: z.string().nullable().optional(),
      age_days: z.coerce.number().nullable().optional(),
      source_label: z.string(),
      reason: z.string(),
      refresh_action: z.string()
    }))
  }),
  execution_profile: z.object({
    diagnosis: z.string(), diagnosis_label: z.string(), confidence: z.enum(['low', 'medium', 'high']),
    evidence_points: z.coerce.number(), confirmed_review_count: z.coerce.number(), action_event_count: z.coerce.number(),
    current_action_count: z.coerce.number(), current_done_count: z.coerce.number(), current_completion_rate: z.coerce.number().nullable().optional(),
    review_status_distribution: z.record(z.string(), z.coerce.number())
  }).passthrough(),
  trends: z.object({
    review_series: z.array(z.object({
      review_id: z.coerce.number(), cycle: z.string().optional(), status: z.string(),
      pass_rate: z.coerce.number().nullable().optional(), confirmed_metric_count: z.coerce.number(), created_at: z.string().optional()
    })),
    review_status_distribution: z.record(z.string(), z.coerce.number()),
    goal_change_count: z.coerce.number(), proposal_count: z.coerce.number(), decided_proposal_count: z.coerce.number(),
    proposal_acceptance_rate: z.coerce.number().nullable().optional(), partial_accept_count: z.coerce.number(),
    average_accepted_changes: z.coerce.number(), plan_stability: z.coerce.number()
  }),
  personalization: z.object({
    enabled: z.boolean(), experiment: z.object({ key: z.string(), variant: z.string() }), recommendation_active: z.boolean(),
    suggested_weekly_action_limit: z.coerce.number(), suggested_weekly_hours: z.coerce.number(), focus: z.string(),
    confidence: z.enum(['low', 'medium', 'high']),
    learned_from: z.object({ confirmed_reviews: z.coerce.number(), action_events: z.coerce.number(), decided_proposals: z.coerce.number(), excluded: z.array(z.string()) }),
    explanation: z.string()
  }),
  reminders: z.array(z.object({ kind: z.string(), severity: z.enum(['info', 'warning']), label: z.string(), due_at: z.string().nullable().optional(), days: z.coerce.number().nullable().optional() })),
  privacy: z.object({ learning_boundary: z.string(), unconfirmed_draft_retention_days: z.coerce.number(), confirmed_history_retention: z.string(), exportable: z.boolean(), deletable: z.boolean() })
})
export const careerReportSchema = z.object({
  generated_at: z.string().optional(), llm_enrich_pending: z.boolean().optional(), summary: z.string().optional(), overview: z.string().optional(),
  targets: z.array(reportTargetSchema).optional(), plans_by_target: z.array(reportPlanSchema).optional(),
  development_lines: z.object({ lines: z.array(z.object({}).passthrough()).optional(), adjustments: z.array(z.object({}).passthrough()).optional() }).passthrough().optional(),
  evaluation: z.object({ metrics: z.array(z.object({ code: z.string().optional(), label: z.string().optional(), target: z.string().optional() }).passthrough()).optional(), latest_review: z.object({}).passthrough().optional(), last_replan_mode: z.string().optional() }).passthrough().optional(),
  decision_support: reportDecisionSupportSchema.optional(),
  input_snapshot: z.object({ schema_version: z.union([z.literal(1), z.literal(2)]), captured_at: z.string(), sha256: z.string().length(64), constraints: z.object({}).passthrough().optional(), revisions: z.record(z.string(), z.unknown()).optional() }).passthrough().optional(),
  enrichment_quality: enrichmentQualitySchema.optional(),
  enrichment: z.object({ completed_at: z.string().optional(), quality_status: z.enum(['accepted', 'repaired', 'fallback']).optional(), quality_score: z.coerce.number().optional(), input_snapshot_sha256: z.string().optional() }).passthrough().optional(),
  longitudinal_insights: reportLongitudinalInsightsSchema.optional()
}).passthrough()
const reportSchema = z.object({ report_id: z.coerce.number(), report: careerReportSchema }).passthrough()
const itemListSchema = z.object({ items: z.array(z.unknown()).default([]) }).passthrough()
const enrichmentStates = ['pending', 'queued', 'running', 'completed', 'failed'] as const

function normalizeTarget(value: unknown): ReportTarget {
  const row = asRecord(value)
  return {
    ...row,
    id: asString(row.id || row.job_id) || undefined,
    job_id: asString(row.job_id || row.id) || undefined,
    title: asString(row.title || row.display_title) || undefined,
    display_title: asString(row.display_title || row.title) || undefined,
    company: asString(row.company) || undefined,
    location: asString(row.location) || undefined
  }
}

function normalizeEnrichment(value: unknown): ReportEnrichmentStatus {
  const row = asRecord(value)
  const status = asString(row.status)
  if (!enrichmentStates.includes(status as ReportEnrichmentStatus['status'])) throw new Error('AI 增强状态无效')
  return { ...row, report_id: asNumber(row.report_id), status } as ReportEnrichmentStatus
}

function normalizeReportResponse(value: unknown): ReportGenerateResponse {
  const parsed = reportSchema.safeParse(value)
  if (!parsed.success) {
    console.error('career_report_contract_invalid', parsed.error.issues)
    throw new Error('报告已生成，但返回数据格式暂不兼容，请刷新后重试')
  }
  const row = parsed.data
  const report = row.report as ReportGenerateResponse['report']
  return {
    ...row,
    report_id: row.report_id,
    title: asString(row.title) || undefined,
    primary_job_id: asString(row.primary_job_id) || undefined,
    target_job_ids: asArray(row.target_job_ids).map(item => asString(item)).filter(Boolean),
    report,
    llm_enrich_pending: row.llm_enrich_pending === undefined
      ? report.llm_enrich_pending === true
      : row.llm_enrich_pending !== false
  }
}

export function useReportApi() {
  const api = useApi()

  const importFromMatch = async (runId: number, limit = 5): Promise<ReportImportFromMatchResponse> => {
    const row = asRecord(await api.ok<unknown>('/api/report/targets/import-from-match', { method: 'POST', body: { run_id: runId, limit } }))
    return { run_id: asNumber(row.run_id), resume_id: asNumber(row.resume_id), match_goal: asString(row.match_goal) || undefined, source: asString(row.source) || undefined, targets: asArray(row.targets).map(normalizeTarget) }
  }

  const generate = async (body: { resume_id: number; target_job_ids: string[]; primary_job_id: string; match_goal: string }): Promise<ReportGenerateResponse> =>
    normalizeReportResponse(await api.ok<unknown>('/api/report/generate', { method: 'POST', body, timeout: 30_000 }))

  const startEnrichment = async (reportId: number, scope: ReportRefreshScope = 'full'): Promise<ReportEnrichmentStatus> =>
    normalizeEnrichment(await api.ok<unknown>(`/api/report/${reportId}/enrichment`, { method: 'POST', body: { scope }, timeout: 10_000 }))

  const enrichmentStatus = async (reportId: number): Promise<ReportEnrichmentStatus> =>
    normalizeEnrichment(await api.ok<unknown>(`/api/report/${reportId}/enrichment`, { timeout: 10_000 }))

  const detail = async (reportId: number): Promise<ReportDetailResponse> => {
    const row = asRecord(normalizeReportResponse(await api.ok<unknown>(`/api/report/${reportId}`)))
    return { ...row, report_id: asNumber(row.report_id), report: row.report as ReportGenerateResponse['report'] } as ReportDetailResponse
  }

  const history = async (limit = 30): Promise<ReportHistoryItem[]> => {
    const row = itemListSchema.parse(await api.ok<unknown>(`/api/report/my/list?limit=${limit}`))
    return asArray(row.items).map((item) => {
      const value = asRecord(item)
      return { ...value, report_id: asNumber(value.report_id || value.id), title: asString(value.title) || undefined } as ReportHistoryItem
    }).filter(item => item.report_id > 0)
  }

  const reviews = async (reportId: number): Promise<ReportReview[]> => {
    const row = itemListSchema.parse(await api.ok<unknown>(`/api/report/${reportId}/reviews`))
    return asArray(row.items).map((item) => {
      const value = asRecord(item)
      return { ...value, review_id: asNumber(value.review_id || value.id) } as ReportReview
    }).filter(item => item.review_id > 0)
  }

  const createReviewDraft = async (body: Record<string, unknown>): Promise<ReportReviewDraft> => {
    const row = asRecord(await api.ok<unknown>('/api/report/review-drafts', { method: 'POST', body, timeout: 130_000 }))
    return {
      ...row,
      draft_id: asNumber(row.draft_id),
      report_id: asNumber(row.report_id),
      candidates: asArray(row.candidates).map(item => ({ ...asRecord(item), value: asNumber(asRecord(item).value), confidence: asNumber(asRecord(item).confidence) }))
    } as ReportReviewDraft
  }

  const confirmReviewDraft = async (draftId: number, body: Record<string, unknown>): Promise<ReportReviewConfirmation> => {
    const row = asRecord(await api.ok<unknown>(`/api/report/review-drafts/${draftId}/confirm`, { method: 'POST', body, timeout: 130_000 }))
    const proposal = asRecord(row.plan_proposal)
    return {
      ...row,
      draft_id: asNumber(row.draft_id),
      review_id: asNumber(row.review_id),
      report_id: asNumber(row.report_id),
      plan_proposal: proposal.proposal_id ? { ...proposal, proposal_id: asNumber(proposal.proposal_id), changes: asArray(proposal.changes) } : null
    } as ReportReviewConfirmation
  }

  const planVersions = async (reportId: number): Promise<ReportPlanVersion[]> => {
    const row = itemListSchema.parse(await api.ok<unknown>(`/api/report/${reportId}/plan-versions`))
    return asArray(row.items).map(item => {
      const value = asRecord(item)
      return { ...value, proposal_id: asNumber(value.proposal_id), changes: asArray(value.changes) } as ReportPlanVersion
    }).filter(item => item.proposal_id > 0)
  }

  const decidePlanProposal = (proposalId: number, body: Record<string, unknown>) =>
    api.ok<unknown>(`/api/report/plan-proposals/${proposalId}/decision`, { method: 'POST', body })

  const submitReview = (body: Record<string, unknown>) => api.ok<unknown>('/api/report/review-cycle', { method: 'POST', body })
  const setPlanActionDone = (reportId: number, body: Record<string, unknown>) => api.ok<unknown>(`/api/report/${reportId}/plan-actions/done`, { method: 'POST', body })
  const createPlanAction = (reportId: number, body: Record<string, unknown>) => api.ok<unknown>(`/api/report/${reportId}/plan-actions`, { method: 'POST', body })
  const updatePlanAction = (reportId: number, actionUid: string, body: Record<string, unknown>) => api.ok<unknown>(`/api/report/${reportId}/plan-actions/${encodeURIComponent(actionUid)}`, { method: 'PATCH', body })
  const deletePlanAction = (reportId: number, actionUid: string, jobId: string) => api.ok<unknown>(`/api/report/${reportId}/plan-actions/${encodeURIComponent(actionUid)}`, { method: 'DELETE', body: { job_id: jobId } })
  const publicInfo = (body: Record<string, unknown>, options: { signal?: AbortSignal } = {}) => api.ok<PublicInfoResponse>('/api/report/track-public-info', { method: 'POST', body, signal: options.signal })
  const exportPdf = (reportId: number, body: ReportPdfExportOptions) => api.request<Blob>(`/api/report/${reportId}/export/pdf`, {
    method: 'POST',
    body,
    responseType: 'blob',
    timeout: 130_000
  })
  const exportData = (reportId: number) => api.ok<Record<string, unknown>>(`/api/report/${reportId}/export/data`)
  const deleteReport = (reportId: number) => api.ok<{ report_id: number; deleted: boolean; recoverable: boolean }>(`/api/report/${reportId}`, { method: 'DELETE', body: { confirm_report_id: reportId } })
  const decidePreferenceStrategy = (reportId: number, body: Record<string, unknown>) => api.ok<Record<string, unknown>>(`/api/report/${reportId}/preference-strategy`, { method: 'PATCH', body })

  return { importFromMatch, generate, startEnrichment, enrichmentStatus, detail, history, reviews, createReviewDraft, confirmReviewDraft, planVersions, decidePlanProposal, submitReview, setPlanActionDone, createPlanAction, updatePlanAction, deletePlanAction, publicInfo, exportPdf, exportData, deleteReport, decidePreferenceStrategy }
}
