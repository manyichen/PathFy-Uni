import { beforeEach, describe, expect, it } from 'vitest'
import { cacheKeysForLogout, normalizeFieldErrors, parseStoredUser, unwrapCode, unwrapOk } from '~/utils/contracts'
import { normalizeMatchPreview, normalizePersonalityResult, normalizeProfileDetail } from '~/utils/normalizers'
import { readProfileCache, writeProfileCache } from '~/utils/cache/profile-cache'
import { canRestorePersonalityProgress, personalityCacheKey, questionSetSignature, readPersonalityCache, writePersonalityCache } from '~/utils/cache/personality-cache'
import { matchCacheKey, readMatchCache, writeMatchCache } from '~/utils/cache/match-cache'
import { readReportCache, reportCacheKey, writeReportCache } from '~/utils/cache/report-cache'
import { classifyProfileMaterial, formatProfileFileSize } from '~/utils/profile-display'
import { defaultUserPreferences, normalizeUserPreferences, validateUserPreferences } from '~/utils/account-preferences'
import { createExpiringCache, createLatestRequestController, SEARCH_DEBOUNCE_MS, shouldVirtualizeList } from '~/utils/request-performance'

describe('request performance primitives', () => {
  it('cancels the previous request and only keeps the latest ticket current', () => {
    const requests = createLatestRequestController()
    const first = requests.start()
    const second = requests.start()
    expect(first.signal.aborted).toBe(true)
    expect(first.isCurrent()).toBe(false)
    expect(second.isCurrent()).toBe(true)
    requests.cancel()
    expect(second.signal.aborted).toBe(true)
  })

  it('expires cached job details after the configured TTL', () => {
    let now = 100
    const cache = createExpiringCache<{ id: string }>(300, () => now)
    cache.set('job-1', { id: 'job-1' })
    expect(cache.get('job-1')).toEqual({ id: 'job-1' })
    now = 401
    expect(cache.get('job-1')).toBeUndefined()
  })

  it('keeps debounce and virtualization thresholds explicit', () => {
    expect(SEARCH_DEBOUNCE_MS).toBe(300)
    expect(shouldVirtualizeList(101, 101)).toBe(true)
    expect(shouldVirtualizeList(500, 20)).toBe(false)
  })
})

beforeEach(() => localStorage.clear())

describe('API contracts', () => {
  it('unwraps the formal success envelope', () => {
    expect(unwrapOk({ ok: true, data: { id: 1 } })).toEqual({ id: 1 })
  })

  it('rejects a formal failure envelope', () => {
    expect(() => unwrapOk({ ok: false, message: '失败' })).toThrow('失败')
  })

  it('unwraps the legacy code envelope', () => {
    expect(unwrapCode({ code: 200, data: [1, 2] })).toEqual([1, 2])
  })

  it('rejects a legacy code failure envelope', () => {
    expect(() => unwrapCode({ code: 400, msg: '错误' })).toThrow('错误')
  })

  it('keeps validation field paths for UI forms', () => {
    expect(normalizeFieldErrors([{ field: 'resume_id', msg: '必填' }, '目标岗位无效'])).toMatchObject([
      { field: 'resume_id', path: 'resume_id', message: '必填' },
      { message: '目标岗位无效' }
    ])
  })
})

describe('auth storage compatibility', () => {
  it('keeps old auth JSON readable', () => {
    expect(parseStoredUser('{"id":7,"username":"u","email":"e"}')?.id).toBe(7)
  })

  it('rejects damaged auth JSON', () => {
    expect(parseStoredUser('bad')).toBeNull()
  })

  it('clears exact user and guest cache versions', () => {
    const keys = cacheKeysForLogout(7)
    expect(keys).toContain('career_profile_portrait_v1_7')
    expect(keys).toContain('career_pj_match_v1_guest')
    expect(keys).toContain('career_personality_v1_7')
    expect(keys).toContain('career_report_workspace_v1_guest')
  })
})

