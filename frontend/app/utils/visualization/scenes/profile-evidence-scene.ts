import type { CapabilityDimension } from '~/types/capability'
import type { ProfileEvidenceFlow, ProfileEvidenceSceneData } from '~/types/profile-evidence'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface Point { x: number; y: number }
interface EvidenceParticle {
  flowIndex: number
  delay: number
  duration: number
  size: number
  bend: number
  phase: number
}

const dimensionColors: Record<CapabilityDimension, string> = {
  cap_req_theory: '#60a5fa',
  cap_req_cross: '#818cf8',
  cap_req_practice: '#2dd4bf',
  cap_req_digital: '#22d3ee',
  cap_req_innovation: '#c084fc',
  cap_req_teamwork: '#34d399',
  cap_req_social: '#fb7185',
  cap_req_growth: '#fbbf24'
}

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeInOutCubic(value: number) {
  return value < .5 ? 4 * value ** 3 : 1 - (-2 * value + 2) ** 3 / 2
}

function seededRandom(seed: number) {
  let value = seed >>> 0
  return () => {
    value += 0x6D2B79F5
    let next = value
    next = Math.imul(next ^ next >>> 15, next | 1)
    next ^= next + Math.imul(next ^ next >>> 7, next | 61)
    return ((next ^ next >>> 14) >>> 0) / 4294967296
  }
}

function emptyData(): ProfileEvidenceSceneData {
  return {
    materials: [], dimensions: [], flows: [], mappingMode: 'overview', animationRevision: 0,
    summary: { materialCount: 0, dimensionCount: 0, explicitFlowCount: 0 }
  }
}

function isSceneData(value: unknown): value is ProfileEvidenceSceneData {
  if (!value || typeof value !== 'object') return false
  const data = value as Partial<ProfileEvidenceSceneData>
  return Array.isArray(data.materials) && Array.isArray(data.dimensions) && Array.isArray(data.flows)
}

function pointOnCurve(start: Point, control: Point, end: Point, amount: number): Point {
  const inverse = 1 - amount
  return {
    x: inverse * inverse * start.x + 2 * inverse * amount * control.x + amount * amount * end.x,
    y: inverse * inverse * start.y + 2 * inverse * amount * control.y + amount * amount * end.y
  }
}

function chooseWeightedFlow(flows: ProfileEvidenceFlow[], random: () => number) {
  const total = flows.reduce((sum, flow) => sum + Math.max(.02, flow.weight), 0)
  let cursor = random() * total
  for (let index = 0; index < flows.length; index += 1) {
    cursor -= Math.max(.02, flows[index]!.weight)
    if (cursor <= 0) return index
  }
  return Math.max(0, flows.length - 1)
}

function buildParticles(data: ProfileEvidenceSceneData): EvidenceParticle[] {
  if (!data.flows.length) return []
  const random = seededRandom(data.animationRevision * 7919 + data.materials.length * 101 + 37)
  const count = Math.min(140, Math.max(48, data.materials.length * 14))
  return Array.from({ length: count }, (_, index) => ({
    flowIndex: chooseWeightedFlow(data.flows, random),
    delay: random() * 580 + index % 7 * 22,
    duration: 720 + random() * 520,
    size: .8 + random() * 1.7,
    bend: (random() - .5) * 74,
    phase: random() * Math.PI * 2
  }))
}

