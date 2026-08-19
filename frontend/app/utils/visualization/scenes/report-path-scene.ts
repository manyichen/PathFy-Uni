import type { ReportGrowthPoint, ReportPathNode, ReportPathSceneData } from '~/types/report-path'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface Point { x: number; y: number }
interface HitTarget { id: string; month: number; point: Point; label: string; progress?: number; kind: string }

const animationDuration = 1100
const actualColor = '#0f8f87'
const plannedColor = '#4b7fe8'
const adjustmentColor = '#8b6bd8'
const phaseColors = ['rgba(14,116,144,.045)', 'rgba(37,99,235,.035)', 'rgba(124,58,237,.035)', 'rgba(15,118,110,.04)']

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeOutCubic(value: number) {
  return 1 - (1 - value) ** 3
}

function isSceneData(value: unknown): value is ReportPathSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<ReportPathSceneData>
  return Array.isArray(candidate.nodes)
    && Array.isArray(candidate.actualPoints)
    && Array.isArray(candidate.plannedPoints)
    && Array.isArray(candidate.phases)
    && typeof candidate.transitionKey === 'string'
}

function emptyData(): ReportPathSceneData {
  return {
    reportId: 0,
    lineId: '',
    title: '',
    transitionKey: '',
    animationRevision: 0,
    animationKind: 'none',
    selectedMonth: 0,
    currentMonth: 0,
    nodes: [],
    edges: [],
    actualPoints: [{ id: 'origin', month: 0, progress: 0, label: '报告起点', kind: 'origin', selected: true }],
    plannedPoints: [],
    phases: [],
    enrichment: { status: 'completed', label: 'AI 内容已处理' },
    summary: { eventCount: 0, planCount: 0, reviewCount: 0, adjustmentCount: 0, actualPointCount: 0, plannedPointCount: 0, dataState: 'unmeasured' }
  }
}

