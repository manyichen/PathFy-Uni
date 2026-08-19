import { capabilityLabels, type CapabilityDimension } from '~/types/capability'
import type { ReportDecisionClaim, ReportDecisionFact, ReportTargetDecision } from '~/types/report'
import type { ReportEvidenceActionSummary, ReportEvidenceDecisionRow, ReportEvidenceRowState, ReportEvidenceSceneData } from '~/types/report-evidence'

const claimOrder = { gap: 0, risk: 1, strength: 2, opportunity: 3 } as const
const stateMeta: Record<ReportDecisionClaim['kind'], { state: ReportEvidenceRowState; label: string }> = {
  gap: { state: 'hard_gap', label: '硬缺口' },
  risk: { state: 'verify', label: '容差内待验证' },
  strength: { state: 'strength', label: '相对优势' },
  opportunity: { state: 'opportunity', label: '发展机会' }
}

function emptyScene(): ReportEvidenceSceneData {
  return {
    jobId: '', title: '', transitionKey: 'empty', selectedRowId: '', rows: [], orphanActions: [],
    summary: { coverage: 0, claimCount: 0, comparableCount: 0, riskCount: 0, actionCount: 0, linkedActionCount: 0, unlinkedActionCount: 0, completedActionCount: 0, outcomeEvidenceCount: 0 }
  }
}

function numberValue(fact?: ReportDecisionFact) {
  if (fact?.value === null || fact?.value === undefined || fact?.value === '') return undefined
  const value = Number(fact.value)
  return Number.isFinite(value) ? value : undefined
}

function factBy(claim: ReportDecisionClaim, predicate: (fact: ReportDecisionFact) => boolean) {
  return claim.facts.find(predicate)
}

function actionSummary(action: ReportTargetDecision['actions'][number], linked: boolean): ReportEvidenceActionSummary {
  return {
    id: action.id, title: action.title, deliverable: action.deliverable, deadline: action.deadline,
    done: Boolean(action.done || action.status === 'done'), linked
  }
}

function dimensionLabel(claim: ReportDecisionClaim) {
  const key = claim.dimension as CapabilityDimension | undefined
  return key && capabilityLabels[key] ? capabilityLabels[key] : claim.title.replace(/(是当前.*|低于岗位.*|仍需.*|是.*补齐项).*/, '') || '综合判断'
}

function buildComparisonLabel(kind: ReportDecisionClaim['kind'], current?: number, required?: number, effectiveGap?: number) {
  if (current === undefined || required === undefined) return '缺少可比较的能力分值'
  const delta = current - required
  if (kind === 'gap') return `低于标尺 ${Math.abs(Math.round(delta))} 分 · 有效缺口 ${Math.round(effectiveGap || Math.abs(delta))} 分`
  if (kind === 'risk') return `低于标尺 ${Math.abs(Math.round(delta))} 分 · 尚在软容差内`
  if (delta > 0) return `高于标尺 ${Math.round(delta)} 分`
  if (delta === 0) return '与岗位标尺持平'
  return `低于标尺 ${Math.abs(Math.round(delta))} 分`
}

