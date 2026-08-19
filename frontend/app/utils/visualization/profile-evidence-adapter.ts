import { capabilityDimensions, capabilityLabels, type CapabilityDimension, type CapabilityScorePatch } from '~/types/capability'
import type { ProfileAnalysis, ProfileEvidenceContributionRecord, ProfileMaterial } from '~/types/profile'
import type {
  ProfileEvidenceDimensionNode,
  ProfileEvidenceFlow,
  ProfileEvidenceMaterialNode,
  ProfileEvidenceSceneData
} from '~/types/profile-evidence'

interface ProfileEvidenceSource {
  materials?: ProfileMaterial[]
  scores?: CapabilityScorePatch
  analysis?: ProfileAnalysis
  animationRevision?: number
}

const dimensionAliases: Record<string, CapabilityDimension> = {
  专业理论: 'cap_req_theory', 理论基础: 'cap_req_theory', 理论: 'cap_req_theory',
  交叉学科: 'cap_req_cross', 跨学科: 'cap_req_cross', 交叉: 'cap_req_cross',
  实践技能: 'cap_req_practice', 实践能力: 'cap_req_practice', 实践: 'cap_req_practice',
  数字素养: 'cap_req_digital', 数字能力: 'cap_req_digital', 数字: 'cap_req_digital',
  创新创业: 'cap_req_innovation', 创新能力: 'cap_req_innovation', 创新: 'cap_req_innovation',
  团队协作: 'cap_req_teamwork', 协作能力: 'cap_req_teamwork', 协作: 'cap_req_teamwork',
  社会网络: 'cap_req_social', 社会能力: 'cap_req_social', 社会: 'cap_req_social',
  学习成长: 'cap_req_growth', 成长能力: 'cap_req_growth', 成长: 'cap_req_growth'
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function number(value: unknown, fallback = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function unitScore(value: unknown): number {
  const parsed = number(value)
  return Math.max(0, Math.min(1, parsed > 1 ? parsed / 100 : parsed))
}

function stableId(value: string, prefix: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `${prefix}:${(hash >>> 0).toString(36)}`
}

function resolveDimension(value: unknown): CapabilityDimension | undefined {
  const name = text(value)
  if ((capabilityDimensions as readonly string[]).includes(name)) return name as CapabilityDimension
  const compact = name.replace(/[\s_-]/g, '')
  const labelMatch = capabilityDimensions.find(dimension => capabilityLabels[dimension].replace(/\s/g, '') === compact)
  return labelMatch || dimensionAliases[compact]
}

function materialNodes(materials: ProfileMaterial[] | undefined): ProfileEvidenceMaterialNode[] {
  const rows = Array.isArray(materials) ? materials : []
  const normalized = rows.map((material, index) => {
    const name = text(material.name, index === 0 ? '补充文本' : `画像材料 ${index + 1}`)
    const explicitId = text(material.id || material.material_id)
    const chars = Math.max(0, number(material.chars || material.character_count))
    return {
      id: explicitId || stableId(`${name}:${index}`, 'material'),
      name,
      kind: text(material.kind || material.type, '材料'),
      status: text(material.status, 'used'),
      chars,
      weight: chars ? Math.max(.45, Math.min(1, .45 + Math.log10(chars + 1) / 7)) : .65
    }
  })

  return normalized.length ? normalized : [{
    id: 'material:combined',
    name: '画像综合材料',
    kind: '综合分析',
    status: 'used',
    chars: 0,
    weight: .72
  }]
}

function dimensionNodes(scores: CapabilityScorePatch | undefined): ProfileEvidenceDimensionNode[] {
  return capabilityDimensions.map(id => ({
    id,
    label: capabilityLabels[id],
    score: Math.max(0, Math.min(100, number(scores?.[id])))
  }))
}

function contributionRows(analysis: ProfileAnalysis | undefined): ProfileEvidenceContributionRecord[] {
  const value = analysis?.capability_evidence_contributions
    || analysis?.evidence_contributions
    || analysis?.material_contributions
  return Array.isArray(value) ? value : []
}

function explicitFlows(
  contributions: ProfileEvidenceContributionRecord[],
  materials: ProfileEvidenceMaterialNode[]
): ProfileEvidenceFlow[] {
  return contributions.flatMap((contribution, index) => {
    const dimension = resolveDimension(contribution.dimension || contribution.capability_dimension || contribution.capabilityDimension)
    if (!dimension) return []
    const requestedId = text(contribution.material_id || contribution.materialId)
    const requestedName = text(contribution.material_name || contribution.materialName)
    const material = materials.find(item => requestedId && item.id === requestedId)
      || materials.find(item => requestedName && item.name === requestedName)
    if (!material) return []
    return [{
      id: `explicit:${index}:${material.id}:${dimension}`,
      materialId: material.id,
      dimension,
      weight: Math.max(.08, unitScore(contribution.weight ?? contribution.contribution ?? contribution.score ?? .5)),
      confidence: contribution.confidence == null ? undefined : unitScore(contribution.confidence),
      excerpt: text(contribution.excerpt) || undefined,
      inferred: false
    }]
  })
}

function overviewFlows(
  materials: ProfileEvidenceMaterialNode[],
  dimensions: ProfileEvidenceDimensionNode[]
): ProfileEvidenceFlow[] {
  return materials.flatMap(material => dimensions.map(dimension => ({
    id: `overview:${material.id}:${dimension.id}`,
    materialId: material.id,
    dimension: dimension.id,
    weight: Math.max(.08, dimension.score / 100) * material.weight,
    inferred: true
  })))
}

export function buildProfileEvidenceSceneData(source: ProfileEvidenceSource): ProfileEvidenceSceneData {
  const materials = materialNodes(source.materials)
  const dimensions = dimensionNodes(source.scores)
  const explicit = explicitFlows(contributionRows(source.analysis), materials)
  const mappingMode = explicit.length ? 'explicit' : 'overview'
  const flows = explicit.length ? explicit : overviewFlows(materials, dimensions)

  return {
    materials,
    dimensions,
    flows,
    mappingMode,
    animationRevision: Math.max(0, Math.floor(number(source.animationRevision))),
    summary: {
      materialCount: materials.length,
      dimensionCount: dimensions.length,
      explicitFlowCount: explicit.length
    }
  }
}
