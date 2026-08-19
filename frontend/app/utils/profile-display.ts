import type { ProfileDimensionAnalysis } from '~/types/profile'
import { capabilityLabels, type CapabilityDimension } from '~/types/capability'

export type ProfileItem = Record<string, unknown>
export type ProfileMaterialCategory = '简历' | '证书' | '成绩' | '项目' | '补充材料'

export const PROFILE_FILE_MAX_BYTES = 10 * 1024 * 1024
export const PROFILE_FILE_MAX_COUNT = 12
export const PROFILE_FILE_EXTENSIONS = new Set(['pdf', 'docx', 'txt', 'md', 'markdown', 'csv', 'json', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'webp'])
const PROFILE_FILE_MIME_TYPES = new Set([
  'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain', 'text/markdown', 'text/csv', 'application/json',
  'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'image/png', 'image/jpeg', 'image/webp'
])

export function validateProfileFile(file: Pick<File, 'name' | 'size' | 'type'>): string | undefined {
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!PROFILE_FILE_EXTENSIONS.has(extension)) return `${file.name}：不支持的文件扩展名`
  if (file.size > PROFILE_FILE_MAX_BYTES) return `${file.name}：单个文件不能超过 10MB`
  if (file.type && !PROFILE_FILE_MIME_TYPES.has(file.type)) return `${file.name}：文件类型与允许格式不符`
  return undefined
}

export function profileItem(value: unknown): ProfileItem {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as ProfileItem : {}
}

export function profileItems(value: unknown): ProfileItem[] {
  return (Array.isArray(value) ? value : value ? [value] : []).map(profileItem)
}

export function profileText(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(profileText).filter(Boolean).join('；')
  const row = profileItem(value)
  return profileText(row.interpretation || row.analysis || row.description || row.summary || row.content || row.plan || row.goal || row.name || row.dimension || Object.values(row))
}

export function profileDimensionName(value: unknown): string {
  const row = profileItem(value)
  const raw = String(row.dimension || row.name || row.label || '能力维度')
  return capabilityLabels[raw as CapabilityDimension] || raw
}

export function profileDimensionScore(value: unknown): number {
  const row = profileItem(value)
  const score = Number(row.score ?? row.value ?? 0)
  return Number.isFinite(score) ? score : 0
}

export function profileDimensionEvidence(value: ProfileDimensionAnalysis, materialNames: string[]): string[] {
  const row = profileItem(value)
  const explicit = row.evidence_sources || row.evidence || row.sources || row.materials
  const sources = (Array.isArray(explicit) ? explicit : explicit ? [explicit] : []).map(profileText).filter(Boolean)
  if (sources.length) return sources
  return materialNames.length ? materialNames.slice(0, 3) : ['画像材料综合分析']
}

export function profileStringList(value: unknown): string[] {
  const rows = Array.isArray(value) ? value : value == null ? [] : [value]
  return rows.map(profileText).map(item => item.trim()).filter(Boolean)
}

interface DimensionActionKit {
  match: RegExp
  actions: string[]
  evidence: string
  metric: string
}

const dimensionActionKits: DimensionActionKit[] = [
  { match: /理论/, actions: ['整理一张核心概念图，并为每个概念补充一个真实案例', '选择一道综合问题完成推导、讲解和错因复盘'], evidence: '核心概念图、问题解答与讲解记录', metric: '覆盖至少 20 个核心概念，并能独立讲解其中 3 个' },
  { match: /交叉|跨学科/, actions: ['选择一个本专业问题，引入另一学科的方法重新分析', '邀请不同专业同伴评审方案并记录修改'], evidence: '跨学科案例报告与评审修改记录', metric: '报告至少使用两类学科方法，并完成 1 次外部评审' },
  { match: /实践/, actions: ['完成一个从需求、实现到复盘的端到端项目', '把过程、结果和关键决策整理为作品集条目'], evidence: '可运行成果、过程记录和项目复盘', metric: '形成 1 个可演示项目，并获得至少 2 条有效反馈' },
  { match: /数字/, actions: ['用数据工具处理一份真实数据并提出业务结论', '保留数据清洗、分析脚本和可视化过程'], evidence: '数据集、脚本、图表与结论说明', metric: '完整交付 1 次可复现分析，关键步骤可由他人复跑' },
  { match: /创新|创业/, actions: ['围绕一个真实痛点提出三种方案并完成取舍', '制作最小原型，向潜在用户收集反馈'], evidence: '问题定义、原型和用户反馈记录', metric: '完成 1 个原型并收集至少 5 条反馈' },
  { match: /团队|协作/, actions: ['在团队任务中主动承担一个可验收角色', '组织一次分工检查和项目复盘'], evidence: '分工表、协作记录与团队复盘', metric: '按期交付负责模块，并获得至少 2 名成员反馈' },
  { match: /社会|网络/, actions: ['参加一次行业活动并带着问题完成定向交流', '建立联系人清单，并在一周内完成后续沟通'], evidence: '活动记录、联系人清单与交流纪要', metric: '新增 5 位有效联系人，完成 2 次深度交流' },
  { match: /学习|成长|发展潜力/, actions: ['设定一个四周学习冲刺并拆分每周成果', '每周复盘一次计划偏差并调整下一周动作'], evidence: '四周计划、成果记录与复盘日志', metric: '连续完成 4 次周复盘，并产出 1 项可展示成果' }
]

