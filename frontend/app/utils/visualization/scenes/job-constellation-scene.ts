import type { JobConstellationNode, JobConstellationSceneData } from '~/types/job-constellation'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface Point { x: number; y: number }
interface PositionedNode extends Point { node: JobConstellationNode }
interface LayoutNode extends PositionedNode { anchorX: number; anchorY: number }

const animationDuration = 880

function emptyData(): JobConstellationSceneData {
  return {
    nodes: [], groups: [], edges: [], selectedId: '', sourceKind: 'list', resultLabel: '',
    totalAvailable: 0, page: 1, pageSize: 20, transitionKey: '', animationRevision: 0,
    summary: { resultCount: 0, regionCount: 0, minimumRequirement: 0, maximumRequirement: 0 }
  }
}

function isSceneData(value: unknown): value is JobConstellationSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<JobConstellationSceneData>
  return Array.isArray(candidate.nodes) && Array.isArray(candidate.groups) && typeof candidate.transitionKey === 'string'
}

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value))
}

function easeOutCubic(value: number) {
  return 1 - (1 - value) ** 3
}

function hashUnit(value: string, salt: number) {
  let hash = 2166136261 + salt
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return ((hash >>> 0) % 1000) / 999
}

export function layoutJobConstellationNodes(
  data: JobConstellationSceneData,
  width: number,
  height: number
): { nodes: PositionedNode[]; centers: Map<string, Point>; columns: number; rows: number } {
  const groupCount = Math.max(1, data.groups.length)
  const columns = Math.min(3, groupCount)
  const rows = Math.max(1, Math.ceil(groupCount / columns))
  const left = 30
  const right = 30
  const top = 38
  const bottom = 42
  const center = { x: width / 2, y: top + (height - top - bottom) / 2 }
  const orbitX = Math.min(width * (width < 620 ? .3 : .32), 410)
  const orbitY = Math.min(height * .25, 142)
  const centers = new Map<string, Point>()
  data.groups.forEach((group, index) => {
    const angle = -Math.PI / 2 + index / groupCount * Math.PI * 2
    centers.set(group.key, {
      x: center.x + Math.cos(angle) * orbitX,
      y: center.y + Math.sin(angle) * orbitY
    })
  })

  const positioned: LayoutNode[] = data.nodes.map(node => {
    const center = centers.get(node.groupKey) || { x: width / 2, y: height / 2 }
    const jitterAngle = hashUnit(node.id, 109) * Math.PI * 2
    const jitterRadius = 9 + hashUnit(node.id, 211) * Math.min(25, width * .035)
    const anchorX = center.x + node.projectedX * Math.min(100, width * .11) + Math.cos(jitterAngle) * jitterRadius
    const anchorY = center.y - node.projectedY * Math.min(62, height * .13) + Math.sin(jitterAngle) * jitterRadius + 7
    return { node, x: anchorX, y: anchorY, anchorX, anchorY }
  })

  for (let iteration = 0; iteration < 42; iteration += 1) {
    for (const item of positioned) {
      item.x += (item.anchorX - item.x) * .012
      item.y += (item.anchorY - item.y) * .012
    }
    for (let leftIndex = 0; leftIndex < positioned.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < positioned.length; rightIndex += 1) {
        const first = positioned[leftIndex]!
        const second = positioned[rightIndex]!
        let dx = second.x - first.x
        let dy = second.y - first.y
        let distance = Math.hypot(dx, dy)
        const minimumDistance = first.node.radius + second.node.radius + 10
        if (distance >= minimumDistance) continue
        if (distance < .001) {
          const angle = hashUnit(`${first.node.id}:${second.node.id}`, 307) * Math.PI * 2
          dx = Math.cos(angle)
          dy = Math.sin(angle)
          distance = 1
        }
        const movement = (minimumDistance - distance) * .54
        const unitX = dx / distance
        const unitY = dy / distance
        first.x -= unitX * movement
        first.y -= unitY * movement
        second.x += unitX * movement
        second.y += unitY * movement
      }
    }

    for (const item of positioned) {
      const horizontalPadding = item.node.radius + 14
      const verticalPadding = item.node.radius + 14
      const minimumX = left + horizontalPadding
      const maximumX = width - right - horizontalPadding
      const minimumY = top + verticalPadding + 20
      const maximumY = height - bottom - verticalPadding
      item.x = Math.max(minimumX, Math.min(maximumX, item.x))
      item.y = Math.max(minimumY, Math.min(maximumY, item.y))
    }
  }

  return { nodes: positioned, centers, columns, rows }
}

