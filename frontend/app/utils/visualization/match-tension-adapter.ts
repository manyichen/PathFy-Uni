import { capabilityDimensions, capabilityLabels, type CapabilityScorePatch } from '~/types/capability'
import type { JobCard } from '~/types/job'
import type { MatchTensionDimension, MatchTensionSceneData, MatchTensionStatus } from '~/types/match-tension'

interface MatchTensionSource {
  studentScores?: CapabilityScorePatch
  job?: Pick<JobCard, 'id' | 'title' | 'scores'>
  animationRevision?: number
}

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizedSeries(scores: CapabilityScorePatch | undefined): Record<string, number> {
  const values = capabilityDimensions.map(dimension => number(scores?.[dimension]))
  const maximum = Math.max(0, ...values)
  const scale = maximum > 0 && maximum <= 1 ? 100 : 1
  return Object.fromEntries(capabilityDimensions.map((dimension, index) => [
    dimension,
    Math.max(0, Math.min(100, values[index]! * scale))
  ]))
}

function statusFor(gap: number): MatchTensionStatus {
  if (gap <= -5) return 'deficit'
  if (gap >= 5) return 'surplus'
  return 'balanced'
}

function stableScoreKey(dimensions: MatchTensionDimension[]): string {
  return dimensions.map(item => `${Math.round(item.studentScore)}-${Math.round(item.requirementScore)}`).join(':')
}

export function buildMatchTensionSceneData(source: MatchTensionSource): MatchTensionSceneData {
  const student = normalizedSeries(source.studentScores)
  const requirement = normalizedSeries(source.job?.scores)
  const dimensions = capabilityDimensions.map((id): MatchTensionDimension => {
    const studentScore = student[id]!
    const requirementScore = requirement[id]!
    const gap = studentScore - requirementScore
    return {
      id,
      label: capabilityLabels[id],
      studentScore,
      requirementScore,
      gap,
      intensity: Math.max(.08, Math.min(1, Math.abs(gap) / 30)),
      status: statusFor(gap)
    }
  })
  const deficits = dimensions.filter(item => item.status === 'deficit')
  const balanced = dimensions.filter(item => item.status === 'balanced')
  const surplus = dimensions.filter(item => item.status === 'surplus')
  const largestDeficit = [...deficits].sort((a, b) => a.gap - b.gap)[0]
  const jobId = String(source.job?.id || '')
  const jobTitle = String(source.job?.title || '待选择岗位')

  return {
    jobId,
    jobTitle,
    transitionKey: `${jobId || jobTitle}:${stableScoreKey(dimensions)}`,
    animationRevision: Math.max(0, Math.floor(number(source.animationRevision))),
    dimensions,
    summary: {
      deficitCount: deficits.length,
      balancedCount: balanced.length,
      surplusCount: surplus.length,
      averageAbsoluteGap: dimensions.reduce((sum, item) => sum + Math.abs(item.gap), 0) / dimensions.length,
      largestDeficit
    }
  }
}
