import type {
  HomeWorkflowExperienceEventDetail,
  HomeWorkflowExperienceEventName,
  HomeWorkflowStageKey
} from '~/types/home-workflow-experience'

export const homeWorkflowExperienceEvent = 'pathfy:workflow-experience'

export function emitHomeWorkflowExperienceEvent(name: HomeWorkflowExperienceEventName, stage?: HomeWorkflowStageKey) {
  if (!import.meta.client) return
  const detail: HomeWorkflowExperienceEventDetail = { name, stage, occurredAt: new Date().toISOString() }
  window.dispatchEvent(new CustomEvent<HomeWorkflowExperienceEventDetail>(homeWorkflowExperienceEvent, { detail }))
}
