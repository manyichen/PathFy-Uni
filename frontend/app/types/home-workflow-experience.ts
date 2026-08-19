export type HomeWorkflowStageKey = 'material' | 'profile' | 'match' | 'plan' | 'review'

export interface HomeWorkflowStage {
  key: HomeWorkflowStageKey
  label: string
  hint: string
  description: string
  to: string
  color: string
}

export interface HomeWorkflowEdge {
  id: string
  source: HomeWorkflowStageKey
  target: HomeWorkflowStageKey
  kind: 'forward' | 'feedback'
}

export interface HomeWorkflowSceneData {
  stages: HomeWorkflowStage[]
  edges: HomeWorkflowEdge[]
  activeIndex: number
  activeStage: HomeWorkflowStage
  animationRevision: number
  transitionKey: string
}

export type HomeWorkflowExperienceEventName = 'open' | 'stage' | 'complete' | 'exit'

export interface HomeWorkflowExperienceEventDetail {
  name: HomeWorkflowExperienceEventName
  stage?: HomeWorkflowStageKey
  occurredAt: string
}
