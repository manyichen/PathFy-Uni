import { capabilityDimensions, type CapabilityScores } from '~/types/capability'
import type { JobCard, JobWorkstyleProfile } from '~/types/job'
import type { MatchCandidate, MatchLlmResult, MatchPreferenceContext, MatchPreferenceFit, MatchPreviewResult, MatchRecommendation } from '~/types/match'
import type { PersonalityDimensionAnalysis, PersonalityDimensionCode, PersonalityDimensionScore, PersonalityPreferenceAxis, PersonalityPreferenceAxisCode, PersonalityQuestion, PersonalityResult } from '~/types/personality'
import type { ProfileDetail, ResumeOption } from '~/types/profile'

export type UnknownRecord = Record<string, unknown>

export function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {}
}

export function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

export function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : value == null ? fallback : String(value)
}

export function asNumber(value: unknown, fallback = 0): number {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

export function optionalNumber(value: unknown): number | undefined {
  const number = Number(value)
  return Number.isFinite(number) ? number : undefined
}

export function normalizeScores(value: unknown): CapabilityScores {
  const row = asRecord(value)
  return Object.fromEntries(capabilityDimensions.map(key => [key, asNumber(row[key])])) as CapabilityScores
}

export function normalizeResumeOption(value: unknown): ResumeOption {
  const row = asRecord(value)
  return {
    ...row,
    id: asNumber(row.id),
    name: asString(row.name) || undefined,
    major: asString(row.major) || undefined,
    education: asString(row.education) || undefined,
    created_at: asString(row.created_at || row.create_time) || undefined,
    create_time: asString(row.create_time || row.created_at) || undefined,
    scores: normalizeScores(row.scores && typeof row.scores === 'object' ? row.scores : row),
    completeness: optionalNumber(row.completeness),
    competitiveness: optionalNumber(row.competitiveness),
    score_avg: optionalNumber(row.score_avg)
  }
}

export function normalizeProfileDetail(value: unknown): ProfileDetail {
  const row = asRecord(value)
  const base = normalizeResumeOption(row)
  const analysis = asRecord(row.detailed_analysis)
  return {
    ...base,
    ...row,
    id: asNumber(row.id || row.resume_id),
    resume_id: optionalNumber(row.resume_id || row.id),
    scores: normalizeScores(row.scores && typeof row.scores === 'object' ? row.scores : row),
    detailed_analysis: analysis,
    materials: asArray(row.materials).map(asRecord)
  }
}

export function normalizePersonalityQuestion(value: unknown): PersonalityQuestion {
  const row = asRecord(value)
  return {
    ...row,
    id: asNumber(row.id),
    question_text: asString(row.question_text || row.question),
    option_a: asString(row.option_a || row.a),
    option_b: asString(row.option_b || row.b)
  }
}

export function normalizePersonalityResult(value: unknown): PersonalityResult {
  const row = asRecord(value)
  const detailed = asRecord(row.detailed_analysis)
  const recommendation = asRecord(row.job_recommendations || detailed.job_recommendations)
  const complete = asRecord(row.complete_analysis || detailed.complete_analysis)
  const normalizeStrings = (input: unknown) => asArray(input).map(item => asString(item)).filter(Boolean)
  const dimensions: PersonalityDimensionAnalysis[] = asArray(row.dimension_analysis || detailed.dimension_analysis).map(item => {
    const dimension = asRecord(item)
    return {
      ...dimension,
      dimension: asString(dimension.dimension) || undefined,
      type: asString(dimension.type) || undefined,
      name: asString(dimension.name) || undefined,
      description: asString(dimension.description) || undefined,
      characteristics: normalizeStrings(dimension.characteristics),
      work_preference: normalizeStrings(dimension.work_preference),
      growth_suggestions: normalizeStrings(dimension.growth_suggestions)
    }
  })
  const dimensionScores: PersonalityDimensionScore[] = asArray(row.dimension_scores || detailed.dimension_scores).flatMap(item => {
    const score = asRecord(item)
    const code = asString(score.code).toUpperCase()
    if (!['EI', 'SN', 'TF', 'JP'].includes(code)) return []
    return [{
      code: code as PersonalityDimensionCode,
      label: asString(score.label) || undefined,
      left: asString(score.left || code[0]),
      right: asString(score.right || code[1]),
      left_count: optionalNumber(score.left_count),
      right_count: optionalNumber(score.right_count),
      left_score: asNumber(score.left_score),
      right_score: asNumber(score.right_score),
      dominant: asString(score.dominant) || undefined,
      confidence: optionalNumber(score.confidence),
      preference_strength: optionalNumber(score.preference_strength),
      borderline: typeof score.borderline === 'boolean' ? score.borderline : undefined
    }]
  })
  const validPreferenceAxes = ['interaction_intensity', 'abstraction_preference', 'analytical_decision', 'structure_preference']
  const preferenceAxes: PersonalityPreferenceAxis[] = asArray(row.preference_axes || detailed.preference_axes).flatMap(item => {
    const axis = asRecord(item)
    const code = asString(axis.code)
    if (!validPreferenceAxes.includes(code)) return []
    const sourceDimension = asString(axis.source_dimension).toUpperCase()
    return [{
      code: code as PersonalityPreferenceAxisCode,
      source_dimension: ['EI', 'SN', 'TF', 'JP'].includes(sourceDimension) ? sourceDimension as PersonalityDimensionCode : undefined,
      value: asNumber(axis.value),
      preference_strength: optionalNumber(axis.preference_strength),
      measurement_quality: optionalNumber(axis.measurement_quality),
      low_label: asString(axis.low_label) || undefined,
      high_label: asString(axis.high_label) || undefined
    }]
  })
  return {
    ...row,
    profile_id: optionalNumber(row.profile_id || row.id),
    mbti_type: asString(row.mbti_type) || undefined,
    personality_analysis: asString(row.personality_analysis) || undefined,
    complete_analysis: {
      ...complete,
      type: asString(complete.type) || undefined,
      name: asString(complete.name) || undefined,
      summary: asString(complete.summary) || undefined,
      core_strengths: normalizeStrings(complete.core_strengths),
      career_tendencies: normalizeStrings(complete.career_tendencies),
      workplace_relationships: normalizeStrings(complete.workplace_relationships),
      development_areas: normalizeStrings(complete.development_areas),
      stress_response: asString(complete.stress_response) || undefined
    },
    dimension_analysis: dimensions,
    dimension_scores: dimensionScores,
    preference_axes: preferenceAxes,
    detailed_analysis: Object.keys(detailed).length ? { ...detailed, dimension_analysis: dimensions, dimension_scores: dimensionScores, preference_axes: preferenceAxes } : undefined,
    recommended_jobs: normalizeStrings(row.recommended_jobs || recommendation.recommended_jobs),
    job_recommendations: { ...recommendation, career_advice: asString(recommendation.career_advice) || undefined },
    status: ['measured', 'legacy', 'missing'].includes(asString(row.status)) ? asString(row.status) as PersonalityResult['status'] : undefined,
    result_status: asString(row.result_status) || undefined,
    question_set_version: asString(row.question_set_version) || undefined,
    scoring_version: asString(row.scoring_version) || undefined,
    answer_signature: asString(row.answer_signature) || undefined,
    is_active: typeof row.is_active === 'boolean' ? row.is_active : Boolean(row.is_active),
    personalization_enabled: typeof row.personalization_enabled === 'boolean' ? row.personalization_enabled : Boolean(row.personalization_enabled),
    completed_at: asString(row.completed_at) || undefined,
    created_at: asString(row.created_at) || undefined
  }
}

function normalizeMatchRecommendation(value: unknown, jobsById: Map<string, JobCard>): MatchRecommendation {
  const row = asRecord(value)
  const jobId = asString(row.job_id || row.id)
  const embedded = normalizeJobCard(row)
  const listed = jobsById.get(jobId)
  const job = normalizeJobCard({ ...(listed || {}), ...row, id: jobId, scores: row.scores || listed?.scores })
  const strings = (input: unknown) => asArray(input).map(item => asString(item)).filter(Boolean)
  return {
    job_id: jobId,
    rank: asNumber(row.rank),
    overall_fit_0_100: asNumber(row.overall_fit_0_100 ?? row.match_score ?? row.score),
    one_line: asString(row.one_line || row.reason || row.explanation) || undefined,
    strengths: strings(row.strengths),
    gaps: strings(row.gaps),
    risks: strings(row.risks),
    llm_fallback: Boolean(row.llm_fallback),
    job: job.id ? job : embedded
  }
}

export function normalizeJobCard(value: unknown): JobCard {
  const row = asRecord(value)
  const workstyle = asRecord(row.workstyle)
  return {
    ...row,
    id: asString(row.id || row.job_id || row.job_key),
    title: asString(row.title || row.job_title || row.name, '未命名岗位'),
    company: asString(row.company),
    location: asString(row.location),
    salary: asString(row.salary || row.salary_norm),
    scores: normalizeScores(row.scores && typeof row.scores === 'object' ? row.scores : row),
    score_avg: optionalNumber(row.score_avg),
    conf_avg: optionalNumber(row.conf_avg),
    workstyle: Object.keys(workstyle).length ? {
      status: asString(workstyle.status, 'insufficient_evidence') as JobWorkstyleProfile['status'],
      axes: asArray(workstyle.axes).map((item) => {
        const axis = asRecord(item)
        return {
          code: asString(axis.code), value: asNumber(axis.value), confidence: asNumber(axis.confidence),
          low_label: asString(axis.low_label), high_label: asString(axis.high_label),
          evidence: asArray(axis.evidence).map((evidence) => { const entry = asRecord(evidence); return { text: asString(entry.text), source: asString(entry.source) || undefined } }).filter(item => item.text),
          source: asString(axis.source) || undefined,
          inherited_from_job_title: Boolean(axis.inherited_from_job_title)
        }
      }),
      axis_count: asNumber(workstyle.axis_count), evidenced_axis_count: asNumber(workstyle.evidenced_axis_count),
      inherited_from_job_title: Boolean(workstyle.inherited_from_job_title),
      scoring_version: asString(workstyle.scoring_version) || undefined,
      snapshot_version: asString(workstyle.snapshot_version) || undefined,
      updated_at: asString(workstyle.updated_at) || undefined
    } : undefined
  }
}

export function normalizeMatchCandidate(value: unknown): MatchCandidate {
  const row = asRecord(value)
  const job = normalizeJobCard(row.job && typeof row.job === 'object' ? row.job : row)
  const preview = asRecord(row.match_preview)
  const preferenceFit = asRecord(preview.preference_fit)
  return {
    ...row,
    id: asString(row.id || job.id) || undefined,
    job,
    match_score: asNumber(row.match_score ?? row.score ?? preview.match_score ?? row.coarse_match_score ?? row.overall_fit_0_100),
    reason: asString(row.reason) || undefined,
    explanation: asString(row.explanation) || undefined,
    match_preview: {
      ...preview,
      match_score: optionalNumber(preview.match_score),
      dimension_gaps: normalizeScores(preview.dimension_gaps),
      preference_fit: Object.keys(preferenceFit).length ? {
        ...preferenceFit,
        status: asString(preferenceFit.status, 'not_enabled') as MatchPreferenceFit['status'],
        score: optionalNumber(preferenceFit.score),
        confidence: optionalNumber(preferenceFit.confidence),
        confidence_level: (asString(preferenceFit.confidence_level) || undefined) as MatchPreferenceFit['confidence_level'],
        evidenced_axes: optionalNumber(preferenceFit.evidenced_axes),
        required_axes: optionalNumber(preferenceFit.required_axes),
        axes: asArray(preferenceFit.axes).map((item) => {
          const axis = asRecord(item)
          return {
            code: asString(axis.code), user_value: asNumber(axis.user_value), job_value: asNumber(axis.job_value),
            preference_strength: asNumber(axis.preference_strength), fit: asNumber(axis.fit), confidence: asNumber(axis.confidence),
            evidence: asArray(axis.evidence).map((evidence) => { const entry = asRecord(evidence); return { text: asString(entry.text), source: asString(entry.source) || undefined } }).filter(item => item.text),
            source: asString(axis.source) || undefined,
            inherited_from_job_title: Boolean(axis.inherited_from_job_title), explanation: asString(axis.explanation)
          }
        }),
        influenced_ranking: Boolean(preferenceFit.influenced_ranking),
        algorithm_version: asString(preferenceFit.algorithm_version) || undefined
      } : undefined
    }
  }
}

export function normalizeMatchPreview(value: unknown): MatchPreviewResult {
  const row = asRecord(value)
  const student = asRecord(row.student)
  const rows = asArray(row.jobs || row.ranked_jobs || row.results)
  const jobs = rows.map(normalizeMatchCandidate)
  const jobsById = new Map(jobs.map(item => [item.job.id, item.job]))
  const llm = asRecord(row.llm)
  const filters = asRecord(row.filters)
  const preferenceContext = asRecord(row.preference_context)
  return {
    ...row,
    student: { ...student, scores: normalizeScores(student.scores && typeof student.scores === 'object' ? student.scores : student) },
    jobs,
    filters: {
      q: asString(filters.q) || undefined,
      location_q: asString(filters.location_q || filters.locationQ) || undefined,
      match_goal: asString(filters.match_goal || filters.goal) || undefined
    },
    llm: Object.keys(llm).length ? {
      ok: Boolean(llm.ok),
      error: asString(llm.error) || undefined,
      error_code: (asString(llm.error_code) || undefined) as MatchLlmResult['error_code'],
      model: asString(llm.model) || undefined,
      pool_size: optionalNumber(llm.pool_size),
      retry_attempted: Boolean(llm.retry_attempted),
      degraded: Boolean(llm.degraded),
      fallback_reason: asString(llm.fallback_reason) || undefined,
      fallback_mode: asString(llm.fallback_mode) || undefined,
      notice: asString(llm.notice) || undefined,
      initial_pool_size: optionalNumber(llm.initial_pool_size),
      fallback_pool_size: optionalNumber(llm.fallback_pool_size),
      top5: asArray(llm.top5).map(item => normalizeMatchRecommendation(item, jobsById)).filter(item => item.job_id)
    } : undefined,
    snapshot_warning: asString(row.snapshot_warning) || undefined,
    run_id: optionalNumber(row.run_id),
    resume_id: optionalNumber(row.resume_id),
    created_at: asString(row.created_at) || undefined,
    preference_context: Object.keys(preferenceContext).length ? {
      mode: (['explain', 'tie_break'].includes(asString(preferenceContext.mode)) ? asString(preferenceContext.mode) : 'off') as MatchPreferenceContext['mode'],
      status: asString(preferenceContext.status, 'off') as MatchPreferenceContext['status'],
      personality_profile_id: optionalNumber(preferenceContext.personality_profile_id),
      mbti_type: asString(preferenceContext.mbti_type) || undefined,
      completed_at: asString(preferenceContext.completed_at) || undefined,
      personalization_enabled: Boolean(preferenceContext.personalization_enabled),
      influenced_ranking: Boolean(preferenceContext.influenced_ranking),
      algorithm_version: asString(preferenceContext.algorithm_version) || undefined,
      workstyle_snapshot_version: asString(preferenceContext.workstyle_snapshot_version) || undefined,
      minimum_evidenced_axes: optionalNumber(preferenceContext.minimum_evidenced_axes),
      minimum_fit_confidence: optionalNumber(preferenceContext.minimum_fit_confidence),
      jobs_with_workstyle_evidence: optionalNumber(preferenceContext.jobs_with_workstyle_evidence),
      jobs_with_preference_fit: optionalNumber(preferenceContext.jobs_with_preference_fit),
      workstyle_coverage: optionalNumber(preferenceContext.workstyle_coverage),
      tie_break: Object.keys(asRecord(preferenceContext.tie_break)).length ? asRecord(preferenceContext.tie_break) as unknown as MatchPreferenceContext['tie_break'] : undefined
    } : undefined
  }
}
