<script setup lang="ts">
import type { CapabilityDimension, PublicInfoState, ReportTarget } from '~/types/api'
import { safeExternalUrl } from '~/utils/external-url'

const props = defineProps<{
  targets: ReportTarget[]
  publicInfo: Record<string, PublicInfoState>
}>()

const emit = defineEmits<{
  'load-public-info': [target: ReportTarget, forceRefresh?: boolean]
}>()

const dimensionLabels: Record<CapabilityDimension, string> = {
  cap_req_theory: '理论',
  cap_req_cross: '交叉',
  cap_req_practice: '实践',
  cap_req_digital: '数字',
  cap_req_innovation: '创新',
  cap_req_teamwork: '协作',
  cap_req_social: '社会',
  cap_req_growth: '成长'
}

function targetKey(item: ReportTarget) {
  return String(item?.job_id || item?.id || '')
}

function publicState(item: ReportTarget) {
  return props.publicInfo[targetKey(item)]
}

function targetTitle(item: ReportTarget) {
  return item.display_title || [item.title, item.company].filter(Boolean).join(' · ') || item.id || item.job_id
}

function targetMeta(item: ReportTarget) {
  return [item.location, item.salary].filter(Boolean).join(' · ') || '岗位信息待补充'
}

function sourceUrl(value: unknown) { return safeExternalUrl(value) }

function gapEntries(item: ReportTarget) {
  const gaps = item.match_preview?.dimension_gaps || {}
  return Object.entries(gaps)
    .map(([key, value]) => ({
      key,
      label: dimensionLabels[key as CapabilityDimension] || key,
      value: Number(value || 0)
    }))
    .sort((a, b) => b.value - a.value)
}

const targetInsight = computed(() => {
  const scores = props.targets
    .map(item => Number(item.match_preview?.match_score || 0))
    .filter(score => score > 0)
  const averageScore = scores.length
    ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
    : 0
  const allGaps = props.targets.flatMap(item => gapEntries(item))
  const topGap = allGaps.sort((a, b) => b.value - a.value)[0]
  const bestTarget = [...props.targets].sort((a, b) => Number(b.match_preview?.match_score || 0) - Number(a.match_preview?.match_score || 0))[0]

  return {
    targetCount: props.targets.length,
    averageScore,
    topGapLabel: topGap ? `${topGap.label} ${Math.round(topGap.value)} 分` : '暂无明显差距',
    bestTitle: bestTarget ? targetTitle(bestTarget) : '等待选择目标'
  }
})
</script>

<template>
  <section>
    <div class="section-heading">
      <h2>目标与能力差距</h2>
      <p>每个目标展示匹配分、图谱信号、近期公开信息和最需要补齐的维度。</p>
    </div>

    <div class="target-insights">
      <article>
        <span>目标数</span>
        <strong>{{ targetInsight.targetCount }}/5</strong>
        <p>建议保留 2-5 个方向，便于比较不同路线的准备成本。</p>
      </article>
      <article>
        <span>平均匹配</span>
        <strong>{{ targetInsight.averageScore || '-' }}</strong>
        <p>匹配分越高，当前画像与岗位要求越贴近。</p>
      </article>
      <article>
        <span>首要差距</span>
        <strong>{{ targetInsight.topGapLabel }}</strong>
        <p>优先把最大差距转成项目、证书或可展示成果。</p>
      </article>
      <article class="wide">
        <span>当前最贴近</span>
        <strong>{{ targetInsight.bestTitle }}</strong>
        <p>招聘可见度看岗位样本活跃度，发展路径看晋升与换岗宽度，资源密度看课程和竞赛可关联数量。</p>
      </article>
    </div>

    <div class="target-grid">
      <UCard v-for="item in targets" :key="targetKey(item)" class="target-card">
        <div class="target-topline">
          <div class="min-w-0">
            <h3 class="truncate font-semibold">{{ targetTitle(item) }}</h3>
            <p class="text-sm muted">{{ targetMeta(item) }}</p>
          </div>
          <div class="score-badge">
            <strong>{{ Math.round(item.match_preview?.match_score || 0) }}</strong>
            <span>匹配</span>
          </div>
        </div>

        <div v-if="item.track_profile" class="metric-row">
          <div class="metric">
            <strong>{{ Math.round(item.track_profile.hiring_visibility_0_100 || 0) }}</strong>
            <span>招聘可见度</span>
          </div>
          <div class="metric">
            <strong>{{ Math.round(item.track_profile.path_breadth_0_100 || 0) }}</strong>
            <span>发展路径</span>
          </div>
          <div class="metric">
            <strong>{{ Math.round(item.track_profile.resource_density_0_100 || 0) }}</strong>
            <span>资源密度</span>
          </div>
        </div>

        <div class="gap-stack">
          <div
            v-for="gap in gapEntries(item).slice(0, 4)"
            :key="gap.key"
            class="gap-row"
          >
            <span>{{ gap.label }}</span>
            <UProgress :model-value="Math.max(0, gap.value)" :max="100" />
            <span class="text-right">{{ gap.value.toFixed(0) }}</span>
          </div>
          <p v-if="!gapEntries(item).length" class="text-sm muted">暂无维度差距数据</p>
        </div>

        <div class="public-block">
          <div class="flex flex-wrap gap-2">
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-globe-2"
              :loading="publicState(item)?.loading"
              @click="emit('load-public-info', item)"
            >
              查看近期公开信息
            </UButton>
            <UButton
              v-if="publicState(item)?.data"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-refresh-cw"
              :loading="publicState(item)?.loading"
              @click="emit('load-public-info', item, true)"
            >
              重新检索
            </UButton>
          </div>
          <UAlert
            v-if="publicState(item)?.error"
            class="mt-3"
            color="error"
            variant="soft"
            icon="i-lucide-triangle-alert"
            :title="publicState(item)?.error"
          />
          <div v-if="publicState(item)?.data" class="public-info">
            <p>{{ publicState(item)?.data?.summary || '暂无摘要' }}</p>
            <div v-if="publicState(item)?.data?.sources?.length" class="mt-2 flex flex-wrap gap-2">
              <a
                v-for="source in publicState(item)?.data?.sources"
                v-show="sourceUrl(source.url)"
                :key="source.url || source.title"
                :href="sourceUrl(source.url)"
                target="_blank"
                rel="noopener noreferrer"
                class="source-link"
              >
                {{ source.title || '来源' }}
              </a>
            </div>
          </div>
        </div>
      </UCard>
    </div>
  </section>
