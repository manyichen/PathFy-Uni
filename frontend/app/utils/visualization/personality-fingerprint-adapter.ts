import type { PersonalityAnswer, PersonalityDimensionCode, PersonalityDimensionScore, PersonalityResult } from '~/types/personality'
import type { PersonalityFingerprintAxis, PersonalityFingerprintSceneData } from '~/types/personality-fingerprint'

interface PersonalityFingerprintSource {
  result?: PersonalityResult
  answers?: Record<number, 'A' | 'B'> | PersonalityAnswer[]
  animationRevision?: number
}

const axisDefinitions: Array<Pick<PersonalityFingerprintAxis, 'code' | 'label' | 'left' | 'right'>> = [
  { code: 'EI', label: '能量来源', left: 'E', right: 'I' },
  { code: 'SN', label: '信息偏好', left: 'S', right: 'N' },
  { code: 'TF', label: '决策方式', left: 'T', right: 'F' },
  { code: 'JP', label: '生活方式', left: 'J', right: 'P' }
]

function clamp(value: number, minimum = 0, maximum = 100): number {
  return Math.max(minimum, Math.min(maximum, value))
}

function validMbti(value: unknown): string {
  const mbti = String(value || '').trim().toUpperCase()
  return /^[EI][SN][TF][JP]$/.test(mbti) ? mbti : 'INTJ'
}

function normalizedMeasuredScores(scores: PersonalityDimensionScore[] | undefined): Map<PersonalityDimensionCode, PersonalityDimensionScore> | undefined {
  if (!Array.isArray(scores)) return undefined
  const mapped = new Map<PersonalityDimensionCode, PersonalityDimensionScore>()
  for (const score of scores) {
    if (!axisDefinitions.some(axis => axis.code === score.code)) continue
    const left = Number(score.left_score)
    const right = Number(score.right_score)
    const total = left + right
    if (!Number.isFinite(left) || !Number.isFinite(right) || total <= 0) continue
    mapped.set(score.code, {
      ...score,
      left_score: clamp(left / total * 100),
      right_score: clamp(right / total * 100)
    })
  }
  return mapped.size === axisDefinitions.length ? mapped : undefined
}

function answerKey(answers: PersonalityFingerprintSource['answers']): string {
  if (Array.isArray(answers)) {
    return [...answers]
      .sort((a, b) => a.question_id - b.question_id)
      .map(answer => `${answer.question_id}:${answer.user_choice}`)
      .join('|')
  }
  return Object.entries(answers || {})
    .map(([questionId, choice]) => [Number(questionId), choice] as const)
    .filter(([questionId, choice]) => Number.isFinite(questionId) && (choice === 'A' || choice === 'B'))
    .sort((a, b) => a[0] - b[0])
    .map(([questionId, choice]) => `${questionId}:${choice}`)
    .join('|')
}

function stableHash(value: string): number {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function axisStrength(axis: PersonalityFingerprintAxis): number {
  return (axis.leftScore - axis.rightScore) / 100
}

export function buildPersonalityFingerprintSceneData(source: PersonalityFingerprintSource): PersonalityFingerprintSceneData {
  const mbti = validMbti(source.result?.mbti_type || source.result?.complete_analysis?.type)
  const measuredScores = normalizedMeasuredScores(source.result?.dimension_scores || source.result?.detailed_analysis?.dimension_scores)
  const mode = measuredScores ? 'measured' : 'signature'
  const axes = axisDefinitions.map((definition, index): PersonalityFingerprintAxis => {
    const measured = measuredScores?.get(definition.code)
    const dominant = mbti[index] || definition.right
    const leftScore = measured?.left_score ?? (dominant === definition.left ? 68 : 32)
    const rightScore = measured?.right_score ?? 100 - leftScore
    const measuredConfidence = Number(measured?.confidence)
    return {
      ...definition,
      leftScore,
      rightScore,
      dominant: leftScore > rightScore ? definition.left : definition.right,
      confidence: Number.isFinite(measuredConfidence) ? clamp(measuredConfidence, 0, 1) : Math.abs(leftScore - rightScore) / 100,
      measured: Boolean(measured)
    }
  })
  const profileKey = String(source.result?.profile_id || 'local')
  const assessmentKey = source.result?.answer_signature || answerKey(source.answers)
  const seed = stableHash(`${profileKey}:${mbti}:${assessmentKey}`)
  const byCode = (code: PersonalityDimensionCode) => axes.find(axis => axis.code === code)!

  return {
    mbti,
    mode,
    seed,
    signatureId: seed.toString(36).padStart(7, '0').slice(-7).toUpperCase(),
    animationRevision: Math.max(0, Math.floor(Number(source.animationRevision) || 0)),
    axes,
    traits: {
      energyDirection: axisStrength(byCode('EI')),
      exploration: clamp(.5 - axisStrength(byCode('SN')) / 2, 0, 1),
      decisionEdge: clamp(.5 + axisStrength(byCode('TF')) / 2, 0, 1),
      structure: clamp(.5 + axisStrength(byCode('JP')) / 2, 0, 1)
    }
  }
}