function dimensionActionKit(name: string): DimensionActionKit {
  return dimensionActionKits.find(item => item.match.test(name)) || {
    match: /.*/,
    actions: ['选择一个真实任务持续练习四周', '保留过程记录并邀请他人给出反馈'],
    evidence: '任务成果、过程记录和反馈',
    metric: '完成 1 项可展示成果并获得外部反馈'
  }
}

export function profileDimensionInsight(value: ProfileDimensionAnalysis, allItems: ProfileDimensionAnalysis[], materialNames: string[]) {
  const row = profileItem(value)
  const name = profileDimensionName(value)
  const score = profileDimensionScore(value)
  const scores = allItems.map(profileDimensionScore).filter(Number.isFinite)
  const average = scores.length ? scores.reduce((sum, item) => sum + item, 0) / scores.length : score
  const rank = Number(row.rank) || [...scores].sort((a, b) => b - a).findIndex(item => item === score) + 1
  const delta = Number.isFinite(Number(row.relative_to_average)) ? Number(row.relative_to_average) : score - average
  const kit = dimensionActionKit(name)
  const actions = profileStringList(row.next_actions || row.actions || row.recommendations || row.suggestions)
  const clues = profileStringList(row.evidence_clues || row.keywords || row.signals)
  const stage = profileText(row.stage) || (score >= 75 ? '优势已形成' : score >= 60 ? '基础可用' : '优先补证')
  const judgement = profileText(row.judgement) || `当前在八维能力中排第 ${Math.max(1, rank)}，比个人均值${delta >= 0 ? '高' : '低'} ${Math.abs(delta).toFixed(1)} 分。${score >= 75 ? '下一步应把优势转成可复用、可展示的成果。' : `距离 75 分稳定优势线还有 ${Math.max(0, 75 - score).toFixed(0)} 分。`}`
  const gap = profileText(row.development_gap || row.gap || row.risk) || `当前最需要补充的不是能力标签，而是能够证明“${kit.evidence}”的连续过程和结果。`
  return {
    name,
    score,
    stage,
    rank: Math.max(1, rank),
    average: Number(row.average_score) || average,
    delta,
    interpretation: profileText(row.interpretation || row.analysis || row.description) || '当前解释仍需结合更多项目、课程或实践材料继续校准。',
    judgement,
    gap,
    actions: (actions.length ? actions : kit.actions).slice(0, 3),
    expectedEvidence: profileText(row.expected_evidence || row.deliverable) || kit.evidence,
    successMetric: profileText(row.success_metric || row.metric || row.validation) || kit.metric,
    evidenceClues: clues,
    sources: profileDimensionEvidence(value, materialNames)
  }
}

export function classifyProfileMaterial(filename: string): ProfileMaterialCategory {
  const name = filename.toLowerCase()
  if (/成绩|transcript|score/.test(name) || /\.(xls|xlsx|csv)$/.test(name)) return '成绩'
  if (/证书|certificate|cert|奖状|资格/.test(name)) return '证书'
  if (/项目|project|作品|portfolio|github/.test(name)) return '项目'
  if (/简历|resume|cv/.test(name)) return '简历'
  return '补充材料'
}

export function formatProfileFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
