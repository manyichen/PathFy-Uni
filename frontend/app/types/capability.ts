export const capabilityDimensions = [
  'cap_req_theory',
  'cap_req_cross',
  'cap_req_practice',
  'cap_req_digital',
  'cap_req_innovation',
  'cap_req_teamwork',
  'cap_req_social',
  'cap_req_growth'
] as const

export type CapabilityDimension = typeof capabilityDimensions[number]
export type CapabilityScores = Record<CapabilityDimension, number>
export type CapabilityScorePatch = Partial<CapabilityScores>

export const capabilityLabels: Record<CapabilityDimension, string> = {
  cap_req_theory: '专业理论',
  cap_req_cross: '交叉学科',
  cap_req_practice: '实践技能',
  cap_req_digital: '数字素养',
  cap_req_innovation: '创新创业',
  cap_req_teamwork: '团队协作',
  cap_req_social: '社会网络',
  cap_req_growth: '学习成长'
}
