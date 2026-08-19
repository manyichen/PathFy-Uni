import type {
  CareerGraphData,
  CareerGraphEdge,
  CareerGraphNode,
  CareerGraphNodeKind,
  CareerGraphSource,
  CareerJobReference,
  CareerPromotionStage
} from '~/types/career-graph'

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function score(value: unknown): number | undefined {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return undefined
  return Math.max(0, Math.min(1, parsed > 1 ? parsed / 100 : parsed))
}

function stablePart(value: string): string {
  const normalized = value.trim().toLocaleLowerCase().replace(/\s+/g, '-')
  let hash = 2166136261
  for (let index = 0; index < normalized.length; index += 1) {
    hash ^= normalized.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `${normalized.replace(/[^\p{L}\p{N}-]+/gu, '').slice(0, 32) || 'node'}-${(hash >>> 0).toString(36)}`
}

function jobTitle(job: CareerJobReference | undefined, fallback: string): string {
  return text(job?.title, fallback)
}

export function buildCareerGraphData(source: CareerGraphSource): CareerGraphData {
  const promotionRoutes = Array.isArray(source.promotion?.routes) ? source.promotion.routes : []
  const lateralRoutes = Array.isArray(source.lateral?.routes) ? source.lateral.routes : []
  const inferredCurrent = source.currentJob || source.promotion?.job || source.lateral?.job || source.transition?.from_job
  const currentTitle = jobTitle(inferredCurrent, '当前岗位')
  const currentNodeId = `current:${text(inferredCurrent?.id, stablePart(currentTitle))}`
  const nodes = new Map<string, CareerGraphNode>()
  const edges = new Map<string, CareerGraphEdge>()

  const addNode = (node: CareerGraphNode) => {
    const existing = nodes.get(node.id)
    if (!existing || node.kind === 'target') nodes.set(node.id, { ...existing, ...node })
  }
  const addEdge = (edge: CareerGraphEdge) => {
    if (edge.source !== edge.target) edges.set(edge.id, edge)
  }
  const relationNodeId = (title: string) => `role:${stablePart(title)}`
  const addRelationNode = (title: string, kind: CareerGraphNodeKind, depth: number, routeIndex: number, nodeScore?: number, description?: string) => {
    const id = relationNodeId(title)
    addNode({ id, title, kind, depth, routeIndex, score: nodeScore, description })
    return id
  }

  addNode({
    id: currentNodeId,
    title: currentTitle,
    kind: 'current',
    depth: 0,
    routeIndex: 0,
    description: text(inferredCurrent?.company)
  })

  promotionRoutes.forEach((route, routeIndex) => {
    const stages = Array.isArray(route.stages) ? route.stages : []
    const fallbackNodes: CareerPromotionStage[] = Array.isArray(route.nodes)
      ? route.nodes.slice(1).map((node, index) => ({ role: node.title, stage: index + 1 }))
      : []
    const routeStages = stages.length ? stages : fallbackNodes
    let previousId = currentNodeId
    routeStages.forEach((stage, stageIndex) => {
      const title = text(stage.role, stageIndex === routeStages.length - 1 ? text(route.target_title, '晋升方向') : `晋升阶段 ${stageIndex + 1}`)
      const nodeId = addRelationNode(
        title,
        'promotion',
        stageIndex + 1,
        routeIndex,
        score(route.confidence),
        text(stage.milestone, text(route.rationale))
      )
      addEdge({
        id: `promotion:${previousId}->${nodeId}`,
        source: previousId,
        target: nodeId,
        kind: 'promotion',
        confidence: score(route.confidence),
        description: text(route.route_title, text(route.rationale))
      })
      previousId = nodeId
    })

    if (!routeStages.length && route.target_title) {
      const nodeId = addRelationNode(route.target_title, 'promotion', 1, routeIndex, score(route.confidence), text(route.rationale))
      addEdge({
        id: `promotion:${currentNodeId}->${nodeId}`,
        source: currentNodeId,
        target: nodeId,
        kind: 'promotion',
        confidence: score(route.confidence),
        description: text(route.route_title, text(route.rationale))
      })
    }
  })

  lateralRoutes.forEach((route, routeIndex) => {
    const title = text(route.target_title)
    if (!title) return
    const similarity = score(route.cap_similarity ?? route.score)
    const nodeId = addRelationNode(title, 'lateral', 1, routeIndex, similarity, text(route.rationale))
    addEdge({
      id: `lateral:${currentNodeId}->${nodeId}`,
      source: currentNodeId,
      target: nodeId,
      kind: 'lateral',
      confidence: similarity,
      description: text(route.rationale)
    })
  })

  const transitionTarget = source.targetJob || source.transition?.to_job
  let targetNodeId: string | undefined
  if (transitionTarget) {
    const title = jobTitle(transitionTarget, '目标岗位')
    targetNodeId = relationNodeId(title)
    addNode({
      id: targetNodeId,
      title,
      kind: 'target',
      depth: 1,
      routeIndex: 0,
      description: text(transitionTarget.company)
    })
    addEdge({
      id: `transition:${currentNodeId}->${targetNodeId}`,
      source: currentNodeId,
      target: targetNodeId,
      kind: 'transition',
      description: text(source.transition?.advice?.summary)
    })
  }

  return {
    nodes: [...nodes.values()],
    edges: [...edges.values()],
    currentNodeId,
    targetNodeId,
    summary: {
      promotionCount: promotionRoutes.length,
      lateralCount: lateralRoutes.length,
      hasTransition: Boolean(source.transition && targetNodeId)
    }
  }
}
