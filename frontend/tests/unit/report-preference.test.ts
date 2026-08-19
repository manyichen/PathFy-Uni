import { describe, expect, it } from 'vitest'
import { reactive } from 'vue'
import { copyPreferenceSections } from '../../app/utils/report-preference'

describe('copyPreferenceSections', () => {
  it('copies Vue reactive report data into an independent editable array', () => {
    const source = reactive([{
      code: 'collaboration',
      title: '协作方式',
      recommendation: '先书面同步',
      alternative: '短会确认',
      rationale: '偏好结构化表达',
      source: { axis_code: 'IE', value: 62, preference_strength: 0.62 }
    }])

    expect(() => structuredClone(source)).toThrow()
    const copy = copyPreferenceSections(source)
    expect(copy).toEqual(source)
    copy[0]!.recommendation = '先开会讨论'
    copy[0]!.source!.value = 40
    expect(source[0]!.recommendation).toBe('先书面同步')
    expect(source[0]!.source!.value).toBe(62)
  })
})
