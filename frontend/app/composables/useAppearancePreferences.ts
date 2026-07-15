export type ThemePreference = 'system' | 'light' | 'dark'
export type HuePreference = string
export type ThemeSwitchOrigin = { x: number, y: number }

export type AppearancePreferences = {
  theme: ThemePreference
  hue: HuePreference
}

const LOCAL_THEME_KEY = 'theme'
const LOCAL_HUE_KEY = 'hue'

export const themePreferenceItems: Array<{ label: string, value: ThemePreference, icon: string }> = [
  { label: '跟随系统', value: 'system', icon: 'i-lucide-monitor' },
  { label: '浅色', value: 'light', icon: 'i-lucide-sun' },
  { label: '深色', value: 'dark', icon: 'i-lucide-moon' }
]

export const huePreferenceItems: Array<{ label: string, value: HuePreference, class: string }> = [
  { label: '青', value: '192', class: 'bg-cyan-500' },
  { label: '蓝', value: '220', class: 'bg-blue-500' },
  { label: '旧蓝', value: '230', class: 'bg-indigo-500' },
  { label: '紫', value: '270', class: 'bg-violet-500' },
  { label: '绿', value: '150', class: 'bg-emerald-500' }
]

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark'
}

export function isHuePreference(value: unknown): value is HuePreference {
  const number = Number.parseInt(String(value), 10)
  return Number.isFinite(number) && number >= 0 && number <= 360
}

export function normalizeThemePreference(value: unknown, fallback: ThemePreference = 'system'): ThemePreference {
  return isThemePreference(value) ? value : fallback
}

export function normalizeHuePreference(value: unknown, fallback: HuePreference = '192'): HuePreference {
  if (!isHuePreference(value)) return fallback
  return String(Math.round(Number(value)))
}

function resolveThemeIsDark(theme: ThemePreference) {
  if (!import.meta.client) return theme === 'dark'
  if (theme === 'system') return window.matchMedia('(prefers-color-scheme: dark)').matches
  return theme === 'dark'
}

function setThemeRevealOrigin(origin?: ThemeSwitchOrigin) {
  if (!import.meta.client) return
  const root = document.documentElement
  if (origin) {
    const radius = Math.hypot(
      Math.max(origin.x, window.innerWidth - origin.x),
      Math.max(origin.y, window.innerHeight - origin.y)
    )
    root.style.setProperty('--theme-x', `${origin.x}px`)
    root.style.setProperty('--theme-y', `${origin.y}px`)
    root.style.setProperty('--theme-r', `${radius}px`)
  } else {
    root.style.setProperty('--theme-x', '50vw')
    root.style.setProperty('--theme-y', '50vh')
    root.style.setProperty('--theme-r', '150vmax')
  }
}

function clearThemeRevealOrigin() {
  if (!import.meta.client) return
  const root = document.documentElement
  root.style.removeProperty('--theme-x')
  root.style.removeProperty('--theme-y')
  root.style.removeProperty('--theme-r')
}

function originFromEvent(event?: MouseEvent | Event): ThemeSwitchOrigin | undefined {
  const currentTarget = event?.currentTarget
  if (!(currentTarget instanceof HTMLElement)) return undefined
  const rect = currentTarget.getBoundingClientRect()
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

export function useAppearancePreferences() {
  const colorMode = useColorMode()
  const theme = useState<ThemePreference>('pathfy-appearance-theme', () => 'system')
  const hue = useState<HuePreference>('pathfy-appearance-hue', () => '192')

  function applyTheme(value: unknown, options: { origin?: ThemeSwitchOrigin, transition?: boolean } = {}) {
    const next = normalizeThemePreference(value)
    theme.value = next
    if (import.meta.client) localStorage.setItem(LOCAL_THEME_KEY, next)
    if (!import.meta.client) return Promise.resolve()

    const root = document.documentElement
    const targetIsDark = resolveThemeIsDark(next)
    const expectedDataTheme = targetIsDark ? 'github-dark' : 'github-light'
    const needsThemeChange = root.classList.contains('dark') !== targetIsDark
    const needsDataThemeChange = root.getAttribute('data-theme') !== expectedDataTheme

    const performThemeChange = () => {
      colorMode.preference = next
      root.classList.toggle('dark', targetIsDark)
      root.setAttribute('data-theme', expectedDataTheme)
    }

    if (!options.transition || (!needsThemeChange && !needsDataThemeChange)) {
      performThemeChange()
      return Promise.resolve()
    }

    setThemeRevealOrigin(options.origin)

    const finishTransition = () => {
      root.classList.remove('is-theme-transitioning', 'use-view-transition')
      clearThemeRevealOrigin()
    }

    const transitionDocument = document as Document & {
      startViewTransition?: (callback: () => void) => { finished: Promise<unknown> }
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (needsThemeChange && transitionDocument.startViewTransition && !prefersReducedMotion) {
      root.classList.add('is-theme-transitioning', 'use-view-transition')
      const transition = transitionDocument.startViewTransition(performThemeChange)
      return new Promise<void>((resolve) => {
        const timer = window.setTimeout(() => {
          finishTransition()
          resolve()
        }, 1200)
        transition.finished.finally(() => {
          window.clearTimeout(timer)
          finishTransition()
          resolve()
        })
      })
    }

    if (needsThemeChange) root.classList.add('is-theme-transitioning')
    performThemeChange()
    return new Promise<void>((resolve) => {
      window.setTimeout(() => {
        root.classList.remove('is-theme-transitioning')
        clearThemeRevealOrigin()
        resolve()
      }, 420)
    })
  }

  function toggleLightDark(event?: MouseEvent | Event) {
    const isDark = import.meta.client
      ? document.documentElement.classList.contains('dark')
      : theme.value === 'dark'
    return applyTheme(isDark ? 'light' : 'dark', { origin: originFromEvent(event), transition: true })
  }

  function applyHue(value: unknown) {
    const next = normalizeHuePreference(value)
    hue.value = next
    if (!import.meta.client) return
    localStorage.setItem(LOCAL_HUE_KEY, next)
    document.documentElement.style.setProperty('--pathfy-hue', next)
    document.documentElement.style.setProperty('--hue', next)
    document.documentElement.dataset.hue = next
  }

  function applyPreferences(preferences?: Partial<AppearancePreferences> | null) {
    applyTheme(preferences?.theme)
    applyHue(preferences?.hue)
  }

  function loadLocal() {
    if (!import.meta.client) return
    applyTheme(localStorage.getItem(LOCAL_THEME_KEY))
    applyHue(localStorage.getItem(LOCAL_HUE_KEY))
  }

  function localPatch(): Partial<AppearancePreferences> {
    if (!import.meta.client) return {}
    const patch: Partial<AppearancePreferences> = {}
    const localTheme = localStorage.getItem(LOCAL_THEME_KEY)
    const localHue = localStorage.getItem(LOCAL_HUE_KEY)
    if (isThemePreference(localTheme)) patch.theme = localTheme
    if (isHuePreference(localHue)) patch.hue = localHue
    return patch
  }

  function snapshot(): AppearancePreferences {
    return { theme: theme.value, hue: hue.value }
  }

  return {
    theme,
    hue,
    themeItems: themePreferenceItems,
    hueItems: huePreferenceItems,
    applyTheme,
    toggleLightDark,
    applyHue,
    applyPreferences,
    loadLocal,
    localPatch,
    snapshot,
    originFromEvent
  }
}
