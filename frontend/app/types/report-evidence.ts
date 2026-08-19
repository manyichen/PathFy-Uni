import type { ReportDecisionClaim, ReportDecisionFact } from './report'

export type ReportEvidenceRowState = 'hard_gap' | 'verify' | 'strength' | 'opportunity'
export type ReportEvidenceClosureState = 'verified' | 'awaiting_review' | 'in_progress' | 'missing_action'

export interface ReportEvidenceActionSummary {
  id: string
  title: string
  deliverable: string
  deadline: string
  done: boolean
  linked: boolean
}

export interface ReportEvidenceDecisionRow {
  id: string
  dimension: string
  dimensionLabel: string
  state: ReportEvidenceRowState
  stateLabel: string
  title: string
  summary: string
  impact: string
  grade: string
  priority: number
  currentScore?: number
  requiredScore?: number
  signedDelta?: number
  rawGap?: number
  effectiveGap?: number
  comparisonLabel: string
  facts: ReportDecisionFact[]
  actions: ReportEvidenceActionSummary[]
  nextAction?: ReportEvidenceActionSummary
  chainConnected: boolean
  closureState: ReportEvidenceClosureState
  closureLabel: string
  claim: ReportDecisionClaim
}

export interface ReportEvidenceSceneData {
  jobId: string
  title: string
  transitionKey: string
  selectedRowId: string
  rows: ReportEvidenceDecisionRow[]
  orphanActions: ReportEvidenceActionSummary[]
  summary: {
    coverage: number
    claimCount: number
    comparableCount: number
    riskCount: number
    actionCount: number
    linkedActionCount: number
    unlinkedActionCount: number
    completedActionCount: number
    outcomeEvidenceCount: number
  }
}

export interface ReportEvidenceSelection {
  rowId: string
}
