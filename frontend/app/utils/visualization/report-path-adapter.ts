import type { CareerReport, DevelopmentAdjustment, DevelopmentLine, ReportEnrichmentState, ReportPlan } from '~/types/report'
import type { ReportGrowthPoint, ReportPathAnimationKind, ReportPathEdge, ReportPathNode, ReportPathPhaseBand, ReportPathSceneData } from '~/types/report-path'

interface ReportPathSource {
  reportId?: number
  report?: CareerReport
  line?: DevelopmentLine
  plan?: ReportPlan
  adjustments?: DevelopmentAdjustment[]
  enrichState?: ReportEnrichmentState | 'idle'
  selectedMonth?: number
  animationRevision?: number
  animationKind?: ReportPathAnimationKind
}

const kindOrder: Record<ReportPathNode['kind'], number> = { origin: 0, plan: 1, review: 2, adjustment: 3 }

function clamp(value: number, minimum: number, maximum: number) {
  return Math.max(minimum, Math.min(maximum, value))
}

function monthValue(value: unknown): number {
  const month = Number(value)
  return Number.isFinite(month) ? clamp(month, 0, 12) : 0
}

function selectedAt(month: number, selectedMonth: number) {
  return Math.round(month) === selectedMonth
}

function progressValue(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined
  const progress = Number(value)
  return Number.isFinite(progress) ? clamp(progress, 0, 100) : undefined
}

function enrichmentState(source: ReportPathSource): ReportEnrichmentState {
  if (source.enrichState && source.enrichState !== 'idle') return source.enrichState
  return source.report?.llm_enrich_pending === true ? 'pending' : 'completed'
}

function enrichmentLabel(status: ReportEnrichmentState): string {
  return ({
    pending: 'AI 内容待处理',
    queued: 'AI 内容排队中',
    running: 'AI 内容处理中',
    completed: 'AI 内容已处理',
    failed: 'AI 内容处理失败'
  } as const)[status]
}

function pointKind(point: Record<string, unknown>, month: number): ReportPathNode['kind'] {
  if (String(point.kind || '').toLowerCase() === 'review' || point.review_id != null) return 'review'
  if (String(point.kind || '').toLowerCase() === 'origin' || month === 0) return 'origin'
  return 'plan'
}

function evidenceCount(point: Record<string, unknown>) {
  const detail = point.detail
  if (!detail || typeof detail !== 'object') return undefined
  const submitted = (detail as { submitted?: unknown }).submitted
  if (!submitted || typeof submitted !== 'object') return undefined
  return Object.values(submitted).filter(value => value !== null && value !== undefined && value !== '').length
}

function timelineNodes(line: DevelopmentLine | undefined, selectedMonth: number): ReportPathNode[] {
  const nodes = (line?.timeline || []).map((point, index): ReportPathNode => {
    const month = monthValue(point.month)
    const kind = pointKind(point, month)
    const reviewId = point.review_id == null ? undefined : String(point.review_id)
    return {
      id: `${kind}:${month}:${reviewId || index}`,
      kind,
      month,
      progress: progressValue(point.progress),
      evidenceCount: evidenceCount(point),
      label: String(point.label || (kind === 'review' ? `第 ${month} 月复盘` : kind === 'origin' ? '报告起点' : `第 ${month} 月计划`)),
      selected: selectedAt(month, selectedMonth),
      reviewId
    }
  })
  if (!nodes.some(node => node.kind === 'origin')) {
    nodes.push({ id: 'origin:0:generated', kind: 'origin', month: 0, progress: 0, label: '报告起点', selected: selectedMonth === 0 })
  }
  return nodes
}

function adjustmentNodes(adjustments: DevelopmentAdjustment[], selectedMonth: number): ReportPathNode[] {
  return adjustments.map((item, index) => {
    const month = monthValue(item.anchor_review_month ?? item.month ?? item.plan_month)
    const linkedMonth = item.plan_month == null ? undefined : monthValue(item.plan_month)
    return {
      id: `adjustment:${month}:${String(item.id || index)}`,
      kind: 'adjustment' as const,
      month,
      linkedMonth,
      progress: progressValue(item.progress),
      label: String(item.label || item.focus_label || `第 ${month} 月计划调整`),
      selected: selectedAt(month, selectedMonth),
      replanMode: item.replan_mode ? String(item.replan_mode) : undefined
    }
  })
}

function buildEdges(nodes: ReportPathNode[]): ReportPathEdge[] {
  const primary = nodes
    .filter(node => node.kind !== 'adjustment')
    .sort((a, b) => a.month - b.month || kindOrder[a.kind] - kindOrder[b.kind] || a.id.localeCompare(b.id))
  const edges: ReportPathEdge[] = primary.slice(1).map((node, index) => ({
    id: `sequence:${primary[index]!.id}:${node.id}`,
    sourceId: primary[index]!.id,
    targetId: node.id,
    kind: 'sequence'
  }))
  for (const adjustment of nodes.filter(node => node.kind === 'adjustment')) {
    const source = [...primary]
      .filter(node => node.month <= adjustment.month)
      .sort((a, b) => b.month - a.month || (a.kind === 'review' ? -1 : 1))[0]
    if (source) edges.push({ id: `replan:${source.id}:${adjustment.id}`, sourceId: source.id, targetId: adjustment.id, kind: 'replan' })
  }
  return edges
}

