import type { PersonalityFingerprintSceneData } from '~/types/personality-fingerprint'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

const animationDuration = 1120
const pointCount = 128
const ringCount = 11

function clamp(value: number, minimum = 0, maximum = 1): number {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeOutCubic(value: number): number {
  return 1 - (1 - value) ** 3
}

function isSceneData(value: unknown): value is PersonalityFingerprintSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<PersonalityFingerprintSceneData>
  return typeof candidate.seed === 'number' && typeof candidate.mbti === 'string' && Array.isArray(candidate.axes)
}

function fallbackData(): PersonalityFingerprintSceneData {
  return {
    mbti: 'INTJ', mode: 'signature', seed: 1, signatureId: '0000001', animationRevision: 0,
    axes: [],
    traits: { energyDirection: 0, exploration: .5, decisionEdge: .5, structure: .5 }
  }
}

function seedUnit(seed: number, offset: number): number {
  let value = (seed + Math.imul(offset + 1, 0x9e3779b1)) >>> 0
  value ^= value >>> 16
  value = Math.imul(value, 0x7feb352d)
  value ^= value >>> 15
  value = Math.imul(value, 0x846ca68b)
  value ^= value >>> 16
  return (value >>> 0) / 4294967295
}

export const createPersonalityFingerprintScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : fallbackData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let animationStartedAt = performance.now()
  let animating = !reducedMotion && data.animationRevision > 0
  let failed = false
  let setupComplete = false

  const p5Instance = new P5((p: any) => {
    const geometry = () => {
      const compact = p.width < 330
      const radius = Math.max(76, Math.min(p.width * .31, p.height * .34, 132))
      return { centerX: p.width / 2, centerY: p.height / 2 + 2, radius, compact }
    }

    const progress = () => animating
      ? easeOutCubic(clamp((performance.now() - animationStartedAt) / animationDuration))
      : 1

    const themeColors = () => {
      const styles = getComputedStyle(options.host)
      return {
        text: styles.getPropertyValue('--ui-text').trim() || '#e2e8f0',
        muted: styles.getPropertyValue('--ui-text-muted').trim() || '#94a3b8',
        primary: styles.getPropertyValue('--ui-primary').trim() || '#38bdf8'
      }
    }

    const axisInfluence = (angle: number) => {
      if (!data.axes.length) return .68
      let weighted = 0
      let total = 0
      data.axes.forEach((axis, index) => {
        const axisAngle = -Math.PI / 2 + index * Math.PI / 2
        const weight = Math.max(0, Math.cos(angle - axisAngle)) ** 4 + .035
        const strength = Math.max(axis.leftScore, axis.rightScore) / 100
        weighted += (.48 + strength * .45) * weight
        total += weight
      })
      return weighted / total
    }

    const pointAt = (angle: number, ring: number) => {
      const { centerX, centerY, radius } = geometry()
      const ringScale = .22 + ring / (ringCount - 1) * .78
      const phaseA = seedUnit(data.seed, ring * 3) * Math.PI * 2
      const phaseB = seedUnit(data.seed, ring * 3 + 1) * Math.PI * 2
      const exploration = data.traits.exploration
      const edge = data.traits.decisionEdge
      const structure = data.traits.structure
      const swirl = data.traits.energyDirection * (.035 + ring * .0017)
      const harmonic =
        Math.sin(angle * (3 + Math.round(exploration * 3)) + phaseA) * (.018 + exploration * .032) +
        Math.sin(angle * 2 + phaseB) * (.012 + (1 - structure) * .026) +
        Math.cos(angle * 4 - phaseA * .45) * edge * .018
      const angular = angle + swirl
      const radial = radius * ringScale * axisInfluence(angle) * (1 + harmonic)
      const verticalScale = .9 + structure * .08
      return {
        x: centerX + Math.cos(angular) * radial,
        y: centerY + Math.sin(angular) * radial * verticalScale
      }
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof themeColors>) => {
      const { centerX, centerY, radius } = geometry()
      ctx.clearRect(0, 0, p.width, p.height)
      const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius * 1.5)
      glow.addColorStop(0, 'rgba(56, 189, 248, .095)')
      glow.addColorStop(.62, 'rgba(129, 140, 248, .035)')
      glow.addColorStop(1, 'rgba(15, 23, 42, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(0, 0, p.width, p.height)
    }

    const drawGuides = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof themeColors>) => {
      const { centerX, centerY, radius } = geometry()
      ctx.save()
      ctx.strokeStyle = 'rgba(148, 163, 184, .13)'
      ctx.lineWidth = 1
      for (let index = 0; index < 4; index += 1) {
        const angle = -Math.PI / 2 + index * Math.PI / 2
        ctx.beginPath()
        ctx.moveTo(centerX + Math.cos(angle) * radius * .16, centerY + Math.sin(angle) * radius * .16)
        ctx.lineTo(centerX + Math.cos(angle) * radius * 1.04, centerY + Math.sin(angle) * radius * 1.04)
        ctx.stroke()
      }
      ctx.restore()
    }

    const drawRings = (ctx: CanvasRenderingContext2D, amount: number, colors: ReturnType<typeof themeColors>) => {
      for (let ring = 0; ring < ringCount; ring += 1) {
        const delayed = clamp((amount - ring * .025) / (1 - ringCount * .025))
        const visiblePoints = Math.max(2, Math.floor(pointCount * delayed))
        const hueMix = ring / Math.max(1, ringCount - 1)
        ctx.save()
        ctx.strokeStyle = hueMix > .58 ? 'rgba(167, 139, 250, .72)' : colors.primary
        ctx.lineWidth = ring === ringCount - 1 ? 1.65 : .85 + ring * .035
        ctx.shadowColor = colors.primary
        ctx.shadowBlur = ring === ringCount - 1 ? 8 : 2
        ctx.globalAlpha = hueMix > .58 ? .62 : .45 + ring / ringCount * .42
        ctx.beginPath()
        for (let point = 0; point <= visiblePoints; point += 1) {
          const direction = data.traits.energyDirection < 0 ? -1 : 1
          const angle = direction * (point / pointCount * Math.PI * 2) - Math.PI / 2
          const position = pointAt(angle, ring)
          if (point === 0) ctx.moveTo(position.x, position.y)
          else ctx.lineTo(position.x, position.y)
        }
        if (visiblePoints >= pointCount) ctx.closePath()
        ctx.stroke()
        ctx.restore()
      }
    }

    const drawTrace = (ctx: CanvasRenderingContext2D, amount: number, colors: ReturnType<typeof themeColors>) => {
      if (!animating || amount >= 1) return
      const angle = (data.traits.energyDirection < 0 ? -1 : 1) * amount * Math.PI * 2 - Math.PI / 2
      const position = pointAt(angle, ringCount - 1)
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      ctx.fillStyle = colors.primary
      ctx.shadowColor = colors.primary
      ctx.shadowBlur = 14
      ctx.beginPath()
      ctx.arc(position.x, position.y, 2.2, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }

    const drawLabels = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof themeColors>) => {
      const { centerX, centerY, radius, compact } = geometry()
      data.axes.forEach((axis, index) => {
        const angle = -Math.PI / 2 + index * Math.PI / 2
        const labelRadius = radius + (compact ? 18 : 23)
        const x = centerX + Math.cos(angle) * labelRadius
        const y = centerY + Math.sin(angle) * labelRadius
        ctx.save()
        ctx.textAlign = Math.cos(angle) > .3 ? 'left' : Math.cos(angle) < -.3 ? 'right' : 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = colors.text
        ctx.font = `700 ${compact ? 10 : 11}px system-ui, sans-serif`
        ctx.fillText(axis.dominant, x, y)
        ctx.restore()
      })
      ctx.save()
      ctx.fillStyle = colors.text
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.font = `700 ${compact ? 20 : 23}px system-ui, sans-serif`
      ctx.fillText(data.mbti, centerX, centerY - 4)
      ctx.fillStyle = colors.muted
      ctx.font = `500 ${compact ? 7 : 8}px ui-monospace, monospace`
      ctx.fillText(data.signatureId, centerX, centerY + 14)
      ctx.restore()
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const amount = progress()
        const colors = themeColors()
        drawBackdrop(ctx, colors)
        drawGuides(ctx, colors)
        drawRings(ctx, amount, colors)
        drawTrace(ctx, amount, colors)
        drawLabels(ctx, colors)
        if (animating && amount >= 1) {
          animating = false
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
      canvas.elt.classList.add('personality-fingerprint-canvas')
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

  const replay = () => {
    animationStartedAt = performance.now()
    animating = active && !reducedMotion
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : fallbackData()
      const changed = next.seed !== data.seed || next.mbti !== data.mbti || next.animationRevision !== data.animationRevision
      data = next
      if (changed && next.animationRevision > 0) replay()
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
      if (reducedMotion) animating = false
      syncLoop()
    },
    resetView: replay,
    destroy() {
      p5Instance.remove()
    }
  }
}