</template>

<style scoped>
.section-heading {
  margin: 0.25rem 0 0.8rem;
}

.section-heading h2 {
  font-size: 1.2rem;
  font-weight: 700;
}

.section-heading p {
  margin-top: 0.2rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

.target-insights {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.target-insights article {
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--ui-primary) 18%, var(--ui-border));
  border-radius: 0.8rem;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--ui-primary) 8%, transparent), transparent 58%),
    color-mix(in srgb, var(--ui-bg-elevated) 72%, transparent);
  padding: 0.85rem;
}

.target-insights span {
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.target-insights strong {
  display: block;
  margin-top: 0.2rem;
  overflow: hidden;
  font-size: 1.15rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.target-insights p {
  margin-top: 0.35rem;
  color: var(--ui-text-muted);
  font-size: 0.75rem;
  line-height: 1.6;
}

.target-grid {
  display: grid;
  gap: 0.75rem;
}

.target-card {
  position: relative;
  overflow: hidden;
}

.target-card::before {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--ui-primary), color-mix(in srgb, var(--ui-primary) 35%, #f59e0b));
}

.target-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.85rem;
}

.score-badge {
  display: grid;
  width: 3.35rem;
  height: 3.35rem;
  flex-shrink: 0;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--ui-primary) 28%, var(--ui-border));
  border-radius: 0.8rem;
  background: color-mix(in srgb, var(--ui-primary) 8%, transparent);
}

.score-badge strong {
  color: var(--ui-primary);
  font-size: 1.35rem;
  line-height: 1;
}

.score-badge span {
  color: var(--ui-text-muted);
  font-size: 0.65rem;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
  margin-top: 1rem;
  text-align: center;
}

.metric {
  display: grid;
  border-radius: 0.6rem;
  background: color-mix(in srgb, var(--ui-primary) 5%, var(--ui-bg-elevated));
  padding: 0.55rem 0.25rem;
}

.metric strong {
  font-size: 1rem;
}

.metric span {
  color: var(--ui-text-muted);
  font-size: 0.65rem;
}

.gap-stack {
  display: grid;
  gap: 0.55rem;
  margin-top: 1rem;
}

.gap-row {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr) 2.5rem;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
}

.public-block {
  margin-top: 1rem;
  border-top: 1px solid var(--ui-border);
  padding-top: 0.85rem;
}

.public-info {
  margin-top: 0.75rem;
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--ui-primary) 6%, var(--ui-bg-elevated));
  padding: 0.8rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
  line-height: 1.7;
}

.source-link {
  border-radius: 999px;
  background: var(--ui-bg);
  color: var(--ui-primary);
  padding: 0.25rem 0.55rem;
  font-size: 0.75rem;
}

@media (min-width: 768px) {
  .target-insights {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .target-insights .wide {
    grid-column: 1 / -1;
  }

  .target-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1180px) {
  .target-insights {
    grid-template-columns: 0.75fr 0.75fr 1fr 1.5fr;
  }

  .target-insights .wide {
    grid-column: auto;
  }
}
</style>