export const createProfileEvidenceScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : emptyData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let animationStartedAt = 0
  let animationRevision = data.animationRevision
  let animating = !reducedMotion
  let particles = buildParticles(data)
  let failed = false
  let setupComplete = false

  const p5Instance = new P5((p: any) => {
    const compact = () => p.width < 680
    const profileCenter = (): Point => compact()
      ? { x: p.width * .5, y: p.height * .62 }
      : { x: p.width * .72, y: p.height * .51 }
    const profileRadius = () => ({
      x: compact() ? Math.min(150, p.width * .35) : Math.min(225, p.width * .22),
      y: compact() ? Math.min(132, p.height * .25) : Math.min(190, p.height * .34)
    })
    const materialPoint = (materialId: string): Point => {
      const index = Math.max(0, data.materials.findIndex(material => material.id === materialId))
      if (compact()) {
        const count = Math.max(1, data.materials.length)
        return { x: 34 + (p.width - 68) * ((index + .5) / count), y: 56 + (index % 2) * 22 }
      }
      const available = Math.max(240, p.height - 110)
      const gap = available / Math.max(1, data.materials.length)
      return { x: Math.min(116, p.width * .15), y: 62 + gap * (index + .5) }
    }
    const dimensionPoint = (dimensionId: CapabilityDimension): Point => {
      const index = Math.max(0, data.dimensions.findIndex(dimension => dimension.id === dimensionId))
      const angle = -Math.PI / 2 + index / Math.max(1, data.dimensions.length) * Math.PI * 2
      const center = profileCenter()
      const radius = profileRadius()
      return { x: center.x + Math.cos(angle) * radius.x, y: center.y + Math.sin(angle) * radius.y }
    }
    const flowGeometry = (flow: ProfileEvidenceFlow, bend = 0) => {
      const start = materialPoint(flow.materialId)
      const end = dimensionPoint(flow.dimension)
      const control = compact()
        ? { x: (start.x + end.x) / 2 + bend, y: start.y + (end.y - start.y) * .48 }
        : { x: start.x + (end.x - start.x) * .52, y: (start.y + end.y) / 2 + bend }
      return { start, control, end }
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createRadialGradient(p.width * .7, p.height * .5, 0, p.width * .7, p.height * .5, Math.max(p.width, p.height) * .65)
      gradient.addColorStop(0, 'rgba(34, 211, 238, .075)')
      gradient.addColorStop(.52, 'rgba(99, 102, 241, .025)')
      gradient.addColorStop(1, 'rgba(15, 23, 42, .11)')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, p.width, p.height)
    }

    const drawFlows = (ctx: CanvasRenderingContext2D, settled: number) => {
      data.flows.forEach(flow => {
        const geometry = flowGeometry(flow)
        const color = dimensionColors[flow.dimension]
        ctx.save()
        ctx.strokeStyle = color
        ctx.globalAlpha = (data.mappingMode === 'explicit' ? .2 : .1) + settled * (data.mappingMode === 'explicit' ? .14 : .08)
        ctx.lineWidth = .7 + flow.weight * 1.35
        if (flow.inferred) ctx.setLineDash([2, 7])
        ctx.beginPath()
        ctx.moveTo(geometry.start.x, geometry.start.y)
        ctx.quadraticCurveTo(geometry.control.x, geometry.control.y, geometry.end.x, geometry.end.y)
        ctx.stroke()
        ctx.restore()
      })
    }

    const drawProfileContour = (ctx: CanvasRenderingContext2D, settled: number) => {
      if (data.dimensions.length < 3) return
      const center = profileCenter()
      const outerPoints = data.dimensions.map(dimension => dimensionPoint(dimension.id))
      const contourPoints = data.dimensions.map((dimension, index) => {
        const outer = outerPoints[index]!
        const scoreRatio = .08 + clamp(dimension.score / 100) * .84
        const reveal = .12 + scoreRatio * easeInOutCubic(settled) * .88
        return {
          x: center.x + (outer.x - center.x) * reveal,
          y: center.y + (outer.y - center.y) * reveal
        }
      })
      const tracePolygon = (points: Point[]) => {
        ctx.beginPath()
        points.forEach((point, index) => index === 0
          ? ctx.moveTo(point.x, point.y)
          : ctx.lineTo(point.x, point.y))
        ctx.closePath()
      }

      ctx.save()
      for (const ratio of [.25, .5, .75, 1]) {
        const gridPoints = outerPoints.map(point => ({
          x: center.x + (point.x - center.x) * ratio,
          y: center.y + (point.y - center.y) * ratio
        }))
        tracePolygon(gridPoints)
        ctx.strokeStyle = ratio === 1 ? 'rgba(100, 116, 139, .3)' : 'rgba(100, 116, 139, .15)'
        ctx.lineWidth = ratio === 1 ? 1.1 : .75
        ctx.stroke()
      }
      outerPoints.forEach(point => {
        ctx.beginPath()
        ctx.moveTo(center.x, center.y)
        ctx.lineTo(point.x, point.y)
        ctx.strokeStyle = 'rgba(100, 116, 139, .18)'
        ctx.lineWidth = .75
        ctx.stroke()
      })

      const fill = ctx.createRadialGradient(center.x, center.y, 4, center.x, center.y, profileRadius().x)
      fill.addColorStop(0, 'rgba(45, 212, 191, .32)')
      fill.addColorStop(.58, 'rgba(34, 211, 238, .2)')
      fill.addColorStop(1, 'rgba(99, 102, 241, .14)')
      tracePolygon(contourPoints)
      ctx.fillStyle = fill
      ctx.fill()
      ctx.strokeStyle = 'rgba(13, 148, 136, .88)'
      ctx.lineWidth = compact() ? 2 : 2.6
      ctx.shadowColor = 'rgba(45, 212, 191, .45)'
      ctx.shadowBlur = 12
      ctx.stroke()
      ctx.shadowBlur = 0

      contourPoints.forEach((point, index) => {
        const dimension = data.dimensions[index]!
        ctx.beginPath()
        ctx.fillStyle = dimensionColors[dimension.id]
        ctx.arc(point.x, point.y, compact() ? 3 : 4, 0, Math.PI * 2)
        ctx.fill()
      })

      const average = data.dimensions.reduce((sum, dimension) => sum + dimension.score, 0) / data.dimensions.length
      ctx.beginPath()
      ctx.fillStyle = 'rgba(248, 250, 252, .94)'
      ctx.strokeStyle = 'rgba(13, 148, 136, .34)'
      ctx.lineWidth = 1.5
      ctx.arc(center.x, center.y, compact() ? 27 : 34, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
      ctx.fillStyle = '#0f766e'
      ctx.font = `800 ${compact() ? 13 : 16}px system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(`${Math.round(average)}`, center.x, center.y - 4)
      ctx.fillStyle = '#64748b'
      ctx.font = `600 ${compact() ? 7 : 9}px system-ui, sans-serif`
      ctx.fillText('综合均值', center.x, center.y + 11)
      ctx.restore()
    }

    const drawParticles = (ctx: CanvasRenderingContext2D, elapsed: number) => {
      particles.forEach(particle => {
        const flow = data.flows[particle.flowIndex]
        if (!flow) return
        const raw = clamp((elapsed - particle.delay) / particle.duration)
        if (raw <= 0 || raw >= 1) return
        const amount = easeInOutCubic(raw)
        const geometry = flowGeometry(flow, particle.bend)
        const point = pointOnCurve(geometry.start, geometry.control, geometry.end, amount)
        const color = dimensionColors[flow.dimension]
        ctx.save()
        ctx.globalCompositeOperation = 'lighter'
        ctx.globalAlpha = Math.sin(raw * Math.PI) * (.56 + (flow.confidence ?? .5) * .35)
        ctx.fillStyle = color
        ctx.shadowColor = color
        ctx.shadowBlur = 8 + particle.size * 3
        ctx.beginPath()
        ctx.arc(point.x, point.y + Math.sin(amount * 9 + particle.phase) * 2.2, particle.size, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      })
    }

    const drawMaterials = (ctx: CanvasRenderingContext2D, pulse: number) => {
      const textColor = getComputedStyle(options.host).getPropertyValue('--ui-text').trim() || '#e2e8f0'
      const muted = getComputedStyle(options.host).getPropertyValue('--ui-text-muted').trim() || '#94a3b8'
      data.materials.forEach((material) => {
        const point = materialPoint(material.id)
        const compactWidth = Math.max(54, Math.min(92, p.width / Math.max(4, data.materials.length) - 8))
        const width = compact() ? compactWidth : Math.min(170, Math.max(112, p.width * .19))
        const height = compact() ? 30 : 43
        ctx.save()
        ctx.translate(point.x, point.y)
        ctx.fillStyle = 'rgba(100, 116, 139, .1)'
        ctx.strokeStyle = 'rgba(148, 163, 184, .28)'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.roundRect(-width / 2, -height / 2, width, height, 8)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = '#dbeafe'
        ctx.globalAlpha = .75 + pulse * .2
        ctx.beginPath()
        ctx.arc(-width / 2 + 12, 0, 3 + material.weight * 2, 0, Math.PI * 2)
        ctx.fill()
        ctx.globalAlpha = 1
        ctx.fillStyle = textColor
        ctx.font = `600 ${compact() ? 9 : 11}px system-ui, sans-serif`
        ctx.textAlign = 'left'
        ctx.textBaseline = 'middle'
        const maxLength = compact() ? 5 : 12
        const label = material.name.length > maxLength ? `${material.name.slice(0, maxLength)}…` : material.name
        ctx.fillText(label, -width / 2 + 22, compact() ? 0 : -7)
        if (!compact()) {
          ctx.fillStyle = muted
          ctx.font = '9px system-ui, sans-serif'
          ctx.fillText(material.kind, -width / 2 + 22, 9)
        }
        ctx.restore()
      })
    }

    const drawDimensions = (ctx: CanvasRenderingContext2D, pulse: number) => {
      const textColor = getComputedStyle(options.host).getPropertyValue('--ui-text').trim() || '#e2e8f0'
      data.dimensions.forEach(dimension => {
        const point = dimensionPoint(dimension.id)
        const color = dimensionColors[dimension.id]
        const radius = compact() ? 8 : 10
        ctx.save()
        ctx.fillStyle = color
        ctx.strokeStyle = color
        ctx.shadowColor = color
        ctx.shadowBlur = 10 + pulse * 8
        ctx.globalAlpha = .88
        ctx.beginPath()
        ctx.arc(point.x, point.y, radius, 0, Math.PI * 2)
        ctx.fill()
        ctx.globalAlpha = .28
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(point.x, point.y, radius + 6 + pulse * 2, 0, Math.PI * 2)
        ctx.stroke()
        ctx.shadowBlur = 0
        ctx.globalAlpha = 1
        ctx.fillStyle = textColor
        ctx.font = `600 ${compact() ? 9 : 11}px system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillText(dimension.label, point.x, point.y + radius + 7)
        ctx.fillStyle = color
        ctx.font = `700 ${compact() ? 9 : 10}px system-ui, sans-serif`
        ctx.fillText(`${Math.round(dimension.score)}`, point.x, point.y - 5)
        ctx.restore()
      })
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const elapsed = animating ? performance.now() - animationStartedAt : 2200
        const settled = clamp((elapsed - 1120) / 700)
        const pulse = animating ? .5 + Math.sin(p.frameCount * .08) * .5 : .35
        drawBackdrop(ctx)
        drawFlows(ctx, settled)
        if (animating) drawParticles(ctx, elapsed)
        drawProfileContour(ctx, settled)
        drawMaterials(ctx, pulse)
        drawDimensions(ctx, pulse)
        if (animating && elapsed > 2050) {
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
      canvas.elt.classList.add('profile-evidence-canvas')
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      p.frameRate(30)
      animationStartedAt = performance.now()
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
    particles = buildParticles(data)
    animationStartedAt = performance.now()
    animating = active && !reducedMotion
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : emptyData()
      const shouldReplay = next.animationRevision > animationRevision
      data = next
      animationRevision = next.animationRevision
      particles = buildParticles(data)
      if (shouldReplay) replay()
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
