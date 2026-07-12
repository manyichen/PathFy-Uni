import { describe, expect, it } from 'vitest'
import { cacheKeysForLogout, parseStoredUser, unwrapCode, unwrapOk } from '~/utils/contracts'

describe('API contracts', () => {
  it('unwraps both backend envelope conventions', () => {
    expect(unwrapOk({ ok: true, data: { id: 1 } })).toEqual({ id: 1 })
    expect(unwrapCode({ code: 200, data: [1, 2] })).toEqual([1, 2])
    expect(() => unwrapOk({ ok: false, message: '失败' })).toThrow('失败')
    expect(() => unwrapCode({ code: 400, msg: '错误' })).toThrow('错误')
  })
})

describe('auth storage compatibility', () => {
  it('keeps old auth JSON readable', () => {
    expect(parseStoredUser('{"id":7,"username":"u","email":"e"}')?.id).toBe(7)
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
