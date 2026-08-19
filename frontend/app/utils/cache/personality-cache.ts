import type { PersonalityResult } from '~/types/personality'
import { asArray, asNumber, asRecord, asString, normalizePersonalityResult } from '~/utils/normalizers'
import { cacheKey, readCache, removeCache, type CacheUserId, writeCache } from './base'

const prefix = 'career_personality_v1_'
export interface PersonalityCacheState {
  answers: Record<number, 'A' | 'B'>
  result?: PersonalityResult
  started: boolean
  currentQuestionIndex: number
  questionSignature?: string
  savedAt?: string
}
export const personalityCacheKey = (userId: CacheUserId) => cacheKey(prefix, userId)

export function questionSetSignature(questions: Array<{ id: number }>): string {
  return questions.map(item => item.id).join(':')
}

export function canRestorePersonalityProgress(state: PersonalityCacheState, signature: string): boolean {
  return Object.keys(state.answers).length === 0 || state.questionSignature === signature
}

function migrate(raw: unknown): PersonalityCacheState | undefined {
  const row = asRecord(raw)
  const payload = asRecord(row.data || row)
  const answersRaw = payload.answers
  const entries: Array<[number, 'A' | 'B']> = Array.isArray(answersRaw)
    ? asArray(answersRaw).map((item): [number, 'A' | 'B'] => { const value = asRecord(item); return [asNumber(value.question_id), asString(value.user_choice) === 'B' ? 'B' : 'A'] })
    : Object.entries(asRecord(answersRaw)).map(([id, choice]): [number, 'A' | 'B'] => [asNumber(id), asString(choice) === 'B' ? 'B' : 'A'])
  const answers = Object.fromEntries(entries.filter(([id]) => id > 0)) as Record<number, 'A' | 'B'>
  const rawResult = payload.result || payload.personalityProfile
  return {
    answers,
    result: rawResult && typeof rawResult === 'object' ? normalizePersonalityResult(rawResult) : undefined,
    started: payload.started != null ? Boolean(payload.started) : payload.showStartScreen === false || Object.keys(answers).length > 0,
    currentQuestionIndex: Math.max(0, asNumber(payload.currentQuestionIndex)),
    questionSignature: asString(payload.questionSignature) || undefined,
    savedAt: asString(payload.savedAt || row.savedAt) || undefined
  }
}

export const readPersonalityCache = (userId: CacheUserId) => readCache(personalityCacheKey(userId), userId, migrate)
export const writePersonalityCache = (userId: CacheUserId, data: PersonalityCacheState) => writeCache(personalityCacheKey(userId), userId, data)
export const clearPersonalityCache = (userId: CacheUserId) => removeCache(personalityCacheKey(userId))
