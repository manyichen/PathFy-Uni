import type { MatchTensionDimension, MatchTensionSceneData, MatchTensionStatus } from '~/types/match-tension'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface Point { x: number; y: number }

const transitionDuration = 1050
const statusColors: Record<MatchTensionStatus, string> = {
  deficit: '#fb7185',
  balanced: '#60a5fa',
  surplus: '#2dd4bf'
}

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeOutCubic(value: number) {
  return 1 - (1 - value) ** 3
}

function axisAngle(index: number, count: number) {
  // Keep the same orientation as CapabilityRadar/ECharts: theory at the top,
  // then cross, practice, digital... in counter-clockwise order.
  return -Math.PI / 2 - index / Math.max(1, count) * Math.PI * 2
}

function emptyData(): MatchTensionSceneData {
  return {
    jobId: '', jobTitle: '', transitionKey: '', animationRevision: 0, dimensions: [],
    summary: { deficitCount: 0, balancedCount: 0, surplusCount: 0, averageAbsoluteGap: 0 }
  }
}

function isSceneData(value: unknown): value is MatchTensionSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<MatchTensionSceneData>
  return Array.isArray(candidate.dimensions) && typeof candidate.transitionKey === 'string'
}

function neutralData(data: MatchTensionSceneData): MatchTensionSceneData {
  return {
    ...data,
    dimensions: data.dimensions.map(item => ({
      ...item,
      requirementScore: item.studentScore,
      gap: 0,
      intensity: .08,
      status: 'balanced'
    }))
  }
}

function dimensionFrom(data: MatchTensionSceneData, id: string): MatchTensionDimension | undefined {
  return data.dimensions.find(item => item.id === id)
}

