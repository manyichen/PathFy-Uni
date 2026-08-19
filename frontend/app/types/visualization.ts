export type P5SceneStatus = 'idle' | 'loading' | 'ready' | 'failed'

export interface P5SceneSize {
  width: number
  height: number
  pixelRatio: number
}

export interface P5SceneRuntime<TData = unknown> {
  update: (data: TData) => void
  resize: (size: P5SceneSize) => void
  setActive: (active: boolean) => void
  setReducedMotion?: (reducedMotion: boolean) => void
  resetView?: () => void
  destroy: () => void
}

export interface P5SceneErrorContext {
  recoverable?: boolean
  phase?: 'create' | 'render' | 'update' | 'resize' | 'interaction'
}

export interface P5SceneFactoryOptions<TData = unknown, TSelection = unknown> {
  host: HTMLElement
  data: TData
  size: P5SceneSize
  reducedMotion: boolean
  onSelect: (selection: TSelection) => void
  onError: (error: unknown, context?: P5SceneErrorContext) => void
}

export type P5SceneFactory<TData = unknown, TSelection = unknown> = (
  options: P5SceneFactoryOptions<TData, TSelection>
) => Promise<P5SceneRuntime<TData>>
