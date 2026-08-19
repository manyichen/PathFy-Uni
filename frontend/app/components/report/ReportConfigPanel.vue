<script setup lang="ts">
import { computed } from 'vue'
import type { ReportTarget, ResumeOption } from '~/types/api'

const props = defineProps<{
  collapsed: boolean
  hasReport: boolean
  status: string
  resumes: ResumeOption[]
  resumeId?: number
  goal: string
  targets: ReportTarget[]
  primaryJobId: string
  loading: string
}>()

const emit = defineEmits<{
  'update:resumeId': [value?: number]
  'update:goal': [value: string]
  'open-match': []
  'open-explorer': []
  'open-picker': []
  'remove-target': [index: number]
  'set-primary': [jobId: string]
  'clear-targets': []
  generate: []
}>()

const resumeModel = computed({
  get: () => props.resumeId,
  set: value => emit('update:resumeId', value)
})

const goalModel = computed({
  get: () => props.goal,
  set: value => emit('update:goal', value)
})

const resumeItems = computed(() => props.resumes.map(item => ({
  label: `${item.name || '能力画像'} · ${item.major || '专业待补充'}`,
  value: item.id
})))

const goalItems = [
  { label: '稳妥目标', value: 'fit' },
  { label: '冲刺目标', value: 'stretch' }
]

const sourceActions = [
  {
    key: 'match',
    title: '导入匹配数据',
    desc: '从人岗匹配历史带回岗位、分数和差距',
    icon: 'i-lucide-wand-sparkles',
    primary: true
  },
  {
    key: 'search',
    title: '搜索候选',
    desc: '按岗位、公司、城市直接补充目标',
    icon: 'i-lucide-search'
  },
  {
    key: 'random',
    title: '随机浏览',
    desc: '从岗位库里发现未考虑过的方向',
    icon: 'i-lucide-shuffle'
  },
  {
    key: 'picker',
    title: '手动选择岗位',
    desc: '打开完整岗位库精确添加',
    icon: 'i-lucide-database'
  }
]

function targetKey(item: ReportTarget) {
  return String(item?.job_id || item?.id || '')
}

function triggerSource(key: string) {
  if (key === 'match') emit('open-match')
  else if (key === 'picker') emit('open-picker')
  else emit('open-explorer')
}
</script>