export const createMatchTensionScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : emptyData()
  let previous = neutralData(data)
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let animationStartedAt = performance.now()
  let animating = !reducedMotion
  let failed = false
  let setupComplete = false

  const p5Instance = new P5((p: any) => {
    const geometry = () => {
      const compact = p.width < 360
      const center = { x: p.width / 2, y: p.height / 2 + (compact ? 6 : 10) }
      const radius = Math.max(72, Math.min(p.width * .29, p.height * .3, 126))
      return { center, radius, compact }
    }

    const axisPoint = (index: number, score: number): Point => {
      const { center, radius } = geometry()
      const angle = axisAngle(index, data.dimensions.length)
      const distance = 22 + clamp(score / 100) * (radius - 22)
      return { x: center.x + Math.cos(angle) * distance, y: center.y + Math.sin(angle) * distance }
    }

    const ringPoint = (index: number, distance: number): Point => {
      const { center } = geometry()
      const angle = axisAngle(index, data.dimensions.length)
      return { x: center.x + Math.cos(angle) * distance, y: center.y + Math.sin(angle) * distance }
    }

    const progress = () => animating
      ? easeOutCubic(clamp((performance.now() - animationStartedAt) / transitionDuration))
      : 1

    const interpolated = (item: MatchTensionDimension, amount: number): MatchTensionDimension => {
      const from = dimensionFrom(previous, item.id) || item
      const studentScore = from.studentScore + (item.studentScore - from.studentScore) * amount
      const requirementScore = from.requirementScore + (item.requirementScore - from.requirementScore) * amount
      return { ...item, studentScore, requirementScore, gap: studentScore - requirementScore }
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const { center, radius } = geometry()
      const glow = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, radius * 1.65)
      glow.addColorStop(0, 'rgba(96, 165, 250, .08)')
      glow.addColorStop(.55, 'rgba(129, 140, 248, .035)')
      glow.addColorStop(1, 'rgba(15, 23, 42, .02)')
      ctx.fillStyle = glow
      ctx.fillRect(0, 0, p.width, p.height)
    }

    const drawGrid = (ctx: CanvasRenderingContext2D) => {
      const { center, radius } = geometry()
      ctx.save()
      ctx.strokeStyle = 'rgba(148, 163, 184, .14)'
      ctx.lineWidth = 1
      for (const ratio of [.25, .5, .75, 1]) {
        ctx.beginPath()
        ctx.arc(center.x, center.y, 22 + (radius - 22) * ratio, 0, Math.PI * 2)
        ctx.stroke()
      }
      data.dimensions.forEach((_, index) => {
        const end = ringPoint(index, radius)
        ctx.beginPath()
        ctx.moveTo(center.x, center.y)
        ctx.lineTo(end.x, end.y)
        ctx.stroke()
      })
      ctx.restore()
    }

    const drawPolygon = (
      ctx: CanvasRenderingContext2D,
      dimensions: MatchTensionDimension[],
      key: 'studentScore' | 'requirementScore',
      stroke: string,
      fill: string
    ) => {
      if (!dimensions.length) return
      ctx.save()
      ctx.strokeStyle = stroke
      ctx.fillStyle = fill
      ctx.lineWidth = 1.4
      ctx.beginPath()
      dimensions.forEach((item, index) => {
        const point = axisPoint(index, item[key])
        if (index === 0) ctx.moveTo(point.x, point.y)
        else ctx.lineTo(point.x, point.y)
      })
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
      ctx.restore()
    }

    const drawTensions = (ctx: CanvasRenderingContext2D, dimensions: MatchTensionDimension[], amount: number) => {
      dimensions.forEach((item, index) => {
        const studentPoint = axisPoint(index, item.studentScore)
        const requirementPoint = axisPoint(index, item.requirementScore)
        const color = statusColors[item.status]
        const intensity = .1 + item.intensity * .9
        ctx.save()
        ctx.strokeStyle = color
        ctx.globalAlpha = .46 + intensity * .4
        ctx.lineWidth = 1.2 + intensity * 2.2
        ctx.shadowColor = color
        ctx.shadowBlur = 4 + intensity * 9
        ctx.beginPath()
        ctx.moveTo(studentPoint.x, studentPoint.y)
        ctx.lineTo(requirementPoint.x, requirementPoint.y)
        ctx.stroke()
        if (animating && Math.abs(item.gap) >= 4) {
          const wave = (Math.sin(p.frameCount * .16 + index * 1.7) + 1) / 2
          const sparkAmount = item.status === 'deficit' ? wave : 1 - wave
          const x = studentPoint.x + (requirementPoint.x - studentPoint.x) * sparkAmount
          const y = studentPoint.y + (requirementPoint.y - studentPoint.y) * sparkAmount
          ctx.globalCompositeOperation = 'lighter'
          ctx.globalAlpha = Math.sin(amount * Math.PI) * .85
          ctx.fillStyle = color
          ctx.beginPath()
          ctx.arc(x, y, 1.5 + intensity * 1.7, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.shadowBlur = 0
        ctx.globalAlpha = 1
        ctx.fillStyle = '#22d3ee'
        ctx.beginPath()
        ctx.arc(studentPoint.x, studentPoint.y, 3, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = '#a78bfa'
        ctx.fillStyle = 'rgba(167, 139, 250, .2)'
        ctx.lineWidth = 1.2
        ctx.beginPath()
        ctx.arc(requirementPoint.x, requirementPoint.y, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        ctx.restore()
      })
    }

    const drawLabels = (ctx: CanvasRenderingContext2D, dimensions: MatchTensionDimension[]) => {
      const { center, radius, compact } = geometry()
      const styles = getComputedStyle(options.host)
      const textColor = styles.getPropertyValue('--ui-text').trim() || '#e2e8f0'
      const muted = styles.getPropertyValue('--ui-text-muted').trim() || '#94a3b8'
      dimensions.forEach((item, index) => {
        const angle = axisAngle(index, dimensions.length)
        const labelRadius = radius + (compact ? 19 : 24)
        const x = center.x + Math.cos(angle) * labelRadius
        const y = center.y + Math.sin(angle) * labelRadius
        ctx.save()
        ctx.textAlign = Math.cos(angle) > .3 ? 'left' : Math.cos(angle) < -.3 ? 'right' : 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = textColor
        ctx.font = `600 ${compact ? 9 : 10}px system-ui, sans-serif`
        ctx.fillText(item.label, x, y - 5)
        ctx.fillStyle = muted
        ctx.font = `${compact ? 8 : 9}px system-ui, sans-serif`
        ctx.fillText(`${Math.round(item.studentScore)} / ${Math.round(item.requirementScore)}`, x, y + 7)
        ctx.restore()
      })
    }

    const drawCenter = (ctx: CanvasRenderingContext2D) => {
      const { center, compact } = geometry()
      ctx.save()
      ctx.fillStyle = 'rgba(15, 23, 42, .58)'
      ctx.strokeStyle = 'rgba(125, 211, 252, .3)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.arc(center.x, center.y, compact ? 19 : 22, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
      ctx.fillStyle = 'rgba(226, 232, 240, .9)'
      ctx.font = `700 ${compact ? 7 : 8}px system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('能力 ↔ 要求', center.x, center.y)
      ctx.restore()
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const amount = progress()
        const dimensions = data.dimensions.map(item => interpolated(item, amount))
        drawBackdrop(ctx)
        drawGrid(ctx)
        drawPolygon(ctx, dimensions, 'requirementScore', 'rgba(167, 139, 250, .72)', 'rgba(167, 139, 250, .055)')
        drawPolygon(ctx, dimensions, 'studentScore', 'rgba(34, 211, 238, .82)', 'rgba(34, 211, 238, .07)')
        drawTensions(ctx, dimensions, amount)
        drawCenter(ctx)
        drawLabels(ctx, dimensions)
        if (animating && amount >= 1) {
          animating = false
          previous = data
          p.noLoop()
        }
      } catch (error) {
        failed = true
        p.noLoop()
        options.onError(error)
      }
    }

    p.setup = () => {
      p.pixelDensity(size.pixelRatio)
      const canvas = p.createCanvas(size.width, size.height)
      canvas.elt.classList.add('match-tension-canvas')
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      p.frameRate(30)
      setupComplete = true
      if (!animating) p.noLoop()
    }
    p.draw = render
  }, options.host)

  const syncLoop = () => {
    if (active && animating && !reducedMotion) p5Instance.loop()
    else {
      p5Instance.noLoop()
      p5Instance.redraw()
    }
  }

  const beginTransition = (from: MatchTensionSceneData) => {
    previous = from
    animationStartedAt = performance.now()
    animating = active && !reducedMotion
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : emptyData()
      const changedJob = next.transitionKey !== data.transitionKey
      const replayed = next.animationRevision !== data.animationRevision
      const from = replayed && !changedJob ? neutralData(next) : data
      data = next
      if (changedJob || replayed) beginTransition(from)
      else p5Instance.redraw()
    },
    resize(nextSize: P5SceneSize) {
      size = nextSize
      if (!setupComplete) return
      p5Instance.pixelDensity(size.pixelRatio)
      p5Instance.resizeCanvas(size.width, size.height)
      p5Instance.redraw()
    },
    setActive(nextActive: boolean) {
      active = nextActive
      syncLoop()
    },
    setReducedMotion(nextReducedMotion: boolean) {
      reducedMotion = nextReducedMotion
      if (reducedMotion) {
        animating = false
        previous = data
      }
      syncLoop()
    },
    resetView() {
      beginTransition(neutralData(data))
    },
    destroy() {
      p5Instance.remove()
    }
  }
}
