import type {
  HomeWorkflowEdge,
  HomeWorkflowSceneData,
  HomeWorkflowStage,
  HomeWorkflowStageKey
} from '~/types/home-workflow-experience'

const stages: HomeWorkflowStage[] = [
  { key: 'material', label: '材料', hint: '建立证据', description: '整理简历、项目、竞赛和作品，形成可追溯的能力材料。', to: '/profile', color: '#22d3ee' },
  { key: 'profile', label: '画像', hint: '识别能力', description: '把材料映射到八维能力，保留分值与证据来源。', to: '/profile', color: '#2dd4bf' },
  { key: 'match', label: '匹配', hint: '比较岗位', description: '用同一组能力维度比较真实岗位要求、优势和差距。', to: '/match', color: '#818cf8' },
  { key: 'plan', label: '计划', hint: '拆解行动', description: '把目标岗位与能力差距拆成分阶段行动和可验证任务。', to: '/report', color: '#c084fc' },
  { key: 'review', label: '复盘', hint: '校准路线', description: '提交月度结果，根据真实完成情况继续修正计划。', to: '/report#review', color: '#f59e0b' }
]

const edges: HomeWorkflowEdge[] = [
  { id: 'material-profile', source: 'material', target: 'profile', kind: 'forward' },
  { id: 'profile-match', source: 'profile', target: 'match', kind: 'forward' },
  { id: 'match-plan', source: 'match', target: 'plan', kind: 'forward' },
  { id: 'plan-review', source: 'plan', target: 'review', kind: 'forward' },
  { id: 'review-profile', source: 'review', target: 'profile', kind: 'feedback' }
]

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function buildHomeWorkflowSceneData(source: { activeStage?: HomeWorkflowStageKey; activeIndex?: number; animationRevision?: number } = {}): HomeWorkflowSceneData {
  const requestedIndex = source.activeStage ? stages.findIndex(stage => stage.key === source.activeStage) : Math.floor(number(source.activeIndex))
  const activeIndex = Math.max(0, Math.min(stages.length - 1, requestedIndex < 0 ? 0 : requestedIndex))
  const animationRevision = Math.max(0, Math.floor(number(source.animationRevision)))
  return {
    stages: stages.map(stage => ({ ...stage })),
    edges: edges.map(edge => ({ ...edge })),
    activeIndex,
    activeStage: { ...stages[activeIndex]! },
    animationRevision,
    transitionKey: `${stages[activeIndex]!.key}:${animationRevision}`
  }
}