<template>
  <UCard v-if="!collapsed || !hasReport" class="config-cockpit">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-base font-semibold">报告配置</h2>
          <p class="mt-1 text-sm muted">先定目标来源，再选择画像与策略，最后生成一张可继续复盘的报告画布。</p>
        </div>
        <UBadge :label="status" color="neutral" variant="soft" />
      </div>
    </template>

    <div class="report-config">
      <section class="config-block source-block">
        <p class="config-label">1 · 目标来源</p>
        <div class="source-grid">
          <button
            v-for="action in sourceActions"
            :key="action.key"
            type="button"
            class="source-action"
            :class="{ primary: action.primary }"
            :disabled="loading === 'import'"
            @click="triggerSource(action.key)"
          >
            <span class="source-icon">
              <UIcon :name="loading === 'import' && action.key === 'match' ? 'i-lucide-loader-circle' : action.icon" class="size-5" />
            </span>
            <span class="min-w-0">
              <strong>{{ action.title }}</strong>
              <small>{{ action.desc }}</small>
            </span>
          </button>
        </div>
      </section>

      <section class="config-block control-block">
        <p class="config-label">2 · 画像与策略</p>
        <div class="grid gap-2">
          <USelect
            v-model="resumeModel"
            :items="resumeItems"
            placeholder="选择能力画像"
          />
          <USelect
            v-model="goalModel"
            :items="goalItems"
          />
        </div>
      </section>

      <section class="config-block target-block">
        <div class="flex items-center justify-between gap-2">
          <p class="config-label">3 · 已选目标 {{ targets.length }}/5</p>
          <UButton v-if="targets.length" size="xs" color="neutral" variant="ghost" @click="emit('clear-targets')">清空</UButton>
        </div>
        <div class="target-list">
          <article
            v-for="(item, index) in targets"
            :key="targetKey(item)"
            class="selected-job"
          >
            <span class="min-w-0">
              <span class="flex items-center gap-2">
                <strong class="block truncate text-sm">{{ item.title || item.job_id }}</strong>
                <UBadge v-if="targetKey(item) === primaryJobId" label="主目标" color="primary" size="sm" variant="soft" />
              </span>
              <span class="block truncate text-xs muted">
                {{ item.company || '未知公司' }}
                <template v-if="item.location"> · {{ item.location }}</template>
              </span>
            </span>
            <span class="target-actions">
              <UButton
                v-if="targetKey(item) !== primaryJobId"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-star"
                aria-label="设为主目标"
                @click="emit('set-primary', targetKey(item))"
              >主目标</UButton>
              <UButton size="xs" color="neutral" variant="ghost" icon="i-lucide-x" aria-label="移除目标" @click="emit('remove-target', Number(index))" />
            </span>
          </article>
          <div v-if="!targets.length" class="empty-targets">
            <UIcon name="i-lucide-map-plus" class="size-5" />
            <span>尚未选择目标</span>
          </div>
        </div>
      </section>

      <div class="generate-block">
        <p class="config-label">4 · 生成报告</p>
        <p class="mb-3 text-xs leading-5 muted">生成后会自动收起配置，保留目标、计划、公开信息入口和复盘记录。</p>
        <UButton
          size="lg"
          block
          :loading="loading === 'generate' || loading === 'enrich'"
          icon="i-lucide-file-chart-column-increasing"
          @click="emit('generate')"
        >
          {{ loading === 'enrich' ? 'AI 增强中…' : '生成 / 重新生成报告' }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.report-config {
  display: grid;
  gap: 1rem;
}

.config-cockpit {
  overflow: hidden;
}

.config-block {
  min-width: 0;
}

.config-label {
  margin-bottom: 0.55rem;
  color: var(--ui-text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.source-grid {
  display: grid;
  gap: 0.6rem;
}

.source-action {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.7rem;
  align-items: start;
  min-height: 4.6rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--ui-bg-elevated) 72%, transparent);
  padding: 0.8rem;
  text-align: left;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.source-action:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--ui-primary) 42%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-primary) 6%, var(--ui-bg-elevated));
  transform: translateY(-1px);
}

.source-action:disabled {
  cursor: wait;
  opacity: 0.7;
}

.source-action.primary {
  border-color: color-mix(in srgb, var(--ui-primary) 34%, var(--ui-border));
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--ui-primary) 10%, transparent), transparent 60%),
    color-mix(in srgb, var(--ui-bg-elevated) 82%, transparent);
}

.source-icon {
  display: grid;
  width: 2.15rem;
  height: 2.15rem;
  place-items: center;
  border-radius: 0.65rem;
  background: color-mix(in srgb, var(--ui-primary) 12%, var(--ui-bg));
  color: var(--ui-primary);
}

.source-action strong,
.source-action small {
  display: block;
}

.source-action small {
  margin-top: 0.25rem;
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  line-height: 1.45;
}

.target-list {
  display: grid;
  gap: 0.45rem;
}

.selected-job {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border-radius: 0.55rem;
  background: color-mix(in srgb, var(--ui-primary) 7%, transparent);
  padding: 0.45rem 0.6rem;
  text-align: left;
}

.target-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.15rem;
}

.empty-targets {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px dashed var(--ui-border);
  border-radius: 0.75rem;
  padding: 0.85rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

.generate-block {
  align-self: stretch;
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--ui-primary) 18%, var(--ui-border));
  border-radius: 0.8rem;
  background: color-mix(in srgb, var(--ui-primary) 5%, transparent);
  padding: 0.85rem;
}

@media (min-width: 1024px) {
  .report-config {
    grid-template-columns: minmax(20rem, 1.25fr) minmax(14rem, 0.8fr) minmax(18rem, 1fr) minmax(13rem, 0.72fr);
    align-items: stretch;
  }

  .source-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