export const createJobConstellationScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : emptyData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let animationStartedAt = performance.now()
  let animating = !reducedMotion && data.nodes.length > 0
  let hoveredId = ''
  let setupComplete = false

  const p5Instance = new P5((p: any) => {
    const layout = () => layoutJobConstellationNodes(data, p.width, p.height)

    const progress = () => animating
      ? easeOutCubic(clamp((performance.now() - animationStartedAt) / animationDuration))
      : 1

    const nearestNode = (x: number, y: number): PositionedNode | undefined => {
      let nearest: PositionedNode | undefined
      let nearestDistance = Number.POSITIVE_INFINITY
      for (const item of layout().nodes) {
        const distance = Math.hypot(x - item.x, y - item.y)
        const hitRadius = Math.max(15, item.node.radius + 6)
        if (distance <= hitRadius && distance < nearestDistance) {
          nearest = item
          nearestDistance = distance
        }
      }
      return nearest
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D, centers: Map<string, Point>) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createRadialGradient(p.width * .5, p.height * .42, 0, p.width * .5, p.height * .42, Math.max(p.width, p.height) * .7)
      gradient.addColorStop(0, 'rgba(56, 189, 248, .07)')
      gradient.addColorStop(.52, 'rgba(129, 140, 248, .035)')
      gradient.addColorStop(1, 'rgba(15, 23, 42, .012)')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, p.width, p.height)
      ctx.save()
      ctx.strokeStyle = 'rgba(125, 211, 252, .09)'
      ctx.setLineDash([3, 8])
      ctx.beginPath()
      ctx.ellipse(p.width / 2, p.height / 2, Math.min(p.width * .32, 410), Math.min(p.height * .25, 142), 0, 0, Math.PI * 2)
      ctx.stroke()
      ctx.setLineDash([])
      for (let index = 0; index < 54; index += 1) {
        const x = 14 + hashUnit(`${data.transitionKey}:${index}`, 401) * (p.width - 28)
        const y = 18 + hashUnit(`${data.transitionKey}:${index}`, 503) * (p.height - 48)
        const radius = .45 + hashUnit(`${index}:${data.transitionKey}`, 607) * 1.15
        ctx.globalAlpha = .14 + hashUnit(`${data.transitionKey}:${index}`, 701) * .3
        ctx.fillStyle = index % 5 === 0 ? '#67e8f9' : '#94a3b8'
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = .16
      ctx.strokeStyle = '#7dd3fc'
      for (const center of centers.values()) {
        ctx.beginPath()
        ctx.moveTo(p.width / 2, p.height / 2)
        ctx.lineTo(center.x, center.y)
        ctx.stroke()
      }
      ctx.restore()
    }

    const drawGroups = (ctx: CanvasRenderingContext2D, centers: Map<string, Point>, amount: number) => {
      const groupByKey = new Map(data.groups.map(group => [group.key, group]))
      for (const [key, center] of centers) {
        const group = groupByKey.get(key)
        if (!group) continue
        const radius = Math.min(104, p.width * .105, p.height * .17)
        const halo = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, Math.max(54, radius))
        halo.addColorStop(0, `${group.color}18`)
        halo.addColorStop(.72, `${group.color}08`)
        halo.addColorStop(1, `${group.color}00`)
        ctx.globalAlpha = (group.count ? 1 : .34) * amount
        ctx.fillStyle = halo
        ctx.beginPath()
        ctx.arc(center.x, center.y, Math.max(54, radius), 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = 'rgba(148, 163, 184, .78)'
        ctx.font = '600 11px ui-sans-serif, system-ui, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(`${group.label} · ${group.count} 颗`, center.x, Math.max(16, center.y - Math.max(42, radius * .72)))
      }
      ctx.globalAlpha = 1
    }

    const drawEdges = (ctx: CanvasRenderingContext2D, positioned: PositionedNode[], amount: number) => {
      const byId = new Map(positioned.map(item => [item.node.id, item]))
      ctx.save()
      ctx.lineWidth = 1
      for (const edge of data.edges) {
        const source = byId.get(edge.source)
        const target = byId.get(edge.target)
        if (!source || !target) continue
        const alpha = (.08 + edge.similarity * .12) * amount
        ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`
        ctx.beginPath()
        ctx.moveTo(source.x, source.y)
        ctx.lineTo(target.x, target.y)
        ctx.stroke()
      }
      ctx.restore()
    }

    const drawNode = (ctx: CanvasRenderingContext2D, item: PositionedNode, amount: number) => {
      const group = data.groups.find(candidate => candidate.key === item.node.groupKey)
      const color = group?.color || '#60a5fa'
      const selected = item.node.id === data.selectedId
      const hovered = item.node.id === hoveredId
      const delay = hashUnit(item.node.id, 131) * .28
      const localAmount = clamp((amount - delay) / Math.max(.05, 1 - delay))
      const radius = item.node.radius * (.3 + .7 * localAmount)
      ctx.save()
      ctx.globalAlpha = .22 + .78 * localAmount
      ctx.shadowColor = color
      ctx.shadowBlur = selected ? 22 : hovered ? 15 : 8
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(item.x, item.y, radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.lineWidth = selected ? 2.5 : hovered ? 1.8 : 1
      ctx.strokeStyle = selected ? '#f8fafc' : `${color}cc`
      ctx.beginPath()
      ctx.arc(item.x, item.y, radius + (selected ? 4 : 2), 0, Math.PI * 2)
      ctx.stroke()
      ctx.restore()
    }

    const drawLabel = (ctx: CanvasRenderingContext2D, item: PositionedNode) => {
      const lines = [item.node.title, `${item.node.company} · ${item.node.location}`, `岗位要求均值 ${Math.round(item.node.requirementAverage)} 分`]
      ctx.save()
      ctx.font = '12px ui-sans-serif, system-ui, sans-serif'
      const width = Math.min(p.width - 24, Math.max(...lines.map(line => ctx.measureText(line).width)) + 24)
      const x = Math.max(12, Math.min(p.width - width - 12, item.x - width / 2))
      const preferAbove = item.y > 88
      const y = preferAbove ? item.y - item.node.radius - 67 : item.y + item.node.radius + 14
      ctx.fillStyle = 'rgba(15, 23, 42, .93)'
      ctx.strokeStyle = 'rgba(148, 163, 184, .28)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.roundRect(x, y, width, 56, 8)
      ctx.fill()
      ctx.stroke()
      ctx.textAlign = 'left'
      ctx.fillStyle = '#f8fafc'
      ctx.font = '600 12px ui-sans-serif, system-ui, sans-serif'
      ctx.fillText(lines[0]!, x + 12, y + 17)
      ctx.fillStyle = '#cbd5e1'
      ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
      ctx.fillText(lines[1]!, x + 12, y + 33)
      ctx.fillStyle = '#94a3b8'
      ctx.fillText(lines[2]!, x + 12, y + 47)
      ctx.restore()
    }

    const drawAxes = (ctx: CanvasRenderingContext2D) => {
      ctx.save()
      ctx.fillStyle = 'rgba(148, 163, 184, .7)'
      ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText('主导能力决定星域', 12, p.height - 12)
      ctx.textAlign = 'right'
      ctx.fillText(`${data.nodes.length} 颗岗位星`, p.width - 12, p.height - 12)
      ctx.textAlign = 'center'
      ctx.fillText('点击星点查看岗位 · 换一片星域随机探索', p.width / 2, p.height - 12)
      ctx.restore()
    }

    const render = () => {
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D
        const amount = progress()
        const current = layout()
        drawBackdrop(ctx, current.centers)
        drawGroups(ctx, current.centers, amount)
        drawEdges(ctx, current.nodes, amount)
        current.nodes.forEach(item => drawNode(ctx, item, amount))
        drawAxes(ctx)
        const focused = current.nodes.find(item => item.node.id === (hoveredId || data.selectedId))
        if (focused) drawLabel(ctx, focused)
        if (animating && amount >= 1) {
          animating = false
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
      canvas.elt.classList.add('job-constellation-canvas')
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      canvas.elt.addEventListener('click', (event: MouseEvent) => {
        const rect = canvas.elt.getBoundingClientRect()
        const x = (event.clientX - rect.left) * p.width / Math.max(1, rect.width)
        const y = (event.clientY - rect.top) * p.height / Math.max(1, rect.height)
        const hit = nearestNode(x, y)
        if (hit) options.onSelect({ jobId: hit.node.id })
      })
      p.frameRate(30)
      setupComplete = true
      if (!animating) p.noLoop()
    }
    p.draw = render
    p.mouseMoved = () => {
      const next = nearestNode(p.mouseX, p.mouseY)?.node.id || ''
      if (next === hoveredId) return
      hoveredId = next
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

  const beginAnimation = () => {
    animationStartedAt = performance.now()
    animating = active && !reducedMotion && data.nodes.length > 0
    syncLoop()
  }

  return {
    update(nextData: unknown) {
      const next = isSceneData(nextData) ? nextData : emptyData()
      const shouldAnimate = next.transitionKey !== data.transitionKey || next.animationRevision !== data.animationRevision
      data = next
      if (shouldAnimate) beginAnimation()
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
      beginAnimation()
    },
    destroy() {
      options.host.style.cursor = ''
      p5Instance.remove()
    }
  }
}
