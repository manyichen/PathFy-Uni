<script setup lang="ts">
const props = defineProps<{
  resumes: any[]
  targets: any[]
  loading: string
  report?: any
  reviewsCount?: number
}>()

const resumeId = defineModel<number | undefined>('resumeId')
const goal = defineModel<string>('goal', { default: 'fit' })
const reviewPeriod = defineModel<string>('reviewPeriod', { default: '' })
const reviewActivities = defineModel<string>('reviewActivities', { default: '' })
const reviewCapability = defineModel<string>('reviewCapability', { default: '' })
const reviewTarget = defineModel<string>('reviewTarget', { default: '' })
const reviewOutputs = defineModel<string>('reviewOutputs', { default: '' })
const reviewNext = defineModel<string>('reviewNext', { default: '' })

defineEmits<{
  import: []
  pick: []
  removeTarget: [index: number]
  clearTargets: []
  generate: []
  review: []
  viewHistory: []
}>()
</script>

<template>
  <div class="sidebar-stack">
    <UCard>
      <template #header>
        <div><p class="text-xs font-semibold uppercase tracking-wide text-primary">报告来源</p><h2 class="mt-1 font-semibold">导入与生成</h2></div>
      </template>

      <div class="grid gap-5">
        <section>
          <p class="config-label">目标岗位</p>
          <div class="grid grid-cols-2 gap-2">
            <UButton icon="i-lucide-wand-sparkles" :loading="loading === 'import'" block @click="$emit('import')">匹配记录</UButton>
            <UButton color="neutral" variant="soft" icon="i-lucide-search" block @click="$emit('pick')">岗位库</UButton>
          </div>
          <p class="mt-2 text-xs leading-5 muted">优先导入最近一次匹配结果，也可从完整岗位库补充。</p>
        </section>

        <section class="grid gap-2">
          <p class="config-label">画像与策略</p>
          <USelect v-model="resumeId" :items="resumes.map(item => ({ label: `${item.name} · ${item.major}`, value: item.id }))" placeholder="选择能力画像" class="w-full" />
          <USelect v-model="goal" :items="[{label:'稳妥目标',value:'fit'},{label:'冲刺目标',value:'stretch'}]" class="w-full" />
        </section>

        <section>
          <div class="mb-2 flex items-center justify-between gap-2"><p class="config-label mb-0">已选目标 {{ targets.length }}/5</p><UButton v-if="targets.length" size="xs" color="neutral" variant="ghost" @click="$emit('clearTargets')">清空</UButton></div>
          <div class="grid gap-1.5">
            <button v-for="(item, index) in targets" :key="item.job_id" type="button" class="selected-job" @click="$emit('removeTarget', Number(index))">
              <span class="min-w-0"><strong class="block truncate text-sm">{{ item.title || item.job_id }}</strong><span class="block truncate text-xs muted">{{ item.company || '未知公司' }}<template v-if="item.location"> · {{ item.location }}</template></span></span>
              <UIcon name="i-lucide-x" class="shrink-0" />
            </button>
            <span v-if="!targets.length" class="rounded-lg bg-elevated p-3 text-sm muted">尚未选择目标岗位</span>
          </div>
        </section>

        <UButton size="lg" block :loading="loading === 'generate' || loading === 'enrich'" icon="i-lucide-file-chart-column-increasing" @click="$emit('generate')">{{ loading === 'enrich' ? 'AI 增强中…' : '生成 / 更新报告' }}</UButton>
      </div>
    </UCard>

    <UCard v-if="report">
      <template #header>
        <div class="flex items-start justify-between gap-2"><div><p class="text-xs font-semibold uppercase tracking-wide text-primary">周期跟进</p><h2 class="mt-1 font-semibold">本月复盘</h2></div><UBadge v-if="reviewsCount" :label="`${reviewsCount} 次`" color="neutral" variant="soft" /></div>
      </template>
      <p class="mb-4 text-xs leading-5 muted">六项均为必填。尽量提供日期、进度百分比、匹配分变化和成果数量，系统才能稳定比较前后变化。</p>
      <div class="grid gap-4">
        <UFormField label="本周期 *" hint="必须写具体日期、月份或第几周">
          <UInput v-model="reviewPeriod" placeholder="例如：7 月 1 日—7 月 14 日 / 第 3—4 周" class="w-full" />
        </UFormField>
        <UFormField label="做过的事 *" hint="至少 20 字，写清做到哪一步">
          <UTextarea v-model="reviewActivities" :rows="3" autoresize :maxrows="7" placeholder="学习、实习、项目、比赛、课程等；具体做了什么、完成到什么程度。" class="w-full" />
        </UFormField>
        <UFormField label="能力短板 *" hint="写明变强与仍薄弱的部分，建议包含百分比">
          <UTextarea v-model="reviewCapability" :rows="3" autoresize :maxrows="7" placeholder="哪块变强了、哪块还弱；例如“接口设计大概改善了 30%”。" class="w-full" />
        </UFormField>
        <UFormField label="和目标岗位 *" hint="明确更好、持平或更难，建议填写匹配分变化">
          <UTextarea v-model="reviewTarget" :rows="3" autoresize :maxrows="7" placeholder="简历或匹配感受；例如“更贴近后端岗位，感觉多了 5 分”。" class="w-full" />
        </UFormField>
        <UFormField label="能拿得出手的成果 *" hint="必须包含至少一个数量">
          <UTextarea v-model="reviewOutputs" :rows="3" autoresize :maxrows="7" placeholder="例如：上线项目 1 个、比赛获奖 1 次、技术文章 2 篇、证书 1 张。" class="w-full" />
        </UFormField>
        <UFormField label="卡点与下周打算 *" hint="分别写当前最卡和下周最想推进的一件事">
          <UTextarea v-model="reviewNext" :rows="3" autoresize :maxrows="7" placeholder="当前最卡：…；下周优先推进：…" class="w-full" />
        </UFormField>
      </div>
      <div class="mt-4 grid gap-2">
        <UButton block :loading="loading === 'review'" @click="$emit('review')">提交复盘并更新计划</UButton>
        <UButton v-if="reviewsCount" color="neutral" variant="ghost" size="sm" icon="i-lucide-history" @click="$emit('viewHistory')">查看历史复盘</UButton>
      </div>
      <div v-if="report.evaluation?.latest_review" class="mt-4 rounded-lg bg-elevated p-3">
        <div class="flex items-center justify-between gap-2"><strong class="text-xs">最近复盘</strong><UBadge :label="`通过率 ${Math.round((report.evaluation.latest_review.evaluation?.pass_rate || 0) * 100)}%`" size="sm" variant="soft" /></div>
        <p v-if="report.evaluation.latest_review.llm_extract?.summary" class="mt-2 line-clamp-3 text-xs leading-5 muted">{{ report.evaluation.latest_review.llm_extract.summary }}</p>
      </div>
    </UCard>
  </div>
</template>

<style scoped>
.sidebar-stack { display: grid; gap: 1rem; align-content: start; }
.config-label { margin-bottom: .5rem; font-size: .7rem; font-weight: 700; color: var(--ui-text-muted); text-transform: uppercase; letter-spacing: .06em; }
.selected-job { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: .5rem; border-radius: .6rem; background: color-mix(in srgb, var(--ui-primary) 7%, transparent); padding: .5rem .6rem; text-align: left; transition: background .15s ease; }
.selected-job:hover { background: color-mix(in srgb, var(--ui-primary) 13%, transparent); }
</style>
