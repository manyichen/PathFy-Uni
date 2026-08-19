import type { CareerGraphData, CareerGraphEdge, CareerGraphNode, CareerGraphNodeKind } from '~/types/career-graph'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface Point { x: number; y: number }
interface PositionedNode extends CareerGraphNode, Point { radius: number }

const kindColor: Record<CareerGraphNodeKind, string> = {
  current: '#f8fafc',
  promotion: '#38bdf8',
  lateral: '#2dd4bf',
  target: '#fbbf24'
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.max(minimum, Math.min(maximum, value))
}

function shortLabel(value: string, maxLength = 11) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}…` : value
}

function emptyGraph(): CareerGraphData {
  return {
    nodes: [],
    edges: [],
    currentNodeId: '',
    summary: { promotionCount: 0, lateralCount: 0, hasTransition: false }
  }
}

function isCareerGraphData(value: unknown): value is CareerGraphData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<CareerGraphData>
  return Array.isArray(candidate.nodes) && Array.isArray(candidate.edges)
}

function layoutNodes(data: CareerGraphData, size: P5SceneSize): PositionedNode[] {
  const promotion = data.nodes.filter(node => node.kind === 'promotion')
  const lateral = data.nodes.filter(node => node.kind === 'lateral')
  const promotionRouteCount = Math.max(1, ...promotion.map(node => node.routeIndex + 1))
  const maxDepth = Math.max(1, ...promotion.map(node => node.depth))
  const availableWidth = Math.max(360, size.width / 1.15)
  const laneGap = Math.min(170, availableWidth / Math.max(2.4, promotionRouteCount))

  return data.nodes.map(node => {
    const confidence = node.score ?? 0.55
    const radius = node.kind === 'current' ? 24 : node.kind === 'target' ? 22 : 14 + confidence * 5
    if (node.kind === 'current') return { ...node, x: 0, y: 36, radius }
    if (node.kind === 'target') return { ...node, x: Math.min(310, size.width * 0.29), y: 28, radius }
    if (node.kind === 'promotion') {
      const lane = node.routeIndex - (promotionRouteCount - 1) / 2
      return {
        ...node,
        x: lane * laneGap + Math.sin(node.depth * 1.7 + node.routeIndex) * 16,
        y: 36 - node.depth * Math.min(118, Math.max(82, (size.height - 110) / maxDepth)),
        radius
      }
    }
    const lateralIndex = lateral.findIndex(item => item.id === node.id)
    const angle = lateral.length <= 1 ? Math.PI / 2 : Math.PI * (.12 + lateralIndex / (lateral.length - 1) * .76)
    const spread = Math.min(270, size.width * .3)
    return {
      ...node,
      x: Math.cos(angle) * spread,
      y: 80 + Math.sin(angle) * Math.min(155, size.height * .22),
      radius
    }
  })
}

export const createCareerGraphScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isCareerGraphData(options.data) ? options.data : emptyGraph()
  let size = options.size
  let positioned = layoutNodes(data, size)
  let active = true
  let reducedMotion = options.reducedMotion
  let selectedId = data.currentNodeId
  let hoveredId = ''
  let zoom = 1
  let pan: Point = { x: 0, y: 0 }
  let dragStart: Point | undefined
  let panStart: Point = { x: 0, y: 0 }
  let pressedNodeId = ''
  let moved = false
  let failed = false
  let renderedSuccessfully = false
  let staticRecovery = false
  let destroyed = false
  let setupComplete = false
  let detachCanvasInteractions = () => {}

  const usesStaticFrame = () => reducedMotion || staticRecovery

  const p5Instance = new P5((p: any) => {
    const screenCenter = () => ({ x: p.width / 2, y: p.height * .54 })
    const screenPoint = (point: Point) => {
      const center = screenCenter()
      return { x: center.x + pan.x + point.x * zoom, y: center.y + pan.y + point.y * zoom }
    }
    const worldPoint = (point: Point) => {
      const center = screenCenter()
      return { x: (point.x - center.x - pan.x) / zoom, y: (point.y - center.y - pan.y) / zoom }
    }
    const nodeAt = (x: number, y: number) => {
      const point = worldPoint({ x, y })
      return [...positioned].reverse().find(node => Math.hypot(node.x - point.x, node.y - point.y) <= node.radius + 8 / zoom)
    }
    const edgePoints = (edge: CareerGraphEdge) => {
      const from = positioned.find(node => node.id === edge.source)
      const to = positioned.find(node => node.id === edge.target)
      return from && to ? { from, to } : undefined
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D) => {
      const style = getComputedStyle(options.host)
      const primary = style.getPropertyValue('--ui-primary').trim() || '#0891b2'
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createRadialGradient(p.width * .5, p.height * .48, 0, p.width * .5, p.height * .48, Math.max(p.width, p.height) * .7)
      gradient.addColorStop(0, 'rgba(14, 165, 233, .1)')
      gradient.addColorStop(.58, 'rgba(15, 23, 42, .025)')
      gradient.addColorStop(1, 'rgba(15, 23, 42, .16)')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, p.width, p.height)

      ctx.fillStyle = primary
      for (let index = 0; index < 54; index += 1) {
        const x = ((index * 83 + 29) % 997) / 997 * p.width
        const y = ((index * 137 + 53) % 991) / 991 * p.height
        const pulse = usesStaticFrame() ? .2 : .14 + Math.sin(p.frameCount * .035 + index) * .07
        ctx.globalAlpha = pulse
        ctx.beginPath()
        ctx.arc(x, y, index % 7 === 0 ? 1.3 : .7, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    const drawEdge = (ctx: CanvasRenderingContext2D, edge: CareerGraphEdge, index: number) => {
      const points = edgePoints(edge)
      if (!points) return
      const from = screenPoint(points.from)
      const to = screenPoint(points.to)
      const selected = selectedId === edge.source || selectedId === edge.target
      const relatedToHover = !hoveredId || hoveredId === edge.source || hoveredId === edge.target
      const color = edge.kind === 'promotion' ? kindColor.promotion : edge.kind === 'lateral' ? kindColor.lateral : kindColor.target
      const controlX = (from.x + to.x) / 2
      const controlY = (from.y + to.y) / 2 + (edge.kind === 'lateral' ? 22 : 0)
      ctx.save()
      ctx.strokeStyle = color
      ctx.globalAlpha = relatedToHover ? (selected ? .88 : .42) : .09
      ctx.lineWidth = (1.1 + (edge.confidence ?? .45) * 1.6) * Math.min(1.2, zoom)
      ctx.shadowColor = color
      ctx.shadowBlur = selected ? 10 : 4
      ctx.beginPath()
      ctx.moveTo(from.x, from.y)
      ctx.quadraticCurveTo(controlX, controlY, to.x, to.y)
      ctx.stroke()

      if (!usesStaticFrame() && relatedToHover) {
        const amount = (p.frameCount * .006 + index * .19) % 1
        const inverse = 1 - amount
        const pulseX = inverse * inverse * from.x + 2 * inverse * amount * controlX + amount * amount * to.x
        const pulseY = inverse * inverse * from.y + 2 * inverse * amount * controlY + amount * amount * to.y
        ctx.globalAlpha = selected ? .95 : .65
        ctx.fillStyle = '#fff'
        ctx.shadowBlur = 12
        ctx.beginPath()
        ctx.arc(pulseX, pulseY, selected ? 2.2 : 1.5, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.restore()
    }

    const drawNode = (ctx: CanvasRenderingContext2D, node: PositionedNode) => {
      const point = screenPoint(node)
      const radius = node.radius * zoom
      const selected = node.id === selectedId
      const hovered = node.id === hoveredId
      const dimmed = hoveredId && !hovered && !data.edges.some(edge => (edge.source === hoveredId && edge.target === node.id) || (edge.target === hoveredId && edge.source === node.id))
      const color = kindColor[node.kind]
      ctx.save()
      ctx.globalAlpha = dimmed ? .22 : 1
      ctx.fillStyle = color
      ctx.strokeStyle = selected ? '#fff' : color
      ctx.shadowColor = color
      ctx.shadowBlur = selected || hovered ? 24 : 12
      ctx.lineWidth = selected ? 2.2 : 1.2
      ctx.beginPath()
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.globalAlpha = dimmed ? .14 : .26
      ctx.beginPath()
      ctx.arc(point.x, point.y, radius + (selected ? 9 : 5), 0, Math.PI * 2)
      ctx.stroke()
      if (selected) {
        ctx.globalAlpha = .42
        ctx.beginPath()
        ctx.arc(point.x, point.y, radius + 15 + Math.sin(p.frameCount * .05) * 3, 0, Math.PI * 2)
        ctx.stroke()
      }
      ctx.shadowBlur = 0
      ctx.globalAlpha = dimmed ? .24 : .92
      ctx.fillStyle = getComputedStyle(options.host).getPropertyValue('--ui-text').trim() || '#e2e8f0'
      ctx.font = `${selected ? 700 : 600} ${clamp(11 * zoom, 10, 13)}px system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(shortLabel(node.title), point.x, point.y + radius + 9)
      ctx.restore()
    }

    const drawLegend = (ctx: CanvasRenderingContext2D) => {
      const items: Array<[CareerGraphNodeKind, string]> = [['current', '当前'], ['promotion', '晋升'], ['lateral', '横向'], ['target', '目标']]
      ctx.save()
      ctx.font = '11px system-ui, sans-serif'
      ctx.textBaseline = 'middle'
      items.forEach(([kind, label], index) => {
        const x = 18 + index * 68
        ctx.globalAlpha = .9
        ctx.fillStyle = kindColor[kind]
        ctx.beginPath()
        ctx.arc(x, 22, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = getComputedStyle(options.host).getPropertyValue('--ui-text-muted').trim() || '#94a3b8'
        ctx.fillText(label, x + 9, 22)
      })
      ctx.restore()
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        drawBackdrop(ctx)
        data.edges.forEach((edge, index) => drawEdge(ctx, edge, index))
        positioned.forEach(node => drawNode(ctx, node))
        drawLegend(ctx)
        renderedSuccessfully = true
      } catch (error) {
        if (renderedSuccessfully && !staticRecovery) {
          staticRecovery = true
          p.noLoop()
          options.onError(error, { recoverable: true, phase: 'render' })
          Promise.resolve().then(() => {
            if (!destroyed) p.redraw()
          })
          return
        }
        failed = true
        p.noLoop()
        options.onError(error, { phase: 'render' })
      }
    }

    p.setup = () => {
      p.pixelDensity(size.pixelRatio)
      const canvas = p.createCanvas(size.width, size.height)
      const canvasElement = canvas.elt as HTMLCanvasElement
      canvasElement.classList.add('career-graph-canvas')
      canvasElement.setAttribute('aria-hidden', 'true')
      canvasElement.setAttribute('role', 'presentation')
      canvasElement.style.touchAction = 'none'
      canvasElement.style.userSelect = 'none'

      const eventPoint = (event: PointerEvent | WheelEvent): Point => {
        const bounds = canvasElement.getBoundingClientRect()
        return {
          x: (event.clientX - bounds.left) * p.width / Math.max(1, bounds.width),
          y: (event.clientY - bounds.top) * p.height / Math.max(1, bounds.height)
        }
      }
      const updateHover = (point: Point) => {
        const next = nodeAt(point.x, point.y)?.id || ''
        if (next !== hoveredId) {
          hoveredId = next
          if (usesStaticFrame()) p.redraw()
        }
        options.host.style.cursor = next ? 'pointer' : dragStart ? 'grabbing' : 'grab'
      }
      const onPointerMove = (event: PointerEvent) => {
        const point = eventPoint(event)
        if (!dragStart) {
          updateHover(point)
          return
        }

        const dx = point.x - dragStart.x
        const dy = point.y - dragStart.y
        if (Math.hypot(dx, dy) > 4) moved = true
        if (!pressedNodeId || moved) pan = { x: panStart.x + dx, y: panStart.y + dy }
        hoveredId = ''
        options.host.style.cursor = 'grabbing'
        if (usesStaticFrame()) p.redraw()
        event.preventDefault()
      }
      const onPointerDown = (event: PointerEvent) => {
        if (!event.isPrimary || event.button !== 0) return
        const point = eventPoint(event)
        dragStart = point
        panStart = { ...pan }
        pressedNodeId = nodeAt(point.x, point.y)?.id || ''
        moved = false
        options.host.style.cursor = pressedNodeId ? 'pointer' : 'grabbing'
        canvasElement.setPointerCapture(event.pointerId)
        event.preventDefault()
      }
      const finishPointerInteraction = (event: PointerEvent) => {
        const point = eventPoint(event)
        if (dragStart && !moved && pressedNodeId) {
          const node = positioned.find(item => item.id === pressedNodeId)
          if (node) {
            selectedId = node.id
            options.onSelect({ ...node })
          }
        }
        dragStart = undefined
        pressedNodeId = ''
        moved = false
        if (canvasElement.hasPointerCapture(event.pointerId)) canvasElement.releasePointerCapture(event.pointerId)
        updateHover(point)
        if (usesStaticFrame()) p.redraw()
      }
      const onPointerLeave = () => {
        if (dragStart) return
        hoveredId = ''
        options.host.style.cursor = 'grab'
        if (usesStaticFrame()) p.redraw()
      }
      const onWheel = (event: WheelEvent) => {
        const point = eventPoint(event)
        const before = worldPoint(point)
        zoom = clamp(zoom * (event.deltaY > 0 ? .9 : 1.1), .68, 1.75)
        const after = screenPoint(before)
        pan.x += point.x - after.x
        pan.y += point.y - after.y
        if (usesStaticFrame()) p.redraw()
        event.preventDefault()
      }

      canvasElement.addEventListener('pointermove', onPointerMove)
      canvasElement.addEventListener('pointerdown', onPointerDown)
      canvasElement.addEventListener('pointerup', finishPointerInteraction)
      canvasElement.addEventListener('pointercancel', finishPointerInteraction)
      canvasElement.addEventListener('pointerleave', onPointerLeave)
      canvasElement.addEventListener('wheel', onWheel, { passive: false })
      detachCanvasInteractions = () => {
        canvasElement.removeEventListener('pointermove', onPointerMove)
        canvasElement.removeEventListener('pointerdown', onPointerDown)
        canvasElement.removeEventListener('pointerup', finishPointerInteraction)
        canvasElement.removeEventListener('pointercancel', finishPointerInteraction)
        canvasElement.removeEventListener('pointerleave', onPointerLeave)
        canvasElement.removeEventListener('wheel', onWheel)
      }
      p.frameRate(30)
      setupComplete = true
      if (usesStaticFrame()) p.noLoop()
    }
    p.draw = render
  }, options.host)

  options.host.style.cursor = 'grab'

  const redrawOrLoop = () => {
    if (active && !usesStaticFrame()) p5Instance.loop()
    else {
      p5Instance.noLoop()
      p5Instance.redraw()
    }
  }

  return {
    update(nextData: unknown) {
      data = isCareerGraphData(nextData) ? nextData : emptyGraph()
      const requestedSelection = data.selectedNodeId || selectedId
      selectedId = data.nodes.some(node => node.id === requestedSelection) ? requestedSelection : data.currentNodeId
      positioned = layoutNodes(data, size)
      p5Instance.redraw()
    },
    resize(nextSize: P5SceneSize) {
      size = nextSize
      positioned = layoutNodes(data, size)
      if (!setupComplete) return
      p5Instance.pixelDensity(size.pixelRatio)
      p5Instance.resizeCanvas(size.width, size.height)
      p5Instance.redraw()
    },
    setActive(nextActive: boolean) {
      active = nextActive
      redrawOrLoop()
    },
    setReducedMotion(nextReducedMotion: boolean) {
      reducedMotion = nextReducedMotion
      redrawOrLoop()
    },
    resetView() {
      zoom = 1
      pan = { x: 0, y: 0 }
      selectedId = data.currentNodeId
      p5Instance.redraw()
    },
    destroy() {
      destroyed = true
      detachCanvasInteractions()
      p5Instance.remove()
      options.host.style.cursor = ''
    }
  }
}
