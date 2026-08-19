import type { AuthJourneyMode, AuthJourneyState } from '~/types/auth-journey'
import { journeyConfig } from '~/components/auth-journey/sketch/config'

let journeyRun = 0
let errorTimer: ReturnType<typeof setTimeout> | undefined
const timelineTimers = new Set<ReturnType<typeof setTimeout>>()

function clearTimers() {
  if (errorTimer) clearTimeout(errorTimer)
  errorTimer = undefined
  for (const timer of timelineTimers) clearTimeout(timer)
  timelineTimers.clear()
}

export function useAuthJourney() {
  const state = useState<AuthJourneyState>('auth-journey-state', () => 'idle')
  const mode = useState<AuthJourneyMode>('auth-journey-mode', () => 'login')
  const identityActive = useState('auth-journey-identity-active', () => false)
  const passwordReady = useState('auth-journey-password-ready', () => false)
  const successStartedAt = useState('auth-journey-success-started-at', () => 0)
  const errorStartedAt = useState('auth-journey-error-started-at', () => 0)
  const liveMessage = useState('auth-journey-live-message', () => '')

  const isTransitioning = computed(() => [
    'success-arm', 'sprint', 'impact', 'fracture', 'branch', 'reveal'
  ].includes(state.value))
  const isRevealing = computed(() => state.value === 'branch' || state.value === 'reveal')

  function reset(nextMode: AuthJourneyMode = mode.value) {
    journeyRun += 1
    clearTimers()
    mode.value = nextMode
    identityActive.value = false
    passwordReady.value = false
    successStartedAt.value = 0
    errorStartedAt.value = 0
    liveMessage.value = ''
    state.value = 'cruise'
  }

  function setMode(nextMode: AuthJourneyMode) {
    if (isTransitioning.value) return
    if (mode.value !== nextMode || state.value === 'idle' || state.value === 'done') reset(nextMode)
    else state.value = 'cruise'
  }

  function setInputProgress(identity: boolean, password: boolean) {
    identityActive.value = identity
    passwordReady.value = password
  }

  function startSubmitting() {
    journeyRun += 1
    clearTimers()
    state.value = 'submitting'
    liveMessage.value = '正在连接你的路径'
  }

  function playError() {
    journeyRun += 1
    clearTimers()
    errorStartedAt.value = import.meta.client ? performance.now() : 0
    state.value = 'error'
    liveMessage.value = '连接未完成，请检查提示后重试'
    if (!import.meta.client) return
    errorTimer = setTimeout(() => {
      state.value = 'cruise'
      liveMessage.value = ''
    }, 720)
  }

  function playSuccess({ destination }: { destination: string }) {
    journeyRun += 1
    const run = journeyRun
    clearTimers()
    successStartedAt.value = import.meta.client ? performance.now() : 0
    state.value = 'success-arm'
    liveMessage.value = mode.value === 'login'
      ? '登录成功，正在进入 PathFy 工作台'
      : '注册成功，正在为你展开职业路径'

    if (!import.meta.client) return Promise.resolve()

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const schedule = (delay: number, callback: () => void) => {
      const timer = setTimeout(() => {
        timelineTimers.delete(timer)
        if (journeyRun === run) callback()
      }, delay)
      timelineTimers.add(timer)
    }

    return new Promise<void>((resolve) => {
      if (reducedMotion) {
        schedule(70, () => { state.value = 'reveal'; void navigateTo(destination) })
        schedule(300, () => {
          state.value = 'done'
          liveMessage.value = ''
          resolve()
        })
        return
      }

      schedule(journeyConfig.sprint.returnMs, () => { state.value = 'sprint' })
      schedule(journeyConfig.sprint.sprintEndMs, () => { state.value = 'impact' })
      schedule(journeyConfig.sprint.impactEndMs, () => { state.value = 'fracture' })
      schedule(journeyConfig.routes.startMs, () => { state.value = 'branch' })
      schedule(journeyConfig.reveal.navigateAt, () => {
        void navigateTo(destination)
      })
      schedule(journeyConfig.reveal.finishAt, () => {
        state.value = 'done'
        liveMessage.value = ''
        resolve()
      })
    })
  }

  return {
    state,
    mode,
    identityActive,
    passwordReady,
    successStartedAt,
    errorStartedAt,
    liveMessage,
    isTransitioning,
    isRevealing,
    reset,
    setMode,
    setInputProgress,
    startSubmitting,
    playError,
    playSuccess
  }
}
