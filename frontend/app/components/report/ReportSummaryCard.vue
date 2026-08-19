<script setup lang="ts">
import { computed } from 'vue'
import type { CareerReport, ReportRefreshScope } from '~/types/api'

const props = defineProps<{
  reportId?: number
  report: CareerReport
  goal: string
}>()
const emit = defineEmits<{ refresh: [scope: ReportRefreshScope] }>()

const generatedAt = computed(() => String(props.report.generated_at || '').replace('T', ' ').slice(0, 19) || '刚刚生成')
const reportTargets = computed(() => props.report.targets || [])
const planCount = computed(() => props.report.plans_by_target?.length || 0)
const lineCount = computed(() => props.report.development_lines?.lines?.length || 0)
const metricCount = computed(() => props.report.evaluation?.metrics?.length || 0)
const goalLabel = computed(() => props.goal === 'stretch' ? '冲刺目标' : '稳妥目标')
const quality = computed(() => props.report.enrichment_quality)
const qualityLabel = computed(() => {
  if (!quality.value) return ''
  const status = { accepted: 'AI 内容已通过', repaired: 'AI 内容已修正', fallback: '当前为规则版' }[quality.value.status]
  return `${status} · ${Math.round(quality.value.score)} 分`
})
const qualityDescription = computed(() => quality.value?.status === 'repaired'
  ? '部分空泛、无依据或不一致内容已由程序修正后再展示。'
  : quality.value?.status === 'fallback'
    ? '本次 AI 输出未达到质量门槛，已自动保留可执行的确定性报告。'
    : '')

const strategyText = computed(() => {
  return props.report.narrative?.text
    || props.report.summary
    || props.report.overview
    || '这份报告以能力画像为起点，对照目标岗位的真实要求，将差距拆成可执行的阶段任务。建议先完成近期里程碑并留下作品、证书或项目证据，再通过每月复盘持续校准路线。'
})

const insightTiles = computed(() => [
  {
    label: '目标方向',
    value: `${reportTargets.value.length || 0} 个`,
    icon: 'i-lucide-target',
    hint: reportTargets.value[0]?.display_title || reportTargets.value[0]?.title || '等待目标沉淀'
  },
  {
    label: '成长计划',
    value: `${planCount.value} 组`,
    icon: 'i-lucide-list-checks',
    hint: '短期补基础，中期做项目，长期形成成果'
  },
  {
    label: '复盘指标',
    value: `${metricCount.value} 项`,
    icon: 'i-lucide-activity',
    hint: lineCount.value ? `${lineCount.value} 条发展线正在跟踪` : '生成报告后可继续月度复盘'
  }
])
</script>

<template>
  <UCard class="report-brief-card">
    <div class="report-brief">
      <div class="brief-copy">
        <div class="brief-kicker">
          <span>报告 #{{ reportId || '-' }}</span>
          <i />
          <span>{{ generatedAt }}</span>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <h2 class="text-xl font-semibold">发展策略摘要</h2>
          <UBadge :label="goalLabel" variant="soft" />
          <UBadge v-if="qualityLabel" :label="qualityLabel" :color="quality?.status === 'accepted' ? 'success' : quality?.status === 'repaired' ? 'warning' : 'neutral'" variant="soft" />
        </div>
        <p class="brief-text">{{ strategyText }}</p>
        <UAlert v-if="qualityDescription" class="mt-3" :color="quality?.status === 'repaired' ? 'warning' : 'neutral'" variant="soft" title="内容质量保护已生效" :description="qualityDescription" />
        <div v-if="reportId" class="mt-3 flex flex-wrap gap-2" aria-label="报告分区刷新">
          <UButton size="sm" color="neutral" variant="soft" icon="i-lucide-message-square-text" @click="emit('refresh', 'narrative')">仅刷新文案</UButton>
          <UButton size="sm" color="neutral" variant="soft" icon="i-lucide-library" @click="emit('refresh', 'resources')">仅刷新资源</UButton>
          <UButton size="sm" color="neutral" variant="soft" icon="i-lucide-list-restart" @click="emit('refresh', 'plan')">仅重排计划</UButton>
        </div>
      </div>

      <aside class="brief-rail" aria-label="报告线索">
        <div v-for="tile in insightTiles" :key="tile.label" class="brief-tile">
          <div class="brief-tile-icon">
            <UIcon :name="tile.icon" class="size-4" />
          </div>
          <div class="min-w-0">
            <span>{{ tile.label }}</span>
            <strong>{{ tile.value }}</strong>
            <p>{{ tile.hint }}</p>
          </div>
        </div>
      </aside>
    </div>

    <div class="strategy-lane">
      <div class="strategy-step">
        <span>01</span>
        <strong>先看差距</strong>
        <p>对照你的水平、岗位期望和待提升量，确定优先补齐的维度。</p>
      </div>
      <div class="strategy-step">
        <span>02</span>
        <strong>再做成果</strong>
        <p>把课程学习转成项目、竞赛、证书或作品集，而不是只记录学习时长。</p>
      </div>
      <div class="strategy-step">
        <span>03</span>
        <strong>每月复盘</strong>
        <p>记录能力和成果变化，发展线会随复盘结果更新并调整下月任务。</p>
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.report-brief-card {
  overflow: hidden;
}

.report-brief {
  display: grid;
  gap: 1rem;
}

.brief-copy {
  min-width: 0;
}

.brief-kicker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  color: var(--ui-primary);
  font-size: 0.75rem;
  font-weight: 700;
}

.brief-kicker i {
  width: 0.25rem;
  height: 0.25rem;
  border-radius: 999px;
  background: currentColor;
}

.brief-text {
  margin-top: 0.9rem;
  max-width: 62rem;
  white-space: pre-wrap;
  color: var(--ui-text-muted);
  line-height: 1.85;
}

.brief-rail {
  display: grid;
  gap: 0.7rem;
}

.brief-tile {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
  border: 1px solid color-mix(in srgb, var(--ui-primary) 22%, var(--ui-border));
  border-radius: 0.8rem;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--ui-primary) 8%, transparent), transparent 54%),
    color-mix(in srgb, var(--ui-bg-elevated) 78%, transparent);
  padding: 0.85rem;
}

.brief-tile-icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 0.65rem;
  background: color-mix(in srgb, var(--ui-primary) 14%, var(--ui-bg));
  color: var(--ui-primary);
}

.brief-tile span {
  display: block;
  color: var(--ui-text-muted);
  font-size: 0.72rem;
}

.brief-tile strong {
  display: block;
  margin-top: 0.1rem;
  font-size: 1.1rem;
}

.brief-tile p {
  margin-top: 0.25rem;
  overflow: hidden;
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-lane {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
  border-top: 1px solid var(--ui-border);
  padding-top: 1rem;
}

.strategy-step {
  position: relative;
  border-left: 3px solid color-mix(in srgb, var(--ui-primary) 45%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-primary) 5%, transparent);
  padding: 0.75rem 0.85rem 0.75rem 1rem;
}

.strategy-step span {
  color: var(--ui-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.72rem;
  font-weight: 800;
}

.strategy-step strong {
  display: block;
  margin-top: 0.2rem;
}

.strategy-step p {
  margin-top: 0.35rem;
  color: var(--ui-text-muted);
  font-size: 0.78rem;
  line-height: 1.65;
}

@media (min-width: 768px) {
  .strategy-lane {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .report-brief {
    grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.34fr);
    align-items: start;
  }
}
</style>
