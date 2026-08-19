import { describe, expect, it } from 'vitest'
import { buildPersonalityFingerprintSceneData } from '~/utils/visualization/personality-fingerprint-adapter'

const measuredResult = {
  profile_id: 42,
  mbti_type: 'ENTJ',
  dimension_scores: [
    { code: 'EI' as const, left: 'E', right: 'I', left_score: 75, right_score: 25, confidence: .5 },
    { code: 'SN' as const, left: 'S', right: 'N', left_score: 20, right_score: 80, confidence: .6 },
    { code: 'TF' as const, left: 'T', right: 'F', left_score: 65, right_score: 35, confidence: .3 },
    { code: 'JP' as const, left: 'J', right: 'P', left_score: 55, right_score: 45, confidence: .1 }
  ]
}

describe('personality fingerprint visualization adapter', () => {
  it('uses all four real dimension ratios when the result contains measured scores', () => {
    const scene = buildPersonalityFingerprintSceneData({ result: measuredResult })

    expect(scene.mode).toBe('measured')
    expect(scene.axes).toHaveLength(4)
    expect(scene.axes.find(axis => axis.code === 'SN')).toMatchObject({ leftScore: 20, rightScore: 80, dominant: 'N', measured: true })
    expect(scene.traits.exploration).toBeCloseTo(.8)
  })

  it('labels legacy results as a type signature and does not invent measured percentages', () => {
    const scene = buildPersonalityFingerprintSceneData({ result: { profile_id: 7, mbti_type: 'ISFP' } })

    expect(scene.mode).toBe('signature')
    expect(scene.axes.map(axis => axis.dominant).join('')).toBe('ISFP')
    expect(scene.axes.every(axis => axis.measured === false)).toBe(true)
    expect(scene.axes[0]).toMatchObject({ leftScore: 32, rightScore: 68 })
  })

  it('creates the same seed for the same answer sequence regardless of record insertion order', () => {
    const first = buildPersonalityFingerprintSceneData({ result: measuredResult, answers: { 3: 'A', 1: 'B', 2: 'A' } })
    const reordered = buildPersonalityFingerprintSceneData({ result: measuredResult, answers: { 1: 'B', 2: 'A', 3: 'A' } })
    const changed = buildPersonalityFingerprintSceneData({ result: measuredResult, answers: { 1: 'B', 2: 'B', 3: 'A' } })

    expect(first.seed).toBe(reordered.seed)
    expect(first.signatureId).toBe(reordered.signatureId)
    expect(first.seed).not.toBe(changed.seed)
  })

  it('uses the persisted answer signature when local answers are unavailable', () => {
    const withAnswers = buildPersonalityFingerprintSceneData({
      result: { ...measuredResult, answer_signature: 'assessment-signature' },
      answers: { 1: 'A', 2: 'B' }
    })
    const restored = buildPersonalityFingerprintSceneData({
      result: { ...measuredResult, answer_signature: 'assessment-signature' }
    })

    expect(restored.seed).toBe(withAnswers.seed)
    expect(restored.signatureId).toBe(withAnswers.signatureId)
  })

  it('falls back safely when one measured axis is missing or malformed', () => {
    const scene = buildPersonalityFingerprintSceneData({
      result: { ...measuredResult, dimension_scores: measuredResult.dimension_scores.slice(0, 3) }
    })

    expect(scene.mode).toBe('signature')
    expect(scene.axes.every(axis => axis.measured === false)).toBe(true)
  })
})
