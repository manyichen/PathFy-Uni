import { describe, expect, it } from 'vitest'
import { safeExternalUrl } from '~/utils/external-url'
import { PROFILE_FILE_MAX_BYTES, validateProfileFile } from '~/utils/profile-display'

describe('external URL policy', () => {
  it('allows only absolute http and https links', () => {
    expect(safeExternalUrl('https://example.com/path')).toBe('https://example.com/path')
    expect(safeExternalUrl('http://example.com')).toBe('http://example.com/')
    expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined()
    expect(safeExternalUrl('data:text/html,bad')).toBeUndefined()
    expect(safeExternalUrl('/relative')).toBeUndefined()
  })
})

describe('profile upload preflight', () => {
  it('checks extension, MIME and size independently of the input accept hint', () => {
    expect(validateProfileFile({ name: '简历.pdf', size: 1024, type: 'application/pdf' })).toBeUndefined()
    expect(validateProfileFile({ name: '脚本.exe', size: 1024, type: 'application/octet-stream' })).toContain('扩展名')
    expect(validateProfileFile({ name: '伪装.pdf', size: 1024, type: 'application/x-msdownload' })).toContain('文件类型')
    expect(validateProfileFile({ name: '大文件.pdf', size: PROFILE_FILE_MAX_BYTES + 1, type: 'application/pdf' })).toContain('10MB')
  })
})