export const createReportPathScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : emptyData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let animationStartedAt = performance.now()
  let animating = !reducedMotion && data.animationRevision > 0
  let hoveredId = ''
  let failed = false
  let setupComplete = false
  let hitTargets: HitTarget[] = []

  const p5Instance = new P5((p: any) => {
    const geometry = () => ({
      left: p.width < 520 ? 46 : 62,
      right: p.width < 520 ? 18 : 34,
      top: p.width < 520 ? 50 : 54,
      bottom: p.width < 520 ? 44 : 48
    })

    const progress = () => animating
      ? easeOutCubic(clamp((performance.now() - animationStartedAt) / animationDuration))
      : 1

    const theme = () => {
      const styles = getComputedStyle(options.host)
      return {
        text: styles.getPropertyValue('--ui-text').trim() || '#24364d',
        muted: styles.getPropertyValue('--ui-text-muted').trim() || '#65758b',
        border: styles.getPropertyValue('--ui-border').trim() || '#d5dee8'
      }
    }

    const xForMonth = (month: number) => {
      const box = geometry()
      return box.left + clamp(month / 12) * Math.max(1, p.width - box.left - box.right)
    }

    const yForProgress = (value: number) => {
      const box = geometry()
      const height = Math.max(1, p.height - box.top - box.bottom)
      return box.top + (1 - clamp(value / 100)) * height
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createLinearGradient(0, 0, p.width, p.height)
      gradient.addColorStop(0, 'rgba(14,116,144,.035)')
      gradient.addColorStop(.55, 'rgba(255,255,255,0)')
      gradient.addColorStop(1, 'rgba(124,58,237,.035)')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, p.width, p.height)
    }

    const drawPhases = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      const box = geometry()
      const plotHeight = p.height - box.top - box.bottom
      data.phases.forEach((phase, index) => {
        const x = xForMonth(phase.startMonth)
        const end = xForMonth(phase.endMonth)
        ctx.fillStyle = phaseColors[index % phaseColors.length]!
        ctx.fillRect(x, box.top, Math.max(2, end - x), plotHeight)
        if (end - x > 72) {
          ctx.fillStyle = colors.muted
          ctx.font = '600 10px system-ui, sans-serif'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillText(phase.label, x + (end - x) / 2, box.top + 8)
        }
      })
    }

    const drawGrid = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      const box = geometry()
      const bottomY = p.height - box.bottom
      ctx.save()
      ctx.font = `${p.width < 520 ? 9 : 10}px system-ui, sans-serif`
      for (let value = 0; value <= 100; value += 20) {
        const y = yForProgress(value)
        ctx.strokeStyle = value === 0 ? 'rgba(100,116,139,.25)' : 'rgba(100,116,139,.11)'
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(box.left, y); ctx.lineTo(p.width - box.right, y); ctx.stroke()
        ctx.fillStyle = colors.muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(String(value), box.left - 10, y)
      }
      for (let month = 0; month <= 12; month += 1) {
        const x = xForMonth(month)
        ctx.strokeStyle = month % 3 === 0 ? 'rgba(100,116,139,.14)' : 'rgba(100,116,139,.055)'
        ctx.beginPath(); ctx.moveTo(x, box.top); ctx.lineTo(x, bottomY); ctx.stroke()
        if (month % 3 === 0) {
          ctx.fillStyle = colors.muted; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(`${month} 月`, x, bottomY + 13)
        }
      }
      ctx.save(); ctx.translate(14, box.top + (bottomY - box.top) / 2); ctx.rotate(-Math.PI / 2)
      ctx.fillStyle = colors.muted; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.font = '600 10px system-ui, sans-serif'; ctx.fillText('已验证成长指数', 0, 0); ctx.restore()
      ctx.restore()
    }

    const drawCurrentMonth = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      if (data.currentMonth <= 0) return
      const box = geometry()
      const x = xForMonth(data.currentMonth)
      ctx.save()
      ctx.strokeStyle = 'rgba(14,116,144,.42)'; ctx.lineWidth = 1.2; ctx.setLineDash([4, 5])
      ctx.beginPath(); ctx.moveTo(x, box.top); ctx.lineTo(x, p.height - box.bottom); ctx.stroke()
      ctx.setLineDash([]); ctx.fillStyle = actualColor; ctx.font = '700 10px system-ui, sans-serif'; ctx.textAlign = x > p.width - 90 ? 'right' : 'left'; ctx.textBaseline = 'bottom'
      ctx.fillText(`当前计划 · ${Math.round(data.currentMonth)} 月`, x + (ctx.textAlign === 'right' ? -6 : 6), box.top - 8)
      ctx.restore()
    }

    const plotPoint = (point: ReportGrowthPoint): Point => ({ x: xForMonth(point.month), y: yForProgress(point.progress) })

    const drawSeries = (ctx: CanvasRenderingContext2D, points: ReportGrowthPoint[], color: string, dashed: boolean, amount: number) => {
      if (!points.length) return
      const visibleMonth = 12 * amount
      const visible = points.filter(point => point.month <= visibleMonth + .01)
      if (!visible.length) return
      const plot = visible.map(plotPoint)
      ctx.save()
      if (dashed) ctx.setLineDash([7, 6])
      ctx.strokeStyle = color; ctx.lineWidth = dashed ? 2 : 3; ctx.lineJoin = 'round'; ctx.lineCap = 'round'
      if (plot.length > 1) {
        ctx.beginPath(); ctx.moveTo(plot[0]!.x, plot[0]!.y)
        for (const point of plot.slice(1)) ctx.lineTo(point.x, point.y)
        ctx.stroke()
      }
      if (!dashed && plot.length > 1) {
        const bottom = yForProgress(0)
        const gradient = ctx.createLinearGradient(0, Math.min(...plot.map(point => point.y)), 0, bottom)
        gradient.addColorStop(0, 'rgba(15,143,135,.14)'); gradient.addColorStop(1, 'rgba(15,143,135,0)')
        ctx.fillStyle = gradient; ctx.beginPath(); ctx.moveTo(plot[0]!.x, bottom); ctx.lineTo(plot[0]!.x, plot[0]!.y)
        for (const point of plot.slice(1)) ctx.lineTo(point.x, point.y)
        ctx.lineTo(plot.at(-1)!.x, bottom); ctx.closePath(); ctx.fill()
      }
      visible.forEach(point => {
        const position = plotPoint(point)
        const selected = point.selected
        const radius = selected ? 7 : point.kind === 'origin' ? 4.5 : 5.5
        ctx.fillStyle = point.kind === 'origin' ? '#94a3b8' : color; ctx.strokeStyle = selected ? '#172033' : '#fff'; ctx.lineWidth = selected ? 2.2 : 1.5
        ctx.beginPath(); ctx.arc(position.x, position.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
        hitTargets.push({ id: point.id, month: point.month, point: position, label: point.label, progress: point.progress, kind: point.kind })
      })
      ctx.restore()
    }

    const drawEventRail = (ctx: CanvasRenderingContext2D, amount: number, colors: ReturnType<typeof theme>) => {
      const box = geometry()
      const visibleMonth = 12 * amount
      const events = data.nodes.filter(node => node.kind === 'adjustment' || (node.kind === 'plan' && node.progress === undefined))
      events.filter(node => node.month <= visibleMonth + .01).forEach((node, index) => {
        const x = xForMonth(node.month)
        // Events without an explicit progress value live in a separate rail above
        // the score plot. Putting them inside the plot would falsely imply a score.
        const y = 19 + (index % 2) * 15
        const color = node.kind === 'adjustment' ? adjustmentColor : plannedColor
        ctx.save(); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.4
        ctx.beginPath(); ctx.moveTo(x, y - 6); ctx.lineTo(x + 6, y); ctx.lineTo(x, y + 6); ctx.lineTo(x - 6, y); ctx.closePath(); ctx.fill()
        ctx.globalAlpha = .28; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(x, y + 7); ctx.lineTo(x, box.top - 3); ctx.stroke(); ctx.restore()
        hitTargets.push({ id: node.id, month: node.month, point: { x, y }, label: node.label, progress: node.progress, kind: node.kind })
      })

      const activeTarget = hitTargets.find(target => target.id === hoveredId)
        || hitTargets.find(target => Math.round(target.month) === data.selectedMonth && target.kind !== 'origin')
      if (!activeTarget) return
      const rightAligned = activeTarget.point.x > p.width * .67
      const text = `${activeTarget.label}${activeTarget.progress === undefined ? '' : ` · ${Math.round(activeTarget.progress)} 分`}`
      ctx.save(); ctx.font = '650 11px system-ui, sans-serif'
      const width = Math.min(250, ctx.measureText(text).width + 22)
      const x = rightAligned ? activeTarget.point.x - width - 10 : activeTarget.point.x + 10
      const y = clamp(activeTarget.point.y - 31, 8, p.height - 36)
      ctx.fillStyle = 'rgba(15,23,42,.9)'; ctx.beginPath(); ctx.roundRect(x, y, width, 27, 7); ctx.fill()
      ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(text.length > 30 ? `${text.slice(0, 29)}…` : text, x + 11, y + 13.5); ctx.restore()
    }

    const drawLatestLabel = (ctx: CanvasRenderingContext2D) => {
      const latest = data.actualPoints.filter(point => point.kind === 'verified').at(-1)
      if (!latest) return
      const point = plotPoint(latest)
      ctx.save(); ctx.fillStyle = actualColor; ctx.font = '800 12px system-ui, sans-serif'; ctx.textAlign = point.x > p.width - 100 ? 'right' : 'left'; ctx.textBaseline = 'bottom'
      ctx.fillText(`${Math.round(latest.progress)} · 已确认`, point.x + (ctx.textAlign === 'right' ? -9 : 9), point.y - 8); ctx.restore()
    }

    const drawEmptyState = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      if (data.summary.dataState !== 'unmeasured') return
      const box = geometry(); const x = box.left + (p.width - box.left - box.right) / 2; const y = box.top + (p.height - box.top - box.bottom) / 2
      ctx.save(); ctx.textAlign = 'center'; ctx.fillStyle = colors.text; ctx.font = '700 15px system-ui, sans-serif'; ctx.fillText('等待第一次确认复盘', x, y - 8)
      ctx.fillStyle = colors.muted; ctx.font = '11px system-ui, sans-serif'; ctx.fillText('没有真实结果时不绘制预测成长线', x, y + 17); ctx.restore()
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const amount = progress(); const colors = theme(); hitTargets = []
        drawBackdrop(ctx); drawPhases(ctx, colors); drawGrid(ctx, colors); drawCurrentMonth(ctx, colors)
        const planned = data.plannedPoints.length ? [{ ...data.actualPoints[0]!, id: 'planned-origin', kind: 'origin' as const }, ...data.plannedPoints] : []
        drawSeries(ctx, planned, plannedColor, true, amount)
        drawSeries(ctx, data.actualPoints, actualColor, false, amount)
        drawEventRail(ctx, amount, colors); drawLatestLabel(ctx); drawEmptyState(ctx, colors)
        if (animating && amount >= 1) { animating = false; p.noLoop() }
      } catch (error) {
        failed = true; p.noLoop(); options.onError(error)
      }
    }

    const nearestTarget = (x: number, y: number) => hitTargets.find(target => Math.hypot(target.point.x - x, target.point.y - y) <= 15)

    p.setup = () => {
      p.pixelDensity(size.pixelRatio)
      const canvas = p.createCanvas(size.width, size.height)
      canvas.elt.classList.add('report-path-canvas')
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      canvas.elt.addEventListener('click', (event: MouseEvent) => {
        const rect = canvas.elt.getBoundingClientRect()
        const x = (event.clientX - rect.left) * p.width / Math.max(1, rect.width)
        const y = (event.clientY - rect.top) * p.height / Math.max(1, rect.height)
        const target = nearestTarget(x, y)
        const box = geometry()
        const fallbackMonth = Math.round(clamp((x - box.left) / Math.max(1, p.width - box.left - box.right)) * 12)
        options.onSelect({ nodeId: target?.id, month: target?.month ?? fallbackMonth })
      })
      p.frameRate(30); setupComplete = true
      if (!animating) p.noLoop()
    }

    p.draw = render
    p.mouseMoved = () => {
      const next = nearestTarget(p.mouseX, p.mouseY)?.id || ''
      if (next === hoveredId) return
      hoveredId = next; options.host.style.cursor = next ? 'pointer' : 'crosshair'
      if (!animating) p.redraw()
    }
  }, options.host)

  const syncLoop = () => {
    if (!setupComplete) return
    if (active && animating && !reducedMotion) p5Instance.loop()
    else { p5Instance.noLoop(); p5Instance.redraw() }
  }

  const beginAnimation = () => {
    animationStartedAt = performance.now()
    animating = active && !reducedMotion
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : emptyData()
      const replayed = next.animationRevision !== data.animationRevision
      data = next
      if (replayed) beginAnimation(); else p5Instance.redraw()
    },
    resize(nextSize: P5SceneSize) {
      size = nextSize
      if (!setupComplete) return
      p5Instance.pixelDensity(size.pixelRatio); p5Instance.resizeCanvas(size.width, size.height); p5Instance.redraw()
    },
    setActive(nextActive: boolean) { active = nextActive; syncLoop() },
    setReducedMotion(nextReducedMotion: boolean) { reducedMotion = nextReducedMotion; if (reducedMotion) animating = false; syncLoop() },
    resetView() { beginAnimation() },
    destroy() { options.host.style.cursor = ''; p5Instance.remove() }
  }
}
