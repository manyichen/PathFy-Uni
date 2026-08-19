import type { HomeWorkflowSceneData, HomeWorkflowStage, HomeWorkflowStageKey } from '~/types/home-workflow-experience'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { buildHomeWorkflowSceneData } from '../home-workflow-adapter'
import { loadP5 } from '../p5-loader'

interface StagePoint { stage: HomeWorkflowStage; x: number; y: number; index: number }

const transitionDuration = 680

function isSceneData(value: unknown): value is HomeWorkflowSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<HomeWorkflowSceneData>
  return Array.isArray(candidate.stages) && Array.isArray(candidate.edges) && typeof candidate.activeIndex === 'number'
}

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeOutCubic(value: number) {
  return 1 - (1 - value) ** 3
}

function hashUnit(index: number, salt: number) {
  const value = Math.sin((index + 1) * 127.1 + salt * 311.7) * 43758.5453
  return value - Math.floor(value)
}

export const createHomeWorkflowScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : buildHomeWorkflowSceneData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let previousActiveIndex = Math.max(0, data.activeIndex - 1)
  let animationStartedAt = performance.now()
  let animating = !reducedMotion
  let hoveredStage: HomeWorkflowStageKey | '' = ''
  let setupComplete = false

  const p5Instance = new P5((p: any) => {
    const points = (): StagePoint[] => {
      const horizontalPadding = p.width < 560 ? 34 : 58
      const usable = Math.max(1, p.width - horizontalPadding * 2)
      const centerY = p.height * .54
      return data.stages.map((stage, index) => ({
        stage,
        index,
        x: horizontalPadding + usable * index / Math.max(1, data.stages.length - 1),
        y: centerY + Math.sin(index * 1.32 - .7) * Math.min(38, p.height * .095)
      }))
    }

    const progress = () => animating
      ? easeOutCubic(clamp((performance.now() - animationStartedAt) / transitionDuration))
      : 1

    const nearestStage = (x: number, y: number) => points().find(point => Math.hypot(x - point.x, y - point.y) <= 25)

    const drawBackdrop = (ctx: CanvasRenderingContext2D) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createLinearGradient(0, 0, p.width, p.height)
      gradient.addColorStop(0, '#071425')
      gradient.addColorStop(.5, '#10172f')
      gradient.addColorStop(1, '#15112b')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, p.width, p.height)
      for (let index = 0; index < 46; index += 1) {
        const x = hashUnit(index, 1) * p.width
        const y = hashUnit(index, 2) * p.height
        const radius = .4 + hashUnit(index, 3) * 1.2
        ctx.fillStyle = `rgba(186, 230, 253, ${.08 + hashUnit(index, 4) * .24})`
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    const drawForwardPath = (ctx: CanvasRenderingContext2D, stagePoints: StagePoint[], amount: number) => {
      ctx.save()
      ctx.lineCap = 'round'
      for (let index = 0; index < stagePoints.length - 1; index += 1) {
        const source = stagePoints[index]!
        const target = stagePoints[index + 1]!
        const reached = index + 1 <= previousActiveIndex || index + 1 < data.activeIndex
        const entering = index + 1 === data.activeIndex
        const segmentAmount = reached ? 1 : entering ? amount : 0
        const controlX = (source.x + target.x) / 2
        const controlY = Math.min(source.y, target.y) - 25
        ctx.strokeStyle = 'rgba(148, 163, 184, .18)'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(source.x, source.y)
        ctx.quadraticCurveTo(controlX, controlY, target.x, target.y)
        ctx.stroke()
        if (segmentAmount <= 0) continue
        const endX = source.x + (target.x - source.x) * segmentAmount
        const endY = source.y + (target.y - source.y) * segmentAmount
        const glow = ctx.createLinearGradient(source.x, source.y, target.x, target.y)
        glow.addColorStop(0, source.stage.color)
        glow.addColorStop(1, target.stage.color)
        ctx.strokeStyle = glow
        ctx.shadowColor = target.stage.color
        ctx.shadowBlur = 12
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.moveTo(source.x, source.y)
        ctx.quadraticCurveTo(controlX, controlY, endX, endY)
        ctx.stroke()
        ctx.shadowBlur = 0
      }
      ctx.restore()
    }

    const drawFeedback = (ctx: CanvasRenderingContext2D, stagePoints: StagePoint[], amount: number) => {
      if (data.activeIndex < data.stages.length - 1) return
      const review = stagePoints.at(-1)!
      const profile = stagePoints[1]!
      ctx.save()
      ctx.setLineDash([5, 7])
      ctx.lineWidth = 1.5
      ctx.strokeStyle = `rgba(245, 158, 11, ${.18 + amount * .38})`
      ctx.beginPath()
      ctx.moveTo(review.x, review.y + 12)
      ctx.bezierCurveTo(review.x - 40, p.height - 35, profile.x + 60, p.height - 28, profile.x, profile.y + 13)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = 'rgba(251, 191, 36, .78)'
      ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('复盘结果回到画像与计划', (review.x + profile.x) / 2, p.height - 28)
      ctx.restore()
    }

    const drawGlyph = (ctx: CanvasRenderingContext2D, point: StagePoint, radius: number) => {
      const { key } = point.stage
      ctx.save()
      ctx.translate(point.x, point.y)
      ctx.strokeStyle = '#f8fafc'
      ctx.fillStyle = 'rgba(248, 250, 252, .9)'
      ctx.lineWidth = 1.4
      if (key === 'material') {
        for (const offset of [-6, 0, 6]) ctx.strokeRect(offset - 4, -8 + Math.abs(offset) * .25, 8, 14)
      } else if (key === 'profile') {
        ctx.beginPath()
        for (let index = 0; index < 8; index += 1) {
          const angle = -Math.PI / 2 + index * Math.PI / 4
          const x = Math.cos(angle) * radius * .55
          const y = Math.sin(angle) * radius * .55
          if (index === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.closePath()
        ctx.stroke()
      } else if (key === 'match') {
        ctx.beginPath(); ctx.arc(-6, 0, 5, 0, Math.PI * 2); ctx.stroke()
        ctx.beginPath(); ctx.arc(6, 0, 5, 0, Math.PI * 2); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(-1, 0); ctx.lineTo(1, 0); ctx.stroke()
      } else if (key === 'plan') {
        ctx.beginPath(); ctx.moveTo(-9, 7); ctx.lineTo(-2, 0); ctx.lineTo(3, 3); ctx.lineTo(10, -7); ctx.stroke()
        ctx.beginPath(); ctx.arc(-9, 7, 2, 0, Math.PI * 2); ctx.arc(10, -7, 2, 0, Math.PI * 2); ctx.fill()
      } else {
        ctx.beginPath(); ctx.arc(0, 0, 8, -.25, Math.PI * 1.55); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(-8, -5); ctx.lineTo(-9, 2); ctx.lineTo(-3, 0); ctx.fill()
      }
      ctx.restore()
    }

    const drawStage = (ctx: CanvasRenderingContext2D, point: StagePoint, amount: number) => {
      const isActive = point.index === data.activeIndex
      const isReached = point.index <= data.activeIndex
      const isHovered = point.stage.key === hoveredStage
      const activeAmount = isActive ? .55 + .45 * amount : 1
      const radius = (isActive ? 20 : 15) * activeAmount
      ctx.save()
      ctx.globalAlpha = isReached ? 1 : .42
      ctx.shadowColor = point.stage.color
      ctx.shadowBlur = isActive ? 24 : isHovered ? 16 : 8
      ctx.fillStyle = isReached ? point.stage.color : 'rgba(100, 116, 139, .7)'
      ctx.beginPath()
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.lineWidth = isActive ? 2.5 : 1
      ctx.strokeStyle = isActive || isHovered ? '#f8fafc' : 'rgba(226, 232, 240, .5)'
      ctx.beginPath()
      ctx.arc(point.x, point.y, radius + 4, 0, Math.PI * 2)
      ctx.stroke()
      drawGlyph(ctx, point, radius)
      ctx.textAlign = 'center'
      ctx.fillStyle = isActive ? '#f8fafc' : 'rgba(226, 232, 240, .78)'
      ctx.font = `${isActive ? 700 : 600} 12px ui-sans-serif, system-ui, sans-serif`
      ctx.fillText(point.stage.label, point.x, point.y + radius + 23)
      ctx.fillStyle = 'rgba(148, 163, 184, .8)'
      ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
      ctx.fillText(point.stage.hint, point.x, point.y + radius + 38)
      ctx.restore()
    }

    const render = () => {
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const amount = progress()
        const stagePoints = points()
        drawBackdrop(ctx)
        drawForwardPath(ctx, stagePoints, amount)
        drawFeedback(ctx, stagePoints, amount)
        stagePoints.forEach(point => drawStage(ctx, point, amount))
        ctx.fillStyle = 'rgba(186, 230, 253, .65)'
        ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('产品流程演示 · 不读取个人数据', p.width / 2, 22)
        if (animating && amount >= 1) {
          animating = false
          previousActiveIndex = data.activeIndex
          p.noLoop()
        }
      } catch (error) {
        options.onError(error)
        p.noLoop()
      }
    }

    p.setup = () => {
      p.pixelDensity(size.pixelRatio)
      const canvas = p.createCanvas(size.width, size.height)
      canvas.elt.classList.add('home-workflow-experience-canvas')
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      canvas.elt.addEventListener('click', (event: MouseEvent) => {
        const rect = canvas.elt.getBoundingClientRect()
        const x = (event.clientX - rect.left) * p.width / Math.max(1, rect.width)
        const y = (event.clientY - rect.top) * p.height / Math.max(1, rect.height)
        const hit = nearestStage(x, y)
        if (hit) options.onSelect({ stage: hit.stage.key })
      })
      p.frameRate(30)
      setupComplete = true
      if (!animating) p.noLoop()
    }
    p.draw = render
    p.mouseMoved = () => {
      const next = nearestStage(p.mouseX, p.mouseY)?.stage.key || ''
      if (next === hoveredStage) return
      hoveredStage = next
      options.host.style.cursor = next ? 'pointer' : 'default'
      if (!animating) p.redraw()
    }
  }, options.host)

  const syncLoop = () => {
    if (!setupComplete) return
    if (active && animating && !reducedMotion) p5Instance.loop()
    else {
      p5Instance.noLoop()
      p5Instance.redraw()
    }
  }

  const beginAnimation = (fromIndex: number) => {
    previousActiveIndex = fromIndex
    animationStartedAt = performance.now()
    animating = active && !reducedMotion
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : buildHomeWorkflowSceneData()
      const fromIndex = data.activeIndex
      const changed = next.transitionKey !== data.transitionKey
      data = next
      if (changed) beginAnimation(fromIndex)
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
    resetView() {
      beginAnimation(Math.max(0, data.activeIndex - 1))
    },
    destroy() {
      options.host.style.cursor = ''
      p5Instance.remove()
    }
  }
}