describe('normalizers', () => {
  it('maps legacy flat profile scores into a typed portrait', () => {
    const portrait = normalizeProfileDetail({ id: '3', name: '小林', cap_req_digital: '91', detailed_analysis: { overall_evaluation: '可靠' } })
    expect(portrait.id).toBe(3)
    expect(portrait.scores?.cap_req_digital).toBe(91)
    expect(portrait.detailed_analysis?.overall_evaluation).toBe('可靠')
  })

  it('maps personality job recommendations from the legacy nested result', () => {
    const result = normalizePersonalityResult({ mbti_type: 'INTJ', job_recommendations: { recommended_jobs: ['数据分析师'] } })
    expect(result.recommended_jobs).toEqual(['数据分析师'])
  })

  it('normalizes every legacy match result alias', () => {
    const result = normalizeMatchPreview({ student: { cap_req_digital: 89 }, ranked_jobs: [{ title: '数据分析师', score: 86 }] })
    expect(result.student.scores.cap_req_digital).toBe(89)
    expect(result.jobs[0]).toMatchObject({ match_score: 86, job: { title: '数据分析师' } })
  })

  it('keeps AI Top 5 separate and reuses listed job scores', () => {
    const result = normalizeMatchPreview({ student: {}, jobs: [{ id: 'j1', title: '数据分析师', cap_req_digital: 92 }], llm: { ok: true, top5: [{ job_id: 'j1', rank: 1, overall_fit_0_100: 94, strengths: ['数字能力'], gaps: ['行业经验'], risks: [] }] } })
    expect(result.jobs).toHaveLength(1)
    expect(result.llm?.top5[0]).toMatchObject({ job_id: 'j1', overall_fit_0_100: 94, job: { title: '数据分析师', scores: { cap_req_digital: 92 } } })
  })

  it('normalizes preference explanation without changing the capability score', () => {
    const result = normalizeMatchPreview({
      student: {},
      preference_context: { mode: 'explain', status: 'measured', personality_profile_id: 9, influenced_ranking: false },
      jobs: [{ id: 'j1', match_preview: { match_score: 84, preference_fit: { status: 'insufficient_job_evidence', influenced_ranking: false } } }]
    })
    expect(result.jobs[0]?.match_score).toBe(84)
    expect(result.jobs[0]?.match_preview?.preference_fit).toMatchObject({ status: 'insufficient_job_evidence', influenced_ranking: false })
    expect(result.preference_context).toMatchObject({ mode: 'explain', personality_profile_id: 9, influenced_ranking: false })
  })

  it('normalizes an auditable workstyle fit and its evidence', () => {
    const result = normalizeMatchPreview({
      student: {},
      preference_context: { mode: 'explain', status: 'measured', jobs_with_preference_fit: 1, influenced_ranking: false },
      jobs: [{ id: 'j1', workstyle: { status: 'available', axis_count: 1, evidenced_axis_count: 1, axes: [{ code: 'structure_preference', value: 75, confidence: .8, low_label: '灵活', high_label: '结构', evidence: [{ text: '固定里程碑' }] }] }, match_preview: { match_score: 84, preference_fit: { status: 'available', score: 92, confidence: .8, confidence_level: 'high', influenced_ranking: false, axes: [{ code: 'structure_preference', user_value: 70, job_value: 75, preference_strength: .4, fit: 98, confidence: .8, evidence: [{ text: '固定里程碑' }], explanation: '方向一致' }] } } }]
    })
    expect(result.jobs[0]?.job.workstyle?.axes[0]).toMatchObject({ value: 75, evidence: [{ text: '固定里程碑' }] })
    expect(result.jobs[0]?.match_preview?.preference_fit).toMatchObject({ status: 'available', score: 92, confidence_level: 'high' })
    expect(result.preference_context?.jobs_with_preference_fit).toBe(1)
  })

  it('normalizes all personality detail categories', () => {
    const result = normalizePersonalityResult({ dimension_analysis: [{ dimension: '能量', characteristics: ['专注'] }], complete_analysis: { career_tendencies: ['研究'], workplace_relationships: ['独立'], development_areas: ['表达'], stress_response: '先独处' } })
    expect(result.dimension_analysis?.[0].characteristics).toEqual(['专注'])
    expect(result.complete_analysis).toMatchObject({ career_tendencies: ['研究'], workplace_relationships: ['独立'], development_areas: ['表达'], stress_response: '先独处' })
  })

  it('restores measured personality dimensions from persisted detailed analysis', () => {
    const result = normalizePersonalityResult({
      mbti_type: 'ENTJ',
      detailed_analysis: {
        dimension_scores: [
          { code: 'EI', left: 'E', right: 'I', left_score: '75', right_score: 25, dominant: 'E', confidence: .5 }
        ]
      }
    })
    expect(result.dimension_scores?.[0]).toMatchObject({ code: 'EI', left_score: 75, right_score: 25, dominant: 'E' })
    expect(result.detailed_analysis?.dimension_scores?.[0].confidence).toBe(.5)
  })
})

describe('iteration 4 UI contracts', () => {
  it('classifies profile materials before upload', () => {
    expect(classifyProfileMaterial('个人简历.pdf')).toBe('简历')
    expect(classifyProfileMaterial('英语证书.jpg')).toBe('证书')
    expect(classifyProfileMaterial('课程成绩.xlsx')).toBe('成绩')
    expect(classifyProfileMaterial('数据项目说明.md')).toBe('项目')
    expect(formatProfileFileSize(1024 * 1024)).toBe('1.0 MB')
  })

  it('validates recommendation limits and integer values', () => {
    const form = { ...defaultUserPreferences, match_result_count: 101, learning_resource_count: 1.5, competition_count: -1 }
    expect(validateUserPreferences(form, { match_result_count: 100, learning_resource_count: 20, competition_count: 10 })).toEqual({
      match_result_count: '请输入 1～100 的整数', learning_resource_count: '请输入 1～20 的整数', competition_count: '请输入 0～10 的整数'
    })
  })

  it('normalizes only known preference fields and drops secrets', () => {
    const normalized = normalizeUserPreferences({ ...defaultUserPreferences, theme: 'dark', api_key: 'must-not-leak' } as typeof defaultUserPreferences & { api_key: string })
    expect(normalized.theme).toBe('dark')
    expect(normalized).not.toHaveProperty('api_key')
  })
})

