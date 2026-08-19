export type AuthJourneyMode = 'login' | 'register'

export type AuthJourneyState =
  | 'idle'
  | 'cruise'
  | 'submitting'
  | 'success-arm'
  | 'sprint'
  | 'impact'
  | 'fracture'
  | 'branch'
  | 'reveal'
  | 'done'
  | 'error'

export interface AuthJourneySnapshot {
  state: AuthJourneyState
  mode: AuthJourneyMode
  identityActive: boolean
  passwordReady: boolean
  successStartedAt: number
  errorStartedAt: number
}