function growthPoints(nodes: ReportPathNode[], selectedMonth: number) {
  const origin: ReportGrowthPoint = { id: 'growth-origin', month: 0, progress: 0, label: '报告起点', kind: 'origin', selected: selectedMonth === 0 }
  const actualPoints: ReportGrowthPoint[] = [origin]
  const plannedPoints: ReportGrowthPoint[] = []
  for (const node of nodes) {
    if (node.progress === undefined || node.kind === 'adjustment' || node.kind === 'origin') continue
    const point: ReportGrowthPoint = {
      id: `growth:${node.id}`,
      month: node.month,
      progress: node.progress,
      label: node.label,
      kind: node.kind === 'review' ? 'verified' : 'planned',
      selected: selectedAt(node.month, selectedMonth),
      evidenceCount: node.evidenceCount,
      reviewId: node.reviewId
    }
    if (node.kind === 'review') actualPoints.push(point)
    else plannedPoints.push(point)
  }
  const byMonth = (a: ReportGrowthPoint, b: ReportGrowthPoint) => a.month - b.month || a.id.localeCompare(b.id)
  return { actualPoints: actualPoints.sort(byMonth), plannedPoints: plannedPoints.sort(byMonth) }
}

function phaseBands(plan: ReportPlan | undefined): ReportPathPhaseBand[] {
  const phases = plan?.phases && typeof plan.phases === 'object' ? plan.phases : {}
  return Object.entries(phases).flatMap(([key, phase]): ReportPathPhaseBand[] => {
    if (!phase || typeof phase !== 'object') return []
    const values = [...String(phase.period || '').matchAll(/\d+(?:\.\d+)?/g)].map(match => Number(match[0]))
    if (!values.length) return []
    const startMonth = clamp(values[0]!, 0, 12)
    const endMonth = clamp(values[1] ?? values[0]!, startMonth, 12)
    return [{ id: `phase:${key}`, label: String(phase.label || phase.summary || key), startMonth, endMonth }]
  }).sort((a, b) => a.startMonth - b.startMonth || a.endMonth - b.endMonth)
}

function currentPlanMonth(plan: ReportPlan | undefined, nodes: ReportPathNode[]) {
  const explicit = Number(plan?.current_plan_month ?? plan?.next_month_plan?.plan_month)
  if (Number.isFinite(explicit)) return clamp(explicit, 0, 12)
  return clamp(Math.max(0, ...nodes.map(node => node.linkedMonth ?? node.month)), 0, 12)
}

export function buildReportPathSceneData(source: ReportPathSource): ReportPathSceneData {
  const selectedMonth = Math.round(monthValue(source.selectedMonth))
  const nodes = [
    ...timelineNodes(source.line, selectedMonth),
    ...adjustmentNodes(Array.isArray(source.adjustments) ? source.adjustments : [], selectedMonth)
  ]
  const status = enrichmentState(source)
  const stableNodes = [...nodes].sort((a, b) => a.month - b.month || kindOrder[a.kind] - kindOrder[b.kind] || a.id.localeCompare(b.id))
  const { actualPoints, plannedPoints } = growthPoints(stableNodes, selectedMonth)
  const verifiedPoints = actualPoints.filter(point => point.kind === 'verified')
  const latest = verifiedPoints.at(-1)
  const lineId = String(source.line?.line_id || source.line?.target_job_id || 'report')
  const reportId = Math.max(0, Math.floor(Number(source.reportId) || 0))
  const transitionKey = `${reportId}:${lineId}:${stableNodes.map(node => `${node.id}:${node.progress ?? ''}:${node.linkedMonth ?? ''}`).join('|')}`

  return {
    reportId,
    lineId,
    title: String(source.line?.line_name || source.plan?.display_title || '当前报告发展路径'),
    transitionKey,
    animationRevision: Math.max(0, Math.floor(Number(source.animationRevision) || 0)),
    animationKind: source.animationKind || 'none',
    selectedMonth,
    currentMonth: currentPlanMonth(source.plan, stableNodes),
    nodes: stableNodes,
    edges: buildEdges(stableNodes),
    actualPoints,
    plannedPoints,
    phases: phaseBands(source.plan),
    enrichment: { status, label: enrichmentLabel(status) },
    summary: {
      eventCount: stableNodes.length,
      planCount: stableNodes.filter(node => node.kind === 'plan').length,
      reviewCount: stableNodes.filter(node => node.kind === 'review').length,
      adjustmentCount: stableNodes.filter(node => node.kind === 'adjustment').length,
      actualPointCount: verifiedPoints.length,
      plannedPointCount: plannedPoints.length,
      latestVerifiedMonth: latest?.month,
      latestVerifiedProgress: latest?.progress,
      dataState: verifiedPoints.length === 0 ? 'unmeasured' : verifiedPoints.length === 1 ? 'single_review' : 'tracked'
    }
  }
}