function rowForClaim(claim: ReportDecisionClaim, decision: ReportTargetDecision): ReportEvidenceDecisionRow {
  const currentFact = factBy(claim, fact => fact.id.startsWith('profile:') || fact.label.includes('当前能力'))
  const requiredFact = factBy(claim, fact => fact.id.startsWith('job:') || fact.label.includes('岗位要求'))
  const rawGapFact = factBy(claim, fact => fact.id.includes('raw-gap:') || fact.label.includes('容差内差值'))
  const effectiveGapFact = factBy(claim, fact => fact.id.includes('gap:') && !fact.id.includes('raw-gap:') || fact.label.includes('有效差距'))
  const currentScore = numberValue(currentFact)
  const requiredScore = numberValue(requiredFact)
  const rawGap = numberValue(rawGapFact) ?? (currentScore !== undefined && requiredScore !== undefined ? Math.max(0, requiredScore - currentScore) : undefined)
  const effectiveGap = numberValue(effectiveGapFact)
  const actions = decision.actions
    .filter(action => action.source_claim_ids.includes(claim.id))
    .map(action => actionSummary(action, Boolean(action.source_fact_refs?.length)))
  const nextAction = actions.find(action => !action.done) || actions[0]
  const hasOutcomeEvidence = claim.facts.some(fact => fact.evidence_grade === 'A' && fact.verified)
  const closureState = hasOutcomeEvidence ? 'verified' : actions.some(action => action.done) ? 'awaiting_review' : actions.length ? 'in_progress' : 'missing_action'
  const closureLabel = hasOutcomeEvidence ? '已有成果证据' : closureState === 'awaiting_review' ? '已勾选 · 待复盘验真' : closureState === 'in_progress' ? '计划中 · 尚无成果' : '尚未配置行动'
  const meta = stateMeta[claim.kind]

  return {
    id: claim.id,
    dimension: claim.dimension || claim.id,
    dimensionLabel: dimensionLabel(claim),
    state: meta.state,
    stateLabel: meta.label,
    title: claim.title,
    summary: claim.summary,
    impact: claim.impact,
    grade: claim.quality.evidence_grade,
    priority: Number(claim.priority || 0),
    currentScore,
    requiredScore,
    signedDelta: currentScore !== undefined && requiredScore !== undefined ? currentScore - requiredScore : undefined,
    rawGap,
    effectiveGap,
    comparisonLabel: buildComparisonLabel(claim.kind, currentScore, requiredScore, effectiveGap),
    facts: claim.facts,
    actions,
    nextAction,
    chainConnected: claim.fact_refs.length > 0 && claim.facts.length > 0 && actions.length > 0 && actions.every(action => action.linked),
    closureState,
    closureLabel,
    claim
  }
}

export function buildReportEvidenceSceneData(decision: ReportTargetDecision | undefined, selectedRowId = ''): ReportEvidenceSceneData {
  if (!decision) return emptyScene()

  const rows = [...decision.claims]
    .sort((a, b) => (claimOrder[a.kind] ?? 9) - (claimOrder[b.kind] ?? 9) || Number(b.priority || 0) - Number(a.priority || 0))
    .slice(0, 5)
    .map(claim => rowForClaim(claim, decision))
  const allClaimIds = new Set(decision.claims.map(claim => claim.id))
  const orphanActions = decision.actions
    .filter(action => !action.source_claim_ids.some(id => allClaimIds.has(id)) || !action.source_fact_refs?.length)
    .map(action => actionSummary(action, false))
  const metrics = decision.evidence_metrics
  const fallbackCoverage = decision.claims.length ? decision.claims.filter(claim => claim.quality.grounded).length / decision.claims.length : 0
  const linkedActionCount = decision.actions.filter(action => action.source_claim_ids.length && action.source_fact_refs?.length).length
  const unlinkedActionCount = metrics?.unlinked_action_count ?? Math.max(0, decision.actions.length - linkedActionCount)
  const outcomeEvidenceCount = decision.evidence_metrics?.outcome_evidence_count ?? decision.outcome_evidence?.length ?? 0
  const defaultSelection = rows.find(row => row.state === 'hard_gap' || row.state === 'verify')?.id || rows[0]?.id || ''
  const resolvedSelection = rows.some(row => row.id === selectedRowId) ? selectedRowId : defaultSelection

  return {
    jobId: decision.job_id,
    title: decision.display_title,
    transitionKey: [decision.job_id, rows.map(row => `${row.id}:${row.actions.length}:${row.closureState}`).join('|'), metrics?.coverage ?? fallbackCoverage].join(':'),
    selectedRowId: resolvedSelection,
    rows,
    orphanActions,
    summary: {
      coverage: metrics?.coverage ?? fallbackCoverage,
      claimCount: metrics?.claim_count ?? decision.claims.length,
      comparableCount: rows.filter(row => row.currentScore !== undefined && row.requiredScore !== undefined).length,
      riskCount: decision.claims.filter(claim => claim.kind === 'gap' || claim.kind === 'risk').length,
      actionCount: metrics?.action_count ?? decision.actions.length,
      linkedActionCount,
      unlinkedActionCount,
      completedActionCount: decision.actions.filter(action => action.done || action.status === 'done').length,
      outcomeEvidenceCount
    }
  }
}