describe('versioned workspace caches', () => {
  it('migrates a v1 profile cache and writes a versioned envelope', () => {
    localStorage.setItem('career_profile_portrait_v1_7', JSON.stringify({ v: 1, resume_id: 2, id: 2, name: '小林', cap_req_theory: 75 }))
    expect(readProfileCache(7)?.portrait.id).toBe(2)
    expect(JSON.parse(localStorage.getItem('career_profile_portrait_v1_7') || '{}').schemaVersion).toBe(2)
  })

  it('writes and reads a current profile cache', () => {
    writeProfileCache(7, { resumeId: 2, portrait: normalizeProfileDetail({ id: 2, name: '小林' }) })
    expect(readProfileCache(7)?.resumeId).toBe(2)
  })

  it('migrates personality answer arrays', () => {
    localStorage.setItem(personalityCacheKey(7), JSON.stringify({ v: 1, answers: [{ question_id: 2, user_choice: 'B' }], showStartScreen: false }))
    expect(readPersonalityCache(7)).toMatchObject({ answers: { 2: 'B' }, started: true })
  })

  it('writes and reads a current personality cache', () => {
    writePersonalityCache(7, { answers: { 1: 'A' }, started: true, currentQuestionIndex: 0 })
    expect(readPersonalityCache(7)?.answers).toEqual({ 1: 'A' })
  })

  it('restores personality progress only for the same ordered question set', () => {
    const state = { answers: { 1: 'A' as const }, started: true, currentQuestionIndex: 1, questionSignature: '1:2:3' }
    expect(questionSetSignature([{ id: 1 }, { id: 2 }, { id: 3 }])).toBe('1:2:3')
    expect(canRestorePersonalityProgress(state, '1:2:3')).toBe(true)
    expect(canRestorePersonalityProgress(state, '1:4:3')).toBe(false)
  })

  it('migrates the v1 match workspace and preserves filters', () => {
    localStorage.setItem(matchCacheKey(7), JSON.stringify({ v: 1, resumeId: 2, result: { student: {}, results: [{ title: '测试岗位', overall_fit_0_100: 70 }] }, filters: { q: '测试', locationQ: '上海', goal: 'stretch', refine: true } }))
    expect(readMatchCache(7)).toMatchObject({ resumeId: 2, filters: { q: '测试', locationQ: '上海', goal: 'stretch', refine: true } })
  })

  it('writes and reads a current match cache', () => {
    writeMatchCache(7, { resumeId: 2, result: normalizeMatchPreview({ student: {}, jobs: [] }), filters: { q: '', locationQ: '', goal: 'fit', refine: false, preferenceMode: 'off' } })
    expect(readMatchCache(7)?.filters.goal).toBe('fit')
  })

  it('migrates report snapshots without retaining resume material text', () => {
    localStorage.setItem(reportCacheKey(7), JSON.stringify({ v: 1, resumeId: 2, reportSnapshot: { summary: '计划', resume_text: '不应持久化' } }))
    const cache = readReportCache(7)
    expect(cache?.reportSnapshot?.summary).toBe('计划')
    expect(cache?.reportSnapshot?.resume_text).toBeUndefined()
  })

  it('writes and reads a current report workspace', () => {
    writeReportCache(7, { resumeId: 2, goal: 'fit', targets: [{ job_id: 'job-1', title: '数据分析师' }] })
    expect(readReportCache(7)?.targets?.[0]?.job_id).toBe('job-1')
  })

  it('migrates the old report focus target and canvas month', () => {
    localStorage.setItem(reportCacheKey(7), JSON.stringify({ v: 1, activeJobId: 'job-2', selectedCanvasMonth: 4, configRailCollapsed: true, selectedTargets: [] }))
    expect(readReportCache(7)).toMatchObject({ activeJobId: 'job-2', selectedMonth: 4, configCollapsed: true })
  })

  it('round-trips the active report target and selected month', () => {
    writeReportCache(7, { activeJobId: 'job-3', selectedMonth: 6, configCollapsed: true })
    expect(readReportCache(7)).toMatchObject({ activeJobId: 'job-3', selectedMonth: 6, configCollapsed: true })
  })

  it('clears only a damaged workspace cache and keeps auth storage', () => {
    localStorage.setItem('auth_token', 'keep-me')
    localStorage.setItem(matchCacheKey(7), '{not-json')
    expect(readMatchCache(7)).toBeUndefined()
    expect(localStorage.getItem(matchCacheKey(7))).toBeNull()
    expect(localStorage.getItem('auth_token')).toBe('keep-me')
  })

  it('does not restore another user’s current cache payload', () => {
    localStorage.setItem(matchCacheKey(7), JSON.stringify({ schemaVersion: 2, savedAt: 1, userId: 8, data: {} }))
    expect(readMatchCache(7)).toBeUndefined()
    expect(localStorage.getItem(matchCacheKey(7))).toBeNull()
  })
})
